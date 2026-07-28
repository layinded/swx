from fastapi import APIRouter, Request

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers import consent_controller
from swx_core.database.db import SessionDep
from swx_core.models.consent import ConsentSummary, ConsentTypePublic, UserConsentCreate, UserConsentPublic

router = APIRouter(prefix="/user/consent", tags=["user-consent"])


@router.get("/", response_model=ConsentSummary)
async def get_consent_summary(session: SessionDep, current_user: UserDep) -> ConsentSummary:
    return await consent_controller.get_consent_summary_controller(session, current_user.id)


@router.get("/types", response_model=list[ConsentTypePublic])
async def list_consent_types(session: SessionDep, current_user: UserDep) -> list[ConsentTypePublic]:
    return await consent_controller.list_consent_types_controller(session)


@router.post("/grant", response_model=UserConsentPublic, status_code=201)
async def grant_consent(session: SessionDep, body: UserConsentCreate, current_user: UserDep, request: Request) -> UserConsentPublic:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await consent_controller.grant_consent_controller(session, current_user.id, body, client_ip, user_agent)


@router.post("/withdraw/{consent_type_key}", response_model=UserConsentPublic)
async def withdraw_consent(session: SessionDep, consent_type_key: str, current_user: UserDep, request: Request) -> UserConsentPublic:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await consent_controller.withdraw_consent_controller(session, current_user.id, consent_type_key, client_ip, user_agent)
