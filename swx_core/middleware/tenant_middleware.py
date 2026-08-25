"""
Tenant Context Middleware
------------------------
Middleware for extracting and setting tenant context from requests.
"""

from uuid import UUID
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from swx_core.config.settings import settings
from swx_core.core.tenant import (
    set_current_tenant,
    set_current_team,
    set_super_admin,
    clear_current_tenant,
)
from swx_core.middleware.logging_middleware import logger


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if self._is_exempt(request.url.path):
            return await call_next(request)
        
        try:
            self._set_context_from_request(request)
            return await call_next(request)
        finally:
            clear_current_tenant()
    
    def _is_exempt(self, path: str) -> bool:
        exempt_prefixes = {
            "/api/access/auth",
            "/api/access/oauth",
            "/api/utils/health",
            "/api/utils/language",
            "/docs",
            "/openapi.json",
            "/redoc",
        }
        return any(path.startswith(p) for p in exempt_prefixes)
    
    def _set_context_from_request(self, request: Request) -> None:
        header_tenant = request.headers.get("X-Tenant-ID")
        if header_tenant:
            try:
                set_current_tenant(UUID(header_tenant))
            except ValueError:
                # Bug #16: Log invalid UUID instead of silently ignoring
                logger.warning(f"Invalid X-Tenant-ID header value: {header_tenant}")
        
        header_team = request.headers.get("X-Team-ID")
        if header_team:
            try:
                set_current_team(UUID(header_team))
            except ValueError:
                # Bug #16: Log invalid UUID instead of silently ignoring
                logger.warning(f"Invalid X-Team-ID header value: {header_team}")
        
        user = getattr(request.state, "user", None)
        if user:
            if hasattr(user, "tenant_id") and user.tenant_id:
                set_current_tenant(user.tenant_id)
            if hasattr(user, "current_team_id") and user.current_team_id:
                set_current_team(user.current_team_id)
            if hasattr(user, "is_superuser") and user.is_superuser:
                set_super_admin(True)


def apply_middleware(app: FastAPI) -> None:
    if not getattr(settings, "ORGANIZATION_ENABLED", True):
        return
    app.add_middleware(TenantContextMiddleware)
    logger.info("TenantContextMiddleware registered")