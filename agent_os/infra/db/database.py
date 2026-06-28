"""
Agent OS V6.0 - Database Layer
PostgreSQL integration with async support, connection pooling, migrations stub
"""
import logging
from typing import Optional, Dict, Any, List, AsyncGenerator
from agent_os.config import get_config, DatabaseConfig

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database connection manager with async support"""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self._config = config or get_config().db
        self._engine = None
        self._session_factory = None

    @property
    def url(self) -> str:
        return self._config.url

    async def initialize(self):
        """Initialize database connections"""
        try:
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
            self._engine = create_async_engine(
                self._config.url,
                echo=False,
                pool_size=self._config.pool_size,
                max_overflow=self._config.max_overflow,
            )
            self._session_factory = async_sessionmaker(
                self._engine, class_=AsyncSession, expire_on_commit=False
            )
            logger.info(f"Database initialized: {self._config.host}:{self._config.port}/{self._config.database}")
        except ImportError:
            logger.warning("SQLAlchemy async not installed, using mock database")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")

    async def get_session(self):
        """Get an async database session"""
        if self._session_factory:
            async with self._session_factory() as session:
                yield session
        else:
            yield None

    async def execute(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute a raw query"""
        if not self._engine:
            return None
        try:
            from sqlalchemy import text
            async with self._engine.begin() as conn:
                result = await conn.execute(text(query), params or {})
                return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return None

    async def health_check(self) -> bool:
        if not self._engine:
            return False
        try:
            from sqlalchemy import text
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def close(self):
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connections closed")


# SQLAlchemy Base Model
try:
    from sqlalchemy.orm import DeclarativeBase
    from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, JSON, ForeignKey, Text

    class Base(DeclarativeBase):
        pass

    class TenantModel(Base):
        __tablename__ = "tenants"
        tenant_id = Column(String, primary_key=True)
        name = Column(String, nullable=False)
        slug = Column(String, unique=True, nullable=False)
        tier = Column(String, default="free")
        status = Column(String, default="active")
        primary_region = Column(String, default="us-east-1")
        shard_key = Column(String)
        created_at = Column(DateTime)
        updated_at = Column(DateTime)
        metadata_json = Column(JSON, default={})

    class AgentModel(Base):
        __tablename__ = "agents"
        agent_id = Column(String, primary_key=True)
        tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
        name = Column(String, nullable=False)
        agent_type = Column(String, default="chat")
        status = Column(String, default="draft")
        price = Column(Float, default=0.0)
        created_at = Column(DateTime)
        updated_at = Column(DateTime)
        config_json = Column(JSON, default={})

    class BillingModel(Base):
        __tablename__ = "billing"
        id = Column(String, primary_key=True)
        tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
        balance = Column(Float, default=0.0)
        total_earned = Column(Float, default=0.0)
        total_spent = Column(Float, default=0.0)
        currency = Column(String, default="USD")
        updated_at = Column(DateTime)

except ImportError:
    Base = None
    TenantModel = None
    AgentModel = None
    BillingModel = None


_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager