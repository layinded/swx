from uuid import UUID

from fastapi import APIRouter, Query

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers import compliance_audit_controller, gdpr_controller
from swx_core.database.db import SessionDep
from swx_core.models.compliance_audit import (
    DataSubjectRequestCreate,
    DataSubjectRequestPublic,
)
from swx_core.models.erasure_certificate import ErasureCertificatePublic

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


@router.post("/export/zip")
async def export_zip(session: SessionDep, current_user: UserDep):
    return await gdpr_controller.export_zip_controller(session, current_user.id)


@router.post("/deletion")
async def request_gdpr_deletion(session: SessionDep, current_user: UserDep) -> dict[str, object]:
    return await gdpr_controller.request_deletion_controller(session, current_user.id)


@router.post("/deletion/cancel")
async def cancel_gdpr_deletion(session: SessionDep, current_user: UserDep) -> dict[str, object]:
    return await gdpr_controller.cancel_deletion_controller(session, current_user.id)


@router.get("/erasure-certificates", response_model=list[ErasureCertificatePublic])
async def list_erasure_certificates(
    session: SessionDep,
    current_user: UserDep,
    status: str | None = Query(default=None),
) -> list[ErasureCertificatePublic]:
    return await gdpr_controller.list_erasure_certificates_controller(
        session, user_id=current_user.id, status=status,
    )


@router.get("/erasure-certificates/{certificate_id}", response_model=ErasureCertificatePublic)
async def get_erasure_certificate(
    session: SessionDep,
    current_user: UserDep,
    certificate_id: UUID,
) -> ErasureCertificatePublic:
    return await gdpr_controller.get_erasure_certificate_controller(session, certificate_id)