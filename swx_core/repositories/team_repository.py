from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from swx_core.models.team import Team, TeamCreate, TeamUpdate
from swx_core.models.team_member import TeamMember, TeamMemberCreate

async def get_team_by_id(session: AsyncSession, team_id: UUID) -> Optional[Team]:
    return await session.get(Team, team_id)

async def get_all_teams(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Team]:
    statement = select(Team).offset(skip).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())

async def create_team(session: AsyncSession, team_in: TeamCreate) -> Team:
    db_obj = Team.model_validate(team_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

async def update_team(session: AsyncSession, db_obj: Team, team_in: TeamUpdate) -> Team:
    update_data = team_in.model_dump(exclude_unset=True)
    db_obj.sqlmodel_update(update_data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

async def delete_team(session: AsyncSession, db_obj: Team) -> None:
    await session.delete(db_obj)
    await session.commit()

async def get_team_member(session: AsyncSession, team_id: UUID, user_id: UUID) -> Optional[TeamMember]:
    statement = select(TeamMember).where(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()

async def get_team_member_by_id(session: AsyncSession, member_id: UUID) -> Optional[TeamMember]:
    return await session.get(TeamMember, member_id)

async def add_team_member(session: AsyncSession, member_in: TeamMemberCreate) -> TeamMember:
    db_obj = TeamMember.model_validate(member_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

async def update_team_member_role(session: AsyncSession, db_obj: TeamMember, role_id: UUID) -> TeamMember:
    db_obj.role_id = role_id
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

async def remove_team_member(session: AsyncSession, db_obj: TeamMember) -> None:
    await session.delete(db_obj)
    await session.commit()

async def list_team_members(session: AsyncSession, team_id: UUID) -> List[TeamMember]:
    statement = select(TeamMember).where(TeamMember.team_id == team_id)
    result = await session.execute(statement)
    return list(result.scalars().all())
