from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, status, Request
from sqlmodel import select
from sqlalchemy.orm import joinedload

from swx_core.database.db import SessionDep
from swx_core.models.team import TeamPublic, TeamCreate, TeamUpdate
from swx_core.models.team_member import TeamMemberCreate, TeamMemberPublic, TeamMember
from swx_core.models.user import UserPublic
from swx_core.models.team_role import TeamRolePublic
from swx_core.models.common import Message
from swx_core.auth.admin.dependencies import get_current_admin_user, AdminUserDep
from swx_core.controllers import team_controller
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome

router = APIRouter(
    prefix="/admin/team",
    tags=["admin-team"],
    dependencies=[Depends(get_current_admin_user)],
)

@router.get("/", response_model=list[TeamPublic])
async def list_teams(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all teams."""
    return await team_controller.list_teams_controller(session, skip, limit)


@router.post("/", response_model=TeamPublic, status_code=status.HTTP_201_CREATED)
async def create_team(
    session: SessionDep,
    team_in: TeamCreate,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Create a new team."""
    audit = get_audit_logger(session)
    try:
        team = await team_controller.create_team_controller(session, team_in)
        await audit.log_event(
            action="team.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="team",
            resource_id=str(team.id),
            outcome=AuditOutcome.SUCCESS,
            context=team_in.model_dump(),
            request=request
        )
        return team
    except Exception as e:
        await audit.log_event(
            action="team.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="team",
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), **team_in.model_dump()},
            request=request
        )
        raise e


@router.get("/{team_id}", response_model=TeamPublic)
async def get_team(
    session: SessionDep,
    team_id: UUID,
) -> Any:
    """Get team by ID."""
    return await team_controller.get_team_controller(session, team_id)


@router.patch("/{team_id}", response_model=TeamPublic)
async def update_team(
    session: SessionDep,
    team_id: UUID,
    team_in: TeamUpdate,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Update a team."""
    audit = get_audit_logger(session)
    try:
        team = await team_controller.update_team_controller(session, team_id, team_in)
        await audit.log_event(
            action="team.update",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="team",
            resource_id=str(team_id),
            outcome=AuditOutcome.SUCCESS,
            context=team_in.model_dump(),
            request=request
        )
        return team
    except Exception as e:
        await audit.log_event(
            action="team.update",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="team",
            resource_id=str(team_id),
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), **team_in.model_dump()},
            request=request
        )
        raise e


@router.delete("/{team_id}", response_model=Message)
async def delete_team(
    session: SessionDep,
    team_id: UUID,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Delete a team."""
    audit = get_audit_logger(session)
    try:
        await team_controller.delete_team_controller(session, team_id)
        await audit.log_event(
            action="team.delete",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="team",
            resource_id=str(team_id),
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return Message(message="Team deleted successfully")
    except Exception as e:
        await audit.log_event(
            action="team.delete",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="team",
            resource_id=str(team_id),
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise e


# Team Membership Management

@router.post("/member", response_model=TeamMemberPublic, status_code=status.HTTP_201_CREATED)
async def add_team_member(
    session: SessionDep,
    member_in: TeamMemberCreate,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Add a user to a team with a specific role."""
    audit = get_audit_logger(session)
    try:
        public = await team_controller.add_team_member_controller(session, member_in)
        await audit.log_event(
            action="team.member.add",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="team",
            resource_id=str(member_in.team_id),
            outcome=AuditOutcome.SUCCESS,
            context=member_in.model_dump(),
            request=request
        )
        return public
    except Exception as e:
        await audit.log_event(
            action="team.member.add",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="team",
            resource_id=str(member_in.team_id),
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), **member_in.model_dump()},
            request=request
        )
        raise e


@router.delete("/member/{member_id}", response_model=Message)
async def remove_team_member(
    session: SessionDep,
    member_id: UUID,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Remove a user from a team."""
    audit = get_audit_logger(session)
    try:
        await team_controller.remove_team_member_controller(session, member_id)
        await audit.log_event(
            action="team.member.remove",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="team_member",
            resource_id=str(member_id),
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return Message(message="Member removed from team")
    except Exception as e:
        await audit.log_event(
            action="team.member.remove",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="team_member",
            resource_id=str(member_id),
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise e


@router.get("/{team_id}/members", response_model=list[TeamMemberPublic])
async def list_team_members(
    session: SessionDep,
    team_id: UUID,
) -> Any:
    """List all members of a team."""
    members = await team_controller.list_team_members_controller(session, team_id)
    return [
        TeamMemberPublic(
            id=m.id,
            team_id=m.team_id,
            user_id=m.user_id,
            team_role_id=m.team_role_id,
            created_at=m.created_at,
        )
        for m in members
    ]


@router.get("/{team_id}/members/enriched")
async def list_team_members_enriched(
    session: SessionDep,
    team_id: UUID,
) -> Any:
    """List all members with full user and role details."""
    from sqlalchemy.orm import joinedload
    from swx_core.models.team_member import TeamMember
    
    result = await session.execute(
        select(TeamMember)
        .where(TeamMember.team_id == team_id)
        .options(joinedload(TeamMember.user), joinedload(TeamMember.team_role))  # type: ignore[attribute]
    )
    members = result.unique().scalars().all()
    
    return [
        {
            "id": str(m.id),
            "team_id": str(m.team_id),
            "user": {
                "id": str(m.user.id),  # type: ignore[union-attr]
                "email": m.user.email,  # type: ignore[union-attr]
                "full_name": m.user.full_name,  # type: ignore[union-attr]
                "avatar_url": m.user.avatar_url,  # type: ignore[union-attr]
            },
            "team_role": {
                "id": str(m.team_role.id),  # type: ignore[union-attr]
                "key": m.team_role.key,  # type: ignore[union-attr]
                "name": m.team_role.name,  # type: ignore[union-attr]
                "permissions": m.team_role.permissions,  # type: ignore[union-attr]
            },
            "created_at": m.created_at.isoformat(),
        }
        for m in members
    ]
