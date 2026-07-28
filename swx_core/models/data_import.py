# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DataImportBase(Base):
    user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False, index=True))
    import_type: str = Field(default="full", max_length=50)
    format: str = Field(default="json", max_length=20)
    status: str = Field(default="pending", max_length=20)
    file_path: str | None = Field(default=None, max_length=500)
    file_size: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    record_count: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    records_succeeded: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    records_failed: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    error_message: str | None = Field(default=None, max_length=1000)
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=Column("metadata", JSONB, nullable=True))


class DataImport(DataImportBase, table=True):
    __tablename__ = "swx_data_import"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now()))


class DataImportCreate(SQLModel):
    import_type: str = Field(default="full", max_length=50)
    format: str = Field(default="json", max_length=20)
    file_path: str | None = None
    file_size: int | None = None
    metadata_: dict[str, Any] | None = None


class DataImportUpdate(SQLModel):
    status: str | None = None
    file_path: str | None = None
    file_size: int | None = None
    record_count: int | None = None
    records_succeeded: int | None = None
    records_failed: int | None = None
    error_message: str | None = None
    metadata_: dict[str, Any] | None = None


class DataImportPublic(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    import_type: str
    format: str
    status: str
    file_path: str | None = None
    file_size: int | None = None
    record_count: int | None = None
    records_succeeded: int | None = None
    records_failed: int | None = None
    error_message: str | None = None
    metadata_: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}