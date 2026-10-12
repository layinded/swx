from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.organization import OrganizationMemberPublic, OrganizationPublic, OrganizationUpdate
from swx_core.models.organization_invitation import OrganizationInvitationCreate, OrganizationInvitationPublic
from swx_core.services import organization_service


async def list_organizations_controller(session: AsyncSession, skip: int = 0, limit: int = 100) -> list[OrganizationPublic]:
    return await organization_service.list_organizations(session, skip, limit)


async def create_organization_controller(session: AsyncSession, data, owner_id: UUID) -> OrganizationPublic:
    return await organization_service.create_organization(session, data, owner_id)


async def get_organization_controller(session: AsyncSession, org_id: UUID) -> OrganizationPublic:
    return await organization_service.get_organization(session, org_id)


async def update_organization_controller(session: AsyncSession, org_id: UUID, data: OrganizationUpdate, user_id: UUID) -> OrganizationPublic:
    return await organization_service.update_organization(session, org_id, data, user_id)


async def delete_organization_controller(session: AsyncSession, org_id: UUID, user_id: UUID) -> bool:
    return await organization_service.delete_organization(session, org_id, user_id)


async def list_user_organizations_controller(session: AsyncSession, user_id: UUID):
    return await organization_service.list_user_organizations(session, user_id)


async def list_members_controller(session: AsyncSession, org_id: UUID, user_id: UUID) -> list[OrganizationMemberPublic]:
    return await organization_service.list_members(session, org_id, user_id)


async def list_pending_invitations_controller(session: AsyncSession, org_id: UUID, user_id: UUID) -> list[OrganizationInvitationPublic]:
    return await organization_service.list_pending_invitations(session, org_id, user_id)


async def invite_member_controller(session: AsyncSession, org_id: UUID, data: OrganizationInvitationCreate, inviter_id: UUID) -> OrganizationInvitationPublic:
    return await organization_service.invite_member(session, org_id, data, inviter_id)


async def accept_invitation_controller(session: AsyncSession, token: str, user_id: UUID) -> OrganizationMemberPublic:
    return await organization_service.accept_invitation(session, token, user_id)


async def reject_invitation_controller(session: AsyncSession, token: str) -> OrganizationInvitationPublic:
    return await organization_service.reject_invitation(session, token)


async def leave_organization_controller(session: AsyncSession, org_id: UUID, user_id: UUID) -> bool:
    return await organization_service.leave_organization(session, org_id, user_id)
