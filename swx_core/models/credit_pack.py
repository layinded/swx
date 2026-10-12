# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class CreditPackBase(SQLModel):
    key: str = Field(max_length=100)
    name: str = Field(max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    tokens: int = Field(gt=0)
    amount: int = Field(gt=0)
    currency: str = Field(default="usd", max_length=3)
    is_active: bool = Field(default=True)
    is_public: bool = Field(default=True)


class CreditPack(CreditPackBase, Base, table=True):
    __tablename__ = "swx_credit_pack"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(sa_column=Column(String(100), nullable=False, unique=True, index=True))
    name: str = Field(sa_column=Column(String(200), nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column(String(500), nullable=True))
    tokens: int = Field(sa_column=Column(Integer, nullable=False))
    amount: int = Field(sa_column=Column(Integer, nullable=False))
    currency: str = Field(default="usd", sa_column=Column(String(3), nullable=False, server_default="'usd'"))
    is_active: bool = Field(default=True, index=True)
    is_public: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    )


class CreditPackPublic(CreditPackBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True
