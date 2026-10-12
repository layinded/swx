# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Float, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

class CurrencyStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"

class CurrencyBase(SQLModel):
    code: str = Field(max_length=3)
    name: str = Field(max_length=100)
    symbol: str = Field(max_length=10)
    decimals: int = 2
    is_base: bool = False
    status: str = Field(default=CurrencyStatus.ACTIVE.value, max_length=20)
    minimum_amount: int = 100
    supported_providers: list[str] = Field(default_factory=list)
    extra_data: dict[str, object] = Field(default_factory=dict, serialization_alias="metadata")

class Currency(CurrencyBase, Base, table=True):
    __tablename__ = "swx_currency"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (Index("idx_swx_currency_status_base", "status", "is_base"), {"extend_existing": True})
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(sa_column=Column(String(3), nullable=False, unique=True, index=True))
    supported_providers: list[str] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")))
    extra_data: dict[str, object] = Field(default_factory=dict, sa_column=Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))

class CurrencyCreate(CurrencyBase):
    pass

class CurrencyUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=100)
    symbol: str | None = Field(default=None, max_length=10)
    decimals: int | None = None
    is_base: bool | None = None
    status: str | None = Field(default=None, max_length=20)
    minimum_amount: int | None = None
    supported_providers: list[str] | None = None
    extra_data: dict[str, object] | None = Field(default=None, serialization_alias="metadata")

class CurrencyPublic(CurrencyBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True

class ExchangeRateBase(SQLModel):
    base_currency: str = Field(max_length=3)
    quote_currency: str = Field(max_length=3)
    rate: float
    source: str | None = Field(default=None, max_length=50)

class ExchangeRate(ExchangeRateBase, Base, table=True):
    __tablename__ = "swx_exchange_rate"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (Index("idx_swx_exchange_rate_pair_fetched", "base_currency", "quote_currency", "fetched_at"), {"extend_existing": True})
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    base_currency: str = Field(sa_column=Column(String(3), nullable=False, index=True))
    quote_currency: str = Field(sa_column=Column(String(3), nullable=False, index=True))
    rate: float = Field(sa_column=Column(Float, nullable=False))
    fetched_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))

class ExchangeRatePublic(ExchangeRateBase):
    id: uuid.UUID
    fetched_at: datetime
    created_at: datetime

    class Config:
        from_attributes: bool = True

class WalletBase(SQLModel):
    account_id: uuid.UUID
    currency: str = Field(max_length=3)
    balance: int = 0
    is_active: bool = True
    extra_data: dict[str, object] = Field(default_factory=dict, serialization_alias="metadata")

class Wallet(WalletBase, Base, table=True):
    __tablename__ = "swx_wallet"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (Index("idx_swx_wallet_account_currency", "account_id", "currency"), {"extend_existing": True})
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True))
    currency: str = Field(sa_column=Column(String(3), nullable=False))
    extra_data: dict[str, object] = Field(default_factory=dict, sa_column=Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))

class WalletPublic(WalletBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True

class WalletTransactionRequest(SQLModel):
    amount_nano: int = Field(gt=0)
    reference: str = Field(max_length=255)
    idempotency_key: str = Field(max_length=255)

class ConvertRequest(SQLModel):
    from_currency: str = Field(max_length=3)
    to_currency: str = Field(max_length=3)
    amount_nano: int = Field(gt=0)
    idempotency_key: str = Field(max_length=255)

class ConvertResponse(SQLModel):
    from_wallet: WalletPublic
    to_wallet: WalletPublic
    converted_amount_nano: int
    rate: float

CURRENCY_DEFAULTS: list[dict[str, object]] = [
    {"code": "USD", "name": "US Dollar", "symbol": "$", "decimals": 2, "is_base": True, "supported_providers": ["paystack", "flutterwave"]},
    {"code": "NGN", "name": "Nigerian Naira", "symbol": "₦", "decimals": 2, "is_base": False, "supported_providers": ["paystack", "flutterwave"]},
    {"code": "KES", "name": "Kenyan Shilling", "symbol": "KSh", "decimals": 2, "is_base": False, "supported_providers": ["flutterwave", "mpesa"]},
    {"code": "ZAR", "name": "South African Rand", "symbol": "R", "decimals": 2, "is_base": False, "supported_providers": ["paystack", "flutterwave"]},
    {"code": "GHS", "name": "Ghanaian Cedi", "symbol": "₵", "decimals": 2, "is_base": False, "supported_providers": ["paystack", "flutterwave"]},
]

TAX_RATES: dict[str, float] = {"NG": 7.5, "KE": 16.0, "ZA": 15.0, "GH": 15.0, "US": 0.0, "GB": 20.0}
