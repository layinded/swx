# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tenant Context Middleware — pure ASGI, SSE-safe.

Extracts X-Tenant-ID / X-Team-ID headers and sets context variables for
the request lifecycle.  Clears context in a finally block to prevent leakage.

Replaces the previous BaseHTTPMiddleware implementation which buffered
response bodies and broke Server-Sent Events streaming.
"""

from uuid import UUID

from starlette.types import ASGIApp, Receive, Scope, Send

from swx_core.config.settings import settings
from swx_core.core.tenant import (
    set_current_tenant,
    set_current_team,
    set_super_admin,
    clear_current_tenant,
)
from swx_core.middleware.logging_middleware import logger


def _extract_header(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    """Extract a header value by lowercase name match."""
    for k, v in headers:
        if k.lower() == name:
            return v.decode("latin-1")
    return None


_EXEMPT_PREFIXES = (
    "/api/access/auth",
    "/api/access/oauth",
    "/api/utils/health",
    "/api/utils/language",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class TenantContextMiddleware:
    """Pure-ASGI tenant context middleware — SSE-safe.

    Sets tenant/team/super-admin context variables from request headers
    before forwarding to the app, then clears them in a finally block.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        if any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES):
            await self.app(scope, receive, send)
            return

        self._set_context_from_scope(scope)
        try:
            await self.app(scope, receive, send)
        finally:
            clear_current_tenant()

    def _set_context_from_scope(self, scope: Scope) -> None:
        """Extract tenant/team/super-admin from headers and scope state."""
        headers: list[tuple[bytes, bytes]] = scope.get("headers", [])

        header_tenant = _extract_header(headers, b"x-tenant-id")
        if header_tenant:
            try:
                set_current_tenant(UUID(header_tenant))
            except ValueError:
                logger.warning(f"Invalid X-Tenant-ID header value: {header_tenant}")

        header_team = _extract_header(headers, b"x-team-id")
        if header_team:
            try:
                set_current_team(UUID(header_team))
            except ValueError:
                logger.warning(f"Invalid X-Team-ID header value: {header_team}")

        state = scope.get("state")
        user = getattr(state, "user", None) if state is not None and not isinstance(state, dict) else (state.get("user") if isinstance(state, dict) else None)
        if user:
            if hasattr(user, "tenant_id") and user.tenant_id:
                set_current_tenant(user.tenant_id)
            if hasattr(user, "current_team_id") and user.current_team_id:
                set_current_team(user.current_team_id)
            if hasattr(user, "is_superuser") and user.is_superuser:
                set_super_admin(True)


def apply_middleware(app: ASGIApp) -> None:
    """Apply TenantContextMiddleware to a FastAPI application."""
    if not getattr(settings, "ORGANIZATION_ENABLED", True):
        return
    from fastapi import FastAPI
    if isinstance(app, FastAPI):
        app.add_middleware(TenantContextMiddleware)
    logger.info("TenantContextMiddleware registered")