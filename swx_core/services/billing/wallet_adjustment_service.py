from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.events.dispatcher import event_bus
from swx_core.middleware.logging_middleware import logger
from swx_core.models.wallet_adjustment import (
    WalletAdjustmentRequest,
    WalletAdjustmentStatus,
)
from swx_core.services.billing import wallet_service
from swx_core.utils.errors import ConflictError, NotFoundError
from swx_core.utils.time import utc_now


async def propose(
    session: AsyncSession,
    account_id: UUID,
    currency: str,
    amount_nano: int,
    adjustment_type: str,
    proposed_by: UUID,
    reason: str | None = None,
) -> WalletAdjustmentRequest:
    if adjustment_type not in ("credit", "debit"):
        raise ConflictError("adjustment_type must be 'credit' or 'debit'")
    request = WalletAdjustmentRequest(
        account_id=account_id,
        currency=currency,
        amount_nano=amount_nano,
        adjustment_type=adjustment_type,
        reason=reason,
        proposed_by=proposed_by,
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    logger.info("Wallet adjustment proposed: %s %d %s for account %s by %s", adjustment_type, amount_nano, currency, account_id, proposed_by)
    await event_bus.dispatch("wallet_adjustment.proposed", payload={"request_id": str(request.id), "account_id": str(account_id)})
    return request


async def approve(session: AsyncSession, request_id: UUID, approver_id: UUID) -> WalletAdjustmentRequest:
    request = await session.get(WalletAdjustmentRequest, request_id)
    if request is None:
        raise NotFoundError("Wallet adjustment", str(request_id))
    if request.status != WalletAdjustmentStatus.PROPOSED:
        raise ConflictError("Adjustment is not in proposed state")
    if request.proposed_by == approver_id:
        raise ConflictError("Approver cannot be the same as proposer")

    request.status = WalletAdjustmentStatus.APPROVED
    request.approved_by = approver_id
    request.approved_at = utc_now()
    session.add(request)
    await session.commit()
    await session.refresh(request)
    logger.info("Wallet adjustment approved: %s by %s", request_id, approver_id)
    await event_bus.dispatch("wallet_adjustment.approved", payload={"request_id": str(request_id), "approver_id": str(approver_id)})

    await _execute(session, request)
    return request


async def reject(session: AsyncSession, request_id: UUID, rejecter_id: UUID) -> WalletAdjustmentRequest:
    request = await session.get(WalletAdjustmentRequest, request_id)
    if request is None:
        raise NotFoundError("Wallet adjustment", str(request_id))
    if request.status != WalletAdjustmentStatus.PROPOSED:
        raise ConflictError("Adjustment is not in proposed state")

    request.status = WalletAdjustmentStatus.REJECTED
    request.approved_by = rejecter_id
    request.approved_at = utc_now()
    session.add(request)
    await session.commit()
    await session.refresh(request)
    logger.info("Wallet adjustment rejected: %s by %s", request_id, rejecter_id)
    await event_bus.dispatch("wallet_adjustment.rejected", payload={"request_id": str(request_id)})
    return request


async def list_pending(session: AsyncSession) -> list[WalletAdjustmentRequest]:
    stmt = select(WalletAdjustmentRequest).where(
        WalletAdjustmentRequest.status == WalletAdjustmentStatus.PROPOSED  # pyright: ignore[reportArgumentType]
    ).order_by(WalletAdjustmentRequest.proposed_at.desc())  # pyright: ignore[reportArgumentType]
    return list((await session.execute(stmt)).scalars().all())


async def _execute(session: AsyncSession, request: WalletAdjustmentRequest) -> None:
    reference = f"adjustment-{request.id}"
    idempotency_key = f"adjustment-{request.id}"

    if request.adjustment_type == "credit":
        await wallet_service.credit_wallet(
            session, request.account_id, request.currency, request.amount_nano, reference, idempotency_key
        )
    else:
        await wallet_service.debit_wallet(
            session, request.account_id, request.currency, request.amount_nano, reference, idempotency_key
        )

    request.status = WalletAdjustmentStatus.EXECUTED
    request.executed_at = utc_now()
    session.add(request)
    await session.commit()
    logger.info("Wallet adjustment executed: %s", request.id)
    await event_bus.dispatch("wallet_adjustment.executed", payload={"request_id": str(request.id)})