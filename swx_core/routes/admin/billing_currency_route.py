from fastapi import APIRouter, Depends
from sqlmodel import SQLModel

from swx_core.auth.admin.dependencies import get_current_admin_user
from swx_core.controllers import billing_controller
from swx_core.database.db import SessionDep
from swx_core.models.currency import CurrencyCreate, CurrencyPublic, CurrencyUpdate, ExchangeRatePublic


class ExchangeRateRequest(SQLModel):
    base_currency: str
    quote_currency: str
    rate: float


router = APIRouter(prefix="/admin/billing", tags=["admin-billing"], dependencies=[Depends(get_current_admin_user)])


@router.post("/currencies", response_model=CurrencyPublic, status_code=201)
async def create_currency(session: SessionDep, body: CurrencyCreate) -> CurrencyPublic:
    return await billing_controller.create_currency_controller(session, body)


@router.get("/currencies", response_model=list[CurrencyPublic])
async def list_currencies(session: SessionDep, active_only: bool = False) -> list[CurrencyPublic]:
    return await billing_controller.list_currencies_controller(session, active_only)


@router.get("/currencies/{code}", response_model=CurrencyPublic)
async def get_currency(session: SessionDep, code: str) -> CurrencyPublic:
    return await billing_controller.get_currency_controller(session, code)


@router.put("/currencies/{code}", response_model=CurrencyPublic)
async def update_currency(session: SessionDep, code: str, body: CurrencyUpdate) -> CurrencyPublic:
    return await billing_controller.update_currency_controller(session, code, body)


@router.post("/exchange-rates", response_model=ExchangeRatePublic, status_code=201)
async def set_exchange_rate(session: SessionDep, body: ExchangeRateRequest) -> ExchangeRatePublic:
    return await billing_controller.set_exchange_rate_controller(session, body.base_currency, body.quote_currency, body.rate)


@router.get("/exchange-rates/{base}", response_model=list[ExchangeRatePublic])
async def get_exchange_rates(session: SessionDep, base: str) -> list[ExchangeRatePublic]:
    return await billing_controller.get_exchange_rates_controller(session, base)


@router.post("/exchange-rates/sync", response_model=dict[str, float])
async def sync_exchange_rates(session: SessionDep, base: str = "USD") -> dict[str, float]:
    return await billing_controller.sync_exchange_rates_controller(session, base)


@router.get("/tax/{jurisdiction}", response_model=dict[str, float | str])
async def get_tax_rate(jurisdiction: str) -> dict[str, float | str]:
    return billing_controller.get_tax_controller(jurisdiction)


@router.get("/tax", response_model=dict[str, float])
async def list_tax_rates() -> dict[str, float]:
    return billing_controller.list_tax_controller()
