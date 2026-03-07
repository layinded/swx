from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from swx_core.models.team import Team, TeamCreate, TeamUpdate
from swx_core.models.team_member import TeamMember, TeamMemberCreate, TeamMemberPublic
from swx_core.services import team_service

async def list_teams_controller(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Team]:
    return await team_service.list_teams_service(session, skip, limit)

async def create_team_controller(session: AsyncSession, team_in: TeamCreate) -> Team:
    return await team_service.create_team_service(session, team_in)

async def get_team_controller(session: AsyncSession, team_id: UUID) -> Team:
    return await team_service.get_team_service(session, team_id)

async def update_team_controller(session: AsyncSession, team_id: UUID, team_in: TeamUpdate) -> Team:
    return await team_service.update_team_service(session, team_id, team_in)

async def delete_team_controller(session: AsyncSession, team_id: UUID) -> None:
    return await team_service.delete_team_service(session, team_id)

# Team Membership Management

async def add_team_member_controller(session: AsyncSession, member_in: TeamMemberCreate) -> TeamMemberPublic:
    member = await team_service.add_team_member_service(session, member_in)
    return TeamMemberPublic(id=member.id, team_id=member.team_id, user_id=member.user_id, role_id=member.role_id)

async def remove_team_member_controller(session: AsyncSession, member_id: UUID) -> None:
    return await team_service.remove_team_member_service(session, member_id)

async def list_team_members_controller(session: AsyncSession, team_id: UUID) -> List[TeamMember]:
    return await team_service.list_team_members_service(session, team_id)
