"""
Agent OS V6.0 - Rate Limiter Middleware
Token bucket algorithm for API rate limiting
"""
import time
import asyncio
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from agent_os.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    tokens: float = 0.0
    max_tokens: float = 100.0
    refill_rate: float = 10.0  # tokens per second
    last_refill: float = field(default_factory=time.time)

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class RateLimiter:
    """Token bucket rate limiter with per-tenant and per-user limits"""

    # Tier-based limits (requests per minute)
    TIER_LIMITS = {
        "free": 60,
        "pro": 600,
        "business": 3000,
        "enterprise": 30000,
    }
    DEFAULT_LIMIT = 60

    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()
        self._config = get_config()

    def _get_bucket_key(self, tenant_id: str, user_id: str = "", path: str = "") -> str:
        """Generate bucket key for a tenant/user/path combination"""
        if user_id:
            return f"user:{tenant_id}:{user_id}"
        return f"tenant:{tenant_id}"

    def _get_tier_limit(self, tenant_id: str) -> int:
        """Get rate limit for tenant based on tier"""
        from agent_os.core_platform.tenant_global import get_tenant_manager
        try:
            tm = get_tenant_manager()
            # Try sync lookup
            tenant = tm._tenants.get(tenant_id)
            if tenant:
                return self.TIER_LIMITS.get(tenant.tier.value, self.DEFAULT_LIMIT)
        except Exception:
            pass
        return self.DEFAULT_LIMIT

    async def check_rate_limit(
        self, tenant_id: str, user_id: str = "", path: str = ""
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Check if request is within rate limits.
        Returns (allowed, rate_limit_info)
        """
        if not tenant_id:
            return True, {"allowed": True, "reason": "no_tenant"}

        async with self._lock:
            key = self._get_bucket_key(tenant_id, user_id, path)
            bucket = self._buckets.get(key)

            limit = self._get_tier_limit(tenant_id)
            rpm = limit  # requests per minute

            if bucket is None:
                bucket = TokenBucket(
                    max_tokens=limit,
                    refill_rate=limit / 60.0,  # tokens per second
                    tokens=limit,  # start full
                )
                self._buckets[key] = bucket

            allowed = bucket.consume(1)
            remaining = int(bucket.tokens)
            reset_at = bucket.last_refill + (1 / bucket.refill_rate) * (bucket.max_tokens - bucket.tokens)

            info = {
                "allowed": allowed,
                "limit": limit,
                "remaining": remaining,
                "reset_at": reset_at,
                "tier": "unknown",
            }

            if not allowed:
                logger.warning(f"Rate limit exceeded for {key}")

            return allowed, info

    async def get_limits(self, tenant_id: str) -> Dict[str, any]:
        """Get current rate limit status for a tenant"""
        limit = self._get_tier_limit(tenant_id)
        key = f"tenant:{tenant_id}"
        async with self._lock:
            bucket = self._buckets.get(key)
            remaining = int(bucket.tokens) if bucket else limit
            return {
                "limit": limit,
                "remaining": remaining,
                "tier": "unknown",
            }


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter