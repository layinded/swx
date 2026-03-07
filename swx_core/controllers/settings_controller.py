"""
Settings Controller
------------------
Controller layer for system settings management.
"""

from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.system_config import (
    SystemConfig,
    SystemConfigCreate,
    SystemConfigUpdate,
    SystemConfigPublic,
    SystemConfigHistory,
)
from swx_core.services import settings_crud_service


async def list_settings_controller(
    session: AsyncSession,
    category: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> List[SystemConfig]:
    """List all system settings."""
    return await settings_crud_service.list_settings_service(session, category, skip, limit)


async def get_setting_controller(
    session: AsyncSession,
    key: str,
) -> SystemConfig:
    """Get setting by key."""
    config = await settings_crud_service.get_setting_service(session, key, raise_on_not_found=True)
    if not config:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return config


async def get_setting_by_id_controller(
    session: AsyncSession,
    setting_id: UUID,
) -> SystemConfig:
    """Get setting by ID."""
    return await settings_crud_service.get_setting_by_id_service(session, setting_id)


async def create_setting_controller(
    session: AsyncSession,
    setting_in: SystemConfigCreate,
    updated_by: str,
) -> SystemConfig:
    """Create a new setting."""
    return await settings_crud_service.create_setting_service(session, setting_in, updated_by)


async def update_setting_controller(
    session: AsyncSession,
    key: str,
    setting_in: SystemConfigUpdate,
    updated_by: str,
) -> SystemConfig:
    """Update a setting."""
    return await settings_crud_service.update_setting_service(session, key, setting_in, updated_by)


async def get_setting_history_controller(
    session: AsyncSession,
    key: str,
    limit: int = 50,
) -> List[SystemConfigHistory]:
    """Get change history for a setting."""
    return await settings_crud_service.get_setting_history_service(session, key, limit)
