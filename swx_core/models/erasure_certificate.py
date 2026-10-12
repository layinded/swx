# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text, func
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class ErasureCertificateBase(Base):
    user_id: uuid.UUID = Field(foreign_key="swx_users.id", index=True)
    request_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="swx_data_subject_request.id",
        description="Linked data subject request, if any",
    )
    erasure_type: str = Field(
        max_length=20,
        description="anonymize or delete",
    )
    status: str = Field(
        default="pending",
        max_length=20,
        description="pending, in_progress, completed, failed",
    )
    tables_affected: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="JSON array of table names that were erased/anonymized",
    )
    certificate_data: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="JSON object with per-table erasure details",
    )
    error_message: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class ErasureCertificate(ErasureCertificateBase, table=True):
    __tablename__ = "swx_erasure_certificates"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


class ErasureCertificateCreate(SQLModel):
    user_id: uuid.UUID
    request_id: uuid.UUID | None = None
    erasure_type: str = "anonymize"


class ErasureCertificatePublic(ErasureCertificateBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}