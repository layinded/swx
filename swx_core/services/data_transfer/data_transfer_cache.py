import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import DATA_TRANSFER_CACHE_TTL
from swx_core.repositories import data_transfer_repository

_transfer_cache: dict[str, tuple[float, Any]] = {}


def _cache_key(prefix: str, identifier: str) -> str:
    return f"data_transfer:{prefix}:{identifier}"


def _is_expired(cached_at: float) -> bool:
    return (time.time() - cached_at) > DATA_TRANSFER_CACHE_TTL


async def get_cached_export_count(session: AsyncSession) -> int:
    cache_key = _cache_key("export_count", "total")
    cached_entry = _transfer_cache.get(cache_key)
    if cached_entry is not None:
        cached_at, value = cached_entry
        if not _is_expired(cached_at):
            return value

    count = await data_transfer_repository.get_export_count(session)
    _transfer_cache[cache_key] = (time.time(), count)
    return count


def invalidate_cache() -> None:
    _transfer_cache.clear()