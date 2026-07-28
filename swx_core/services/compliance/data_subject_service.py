import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import COMPLIANCE_DATA_SUBJECT_REQUEST_EXPIRY_DAYS
from swx_core.events.dispatcher import event_bus
from swx_core.models.compliance_audit import DataSubjectRequestCreate, DataSubjectRequestPublic
from swx_core.repositories import compliance_audit_repository
from swx_core.services.job.job_dispatcher import enqueue_job


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_data_subject_request(session: AsyncSession, user_id: UUID, data: DataSubjectRequestCreate) -> DataSubjectRequestPublic:
    now = _utc_now()
    request = await compliance_audit_repository.create_data_subject_request(session, {
        "user_id": user_id,
        "request_type": data.request_type,
        "status": "pending",
        "description": data.description,
        "requested_at": now,
        "expires_at": now + timedelta(days=COMPLIANCE_DATA_SUBJECT_REQUEST_EXPIRY_DAYS),
        "verification_token": secrets.token_urlsafe(24),
        "verified": False,
    })
    await event_bus.dispatch("compliance.request_created", payload={"request_id": str(request.id), "user_id": str(user_id), "request_type": request.request_type})
    return DataSubjectRequestPublic.model_validate(request)


async def verify_request(session: AsyncSession, request_id: UUID, verification_token: str, user_id: UUID | None = None) -> DataSubjectRequestPublic:
    request = await compliance_audit_repository.get_data_subject_request(session, request_id)
    if request is None or request.verification_token != verification_token or (user_id and request.user_id != user_id):
        raise HTTPException(status_code=404, detail="Data subject request not found")
    updated = await compliance_audit_repository.update_data_subject_request(session, request_id, {"verified": True, "status": "processing"})
    if updated is None:
        raise HTTPException(status_code=404, detail="Data subject request not found")
    await event_bus.dispatch("compliance.request_verified", payload={"request_id": str(updated.id), "user_id": str(updated.user_id)})
    return DataSubjectRequestPublic.model_validate(updated)


async def process_data_subject_request(session: AsyncSession, request_id: UUID, admin_notes: str | None = None) -> dict[str, Any]:
    request = await compliance_audit_repository.get_data_subject_request(session, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Data subject request not found")
    if not request.verified:
        raise HTTPException(status_code=400, detail="Request must be verified before processing")
    payload: dict[str, Any] = {"request_id": str(request.id), "user_id": str(request.user_id), "request_type": request.request_type}
    request_type = request.request_type
    if request_type in {"access", "portability"}:
        payload["export"] = await compliance_audit_repository.export_user_data(session, request.user_id)
        await event_bus.dispatch("compliance.data_exported", payload=payload)
    elif request_type == "deletion":
        await enqueue_job("compliance.data_subject.delete", {"request_id": str(request.id), "user_id": str(request.user_id)}, session=session, tags=["compliance", "gdpr"])
        await event_bus.dispatch("compliance.data_deleted", payload=payload)
    status = "completed"
    updated = await compliance_audit_repository.update_data_subject_request(session, request_id, {"status": status, "completed_at": _utc_now(), "admin_notes": admin_notes})
    await event_bus.dispatch("compliance.request_processed", payload={**payload, "status": status})
    return {"request": DataSubjectRequestPublic.model_validate(updated) if updated else None, "payload": payload}


async def get_data_subject_requests(session: AsyncSession, user_id: UUID | None = None) -> list[DataSubjectRequestPublic]:
    return [DataSubjectRequestPublic.model_validate(item) for item in await compliance_audit_repository.list_data_subject_requests(session, user_id=user_id)]


async def cancel_data_subject_request(session: AsyncSession, request_id: UUID, user_id: UUID) -> DataSubjectRequestPublic:
    request = await compliance_audit_repository.get_data_subject_request(session, request_id)
    if request is None or request.user_id != user_id:
        raise HTTPException(status_code=404, detail="Data subject request not found")
    if request.status not in {"pending", "processing"}:
        raise HTTPException(status_code=400, detail="Only pending or processing requests can be cancelled")
    updated = await compliance_audit_repository.update_data_subject_request(session, request_id, {"status": "rejected", "admin_notes": "Cancelled by user"})
    if updated is None:
        raise HTTPException(status_code=404, detail="Data subject request not found")
    await event_bus.dispatch("compliance.request_cancelled", payload={"request_id": str(updated.id), "user_id": str(updated.user_id)})
    return DataSubjectRequestPublic.model_validate(updated)


async def export_own_data(session: AsyncSession, user_id: UUID) -> dict[str, Any]:
    payload = await compliance_audit_repository.export_user_data(session, user_id)
    await event_bus.dispatch("compliance.data_exported", payload={"user_id": str(user_id), "source": "self_service"})
    return payload
