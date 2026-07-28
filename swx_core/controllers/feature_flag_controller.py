from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.feature_flag import FeatureFlagCreate, FeatureFlagPublic, FeatureFlagUpdate
from swx_core.models.flag_evaluation import FlagEvaluationPublic
from swx_core.services.feature_flag import feature_flag_service, feature_flag_evaluation_service


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


async def create_flag_controller(session: AsyncSession, data: FeatureFlagCreate) -> FeatureFlagPublic:
    return await feature_flag_service.create_flag(session, data)


async def get_flag_controller(session: AsyncSession, flag_id: UUID) -> FeatureFlagPublic:
    try:
        return await feature_flag_service.get_flag(session, flag_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_flags_controller(session: AsyncSession, enabled: bool | None = None, skip: int = 0, limit: int = 50) -> list[FeatureFlagPublic]:
    return await feature_flag_service.list_flags(session, enabled=enabled, skip=skip, limit=limit)


async def update_flag_controller(session: AsyncSession, flag_id: UUID, data: FeatureFlagUpdate) -> FeatureFlagPublic:
    try:
        return await feature_flag_service.update_flag(session, flag_id, data)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def delete_flag_controller(session: AsyncSession, flag_id: UUID) -> FeatureFlagPublic:
    try:
        return await feature_flag_service.delete_flag(session, flag_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def evaluate_flag_controller(session: AsyncSession, flag_key: str, user_id: UUID | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    return await feature_flag_evaluation_service.evaluate_flag(session, flag_key, user_id, context)


async def evaluate_flags_for_user_controller(session: AsyncSession, user_id: UUID | None = None, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return await feature_flag_evaluation_service.evaluate_flags_for_user(session, user_id, context)


async def get_flag_evaluations_controller(session: AsyncSession, flag_id: UUID, skip: int = 0, limit: int = 50) -> list[FlagEvaluationPublic]:
    return await feature_flag_evaluation_service.get_flag_evaluations(session, flag_id, skip=skip, limit=limit)