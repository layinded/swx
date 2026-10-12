from uuid import UUID

from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.erasure_certificate import ErasureCertificatePublic
from swx_core.services.compliance.erasure_service import (
    get_erasure_certificate,
    list_erasure_certificates,
)


async def export_zip_controller(session: AsyncSession, user_id: UUID) -> Response:
    from swx_core.services.data_transfer.gdpr_service import export_user_data_zip
    zip_bytes = await export_user_data_zip(session, user_id)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=gdpr_export_{user_id}.zip"},
    )


async def request_deletion_controller(session: AsyncSession, user_id: UUID) -> dict[str, object]:
    from swx_core.services.data_transfer.gdpr_service import request_deletion
    return await request_deletion(session, user_id)


async def cancel_deletion_controller(session: AsyncSession, user_id: UUID) -> dict[str, object]:
    from swx_core.services.data_transfer.gdpr_service import cancel_deletion
    return await cancel_deletion(session, user_id)


async def get_erasure_certificate_controller(session: AsyncSession, certificate_id: UUID) -> ErasureCertificatePublic:
    cert = await get_erasure_certificate(session, certificate_id)
    if cert is None:
        raise HTTPException(status_code=404, detail="Erasure certificate not found")
    return cert


async def list_erasure_certificates_controller(
    session: AsyncSession,
    user_id: UUID | None = None,
    status: str | None = None,
) -> list[ErasureCertificatePublic]:
    return await list_erasure_certificates(session, user_id=user_id, status=status)