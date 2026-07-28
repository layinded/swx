# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LLMUsageLog(Base, table=True):
    __tablename__ = "swx_llm_usage_log"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        Index("idx_swx_llm_usage_account_created", "account_id", "created_at"),
        {"extend_existing": True},
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider_config_id: uuid.UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_llm_provider_config.id"), nullable=True))
    provider: str = Field(sa_column=Column(String(50), nullable=False))
    model_name: str = Field(sa_column=Column(String(100), nullable=False))
    phase: str | None = Field(default=None, sa_column=Column(String(50), nullable=True))
    prompt_tokens: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    completion_tokens: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    total_tokens: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    cost_usd: float = Field(default=0.0, sa_column=Column(Float, nullable=False, server_default="0"))
    latency_ms: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    success: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true"))
    error_message: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now()))
    account_id: uuid.UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), nullable=True, index=True))


class LLMUsageLogPublic(SQLModel):
    id: uuid.UUID
    provider_config_id: uuid.UUID | None = None
    provider: str
    model_name: str
    phase: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    success: bool = True
    error_message: str | None = None
    created_at: datetime
    account_id: uuid.UUID | None = None

    class Config:
        from_attributes: bool = True
