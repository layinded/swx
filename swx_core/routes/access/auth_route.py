"""
Authentication Routes
----------------------
This module defines the API routes for authentication-related operations.

Features:
- User login (local authentication).
- Token refresh for authentication renewal.
- User registration.
- User logout (revoking refresh tokens).
- Password recovery and reset.
- Cookie-based authentication (BFF pattern).

Methods:
- `login()`: Handles user login.
- `refresh_token()`: Generates a new access token using a refresh token.
- `register()`: Registers a new user.
- `logout()`: Revokes the user's refresh token.
- `recover_password()`: Sends a password reset email.
- `reset_password()`: Resets a user's password and revokes active tokens.
- `get_me()`: Returns current authenticated user (cookie-auth compatible).
- `cookie_login()`: Login with email/password, sets httpOnly cookies.
- `cookie_refresh()`: Refresh tokens using httpOnly cookie.
- `cookie_logout()`: Clears httpOnly auth cookies.
"""

from typing import Any
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from starlette.responses import Response, JSONResponse

from swx_core.controllers.auth_controller import (
    login_controller,
    logout_controller,
    refresh_token_controller,
    recover_password_controller,
    reset_password_controller,
    register_controller,
)
from swx_core.database.db import SessionDep
from swx_core.models.common import Message
from swx_core.models.token import Token, TokenRefreshRequest
from swx_core.models.user import UserCreate, UserNewPassword, UserPublic
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource, AlertActorType
from swx_core.services.settings_helper import get_token_expiration
from swx_core.config.settings import settings
from swx_core.auth.user.dependencies import UserDep
from swx_core.utils.rate_limit import rate_limit_by_ip

router = APIRouter(prefix="/auth")


@router.post("/", response_model=Token)
@rate_limit_by_ip(max_requests=5, window_seconds=60, action="login")
async def login(
    session: SessionDep,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    """
    Handles user login.

    Args:
        session: The database session.
        form_data (OAuth2PasswordRequestForm): The login form containing username and password.
        request (Request, optional): The HTTP request object.

    Returns:
        Token: A dictionary containing the access token, refresh token, and token type.
    """
    audit = get_audit_logger(session)
    try:
        token = await login_controller(session, form_data, request)
        await audit.log_event(
            action="user.login",
            actor_type=ActorType.USER,
            actor_id=form_data.username,
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return token
    except Exception as e:
        await audit.log_event(
            action="user.login",
            actor_type=ActorType.USER,
            actor_id=form_data.username,
            outcome=AuditOutcome.FAILURE,
            context={"reason": str(e)},
            request=request
        )
        await alert_engine.emit(
            severity=AlertSeverity.WARNING,
            source=AlertSource.AUTH,
            event_type="LOGIN_FAILURE",
            message=f"Failed login attempt for user: {form_data.username}",
            actor_type=AlertActorType.USER,
            actor_id=form_data.username,
            metadata={"error": str(e)}
        )
        raise e


@router.post("/refresh", response_model=Token)
async def refresh_token(
    session: SessionDep, request_data: TokenRefreshRequest, request: Request
) -> Token:
    """
    Generates a new access token using a refresh token.

    Args:
        session: The database session.
        request_data (TokenRefreshRequest): The refresh token request data.
        request (Request): The HTTP request object.

    Returns:
        Token: A dictionary containing the new access token, refresh token, and token type.
    """
    audit = get_audit_logger(session)
    try:
        token = await refresh_token_controller(session, request_data, request)
        # We don't log the token itself, but we can log that a refresh happened
        await audit.log_event(
            action="user.token.refresh",
            actor_type=ActorType.USER,
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return token
    except Exception as e:
        await audit.log_event(
            action="user.token.refresh",
            actor_type=ActorType.USER,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise e


@router.post("/register", response_model=UserPublic, operation_id="register_new_user")
@rate_limit_by_ip(max_requests=3, window_seconds=3600, action="register")
async def register(
    session: SessionDep, 
    user_in: UserCreate, 
    request: Request,
    event_context: dict[str, Any] | None = None,
):
    """
    Registers a new user.

    Args:
        session: The database session.
        user_in (UserCreate): The user registration data.
        request (Request): The HTTP request object.
        event_context (dict[str, Any] | None): Additional context for user.created event.

    Returns:
        UserPublic: The newly created user.
    """
    audit = get_audit_logger(session)
    try:
        user = await register_controller(session, user_in, request, event_context)
        await audit.log_event(
            action="user.register",
            actor_type=ActorType.USER,
            actor_id=str(user.id),
            outcome=AuditOutcome.SUCCESS,
            context=user_in.model_dump(),
            request=request
        )
        return user
    except Exception as e:
        await audit.log_event(
            action="user.register",
            actor_type=ActorType.USER,
            actor_id=user_in.email,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), **user_in.model_dump()},
            request=request
        )
        raise e


@router.post("/revoke")
async def logout(session: SessionDep, request_data: TokenRefreshRequest, request: Request):
    """
    Logs out the user by revoking their refresh token.

    Args:
        session: The database session.
        request_data (TokenRefreshRequest): The refresh token to revoke.
        request (Request): The HTTP request object.

    Returns:
        dict: A message indicating successful logout.
    """
    audit = get_audit_logger(session)
    try:
        res = await logout_controller(session, request_data, request)
        await audit.log_event(
            action="user.logout",
            actor_type=ActorType.USER,
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return res
    except Exception as e:
        await audit.log_event(
            action="user.logout",
            actor_type=ActorType.USER,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise e


@router.post("/password/recover/{email}", response_model=Message)
@rate_limit_by_ip(max_requests=3, window_seconds=3600, action="password_recover")
async def recover_password(email: str, session: SessionDep, request: Request):
    """
    Sends a password reset email to the user.

    Args:
        email (str): The user's email address.
        session: The database session.
        request (Request, optional): The HTTP request object.

    Returns:
        Message: A response indicating that the reset email has been sent.
    """
    audit = get_audit_logger(session)
    try:
        res = await recover_password_controller(email, session, request)
        await audit.log_event(
            action="user.password.recover",
            actor_type=ActorType.USER,
            actor_id=email,
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return res
    except Exception as e:
        await audit.log_event(
            action="user.password.recover",
            actor_type=ActorType.USER,
            actor_id=email,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise e


@router.post("/password/reset", response_model=Message)
async def reset_password(session: SessionDep, body: UserNewPassword, request: Request):
    """
    Resets the user's password and revokes all active tokens.

    Args:
        session (Session): The database session.
        body (UserNewPassword): The password reset request data.
        request (Request, optional): The HTTP request object.

    Returns:
        Message: A success message indicating that the password has been reset.
    """
    audit = get_audit_logger(session)
    try:
        res = await reset_password_controller(session, body, request)
        await audit.log_event(
            action="user.password.reset",
            actor_type=ActorType.USER,
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return res
    except Exception as e:
        await audit.log_event(
            action="user.password.reset",
            actor_type=ActorType.USER,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise e


@router.post("/cookie/logout")
async def cookie_logout(request: Request, session: SessionDep):
    """
    Clears HTTP-only auth cookies for cookie-based authentication.

    Use this endpoint when using the BFF (Backend-for-Frontend) pattern
    where tokens are stored in HTTP-only cookies instead of localStorage.

    Returns:
        dict: A message indicating successful logout.
    """
    audit = get_audit_logger(session)
    try:
        response = Response(
            content='{"message": "Logged out successfully"}',
            media_type="application/json",
            status_code=200,
        )
        
        response.delete_cookie(
            key=settings.COOKIE_ACCESS_TOKEN_NAME,
            path="/",
            domain=settings.COOKIE_DOMAIN,
        )
        response.delete_cookie(
            key=settings.COOKIE_REFRESH_TOKEN_NAME,
            path="/api",
            domain=settings.COOKIE_DOMAIN,
        )
        
        await audit.log_event(
            action="user.cookie.logout",
            actor_type=ActorType.USER,
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return response
    except Exception as e:
        await audit.log_event(
            action="user.cookie.logout",
            actor_type=ActorType.USER,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise e


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: UserDep):
    """
    Returns current authenticated user profile.

    Works with both Authorization header and httpOnly cookie authentication.
    Used by frontend to check auth state on app boot.

    Returns:
        UserPublic: The authenticated user's profile.
    """
    return UserPublic.model_validate(current_user)


@router.post("/cookie/login")
@rate_limit_by_ip(max_requests=5, window_seconds=60, action="cookie_login")
async def cookie_login(
    request: Request,
    session: SessionDep,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    Authenticate with email/password and set httpOnly auth cookies.

    For browser-based apps using cookie-based auth (BFF pattern).
    Returns user profile JSON in the response body.
    Sets swx_access_token and swx_refresh_token as httpOnly cookies.

    Returns:
        JSONResponse: User profile with cookies set.
    """
    audit = get_audit_logger(session)
    try:
        auth_token = await login_controller(session, form_data, request)
        
        access_expires = await get_token_expiration(session, "access")
        refresh_expires = await get_token_expiration(session, "refresh")

        response = JSONResponse({
            "email": form_data.username,
            "message": "Authentication successful",
        })
        
        secure = settings.COOKIE_SECURE and settings.ENVIRONMENT != "local"
        samesite = settings.COOKIE_SAMESITE
        domain = settings.COOKIE_DOMAIN

        response.set_cookie(
            key=settings.COOKIE_ACCESS_TOKEN_NAME,
            value=auth_token.access_token,
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=int(access_expires.total_seconds()),
            path="/",
            domain=domain,
        )
        if auth_token.refresh_token:
            response.set_cookie(
                key=settings.COOKIE_REFRESH_TOKEN_NAME,
                value=auth_token.refresh_token,
                httponly=True,
                secure=secure,
                samesite=samesite,
                max_age=int(refresh_expires.total_seconds()),
                path="/api",
                domain=domain,
            )

        await audit.log_event(
            action="user.cookie.login",
            actor_type=ActorType.USER,
            actor_id=form_data.username,
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return response
    except Exception as e:
        await audit.log_event(
            action="user.cookie.login",
            actor_type=ActorType.USER,
            actor_id=form_data.username,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise e


@router.post("/cookie/refresh")
@rate_limit_by_ip(max_requests=10, window_seconds=60, action="cookie_refresh")
async def cookie_refresh(
    request: Request,
    session: SessionDep,
):
    """
    Refresh access token using httpOnly refresh cookie.

    Reads swx_refresh_token from cookies, validates it,
    issues new access + refresh tokens, sets new cookies.

    Returns:
        JSONResponse: Success message with new cookies set.
    """
    refresh_token = request.cookies.get(settings.COOKIE_REFRESH_TOKEN_NAME)
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="No refresh token in cookie"
        )

    audit = get_audit_logger(session)
    try:
        auth_token = await refresh_token_controller(
            session,
            TokenRefreshRequest(refresh_token=refresh_token),
            request,
        )

        access_expires = await get_token_expiration(session, "access")
        refresh_expires = await get_token_expiration(session, "refresh")

        response = JSONResponse({"status": "ok"})

        secure = settings.COOKIE_SECURE and settings.ENVIRONMENT != "local"
        samesite = settings.COOKIE_SAMESITE
        domain = settings.COOKIE_DOMAIN

        response.set_cookie(
            key=settings.COOKIE_ACCESS_TOKEN_NAME,
            value=auth_token.access_token,
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=int(access_expires.total_seconds()),
            path="/",
            domain=domain,
        )
        if auth_token.refresh_token:
            response.set_cookie(
                key=settings.COOKIE_REFRESH_TOKEN_NAME,
                value=auth_token.refresh_token,
                httponly=True,
                secure=secure,
                samesite=samesite,
                max_age=int(refresh_expires.total_seconds()),
                path="/api",
                domain=domain,
            )

        await audit.log_event(
            action="user.cookie.refresh",
            actor_type=ActorType.USER,
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return response
    except Exception as e:
        await audit.log_event(
            action="user.cookie.refresh",
            actor_type=ActorType.USER,
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise e
