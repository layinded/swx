# pyright: reportMissingTypeArgument=false

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.controllers.safety_controller import get_check_controller, list_checks_controller, run_safety_check_controller
from swx_core.database.db import get_session
from swx_core.models.safety_check import SafetyCheckPublic, SafetyCheckRequest
from swx_core.security.dependencies import get_current_user

router = APIRouter(prefix="/safety", tags=["User - Safety"])


def _current_user_id(user: dict[str, object] | object) -> UUID:
    if isinstance(user, dict):
        return UUID(str(user["id"]))
    identifier = cast(str | UUID | None, getattr(user, "id", None))
    if identifier is None:
        raise ValueError("Authenticated user is missing an id")
    return identifier if isinstance(identifier, UUID) else UUID(str(identifier))


@router.post("/check", response_model=SafetyCheckPublic, status_code=201)
async def run_safety_check(
    body: SafetyCheckRequest,
    session: AsyncSession = Depends(get_session),
    user: object = Depends(get_current_user),
):
    user_id = _current_user_id(user)
    return await run_safety_check_controller(session, body.content, body.content_type, user_id, body.source, body.conversation_id)


@router.get("/checks", response_model=list[SafetyCheckPublic])
async def list_checks(
    overall_verdict: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    user: object = Depends(get_current_user),
):
    user_id = _current_user_id(user)
    return await list_checks_controller(session, user_id=user_id, overall_verdict=overall_verdict, skip=skip, limit=limit)


@router.get("/checks/{check_id}", response_model=SafetyCheckPublic)
async def get_check(check_id: UUID, session: AsyncSession = Depends(get_session), user: object = Depends(get_current_user)):
    user_id = _current_user_id(user)
    return await get_check_controller(session, check_id, user_id)
