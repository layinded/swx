# pyright: reportAny=false, reportUnknownVariableType=false

from datetime import datetime, timezone
from typing import TypedDict
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import desc, func, select

from swx_core.models.consent import ConsentType, ConsentVersion, UserConsent


class ConsentTypeData(TypedDict):
    key: str
    name: str
    description: str | None
    is_required: bool
    is_active: bool


class UserConsentData(TypedDict, total=False):
    user_id: UUID
    consent_type_id: UUID
    status: str
    version: str
    granted_at: datetime | None
    withdrawn_at: datetime | None
    expires_at: datetime | None
    ip_address: str | None
    user_agent: str | None
    source: str | None
    notes: str | None


class ConsentVersionData(TypedDict):
    consent_type_id: UUID
    version: str
    document_url: str | None
    document_text: str | None
    is_active: bool
    effective_date: datetime


class ConsentSummaryData(TypedDict):
    user_id: UUID
    pending: int
    granted: int
    withdrawn: int
    expired: int
    total: int


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def get_consent_type_by_key(session: AsyncSession, key: str) -> ConsentType | None:
    stmt = select(ConsentType).where(ConsentType.key == key)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_consent_type_by_id(session: AsyncSession, consent_type_id: UUID) -> ConsentType | None:
    stmt = select(ConsentType).where(ConsentType.id == consent_type_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_all_consent_types(session: AsyncSession, active_only: bool = True) -> list[ConsentType]:
    stmt = select(ConsentType)
    if active_only:
        stmt = stmt.where(ConsentType.is_active)
    stmt = stmt.order_by(ConsentType.name)
    return list((await session.execute(stmt)).scalars().all())


async def create_consent_type(session: AsyncSession, data: ConsentTypeData) -> ConsentType:
    consent_type = ConsentType(**data)
    session.add(consent_type)
    await session.commit()
    await session.refresh(consent_type)
    return consent_type


async def get_user_consent(session: AsyncSession, user_id: UUID, consent_type_id: UUID) -> UserConsent | None:
    stmt = select(UserConsent).where(
        and_(
            UserConsent.user_id == user_id,  # pyright: ignore[reportArgumentType]
            UserConsent.consent_type_id == consent_type_id,  # pyright: ignore[reportArgumentType]
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_latest_user_consent(session: AsyncSession, user_id: UUID, consent_type_id: UUID) -> UserConsent | None:
    stmt = select(UserConsent).where(
        and_(
            UserConsent.user_id == user_id,  # pyright: ignore[reportArgumentType]
            UserConsent.consent_type_id == consent_type_id,  # pyright: ignore[reportArgumentType]
        )
    ).order_by(desc(UserConsent.updated_at))
    return (await session.execute(stmt)).scalars().first()


async def get_user_consents(session: AsyncSession, user_id: UUID) -> list[UserConsent]:
    stmt = select(UserConsent).where(UserConsent.user_id == user_id).order_by(desc(UserConsent.updated_at))
    return list((await session.execute(stmt)).scalars().all())


async def create_user_consent(session: AsyncSession, data: UserConsentData) -> UserConsent:
    consent = UserConsent(**data)
    session.add(consent)
    await session.commit()
    await session.refresh(consent)
    return consent


async def update_user_consent_status(
    session: AsyncSession,
    consent_id: UUID,
    status: str,
    granted_at: datetime | None = None,
    withdrawn_at: datetime | None = None,
    expires_at: datetime | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    notes: str | None = None,
) -> UserConsent | None:
    consent = await session.get(UserConsent, consent_id)
    if not consent:
        return None
    consent.status = status
    if granted_at is not None:
        consent.granted_at = granted_at
    if withdrawn_at is not None:
        consent.withdrawn_at = withdrawn_at
    if expires_at is not None:
        consent.expires_at = expires_at
    if ip_address is not None:
        consent.ip_address = ip_address
    if user_agent is not None:
        consent.user_agent = user_agent
    if notes is not None:
        consent.notes = notes
    consent.updated_at = utc_now_naive()
    session.add(consent)
    await session.commit()
    await session.refresh(consent)
    return consent


async def get_consents_by_status(session: AsyncSession, status: str) -> list[UserConsent]:
    stmt = select(UserConsent).where(UserConsent.status == status).order_by(desc(UserConsent.updated_at))
    return list((await session.execute(stmt)).scalars().all())


async def get_consent_summary(session: AsyncSession, user_id: UUID) -> ConsentSummaryData:
    stmt = select(UserConsent.status, func.count(UserConsent.id)).where(UserConsent.user_id == user_id).group_by(UserConsent.status)  # pyright: ignore[reportArgumentType]
    rows = (await session.execute(stmt)).all()
    counts: ConsentSummaryData = {
        "user_id": user_id,
        "pending": 0,
        "granted": 0,
        "withdrawn": 0,
        "expired": 0,
        "total": 0,
    }
    total = 0
    for status, count in rows:
        count_value = int(count)
        status_value = str(status)
        if status_value == "pending":
            counts["pending"] = count_value
        elif status_value == "granted":
            counts["granted"] = count_value
        elif status_value == "withdrawn":
            counts["withdrawn"] = count_value
        elif status_value == "expired":
            counts["expired"] = count_value
        total += count_value
    counts["total"] = total
    return counts


async def get_active_consent_version(session: AsyncSession, consent_type_id: UUID) -> ConsentVersion | None:
    stmt = select(ConsentVersion).where(
        and_(
            ConsentVersion.consent_type_id == consent_type_id,  # pyright: ignore[reportArgumentType]
            ConsentVersion.is_active == True,  # pyright: ignore[reportArgumentType]
            ConsentVersion.effective_date <= utc_now_naive(),  # pyright: ignore[reportArgumentType]
        )
    ).order_by(desc(ConsentVersion.effective_date))
    return (await session.execute(stmt)).scalars().first()


async def create_consent_version(session: AsyncSession, data: ConsentVersionData) -> ConsentVersion:
    version = ConsentVersion(**data)
    session.add(version)
    await session.commit()
    await session.refresh(version)
    return version
