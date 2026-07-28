import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import API_KEY_DEFAULT_EXPIRY_DAYS, API_KEY_ROTATION_GRACE_HOURS
from swx_core.events.dispatcher import event_bus
from swx_core.models.api_key_scope import (
    ApiKeyCreate, ApiKeyPublic, ApiKeyPublicWithScopes, ApiKeyScopePublic, ApiKeyCreatedResponse,
)
from swx_core.repositories import api_key_scope_repository as repo


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_api_key(
    session: AsyncSession, user_id: UUID, data: ApiKeyCreate
) -> ApiKeyCreatedResponse:
    raw_key = secrets.token_urlsafe(32)
    key_prefix = raw_key[:8]
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    expires_at = data.expires_at
    if expires_at is None:
        expires_at = _utc_now() + timedelta(days=API_KEY_DEFAULT_EXPIRY_DAYS)

    key = await repo.create_api_key(session, {
        "name": data.name,
        "key_prefix": key_prefix,
        "hashed_key": hashed_key,
        "user_id": user_id,
        "is_active": True,
        "expires_at": expires_at,
        "rate_limit_override": data.rate_limit_override,
        "metadata_": {},
    })

    scopes: list[ApiKeyScopePublic] = []
    if data.scopes:
        created = await repo.add_scopes(session, key.id, data.scopes)
        scopes = [ApiKeyScopePublic.model_validate(s) for s in created]

    await event_bus.dispatch("api_key.created", payload={
        "key_id": str(key.id), "user_id": str(user_id), "name": data.name, "key_prefix": key_prefix,
    })

    return ApiKeyCreatedResponse(
        id=key.id, name=key.name, key_prefix=key_prefix, raw_key=raw_key,
        scopes=scopes, expires_at=key.expires_at, created_at=key.created_at,
    )


async def rotate_api_key(session: AsyncSession, key_id: UUID, user_id: UUID) -> ApiKeyCreatedResponse:
    old_key = await repo.get_api_key_by_id(session, key_id)
    if old_key is None or old_key.user_id != user_id:
        raise HTTPException(status_code=404, detail="API key not found")

    old_key.is_active = False
    old_key.expires_at = _utc_now() + timedelta(hours=API_KEY_ROTATION_GRACE_HOURS)
    session.add(old_key)
    await session.commit()

    scopes = await repo.get_scopes_for_key(session, old_key.id)
    scope_dicts = [{"resource": s.resource, "action": s.action} for s in scopes]

    new_response = await create_api_key(session, user_id, ApiKeyCreate(
        name=old_key.name, scopes=scope_dicts,
        expires_at=None, rate_limit_override=old_key.rate_limit_override,
    ))

    await event_bus.dispatch("api_key.rotated", payload={
        "old_key_id": str(key_id), "new_key_id": str(new_response.id), "user_id": str(user_id),
    })
    return new_response


async def revoke_api_key(session: AsyncSession, key_id: UUID, user_id: UUID) -> ApiKeyPublic:
    key = await repo.get_api_key_by_id(session, key_id)
    if key is None or key.user_id != user_id:
        raise HTTPException(status_code=404, detail="API key not found")
    deactivated = await repo.deactivate_api_key(session, key_id)
    if deactivated is None:
        raise HTTPException(status_code=404, detail="API key not found")
    await event_bus.dispatch("api_key.revoked", payload={"key_id": str(key_id), "user_id": str(user_id)})
    return ApiKeyPublic.model_validate(deactivated)


async def validate_api_key(session: AsyncSession, raw_key: str) -> Optional[ApiKeyPublic]:
    hashed = hashlib.sha256(raw_key.encode()).hexdigest()
    key = await repo.get_api_key_by_hash(session, hashed)
    if key is None or not key.is_active:
        return None
    if key.expires_at and key.expires_at < _utc_now():
        return None
    await repo.update_last_used(session, key.id)
    return ApiKeyPublic.model_validate(key)


async def list_user_api_keys(session: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 100) -> list[ApiKeyPublic]:
    keys = await repo.list_api_keys(session, user_id=user_id, is_active=None, skip=skip, limit=limit)
    return [ApiKeyPublic.model_validate(k) for k in keys]


async def get_api_key_detail(session: AsyncSession, key_id: UUID) -> ApiKeyPublicWithScopes:
    key = await repo.get_api_key_by_id(session, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    scopes = await repo.get_scopes_for_key(session, key_id)
    public = ApiKeyPublicWithScopes.model_validate(key)
    public.scopes = [ApiKeyScopePublic.model_validate(s) for s in scopes]
    return public


async def update_scopes(
    session: AsyncSession, key_id: UUID, add: list[dict[str, str]], remove: list[UUID]
) -> ApiKeyPublicWithScopes:
    key = await repo.get_api_key_by_id(session, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    if add:
        await repo.add_scopes(session, key_id, add)
    if remove:
        await repo.remove_scopes(session, key_id, remove)
    await event_bus.dispatch("api_key.scope_changed", payload={"key_id": str(key_id)})
    return await get_api_key_detail(session, key_id)


async def get_usage_analytics(session: AsyncSession, key_id: UUID) -> dict[str, Any]:
    key = await repo.get_api_key_by_id(session, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    scopes = await repo.get_scopes_for_key(session, key_id)
    return {
        "key_id": str(key.id),
        "name": key.name,
        "is_active": key.is_active,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "rate_limit_override": key.rate_limit_override,
        "scope_count": len(scopes),
        "scopes": [{"resource": s.resource, "action": s.action} for s in scopes],
    }