from uuid import UUID

from fastapi import APIRouter
from sqlmodel import SQLModel

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers import organization_controller
from swx_core.database.db import SessionDep
from swx_core.models.common import Message
from swx_core.models.organization import OrganizationMemberPublic
from swx_core.models.organization_invitation import OrganizationInvitationPublic


class InvitationTokenRequest(SQLModel):
    token: str


router = APIRouter(prefix="/user/organizations", tags=["user-organizations"])


@router.get("/", response_model=list[OrganizationMemberPublic])
async def list_user_organizations(session: SessionDep, current_user: UserDep) -> list[OrganizationMemberPublic]:
    organizations = await organization_controller.list_user_organizations_controller(session, current_user.id)
    return [OrganizationMemberPublic.model_validate(item) for item in organizations]


@router.post("/accept-invitation", response_model=OrganizationMemberPublic)
async def accept_invitation(session: SessionDep, body: InvitationTokenRequest, current_user: UserDep) -> OrganizationMemberPublic:
    return await organization_controller.accept_invitation_controller(session, body.token, current_user.id)


@router.post("/reject-invitation", response_model=OrganizationInvitationPublic)
async def reject_invitation(session: SessionDep, body: InvitationTokenRequest, current_user: UserDep) -> OrganizationInvitationPublic:
    return await organization_controller.reject_invitation_controller(session, body.token)


@router.delete("/{org_id}/leave", response_model=Message)
async def leave_organization(session: SessionDep, org_id: UUID, current_user: UserDep) -> Message:
    await organization_controller.leave_organization_controller(session, org_id, current_user.id)
    return Message(message="Organization left successfully")
