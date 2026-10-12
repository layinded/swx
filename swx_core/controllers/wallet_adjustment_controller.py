from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.services.billing import wallet_adjustment_service


async def propose_adjustment_controller(
    session: AsyncSession,
    account_id: UUID,
    currency: str,
    amount_nano: int,
    adjustment_type: str,
    proposed_by: UUID,
    reason: str | None = None,
) -> dict[str, object]:
    request = await wallet_adjustment_service.propose(
        session, account_id, currency, amount_nano, adjustment_type, proposed_by, reason
    )
    return {"id": str(request.id), "status": request.status}


async def approve_adjustment_controller(
    session: AsyncSession, request_id: UUID, approver_id: UUID
) -> dict[str, object]:
    request = await wallet_adjustment_service.approve(session, request_id, approver_id)
    return {"id": str(request.id), "status": request.status}


async def reject_adjustment_controller(
    session: AsyncSession, request_id: UUID, rejecter_id: UUID
) -> dict[str, object]:
    request = await wallet_adjustment_service.reject(session, request_id, rejecter_id)
    return {"id": str(request.id), "status": request.status}


async def list_pending_adjustments_controller(session: AsyncSession) -> list[dict[str, object]]:
    requests = await wallet_adjustment_service.list_pending(session)
    return [
        {
            "id": str(r.id),
            "account_id": str(r.account_id),
            "currency": r.currency,
            "amount_nano": r.amount_nano,
            "adjustment_type": r.adjustment_type,
            "reason": r.reason,
            "proposed_by": str(r.proposed_by),
            "proposed_at": r.proposed_at.isoformat(),
        }
        for r in requests
    ]