# pyright: reportUnknownMemberType=false

import time
from uuid import UUID
from swx_core.utils.time import utc_now, ensure_aware

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import EventBus
from swx_core.events import event_bus
from swx_core.models.consent import (
    ConsentStatus,
    ConsentSummary,
    ConsentTypeCreate,
    ConsentTypePublic,
    ConsentVersionCreate,
    ConsentVersionPublic,
    UserConsent,
    UserConsentPublic,
)
from swx_core.repositories import consent_repository

typed_event_bus: EventBus = event_bus

_consent_cache: dict[str, tuple[bool, float]] = {}
_CONSENT_TTL: float = 30.0

def clear_consent_cache() -> None:
    _consent_cache.clear()

async def has_consent_cached(session: AsyncSession, user_id: UUID, consent_type_key: str) -> bool:
    cache_key = f"{user_id}:{consent_type_key}"
    now = time.monotonic()
    cached = _consent_cache.get(cache_key)
    if cached is not None and now - cached[1] < _CONSENT_TTL:
        return cached[0]
    result = await has_consent(session, user_id, consent_type_key)
    _consent_cache[cache_key] = (result, now)
    return result

async def grant_consent(session: AsyncSession, user_id: UUID, consent_type_key: str, version: str, ip: str | None, user_agent: str | None, source: str | None) -> UserConsent:
    consent_type = await consent_repository.get_consent_type_by_key(session, consent_type_key)
    if not consent_type or not consent_type.is_active:
        raise HTTPException(status_code=404, detail="Consent type not found")
    consent = await consent_repository.create_user_consent(session, {
        "user_id": user_id,
        "consent_type_id": consent_type.id,
        "status": ConsentStatus.GRANTED.value,
        "version": version,
        "granted_at": utc_now(),
        "ip_address": ip,
        "user_agent": user_agent,
        "source": source,
    })
    await typed_event_bus.dispatch("consent.granted", payload={"user_id": str(user_id), "consent_type_key": consent_type_key, "consent_id": str(consent.id), "version": version})
    clear_consent_cache()
    return consent

async def withdraw_consent(session: AsyncSession, user_id: UUID, consent_type_key: str, ip: str | None, user_agent: str | None) -> UserConsent:
    consent_type = await consent_repository.get_consent_type_by_key(session, consent_type_key)
    if not consent_type:
        raise HTTPException(status_code=404, detail="Consent type not found")
    consent = await consent_repository.get_latest_user_consent(session, user_id, consent_type.id)
    if not consent:
        raise HTTPException(status_code=404, detail="Consent record not found")
    updated = await consent_repository.update_user_consent_status(
        session, consent.id, ConsentStatus.WITHDRAWN.value, withdrawn_at=utc_now(), ip_address=ip, user_agent=user_agent
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Consent record not found")
    await typed_event_bus.dispatch("consent.withdrawn", payload={"user_id": str(user_id), "consent_type_key": consent_type_key, "consent_id": str(updated.id), "version": updated.version})
    clear_consent_cache()
    return updated

async def get_user_consent_status(session: AsyncSession, user_id: UUID) -> ConsentSummary:
    return ConsentSummary(**await consent_repository.get_consent_summary(session, user_id))

async def get_user_consents(session: AsyncSession, user_id: UUID) -> list[UserConsentPublic]:
    consents = await consent_repository.get_user_consents(session, user_id)
    return [UserConsentPublic.model_validate(consent) for consent in consents]

async def has_consent(session: AsyncSession, user_id: UUID, consent_type_key: str) -> bool:
    consent_type = await consent_repository.get_consent_type_by_key(session, consent_type_key)
    if not consent_type:
        return False
    consent = await consent_repository.get_latest_user_consent(session, user_id, consent_type.id)
    if not consent:
        return False
    expires_at = ensure_aware(consent.expires_at)
    if expires_at is not None and expires_at <= utc_now():
        return False
    return consent.status == ConsentStatus.GRANTED.value

async def require_consent(session: AsyncSession, user_id: UUID, consent_type_key: str) -> UserConsent:
    consent_type = await consent_repository.get_consent_type_by_key(session, consent_type_key)
    if not consent_type:
        raise HTTPException(status_code=404, detail="Consent type not found")
    consent = await consent_repository.get_latest_user_consent(session, user_id, consent_type.id)
    if not consent or consent.status != ConsentStatus.GRANTED.value:
        raise HTTPException(status_code=403, detail=f"Consent '{consent_type_key}' is required")
    expires_at = ensure_aware(consent.expires_at)
    if expires_at is not None and expires_at <= utc_now():
        raise HTTPException(status_code=403, detail=f"Consent '{consent_type_key}' has expired")
    return consent

async def check_expired_consents(session: AsyncSession) -> int:
    count = 0
    now = utc_now()
    consents = await consent_repository.get_consents_by_status(session, ConsentStatus.GRANTED.value)
    for consent in consents:
        expires_at = ensure_aware(consent.expires_at)
        if expires_at is not None and expires_at <= now:
            updated = await consent_repository.update_user_consent_status(session, consent.id, ConsentStatus.EXPIRED.value)
            if updated:
                await typed_event_bus.dispatch("consent.expired", payload={"user_id": str(consent.user_id), "consent_id": str(consent.id), "consent_type_id": str(consent.consent_type_id), "version": consent.version})
                count += 1
    return count

async def get_consent_types(session: AsyncSession, active_only: bool = True) -> list[ConsentTypePublic]:
    consent_types = await consent_repository.get_all_consent_types(session, active_only=active_only)
    return [ConsentTypePublic.model_validate(consent_type) for consent_type in consent_types]

async def create_consent_type(session: AsyncSession, data: ConsentTypeCreate) -> ConsentTypePublic:
    existing = await consent_repository.get_consent_type_by_key(session, data.key)
    if existing:
        raise HTTPException(status_code=400, detail="Consent type key already exists")
    consent_type = await consent_repository.create_consent_type(session, {
        "key": data.key,
        "name": data.name,
        "description": data.description,
        "is_required": data.is_required,
        "is_active": data.is_active,
    })
    return ConsentTypePublic.model_validate(consent_type)

async def create_consent_version(session: AsyncSession, data: ConsentVersionCreate) -> ConsentVersionPublic:
    consent_type = await consent_repository.get_consent_type_by_id(session, data.consent_type_id)
    if not consent_type:
        raise HTTPException(status_code=404, detail="Consent type not found")
    version = await consent_repository.create_consent_version(session, {
        "consent_type_id": data.consent_type_id,
        "version": data.version,
        "document_url": data.document_url,
        "document_text": data.document_text,
        "is_active": data.is_active,
        "effective_date": data.effective_date,
    })
    return ConsentVersionPublic.model_validate(version)
