"""
Agent OS V6.0 - Redis Client
Caching, session management, rate limiting, distributed locks
"""
import time
import json
import logging
from typing import Optional, Dict, Any, List
from agent_os.config import get_config, RedisConfig

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper with cluster support"""

    def __init__(self, config: Optional[RedisConfig] = None):
        self._config = config or get_config().redis
        self._client = None
        self._connected = False

    async def connect(self):
        try:
            import redis.asyncio as aioredis
            if self._config.cluster_mode and self._config.cluster_nodes:
                self._client = aioredis.RedisCluster(
                    host=self._config.cluster_nodes[0].split(":")[0],
                    port=int(self._config.cluster_nodes[0].split(":")[1]) if ":" in self._config.cluster_nodes[0] else 6379,
                    password=self._config.password or None,
                    decode_responses=True,
                )
            else:
                self._client = aioredis.Redis(
                    host=self._config.host,
                    port=self._config.port,
                    password=self._config.password or None,
                    db=self._config.db,
                    decode_responses=True,
                )
            await self._client.ping()
            self._connected = True
            logger.info(f"Redis connected: {self._config.host}:{self._config.port}")
        except ImportError:
            logger.warning("redis not installed, using in-memory cache")
            self._client = None
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self._client = None

    async def get(self, key: str) -> Optional[str]:
        if self._client:
            return await self._client.get(key)
        return self._memory_cache.get(key)

    async def set(self, key: str, value: str, expire: int = 300):
        if self._client:
            await self._client.set(key, value, ex=expire)
        else:
            self._memory_cache[key] = value

    async def delete(self, key: str):
        if self._client:
            await self._client.delete(key)
        else:
            self._memory_cache.pop(key, None)

    async def exists(self, key: str) -> bool:
        if self._client:
            return await self._client.exists(key) > 0
        return key in self._memory_cache

    async def hset(self, name: str, key: str, value: str):
        if self._client:
            await self._client.hset(name, key, value)

    async def hget(self, name: str, key: str) -> Optional[str]:
        if self._client:
            return await self._client.hget(name, key)
        return None

    async def hgetall(self, name: str) -> Dict[str, str]:
        if self._client:
            return await self._client.hgetall(name)
        return {}

    # Rate Limiting
    async def check_rate_limit(
        self, key: str, max_requests: int, window_seconds: int = 60
    ) -> bool:
        """Check if rate limit is exceeded. Returns True if allowed."""
        if not self._client:
            return True
        current = await self._client.get(key)
        if current is None:
            await self._client.set(key, 1, ex=window_seconds)
            return True
        count = int(current)
        if count >= max_requests:
            return False
        await self._client.incr(key)
        return True

    # Session Management
    async def set_session(self, session_id: str, data: Dict, expire: int = 3600):
        await self.set(f"session:{session_id}", json.dumps(data), expire)

    async def get_session(self, session_id: str) -> Optional[Dict]:
        data = await self.get(f"session:{session_id}")
        return json.loads(data) if data else None

    async def delete_session(self, session_id: str):
        await self.delete(f"session:{session_id}")

    # Distributed Lock
    async def acquire_lock(self, lock_name: str, expire: int = 30) -> bool:
        if not self._client:
            return True
        return await self._client.set(f"lock:{lock_name}", "1", nx=True, ex=expire)

    async def release_lock(self, lock_name: str):
        if self._client:
            await self._client.delete(f"lock:{lock_name}")

    # In-memory fallback
    _memory_cache: Dict[str, str] = {}

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    async def close(self):
        if self._client:
            await self._client.close()
            logger.info("Redis connection closed")


_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client