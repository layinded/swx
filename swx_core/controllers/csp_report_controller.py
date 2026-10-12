"""CSP violation report controller.

Receives CSP violation reports from browsers, logs them as audit events,
and returns a minimal acknowledgment.
"""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.services.audit_logger import AuditLogger, ActorType, AuditOutcome, AuditAction


async def csp_report_controller(session: AsyncSession, report: dict, request: Request) -> dict:
    source_ip = request.client.host if request.client else "unknown"
    csp_report = report.get("csp-report", report)
    violated_directive = csp_report.get("violated-directive", "unknown")
    document_uri = csp_report.get("document-uri", "unknown")

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.SECURITY_CSP_VIOLATION,
        actor_type=ActorType.SYSTEM,
        resource_type="csp_report",
        outcome=AuditOutcome.FAILURE,
        context={
            "violated_directive": violated_directive,
            "document_uri": document_uri,
            "source_ip": source_ip,
        },
        request=request,
    )

    return {"status": "received"}