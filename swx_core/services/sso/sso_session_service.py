# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

from uuid import UUID
from swx_core.utils.time import utc_now

from sqlalchemy.ext.asyncio import AsyncSession

from ...events.dispatcher import event_bus
from ...models.sso_session import SSOSession, SSOSessionCreate, SSOSessionPublic, SSOSessionUpdate
from ...repositories import sso_repository
from .sso_cache import get_cached_provider

def _to_public(sso_session: SSOSession) -> SSOSessionPublic:
    return SSOSessionPublic.model_validate(sso_session)

async def _get_session_or_raise(session: AsyncSession, sso_session_id: UUID, user_id: UUID | None = None) -> SSOSession:
    sso_session = await sso_repository.get_session_by_id(session, sso_session_id)
    if sso_session is None:
        raise ValueError("SSO session not found")
    if user_id is not None and sso_session.user_id != user_id:
        raise PermissionError("SSO session access denied")
    return sso_session

async def initiate_sso(session: AsyncSession, user_id: UUID, provider_id: UUID, metadata: dict[str, object] | None = None) -> dict[str, object]:
    provider = await get_cached_provider(session, provider_id)
    if provider is None or not provider.enabled:
        raise ValueError("SSO provider not found")
    active_session = await sso_repository.get_active_session_by_user(session, user_id, provider_id)
    if active_session is None:
        active_session = await sso_repository.create_session(session, SSOSessionCreate(user_id=user_id, provider_id=provider_id, metadata_=metadata or {}).model_dump())
    _ = await event_bus.dispatch("sso.session_initiated", payload={"session_id": str(active_session.id), "user_id": str(user_id), "provider_id": str(provider_id)})
    return {
        "session_id": str(active_session.id),
        "provider_id": str(provider.id),
        "provider_type": provider.provider_type,
        "authorization_url": provider.authorization_url,
        "issuer_url": provider.issuer_url,
        "sso_url": provider.sso_url,
        "scopes": provider.scopes or [],
        "domain": provider.domain,
        "metadata": provider.metadata_ or {},
    }

async def complete_sso_login(session: AsyncSession, sso_session_id: UUID, body: SSOSessionUpdate, user_id: UUID | None = None) -> SSOSessionPublic:
    await _get_session_or_raise(session, sso_session_id, user_id)
    sso_session = await sso_repository.update_session(session, sso_session_id, body.model_dump(exclude_unset=True))
    if sso_session is None:
        raise ValueError("SSO session not found")
    _ = await event_bus.dispatch("sso.session_completed", payload={"session_id": str(sso_session.id), "user_id": str(sso_session.user_id), "provider_id": str(sso_session.provider_id)})
    return _to_public(sso_session)

async def terminate_session(session: AsyncSession, sso_session_id: UUID, user_id: UUID | None = None) -> SSOSessionPublic:
    await _get_session_or_raise(session, sso_session_id, user_id)
    sso_session = await sso_repository.terminate_session(session, sso_session_id)
    if sso_session is None:
        raise ValueError("SSO session not found")
    _ = await event_bus.dispatch("sso.session_terminated", payload={"session_id": str(sso_session.id), "user_id": str(sso_session.user_id), "provider_id": str(sso_session.provider_id)})
    return _to_public(sso_session)

async def get_active_sessions(session: AsyncSession, user_id: UUID | None = None, skip: int = 0, limit: int = 100) -> list[SSOSessionPublic]:
    sessions = await sso_repository.list_sessions(session, user_id=user_id, skip=skip, limit=limit)
    return [_to_public(sso_session) for sso_session in sessions]

async def cleanup_expired_sessions(session: AsyncSession) -> list[SSOSessionPublic]:
    expired_sessions: list[SSOSessionPublic] = []
    for sso_session in await sso_repository.list_sessions(session, status="active", limit=500):
        if sso_session.expires_at is None or sso_session.expires_at > utc_now():
            continue
        expired = await sso_repository.update_session(session, sso_session.id, {"status": "expired"})
        if expired is not None:
            expired_sessions.append(_to_public(expired))
    return expired_sessions
