# pyright: reportMissingTypeArgument=false, reportMissingImports=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...controllers.sso_controller import initiate_sso_controller, list_providers_controller, list_sessions_controller, terminate_session_controller
from ...database.db import get_session
from ...models.sso_provider import SSOProviderPublic
from ...models.sso_session import SSOSessionPublic
from ...security.dependencies import get_current_user


class SSOInitiateRequest(BaseModel):
    provider_id: UUID
    metadata_: dict[str, object] | None = None


router = APIRouter(prefix="/sso", tags=["User - SSO"])


def _current_user_id(user: object) -> UUID:
    return UUID(str(user["id"])) if isinstance(user, dict) else UUID(str(getattr(user, "id")))


@router.post("/initiate", response_model=dict[str, object])
async def initiate_sso(body: SSOInitiateRequest, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_user)):
    return await initiate_sso_controller(session, _current_user_id(user), body.provider_id, body.metadata_)


@router.get("/providers", response_model=list[SSOProviderPublic])
async def list_enabled_providers(skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=200), session: AsyncSession = Depends(get_session), _user: dict = Depends(get_current_user)):
    return await list_providers_controller(session, enabled_only=True, skip=skip, limit=limit)


@router.get("/sessions", response_model=list[SSOSessionPublic])
async def list_my_sessions(skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=200), session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_user)):
    return await list_sessions_controller(session, user_id=_current_user_id(user), skip=skip, limit=limit)


@router.delete("/sessions/{sso_session_id}", response_model=SSOSessionPublic)
async def terminate_my_session(sso_session_id: UUID, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_user)):
    return await terminate_session_controller(session, sso_session_id, _current_user_id(user))
