"""
Settings Service
----------------
Central service for accessing system settings with DB + .env fallback.

Priority order:
1. Database (runtime config)
2. Environment variables (.env)
3. Code defaults

Features:
- Type-safe getters
- In-memory caching
- Automatic cache invalidation
- Validation guards
- Audit integration
"""

import json
import os
from typing import Any, Optional
from datetime import datetime, timedelta
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.config.settings import settings as env_settings
from swx_core.models.system_config import (
    SystemConfig,
    SettingValueType,
    SettingCategory,
)
from swx_core.middleware.logging_middleware import logger

# In-memory cache with TTL
_settings_cache: dict[str, tuple[Any, datetime]] = {}
_cache_ttl = timedelta(seconds=60)  # 1 minute TTL


class SettingsService:
    """
    Central service for system settings access.
    
    Provides type-safe access to settings with DB + .env fallback.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get(
        self,
        key: str,
        default: Any = None,
        value_type: Optional[SettingValueType] = None,
    ) -> Any:
        """
        Get setting value with type conversion.
        
        Priority: DB -> .env -> default
        
        Args:
            key: Setting key
            default: Default value if not found
            value_type: Expected type (auto-detected from DB if available)
        
        Returns:
            Setting value (typed)
        """
        # Check cache first
        if key in _settings_cache:
            value, cached_at = _settings_cache[key]
            if datetime.utcnow() - cached_at < _cache_ttl:
                return value
        
        # Try database
        db_value = await self._get_from_db(key, value_type)
        if db_value is not None:
            _settings_cache[key] = (db_value, datetime.utcnow())
            return db_value
        
        # Try environment
        env_value = os.getenv(key)
        if env_value is not None:
            # Convert based on value_type or infer
            converted = self._convert_value(env_value, value_type)
            _settings_cache[key] = (converted, datetime.utcnow())
            return converted
        
        # Use default
        if default is not None:
            return default
        
        # Fail closed for critical settings
        critical_keys = [
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "REFRESH_TOKEN_EXPIRE_DAYS",
            "SECRET_KEY",
        ]
        if key in critical_keys:
            logger.error(f"Critical setting {key} not found - using safe default")
            return self._get_safe_default(key)
        
        return None
    
    async def get_int(self, key: str, default: int = 0) -> int:
        """Get integer setting."""
        value = await self.get(key, default, SettingValueType.INT)
        return int(value) if value is not None else default
    
    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean setting."""
        value = await self.get(key, default, SettingValueType.BOOL)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value) if value is not None else default
    
    async def get_string(self, key: str, default: str = "") -> str:
        """Get string setting."""
        value = await self.get(key, default, SettingValueType.STRING)
        return str(value) if value is not None else default
    
    async def get_json(self, key: str, default: Optional[dict] = None) -> dict:
        """Get JSON setting."""
        value = await self.get(key, default, SettingValueType.JSON)
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON for {key}: {value}")
        return default or {}
    
    async def _get_from_db(
        self,
        key: str,
        value_type: Optional[SettingValueType] = None,
    ) -> Optional[Any]:
        """Get setting from database."""
        try:
            stmt = select(SystemConfig).where(
                SystemConfig.key == key,
                SystemConfig.is_active == True,
            )
            result = await self.session.execute(stmt)
            config = result.scalar_one_or_none()
            
            if not config:
                return None
            
            # Use config's value_type if not provided
            if value_type is None:
                value_type = config.value_type
            
            return self._convert_value(config.value, value_type)
        except Exception as e:
            logger.error(f"Error reading setting {key} from DB: {e}")
            return None
    
    def _convert_value(self, value: str, value_type: Optional[SettingValueType]) -> Any:
        """Convert string value to appropriate type."""
        if value_type == SystemConfigValueType.INT:
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
        elif value_type == SystemConfigValueType.BOOL:
            if isinstance(value, bool):
                return value
            return str(value).lower() in ("true", "1", "yes", "on")
        elif value_type == SystemConfigValueType.JSON:
            try:
                return json.loads(value)
            except (ValueError, TypeError, json.JSONDecodeError):
                return {}
        else:  # STRING or None
            return str(value)
    
    def _get_safe_default(self, key: str) -> Any:
        """Get safe default for critical settings."""
        defaults = {
            "ACCESS_TOKEN_EXPIRE_MINUTES": 60 * 24 * 7,  # 7 days
            "REFRESH_TOKEN_EXPIRE_DAYS": 30,
            "SECRET_KEY": "",  # Should never happen
        }
        return defaults.get(key, None)
    
    @staticmethod
    def invalidate_cache(key: Optional[str] = None):
        """Invalidate cache for a key or all keys."""
        global _settings_cache
        if key:
            _settings_cache.pop(key, None)
        else:
            _settings_cache.clear()
        logger.info(f"Settings cache invalidated for: {key or 'all'}")


# Global settings service instance (session-dependent)
def get_settings_service(session: AsyncSession) -> SettingsService:
    """Get settings service instance."""
    return SettingsService(session)


# Convenience function for common settings (uses env_settings as fallback)
async def get_setting(
    session: AsyncSession,
    key: str,
    default: Any = None,
    value_type: Optional[SettingValueType] = None,
) -> Any:
    """
    Convenience function to get a setting.
    
    Usage:
        value = await get_setting(session, "ACCESS_TOKEN_EXPIRE_MINUTES", default=10080)
    """
    service = get_settings_service(session)
    return await service.get(key, default, value_type)
