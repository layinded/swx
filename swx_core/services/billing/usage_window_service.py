"""Usage window tracking via Redis — 5-hour rolling window + monthly counters.

Provides token usage counting with a rolling window and monthly aggregate.
Redis is the primary store; an in-memory fallback is used when Redis is
unavailable so the service degrades gracefully.

This is complementary to ``quota_service.py`` (which checks plan
entitlements) — this module tracks *actual usage* against those limits.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import SQLModel

from swx_core.config.settings import settings
from swx_core.events import event_bus
from swx_core.middleware.logging_middleware import logger
from swx_core.utils.errors import QuotaExceededError
from swx_core.utils.time import utc_now

try:
    import redis.asyncio as _redis_mod  # type: ignore[import-untyped]

    _redis_available = True
except ImportError:
    _redis_mod = None  # type: ignore[assignment]
    _redis_available = False


class QuotaStatus(SQLModel):
    monthly_quota: int
    monthly_used: int
    monthly_remaining: int
    window_quota: int
    window_used: int
    window_remaining: int
    window_resets_at: datetime
    window_resets_available: bool


def _window_seconds() -> int:
    return settings.QUOTA_WINDOW_HOURS * 3600


def _window_ttl() -> int:
    return _window_seconds() + settings.QUOTA_WINDOW_TTL_BUFFER_HOURS * 3600


def _monthly_ttl() -> int:
    return settings.QUOTA_MONTHLY_TTL_DAYS * 24 * 3600


def _daily_ttl() -> int:
    return settings.QUOTA_DAILY_TTL_HOURS * 3600


def _window_start(now: datetime) -> int:
    return int(now.timestamp() // _window_seconds() * _window_seconds())


def _window_end_ts(window_start: int) -> int:
    return window_start + _window_seconds()


def _monthly_key(account_id: UUID) -> str:
    now = utc_now()
    return f"quota:{account_id}:monthly:{now.year}{now.month:02d}"


def _window_key(account_id: UUID, window_start_ts: int) -> str:
    return f"quota:{account_id}:window:{window_start_ts}"


def _window_reset_key(account_id: UUID, window_start_ts: int) -> str:
    return f"quota:{account_id}:resets:window:{window_start_ts}"


def _daily_reset_key(account_id: UUID) -> str:
    now = utc_now()
    return f"quota:{account_id}:resets:daily:{now.year}{now.month:02d}{now.day:02d}"


class UsageWindowService:
    def __init__(self):
        self._redis = None
        self._memory: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def _get_redis(self):
        if self._redis is not None:
            return self._redis
        if not _redis_available or not settings.REDIS_ENABLED:
            return None
        try:
            assert _redis_mod is not None
            self._redis = _redis_mod.from_url(settings.redis_url)
            return self._redis
        except Exception:
            logger.warning("UsageWindowService: Redis unavailable, using in-memory fallback")
            self._redis = None
            return None

    async def _incr(self, key: str, ttl: int | None = None, amount: int = 1) -> int:
        redis = await self._get_redis()
        if redis is not None:
            count = await redis.incrby(key, amount)
            if ttl is not None and count == amount:
                await redis.expire(key, ttl)
            return count
        async with self._lock:
            self._memory[key] = self._memory.get(key, 0) + amount
            return self._memory[key]

    async def _get(self, key: str) -> int:
        redis = await self._get_redis()
        if redis is not None:
            value = await redis.get(key)
            return int(value) if value is not None else 0
        async with self._lock:
            return self._memory.get(key, 0)

    async def _set_zero(self, key: str, ttl: int | None = None) -> None:
        redis = await self._get_redis()
        if redis is not None:
            if ttl is not None:
                await redis.setex(key, ttl, 0)
            else:
                await redis.set(key, 0)
            return
        async with self._lock:
            self._memory[key] = 0

    async def get_status(self, account_id: UUID, monthly_quota: int | None = None) -> QuotaStatus:
        quota = monthly_quota if monthly_quota is not None else settings.QUOTA_MONTHLY_DEFAULT_TOKENS
        window_quota = settings.QUOTA_WINDOW_DEFAULT_TOKENS

        now = utc_now()
        w_start = _window_start(now)
        w_end = datetime.fromtimestamp(_window_end_ts(w_start), tz=timezone.utc)

        monthly_used = await self._get(_monthly_key(account_id))
        window_used = await self._get(_window_key(account_id, w_start))
        resets_available = await self._can_reset(account_id, w_start)

        return QuotaStatus(
            monthly_quota=quota,
            monthly_used=monthly_used,
            monthly_remaining=max(0, quota - monthly_used),
            window_quota=window_quota,
            window_used=window_used,
            window_remaining=max(0, window_quota - window_used),
            window_resets_at=w_end,
            window_resets_available=resets_available,
        )

    async def record_usage(self, account_id: UUID, tokens: int) -> None:
        await self._incr(_monthly_key(account_id), ttl=_monthly_ttl(), amount=tokens)
        await self._incr(_window_key(account_id, _window_start(utc_now())), ttl=_window_ttl(), amount=tokens)
        await event_bus.dispatch("quota.usage_recorded", payload={
            "account_id": str(account_id),
            "tokens": tokens,
        })

    async def reset_window(self, account_id: UUID) -> QuotaStatus:
        now = utc_now()
        w_start = _window_start(now)

        if not await self._can_reset(account_id, w_start):
            raise QuotaExceededError(resource="window_reset", message="Window reset limit reached")

        await self._incr(_window_reset_key(account_id, w_start), ttl=_window_ttl())
        await self._incr(_daily_reset_key(account_id), ttl=_daily_ttl())
        await self._set_zero(_window_key(account_id, w_start), ttl=_window_ttl())

        await event_bus.dispatch("quota.window_reset", payload={
            "account_id": str(account_id),
            "window_start": w_start,
        })

        return await self.get_status(account_id)

    async def _can_reset(self, account_id: UUID, w_start: int) -> bool:
        window_resets = await self._get(_window_reset_key(account_id, w_start))
        if window_resets >= settings.QUOTA_WINDOW_MAX_RESETS:
            return False
        daily_resets = await self._get(_daily_reset_key(account_id))
        if daily_resets >= settings.QUOTA_DAILY_MAX_RESETS:
            return False
        return True


_service: UsageWindowService | None = None


def get_usage_window_service() -> UsageWindowService:
    global _service
    if _service is None:
        _service = UsageWindowService()
    return _service
