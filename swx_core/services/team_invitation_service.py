"""
Team Invitation Service
----------------------
Service for managing team invitations.
"""

import secrets
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import List

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_

from swx_core.models.team_invitation import (
    TeamInvitation,
    TeamInvitationCreate,
    InvitationStatus,
)
from swx_core.models.team_role import TeamRole
from swx_core.models.team import Team
from swx_core.models.team_member import TeamMember
from swx_core.models.user import User
from swx_core.middleware.logging_middleware import logger


class TeamInvitationService:
    """
    Service for managing team invitations.
    
    Handles invitation creation, acceptance, rejection, and revocation.
    Validates permissions and ensures data integrity.
    """
    
    INVITATION_EXPIRY_DAYS = 7
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_invitation(
        self,
        team_id: UUID,
        inviter_id: UUID,
        invitee_email: str,
        team_role_id: UUID,
        message: str | None = None,
    ) -> TeamInvitation:
        """
        Create a team invitation.
        
        Validates:
        - Inviter has permission to invite
        - Team exists
        - Invitee is not already a member
        - No pending invitation exists for this email
        """
        team = await self._get_team(team_id)
        if not team:
            raise HTTPException(404, "Team not found")
        
        await self._validate_invite_permission(inviter_id, team_id)
        
        existing_member = await self._get_team_member_by_email(team_id, invitee_email)
        if existing_member:
            raise HTTPException(400, "User is already a team member")
        
        pending = await self._get_pending_invitation(team_id, invitee_email)
        if pending:
            raise HTTPException(400, "Pending invitation already exists for this email")
        
        team_role = await self._get_team_role(team_role_id)
        if not team_role:
            raise HTTPException(404, "Team role not found")
        
        invitation = TeamInvitation(
            team_id=team_id,
            inviter_id=inviter_id,
            invitee_email=invitee_email,
            team_role_id=team_role_id,
            message=message,
            token=secrets.token_urlsafe(32),
            status=InvitationStatus.PENDING,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=self.INVITATION_EXPIRY_DAYS),
        )
        
        self.session.add(invitation)
        await self.session.commit()
        await self.session.refresh(invitation)
        
        logger.info(f"Created team invitation for {invitee_email} to team {team_id}")
        
        return invitation
    
    async def accept_invitation(self, token: str, user_id: UUID) -> Team:
        """
        Accept a team invitation.
        
        Validates:
        - Token is valid
        - Invitation is pending
        - Invitation not expired
        - User email matches invitee_email
        """
        invitation = await self._get_invitation_by_token(token)
        
        if not invitation:
            raise HTTPException(404, "Invitation not found")
        
        if invitation.status != InvitationStatus.PENDING:
            raise HTTPException(400, f"Invitation already {invitation.status.value}")
        
        if invitation.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            invitation.status = InvitationStatus.EXPIRED
            await self.session.commit()
            raise HTTPException(400, "Invitation has expired")
        
        user = await self._get_user(user_id)
        if not user:
            raise HTTPException(404, "User not found")
        
        if user.email != invitation.invitee_email:
            raise HTTPException(403, "This invitation is for a different email address")
        
        existing_member = await self._get_team_member(invitation.team_id, user_id)
        if existing_member:
            invitation.status = InvitationStatus.ACCEPTED
            invitation.accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await self.session.commit()
            return await self._get_team(invitation.team_id)
        
        member = TeamMember(
            team_id=invitation.team_id,
            user_id=user_id,
            team_role_id=invitation.team_role_id,
        )
        self.session.add(member)
        
        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.session.commit()
        
        logger.info(f"User {user_id} accepted invitation to team {invitation.team_id}")
        
        return await self._get_team(invitation.team_id)
    
    async def reject_invitation(self, token: str, user_id: UUID) -> None:
        """Reject a team invitation."""
        invitation = await self._get_invitation_by_token(token)
        
        if not invitation:
            raise HTTPException(404, "Invitation not found")
        
        if invitation.status != InvitationStatus.PENDING:
            raise HTTPException(400, f"Invitation already {invitation.status.value}")
        
        user = await self._get_user(user_id)
        if user and user.email != invitation.invitee_email:
            raise HTTPException(403, "This invitation is for a different email address")
        
        invitation.status = InvitationStatus.REJECTED
        invitation.rejected_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.session.commit()
        
        logger.info(f"Invitation {invitation.id} rejected")
    
    async def revoke_invitation(self, invitation_id: UUID, revoker_id: UUID) -> None:
        """Revoke a pending invitation (inviter or team owner only)."""
        invitation = await self._get_invitation(invitation_id)
        
        if not invitation:
            raise HTTPException(404, "Invitation not found")
        
        if invitation.status != InvitationStatus.PENDING:
            raise HTTPException(400, "Can only revoke pending invitations")
        
        await self._validate_revoke_permission(revoker_id, invitation)
        
        invitation.status = InvitationStatus.REVOKED
        await self.session.commit()
        
        logger.info(f"Invitation {invitation_id} revoked by {revoker_id}")
    
    async def list_team_invitations(
        self, team_id: UUID, user_id: UUID
    ) -> List[TeamInvitation]:
        """List all invitations for a team (requires team owner permission)."""
        await self._validate_view_permission(user_id, team_id)
        
        result = await self.session.execute(
            select(TeamInvitation).where(TeamInvitation.team_id == team_id)
        )
        return list(result.scalars().all())
    
    async def list_user_invitations(self, user_email: str) -> List[TeamInvitation]:
        """List all pending invitations for a user's email."""
        result = await self.session.execute(
            select(TeamInvitation).where(
                and_(
                    TeamInvitation.invitee_email == user_email,
                    TeamInvitation.status == InvitationStatus.PENDING,
                )
            )
        )
        return list(result.scalars().all())
    
    # Private helper methods
    
    async def _get_team(self, team_id: UUID) -> Team | None:
        result = await self.session.execute(select(Team).where(Team.id == team_id))
        return result.scalar_one_or_none()
    
    async def _get_user(self, user_id: UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def _get_team_role(self, team_role_id: UUID) -> TeamRole | None:
        result = await self.session.execute(select(TeamRole).where(TeamRole.id == team_role_id))
        return result.scalar_one_or_none()
    
    async def _get_invitation(self, invitation_id: UUID) -> TeamInvitation | None:
        result = await self.session.execute(select(TeamInvitation).where(TeamInvitation.id == invitation_id))
        return result.scalar_one_or_none()
    
    async def _get_invitation_by_token(self, token: str) -> TeamInvitation | None:
        result = await self.session.execute(select(TeamInvitation).where(TeamInvitation.token == token))
        return result.scalar_one_or_none()
    
    async def _get_team_member(
        self, team_id: UUID, user_id: UUID
    ) -> TeamMember | None:
        result = await self.session.execute(
            select(TeamMember).where(
                and_(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_team_member_by_email(
        self, team_id: UUID, email: str
    ) -> TeamMember | None:
        user_result = await self.session.execute(
            select(User).where(User.email == email)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return None

        return await self._get_team_member(team_id, user.id)
    
    async def _get_pending_invitation(
        self, team_id: UUID, email: str
    ) -> TeamInvitation | None:
        result = await self.session.execute(
            select(TeamInvitation).where(
                and_(
                    TeamInvitation.team_id == team_id,
                    TeamInvitation.invitee_email == email,
                    TeamInvitation.status == InvitationStatus.PENDING,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _validate_invite_permission(self, user_id: UUID, team_id: UUID) -> None:
        """Check if user can invite to this team (owner or editor role)."""
        member = await self._get_team_member(team_id, user_id)
        if not member:
            raise HTTPException(403, "You are not a member of this team")
        
        team_role = await self._get_team_role(member.team_role_id)
        if not team_role:
            raise HTTPException(500, "Team role not found")
        
        if not team_role.permissions.get("can_invite", False):
            raise HTTPException(403, "You do not have permission to invite members")
    
    async def _validate_revoke_permission(
        self, user_id: UUID, invitation: TeamInvitation
    ) -> None:
        """Check if user can revoke this invitation (inviter or team owner)."""
        if invitation.inviter_id == user_id:
            return
        
        member = await self._get_team_member(invitation.team_id, user_id)
        if not member:
            raise HTTPException(403, "You are not a member of this team")
        
        team_role = await self._get_team_role(member.team_role_id)
        if team_role and team_role.key == "owner":
            return
        
        raise HTTPException(403, "You do not have permission to revoke this invitation")
    
    async def _validate_view_permission(self, user_id: UUID, team_id: UUID) -> None:
        """Check if user can view invitations for this team."""
        member = await self._get_team_member(team_id, user_id)
        if not member:
            raise HTTPException(403, "You are not a member of this team")
        
        team_role = await self._get_team_role(member.team_role_id)
        if not team_role:
            raise HTTPException(500, "Team role not found")
        
        if not team_role.permissions.get("can_invite", False):
            raise HTTPException(403, "You do not have permission to view invitations")