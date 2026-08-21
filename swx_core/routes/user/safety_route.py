# pyright: reportMissingTypeArgument=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers.safety_controller import get_check_controller, list_checks_controller, run_safety_check_controller
from swx_core.database.db import get_session
from swx_core.models.safety_check import SafetyCheckPublic, SafetyCheckRequest

router = APIRouter(prefix="/safety", tags=["User - Safety"])


@router.post("/check", response_model=SafetyCheckPublic, status_code=201)
async def run_safety_check(
    user: UserDep,
    body: SafetyCheckRequest,
    session: AsyncSession = Depends(get_session),
):
    return await run_safety_check_controller(session, body.content, body.content_type, user.id, body.source, body.conversation_id)


@router.get("/checks", response_model=list[SafetyCheckPublic])
async def list_checks(
    user: UserDep,
    session: AsyncSession = Depends(get_session),
    overall_verdict: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    return await list_checks_controller(session, user_id=user.id, overall_verdict=overall_verdict, skip=skip, limit=limit)


@router.get("/checks/{check_id}", response_model=SafetyCheckPublic)
async def get_check(
    user: UserDep,
    check_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_check_controller(session, check_id, user.id)