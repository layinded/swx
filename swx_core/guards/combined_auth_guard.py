"""Combined JWT-or-API-key Guard
---------------------------------
FastAPI dependency that tries JWT authentication first, then falls back
to API key.  Returns an ``AuthenticatedUser`` annotated with
``auth_mode`` in metadata so callers can tell which guard succeeded.

Uses the existing ``GuardManager`` to compose guards.  Early return on
success — no nested conditionals.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Request, status

from swx_core.guards.base import AuthenticatedUser
from swx_core.guards.guard_manager import GuardManager, get_guard_manager


async def _get_authenticated_user(
    request: Request,
    manager: GuardManager = Depends(get_guard_manager),
) -> AuthenticatedUser:
    """FastAPI dependency: authenticate via JWT (primary) or API key (fallback).

    Raises:
        HTTPException(401): If neither guard authenticates the request.
    """
    # 1. Try JWT guard
    jwt_user = await manager.authenticate(request, guard="jwt")
    if jwt_user is not None:
        jwt_user.metadata["auth_mode"] = "jwt"
        return jwt_user

    # 2. Fallback to API key guard
    api_user = await manager.authenticate(request, guard="api_key")
    if api_user is not None:
        api_user.metadata["auth_mode"] = "api_key"
        return api_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required — provide a valid JWT or API key",
    )


async def _get_authenticated_user_optional(
    request: Request,
    manager: GuardManager = Depends(get_guard_manager),
) -> AuthenticatedUser | None:
    """Optional variant: returns ``None`` instead of raising when unauthenticated."""
    jwt_user = await manager.authenticate(request, guard="jwt")
    if jwt_user is not None:
        jwt_user.metadata["auth_mode"] = "jwt"
        return jwt_user

    api_user = await manager.authenticate(request, guard="api_key")
    if api_user is not None:
        api_user.metadata["auth_mode"] = "api_key"
        return api_user

    return None


AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(_get_authenticated_user)]
"""Inject a fully-authenticated user (JWT or API key) into route handlers.

Raises 401 if neither guard succeeds.

Usage::

    @router.get("/me")
    async def get_me(user: AuthenticatedUserDep):
        ...
"""

OptionalAuthenticatedUserDep = Annotated[
    AuthenticatedUser | None, Depends(_get_authenticated_user_optional)
]
"""Inject an optional authenticated user into route handlers.

Returns ``None`` if unauthenticated — use for public endpoints that
optionally identify the caller.

Usage::

    @router.get("/public-feed")
    async def public_feed(user: OptionalAuthenticatedUserDep):
        ...
"""