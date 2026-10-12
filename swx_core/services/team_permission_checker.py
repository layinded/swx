"""
Team Permission Checker
-----------------------
Service for checking team-scoped permissions.
"""

from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.team_member import TeamMember
from swx_core.models.team_role import TeamRole
from swx_core.models.user import User


class TeamPermissionChecker:
    """Check team-scoped permissions for users.

    Uses TeamRole.permissions dict to determine if a user
    has specific permissions within a team context.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def has_permission(
        self,
        user_id: UUID,
        team_id: UUID,
        permission: str,
    ) -> bool:
        """Check if user has a specific permission in a team."""
        member = await self._get_team_member_with_role(team_id, user_id)
        if not member:
            return False

        if await self._is_superuser(user_id):
            return True

        team_role = member.team_role if hasattr(member, 'team_role') else None
        if not team_role:
            return False

        return team_role.permissions.get(permission, False)

    async def get_permissions(self, user_id: UUID, team_id: UUID) -> dict:
        """Get all permissions for a user in a team."""
        default_permissions = {
            "can_edit": False,
            "can_delete": False,
            "can_invite": False,
            "can_remove": False,
            "can_change_roles": False,
            "can_manage_billing": False,
        }

        member = await self._get_team_member_with_role(team_id, user_id)
        if not member:
            return default_permissions

        if await self._is_superuser(user_id):
            return {k: True for k in default_permissions}

        team_role = member.team_role if hasattr(member, 'team_role') else None
        if not team_role:
            return default_permissions

        return {**default_permissions, **team_role.permissions}

    async def get_team_role(self, user_id: UUID, team_id: UUID) -> Optional[TeamRole]:
        """Get the team role for a user in a team."""
        member = await self._get_team_member_with_role(team_id, user_id)
        if not member:
            return None

        return member.team_role if hasattr(member, 'team_role') else None

    async def is_team_member(self, user_id: UUID, team_id: UUID) -> bool:
        """Check if user is a member of the team."""
        member = await self._get_team_member(team_id, user_id)
        return member is not None

    async def is_team_owner(self, user_id: UUID, team_id: UUID) -> bool:
        """Check if user is the owner of the team."""
        member = await self._get_team_member_with_role(team_id, user_id)
        if not member:
            return False

        team_role = member.team_role if hasattr(member, 'team_role') else None
        return team_role is not None and team_role.key == "owner"

    # Private helper methods

    async def _get_team_member(
        self, team_id: UUID, user_id: UUID
    ) -> Optional[TeamMember]:
        result = await self.session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_team_member_with_role(
        self, team_id: UUID, user_id: UUID
    ) -> Optional[TeamMember]:
        """Get team member with team_role relationship loaded.

        TeamMember.team_role uses lazy="selectin" so the relationship
        is automatically eager-loaded in the same query.
        """
        result = await self.session.execute(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _is_superuser(self, user_id: UUID) -> bool:
        """Check if user is a superuser (bypasses team permissions)."""
        result = await self.session.execute(
            select(User.is_superuser).where(User.id == user_id)
        )
        is_superuser = result.scalar_one_or_none()
        return is_superuser is True