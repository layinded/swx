# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EntryType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


class ReferenceType(str, Enum):
    TOPUP = "topup"
    USAGE = "usage"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    EXPIRY = "expiry"


class LedgerEntry(Base, table=True):
    __tablename__ = "swx_ledger_entry"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        Index("idx_swx_ledger_entry_account_created", "account_id", "created_at"),
        {"extend_existing": True},
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True))
    entry_type: str = Field(sa_column=Column(String(20), nullable=False))
    amount: int = Field(nullable=False)
    currency: str = Field(default="USD", sa_column=Column(String(3), nullable=False, server_default=text("'USD'")))
    reference_type: str | None = Field(default=None, sa_column=Column(String(50), nullable=True))
    reference_id: str | None = Field(default=None, max_length=255)
    idempotency_key: str | None = Field(default=None, max_length=255, index=True)
    description: str | None = Field(default=None, max_length=500)
    metadata_: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    )
    balance_after: int = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, server_default=func.now(), nullable=False))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=True))


class LedgerBalance(Base, table=True):
    __tablename__ = "swx_ledger_balance"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, unique=True, index=True))
    currency: str = Field(default="USD", sa_column=Column(String(3), nullable=False, server_default=text("'USD'")))
    balance: int = Field(nullable=False)
    last_entry_id: uuid.UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_ledger_entry.id"), nullable=True))
    updated_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False))


class IdempotencyRecord(Base, table=True):
    __tablename__ = "swx_idempotency_record"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(max_length=255, unique=True, index=True)
    account_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True))
    entry_id: uuid.UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_ledger_entry.id"), nullable=True))
    status: str = Field(default="completed", sa_column=Column(String(20), nullable=False, server_default=text("'completed'")))
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, server_default=func.now(), nullable=False))


class LedgerEntryBase(SQLModel):
    account_id: uuid.UUID
    entry_type: str = Field(max_length=20)
    amount: int
    currency: str = Field(default="USD", max_length=3)
    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: str | None = Field(default=None, max_length=255)
    idempotency_key: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    entry_metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict, serialization_alias="metadata")
    balance_after: int
    created_by: uuid.UUID | None = None


class LedgerEntryPublic(LedgerEntryBase):
    id: uuid.UUID
    created_at: datetime


class LedgerBalanceBase(SQLModel):
    account_id: uuid.UUID
    currency: str = Field(default="USD", max_length=3)
    balance: int
    last_entry_id: uuid.UUID | None = None


class LedgerBalancePublic(LedgerBalanceBase):
    id: uuid.UUID
    updated_at: datetime


class CreditRequest(SQLModel):
    account_id: uuid.UUID
    amount: int = Field(gt=0)
    currency: str = Field(default="USD", max_length=3)
    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: str | None = Field(default=None, max_length=255)
    idempotency_key: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=500)


class DebitRequest(CreditRequest):
    pass


class TransferRequest(SQLModel):
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: int = Field(gt=0)
    currency: str = Field(default="USD", max_length=3)
    idempotency_key: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=500)


class LedgerSummary(SQLModel):
    account_id: uuid.UUID
    currency: str = Field(default="USD", max_length=3)
    balance: int
    pending_count: int = 0
    entry_count: int = 0
