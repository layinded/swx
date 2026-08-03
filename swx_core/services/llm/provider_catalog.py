"""DB-Driven Provider Catalog
-----------------------------
Reads supported LLM providers from SystemConfig (key ``llm.provider_catalog``
under GENERAL category), Redis-cached for 1 hour, with fallback to the static
``LLM_PROVIDER_DEFAULTS``.

Simple Redis TTL cache — a provider catalog changes rarely, so 1 hour is
sufficient.  No need for a three-tier cache here.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.llm_provider_config import LLM_PROVIDER_DEFAULTS
from swx_core.models.system_config import SettingCategory, SystemConfig
from swx_core.utils.cache import get_cache

logger = logging.getLogger(__name__)

_CATALOG_CACHE_KEY = "llm:provider_catalog"
_CATALOG_CACHE_TTL = 3600  # 1 hour


async def _read_catalog_from_db(session: AsyncSession) -> list[dict[str, Any]] | None:
    """Try to read provider catalog from SystemConfig (key llm.provider_catalog)."""
    from sqlmodel import select

    stmt = (
        select(SystemConfig)
        .where(
            SystemConfig.category == SettingCategory.GENERAL,
            SystemConfig.key == "llm.provider_catalog",
            SystemConfig.is_active == True,  # noqa: E712
        )
    )
    result = await session.execute(stmt)
    config = result.scalar_one_or_none()
    if config is None:
        return None

    value = config.value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in llm.provider_catalog SystemConfig")
            return None

    if isinstance(value, list):
        return value

    # value_type might be JSON — already a dict/list
    if isinstance(value, dict) and "providers" in value:
        return value["providers"]

    return None


async def get_provider_catalog(session: AsyncSession | None = None) -> list[dict[str, Any]]:
    """Return the LLM provider catalog.

    Priority:
      1. Redis cache (1-hour TTL)
      2. SystemConfig DB (category key ``llm.provider_catalog``)
      3. Static ``LLM_PROVIDER_DEFAULTS`` fallback
    """
    # 1. Try Redis cache
    cache = get_cache()
    cached = await cache.get(_CATALOG_CACHE_KEY)
    if cached is not None:
        logger.debug("Provider catalog cache hit")
        return cached  # type: ignore[return-value]

    # 2. Try DB
    db_catalog: list[dict[str, Any]] | None = None
    if session is not None:
        try:
            db_catalog = await _read_catalog_from_db(session)
        except Exception:
            logger.debug("Failed to read provider catalog from DB, using defaults", exc_info=True)

    # 3. Fallback to static defaults
    catalog = db_catalog if db_catalog is not None else list(LLM_PROVIDER_DEFAULTS)

    # Cache for next read
    try:
        await cache.set(_CATALOG_CACHE_KEY, catalog, ttl=_CATALOG_CACHE_TTL)
    except Exception:
        logger.debug("Failed to cache provider catalog", exc_info=True)

    return catalog


async def invalidate_catalog_cache() -> None:
    """Invalidate the provider catalog cache (call after admin catalog updates)."""
    cache = get_cache()
    try:
        await cache.delete(_CATALOG_CACHE_KEY)
        logger.info("Provider catalog cache invalidated")
    except Exception:
        logger.debug("Failed to invalidate provider catalog cache", exc_info=True)