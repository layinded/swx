"""
Settings Helper
---------------
Helper functions for accessing settings without session dependency.

Provides cached access to commonly used settings.
"""

from datetime import timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings as env_settings
from swx_core.services.settings_service import get_settings_service


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
    elif token_type == "refresh":
        days = await service.get_int(
            "auth.refresh_token_expire_days",
            default=env_settings.REFRESH_TOKEN_EXPIRE_DAYS,
        )
        return timedelta(days=days)
    elif token_type == "password_reset":
        hours = await service.get_int(
            "auth.email_reset_token_expire_hours",
            default=env_settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
        )
        return timedelta(hours=hours)
    else:
        # Default fallback
        return timedelta(minutes=env_settings.ACCESS_TOKEN_EXPIRE_MINUTES)


async def get_feature_flag(
    session: AsyncSession,
    flag_key: str,
    default: bool = False,
) -> bool:
    """
    Get feature flag value.
    
    Args:
        session: Database session
        flag_key: Feature flag key (e.g., "enable_google_login")
        default: Default value if not found
    
    Returns:
        bool: Feature flag value
    """
    service = get_settings_service(session)
    full_key = f"feature.{flag_key}"
    return await service.get_bool(full_key, default=default)
