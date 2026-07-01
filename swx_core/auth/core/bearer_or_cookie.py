"""
Bearer or Cookie Authentication
--------------------------------
Authentication scheme that extracts JWT from Authorization header or httpOnly cookie.

This enables the Backend-for-Frontend (BFF) pattern where:
- API clients use Authorization: Bearer header (existing behavior)
- Browser clients use httpOnly cookies (automatic with credentials: 'include')

Security:
- httpOnly cookies prevent XSS token theft
- SameSite attribute prevents CSRF
- Backward compatible with existing Authorization header usage
"""

from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

from swx_core.config.settings import settings


class BearerOrCookieAuth:
    """
    Extract JWT from Authorization header, falling back to httpOnly cookie.

    Priority:
    1. Authorization: Bearer <token> header
    2. swx_access_token cookie

    This allows both API clients and browser-based apps to authenticate
    using the same endpoints without code changes.
    """

    scheme_name: str = "BearerOrCookie"

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        """
        Extract credentials from request.

        Args:
            request: FastAPI request object

        Returns:
            HTTPAuthorizationCredentials if token found, None otherwise
        """
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            return HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=auth_header[7:],
            )

        cookie_token = request.cookies.get(settings.COOKIE_ACCESS_TOKEN_NAME)
        if cookie_token:
            return HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=cookie_token,
            )

        return None


class OptionalBearerOrCookieAuth:
    """
    Optional version that doesn't raise 401 when no credentials present.

    Use for endpoints that work for both authenticated and anonymous users.
    """

    scheme_name: str = "OptionalBearerOrCookie"

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        """
        Extract credentials from request, returning None if not found.

        Args:
            request: FastAPI request object

        Returns:
            HTTPAuthorizationCredentials if token found, None otherwise
        """
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            return HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=auth_header[7:],
            )

        cookie_token = request.cookies.get(settings.COOKIE_ACCESS_TOKEN_NAME)
        if cookie_token:
            return HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=cookie_token,
            )

        return None