from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.repositories import consent_repository
from swx_core.services import consent_service


async def enforce_consent(session: AsyncSession, user_id: UUID, consent_type_key: str) -> None:
    await consent_service.require_consent(session, user_id, consent_type_key)


async def enforce_required_consents(session: AsyncSession, user_id: UUID) -> None:
    consent_types = await consent_repository.get_all_consent_types(session, active_only=True)
    for consent_type in consent_types:
        if consent_type.is_required and not await consent_service.has_consent_cached(session, user_id, consent_type.key):
            raise HTTPException(status_code=403, detail=f"Consent '{consent_type.key}' is required")
