"""
System Settings Management Routes
----------------------------------
Admin-only APIs for managing runtime system settings.

Endpoints:
- List settings
- Get setting by key/ID
- Create setting
- Update setting
- Get setting history
"""

from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request, HTTPException, status, Query

from swx_core.database.db import SessionDep
from swx_core.models.system_config import (
    SystemConfig,
    SystemConfigCreate,
    SystemConfigUpdate,
    SystemConfigPublic,
    SystemConfigHistory,
    SettingCategory,
)
from swx_core.models.common import Message
from swx_core.auth.admin.dependencies import get_current_admin_user, AdminUserDep
from swx_core.controllers import settings_controller
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome

router = APIRouter(
    prefix="/admin/settings",
    tags=["admin-settings"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("/", response_model=List[SystemConfigPublic])
async def list_settings(
    session: SessionDep,
    category: Optional[SettingCategory] = Query(None, description="Filter by category"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> Any:
    """List all system settings, optionally filtered by category."""
    return await settings_controller.list_settings_controller(
        session,
        category.value if category else None,
        skip,
        limit,
    )


@router.get("/key/{key}", response_model=SystemConfigPublic)
async def get_setting_by_key(
    session: SessionDep,
    key: str,
) -> Any:
    """Get setting by key."""
    return await settings_controller.get_setting_controller(session, key)


@router.get("/{setting_id}", response_model=SystemConfigPublic)
async def get_setting_by_id(
    session: SessionDep,
    setting_id: UUID,
) -> Any:
    """Get setting by ID."""
    return await settings_controller.get_setting_by_id_controller(session, setting_id)


@router.post("/", response_model=SystemConfigPublic, status_code=status.HTTP_201_CREATED)
async def create_setting(
    session: SessionDep,
    setting_in: SystemConfigCreate,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Create a new system setting."""
    audit = get_audit_logger(session)
    try:
        setting = await settings_controller.create_setting_controller(
            session,
            setting_in,
            current_admin.email,
        )
        await audit.log_event(
            action="system_config.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="system_config",
            resource_id=str(setting.id),
            outcome=AuditOutcome.SUCCESS,
            context=setting_in.model_dump(),
            request=request,
        )
        return setting
    except HTTPException:
        raise
    except Exception as e:
        await audit.log_event(
            action="system_config.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="system_config",
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), **setting_in.model_dump()},
            request=request,
        )
        raise


@router.patch("/key/{key}", response_model=SystemConfigPublic)
async def update_setting_by_key(
    session: SessionDep,
    key: str,
    setting_in: SystemConfigUpdate,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Update a system setting by key."""
    audit = get_audit_logger(session)
    try:
        setting = await settings_controller.update_setting_controller(
            session,
            key,
            setting_in,
            current_admin.email,
        )
        await audit.log_event(
            action="system_config.update",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="system_config",
            resource_id=str(setting.id),
            outcome=AuditOutcome.SUCCESS,
            context={"key": key, **setting_in.model_dump()},
            request=request,
        )
        return setting
    except HTTPException:
        raise
    except Exception as e:
        await audit.log_event(
            action="system_config.update",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="system_config",
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), "key": key, **setting_in.model_dump()},
            request=request,
        )
        raise


@router.get("/key/{key}/history", response_model=List[SystemConfigHistory])
async def get_setting_history(
    session: SessionDep,
    key: str,
    limit: int = Query(50, ge=1, le=500),
) -> Any:
    """Get change history for a setting."""
    return await settings_controller.get_setting_history_controller(session, key, limit)
