"""
Settings Helper
---------------
Helper functions for accessing settings without session dependency.

Provides L1/L2 cached access to commonly used settings and feature flags.
Backward compatible: caches disabled by default.
"""

from datetime import timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings as env_settings
from swx_core.services.settings_service import get_settings_service
from swx_core.utils.runtime_cache import (
    get_cached_feature_flag,
    set_cached_feature_flag,
    get_cached_setting,
    set_cached_setting,
)


async def get_token_expiration(
    session: AsyncSession,
    token_type: str = "access",
) -> timedelta:
    """
    Get token expiration timedelta from settings.
    
    Args:
        session: Database session
        token_type: "access", "refresh", or "password_reset"
    
    Returns:
        timedelta for token expiration
    """
    service = get_settings_service(session)

    if token_type == "access":
        minutes = await service.get_int(
            "auth.access_token_expire_minutes",
            default=env_settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
        return timedelta(minutes=minutes)
    if token_type == "refresh":
        days = await service.get_int(
            "auth.refresh_token_expire_days",
            default=env_settings.REFRESH_TOKEN_EXPIRE_DAYS,
        )
        return timedelta(days=days)
    if token_type == "password_reset":
        hours = await service.get_int(
            "auth.email_reset_token_expire_hours",
            default=env_settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
        )
        return timedelta(hours=hours)

    return timedelta(minutes=env_settings.ACCESS_TOKEN_EXPIRE_MINUTES)


async def get_feature_flag(
    session: AsyncSession,
    flag_key: str,
    default: bool = False,
) -> bool:
    """Get feature flag value with L1/L2 caching.

    When FEATURE_FLAG_CACHE_ENABLED=True, checks L1 → L2 → DB.
    When disabled (default), queries DB directly (backward compatible).
    """
    if env_settings.FEATURE_FLAG_CACHE_ENABLED:
        cached = await get_cached_feature_flag(flag_key)
        if cached is not None:
            return cached

    service = get_settings_service(session)
    full_key = f"feature.{flag_key}"
    value = await service.get_bool(full_key, default=default)

    if env_settings.FEATURE_FLAG_CACHE_ENABLED:
        await set_cached_feature_flag(flag_key, value)

    return value


async def get_setting_cached(
    session: AsyncSession,
    key: str,
    default=None,
    value_type=None,
) -> Optional[object]:
    """Get a setting value with L1/L2 caching.

    When SETTINGS_CACHE_ENABLED=True, checks L1 → L2 → DB.
    When disabled (default), queries DB directly (backward compatible).
    """
    if env_settings.SETTINGS_CACHE_ENABLED:
        cached = await get_cached_setting(key)
        if cached is not None:
            return cached

    service = get_settings_service(session)
    value = await service.get(key, default, value_type)

    if env_settings.SETTINGS_CACHE_ENABLED and value is not None:
        await set_cached_setting(key, value)

    return value
