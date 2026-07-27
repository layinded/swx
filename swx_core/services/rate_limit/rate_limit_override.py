"""
Rate Limit Override Resolver
----------------------------
Database-driven rate limit overrides backed by SystemConfig.

Override keys stored in SystemConfig follow the pattern::

    rate_limit.{plan}.{feature}.{endpoint_class}.{limit_type}

e.g. ``rate_limit.pro.api_requests.read.burst = 500``

Overrides are loaded into an in-memory dict at first request and
can be refreshed via :func:`reload_overrides`.
"""

from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.middleware.logging_middleware import logger

_overrides: Dict[str, int] = {}
_loaded: bool = False


def _override_key(
    plan: str, feature: str, endpoint_class: str, limit_type: str
) -> str:
    return f"rate_limit.{plan}.{feature}.{endpoint_class}.{limit_type}"


async def load_overrides(session: AsyncSession) -> None:
    """Load all active ``RATE_LIMIT`` overrides from SystemConfig."""
    global _overrides, _loaded
    try:
        from swx_core.repositories.system_config_repository import get_active_rate_limit_configs  # pyright: ignore[reportMissingImports]

        configs = await get_active_rate_limit_configs(session)

        _overrides = {c.key: int(c.value) for c in configs}
        _loaded = True
        logger.info(f"Loaded {len(_overrides)} rate limit overrides from SystemConfig")
    except Exception as e:
        logger.warning(f"Failed to load rate limit overrides: {e}")
        _loaded = True


def get_override(
    plan: str, feature: str, endpoint_class: str, limit_type: str
) -> Optional[int]:
    """Return the DB override value, or ``None`` if not set."""
    return _overrides.get(
        _override_key(plan, feature, endpoint_class, limit_type)
    )


def is_loaded() -> bool:
    return _loaded


async def reload_overrides(session: AsyncSession) -> None:
    """Force a refresh of overrides from the database."""
    global _loaded
    _loaded = False
    await load_overrides(session)


def clear_overrides() -> None:
    global _overrides, _loaded
    _overrides.clear()
    _loaded = False
