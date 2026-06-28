"""
Agent OS V6.0 - Event Bus (Kafka Abstraction)
Supports Kafka/Redpanda with in-memory fallback for dev
"""
import asyncio
import json
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.config import get_config, AppConfig, KafkaConfig
from agent_os.core_platform.base import ServiceContext

logger = logging.getLogger(__name__)


@dataclass
class Event:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    trace_id: str = ""
    tenant_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: str = "1.0"

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "source": self.source,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp,
            "version": self.version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        return cls(**data)


# Standard Event Types
class EventTypes:
    # Agent Events
    AGENT_CREATED = "agent.created"
    AGENT_UPDATED = "agent.updated"
    AGENT_DELETED = "agent.deleted"
    AGENT_EXECUTED = "agent.executed"
    AGENT_PUBLISHED = "agent.published"
    AGENT_EXECUTION_STARTED = "agent.execution.started"
    AGENT_EXECUTION_STREAMING = "agent.execution.streaming"
    AGENT_EXECUTION_COMPLETED = "agent.execution.completed"
    AGENT_EXECUTION_FAILED = "agent.execution.failed"

    # Workflow Events
    WORKFLOW_CREATED = "workflow.created"
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_NODE_EXECUTED = "workflow.node_executed"
    WORKFLOW_NODE_EXECUTING = "workflow.node.executing"

    # Billing Events
    BILLING_INVOICE_CREATED = "billing.invoice.created"
    BILLING_PAYMENT_RECEIVED = "billing.payment.received"
    BILLING_CREDITS_DEDUCTED = "billing.credits.deducted"
    BILLING_REVENUE_SHARED = "billing.revenue.shared"

    # Plugin Events
    PLUGIN_INSTALLED = "plugin.installed"
    PLUGIN_EXECUTED = "plugin.executed"
    PLUGIN_PUBLISHED = "plugin.published"
    PLUGIN_VERSION_UPDATED = "plugin.version.updated"

    # Tool Events
    TOOL_CALL_STARTED = "tool.call.started"
    TOOL_CALL_COMPLETED = "tool.call.completed"
    TOOL_CALL_FAILED = "tool.call.failed"

    # Tenant Events
    TENANT_CREATED = "tenant.created"
    TENANT_UPDATED = "tenant.updated"
    TENANT_DELETED = "tenant.deleted"
    TENANT_REGION_ASSIGNED = "tenant.region.assigned"

    # Marketplace Events
    MARKETPLACE_LISTING_CREATED = "marketplace.listing.created"
    MARKETPLACE_PURCHASE_COMPLETED = "marketplace.purchase.completed"
    MARKETPLACE_REVIEW_ADDED = "marketplace.review.added"

    # System Events
    SYSTEM_HEALTH_CHECK = "system.health.check"
    SYSTEM_REGION_FAILOVER = "system.region.failover"


class MessageBroker(ABC):
    """Abstract message broker interface"""

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def publish(self, topic: str, event: Event) -> bool:
        pass

    @abstractmethod
    async def subscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> None:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass


class InMemoryBroker(MessageBroker):
    """In-memory message broker for development"""

    def __init__(self):
        self._subscriptions: Dict[str, List[Callable[[Event], Awaitable[None]]]] = {}
        self._event_log: List[Event] = []
        self._connected = False

    async def connect(self) -> None:
        self._connected = True
        logger.info("InMemoryBroker connected")

    async def disconnect(self) -> None:
        self._connected = False
        self._subscriptions.clear()
        logger.info("InMemoryBroker disconnected")

    async def publish(self, topic: str, event: Event) -> bool:
        self._event_log.append(event)
        handlers = self._subscriptions.get(topic, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"InMemoryBroker handler error for {topic}: {e}")
        return True

    async def subscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> None:
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        self._subscriptions[topic].append(handler)
        logger.info(f"Subscribed to topic: {topic}")

    async def health_check(self) -> bool:
        return self._connected


class KafkaBroker(MessageBroker):
    """Kafka/Redpanda message broker for production"""

    def __init__(self, config: KafkaConfig):
        self._config = config
        self._producer = None
        self._consumer = None
        self._connected = False

    async def connect(self) -> None:
        try:
            from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._config.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            )
            await asyncio.wait_for(self._producer.start(), timeout=5.0)
            self._connected = True
            logger.info(f"KafkaBroker connected to {self._config.bootstrap_servers}")
        except ImportError:
            logger.warning("aiokafka not installed, falling back to InMemoryBroker")
            self._connected = False
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"KafkaBroker connection failed (will use InMemoryBroker): {e}")
            self._connected = False
            # Clean up unclosed producer
            if self._producer:
                try:
                    await self._producer.stop()
                except Exception:
                    pass
                self._producer = None

    async def disconnect(self) -> None:
        if self._producer:
            await self._producer.stop()
        self._connected = False

    async def publish(self, topic: str, event: Event) -> bool:
        if not self._connected or not self._producer:
            return False
        try:
            await self._producer.send_and_wait(topic, event.to_dict())
            return True
        except Exception as e:
            logger.error(f"KafkaBroker publish error: {e}")
            return False

    async def subscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> None:
        try:
            from aiokafka import AIOKafkaConsumer
            self._consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self._config.bootstrap_servers,
                group_id=self._config.consumer_group,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
            await self._consumer.start()
            asyncio.create_task(self._consume_loop(handler))
        except Exception as e:
            logger.error(f"KafkaBroker subscribe error: {e}")

    async def _consume_loop(self, handler: Callable[[Event], Awaitable[None]]):
        async for msg in self._consumer:
            event = Event.from_dict(msg.value)
            await handler(event)

    async def health_check(self) -> bool:
        return self._connected


class EventBus:
    """Singleton Event Bus with automatic broker selection"""
    _instance: Optional["EventBus"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._config = get_config()
        self._broker: Optional[MessageBroker] = None
        self._initialized = False

    @classmethod
    async def get_instance(cls) -> "EventBus":
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    bus = EventBus()
                    await bus.initialize()
                    cls._instance = bus
        return cls._instance

    @classmethod
    def get_instance_sync(cls) -> "EventBus":
        """Get instance without async init (uses in-memory broker)"""
        if cls._instance is None:
            cls._instance = EventBus()
            cls._instance._broker = InMemoryBroker()
        return cls._instance

    async def initialize(self):
        if self._initialized:
            return
        try:
            self._broker = KafkaBroker(self._config.kafka)
            await self._broker.connect()
            if not await self._broker.health_check():
                self._broker = InMemoryBroker()
                await self._broker.connect()
        except Exception:
            self._broker = InMemoryBroker()
            await self._broker.connect()
        self._initialized = True
        logger.info(f"EventBus initialized with {self._broker.__class__.__name__}")

    async def publish(self, event_type: str, payload: Dict[str, Any], ctx: Optional[ServiceContext] = None) -> bool:
        if not self._broker:
            await self.initialize()
        event = Event(
            event_type=event_type,
            payload=payload,
            trace_id=ctx.trace_id if ctx else "",
            tenant_id=ctx.tenant_id if ctx else "",
            source="agent-os",
        )
        topic = self._config.kafka.topics.get("agent_events", "agent_os.events")
        return await self._broker.publish(topic, event)

    async def subscribe(self, event_type: str, handler: Callable[[Event], Awaitable[None]]):
        if not self._broker:
            await self.initialize()
        topic = self._config.kafka.topics.get("agent_events", "agent_os.events")
        await self._broker.subscribe(topic, handler)

    async def publish_to_topic(self, topic: str, event: Event) -> bool:
        if not self._broker:
            await self.initialize()
        return await self._broker.publish(topic, event)

    async def health_check(self) -> bool:
        if not self._broker:
            return False
        return await self._broker.health_check()