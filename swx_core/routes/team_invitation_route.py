"""
Team Invitation Routes
---------------------
API routes for team invitation management.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.database import get_session
from swx_core.auth.user.dependencies import get_current_user
from swx_core.models.user import User
from swx_core.models.team_invitation import (
    TeamInvitation,
    TeamInvitationCreate,
    TeamInvitationPublic,
)
from swx_core.services.team_invitation_service import TeamInvitationService


router = APIRouter(prefix="/team-invitations", tags=["team-invitations"])


@router.post("/", response_model=TeamInvitationPublic, status_code=201)
async def create_invitation(
    invitation: TeamInvitationCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TeamInvitation:
    """Create a team invitation."""
    service = TeamInvitationService(session)
    return await service.create_invitation(
        team_id=invitation.team_id,
        inviter_id=current_user.id,
        invitee_email=invitation.invitee_email,
        team_role_id=invitation.team_role_id,
        message=invitation.message,
    )


@router.post("/{token}/accept", response_model=dict)
async def accept_invitation(
    token: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Accept a team invitation."""
    service = TeamInvitationService(session)
    team = await service.accept_invitation(token, current_user.id)
    return {"status": "accepted", "team_id": str(team.id)}


@router.post("/{token}/reject", response_model=dict)
async def reject_invitation(
    token: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Reject a team invitation."""
    service = TeamInvitationService(session)
    await service.reject_invitation(token, current_user.id)
    return {"status": "rejected"}


@router.delete("/{invitation_id}", response_model=dict)
async def revoke_invitation(
    invitation_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Revoke a team invitation."""
    service = TeamInvitationService(session)
    await service.revoke_invitation(invitation_id, current_user.id)
    return {"status": "revoked"}


@router.get("/team/{team_id}", response_model=list[TeamInvitationPublic])
async def list_team_invitations(
    team_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[TeamInvitation]:
    """List all invitations for a team."""
    service = TeamInvitationService(session)
    return await service.list_team_invitations(team_id, current_user.id)


@router.get("/me", response_model=list[TeamInvitationPublic])
async def list_my_invitations(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[TeamInvitation]:
    """List pending invitations for current user."""
    service = TeamInvitationService(session)
    return await service.list_user_invitations(current_user.email)