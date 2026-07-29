import secrets
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID
from swx_core.utils.time import utc_now

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.events import event_bus
from swx_core.models.organization import (
    OrganizationCreate,
    OrganizationMemberPublic,
    OrganizationPublic,
    OrganizationRole,
    OrganizationUpdate,
)
from swx_core.models.organization_invitation import (
    OrganizationInvitationCreate,
    OrganizationInvitationPublic,
)
from swx_core.models.team_invitation import InvitationStatus
from swx_core.repositories import organization_repository
from swx_core.repositories.organization_repository import OrganizationData

async def _require_org(session: AsyncSession, org_id: UUID):
    organization = await organization_repository.get_organization_by_id(session, org_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization

async def _require_member(session: AsyncSession, org_id: UUID, user_id: UUID):
    member = await organization_repository.get_member(session, org_id, user_id)
    if not member or not member.is_active:
        raise HTTPException(status_code=403, detail="You are not a member of this organization")
    return member

async def _require_admin_member(session: AsyncSession, org_id: UUID, user_id: UUID):
    member = await _require_member(session, org_id, user_id)
    if member.role not in {OrganizationRole.OWNER.value, OrganizationRole.ADMIN.value}:
        raise HTTPException(status_code=403, detail="Admin access required")
    return member

async def create_organization(session: AsyncSession, data: OrganizationCreate, owner_id: UUID) -> OrganizationPublic:
    if await organization_repository.get_organization_by_slug(session, data.slug):
        raise HTTPException(status_code=400, detail="Organization slug already exists")
    organization_data = cast(OrganizationData, cast(object, {**data.model_dump(exclude_unset=True), "owner_id": owner_id}))
    organization = await organization_repository.create_organization(session, organization_data)
    await organization_repository.add_member(session, {"organization_id": organization.id, "user_id": owner_id, "role": OrganizationRole.OWNER.value, "invited_by": owner_id, "joined_at": utc_now(), "is_active": True})
    await event_bus.dispatch("organization.created", payload={"organization_id": str(organization.id), "owner_id": str(owner_id), "slug": organization.slug})
    return OrganizationPublic.model_validate(organization)

async def get_organization(session: AsyncSession, org_id: UUID) -> OrganizationPublic:
    return OrganizationPublic.model_validate(await _require_org(session, org_id))

async def update_organization(session: AsyncSession, org_id: UUID, data: OrganizationUpdate, user_id: UUID) -> OrganizationPublic:
    await _require_member(session, org_id, user_id)
    if data.slug:
        existing = await organization_repository.get_organization_by_slug(session, data.slug)
        if existing and existing.id != org_id:
            raise HTTPException(status_code=400, detail="Organization slug already exists")
    update_data = cast(OrganizationData, cast(object, data.model_dump(exclude_unset=True)))
    organization = await organization_repository.update_organization(session, org_id, update_data)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    await event_bus.dispatch("organization.updated", payload={"organization_id": str(organization.id), "name": organization.name, "slug": organization.slug})
    return OrganizationPublic.model_validate(organization)

async def delete_organization(session: AsyncSession, org_id: UUID, user_id: UUID) -> bool:
    organization = await _require_org(session, org_id)
    if organization.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only the organization owner can delete this organization")
    deleted = await organization_repository.delete_organization(session, org_id)
    if deleted:
        await event_bus.dispatch("organization.deleted", payload={"organization_id": str(org_id)})
    return deleted

async def list_organizations(session: AsyncSession, skip: int, limit: int) -> list[OrganizationPublic]:
    return [OrganizationPublic.model_validate(org) for org in await organization_repository.get_all_organizations(session, skip, limit)]

async def list_user_organizations(session: AsyncSession, user_id: UUID):
    return await organization_repository.get_user_organizations(session, user_id)

async def list_members(session: AsyncSession, org_id: UUID, user_id: UUID) -> list[OrganizationMemberPublic]:
    await _require_member(session, org_id, user_id)
    return [OrganizationMemberPublic.model_validate(member) for member in await organization_repository.get_organization_members(session, org_id)]

async def list_pending_invitations(session: AsyncSession, org_id: UUID, user_id: UUID) -> list[OrganizationInvitationPublic]:
    await _require_member(session, org_id, user_id)
    return [OrganizationInvitationPublic.model_validate(invitation) for invitation in await organization_repository.get_pending_invitations(session, org_id)]

async def invite_member(session: AsyncSession, org_id: UUID, data: OrganizationInvitationCreate, inviter_id: UUID) -> OrganizationInvitationPublic:
    await _require_admin_member(session, org_id, inviter_id)
    members = await organization_repository.get_organization_members(session, org_id)
    max_members = settings.ORGANIZATION_MAX_MEMBERS
    if max_members > 0 and len(members) >= max_members:
        raise HTTPException(status_code=400, detail="Organization member limit reached")
    invitation = await organization_repository.create_invitation(session, {"organization_id": org_id, "inviter_id": inviter_id, "invitee_email": data.invitee_email, "role": data.role, "status": InvitationStatus.PENDING.value, "token": secrets.token_urlsafe(32)[:64], "message": data.message, "expires_at": utc_now() + timedelta(days=settings.ORGANIZATION_INVITATION_EXPIRY_DAYS)})
    await event_bus.dispatch("organization.invitation_sent", payload={"organization_id": str(org_id), "invitation_id": str(invitation.id), "invitee_email": invitation.invitee_email})
    return OrganizationInvitationPublic.model_validate(invitation)

async def accept_invitation(session: AsyncSession, token: str, user_id: UUID) -> OrganizationMemberPublic:
    invitation = await organization_repository.get_invitation_by_token(session, token)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.status != InvitationStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Invitation is not pending")
    if invitation.expires_at <= utc_now():
        await organization_repository.update_invitation_status(session, invitation.id, InvitationStatus.EXPIRED.value)
        raise HTTPException(status_code=400, detail="Invitation has expired")
    member = await organization_repository.get_member(session, invitation.organization_id, user_id)
    if not member:
        member = await organization_repository.add_member(session, {"organization_id": invitation.organization_id, "user_id": user_id, "role": invitation.role, "invited_by": invitation.inviter_id, "joined_at": utc_now(), "is_active": True})
    public_member = OrganizationMemberPublic.model_validate(member)
    await organization_repository.update_invitation_status(session, invitation.id, InvitationStatus.ACCEPTED.value, accepted_at=utc_now())
    await event_bus.dispatch("organization.member_joined", payload={"organization_id": str(invitation.organization_id), "user_id": str(user_id), "role": public_member.role})
    return public_member

async def reject_invitation(session: AsyncSession, token: str) -> OrganizationInvitationPublic:
    invitation = await organization_repository.get_invitation_by_token(session, token)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    updated = await organization_repository.update_invitation_status(session, invitation.id, InvitationStatus.REJECTED.value, rejected_at=utc_now())
    if not updated:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return OrganizationInvitationPublic.model_validate(updated)

async def update_member_role(session: AsyncSession, org_id: UUID, member_id: UUID, role: str, requester_id: UUID) -> OrganizationMemberPublic:
    await _require_admin_member(session, org_id, requester_id)
    member = await organization_repository.update_member_role(session, member_id, role)
    if not member or member.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Organization member not found")
    await event_bus.dispatch("organization.member_role_changed", payload={"organization_id": str(org_id), "user_id": str(member.user_id), "role": role})
    return OrganizationMemberPublic.model_validate(member)

async def remove_member(session: AsyncSession, org_id: UUID, member_id: UUID, requester_id: UUID) -> bool:
    member = next((m for m in await organization_repository.get_organization_members(session, org_id) if m.id == member_id), None)
    if not member:
        raise HTTPException(status_code=404, detail="Organization member not found")
    if requester_id != member.user_id:
        await _require_admin_member(session, org_id, requester_id)
    removed = await organization_repository.remove_member(session, member_id)
    if removed:
        await event_bus.dispatch("organization.member_removed", payload={"organization_id": str(org_id), "user_id": str(member.user_id), "member_id": str(member_id)})
    return removed

async def leave_organization(session: AsyncSession, org_id: UUID, user_id: UUID) -> bool:
    member = await _require_member(session, org_id, user_id)
    return await remove_member(session, org_id, member.id, user_id)
