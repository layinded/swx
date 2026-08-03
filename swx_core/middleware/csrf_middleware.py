# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

"""
CSRF Protection Middleware with Cookie Lifecycle
-------------------------------------------------
Protects against Cross-Site Request Forgery attacks for cookie-based authentication.

Security:
- Double Submit Cookie pattern
- CSRF token validation for state-changing requests
- Compatible with SameSite cookies
- Auto-sets CSRF cookie on login/refresh paths
- Auto-deletes CSRF cookie on logout paths
- Skips validation when Bearer or API-key auth is present
- Lazy-sets CSRF cookie if auth cookies exist but CSRF cookie is missing
"""

import secrets
from dataclasses import dataclass, field

from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import Response

from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger


@dataclass
class CSRFConfig:
    cookie_name: str = "csrf_token"
    header_name: str = "X-CSRF-Token"
    cookie_max_age: int = 86400
    login_paths: list[str] = field(default_factory=lambda: ["/api/auth/login", "/api/auth/social/login"])
    logout_paths: list[str] = field(default_factory=lambda: ["/api/auth/logout"])
    refresh_paths: list[str] = field(default_factory=lambda: ["/api/auth/refresh"])
    exempt_paths: set[str] = field(default_factory=lambda: {"/docs", "/openapi.json", "/redoc", "/"})
    exempt_prefixes: list[str] = field(default_factory=lambda: ["/api/utils/health", "/api/utils/language"])
    protected_methods: set[str] = field(default_factory=lambda: {"POST", "PUT", "PATCH", "DELETE"})


class CSRFMiddleware:
    """Pure ASGI CSRF middleware with cookie lifecycle management.

    Unlike BaseHTTPMiddleware, this streams responses through without buffering,
    preserving SSE compatibility. Adds automatic CSRF cookie lifecycle:
    - Sets CSRF cookie on login/refresh-token paths
    - Deletes CSRF cookie on logout
    - Skips validation when Bearer or API-key auth is present
    - Lazy-sets CSRF cookie if auth cookies exist but CSRF cookie is missing
    """

    def __init__(self, app: ASGIApp, config: CSRFConfig | None = None) -> None:
        self.app: ASGIApp = app
        self.config: CSRFConfig = config or CSRFConfig()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        method = scope.get("method", "GET")
        headers_raw: list[tuple[bytes, bytes]] = scope.get("headers", [])
        headers = {k.lower(): v for k, v in headers_raw}
        # Preserve multiple Cookie headers by joining them (RFC 6265 allows multiple)
        cookie_parts = [v.decode("latin-1") for k, v in headers_raw if k.lower() == b"cookie"]
        combined_cookie = "; ".join(cookie_parts) if cookie_parts else ""

        has_bearer = b"authorization" in headers and headers[b"authorization"].lower().startswith(b"bearer ")
        has_api_key = b"x-api-key" in headers
        skip_validation = has_bearer or has_api_key

        is_login = _matches_path(path, self.config.login_paths)
        is_logout = _matches_path(path, self.config.logout_paths)
        is_refresh = _matches_path(path, self.config.refresh_paths)
        needs_cookie_set = is_login or is_refresh or _has_auth_cookie_no_csrf(combined_cookie, self.config)

        original_send = send
        cookie_action = None
        if is_logout:
            cookie_action = "delete"
        elif needs_cookie_set:
            cookie_action = "set"

        injected = False

        async def send_with_csrf(message: Message) -> None:
            nonlocal injected
            if message["type"] == "http.response.start" and not injected:
                new_headers = list(message.get("headers", []))
                if cookie_action == "delete":
                    new_headers = _add_delete_cookie(new_headers, self.config)
                elif cookie_action == "set":
                    token = _get_or_create_csrf_token(combined_cookie, self.config)
                    new_headers = _add_set_cookie(new_headers, token, self.config)
                message = {**message, "headers": new_headers}
                injected = True
            await original_send(message)

        if skip_validation or method not in self.config.protected_methods:
            await self.app(scope, receive, send_with_csrf)
            return

        if _is_exempt(path, self.config):
            await self.app(scope, receive, send_with_csrf)
            return

        cookie_token = _get_cookie_value(combined_cookie, self.config.cookie_name)
        header_token = headers.get(self.config.header_name.lower().encode(), b"").decode()

        if not cookie_token or not header_token:
            logger.warning(
                "CSRF token missing: path=%s, method=%s, cookie=%s, header=%s",
                path, method, bool(cookie_token), bool(header_token),
            )
            await _send_forbidden(scope, receive, original_send, "CSRF token validation failed")
            return

        if not secrets.compare_digest(cookie_token, header_token):
            logger.warning("CSRF token mismatch: path=%s, method=%s", path, method)
            await _send_forbidden(scope, receive, original_send, "CSRF token validation failed")
            return

        await self.app(scope, receive, send_with_csrf)


def _matches_path(path: str, patterns: list[str]) -> bool:
    return any(path == p or path.startswith(p + "/") for p in patterns)


def _is_exempt(path: str, config: CSRFConfig) -> bool:
    if path in config.exempt_paths:
        return True
    return any(path.startswith(prefix) for prefix in config.exempt_prefixes)


def _has_auth_cookie_no_csrf(cookie_header: str, config: CSRFConfig) -> bool:
    has_access = f"{settings.COOKIE_ACCESS_TOKEN_NAME}=" in cookie_header
    has_csrf = f"{config.cookie_name}=" in cookie_header
    return has_access and not has_csrf


def _get_cookie_value(cookie_header: str, name: str) -> str | None:
    prefix = f"{name}="
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(prefix):
            return part[len(prefix):]
    return None


def _get_or_create_csrf_token(combined_cookie: str, config: CSRFConfig) -> str:
    existing = _get_cookie_value(combined_cookie, config.cookie_name)
    return existing if existing else secrets.token_urlsafe(config.cookie_max_age // 8)


def _add_set_cookie(headers: list[tuple[bytes, bytes]], token: str, config: CSRFConfig) -> list[tuple[bytes, bytes]]:
    secure = settings.COOKIE_SECURE and settings.ENVIRONMENT != "local"
    parts = [
        f"{config.cookie_name}={token}",
        f"Max-Age={config.cookie_max_age}",
        f"Path=/",
        f"SameSite={settings.COOKIE_SAMESITE}",
    ]
    if secure:
        parts.append("Secure")
    if settings.COOKIE_DOMAIN:
        parts.append(f"Domain={settings.COOKIE_DOMAIN}")
    cookie_value = "; ".join(parts)
    return headers + [(b"set-cookie", cookie_value.encode())]


def _add_delete_cookie(headers: list[tuple[bytes, bytes]], config: CSRFConfig) -> list[tuple[bytes, bytes]]:
    cookie_value = f"{config.cookie_name}=; Max-Age=0; Path=/; SameSite={settings.COOKIE_SAMESITE}"
    return headers + [(b"set-cookie", cookie_value.encode())]


async def _send_forbidden(_scope: Scope, _receive: Receive, send: Send, detail: str) -> None:
    body = f'{{"detail":"{detail}"}}'.encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    await send({"type": "http.response.start", "status": 403, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def generate_csrf_token() -> str:
    """Generate a secure CSRF token."""
    return secrets.token_urlsafe(settings.CSRF_TOKEN_LENGTH)


async def get_csrf_token(request: Request, cookie_name: str = settings.CSRF_COOKIE_NAME) -> str:
    """Get or create CSRF token for the current session."""
    existing_token = request.cookies.get(cookie_name)
    return existing_token if existing_token else generate_csrf_token()


async def set_csrf_cookie(response: Response, token: str, cookie_name: str = settings.CSRF_COOKIE_NAME) -> None:
    """Set CSRF token in response cookie."""
    response.set_cookie(
        key=cookie_name,
        value=token,
        httponly=False,
        secure=settings.COOKIE_SECURE and settings.ENVIRONMENT != "local",
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.CSRF_COOKIE_MAX_AGE,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


def apply_middleware(app: ASGIApp) -> None:
    """Apply CSRF middleware to FastAPI app."""
    from fastapi import FastAPI

    config = CSRFConfig(
        cookie_name=settings.CSRF_COOKIE_NAME,
        header_name=settings.CSRF_HEADER_NAME,
        cookie_max_age=settings.CSRF_COOKIE_MAX_AGE,
        login_paths=list(settings.CSRF_LOGIN_PATHS) if hasattr(settings, "CSRF_LOGIN_PATHS") else ["/api/auth/login", "/api/auth/social/login"],
        logout_paths=list(settings.CSRF_LOGOUT_PATHS) if hasattr(settings, "CSRF_LOGOUT_PATHS") else ["/api/auth/logout"],
        refresh_paths=list(settings.CSRF_REFRESH_PATHS) if hasattr(settings, "CSRF_REFRESH_PATHS") else ["/api/auth/refresh"],
    )

    if settings.CSRF_ENABLED:
        if isinstance(app, FastAPI):
            app.add_middleware(CSRFMiddleware, config=config)
        logger.info("CSRF middleware applied (pure ASGI)")
    else:
        logger.info("CSRF middleware disabled for environment: %s", settings.ENVIRONMENT)