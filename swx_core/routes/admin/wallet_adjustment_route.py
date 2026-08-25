from uuid import UUID

from fastapi import APIRouter, status
from pydantic import Field
from sqlmodel import SQLModel

from swx_core.auth.admin.dependencies import AdminUserDep
from swx_core.controllers import wallet_adjustment_controller
from swx_core.database.db import SessionDep

router = APIRouter(prefix="/admin/billing/adjustments", tags=["admin-billing"])


class AdjustmentProposeRequest(SQLModel):
    account_id: UUID
    currency: str = Field(max_length=3)
    amount_nano: int = Field(gt=0)
    adjustment_type: str
    reason: str | None = None


@router.post("/", status_code=status.HTTP_201_CREATED)
async def propose_adjustment(session: SessionDep, body: AdjustmentProposeRequest, admin: AdminUserDep) -> dict[str, object]:
    return await wallet_adjustment_controller.propose_adjustment_controller(
        session, body.account_id, body.currency, body.amount_nano, body.adjustment_type, admin.id, body.reason
    )


@router.post("/{request_id}/approve")
async def approve_adjustment(session: SessionDep, request_id: UUID, admin: AdminUserDep) -> dict[str, object]:
    return await wallet_adjustment_controller.approve_adjustment_controller(session, request_id, admin.id)


@router.post("/{request_id}/reject")
async def reject_adjustment(session: SessionDep, request_id: UUID, admin: AdminUserDep) -> dict[str, object]:
    return await wallet_adjustment_controller.reject_adjustment_controller(session, request_id, admin.id)


@router.get("/pending")
async def list_pending_adjustments(session: SessionDep, admin: AdminUserDep) -> list[dict[str, object]]:
    return await wallet_adjustment_controller.list_pending_adjustments_controller(session)