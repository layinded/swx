# pyright: reportMissingImports=false

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.sso_provider import SSOProviderCreate, SSOProviderPublic, SSOProviderUpdate
from ..models.sso_session import SSOSessionPublic
from ..services.sso import sso_provider_service, sso_session_service


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


async def create_provider_controller(session: AsyncSession, body: SSOProviderCreate) -> SSOProviderPublic:
    return await sso_provider_service.create_provider(session, body)


async def get_provider_controller(session: AsyncSession, provider_id: UUID, *, enabled_only: bool = False) -> SSOProviderPublic:
    try:
        return await sso_provider_service.get_provider(session, provider_id, enabled_only=enabled_only)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_providers_controller(session: AsyncSession, *, enabled_only: bool = False, skip: int = 0, limit: int = 100) -> list[SSOProviderPublic]:
    return await sso_provider_service.list_providers(session, enabled_only=enabled_only, skip=skip, limit=limit)


async def update_provider_controller(session: AsyncSession, provider_id: UUID, body: SSOProviderUpdate) -> SSOProviderPublic:
    try:
        return await sso_provider_service.update_provider(session, provider_id, body)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def delete_provider_controller(session: AsyncSession, provider_id: UUID) -> dict[str, bool]:
    try:
        return await sso_provider_service.delete_provider(session, provider_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def initiate_sso_controller(session: AsyncSession, user_id: UUID, provider_id: UUID, metadata: dict[str, object] | None = None) -> dict[str, object]:
    try:
        return await sso_session_service.initiate_sso(session, user_id, provider_id, metadata)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_sessions_controller(session: AsyncSession, user_id: UUID | None = None, skip: int = 0, limit: int = 100) -> list[SSOSessionPublic]:
    return await sso_session_service.get_active_sessions(session, user_id=user_id, skip=skip, limit=limit)


async def terminate_session_controller(session: AsyncSession, sso_session_id: UUID, user_id: UUID | None = None) -> SSOSessionPublic:
    try:
        return await sso_session_service.terminate_session(session, sso_session_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
