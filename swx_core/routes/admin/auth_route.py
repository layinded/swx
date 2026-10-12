from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm

from swx_core.database.db import SessionDep
from swx_core.models.token import Token, TokenRefreshRequest
from swx_core.controllers.admin_auth_controller import (
    login_admin_controller,
    refresh_admin_token_controller,
    logout_admin_controller,
)
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource, AlertActorType
from swx_core.utils.rate_limit import rate_limit_by_ip

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


@router.post("/", response_model=Token)
@rate_limit_by_ip(max_requests=5, window_seconds=60, action="admin_login")
async def login_admin(
    session: SessionDep,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    audit = get_audit_logger(session)
    try:
        token = await login_admin_controller(session, form_data, request)
        await audit.log_event(
            action="admin.login",
            actor_type=ActorType.ADMIN,
            actor_id=form_data.username,
            outcome=AuditOutcome.SUCCESS,
            request=request,
        )
        return token
    except HTTPException:
        await audit.log_event(
            action="admin.login",
            actor_type=ActorType.ADMIN,
            actor_id=form_data.username,
            outcome=AuditOutcome.FAILURE,
            context={"reason": "Invalid credentials"},
            request=request,
        )
        await alert_engine.emit(
            severity=AlertSeverity.ERROR,
            source=AlertSource.AUTH,
            event_type="ADMIN_LOGIN_FAILURE",
            message=f"Failed admin login attempt: {form_data.username}",
            actor_type=AlertActorType.ADMIN,
            actor_id=form_data.username,
            metadata={"reason": "Invalid credentials"},
        )
        raise


@router.post("/refresh", response_model=Token)
async def refresh_admin_token(
    session: SessionDep, request_data: TokenRefreshRequest, request: Request
) -> Token:
    audit = get_audit_logger(session)
    try:
        token = await refresh_admin_token_controller(session, request_data, request)
        await audit.log_event(
            action="admin.token.refresh",
            actor_type=ActorType.ADMIN,
            outcome=AuditOutcome.SUCCESS,
            request=request,
        )
        return token
    except Exception as e:
        await audit.log_event(
            action="admin.token.refresh",
            actor_type=ActorType.ADMIN,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request,
        )
        raise


@router.post("/revoke")
async def logout_admin(session: SessionDep, request_data: TokenRefreshRequest, request: Request):
    audit = get_audit_logger(session)
    try:
        result = await logout_admin_controller(session, request_data, request)
        await audit.log_event(
            action="admin.logout",
            actor_type=ActorType.ADMIN,
            outcome=AuditOutcome.SUCCESS,
            request=request,
        )
        return result
    except Exception as e:
        await audit.log_event(
            action="admin.logout",
            actor_type=ActorType.ADMIN,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request,
        )
        raise
