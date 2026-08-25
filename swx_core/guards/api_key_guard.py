"""API Key Authentication Guard (SOC 2 CC6.1).

Authenticates requests via X-API-Key header or api_key query parameter.
Delegates all DB operations to the api_key_service layer, following
the SWX Controller → Service → Repository pattern.
"""

from typing import Optional, Dict, Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.guards.base import BaseGuard, AuthenticatedUser
from swx_core.middleware.logging_middleware import logger


class APIKeyGuard(BaseGuard):
    """API Key authentication guard.

    Delegates validation and last_used_at updates to api_key_service,
    following the SWX pattern (guard → service → repository).
    """

    def __init__(
        self,
        header_name: str = "X-API-Key",
        query_param: str = "api_key",
    ):
        self.header_name = header_name
        self.query_param = query_param

    @property
    def name(self) -> str:
        return "api_key"

    async def authenticate(self, request: Request) -> Optional[AuthenticatedUser]:
        """Authenticate via API key through the service layer."""
        raw_key = await self._extract_key(request)
        if not raw_key:
            return None

        session = self._get_session(request)
        if session is None:
            logger.warning("No DB session available for API key authentication")
            return None

        from swx_core.services.auth.api_key_service import validate_api_key

        key_public = await validate_api_key(session, raw_key)
        if key_public is None:
            logger.warning(
                "Invalid or expired API key from %s",
                request.client.host if request.client else "unknown",
            )
            return None

        return AuthenticatedUser(
            id=str(key_public.user_id),
            email="",
            type="api_key",
            roles=["api_user"],
            permissions=[],
            is_superuser=False,
            is_active=True,
            metadata={
                "key_id": str(key_public.id),
                "key_prefix": key_public.key_prefix,
                "key_name": key_public.name,
            },
        )

    async def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate API key by delegating to the service layer."""
        from swx_core.database.db import async_session
        from swx_core.services.auth.api_key_service import validate_api_key
        async with async_session() as session:
            key_public = await validate_api_key(session, token)
            if key_public is None:
                return {"valid": False, "key_prefix": token[:8] if token else ""}
            return {"valid": True, "key_prefix": key_public.key_prefix, "key_id": str(key_public.id)}

    async def _extract_key(self, request: Request) -> Optional[str]:
        """Extract API key from request header or query parameter."""
        key = request.headers.get(self.header_name)
        if key:
            return key

        key = request.query_params.get(self.query_param)
        if key:
            return key

        return None

    def _get_session(self, request: Request) -> Optional[AsyncSession]:
        """Extract DB session from request state."""
        return getattr(request.state, "db_session", None) or getattr(request.app.state, "db_session", None)

    def can_revoke(self) -> bool:
        """Check if revocation is supported."""
        return True