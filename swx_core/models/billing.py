"""
Billing Models
--------------
This module defines the database models for the billing and entitlement system.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, Relationship, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class BillingAccountType(str, Enum):
    USER = "user"
    TEAM = "team"
    ORGANIZATION = "organization"

class BillingInterval(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

BILLING_INTERVAL_DAYS: Dict[BillingInterval, int] = {
    BillingInterval.WEEKLY: 7,
    BillingInterval.MONTHLY: 30,
    BillingInterval.YEARLY: 365,
}

class FeatureType(str, Enum):
    BOOLEAN = "boolean"
    QUOTA = "quota"
    METERED = "metered"

class SubscriptionStatus(str, Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    EXPIRED = "expired"


ACTIVE_STATUSES: tuple[SubscriptionStatus, ...] = (
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.TRIALING,
    SubscriptionStatus.PAST_DUE,
)

TERMINAL_STATUSES: tuple[SubscriptionStatus, ...] = (
    SubscriptionStatus.CANCELED,
    SubscriptionStatus.EXPIRED,
)

__all__ = [
    "ACTIVE_STATUSES",
    "BILLING_INTERVAL_DAYS",
    "TERMINAL_STATUSES",
    "BillingAccount",
    "BillingAccountType",
    "BillingInterval",
    "FeatureType",
    "Plan",
    "Subscription",
    "SubscriptionPublic",
    "SubscriptionStatus",
    "UsageRecord",
]

class BillingAccount(Base, table=True):
    """
    Represents a billed entity (User, Team, or Org).
    """
    __tablename__ = "swx_billing_account"  # pyright: ignore[reportAssignmentType]
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_type: BillingAccountType = Field(index=True)
    owner_id: uuid.UUID = Field(index=True) # ID of User or Team
    
    stripe_customer_id: Optional[str] = Field(default=None, unique=True, index=True)
    billing_email: Optional[str] = Field(default=None)
    
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    )

    subscriptions: List["Subscription"] = Relationship(back_populates="account", sa_relationship_kwargs={"lazy": "selectin"})

class Feature(Base, table=True):
    """
    Defines a gateable capability in the system.
    """
    __tablename__ = "swx_billing_feature"  # pyright: ignore[reportAssignmentType]
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(unique=True, index=True) # e.g., "api.calls"
    name: str
    description: Optional[str] = None
    feature_type: FeatureType = Field(default=FeatureType.BOOLEAN)
    unit: Optional[str] = None # e.g., "tokens", "requests"
    
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )

class Plan(Base, table=True):
    """
    A collection of entitlements.
    """
    __tablename__ = "swx_billing_plan"  # pyright: ignore[reportAssignmentType]
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(unique=True, index=True) # e.g., "pro_v1"
    name: str
    description: Optional[str] = None
    is_active: bool = Field(default=True, index=True)
    is_public: bool = Field(default=True)
    billing_interval: BillingInterval = Field(default=BillingInterval.MONTHLY)
    stripe_price_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, index=True),
    )
    stripe_product_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    amount: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
    )
    currency: Optional[str] = Field(
        default="usd",
        sa_column=Column(String(3), nullable=True),
    )
    
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    )

class PlanEntitlement(Base, table=True):
    """
    Maps Features to Plans with specific limits.
    """
    __tablename__ = "swx_billing_plan_entitlement"  # pyright: ignore[reportAssignmentType]
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    plan_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_billing_plan.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    feature_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_billing_feature.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    
    # Value can be a boolean string ("true"), a number ("1000"), or a config JSON
    value: str 
    
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )

class Subscription(Base, table=True):
    """
    An active link between an account and a plan.
    """
    __tablename__ = "swx_billing_subscription"  # pyright: ignore[reportAssignmentType]
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_billing_account.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    plan_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_billing_plan.id", ondelete="RESTRICT"),
            index=True,
            nullable=False,
        )
    )
    
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE, index=True)
    
    current_period_start: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    current_period_end: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    
    cancel_at_period_end: bool = Field(default=False)
    canceled_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    
    stripe_subscription_id: Optional[str] = Field(default=None, unique=True, index=True)
    
    trial_ends_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the trial period ends. Null means no trial or trial expired.",
    )
    
    grace_period_ends_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the renewal grace period ends. Null means no grace period.",
    )
    
    renewal_failure_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    
    subscription_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    )
    
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    )

    account: BillingAccount = Relationship(back_populates="subscriptions", sa_relationship_kwargs={"lazy": "selectin"})


class SubscriptionPublic(SQLModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    plan_key: str = ""
    plan_name: Optional[str] = None
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    canceled_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True

class UsageRecord(Base, table=True):
    """
    Tracks consumption of quota-based features.
    """
    __tablename__ = "swx_billing_usage_record"  # pyright: ignore[reportAssignmentType]
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_billing_account.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    feature_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_billing_feature.id", ondelete="RESTRICT"),
            index=True,
            nullable=False,
        )
    )
    subscription_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_billing_subscription.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    
    quantity: int = Field(default=0)
    period_start: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    period_end: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    )
