"""
Billing Models
--------------
This module defines the database models for the billing and entitlement system.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from sqlalchemy import Column, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel
from swx_core.models.base import Base

class BillingAccountType(str, Enum):
    USER = "user"
    TEAM = "team"
    ORGANIZATION = "organization"

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

class BillingAccount(Base, table=True):
    """
    Represents a billed entity (User, Team, or Org).
    """
    __tablename__ = "billing_account"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_type: BillingAccountType = Field(index=True)
    owner_id: uuid.UUID = Field(index=True) # ID of User or Team
    
    stripe_customer_id: Optional[str] = Field(default=None, unique=True, index=True)
    billing_email: Optional[str] = Field(default=None)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    subscriptions: List["Subscription"] = Relationship(back_populates="account")

class Feature(Base, table=True):
    """
    Defines a gateable capability in the system.
    """
    __tablename__ = "billing_feature"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(unique=True, index=True) # e.g., "api.calls"
    name: str
    description: Optional[str] = None
    feature_type: FeatureType = Field(default=FeatureType.BOOLEAN)
    unit: Optional[str] = None # e.g., "tokens", "requests"
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Plan(Base, table=True):
    """
    A collection of entitlements.
    """
    __tablename__ = "billing_plan"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(unique=True, index=True) # e.g., "pro_v1"
    name: str
    description: Optional[str] = None
    is_active: bool = Field(default=True, index=True)
    is_public: bool = Field(default=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class PlanEntitlement(Base, table=True):
    """
    Maps Features to Plans with specific limits.
    """
    __tablename__ = "billing_plan_entitlement"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    plan_id: uuid.UUID = Field(foreign_key="billing_plan.id", index=True)
    feature_id: uuid.UUID = Field(foreign_key="billing_feature.id", index=True)
    
    # Value can be a boolean string ("true"), a number ("1000"), or a config JSON
    value: str 
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Subscription(Base, table=True):
    """
    An active link between an account and a plan.
    """
    __tablename__ = "billing_subscription"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(foreign_key="billing_account.id", index=True)
    plan_id: uuid.UUID = Field(foreign_key="billing_plan.id", index=True)
    
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE, index=True)
    
    current_period_start: datetime = Field(default_factory=datetime.utcnow)
    current_period_end: Optional[datetime] = None
    
    cancel_at_period_end: bool = Field(default=False)
    canceled_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    
    stripe_subscription_id: Optional[str] = Field(default=None, unique=True, index=True)
    
    subscription_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    )
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    account: BillingAccount = Relationship(back_populates="subscriptions")

class UsageRecord(Base, table=True):
    """
    Tracks consumption of quota-based features.
    """
    __tablename__ = "billing_usage_record"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(foreign_key="billing_account.id", index=True)
    feature_id: uuid.UUID = Field(foreign_key="billing_feature.id", index=True)
    subscription_id: uuid.UUID = Field(foreign_key="billing_subscription.id", index=True)
    
    quantity: int = Field(default=0)
    period_start: datetime = Field(index=True)
    period_end: datetime = Field(index=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
