"""
Policy Models
-------------
Database models for Attribute-Based Access Control (ABAC) policies.

Policies sit on top of RBAC and billing entitlements, providing
the final authorization layer that answers "under which conditions".
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base


class PolicyEffect(str, Enum):
    """Policy evaluation effect."""
    ALLOW = "allow"
    DENY = "deny"
    CONDITIONAL_ALLOW = "conditional"


class ConditionOperator(str, Enum):
    """Condition comparison operators."""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


class Condition(SQLModel):
    """A single condition in a policy."""
    attribute: str  # e.g., "actor.team_id"
    operator: ConditionOperator
    value: Any  # Comparison value or reference (e.g., "resource.team_id")
    logical_op: Optional[str] = None  # "AND" | "OR" for compound conditions


class Policy(Base, table=True):
    """
    Policy definition for ABAC authorization.
    
    Policies evaluate conditions on actor, action, resource, and context
    to determine if access should be ALLOW, DENY, or CONDITIONAL_ALLOW.
    """
    __tablename__ = "policy"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    policy_id: str = Field(unique=True, index=True)  # Human-readable ID (e.g., "team.update.owner")
    name: str
    description: Optional[str] = None
    
    effect: PolicyEffect = Field(default=PolicyEffect.ALLOW)
    
    # Action matching
    action_pattern: str = Field(index=True)  # e.g., "team:update" or "team:*"
    resource_type: str = Field(index=True)  # e.g., "team", "user"
    
    # Conditions stored as JSONB
    conditions: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False)
    )
    
    priority: int = Field(default=100, index=True)  # Higher = evaluated first
    enabled: bool = Field(default=True, index=True)
    
    # Metadata
    owner: Optional[str] = None  # Module/team that owns this policy
    tags: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False)
    )
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PolicyDecision(str, Enum):
    """Policy evaluation result."""
    ALLOW = "allow"
    DENY = "deny"


class PolicyEvaluation(SQLModel):
    """Result of a policy evaluation."""
    policy_id: str
    decision: PolicyDecision
    conditions_evaluated: List[Dict[str, Any]]  # Condition results
    matched: bool  # Did this policy match the request
