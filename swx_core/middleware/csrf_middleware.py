"""
CSRF Protection Middleware
---------------------------
Protects against Cross-Site Request Forgery attacks for cookie-based authentication.

Security:
- Double Submit Cookie pattern
- CSRF token validation for state-changing requests
- Compatible with SameSite cookies
"""

import secrets
from typing import Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from swx_core.middleware.logging_middleware import logger


CSRF_TOKEN_LENGTH = 32
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_COOKIE_NAME = "csrf_token"


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware using Double Submit Cookie pattern.

    For cookie-based authentication (BFF pattern), this provides CSRF protection
    when SameSite=None is configured or for older browsers.

    How it works:
    1. Server generates CSRF token and sets it in httpOnly cookie
    2. Client reads token from cookie and includes it in request header
    3. Middleware validates cookie token matches header token

    Protected Methods:
    - POST, PUT, PATCH, DELETE (state-changing operations)

    Exempt Paths:
    - GET, HEAD, OPTIONS, TRACE (safe methods)
    - /docs, /openapi.json, /redoc (documentation)
    - /api/utils/health* (health checks)
    """

    # Methods that require CSRF protection
    PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    # Paths exempt from CSRF protection
    EXEMPT_PATHS = {
        "/docs",
        "/openapi.json",
        "/redoc",
        "/",
    }

    # Path prefixes exempt from CSRF protection
    EXEMPT_PREFIXES = [
        "/api/utils/health",
        "/api/utils/language",
    ]

    def __init__(
        self,
        app: ASGIApp,
        cookie_name: str = CSRF_COOKIE_NAME,
        header_name: str = CSRF_HEADER_NAME,
        exempt_paths: Optional[set[str]] = None,
        exempt_prefixes: Optional[list[str]] = None,
    ):
        """
        Initialize CSRF middleware.

        Args:
            app: ASGI application
            cookie_name: Name of CSRF cookie
            header_name: Name of CSRF header
            exempt_paths: Additional paths to exempt
            exempt_prefixes: Additional path prefixes to exempt
        """
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.exempt_paths = self.EXEMPT_PATHS | (exempt_paths or set())
        self.exempt_prefixes = self.EXEMPT_PREFIXES + (exempt_prefixes or [])

    async def dispatch(self, request: Request, call_next):
        """Process request with CSRF protection."""

        # Skip CSRF for safe methods
        if request.method not in self.PROTECTED_METHODS:
            return await call_next(request)

        # Skip CSRF for exempt paths
        if self._is_exempt(request.url.path):
            return await call_next(request)

        # Validate CSRF token
        if not await self._validate_csrf(request):
            logger.warning(
                f"CSRF validation failed: path={request.url.path}, "
                f"method={request.method}, "
                f"ip={request.client.host if request.client else 'unknown'}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed",
            )

        return await call_next(request)

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from CSRF protection."""
        # Exact path match
        if path in self.exempt_paths:
            return True

        # Prefix match
        for prefix in self.exempt_prefixes:
            if path.startswith(prefix):
                return True

        return False

    async def _validate_csrf(self, request: Request) -> bool:
        """
        Validate CSRF token using Double Submit Cookie pattern.

        Returns:
            True if valid, False otherwise
        """
        # Get token from cookie
        cookie_token = request.cookies.get(self.cookie_name)

        # Get token from header
        header_token = request.headers.get(self.header_name)

        # Both must be present
        if not cookie_token or not header_token:
            logger.debug(
                f"CSRF token missing: cookie={bool(cookie_token)}, header={bool(header_token)}"
            )
            return False

        # Tokens must match
        if not secrets.compare_digest(cookie_token, header_token):
            logger.debug("CSRF token mismatch")
            return False

        return True


def generate_csrf_token() -> str:
    """
    Generate a secure CSRF token.

    Returns:
        URL-safe CSRF token
    """
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


async def get_csrf_token(request: Request, cookie_name: str = CSRF_COOKIE_NAME) -> str:
    """
    Get or create CSRF token for the current session.

    If CSRF cookie exists, returns it.
    If not, generates a new token (caller should set cookie).

    Args:
        request: FastAPI request object
        cookie_name: Name of the CSRF cookie to read (defaults to module constant).

    Returns:
        CSRF token
    """
    # Check if token exists in cookie
    existing_token = request.cookies.get(cookie_name)

    if existing_token:
        return existing_token

    # Generate new token
    return generate_csrf_token()


async def set_csrf_cookie(
    response, token: str, cookie_name: str = CSRF_COOKIE_NAME
) -> None:
    """
    Set CSRF token in response cookie.

    Args:
        response: Response object
        token: CSRF token to set
        cookie_name: Name of the CSRF cookie to write (defaults to module constant).
    """
    from swx_core.config.settings import settings

    response.set_cookie(
        key=cookie_name,
        value=token,
        httponly=False,  # Must be readable by JavaScript
        secure=settings.COOKIE_SECURE and settings.ENVIRONMENT != "local",
        samesite=settings.COOKIE_SAMESITE,
        max_age=60 * 60 * 24,  # 24 hours
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


def apply_middleware(app) -> None:
    """
    Apply CSRF middleware to FastAPI app.

    This function is called by the dynamic middleware loader.
    """
    from swx_core.config.settings import settings

    # Only apply if CSRF protection is enabled
    # Default: enabled for production, disabled for local development
    csrf_enabled = settings.ENVIRONMENT not in ["local", "development", "dev"]

    if csrf_enabled:
        app.add_middleware(CSRFMiddleware)
        logger.info("CSRF middleware applied")
    else:
        logger.info(f"CSRF middleware disabled for environment: {settings.ENVIRONMENT}")