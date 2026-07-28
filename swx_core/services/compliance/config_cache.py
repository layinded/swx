import json
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.middleware.logging_middleware import logger
from swx_core.models.compliance_audit import ComplianceConfig
from swx_core.repositories import compliance_audit_repository
from swx_core.services.llm.config_resolver import mask_api_key, resolve_config

_CACHE: dict[str, tuple[list[ComplianceConfig], float]] = {}
_TTL = 30.0
_SENSITIVE = ("secret", "token", "password", "key")


def invalidate_compliance_config_cache() -> None:
    _CACHE.clear()


async def get_cached_configs(session: AsyncSession, category: str | None = None, active_only: bool = True) -> list[ComplianceConfig]:
    cache_key = f"{category or 'all'}:{active_only}"
    cached_configs = _CACHE.get(cache_key)
    current_time = time.monotonic()
    if cached_configs and current_time - cached_configs[1] < _TTL:
        return cached_configs[0]
    configs = await compliance_audit_repository.list_compliance_configs(session, category=category, active_only=active_only)
    _CACHE[cache_key] = (configs, current_time)
    return configs


def resolve_config_value(raw_value: str) -> Any:
    try:
        resolved_config = resolve_config({"value": raw_value})
        resolved_value = resolved_config.get("value")
    except ValueError as exc:
        logger.warning(
            f"Failed to resolve compliance config value '{raw_value}': {exc}"
        )
        return raw_value
    if not isinstance(resolved_value, str):
        return resolved_value
    try:
        return json.loads(resolved_value)
    except json.JSONDecodeError:
        return resolved_value


def serialize_config_value(key: str, raw_value: str) -> Any:
    value = resolve_config_value(raw_value)
    normalized_key = key.lower()
    if isinstance(value, str) and any(part in normalized_key for part in _SENSITIVE):
        return mask_api_key(value)
    return value
