from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from starlette.responses import Response, JSONResponse

from swx_core.auth.core.jwt import create_token, TokenAudience
from swx_core.config.settings import settings
from swx_core.database.db import SessionDep
from swx_core.repositories.admin_user_repository import authenticate_admin
from swx_core.security.refresh_token_service import create_refresh_token, revoke_refresh_token
from swx_core.services.admin_auth_service import (
    verify_admin_cookie_refresh,
    set_auth_cookies,
    clear_auth_cookies,
)
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome
from swx_core.services.settings_helper import get_token_expiration
from swx_core.utils.rate_limit import rate_limit_by_ip

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


@router.post("/cookie/login")
@rate_limit_by_ip(max_requests=5, window_seconds=60, action="admin_cookie_login")
async def cookie_login(
    request: Request,
    session: SessionDep,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    audit = get_audit_logger(session)
    admin_user = await authenticate_admin(
        session=session, email=form_data.username, password=form_data.password
    )

    if not admin_user:
        await audit.log_event(
            action="admin.cookie.login",
            actor_type=ActorType.ADMIN,
            actor_id=form_data.username,
            outcome=AuditOutcome.FAILURE,
            context={"reason": "Invalid credentials"},
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin email or password",
        )

    if not admin_user.is_active:
        await audit.log_event(
            action="admin.cookie.login",
            actor_type=ActorType.ADMIN,
            actor_id=admin_user.email,
            outcome=AuditOutcome.FAILURE,
            context={"reason": "Inactive user"},
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive admin user",
        )

    access_token_expires = await get_token_expiration(session, "access")
    refresh_token_expires = await get_token_expiration(session, "refresh")

    access_token = create_token(admin_user.email, TokenAudience.ADMIN, expires_delta=access_token_expires)
    refresh_token = await create_refresh_token(
        session, admin_user.email, expires_delta=refresh_token_expires
    )

    response = JSONResponse({
        "email": admin_user.email,
        "message": "Admin authentication successful",
    })

    set_auth_cookies(
        response,
        access_token=access_token,
        refresh_token=refresh_token,
        access_max_age=int(access_token_expires.total_seconds()),
        refresh_max_age=int(refresh_token_expires.total_seconds()),
    )

    await audit.log_event(
        action="admin.cookie.login",
        actor_type=ActorType.ADMIN,
        actor_id=admin_user.email,
        outcome=AuditOutcome.SUCCESS,
        request=request,
    )
    return response


@router.post("/cookie/refresh")
@rate_limit_by_ip(max_requests=10, window_seconds=60, action="admin_cookie_refresh")
async def cookie_refresh(
    request: Request,
    session: SessionDep,
):
    refresh_token = request.cookies.get(settings.COOKIE_REFRESH_TOKEN_NAME)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token in cookie")

    audit = get_audit_logger(session)
    try:
        admin_user, email, auth_provider = await verify_admin_cookie_refresh(
            session, refresh_token, request
        )

        access_token_expires = await get_token_expiration(session, "access")
        refresh_token_expires = await get_token_expiration(session, "refresh")

        new_access_token = create_token(email, TokenAudience.ADMIN, expires_delta=access_token_expires)
        new_refresh_token = await create_refresh_token(
            session, email, expires_delta=refresh_token_expires, auth_provider=auth_provider
        )

        response = JSONResponse({"status": "ok"})

        set_auth_cookies(
            response,
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            access_max_age=int(access_token_expires.total_seconds()),
            refresh_max_age=int(refresh_token_expires.total_seconds()),
        )

        await audit.log_event(
            action="admin.cookie.refresh",
            actor_type=ActorType.ADMIN,
            actor_id=email,
            outcome=AuditOutcome.SUCCESS,
            request=request,
        )
        return response
    except Exception as e:
        await audit.log_event(
            action="admin.cookie.refresh",
            actor_type=ActorType.ADMIN,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request,
        )
        raise


@router.post("/cookie/logout")
async def cookie_logout(request: Request, session: SessionDep):
    audit = get_audit_logger(session)
    try:
        refresh_token = request.cookies.get(settings.COOKIE_REFRESH_TOKEN_NAME)
        if refresh_token:
            await revoke_refresh_token(session, refresh_token)

        response = Response(
            content='{"message": "Admin logged out successfully"}',
            media_type="application/json",
            status_code=200,
        )

        clear_auth_cookies(response)

        await audit.log_event(
            action="admin.cookie.logout",
            actor_type=ActorType.ADMIN,
            outcome=AuditOutcome.SUCCESS,
            request=request,
        )
        return response
    except Exception as e:
        await audit.log_event(
            action="admin.cookie.logout",
            actor_type=ActorType.ADMIN,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request,
        )
        raise