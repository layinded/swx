"""
Settings CRUD Service
---------------------
Service layer for system settings CRUD operations with validation and audit.
"""

import json
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.system_config import (
    SystemConfig,
    SystemConfigCreate,
    SystemConfigUpdate,
    SystemConfigHistory,
    SettingValueType,
    SettingCategory,
)
from swx_core.middleware.logging_middleware import logger
from swx_core.services.settings_service import SettingsService
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource, AlertActorType


# Settings that should trigger alerts when changed
HIGH_RISK_SETTINGS = {
    "auth.access_token_expire_minutes",
    "auth.refresh_token_expire_days",
    "rate_limit.free.read.burst",
    "rate_limit.free.write.burst",
}


def validate_setting_value(value: str, value_type: SettingValueType) -> bool:
    """Validate setting value matches its type."""
    try:
        if value_type == SettingValueType.INT:
            int(value)
        elif value_type == SettingValueType.BOOL:
            str(value).lower() in ("true", "false", "1", "0", "yes", "no", "on", "off")
        elif value_type == SettingValueType.JSON:
            json.loads(value)
        # STRING always valid
        return True
    except (ValueError, json.JSONDecodeError):
        return False


def validate_security_guards(key: str, value: str, value_type: SettingValueType) -> tuple[bool, Optional[str]]:
    """
    Validate security guards for setting updates.
    
    Returns:
        (is_valid, error_message)
    """
    # Prevent secrets from being stored
    secret_keywords = ["secret", "password", "key", "token", "credential"]
    if any(kw in key.lower() for kw in secret_keywords):
        return False, f"Setting key '{key}' contains secret keyword - secrets must remain in .env"
    
    # Prevent invalid token expiration
    if "token_expire" in key.lower() or "expire_minutes" in key.lower():
        try:
            expire_value = int(value)
            if expire_value <= 0:
                return False, f"Token expiration must be positive, got {expire_value}"
            if expire_value > 60 * 24 * 365:  # 1 year max
                return False, f"Token expiration too large: {expire_value} minutes (max 1 year)"
        except (ValueError, TypeError):
            return False, f"Invalid expiration value: {value}"
    
    # Prevent invalid rate limits
    if "rate_limit" in key.lower():
        try:
            limit_value = int(value)
            if limit_value < 0:
                return False, f"Rate limit must be non-negative, got {limit_value}"
        except (ValueError, TypeError):
            return False, f"Invalid rate limit value: {value}"
    
    return True, None


async def list_settings_service(
    session: AsyncSession,
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[SystemConfig]:
    """List all system settings, optionally filtered by category."""
    stmt = select(SystemConfig).where(SystemConfig.is_active == True)
    if category:
        stmt = stmt.where(SystemConfig.category == category)
    stmt = stmt.offset(skip).limit(limit).order_by(SystemConfig.key)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_setting_service(
    session: AsyncSession,
    key: str,
    raise_on_not_found: bool = True,
) -> SystemConfig | None:
    """Get setting by key."""
    stmt = select(SystemConfig).where(
        SystemConfig.key == key,
        SystemConfig.is_active == True,
    )
    result = await session.execute(stmt)
    config = result.scalar_one_or_none()
    if not config:
        if raise_on_not_found:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
        return None
    return config


async def get_setting_by_id_service(
    session: AsyncSession,
    setting_id: UUID,
) -> SystemConfig:
    """Get setting by ID."""
    config = await session.get(SystemConfig, setting_id)
    if not config:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Setting not found")
    return config


async def create_setting_service(
    session: AsyncSession,
    setting_in: SystemConfigCreate,
    updated_by: str,
) -> SystemConfig:
    """Create a new setting with validation."""
    # Check if exists
    existing = await get_setting_service(session, setting_in.key, raise_on_not_found=False)
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=f"Setting '{setting_in.key}' already exists")
    
    # Validate value
    if not validate_setting_value(setting_in.value, setting_in.value_type):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Invalid value '{setting_in.value}' for type {setting_in.value_type}"
        )
    
    # Security guards
    is_valid, error_msg = validate_security_guards(setting_in.key, setting_in.value, setting_in.value_type)
    if not is_valid:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Create setting
    config = SystemConfig(
        key=setting_in.key,
        value=setting_in.value,
        value_type=setting_in.value_type,
        category=setting_in.category,
        description=setting_in.description,
        is_sensitive=False,  # Always False - validation enforces
        updated_by=updated_by,
        metadata_=setting_in.metadata or {},
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    
    # Invalidate cache
    SettingsService.invalidate_cache(setting_in.key)
    
    logger.info(f"Created setting: {setting_in.key} = {setting_in.value}")
    return config


async def update_setting_service(
    session: AsyncSession,
    key: str,
    setting_in: SystemConfigUpdate,
    updated_by: str,
) -> SystemConfig:
    """Update a setting with validation and audit."""
    # Get existing
    config = await get_setting_service(session, key)
    old_value = config.value
    
    # Update fields
    if setting_in.value is not None:
        # Validate new value against existing config's type
        if not validate_setting_value(setting_in.value, config.value_type):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail=f"Invalid value '{setting_in.value}' for type {config.value_type}"
            )
        
        # Security guards
        is_valid, error_msg = validate_security_guards(key, setting_in.value, config.value_type)
        if not is_valid:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=error_msg)
        
        config.value = setting_in.value
    
    if setting_in.description is not None:
        config.description = setting_in.description
    if setting_in.is_active is not None:
        config.is_active = setting_in.is_active
    if setting_in.metadata is not None:
        config.metadata_ = setting_in.metadata
    
    config.updated_by = updated_by
    config.updated_at = datetime.utcnow()
    
    # Create history record
    history = SystemConfigHistory(
        config_id=config.id,
        key=config.key,
        old_value=old_value,
        new_value=config.value,
        updated_by=updated_by,
    )
    session.add(history)
    
    await session.commit()
    await session.refresh(config)
    
    # Invalidate cache
    SettingsService.invalidate_cache(key)
    
    # Audit log
    audit = get_audit_logger(session)
    await audit.log_event(
        action="system_config.update",
        actor_type=ActorType.ADMIN,
        actor_id=updated_by,
        resource_type="system_config",
        resource_id=str(config.id),
        outcome=AuditOutcome.SUCCESS,
        context={
            "key": key,
            "old_value": old_value,
            "new_value": config.value,
        },
    )
    
    # Alert on high-risk changes
    if key in HIGH_RISK_SETTINGS:
        await alert_engine.emit(
            severity=AlertSeverity.WARNING,
            source=AlertSource.SYSTEM,
            event_type="SETTING_HIGH_RISK_CHANGE",
            message=f"High-risk setting '{key}' updated: {old_value} -> {config.value}",
            actor_type=AlertActorType.ADMIN,
            actor_id=updated_by,
            metadata={
                "key": key,
                "old_value": old_value,
                "new_value": config.value,
            }
        )
    
    logger.info(f"Updated setting: {key} = {old_value} -> {config.value} (by {updated_by})")
    return config


async def get_setting_history_service(
    session: AsyncSession,
    key: str,
    limit: int = 50,
) -> List[SystemConfigHistory]:
    """Get change history for a setting."""
    # First get the config to find its ID
    config = await get_setting_service(session, key)
    
    stmt = select(SystemConfigHistory).where(
        SystemConfigHistory.config_id == config.id
    ).order_by(SystemConfigHistory.updated_at.desc()).limit(limit)
    
    result = await session.execute(stmt)
    return list(result.scalars().all())
