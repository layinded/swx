from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from swx_core.database.db import SessionDep
from swx_core.models.admin_user import AdminUser, AdminUserPublic
from swx_core.models.token import Token
from swx_core.security.password_security import verify_password
from swx_core.auth.core.jwt import create_token, TokenAudience
from swx_core.config.settings import settings
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource, AlertActorType

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

@router.post("/", response_model=Token)
async def login_admin(
    session: SessionDep,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    Login for Admin domain users.
    """
    audit = get_audit_logger(session)
    statement = select(AdminUser).where(AdminUser.email == form_data.username)
    result = await session.execute(statement)
    admin_user = result.scalar_one_or_none()
    
    if not admin_user or not await verify_password(form_data.password, admin_user.hashed_password):
        await audit.log_event(
            action="admin.login",
            actor_type=ActorType.ADMIN,
            actor_id=form_data.username,
            outcome=AuditOutcome.FAILURE,
            context={"reason": "Invalid credentials"},
            request=request
        )
        await alert_engine.emit(
            severity=AlertSeverity.ERROR,
            source=AlertSource.AUTH,
            event_type="ADMIN_LOGIN_FAILURE",
            message=f"Failed admin login attempt: {form_data.username}",
            actor_type=AlertActorType.ADMIN,
            actor_id=form_data.username,
            metadata={"reason": "Invalid credentials"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin email or password",
        )
    
    if not admin_user.is_active:
        await audit.log_event(
            action="admin.login",
            actor_type=ActorType.ADMIN,
            actor_id=admin_user.email,
            outcome=AuditOutcome.FAILURE,
            context={"reason": "Inactive user"},
            request=request
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive admin user",
        )

    await audit.log_event(
        action="admin.login",
        actor_type=ActorType.ADMIN,
        actor_id=admin_user.email,
        outcome=AuditOutcome.SUCCESS,
        request=request
    )

    # Get token expiration from settings service (DB -> .env -> default)
    from swx_core.services.settings_helper import get_token_expiration
    access_token_expires = await get_token_expiration(session, "access")
    return Token(
        access_token=create_token(
            admin_user.email, TokenAudience.ADMIN, expires_delta=access_token_expires
        ),
        token_type="bearer",
    )
