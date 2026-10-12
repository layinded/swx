from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from swx_core.auth.admin.dependencies import get_current_admin_user
from swx_core.controllers import organization_controller
from swx_core.database.db import SessionDep
from swx_core.models.common import Message
from swx_core.models.organization import OrganizationCreate, OrganizationMemberPublic, OrganizationPublic, OrganizationUpdate
from swx_core.models.organization_invitation import OrganizationInvitationCreate, OrganizationInvitationPublic

router = APIRouter(prefix="/admin/organizations", tags=["admin-organizations"], dependencies=[Depends(get_current_admin_user)])


async def _owner_id_for_org(session: SessionDep, org_id: UUID) -> UUID:
    organization = await organization_controller.get_organization_controller(session, org_id)
    if not organization.owner_id:
        raise HTTPException(status_code=400, detail="Organization owner is not set")
    return organization.owner_id


@router.get("/", response_model=list[OrganizationPublic])
async def list_organizations(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    return await organization_controller.list_organizations_controller(session, skip, limit)


@router.get("/{org_id}", response_model=OrganizationPublic)
async def get_organization(session: SessionDep, org_id: UUID) -> Any:
    return await organization_controller.get_organization_controller(session, org_id)


@router.post("/", response_model=OrganizationPublic, status_code=status.HTTP_201_CREATED)
async def create_organization(session: SessionDep, body: OrganizationCreate) -> Any:
    if not body.owner_id:
        raise HTTPException(status_code=400, detail="owner_id is required")
    return await organization_controller.create_organization_controller(session, body, body.owner_id)


@router.put("/{org_id}", response_model=OrganizationPublic)
async def update_organization(session: SessionDep, org_id: UUID, body: OrganizationUpdate) -> Any:
    owner_id = await _owner_id_for_org(session, org_id)
    return await organization_controller.update_organization_controller(session, org_id, body, owner_id)


@router.delete("/{org_id}", response_model=Message)
async def delete_organization(session: SessionDep, org_id: UUID) -> Message:
    owner_id = await _owner_id_for_org(session, org_id)
    await organization_controller.delete_organization_controller(session, org_id, owner_id)
    return Message(message="Organization deleted successfully")


@router.get("/{org_id}/members", response_model=list[OrganizationMemberPublic])
async def list_members(session: SessionDep, org_id: UUID) -> Any:
    owner_id = await _owner_id_for_org(session, org_id)
    return await organization_controller.list_members_controller(session, org_id, owner_id)


@router.post("/{org_id}/invitations", response_model=OrganizationInvitationPublic, status_code=status.HTTP_201_CREATED)
async def invite_member(session: SessionDep, org_id: UUID, body: OrganizationInvitationCreate) -> Any:
    owner_id = await _owner_id_for_org(session, org_id)
    return await organization_controller.invite_member_controller(session, org_id, body, owner_id)


@router.get("/{org_id}/invitations", response_model=list[OrganizationInvitationPublic])
async def list_pending_invitations(session: SessionDep, org_id: UUID) -> Any:
    owner_id = await _owner_id_for_org(session, org_id)
    return await organization_controller.list_pending_invitations_controller(session, org_id, owner_id)
