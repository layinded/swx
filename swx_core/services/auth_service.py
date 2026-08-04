"""
Authentication Service
----------------------
This module provides authentication-related services, including:
- User login (local and social authentication)
- Token management (access and refresh tokens)
- User registration
- Password recovery and reset

Methods:
- `login_user_service()`: Handles user login for local accounts.
- `login_social_user_service()`: Handles login via social authentication providers.
- `refresh_access_token_service()`: Generates a new access token using a valid refresh token.
- `register_user_service()`: Registers a new user (emits user.created event).
- `logout_service()`: Revokes the refresh token to log a user out.
- `recover_password_service()`: Sends a password reset email.
- `reset_password_service()`: Resets a user's password and revokes existing tokens.

Events Emitted:
- user.created: Emitted when a new user is registered (via register_user_service)
"""

from datetime import timedelta
from typing import Any, Callable, Awaitable
from fastapi import HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm

from swx_core.email.email_service import generate_reset_password_email, send_email
from swx_core.models.common import Message
from swx_core.models.user import User, UserCreate, UserNewPassword
from swx_core.models.token import Token, TokenRefreshRequest
from swx_core.repositories.user_repository import (
    authenticate_user,
    create_user,
    get_user_by_email,
)
from swx_core.security.password_security import (
    generate_password_reset_token,
    verify_password_reset_token,
    get_password_hash,
)
from swx_core.security.refresh_token_service import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
    revoke_all_tokens,
)
from swx_core.services.billing.plan_helper import get_user_plan_key
from swx_core.rbac.helpers import get_user_permissions
from swx_core.utils.language_helper import translate


from sqlalchemy.ext.asyncio import AsyncSession


async def login_user_service(
    session: AsyncSession,
    form_data: OAuth2PasswordRequestForm,
    request: Request = None,  # pyright: ignore[reportArgumentType]
) -> Token:
    """
    Handles user login using email and password authentication.

    Args:
        session (AsyncSession): The database session.
        form_data (OAuth2PasswordRequestForm): The login form data (username & password).
        request (Request, optional): The HTTP request object.

    Returns:
        Token: A dictionary containing the access token, refresh token, and token type.
    """
    existing_user = await authenticate_user(
        session=session, email=form_data.username, password=form_data.password
    )
    if not existing_user:
        raise HTTPException(
            status_code=400, detail=translate(request, "incorrect_email_or_password")
        )
    if not existing_user.is_active:
        raise HTTPException(status_code=400, detail=translate(request, "inactive_user"))

    # Get user permissions for token scopes
    permissions = await get_user_permissions(session, existing_user.id, domain="user")
    scopes = [p.name for p in permissions] if permissions else []

    # Get token expiration from settings service (DB -> .env -> default)
    from swx_core.services.settings_helper import get_token_expiration
    access_token_expires = await get_token_expiration(session, "access")
    refresh_token_expires = await get_token_expiration(session, "refresh")
    billing_plan = await get_user_plan_key(session, existing_user.id)
    access_token = create_access_token(
        existing_user.email,
        expires_delta=access_token_expires,
        scopes=scopes or None,
        billing_plan=billing_plan,
    )
    refresh_token = await create_refresh_token(
        session, existing_user.email, expires_delta=refresh_token_expires
    )

    return Token(
        access_token=access_token, refresh_token=refresh_token, token_type="bearer"
    )


async def login_social_user_service(
    session: AsyncSession, 
    user_email: str,
    event_context: dict[str, Any] | None = None,
) -> Token:
    """
    Handles login for users authenticated via social authentication providers.

    Args:
        session (AsyncSession): The database session.
        user_email (str): The email address of the user.
        event_context (dict[str, Any] | None): Additional context for user.login.social event.

    Returns:
        Token: A dictionary containing the access token, refresh token, and token type.
    
    Emits:
        user.login.social: Event with payload {email, provider, context}
    """
    user = await get_user_by_email(session=session, email=user_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    permissions = await get_user_permissions(session, user.id, domain="user")
    scopes = [p.name for p in permissions] if permissions else []

    from swx_core.services.settings_helper import get_token_expiration
    access_token_expires = await get_token_expiration(session, "access")
    refresh_token_expires = await get_token_expiration(session, "refresh")
    billing_plan = await get_user_plan_key(session, user.id)
    access_token = create_access_token(
        user_email,
        expires_delta=access_token_expires,
        scopes=scopes or None,
        billing_plan=billing_plan,
    )
    refresh_token = await create_refresh_token(
        session, user_email, expires_delta=refresh_token_expires
    )

    from swx_core.events.dispatcher import event_bus, Event
    payload = {
        "email": user_email,
        "user_id": str(user.id),
        "provider": event_context.get("provider", "unknown") if event_context else "unknown",
        "is_new_user": event_context.get("is_new_user", False) if event_context else False,
    }
    if event_context:
        payload["context"] = event_context
    
    await event_bus.emit(Event(name="user.login.social", payload=payload))

    return Token(
        access_token=access_token, refresh_token=refresh_token, token_type="bearer"
    )


async def refresh_access_token_service(
    session: AsyncSession, request_data: TokenRefreshRequest, request: Request
) -> Token:
    """
    Generates a new access token using a valid refresh token.

    Args:
        session (AsyncSession): The database session.
        request_data (TokenRefreshRequest): The refresh token request data.
        request (Request): The HTTP request object.

    Returns:
        Token: A dictionary containing the new access token, refresh token, and token type.
    """
    result = await verify_refresh_token(session, request_data.refresh_token, request)
    if not result:
        raise HTTPException(
            status_code=401,
            detail=translate(request, "invalid_or_expired_refresh_token"),
        )
    email, auth_provider = result
    
    # Get user to fetch permissions
    user = await get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user permissions for token scopes
    permissions = await get_user_permissions(session, user.id, domain="user")
    scopes = [p.name for p in permissions] if permissions else []

    # Get token expiration from settings service (DB -> .env -> default)
    from swx_core.services.settings_helper import get_token_expiration
    access_token_expires = await get_token_expiration(session, "access")
    refresh_token_expires = await get_token_expiration(session, "refresh")
    billing_plan = await get_user_plan_key(session, user.id)
    new_access_token = create_access_token(
        email,
        expires_delta=access_token_expires,
        auth_provider=auth_provider,
        scopes=scopes or None,
        billing_plan=billing_plan,
    )
    new_refresh_token = await create_refresh_token(
        session, email, expires_delta=refresh_token_expires, auth_provider=auth_provider
    )
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


async def register_user_service(
    session: AsyncSession, 
    user_in: UserCreate, 
    request: Request,
    event_context: dict[str, Any] | None = None,
    pre_register_hook: Callable[[UserCreate, dict[str, Any]], Awaitable[UserCreate]] | None = None,
    post_register_hook: Callable[[User, dict[str, Any]], Awaitable[User | None]] | None = None,
    auth_provider: str = "local",
    provider_id: str | None = None,
) -> User:
    """
    Registers a new user account with optional lifecycle hooks.

    Args:
        session (AsyncSession): The database session.
        user_in (UserCreate): The user registration data.
        request (Request): The HTTP request object.
        event_context (dict[str, Any] | None): Additional context for user.created event
            and lifecycle hooks. Passed to both pre_register_hook and post_register_hook.
        pre_register_hook (Callable | None): Async function called BEFORE user creation.
            Receives (user_in, event_context) and must return modified UserCreate.
            Use for: validation, tenant assignment, data enrichment.
            Example:
                async def my_pre_hook(user_in: UserCreate, ctx: dict) -> UserCreate:
                    user_in.tenant_id = ctx.get("tenant_id")
                    return user_in
        post_register_hook (Callable | None): Async function called AFTER user creation.
            Receives (user, event_context) and can return modified User or None.
            Use for: organization setup, tenant creation, welcome emails, audit logging.
            Example:
                async def my_post_hook(user: User, ctx: dict) -> User:
                    await create_organization(user.id, ctx.get("org_name"))
                    return user
        auth_provider (str): The authentication provider (e.g., "local", "google", "facebook").
            Defaults to "local" for traditional email/password registration.
        provider_id (str | None): The provider-specific user ID for social auth.
            Required for social auth providers (Google sub, Facebook id, etc.).

    Returns:
        User: The newly created user (possibly modified by post_register_hook).

    Raises:
        HTTPException: If user already exists or registration fails.
    
    Emits:
        user.created: Event with payload {id, data, context}

    Hook Execution Order:
        1. pre_register_hook (modify UserCreate before creation)
        2. create_user (database insert)
        3. post_register_hook (side effects after creation)
        4. emit user.created event
        5. return user

    Example:
        async def setup_tenant(user: User, ctx: dict) -> User:
            org = await create_organization(user.id, ctx.get("organization_name"))
            await assign_user_to_org(user.id, org.id)
            return user

        user = await register_user_service(
            session=session,
            user_in=user_data,
            request=request,
            event_context={"organization_name": "Acme Corp", "tenant_id": "tenant-123"},
            post_register_hook=setup_tenant,
        )
        
        # For social auth:
        user = await register_user_service(
            session=session,
            user_in=UserCreate(email="user@example.com", password="", full_name="John"),
            request=request,
            auth_provider="google",
            provider_id="google-sub-123",
            event_context={"social_provider": "google"},
        )
    """
    context = event_context or {}
    
    # Pre-registration hook: validate/modify input before user creation
    if pre_register_hook:
        user_in = await pre_register_hook(user_in, context)
    
    existing_user = await get_user_by_email(session=session, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=400, detail=translate(request, "user_already_exists")
        )
    
    try:
        user = await create_user(
            session=session,
            user_create=user_in,
            auth_provider=auth_provider,
            provider_id=provider_id,
        )
    except Exception as e:
        from swx_core.middleware.logging_middleware import logger
        logger.error(f"Error creating user: {e}")
        error_str = str(e).lower()
        if any(
            marker in error_str
            for marker in ("unique", "duplicate", "already exists")
        ):
            raise HTTPException(
                status_code=400, detail=translate(request, "user_already_exists")
            )
        raise HTTPException(
            status_code=400, detail=f"Failed to create user: {str(e)}"
        )
    
    # Post-registration hook: side effects after user creation
    # Run outside the create_user try block so hook failures don't
    # mask a successful user creation with a 400 error.
    if post_register_hook:
        try:
            result = await post_register_hook(user, context)
            if result is not None:
                user = result
        except Exception as hook_error:
            from swx_core.middleware.logging_middleware import logger
            logger.warning(f"Post-registration hook failed for user {user.id}: {hook_error}")

    # Reload user from DB to pick up any changes made by hooks in separate
    # sessions (e.g. updated_at bumped by onupdate=func.now() during
    # cross-session UPDATEs like create_personal_team).
    await session.refresh(user)
    
    # Emit user.created event with context
    from swx_core.events.dispatcher import event_bus, Event
    payload = {
        "id": str(user.id),
        "data": {
            "email": user.email,
            "full_name": user.full_name,
            "auth_provider": user.auth_provider,
        },
    }
    if event_context is not None:
        payload["context"] = event_context
    
    await event_bus.emit(Event(name="user.created", payload=payload))
    
    return user


async def logout_service(session: AsyncSession, request_data: TokenRefreshRequest, request: Request):
    """
    Logs out the user by revoking their refresh token.

    Args:
        session (AsyncSession): The database session.
        request_data (TokenRefreshRequest): The refresh token to revoke.
        request (Request): The HTTP request object.

    Returns:
        dict: A message indicating successful logout.
    """
    result = await verify_refresh_token(session, request_data.refresh_token, request)
    if not result:
        raise HTTPException(
            status_code=401,
            detail=translate(request, "invalid_or_expired_refresh_token"),
        )
    revoked = await revoke_refresh_token(session, request_data.refresh_token)
    if not revoked:
        raise HTTPException(
            status_code=401, detail=translate(request, "token_already_revoked")
        )
    return {"message": translate(request, "logged_out_successfully")}


async def recover_password_service(
    email: str,
    session: AsyncSession,
    request: Request = None,  # pyright: ignore[reportArgumentType]
) -> Message:
    """
    Sends a password reset email to the user.

    Args:
        email (str): The user's email address.
        session (AsyncSession): The database session.
        request (Request, optional): The HTTP request object.

    Returns:
        Message: A response indicating that the reset email has been sent.
    """
    existing_user = await get_user_by_email(session=session, email=email)
    if not existing_user:
        raise HTTPException(
            status_code=404, detail=translate(request, "user_email_not_found")
        )
    if existing_user.auth_provider != "local":
        raise HTTPException(
            status_code=400, detail=translate(request, "password_reset_not_available")
        )
    if not existing_user.is_active:
        raise HTTPException(
            status_code=400, detail=translate(request, "account_disabled")
        )
    password_reset_token = await generate_password_reset_token(session, email=email)
    if password_reset_token is None:
        raise HTTPException(
            status_code=400, detail=translate(request, "password_reset_not_available")
        )
    email_data = generate_reset_password_email(
        email_to=existing_user.email, email=email, token=password_reset_token
    )
    send_email(
        email_to=existing_user.email,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message=translate(request, "password_recovery_email_sent_successfully"))


async def reset_password_service(
    session: AsyncSession,
    body: UserNewPassword,
    request: Request = None,  # pyright: ignore[reportArgumentType]
) -> Message:
    """
    Resets the user's password and revokes all active tokens.

    Args:
        session (AsyncSession): The database session.
        body (UserNewPassword): The password reset request data.
        request (Request, optional): The HTTP request object.

    Returns:
        Message: A success message indicating that the password has been reset.
    """
    token = body.token
    if token is None:
        raise HTTPException(
            status_code=400, detail=translate(request, "invalid_or_expired_reset_token")
        )

    email = verify_password_reset_token(token)
    if not email:
        raise HTTPException(
            status_code=400, detail=translate(request, "invalid_or_expired_reset_token")
        )
    existing_user = await get_user_by_email(session=session, email=email)
    if not existing_user:
        raise HTTPException(
            status_code=404, detail=translate(request, "user_not_found")
        )
    new_password = body.new_password
    if new_password is None:
        raise HTTPException(
            status_code=400, detail=translate(request, "invalid_or_expired_reset_token")
        )

    existing_user.hashed_password = await get_password_hash(new_password)
    session.add(existing_user)
    await session.commit()
    await revoke_all_tokens(session, email)
    return Message(message=translate(request, "password_reset_successful"))
