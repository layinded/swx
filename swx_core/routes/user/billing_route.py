from fastapi import APIRouter
from pydantic import Field
from sqlmodel import SQLModel

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers import billing_controller
from swx_core.database.db import SessionDep
from swx_core.models.currency import ConvertRequest, ConvertResponse, WalletPublic, WalletTransactionRequest


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


router = APIRouter(prefix="/user/billing", tags=["user-billing"])


@router.get("/wallets", response_model=list[WalletPublic])
async def list_wallets(session: SessionDep, current_user: UserDep) -> list[WalletPublic]:
    return await billing_controller.list_wallets_controller(session, current_user.id)


@router.get("/wallets/{currency}/balance", response_model=WalletPublic)
async def get_wallet_balance(session: SessionDep, currency: str, current_user: UserDep) -> WalletPublic:
    return await billing_controller.wallet_balance_controller(session, current_user.id, currency)


@router.post("/wallets/{currency}/credit", response_model=WalletPublic)
async def credit_wallet(session: SessionDep, currency: str, body: WalletTransactionRequest, current_user: UserDep) -> WalletPublic:
    return await billing_controller.credit_wallet_controller(session, current_user.id, currency, body.amount_nano, body.reference, body.idempotency_key)


@router.post("/convert", response_model=ConvertResponse)
async def convert_wallets(session: SessionDep, body: ConvertRequest, current_user: UserDep) -> ConvertResponse:
    return await billing_controller.convert_wallet_controller(session, current_user.id, body.from_currency, body.to_currency, body.amount_nano, body.idempotency_key)


@router.post("/payments/initialize", response_model=dict[str, object])
async def initialize_payment(body: PaymentInitializeRequest, current_user: UserDep) -> dict[str, object]:
    email = body.email or current_user.email
    return await billing_controller.initialize_payment_controller(body.provider, body.amount_nano, body.currency, email, body.reference, body.callback_url, metadata=body.extra_data, phone_number=body.phone_number)


@router.post("/payments/verify", response_model=dict[str, object])
async def verify_payment(body: PaymentVerifyRequest) -> dict[str, object]:
    return await billing_controller.verify_payment_controller(body.provider, body.reference)
