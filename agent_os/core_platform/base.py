"""
Agent OS V6.0 - Base Service Layer
All services inherit from BaseService with built-in tracing, logging, event emission
"""
import uuid
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Type, TypeVar, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.config import get_config, AppConfig

T = TypeVar("T")

logger = logging.getLogger(__name__)


@dataclass
class ServiceContext:
    """Context passed through all service calls for tracing"""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    region: str = "us-east-1"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def child(self, **kwargs) -> "ServiceContext":
        """Create a child context with same trace but new request_id"""
        child_ctx = ServiceContext(
            request_id=str(uuid.uuid4()),
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            agent_id=self.agent_id,
            region=self.region,
            metadata={**self.metadata},
        )
        for k, v in kwargs.items():
            setattr(child_ctx, k, v)
        return child_ctx


class BaseService(ABC):
    """Base service with built-in observability and event emission"""

    def __init__(self, config: Optional[AppConfig] = None):
        self._config = config or get_config()
        self._event_handlers: Dict[str, list] = {}

    @property
    def config(self) -> AppConfig:
        return self._config

    def log(self, level: str, message: str, ctx: Optional[ServiceContext] = None, **kwargs):
        """Structured logging with trace context"""
        log_data = {
            "service": self.__class__.__name__,
            "request_id": ctx.request_id if ctx else None,
            "trace_id": ctx.trace_id if ctx else None,
            "tenant_id": ctx.tenant_id if ctx else None,
            **kwargs,
        }
        getattr(logger, level.lower(), logger.info)(f"{message} | {log_data}")

    def on_event(self, event_type: str):
        """Decorator to register event handlers"""
        def decorator(func: Callable):
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(func)
            return func
        return decorator

    async def emit_event(self, event_type: str, payload: Dict[str, Any], ctx: Optional[ServiceContext] = None):
        """Emit an event to the event bus"""
        from agent_os.core_platform.event_bus.bus import EventBus
        bus = await EventBus.get_instance()
        await bus.publish(event_type, payload, ctx)

    async def handle_event(self, event_type: str, payload: Dict[str, Any], ctx: Optional[ServiceContext] = None):
        """Handle incoming events"""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(payload, ctx)
            except Exception as e:
                self.log("error", f"Event handler error for {event_type}: {e}", ctx)

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Health check for this service"""
        return {"status": "healthy", "service": self.__class__.__name__}


class ServiceRegistry:
    """Global service registry for dependency injection"""
    _services: Dict[str, BaseService] = {}

    @classmethod
    def register(cls, name: str, service: BaseService):
        cls._services[name] = service
        logger.info(f"Service registered: {name}")

    @classmethod
    def get(cls, name: str, service_type: Type[T] = BaseService) -> Optional[T]:
        return cls._services.get(name)

    @classmethod
    def get_all(cls) -> Dict[str, BaseService]:
        return cls._services.copy()

    @classmethod
    def list_services(cls) -> list:
        return list(cls._services.keys())