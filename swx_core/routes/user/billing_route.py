from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import Field
from sqlmodel import SQLModel

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers import (
    billing_controller,
    quota_controller,
    subscription_controller,
)
from swx_core.database.db import SessionDep
from swx_core.models.billing import SubscriptionPublic
from swx_core.models.currency import WalletPublic
from swx_core.models.ledger import LedgerEntryPublic
from swx_core.services.billing.usage_window_service import QuotaStatus


class PaymentInitializeRequest(SQLModel):
    provider: str
    amount_nano: int
    currency: str
    reference: str
    callback_url: str
    email: str | None = None
    extra_data: dict[str, object] = Field(default_factory=dict)
    phone_number: str | None = None


class PaymentVerifyRequest(SQLModel):
    provider: str
    reference: str


class PaymentConfirmRequest(SQLModel):
    provider: str
    reference: str


class PaymentInitializePlanRequest(SQLModel):
    plan_key: str
    provider: str
    callback_url: str
    currency: str | None = None


class PaymentInitializePackRequest(SQLModel):
    provider: str
    callback_url: str


router = APIRouter(prefix="/user/billing", tags=["user-billing"])


# Wallet: read-only (mutations via admin adjustment or verified payment only)


@router.get("/wallets", response_model=list[WalletPublic])
async def list_wallets(session: SessionDep, current_user: UserDep) -> list[WalletPublic]:
    return await billing_controller.list_wallets_controller(session, current_user.id)


@router.get("/wallets/{currency}/balance", response_model=WalletPublic)
async def get_wallet_balance(session: SessionDep, currency: str, current_user: UserDep) -> WalletPublic:
    return await billing_controller.wallet_balance_controller(session, current_user.id, currency)


# Payments


@router.post("/payments/initialize", response_model=dict[str, object])
async def initialize_payment(body: PaymentInitializeRequest, current_user: UserDep) -> dict[str, object]:
    email = body.email or current_user.email
    return await billing_controller.initialize_payment_controller(body.provider, body.amount_nano, body.currency, email, body.reference, body.callback_url, metadata=body.extra_data, phone_number=body.phone_number)


@router.post("/payments/verify", response_model=dict[str, object])
async def verify_payment(body: PaymentVerifyRequest, current_user: UserDep) -> dict[str, object]:
    return await billing_controller.verify_payment_controller(body.provider, body.reference)


@router.post("/payments/confirm", response_model=dict[str, object])
async def confirm_payment_endpoint(body: PaymentConfirmRequest, session: SessionDep, current_user: UserDep) -> dict[str, object]:
    """Verify a payment and apply the result (SWX-021).

    Bridges the gap between "provider says paid" and "account reflects it".
    Idempotent with the webhook via shared Redis dedup key — so if both
    the webhook and /confirm fire, the user is not double-charged.
    """
    redis_client = None
    try:
        from swx_core.container.container import get_container
        container = get_container()
        if container.bound("redis.client"):
            redis_client = container.make("redis.client")
    except Exception:
        pass

    return await billing_controller.confirm_payment_controller(
        session, current_user.id, body.provider, body.reference, redis_client,
    )


@router.get("/plans", response_model=list[dict[str, object]])
async def list_public_plans() -> list[dict[str, object]]:
    return await billing_controller.list_public_plans_controller()


@router.post("/payments/initialize/plan", response_model=dict[str, object])
async def initialize_payment_for_plan(body: PaymentInitializePlanRequest, current_user: UserDep) -> dict[str, object]:
    return await billing_controller.initialize_payment_for_plan_controller(
        plan_key=body.plan_key,
        provider=body.provider,
        callback_url=body.callback_url,
        email=current_user.email,
        currency=body.currency,
    )


@router.get("/credit-packs", response_model=list[dict[str, object]])
async def list_credit_packs() -> list[dict[str, object]]:
    return await billing_controller.list_credit_packs_controller()


@router.post("/credit-packs/{pack_key}/purchase", response_model=dict[str, object])
async def purchase_credit_pack(pack_key: str, body: PaymentInitializePackRequest, current_user: UserDep) -> dict[str, object]:
    return await billing_controller.initialize_payment_for_pack_controller(
        pack_key=pack_key,
        provider=body.provider,
        callback_url=body.callback_url,
        email=current_user.email,
    )


# Subscriptions


class CreateSubscriptionRequest(SQLModel):
    plan_key: str


@router.get("/subscriptions/current", response_model=SubscriptionPublic)
async def get_current_subscription(session: SessionDep, current_user: UserDep) -> SubscriptionPublic:
    return await subscription_controller.get_current_subscription_controller(session, current_user.id)


@router.get("/subscriptions", response_model=list[SubscriptionPublic])
async def list_subscriptions(session: SessionDep, current_user: UserDep, skip: int = 0, limit: int = 100) -> list[SubscriptionPublic]:
    return await subscription_controller.list_subscriptions_controller(session, current_user.id, skip, limit)


@router.post("/subscriptions", response_model=SubscriptionPublic, status_code=201)
async def create_subscription(session: SessionDep, body: CreateSubscriptionRequest, current_user: UserDep) -> SubscriptionPublic:
    return await subscription_controller.create_subscription_controller(session, current_user.id, body.plan_key)


@router.post("/subscriptions/{subscription_id}/cancel", response_model=SubscriptionPublic)
async def cancel_subscription(session: SessionDep, subscription_id: UUID, current_user: UserDep, immediate: bool = False) -> SubscriptionPublic:
    return await subscription_controller.cancel_subscription_controller(session, current_user.id, subscription_id, immediate)


# Transactions & quota


@router.get("/transactions", response_model=list[LedgerEntryPublic])
async def list_transactions(
    session: SessionDep,
    current_user: UserDep,
    entry_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[LedgerEntryPublic]:
    return await billing_controller.list_transactions_controller(
        session, current_user.id, entry_type, date_from, date_to, skip, limit
    )


@router.get("/quota/status", response_model=QuotaStatus)
async def get_quota_status(session: SessionDep, current_user: UserDep) -> QuotaStatus:
    return await quota_controller.get_quota_status_controller(session, current_user.id)


@router.post("/quota/reset-window", response_model=QuotaStatus)
async def reset_quota_window(session: SessionDep, current_user: UserDep) -> QuotaStatus:
    return await quota_controller.reset_quota_window_controller(session, current_user.id)
