# pyright: reportAny=false, reportUnknownVariableType=false

from datetime import datetime
from typing import TypedDict
from uuid import UUID
from swx_core.utils.time import utc_now

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.organization import Organization, OrganizationMember
from swx_core.models.organization_invitation import OrganizationInvitation
from swx_core.models.team_invitation import InvitationStatus

class OrganizationData(TypedDict, total=False):
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    owner_id: UUID | None
    is_active: bool
    is_verified: bool
    settings: dict[str, object]

class OrganizationMemberData(TypedDict, total=False):
    organization_id: UUID
    user_id: UUID
    role: str
    is_active: bool
    invited_by: UUID | None
    joined_at: datetime

class OrganizationInvitationData(TypedDict, total=False):
    organization_id: UUID
    inviter_id: UUID
    invitee_email: str
    role: str
    status: str
    token: str
    message: str | None
    expires_at: datetime

async def get_organization_by_id(session: AsyncSession, org_id: UUID) -> Organization | None:
    stmt = select(Organization).where(Organization.id == org_id)
    return (await session.execute(stmt)).scalar_one_or_none()

async def get_organization_by_slug(session: AsyncSession, slug: str) -> Organization | None:
    stmt = select(Organization).where(Organization.slug == slug)
    return (await session.execute(stmt)).scalar_one_or_none()

async def get_all_organizations(session: AsyncSession, skip: int, limit: int) -> list[Organization]:
    stmt = select(Organization).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())

async def create_organization(session: AsyncSession, data: OrganizationData) -> Organization:
    organization = Organization(**data)
    session.add(organization)
    await session.commit()
    await session.refresh(organization)
    return organization

async def update_organization(session: AsyncSession, org_id: UUID, data: OrganizationData) -> Organization | None:
    organization = await session.get(Organization, org_id)
    if not organization:
        return None
    for key, value in data.items():
        setattr(organization, key, value)
    organization.updated_at = utc_now()
    session.add(organization)
    await session.commit()
    await session.refresh(organization)
    return organization

async def delete_organization(session: AsyncSession, org_id: UUID) -> bool:
    organization = await session.get(Organization, org_id)
    if not organization:
        return False
    await session.delete(organization)
    await session.commit()
    return True

async def get_member(session: AsyncSession, org_id: UUID, user_id: UUID) -> OrganizationMember | None:
    stmt = select(OrganizationMember).where(and_(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user_id))  # pyright: ignore[reportArgumentType]
    return (await session.execute(stmt)).scalar_one_or_none()

async def get_organization_members(session: AsyncSession, org_id: UUID) -> list[OrganizationMember]:
    stmt = select(OrganizationMember).where(OrganizationMember.organization_id == org_id)
    return list((await session.execute(stmt)).scalars().all())

async def get_user_organizations(session: AsyncSession, user_id: UUID) -> list[OrganizationMember]:
    stmt = select(OrganizationMember).join(Organization, Organization.id == OrganizationMember.organization_id).where(OrganizationMember.user_id == user_id)  # pyright: ignore[reportArgumentType]
    return list((await session.execute(stmt)).scalars().all())

async def add_member(session: AsyncSession, data: OrganizationMemberData) -> OrganizationMember:
    member = OrganizationMember(**data)
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member

async def update_member_role(session: AsyncSession, member_id: UUID, role: str) -> OrganizationMember | None:
    member = await session.get(OrganizationMember, member_id)
    if not member:
        return None
    member.role = role
    member.updated_at = utc_now()
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member

async def remove_member(session: AsyncSession, member_id: UUID) -> bool:
    member = await session.get(OrganizationMember, member_id)
    if not member:
        return False
    await session.delete(member)
    await session.commit()
    return True

async def create_invitation(session: AsyncSession, data: OrganizationInvitationData) -> OrganizationInvitation:
    invitation = OrganizationInvitation(**data)
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)
    return invitation

async def get_invitation_by_token(session: AsyncSession, token: str) -> OrganizationInvitation | None:
    stmt = select(OrganizationInvitation).where(OrganizationInvitation.token == token)
    return (await session.execute(stmt)).scalar_one_or_none()

async def get_pending_invitations(session: AsyncSession, org_id: UUID) -> list[OrganizationInvitation]:
    stmt = select(OrganizationInvitation).where(and_(OrganizationInvitation.organization_id == org_id, OrganizationInvitation.status == InvitationStatus.PENDING.value))  # pyright: ignore[reportArgumentType]
    return list((await session.execute(stmt)).scalars().all())

async def update_invitation_status(session: AsyncSession, invitation_id: UUID, status: str, accepted_at: datetime | None = None, rejected_at: datetime | None = None) -> OrganizationInvitation | None:
    invitation = await session.get(OrganizationInvitation, invitation_id)
    if not invitation:
        return None
    invitation.status = status
    invitation.accepted_at = accepted_at
    invitation.rejected_at = rejected_at
    invitation.updated_at = utc_now()
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)
    return invitation
