"""User-scoped workspace endpoints for Enterprise Dashboard."""
from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends

from swx_core.database.db import SessionDep
from swx_core.models.team import TeamPublic, TeamCreate, TeamUpdate
from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers import team_controller

router = APIRouter(
    prefix="/workspaces",
    tags=["workspaces"],
)


@router.get("/", response_model=list[TeamPublic])
async def list_user_workspaces(
    session: SessionDep,
    current_user: UserDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all workspaces (teams) where current user is a member."""
    from swx_core.services.team_service import list_user_teams_service
    return await list_user_teams_service(session, current_user.id, skip, limit)


@router.get("/{workspace_id}", response_model=TeamPublic)
async def get_workspace(
    session: SessionDep,
    workspace_id: UUID,
    current_user: UserDep,
) -> Any:
    """Get workspace details (user must be member)."""
    from swx_core.services.team_service import get_user_team_service
    return await get_user_team_service(session, workspace_id, current_user.id)


@router.post("/", response_model=TeamPublic, status_code=201)
async def create_workspace(
    session: SessionDep,
    team_in: TeamCreate,
    current_user: UserDep,
) -> Any:
    """Create a new workspace (team)."""
    return await team_controller.create_team_controller(session, team_in)


@router.put("/{workspace_id}", response_model=TeamPublic)
async def update_workspace(
    session: SessionDep,
    workspace_id: UUID,
    team_in: TeamUpdate,
    current_user: UserDep,
) -> Any:
    """Update workspace (user must have write permission)."""
    return await team_controller.update_team_controller(session, workspace_id, team_in)


@router.delete("/{workspace_id}", response_model=dict)
async def delete_workspace(
    session: SessionDep,
    workspace_id: UUID,
    current_user: UserDep,
) -> Any:
    """Archive/delete workspace (user must be owner)."""
    await team_controller.delete_team_controller(session, workspace_id)
    return {"message": "Workspace deleted successfully"}