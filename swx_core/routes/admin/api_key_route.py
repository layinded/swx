from uuid import UUID
from fastapi import APIRouter, Depends, Query

from swx_core.auth.admin.dependencies import get_current_admin_user
from swx_core.controllers import api_key_controller
from swx_core.database.db import SessionDep
from swx_core.models.api_key_scope import ApiKeyPublicWithScopes, ApiKeyPublic
from swx_core.services.auth import api_key_service as svc

router = APIRouter(
    prefix="/admin/api-keys",
    tags=["admin-api-keys"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("/", response_model=list[ApiKeyPublic])
async def list_api_keys(
    session: SessionDep,
    user_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[ApiKeyPublic]:
    if user_id:
        return await svc.list_user_api_keys(session, user_id=user_id, skip=skip, limit=limit)
    return []


@router.get("/{key_id}", response_model=ApiKeyPublicWithScopes)
async def get_api_key_detail(session: SessionDep, key_id: UUID) -> ApiKeyPublicWithScopes:
    return await api_key_controller.get_api_key_detail_controller(session, key_id)


@router.post("/{key_id}/revoke")
async def revoke_api_key(session: SessionDep, key_id: UUID) -> dict[str, str]:
    from fastapi import HTTPException
    from swx_core.repositories import api_key_scope_repository as repo
    key = await repo.get_api_key_by_id(session, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    result = await api_key_controller.revoke_api_key_controller(session, key_id, key.user_id)
    return {"status": "revoked", "key_id": str(result.id)}


@router.get("/{key_id}/analytics")
async def get_usage_analytics(session: SessionDep, key_id: UUID) -> dict[str, object]:
    return await api_key_controller.get_usage_analytics_controller(session, key_id)