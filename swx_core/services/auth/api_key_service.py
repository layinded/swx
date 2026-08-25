import hashlib
import secrets
from datetime import timedelta
from typing import Any, Optional
from uuid import UUID
from swx_core.utils.time import utc_now, ensure_aware

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import API_KEY_DEFAULT_EXPIRY_DAYS, API_KEY_MAX_EXPIRY_DAYS, API_KEY_ROTATION_GRACE_HOURS
from swx_core.events.dispatcher import event_bus
from swx_core.services.audit_logger import AuditLogger, ActorType, AuditOutcome, AuditAction
from swx_core.models.api_key_scope import (
    ApiKeyCreate, ApiKeyPublic, ApiKeyPublicWithScopes, ApiKeyScopePublic, ApiKeyCreatedResponse,
)
from swx_core.repositories import api_key_scope_repository as repo
from swx_core.services.auth.api_key_scope_service import parse_scope_string

def _normalize_scopes(scopes: list[str] | list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for scope in scopes:
        if isinstance(scope, str):
            resource, action = parse_scope_string(scope)
            result.append({"resource": resource, "action": action})
        elif isinstance(scope, dict):
            result.append({"resource": scope["resource"], "action": scope["action"]})
        else:
            raise ValueError(f"Invalid scope type: {type(scope)}. Expected str or dict")
    return result

async def create_api_key(
    session: AsyncSession, user_id: UUID, data: ApiKeyCreate
) -> ApiKeyCreatedResponse:
    raw_key = secrets.token_urlsafe(32)
    key_prefix = raw_key[:8]
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    expires_at = data.expires_at
    if expires_at is None:
        expires_at = utc_now() + timedelta(days=API_KEY_DEFAULT_EXPIRY_DAYS)
    else:
        max_expiry = utc_now() + timedelta(days=API_KEY_MAX_EXPIRY_DAYS)
        expires_at = min(ensure_aware(expires_at), max_expiry)

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
        normalized = _normalize_scopes(data.scopes)
        created = await repo.add_scopes(session, key.id, normalized)
        scopes = [ApiKeyScopePublic.model_validate(s) for s in created]

    await event_bus.dispatch("api_key.created", payload={
        "key_id": str(key.id), "user_id": str(user_id), "name": data.name, "key_prefix": key_prefix,
    })

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.API_KEY_CREATED,
        actor_type=ActorType.USER,
        actor_id=str(user_id),
        resource_type="api_key",
        resource_id=str(key.id),
        outcome=AuditOutcome.SUCCESS,
        context={"name": data.name, "key_prefix": key_prefix},
    )

    return ApiKeyCreatedResponse(
        id=key.id, name=key.name, key_prefix=key_prefix, raw_key=raw_key,
        scopes=scopes, expires_at=key.expires_at, created_at=key.created_at,
    )

async def rotate_api_key(session: AsyncSession, key_id: UUID, user_id: UUID) -> ApiKeyCreatedResponse:
    old_key = await repo.get_api_key_by_id(session, key_id)
    if old_key is None or old_key.user_id != user_id:
        raise HTTPException(status_code=404, detail="API key not found")

    await repo.deactivate_and_extend_key(session, key_id, API_KEY_ROTATION_GRACE_HOURS)

    scopes = await repo.get_scopes_for_key(session, old_key.id)
    scope_dicts = [{"resource": s.resource, "action": s.action} for s in scopes]

    new_response = await create_api_key(session, user_id, ApiKeyCreate(
        name=old_key.name, scopes=scope_dicts,
        expires_at=None, rate_limit_override=old_key.rate_limit_override,
    ))

    await repo.set_rotated_from_id(session, new_response.id, old_key.id)

    await event_bus.dispatch("api_key.rotated", payload={
        "old_key_id": str(key_id), "new_key_id": str(new_response.id), "user_id": str(user_id),
    })

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.API_KEY_ROTATED,
        actor_type=ActorType.USER,
        actor_id=str(user_id),
        resource_type="api_key",
        resource_id=str(key_id),
        outcome=AuditOutcome.SUCCESS,
        context={"new_key_id": str(new_response.id)},
    )

    return new_response

async def revoke_api_key(session: AsyncSession, key_id: UUID, user_id: UUID) -> ApiKeyPublic:
    key = await repo.get_api_key_by_id(session, key_id)
    if key is None or key.user_id != user_id:
        raise HTTPException(status_code=404, detail="API key not found")
    deactivated = await repo.deactivate_api_key(session, key_id)
    if deactivated is None:
        raise HTTPException(status_code=404, detail="API key not found")
    await event_bus.dispatch("api_key.revoked", payload={"key_id": str(key_id), "user_id": str(user_id)})

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.API_KEY_REVOKED,
        actor_type=ActorType.USER,
        actor_id=str(user_id),
        resource_type="api_key",
        resource_id=str(key_id),
        outcome=AuditOutcome.SUCCESS,
    )

    return ApiKeyPublic.model_validate(deactivated)

async def validate_api_key(session: AsyncSession, raw_key: str) -> Optional[ApiKeyPublic]:
    hashed = hashlib.sha256(raw_key.encode()).hexdigest()
    key = await repo.get_api_key_by_hash(session, hashed)
    if key is None or not key.is_active:
        return None
    # SWX-009: normalize naive datetimes from PostgreSQL to avoid
    # TypeError when comparing with timezone-aware utc_now() (Python 3.12+)
    expires_at = ensure_aware(key.expires_at)
    if expires_at is not None and expires_at < utc_now():
        return None
    # SWX-007: build ApiKeyPublic from explicit attributes to avoid
    # MissingGreenlet from model_validate on a detached ORM object
    result = ApiKeyPublic(
        id=key.id,
        team_id=key.team_id,
        name=key.name,
        key_prefix=key.key_prefix,
        user_id=key.user_id,
        is_active=key.is_active,
        expires_at=expires_at,
        last_used_at=ensure_aware(key.last_used_at),
        rate_limit_override=key.rate_limit_override,
        rotated_from_id=key.rotated_from_id,
        is_expired=expires_at is not None and expires_at < utc_now(),
        created_at=key.created_at,
        updated_at=key.updated_at,
    )
    await repo.update_last_used(session, key.id)
    return result

async def list_user_api_keys(session: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 100) -> list[ApiKeyPublic]:
    keys = await repo.list_api_keys(session, user_id=user_id, is_active=None, skip=skip, limit=limit)
    now = utc_now()
    return [
        ApiKeyPublic(
            id=k.id,
            team_id=k.team_id,
            name=k.name,
            key_prefix=k.key_prefix,
            user_id=k.user_id,
            is_active=k.is_active,
            expires_at=ensure_aware(k.expires_at),
            last_used_at=ensure_aware(k.last_used_at),
            rate_limit_override=k.rate_limit_override,
            rotated_from_id=k.rotated_from_id,
            is_expired=k.expires_at is not None and ensure_aware(k.expires_at) < now,
            created_at=k.created_at,
            updated_at=k.updated_at,
        )
        for k in keys
    ]

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
