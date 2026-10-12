from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.consent import (
    ConsentSummary,
    ConsentTypeCreate,
    ConsentTypePublic,
    ConsentVersionCreate,
    ConsentVersionPublic,
    UserConsentCreate,
    UserConsentPublic,
)
from swx_core.services import consent_service


async def grant_consent_controller(session: AsyncSession, user_id: UUID, data: UserConsentCreate, ip: str | None = None, user_agent: str | None = None) -> UserConsentPublic:
    return UserConsentPublic.model_validate(await consent_service.grant_consent(session, user_id, data.consent_type_key, data.version, ip, user_agent, data.source))


async def withdraw_consent_controller(session: AsyncSession, user_id: UUID, consent_type_key: str, ip: str | None = None, user_agent: str | None = None) -> UserConsentPublic:
    return UserConsentPublic.model_validate(await consent_service.withdraw_consent(session, user_id, consent_type_key, ip, user_agent))


async def get_consent_summary_controller(session: AsyncSession, user_id: UUID) -> ConsentSummary:
    return await consent_service.get_user_consent_status(session, user_id)


async def list_consent_types_controller(session: AsyncSession, active_only: bool = True) -> list[ConsentTypePublic]:
    return await consent_service.get_consent_types(session, active_only=active_only)


async def get_user_consents_controller(session: AsyncSession, user_id: UUID) -> list[UserConsentPublic]:
    return await consent_service.get_user_consents(session, user_id)


async def create_consent_type_controller(session: AsyncSession, data: ConsentTypeCreate) -> ConsentTypePublic:
    return await consent_service.create_consent_type(session, data)


async def create_consent_version_controller(session: AsyncSession, data: ConsentVersionCreate) -> ConsentVersionPublic:
    return await consent_service.create_consent_version(session, data)
