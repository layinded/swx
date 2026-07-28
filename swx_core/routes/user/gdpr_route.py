from uuid import UUID

from fastapi import APIRouter

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers import compliance_audit_controller
from swx_core.database.db import SessionDep
from swx_core.models.compliance_audit import DataSubjectRequestCreate, DataSubjectRequestPublic

router = APIRouter(prefix="/user/gdpr", tags=["user-gdpr"])


@router.get("/requests", response_model=list[DataSubjectRequestPublic])
async def list_requests(session: SessionDep, current_user: UserDep) -> list[DataSubjectRequestPublic]:
    return await compliance_audit_controller.list_data_subject_requests_controller(session, current_user.id)


@router.post("/requests", response_model=DataSubjectRequestPublic, status_code=201)
async def create_request(session: SessionDep, body: DataSubjectRequestCreate, current_user: UserDep) -> DataSubjectRequestPublic:
    return await compliance_audit_controller.create_data_subject_request_controller(session, current_user.id, body)


@router.post("/requests/{request_id}/verify", response_model=DataSubjectRequestPublic)
async def verify_request(session: SessionDep, request_id: UUID, token: str, current_user: UserDep) -> DataSubjectRequestPublic:
    return await compliance_audit_controller.verify_data_subject_request_controller(session, request_id, token, current_user.id)


@router.post("/requests/{request_id}/cancel", response_model=DataSubjectRequestPublic)
async def cancel_request(session: SessionDep, request_id: UUID, current_user: UserDep) -> DataSubjectRequestPublic:
    return await compliance_audit_controller.cancel_data_subject_request_controller(session, request_id, current_user.id)


@router.get("/export")
async def export_own_data(session: SessionDep, current_user: UserDep) -> dict[str, object]:
    return await compliance_audit_controller.export_own_data_controller(session, current_user.id)
