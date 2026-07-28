from uuid import UUID
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.api_key_scope import ApiKeyCreate, ApiKeyPublic, ApiKeyPublicWithScopes, ApiKeyCreatedResponse
from swx_core.services.auth import api_key_service


async def create_api_key_controller(session: AsyncSession, user_id: UUID, body: ApiKeyCreate) -> ApiKeyCreatedResponse:
    return await api_key_service.create_api_key(session, user_id, body)


async def rotate_api_key_controller(session: AsyncSession, key_id: UUID, user_id: UUID) -> ApiKeyCreatedResponse:
    return await api_key_service.rotate_api_key(session, key_id, user_id)


async def revoke_api_key_controller(session: AsyncSession, key_id: UUID, user_id: UUID) -> ApiKeyPublic:
    return await api_key_service.revoke_api_key(session, key_id, user_id)


async def list_api_keys_controller(session: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 100) -> list[ApiKeyPublic]:
    return await api_key_service.list_user_api_keys(session, user_id, skip, limit)


async def get_api_key_detail_controller(session: AsyncSession, key_id: UUID) -> ApiKeyPublicWithScopes:
    return await api_key_service.get_api_key_detail(session, key_id)


async def update_scopes_controller(
    session: AsyncSession, key_id: UUID, add: list[dict[str, str]], remove: list[UUID]
) -> ApiKeyPublicWithScopes:
    return await api_key_service.update_scopes(session, key_id, add, remove)


async def get_usage_analytics_controller(session: AsyncSession, key_id: UUID) -> dict[str, object]:
    return await api_key_service.get_usage_analytics(session, key_id)