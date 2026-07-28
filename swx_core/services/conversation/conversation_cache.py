import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import CONVERSATION_CACHE_TTL
from swx_core.repositories import conversation_repository

_conversation_cache: dict[str, tuple[float, Any]] = {}


def _cache_key(prefix: str, identifier: str) -> str:
    return f"conversation:{prefix}:{identifier}"


def _is_expired(cached_at: float) -> bool:
    return (time.time() - cached_at) > CONVERSATION_CACHE_TTL


async def get_cached_conversation_config(session: AsyncSession, key: str) -> Any:
    cache_key = _cache_key("config", key)
    cached_entry = _conversation_cache.get(cache_key)
    if cached_entry is not None:
        cached_at, value = cached_entry
        if not _is_expired(cached_at):
            return value

    conversation_count = await conversation_repository.get_conversation_count(session)
    _conversation_cache[cache_key] = (time.time(), conversation_count)
    return conversation_count


def invalidate_cache() -> None:
    _conversation_cache.clear()
