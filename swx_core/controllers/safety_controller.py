from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.content_filter import ContentFilterCreate, ContentFilterPublic, ContentFilterUpdate
from swx_core.models.safety_check import SafetyCheckPublic
from swx_core.services.safety import safety_check_service, safety_service


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


async def create_filter_controller(session: AsyncSession, body: ContentFilterCreate) -> ContentFilterPublic:
    try:
        return await safety_service.create_filter(session, body)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def get_filter_controller(session: AsyncSession, filter_id: UUID) -> ContentFilterPublic:
    try:
        return await safety_service.get_filter(session, filter_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_filters_controller(session: AsyncSession, enabled: bool | None = None, category: str | None = None, skip: int = 0, limit: int = 100) -> list[ContentFilterPublic]:
    try:
        return await safety_service.list_filters(session, enabled=enabled, category=category, skip=skip, limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def update_filter_controller(session: AsyncSession, filter_id: UUID, body: ContentFilterUpdate) -> ContentFilterPublic:
    try:
        return await safety_service.update_filter(session, filter_id, body)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def delete_filter_controller(session: AsyncSession, filter_id: UUID) -> ContentFilterPublic:
    try:
        return await safety_service.delete_filter(session, filter_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def run_safety_check_controller(session: AsyncSession, content: str, content_type: str, user_id: UUID, source: str, conversation_id: UUID | None = None) -> SafetyCheckPublic:
    try:
        return await safety_check_service.run_safety_check(session, content, content_type, user_id, source, conversation_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def get_check_controller(session: AsyncSession, check_id: UUID, user_id: UUID | None = None) -> SafetyCheckPublic:
    try:
        return await safety_check_service.get_check(session, check_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_checks_controller(session: AsyncSession, user_id: UUID | None = None, overall_verdict: str | None = None, skip: int = 0, limit: int = 100) -> list[SafetyCheckPublic]:
    try:
        return await safety_check_service.list_checks(session, user_id=user_id, overall_verdict=overall_verdict, skip=skip, limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
