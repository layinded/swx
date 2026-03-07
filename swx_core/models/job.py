"""
Job Model
---------
Database model for background jobs and task orchestration.

Jobs are idempotent, retryable, and auditable.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from enum import Enum
from sqlalchemy import Column, DateTime, text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base


class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Predefined job types."""
    # Billing jobs
    BILLING_SYNC = "billing.sync"
    BILLING_WEBHOOK = "billing.webhook"
    SUBSCRIPTION_RENEWAL = "billing.subscription.renewal"
    
    # Alert jobs
    ALERT_SEND = "alert.send"
    ALERT_AGGREGATE = "alert.aggregate"
    
    # Audit jobs
    AUDIT_AGGREGATE = "audit.aggregate"
    AUDIT_CLEANUP = "audit.cleanup"
    
    # System jobs
    CACHE_REFRESH = "system.cache.refresh"
    DATA_EXPORT = "system.data.export"
    
    # Generic
    GENERIC = "generic"


class JobBase(Base):
    """Base model for job fields."""
    job_type: str = Field(index=True, max_length=255)
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    )
    status: JobStatus = Field(default=JobStatus.PENDING, index=True)
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=3)
    scheduled_at: Optional[datetime] = Field(default=None, index=True)
    locked_at: Optional[datetime] = Field(default=None)
    locked_by: Optional[str] = Field(default=None, max_length=255)  # Worker identifier
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    last_error: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB)
    )
    priority: int = Field(default=100, index=True)  # Lower = higher priority
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    )


class Job(JobBase, table=True):
    """
    Database model representing a background job.
    
    Jobs are idempotent and retryable. They track execution state,
    attempts, and errors for observability.
    """
    __tablename__ = "job"
    __table_args__ = (
        Index("idx_job_status_scheduled", "status", "scheduled_at"),
        Index("idx_job_type_status", "job_type", "status"),
        {"extend_existing": True}
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )


class JobCreate(SQLModel):
    """Schema for creating a new job."""
    job_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None
    max_attempts: int = Field(default=3)
    priority: int = Field(default=100)
    tags: list[str] = Field(default_factory=list)


class JobUpdate(SQLModel):
    """Schema for updating a job."""
    status: Optional[JobStatus] = None
    attempts: Optional[int] = None
    last_error: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    tags: Optional[list[str]] = None


class JobPublic(SQLModel):
    """Public schema for job responses."""
    id: uuid.UUID
    job_type: str
    payload: Dict[str, Any]
    status: JobStatus
    attempts: int
    max_attempts: int
    scheduled_at: Optional[datetime]
    locked_at: Optional[datetime]
    locked_by: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    last_error: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    priority: int
    tags: list[str]
    created_at: datetime
    updated_at: datetime
