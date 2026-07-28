from uuid import UUID

from fastapi import APIRouter, Depends

from swx_core.auth.admin.dependencies import get_current_admin_user
from swx_core.controllers import consent_controller
from swx_core.database.db import SessionDep
from swx_core.models.consent import (
    ConsentTypeCreate,
    ConsentTypePublic,
    ConsentVersionCreate,
    ConsentVersionPublic,
    UserConsentPublic,
)

router = APIRouter(
    prefix="/admin/consent",
    tags=["admin-consent"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("/types", response_model=list[ConsentTypePublic])
async def list_consent_types(session: SessionDep) -> list[ConsentTypePublic]:
    return await consent_controller.list_consent_types_controller(session, active_only=False)


@router.post("/types", response_model=ConsentTypePublic, status_code=201)
async def create_consent_type(session: SessionDep, body: ConsentTypeCreate) -> ConsentTypePublic:
    return await consent_controller.create_consent_type_controller(session, body)


@router.post("/versions", response_model=ConsentVersionPublic, status_code=201)
async def create_consent_version(session: SessionDep, body: ConsentVersionCreate) -> ConsentVersionPublic:
    return await consent_controller.create_consent_version_controller(session, body)


@router.get("/users/{user_id}", response_model=list[UserConsentPublic])
async def get_user_consents(session: SessionDep, user_id: UUID) -> list[UserConsentPublic]:
    return await consent_controller.get_user_consents_controller(session, user_id)
