from uuid import UUID
from fastapi import APIRouter, Depends, Query

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers import api_key_controller
from swx_core.database.db import SessionDep
from swx_core.models.api_key_scope import ApiKeyCreate, ApiKeyPublic, ApiKeyPublicWithScopes, ApiKeyCreatedResponse

router = APIRouter(prefix="/user/api-keys", tags=["user-api-keys"])


@router.get("/", response_model=list[ApiKeyPublic])
async def list_own_api_keys(
    session: SessionDep,
    current_user: UserDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[ApiKeyPublic]:
    return await api_key_controller.list_api_keys_controller(session, current_user.id, skip, limit)


@router.post("/", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(session: SessionDep, body: ApiKeyCreate, current_user: UserDep) -> ApiKeyCreatedResponse:
    return await api_key_controller.create_api_key_controller(session, current_user.id, body)


@router.get("/{key_id}", response_model=ApiKeyPublicWithScopes)
async def get_api_key_detail(session: SessionDep, key_id: UUID, current_user: UserDep) -> ApiKeyPublicWithScopes:
    return await api_key_controller.get_api_key_detail_controller(session, key_id)


@router.post("/{key_id}/rotate", response_model=ApiKeyCreatedResponse)
async def rotate_api_key(session: SessionDep, key_id: UUID, current_user: UserDep) -> ApiKeyCreatedResponse:
    return await api_key_controller.rotate_api_key_controller(session, key_id, current_user.id)


@router.delete("/{key_id}")
async def revoke_api_key(session: SessionDep, key_id: UUID, current_user: UserDep) -> dict[str, str]:
    result = await api_key_controller.revoke_api_key_controller(session, key_id, current_user.id)
    return {"status": "revoked", "key_id": str(result.id)}


@router.put("/{key_id}/scopes", response_model=ApiKeyPublicWithScopes)
async def update_scopes(session: SessionDep, key_id: UUID, add: list[dict[str, str]] | None = None, remove: list[UUID] | None = None) -> ApiKeyPublicWithScopes:
    return await api_key_controller.update_scopes_controller(session, key_id, add or [], remove or [])