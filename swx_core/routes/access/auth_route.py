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

Methods:
- `login()`: Handles user login.
- `refresh_token()`: Generates a new access token using a refresh token.
- `register()`: Registers a new user.
- `logout()`: Revokes the user's refresh token.
- `recover_password()`: Sends a password reset email.
- `reset_password()`: Resets a user's password and revokes active tokens.
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

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

# Initialize API router with a prefix for authentication-related endpoints
router = APIRouter(prefix="/auth")


@router.post("/", response_model=Token)
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
async def register(session: SessionDep, user_in: UserCreate, request: Request):
    """
    Registers a new user.

    Args:
        session: The database session.
        user_in (UserCreate): The user registration data.
        request (Request): The HTTP request object.

    Returns:
        UserPublic: The newly created user.
    """
    audit = get_audit_logger(session)
    try:
        user = await register_controller(session, user_in, request)
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
async def recover_password(email: str, session: SessionDep, request: Request = None):
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
async def reset_password(session: SessionDep, body: UserNewPassword, request: Request = None):
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
