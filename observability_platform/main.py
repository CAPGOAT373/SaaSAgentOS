"""
AI Agent Observability Platform - FastAPI Application Entry Point.
Enterprise-grade AI Agent observability: traces, metrics, logs, cost, replay, security.
"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import config
from .core.storage import get_store, init_postgres
from .api import traces, metrics, cost, replay, security, observability, demo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Agent Observability Platform",
    description="Enterprise-grade AI Agent observability: LangSmith + Datadog + OpenTelemetry + AI Security",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────
API_PREFIX = "/api/v1"
app.include_router(traces.router, prefix=API_PREFIX)
app.include_router(metrics.router, prefix=API_PREFIX)
app.include_router(cost.router, prefix=API_PREFIX)
app.include_router(replay.router, prefix=API_PREFIX)
app.include_router(security.router, prefix=API_PREFIX)
app.include_router(observability.router, prefix=API_PREFIX)
app.include_router(demo.router, prefix=API_PREFIX)


# ── Tenant context middleware ─────────────────────────
@app.middleware("http")
async def tenant_context_middleware(request: Request, call_next):
    """Extract tenant_id from header or query param for multi-tenant isolation."""
    tenant_id = request.headers.get("X-Tenant-ID", "")
    if not tenant_id:
        tenant_id = request.query_params.get("tenant_id", "")
    request.state.tenant_id = tenant_id or config.DEFAULT_TENANT
    response = await call_next(request)
    response.headers["X-Platform"] = "AI-Agent-Observability"
    return response


# ── Health & root ─────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ai-agent-observability", "version": "1.0.0"}


@app.get("/api/v1/health")
async def api_health():
    store_health = get_store().health()
    return {
        "status": "healthy", "service": "ai-agent-observability", "version": "1.0.0",
        "storage": store_health,
        "otel_available": _otel_available(),
        "postgres_available": init_postgres(config.DATABASE_URL).available if config.DATABASE_URL else False,
    }


def _otel_available() -> bool:
    try:
        from .core.otel_integration import get_otel
        return get_otel(config.JAEGER_ENDPOINT).available
    except Exception:
        return False


# ── UI ────────────────────────────────────────────────
UI_DIR = Path(__file__).parent / "ui"


@app.get("/", response_class=HTMLResponse)
async def ui():
    index = UI_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>AI Agent Observability Platform</h1><p>UI not found</p>")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL", "message": str(exc)}},
    )


def main():
    import uvicorn
    logger.info("=" * 60)
    logger.info("AI Agent Observability Platform v1.0.0")
    logger.info(f"Listening on http://{config.HOST}:{config.PORT}")
    logger.info(f"UI: http://localhost:{config.PORT}/")
    logger.info(f"API docs: http://localhost:{config.PORT}/docs")
    logger.info(f"Storage: {'PostgreSQL' if config.DATABASE_URL else 'In-Memory'}")
    logger.info(f"OpenTelemetry: {'enabled' if config.OTEL_ENABLED else 'disabled'}")
    logger.info("=" * 60)
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
