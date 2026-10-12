from fastapi import APIRouter, Request

from swx_core.controllers import csp_report_controller
from swx_core.database.db import SessionDep

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post("/csp-report", status_code=204)
async def report_csp_violation(session: SessionDep, request: Request) -> None:
    """Receive CSP violation reports from browsers and log as audit events."""
    try:
        report = await request.json()
    except Exception:
        return

    await csp_report_controller.csp_report_controller(session, report, request)