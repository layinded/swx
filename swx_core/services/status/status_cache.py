import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import STATUS_CACHE_TTL
from swx_core.repositories import status_repository

_component_cache: dict[str, tuple[float, Any]] = {}


def _cache_key(prefix: str, identifier: str) -> str:
    return f"status:{prefix}:{identifier}"


def _is_expired(cached_at: float) -> bool:
    return (time.time() - cached_at) > STATUS_CACHE_TTL


async def get_cached_component_count(session: AsyncSession) -> int:
    cache_key = _cache_key("component_count", "total")
    cached_entry = _component_cache.get(cache_key)
    if cached_entry is not None:
        cached_at, value = cached_entry
        if not _is_expired(cached_at):
            return value

    count = await status_repository.get_component_count(session)
    _component_cache[cache_key] = (time.time(), count)
    return count


def invalidate_cache() -> None:
    _component_cache.clear()