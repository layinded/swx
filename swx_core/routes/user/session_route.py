from uuid import UUID

from fastapi import APIRouter, Depends

from swx_core.auth.user.dependencies import get_current_user
from swx_core.database.db import SessionDep
from swx_core.models.refresh_token import SessionPublic
from swx_core.models.user import User
from swx_core.controllers import session_controller

router = APIRouter(
    prefix="/user/sessions",
    tags=["user-sessions"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/", response_model=list[SessionPublic])
async def list_sessions(
    session: SessionDep,
    current_user: User = Depends(get_current_user),
) -> list[SessionPublic]:
    return await session_controller.list_sessions_controller(session, current_user.email)


@router.delete("/{token_id}")
async def revoke_session(
    token_id: UUID,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    return await session_controller.revoke_session_controller(session, token_id, current_user.email)


@router.delete("/")
async def revoke_all_sessions(
    session: SessionDep,
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    return await session_controller.revoke_all_sessions_controller(session, current_user.email)