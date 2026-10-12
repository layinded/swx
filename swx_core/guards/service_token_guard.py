"""Service Token Guard
--------------------
FastAPI dependency that validates the ``X-Service-Token`` header against
the ``SWX_SERVICE_TOKEN`` setting.

Returns a ``ServicePrincipal`` on success, raises 401 otherwise.

Typical use: internal service-to-service calls that bypass user auth but
still need identity tracking for audit.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status

from swx_core.config.settings import settings
from swx_core.guards.base import AuthenticatedUser


@dataclass(frozen=True)
class ServicePrincipal:
    """Identity returned by the service-token guard.

    ``service_name`` comes from the optional ``X-Service-Name`` header
    (defaults to ``"service"`` when absent).  ``scopes`` are configurable
    via the ``SWX_SERVICE_TOKEN_SCOPES`` setting (comma-separated).
    """

    service_name: str
    scopes: list[str] = field(default_factory=list)

    def to_authenticated_user(self) -> AuthenticatedUser:
        """Convert to the unified ``AuthenticatedUser`` for downstream guards."""
        return AuthenticatedUser(
            id=f"svc:{self.service_name}",
            email=f"{self.service_name}@service.internal",
            type="service",
            roles=["service"],
            permissions=self.scopes,
            is_superuser=False,
            is_active=True,
            metadata={"service_name": self.service_name},
        )


async def _get_service_principal(request: Request) -> ServicePrincipal:
    """FastAPI dependency: validate ``X-Service-Token`` and return ``ServicePrincipal``.

    Raises:
        HTTPException(401): If the header is missing or the token does not match.
    """
    token = request.headers.get("X-Service-Token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Service-Token header",
        )

    expected = settings.SWX_SERVICE_TOKEN
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service token authentication is not configured",
        )

    if not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
        )

    service_name = request.headers.get("X-Service-Name", "service")
    scopes = [s.strip() for s in settings.SWX_SERVICE_TOKEN_SCOPES.split(",") if s.strip()] if settings.SWX_SERVICE_TOKEN_SCOPES else []

    return ServicePrincipal(service_name=service_name, scopes=scopes)


ServiceTokenDep = Annotated[ServicePrincipal, Depends(_get_service_principal)]
"""Inject the authenticated service principal into route handlers.

Usage::

    @router.post("/internal/sync")
    async def sync_endpoint(svc: ServiceTokenDep):
        ...
"""