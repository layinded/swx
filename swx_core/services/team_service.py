from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from swx_core.models.team import Team, TeamCreate, TeamUpdate
from swx_core.models.team_member import TeamMember, TeamMemberCreate
from swx_core.repositories import team_repository, user_repository, role_repository
from swx_core.events.dispatcher import EventBus, Event


async def list_teams_service(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Team]:
    return await team_repository.get_all_teams(session, skip, limit)


async def create_team_service(
    session: AsyncSession, 
    team_in: TeamCreate,
    event_context: Dict[str, Any] | None = None,
) -> Team:
    team = await team_repository.create_team(session, team_in)
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="team.created",
        payload={
            "id": str(team.id),
            "data": {"name": team.name, "description": team.description},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return team


async def get_team_service(session: AsyncSession, team_id: UUID) -> Team:
    team = await team_repository.get_team_by_id(session, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


async def update_team_service(
    session: AsyncSession, 
    team_id: UUID, 
    team_in: TeamUpdate,
    event_context: Dict[str, Any] | None = None,
) -> Team:
    team = await get_team_service(session, team_id)
    old_values = {"name": team.name, "description": team.description}
    team = await team_repository.update_team(session, team, team_in)
    new_values = {"name": team.name, "description": team.description}
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="team.updated",
        payload={
            "id": str(team.id),
            "old_values": old_values,
            "new_values": new_values,
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return team


async def delete_team_service(
    session: AsyncSession, 
    team_id: UUID,
    event_context: Dict[str, Any] | None = None,
) -> None:
    team = await get_team_service(session, team_id)
    
    # Check if has members
    members = await team_repository.list_team_members(session, team_id)
    if members:
        raise HTTPException(status_code=400, detail="Cannot delete team with members")
        
    await team_repository.delete_team(session, team)
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="team.deleted",
        payload={
            "id": str(team_id),
            "data": {"name": team.name},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))


# Team Membership Management

async def add_team_member_service(
    session: AsyncSession, 
    member_in: TeamMemberCreate,
    event_context: Dict[str, Any] | None = None,
) -> TeamMember:
    await get_team_service(session, member_in.team_id) # Validate team existence
    
    user = await user_repository.get_user_by_id(session, member_in.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    role = await role_repository.get_role_by_id(session, member_in.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    existing = await team_repository.get_team_member(session, member_in.team_id, member_in.user_id)
    if existing:
        return await team_repository.update_team_member_role(session, existing, member_in.role_id)
        
    member = await team_repository.add_team_member(session, member_in)
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="team.member_added",
        payload={
            "id": str(member.id),
            "data": {"team_id": str(member_in.team_id), "user_id": str(member_in.user_id), "role_id": str(member_in.role_id)},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return member


async def remove_team_member_service(
    session: AsyncSession, 
    member_id: UUID,
    event_context: Dict[str, Any] | None = None,
) -> None:
    member = await team_repository.get_team_member_by_id(session, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    await team_repository.remove_team_member(session, member)
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="team.member_removed",
        payload={
            "id": str(member_id),
            "data": {"team_id": str(member.team_id), "user_id": str(member.user_id)},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))


async def list_team_members_service(session: AsyncSession, team_id: UUID) -> List[TeamMember]:
    await get_team_service(session, team_id) # Validate existence
    return await team_repository.list_team_members(session, team_id)
