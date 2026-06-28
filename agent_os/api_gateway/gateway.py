"""
Agent OS V6.0 - API Gateway
FastAPI-based API Gateway with all routes, middleware, authentication
"""
import time
import uuid
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends, Header, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from agent_os.config import get_config
from agent_os.core_platform.exceptions import AgentOSException
from agent_os.core_platform.base import ServiceContext
from agent_os.infra.observability import get_observability
from agent_os.api_gateway.security import security, get_current_user, get_optional_user
from agent_os.api_gateway.rate_limiter import get_rate_limiter
from agent_os.api_gateway.ws_manager import get_ws_manager

logger = logging.getLogger(__name__)


# ─── Models ───────────────────────────────────────────

class LoginRequest(BaseModel):
    tenant_id: str = Field(..., description="Tenant ID")
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")


class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z0-9-]+$")
    tier: str = Field(default="free")
    region: Optional[str] = None


class AgentRegisterRequest(BaseModel):
    tenant_id: str
    owner_id: str
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    agent_type: str = "chat"
    system_prompt: str = ""
    price_model: str = "free"
    price: float = 0.0
    tags: Optional[list] = None
    category: str = ""


class AgentExecuteRequest(BaseModel):
    agent_id: str
    user_input: str
    user_id: str = ""
    tenant_id: str = ""


class WorkflowRunRequest(BaseModel):
    workflow_id: str
    input_data: Optional[Dict[str, Any]] = None


class MarketplaceListRequest(BaseModel):
    category: str = ""
    search: str = ""
    sort_by: str = "newest"
    limit: int = 50
    offset: int = 0


class BillingReportRequest(BaseModel):
    tenant_id: str


class PluginRegisterRequest(BaseModel):
    tenant_id: str
    developer_id: str
    name: str
    description: str = ""
    plugin_type: str = "tool"
    price: float = 0.0
    price_model: str = "free"
    code: str = ""


class PluginInstallRequest(BaseModel):
    tenant_id: str
    plugin_id: str


class IdentityCreateRequest(BaseModel):
    tenant_id: str
    username: str
    email: str
    password: str


# ─── App Factory ──────────────────────────────────────

def create_app() -> FastAPI:

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Agent OS V6.0 API Gateway starting...")
        await _init_services()
        yield
        logger.info("Agent OS V6.0 API Gateway shutting down...")

    app = FastAPI(
        title="Agent OS V6.0 - Capital Grade AI Agent Economy Platform",
        description="Multi-Region, Multi-Tenant, Event-Driven AI Agent Operating System",
        version="6.0.0",
        lifespan=lifespan,
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "filter": True,
        },
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handler
    @app.exception_handler(AgentOSException)
    async def agent_os_exception_handler(request: Request, exc: AgentOSException):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": "HTTP_ERROR", "message": exc.detail}})

    # ─── Middleware ────────────────────────────────────
    # IMPORTANT: Starlette middleware runs in LIFO order (last added runs first).
    # Order: tenant_isolation (innermost) → auth → rate_limit → observability (outermost)

    @app.middleware("http")
    async def tenant_isolation_middleware(request: Request, call_next):
        """Ensure tenant isolation - all data access must be tenant-scoped (innermost, runs last)"""
        public_paths = ["/health", "/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/tenant", "/docs", "/openapi.json", "/metrics"]
        public_prefixes = ["/docs", "/api/v1/observability", "/api/v1/marketplace"]
        if request.url.path in public_paths or any(request.url.path.startswith(p) for p in public_prefixes) or "/tenant" in request.url.path:
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", "")
        if not tenant_id:
            if "/marketplace" in request.url.path:
                return await call_next(request)
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "TENANT_REQUIRED", "message": "Tenant context required for this operation"}},
            )

        return await call_next(request)

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        # Skip auth for public endpoints
        public_paths = ["/health", "/api/v1/auth/login", "/api/v1/auth/register", "/docs", "/openapi.json", "/metrics"]
        if request.url.path in public_paths or request.url.path.startswith("/docs"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            from agent_os.core_platform.identity import get_iam_service
            iam = get_iam_service()
            decoded = iam.decode_jwt(token)
            if decoded:
                request.state.user_id = decoded.get("sub", "")
                request.state.tenant_id = decoded.get("tenant_id", "")
                request.state.user_roles = decoded.get("roles", [])
            else:
                return JSONResponse(status_code=401, content={"error": {"code": "UNAUTHORIZED", "message": "Invalid token"}})

        return await call_next(request)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        """Rate limiting middleware based on tenant tier"""
        public_paths = ["/health", "/docs", "/openapi.json", "/metrics"]
        if request.url.path in public_paths or request.url.path.startswith("/docs"):
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", "")
        if tenant_id:
            limiter = get_rate_limiter()
            allowed, info = await limiter.check_rate_limit(tenant_id)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please slow down.",
                            "retry_after": int(info.get("reset_at", time.time() + 60) - time.time()),
                        }
                    },
                    headers={"X-RateLimit-Limit": str(info["limit"]), "Retry-After": str(int(info.get("reset_at", time.time() + 60) - time.time()))},
                )

        response = await call_next(request)
        return response

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        request.state.trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        request.state.tenant_id = request.headers.get("X-Tenant-ID", "")

        response = await call_next(request)

        latency = (time.time() - start_time) * 1000
        obs = get_observability()
        obs.record_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency,
            tenant_id=request.state.tenant_id,
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{latency:.2f}ms"
        return response

    def get_service_context(request: Request) -> ServiceContext:
        return ServiceContext(
            request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
            trace_id=getattr(request.state, "trace_id", str(uuid.uuid4())),
            tenant_id=getattr(request.state, "tenant_id", ""),
            user_id=getattr(request.state, "user_id", ""),
        )

    # ─── Health Check ──────────────────────────────────

    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "service": "Agent OS API Gateway",
            "version": "6.0.0",
            "timestamp": time.time(),
        }

    @app.get("/metrics")
    async def metrics():
        obs = get_observability()
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=obs.get_prometheus_metrics())

    @app.get("/api/v1/observability/traces")
    async def traces_list(
        tenant_id: str = Header(default="", alias="X-Tenant-ID"),
        limit: int = 50,
    ):
        from agent_os.infra.observability import get_trace_manager
        tm = get_trace_manager()
        return tm.list_traces(tenant_id, limit)

    @app.get("/api/v1/observability/traces/{trace_id}")
    async def trace_get(trace_id: str):
        from agent_os.infra.observability import get_trace_manager
        tm = get_trace_manager()
        trace = tm.get_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")
        return trace.to_dict()

    @app.get("/api/v1/observability/traces/{trace_id}/graph")
    async def trace_graph(trace_id: str):
        """Execution trace graph for visualization"""
        from agent_os.infra.observability import get_trace_manager
        tm = get_trace_manager()
        graph = tm.get_execution_graph(trace_id)
        if not graph:
            raise HTTPException(status_code=404, detail="Trace not found")
        return graph

    @app.get("/api/v1/observability/latency")
    async def latency_metrics(
        tenant_id: str = Header(default="", alias="X-Tenant-ID"),
    ):
        from agent_os.infra.observability import get_trace_manager
        tm = get_trace_manager()
        return tm.get_latency_metrics(tenant_id)

    @app.get("/api/v1/observability/tokens")
    async def token_usage_stats(
        tenant_id: str = Header(default="", alias="X-Tenant-ID"),
    ):
        from agent_os.infra.observability import get_trace_manager
        tm = get_trace_manager()
        return tm.get_token_usage_stats(tenant_id)

    @app.get("/api/v1/observability/active-traces")
    async def active_traces():
        from agent_os.infra.observability import get_trace_manager
        tm = get_trace_manager()
        return tm.get_active_traces()

    # ─── Auth Routes ───────────────────────────────────

    @app.post("/api/v1/auth/login")
    async def auth_login(req: LoginRequest, ctx: ServiceContext = Depends(get_service_context)):
        from agent_os.services.auth_service import get_auth_service
        svc = get_auth_service()
        return await svc.login(req.tenant_id, req.email, req.password, ctx)

    @app.post("/api/v1/auth/register")
    async def auth_register(req: IdentityCreateRequest, ctx: ServiceContext = Depends(get_service_context)):
        from agent_os.services.auth_service import get_auth_service
        svc = get_auth_service()
        return await svc.register(req.tenant_id, req.username, req.email, req.password, ctx)

    @app.get("/api/v1/auth/me")
    async def auth_me(current_user: dict = Depends(get_current_user)):
        """获取当前登录用户信息（需要 Bearer Token）"""
        from agent_os.core_platform.identity import get_iam_service
        iam = get_iam_service()
        identity = await iam.get_identity(current_user["user_id"])
        return identity.to_dict()

    # ─── Tenant Routes ─────────────────────────────────

    @app.post("/api/v1/tenant/create")
    async def tenant_create(req: TenantCreateRequest, ctx: ServiceContext = Depends(get_service_context)):
        from agent_os.core_platform.tenant_global import get_tenant_manager, TenantTier
        tm = get_tenant_manager()
        tier = TenantTier(req.tier) if isinstance(req.tier, str) else req.tier
        tenant = await tm.create_tenant(req.name, req.slug, tier, req.region, ctx)
        return tenant.to_dict()

    @app.get("/api/v1/tenant/{tenant_id}")
    async def tenant_get(tenant_id: str):
        from agent_os.core_platform.tenant_global import get_tenant_manager
        tm = get_tenant_manager()
        tenant = await tm.get_tenant(tenant_id)
        return tenant.to_dict()

    @app.get("/api/v1/tenant")
    async def tenant_list(region: Optional[str] = None):
        from agent_os.core_platform.tenant_global import get_tenant_manager
        tm = get_tenant_manager()
        tenants = await tm.list_tenants(region)
        return [t.to_dict() for t in tenants]

    # ─── Agent Routes ──────────────────────────────────

    @app.post("/api/v1/agent/register")
    async def agent_register(
        req: AgentRegisterRequest,
        ctx: ServiceContext = Depends(get_service_context),
        current_user: dict = Depends(get_current_user),
    ):
        from agent_os.services.agent_service import get_agent_service
        svc = get_agent_service()
        return await svc.register_agent(
            tenant_id=req.tenant_id, owner_id=req.owner_id,
            name=req.name, description=req.description,
            agent_type=req.agent_type, system_prompt=req.system_prompt,
            price_model=req.price_model, price=req.price,
            tags=req.tags, category=req.category, ctx=ctx,
        )

    @app.get("/api/v1/agent/{agent_id}")
    async def agent_get(agent_id: str):
        from agent_os.services.agent_service import get_agent_service
        svc = get_agent_service()
        return await svc.get_agent(agent_id)

    @app.get("/api/v1/agent")
    async def agent_list(
        tenant_id: Optional[str] = None, limit: int = 50, offset: int = 0
    ):
        from agent_os.services.agent_service import get_agent_service
        svc = get_agent_service()
        return await svc.list_agents(tenant_id, limit, offset)

    @app.post("/api/v1/agent/execute")
    async def agent_execute(
        req: AgentExecuteRequest,
        ctx: ServiceContext = Depends(get_service_context),
        current_user: dict = Depends(get_current_user),
    ):
        from agent_os.services.agent_service import get_agent_service
        svc = get_agent_service()
        return await svc.execute_agent(req.agent_id, req.user_input, req.user_id, req.tenant_id, ctx)

    @app.post("/api/v1/agent/execute/stream")
    async def agent_execute_stream(
        req: AgentExecuteRequest,
        ctx: ServiceContext = Depends(get_service_context),
        current_user: dict = Depends(get_current_user),
    ):
        """Stream agent execution output as Server-Sent Events (SSE)"""
        from agent_os.ai_layer.agent_runtime_v3 import get_agent_runtime
        import json as _json

        runtime = get_agent_runtime()
        async def generate():
            async for event in runtime.execute_agent_stream(
                req.agent_id, req.user_input, req.user_id, req.tenant_id, ctx
            ):
                yield f"data: {_json.dumps(event, default=str)}\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream")

    # ─── WebSocket Routes ──────────────────────────────

    @app.websocket("/ws/agent/execute")
    async def ws_agent_execute(websocket: WebSocket):
        """WebSocket endpoint for real-time agent execution streaming"""
        ws_mgr = get_ws_manager()
        conn = await ws_mgr.connect(websocket)

        try:
            from agent_os.ai_layer.agent_runtime_v3 import get_agent_runtime
            runtime = get_agent_runtime()

            while True:
                data = await websocket.receive_json()
                agent_id = data.get("agent_id", "")
                user_input = data.get("user_input", "")
                user_id = data.get("user_id", "")
                tenant_id = data.get("tenant_id", "")

                if not agent_id or not user_input:
                    await websocket.send_json({"type": "error", "message": "agent_id and user_input required"})
                    continue

                # Update connection metadata
                conn.tenant_id = tenant_id
                conn.user_id = user_id

                async for event in runtime.execute_agent_stream(
                    agent_id, user_input, user_id, tenant_id
                ):
                    await websocket.send_json(event)
        except WebSocketDisconnect:
            logger.info("WS agent execute client disconnected")
        except Exception as e:
            logger.error(f"WS agent execute error: {e}")
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            await ws_mgr.disconnect(conn.connection_id)

    @app.websocket("/ws/events")
    async def ws_events(websocket: WebSocket):
        """WebSocket endpoint for real-time event streaming (Command Center)"""
        ws_mgr = get_ws_manager()
        conn = await ws_mgr.connect(websocket)

        from agent_os.core_platform.event_bus import EventBus

        async def event_handler(event):
            try:
                await websocket.send_json({
                    "type": "event",
                    "event_type": event.event_type,
                    "payload": event.payload,
                    "tenant_id": event.tenant_id,
                    "timestamp": event.timestamp,
                })
            except Exception:
                pass

        bus = EventBus.get_instance_sync()
        topics = ["agent_os.agent.events", "agent_os.workflow.events", "agent_os.system.events"]
        for topic in topics:
            await bus._broker.subscribe(topic, event_handler)

        try:
            while True:
                data = await websocket.receive_text()
                # Allow client to filter by tenant
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "subscribe" and msg.get("tenant_id"):
                        conn.tenant_id = msg["tenant_id"]
                except Exception:
                    pass
        except WebSocketDisconnect:
            logger.info("WS events client disconnected")
        finally:
            await ws_mgr.disconnect(conn.connection_id)

    @app.websocket("/ws/command-center")
    async def ws_command_center(websocket: WebSocket):
        """WebSocket for Command Center: real-time agent status, logs, token usage, execution feed"""
        ws_mgr = get_ws_manager()
        conn = await ws_mgr.connect(websocket)

        from agent_os.core_platform.event_bus import EventBus
        import json as _json

        async def broadcast_event(event):
            """Forward events to command center with tenant filtering"""
            try:
                # Only send events matching the connection's tenant
                if conn.tenant_id and event.tenant_id and conn.tenant_id != event.tenant_id:
                    return
                await websocket.send_json({
                    "type": "event",
                    "stream": event.event_type,
                    "data": event.payload,
                    "timestamp": event.timestamp,
                })
            except Exception:
                pass

        bus = EventBus.get_instance_sync()
        # Subscribe to all relevant event topics
        all_topics = [
            "agent_os.agent.events",
            "agent_os.workflow.events",
            "agent_os.billing.events",
            "agent_os.system.events",
        ]
        for topic in all_topics:
            await bus._broker.subscribe(topic, broadcast_event)

        # Send initial stats
        from agent_os.ai_layer.agent_runtime_v3 import get_agent_runtime
        runtime = get_agent_runtime()
        stats = await runtime.health_check()
        await websocket.send_json({
            "type": "system_stats",
            "data": stats,
            "connections": (await ws_mgr.get_stats())["total_connections"],
        })

        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = _json.loads(data)
                    if msg.get("type") == "set_tenant":
                        conn.tenant_id = msg.get("tenant_id", "")
                        await websocket.send_json({
                            "type": "tenant_set",
                            "tenant_id": conn.tenant_id,
                        })
                except Exception:
                    pass
        except WebSocketDisconnect:
            logger.info("Command Center client disconnected")
        finally:
            await ws_mgr.disconnect(conn.connection_id)

    @app.get("/api/v1/agent/{agent_id}/executions")
    async def agent_executions(agent_id: str, limit: int = 50):
        from agent_os.services.agent_service import get_agent_service
        svc = get_agent_service()
        return await svc.list_executions(agent_id, limit)

    @app.post("/api/v1/agent/{agent_id}/publish")
    async def agent_publish(agent_id: str, ctx: ServiceContext = Depends(get_service_context)):
        from agent_os.services.agent_service import get_agent_service
        svc = get_agent_service()
        return await svc.publish_agent(agent_id, ctx)

    @app.post("/api/v1/agent/{agent_id}/purchase")
    async def agent_purchase(
        agent_id: str,
        buyer_tenant_id: str = Header(..., alias="X-Tenant-ID"),
        buyer_user_id: str = Header(..., alias="X-User-ID"),
        ctx: ServiceContext = Depends(get_service_context),
    ):
        from agent_os.services.agent_service import get_agent_service
        svc = get_agent_service()
        return await svc.purchase_agent(agent_id, buyer_tenant_id, buyer_user_id, ctx)

    @app.post("/api/v1/agent/{agent_id}/review")
    async def agent_review(
        agent_id: str,
        rating: int = Query(..., ge=1, le=5),
        comment: str = "",
        ctx: ServiceContext = Depends(get_service_context),
    ):
        from agent_os.services.agent_service import get_agent_service
        svc = get_agent_service()
        return await svc.add_review(agent_id, ctx.tenant_id, ctx.user_id, rating, comment, ctx)

    # ─── Marketplace Routes ────────────────────────────

    @app.get("/api/v1/marketplace/list")
    async def marketplace_list(
        category: str = "", search: str = "", sort_by: str = "newest",
        limit: int = 50, offset: int = 0,
    ):
        from agent_os.services.marketplace_service import get_marketplace_service
        svc = get_marketplace_service()
        return await svc.list_agent_marketplace(category, search, sort_by, limit, offset)

    @app.get("/api/v1/marketplace/featured")
    async def marketplace_featured():
        from agent_os.services.marketplace_service import get_marketplace_service
        svc = get_marketplace_service()
        return await svc.get_featured_agents()

    @app.get("/api/v1/marketplace/categories")
    async def marketplace_categories():
        from agent_os.services.marketplace_service import get_marketplace_service
        svc = get_marketplace_service()
        return await svc.get_agent_categories()

    @app.get("/api/v1/marketplace/plugins")
    async def marketplace_plugins(
        category: str = "", search: str = "", sort_by: str = "newest",
        limit: int = 50, offset: int = 0,
    ):
        from agent_os.services.marketplace_service import get_marketplace_service
        svc = get_marketplace_service()
        return await svc.list_plugin_marketplace(category, search, sort_by, limit, offset)

    # ─── Plugin Routes ─────────────────────────────────

    @app.post("/api/v1/plugin/register")
    async def plugin_register(
        req: PluginRegisterRequest,
        ctx: ServiceContext = Depends(get_service_context),
        current_user: dict = Depends(get_current_user),
    ):
        from agent_os.core_platform.plugin_runtime import get_plugin_runtime
        svc = get_plugin_runtime()
        return await svc.register_plugin(
            tenant_id=req.tenant_id, developer_id=req.developer_id,
            name=req.name, description=req.description,
            plugin_type=req.plugin_type, price=req.price,
            price_model=req.price_model, code=req.code, ctx=ctx,
        )

    @app.get("/api/v1/plugin/{plugin_id}")
    async def plugin_get(plugin_id: str):
        from agent_os.core_platform.plugin_runtime import get_plugin_runtime
        svc = get_plugin_runtime()
        plugin = await svc.get_plugin(plugin_id)
        return plugin.to_dict()

    @app.post("/api/v1/plugin/install")
    async def plugin_install(req: PluginInstallRequest, ctx: ServiceContext = Depends(get_service_context)):
        from agent_os.core_platform.plugin_runtime import get_plugin_runtime
        svc = get_plugin_runtime()
        return await svc.install_plugin(req.tenant_id, req.plugin_id, ctx)

    @app.get("/api/v1/plugin/{tenant_id}/installed")
    async def plugin_installed(tenant_id: str):
        from agent_os.core_platform.plugin_runtime import get_plugin_runtime
        svc = get_plugin_runtime()
        plugins = await svc.get_installed_plugins(tenant_id)
        return [p.to_dict() for p in plugins]

    # ─── Billing Routes ────────────────────────────────

    @app.get("/api/v1/billing/report")
    async def billing_report(
        tenant_id: str = Header(..., alias="X-Tenant-ID"),
        current_user: dict = Depends(get_current_user),
    ):
        from agent_os.services.billing_service import get_billing_service
        svc = get_billing_service()
        return await svc.get_revenue_report(tenant_id)

    @app.get("/api/v1/billing/balance")
    async def billing_balance(
        tenant_id: str = Header(..., alias="X-Tenant-ID"),
        current_user: dict = Depends(get_current_user),
    ):
        from agent_os.services.billing_service import get_billing_service
        svc = get_billing_service()
        return await svc.get_balance(tenant_id)

    @app.get("/api/v1/billing/usage")
    async def billing_usage(
        tenant_id: str = Header(..., alias="X-Tenant-ID"), limit: int = 100
    ):
        from agent_os.services.billing_service import get_billing_service
        svc = get_billing_service()
        return await svc.get_usage_records(tenant_id, limit)

    @app.post("/api/v1/billing/subscription")
    async def billing_subscription(
        tier: str = Query(...),
        period: str = "monthly",
        tenant_id: str = Header(..., alias="X-Tenant-ID"),
        ctx: ServiceContext = Depends(get_service_context),
    ):
        from agent_os.services.billing_service import get_billing_service
        svc = get_billing_service()
        return await svc.create_subscription(tenant_id, tier, period, ctx)

    # ─── Workflow Routes ───────────────────────────────

    @app.get("/api/v1/workflow")
    async def workflow_list(
        tenant_id: str = Header(default="", alias="X-Tenant-ID"),
    ):
        from agent_os.services.workflow_service import get_workflow_service
        svc = get_workflow_service()
        workflows = await svc.list_workflows(tenant_id)
        return [w.to_dict() for w in workflows]

    @app.post("/api/v1/workflow/create")
    async def workflow_create(
        name: str = Query(...), description: str = "",
        tenant_id: str = Header(..., alias="X-Tenant-ID"),
        ctx: ServiceContext = Depends(get_service_context),
    ):
        from agent_os.services.workflow_service import get_workflow_service, WorkflowNode
        svc = get_workflow_service()
        nodes = [WorkflowNode(name="start", node_type="code", config={"code": "pass"})]
        workflow = await svc.create_workflow(tenant_id, name, description, nodes, ctx=ctx)
        return workflow.to_dict()

    @app.post("/api/v1/workflow/run")
    async def workflow_run(
        req: WorkflowRunRequest,
        ctx: ServiceContext = Depends(get_service_context),
        current_user: dict = Depends(get_current_user),
    ):
        from agent_os.services.workflow_service import get_workflow_service
        svc = get_workflow_service()
        execution = await svc.execute_workflow(req.workflow_id, req.input_data, ctx)
        return execution.to_dict()

    @app.post("/api/v1/workflow/run/stream")
    async def workflow_run_stream(
        req: WorkflowRunRequest,
        ctx: ServiceContext = Depends(get_service_context),
        current_user: dict = Depends(get_current_user),
    ):
        """Stream workflow execution as Server-Sent Events (SSE)"""
        from agent_os.services.workflow_service import get_workflow_service
        import json as _json

        svc = get_workflow_service()
        async def generate():
            async for event in svc.execute_workflow_stream(req.workflow_id, req.input_data, ctx):
                yield f"data: {_json.dumps(event, default=str)}\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post("/api/v1/workflow/{execution_id}/pause")
    async def workflow_pause(
        execution_id: str,
        ctx: ServiceContext = Depends(get_service_context),
    ):
        from agent_os.services.workflow_service import get_workflow_service
        svc = get_workflow_service()
        await svc.pause_workflow(execution_id)
        return {"status": "paused", "execution_id": execution_id}

    @app.post("/api/v1/workflow/{execution_id}/resume")
    async def workflow_resume(
        execution_id: str,
        ctx: ServiceContext = Depends(get_service_context),
    ):
        from agent_os.services.workflow_service import get_workflow_service
        svc = get_workflow_service()
        await svc.resume_workflow(execution_id)
        return {"status": "resumed", "execution_id": execution_id}

    @app.post("/api/v1/workflow/{execution_id}/cancel")
    async def workflow_cancel(
        execution_id: str,
        ctx: ServiceContext = Depends(get_service_context),
    ):
        from agent_os.services.workflow_service import get_workflow_service
        svc = get_workflow_service()
        await svc.cancel_workflow(execution_id)
        return {"status": "cancelled", "execution_id": execution_id}

    @app.get("/api/v1/workflow/{workflow_id}")
    async def workflow_get(workflow_id: str):
        from agent_os.services.workflow_service import get_workflow_service
        svc = get_workflow_service()
        workflow = await svc.get_workflow(workflow_id)
        return workflow.to_dict()

    @app.get("/api/v1/workflow/{workflow_id}/executions")
    async def workflow_executions(workflow_id: str):
        from agent_os.services.workflow_service import get_workflow_service
        svc = get_workflow_service()
        executions = await svc.list_executions(workflow_id)
        return [e.to_dict() for e in executions]

    # ─── Usage Routes ──────────────────────────────────

    @app.get("/api/v1/usage/summary")
    async def usage_summary(
        tenant_id: str = Header(..., alias="X-Tenant-ID"),
        current_user: dict = Depends(get_current_user),
    ):
        from agent_os.services.usage_service import get_usage_service
        svc = get_usage_service()
        summary = await svc.get_usage_summary(tenant_id)
        return summary.to_dict()

    @app.get("/api/v1/usage/analytics")
    async def usage_analytics(
        tenant_id: str = Header(..., alias="X-Tenant-ID"),
        current_user: dict = Depends(get_current_user),
    ):
        from agent_os.services.usage_service import get_usage_service
        svc = get_usage_service()
        return await svc.get_tenant_analytics(tenant_id)

    # ─── Admin Routes ──────────────────────────────────

    @app.get("/api/v1/admin/health/all")
    async def admin_health_all(current_user: dict = Depends(get_current_user)):
        checks = {}
        from agent_os.core_platform.tenant_global import get_tenant_manager
        checks["tenant_manager"] = await get_tenant_manager().health_check()
        from agent_os.core_platform.identity import get_iam_service
        checks["iam"] = await get_iam_service().health_check()
        from agent_os.core_platform.billing_engine import get_billing_engine
        checks["billing"] = await get_billing_engine().health_check()
        from agent_os.core_platform.agent_economy import get_agent_economy
        checks["agent_economy"] = await get_agent_economy().health_check()
        from agent_os.core_platform.plugin_runtime import get_plugin_runtime
        checks["plugin_runtime"] = await get_plugin_runtime().health_check()
        from agent_os.ai_layer.llm_gateway import get_llm_gateway
        checks["llm_gateway"] = await get_llm_gateway().health_check()
        from agent_os.ai_layer.agent_runtime_v3 import get_agent_runtime
        checks["agent_runtime"] = await get_agent_runtime().health_check()
        from agent_os.ai_layer.memory_system import get_memory_system
        checks["memory"] = await get_memory_system().health_check()
        return {"status": "healthy", "services": checks}

    # Files Management (mock in-memory)
    import uuid as _uuid, datetime as _dt
    _file_store: dict[str, dict] = {}

    @app.get("/api/v1/files")
    async def files_list(current_user: dict = Depends(get_current_user)):
        return sorted(_file_store.values(), key=lambda f: f.get("uploaded_at", ""), reverse=True)

    @app.post("/api/v1/files/upload")
    async def files_upload(
        filename: str = Query(..., min_length=1),
        size: int = Query(0),
        current_user: dict = Depends(get_current_user),
    ):
        fid = str(_uuid.uuid4())
        record = {"id": fid, "filename": filename.strip(), "size": size, "uploaded_at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
        _file_store[fid] = record
        return record

    @app.delete("/api/v1/files/{file_id}")
    async def files_delete(file_id: str, current_user: dict = Depends(get_current_user)):
        if file_id not in _file_store:
            raise HTTPException(status_code=404, detail="File not found")
        return _file_store.pop(file_id)

    # Model Management (mock in-memory, pre-seeded)
    import random as _random, logging as _logging
    _model_logger = _logging.getLogger("agent_os.models")
    _model_store: dict[str, dict] = {
        "openai-gpt4": {"id":"openai-gpt4","name":"GPT-4o","provider":"OpenAI","base_url":"https://api.openai.com/v1","api_key_status":"configured","created_at":"2026-01-15T00:00:00Z"},
        "anthropic-claude": {"id":"anthropic-claude","name":"Claude 3.5 Sonnet","provider":"Anthropic","base_url":"https://api.anthropic.com","api_key_status":"configured","created_at":"2026-02-01T00:00:00Z"},
        "local-llama": {"id":"local-llama","name":"Llama 3.3 70B","provider":"Local","base_url":"http://localhost:11434","api_key_status":"missing","created_at":"2026-03-10T00:00:00Z"},
    }

    @app.get("/api/v1/models")
    async def models_list(current_user: dict = Depends(get_current_user)):
        return sorted(_model_store.values(), key=lambda m: m.get("name", ""))

    @app.post("/api/v1/models/{model_id}/test")
    async def models_test(model_id: str, current_user: dict = Depends(get_current_user)):
        _model_logger.info("Test connection requested for model=%s", model_id)
        try:
            return _models_test_impl(model_id)
        except HTTPException:
            raise
        except Exception as exc:
            _model_logger.exception("Unexpected error testing model=%s", model_id)
            raise HTTPException(status_code=500, detail=f"Internal error during connection test: {exc}")

    def _models_test_impl(model_id: str):
        model = _model_store.get(model_id)
        if not model:
            _model_logger.warning("Model not found: %s", model_id)
            raise HTTPException(status_code=404, detail="Model not found")
        status = model["api_key_status"]
        _model_logger.info("Model %s status=%s, running test...", model_id, status)
        if status == "missing":
            _model_logger.warning("Model %s has no API key configured", model_id)
            return {"success": False, "message": "API key not configured. Please add an API key in Settings.", "latency_ms": 0}
        if status == "error":
            _model_logger.warning("Model %s API key is invalid", model_id)
            return {"success": False, "message": "API key invalid or expired. Please check your credentials.", "latency_ms": 0}
        ok = _random.random() > 0.2
        latency = _random.randint(20, 400) if ok else 0
        _model_logger.info("Model %s test result: success=%s latency=%dms", model_id, ok, latency)
        return {"success": ok, "message": f"Connection OK ({latency}ms)" if ok else "Connection timed out — the model provider may be unreachable.", "latency_ms": latency}

    # Task Center (mock in-memory, pre-seeded)
    import random as _trandom
    _task_store: dict[str, dict] = {
        "t-001": {"id":"t-001","name":"Customer Support — ETL Pipeline","status":"completed","created_at":"2026-06-27T14:22:00Z","duration": 3420},
        "t-002": {"id":"t-002","name":"Code Review — PR #1287","status":"running","created_at":"2026-06-28T08:15:00Z","duration": 0},
        "t-003": {"id":"t-003","name":"Data Analysis — Q2 Report","status":"failed","created_at":"2026-06-28T09:30:00Z","duration": 12500},
        "t-004": {"id":"t-004","name":"Agent Execution — ChatBot v2","status":"pending","created_at":"2026-06-28T10:00:00Z","duration": 0},
        "t-005": {"id":"t-005","name":"Knowledge Base — Index Rebuild","status":"completed","created_at":"2026-06-25T16:00:00Z","duration": 8900},
    }
    _task_logs: dict[str, list[str]] = {
        "t-001": ["[14:22:01] Task started","[14:24:30] Stage 1 completed","[14:26:15] Stage 2 completed","[14:27:10] Task finished successfully"],
        "t-002": ["[08:15:00] Task started","[08:15:30] Processing file analysis","[08:16:00] Running security scan..."],
        "t-003": ["[09:30:00] Task started","[09:32:00] Processing data","[09:35:00] Error: Data format mismatch","[09:35:01] Task failed"],
        "t-004": ["[10:00:00] Task queued — waiting for agent runtime"],
        "t-005": ["[16:00:00] Task started","[16:05:00] Indexing documents","[16:12:00] Rebuild complete"],
    }

    @app.get("/api/v1/tasks")
    async def tasks_list(current_user: dict = Depends(get_current_user)):
        return sorted(_task_store.values(), key=lambda t: t.get("created_at", ""), reverse=True)

    @app.get("/api/v1/tasks/{task_id}")
    async def tasks_detail(task_id: str, current_user: dict = Depends(get_current_user)):
        task = _task_store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return {**task, "logs": _task_logs.get(task_id, [])}

    # Settings (mock in-memory)
    _settings: dict[str, str] = {
        "system_name": "Agent OS",
        "default_model": "GPT-4o",
        "timezone": "UTC",
        "log_level": "INFO",
    }

    @app.get("/api/v1/settings")
    async def settings_get(current_user: dict = Depends(get_current_user)):
        return dict(_settings)

    @app.put("/api/v1/settings")
    async def settings_update(body: dict, current_user: dict = Depends(get_current_user)):
        for key in ("system_name", "default_model", "timezone", "log_level"):
            if key in body:
                _settings[key] = str(body[key]).strip()
        return {"success": True, "settings": dict(_settings)}

    return app


async def _init_services():
    """Initialize all core services"""
    from agent_os.core_platform.event_bus import EventBus
    await EventBus.get_instance()
    logger.info("All core services initialized")


app = create_app()
