"""
Rate Limiting Service Provider.

Registers rate limiting services including:
- Redis client
- Rate limiter
- Abuse detector
"""

from swx_core.providers.base import ServiceProvider


class RateLimitServiceProvider(ServiceProvider):
    priority = 30

    def register(self) -> None:
        from swx_core.config.settings import settings

        if not settings.REDIS_ENABLED:
            return

        self.singleton("redis.client", self._create_redis_client)
        self.singleton("rate_limiter", self._create_rate_limiter)
        self.singleton("abuse_detector", self._create_abuse_detector)
        self.alias("rate_limiter", "RateLimiter")
        self.alias("redis.client", "redis")

    def boot(self) -> None:
        """Boot rate limiting services."""
        pass

    def _create_redis_client(self, app):
        """Create Redis client."""
        from swx_core.config.settings import settings
        import redis.asyncio as aioredis

        if not getattr(settings, "REDIS_ENABLED", True):
            return None

        try:
            return aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        except Exception:
            return None

    def _create_rate_limiter(self, app):
        """Create rate limiter."""
        from swx_core.services.rate_limit.rate_limiter import RateLimiter

        redis_client = app.make("redis.client")
        return RateLimiter(redis_client=redis_client)

    def _create_abuse_detector(self, app):
        """Create abuse detector."""
        from swx_core.services.rate_limit.abuse_detector import AbuseDetector

        redis_client = app.make("redis.client")
        return AbuseDetector(redis_client=redis_client)
