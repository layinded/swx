import asyncio
import time

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import SAFETY_CACHE_TTL
from swx_core.models.content_filter import ContentFilter
from swx_core.repositories import safety_repository

_safety_cache: dict[str, tuple[float, list[ContentFilter]]] = {}
_cache_lock = asyncio.Lock()


def _cache_key() -> str:
    return "safety:enabled_filters"


def _is_expired(cached_at: float) -> bool:
    return (time.time() - cached_at) > SAFETY_CACHE_TTL


async def get_cached_filters(session: AsyncSession) -> list[ContentFilter]:
    cache_key = _cache_key()
    cached_entry = _safety_cache.get(cache_key)
    if cached_entry is not None:
        cached_at, filters = cached_entry
        if not _is_expired(cached_at):
            return filters
    async with _cache_lock:
        cached_entry = _safety_cache.get(cache_key)
        if cached_entry is not None:
            cached_at, filters = cached_entry
            if not _is_expired(cached_at):
                return filters
        filters = await safety_repository.list_filters(session, enabled=True, limit=500)
        _safety_cache[cache_key] = (time.time(), filters)
        return filters


def invalidate_cache() -> None:
    _safety_cache.clear()
