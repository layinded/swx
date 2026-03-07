"""
Policy Engine
-------------
Attribute-Based Access Control (ABAC) policy engine.

This module provides the final authorization layer that sits on top of
RBAC and billing entitlements.
"""

from swx_core.services.policy.policy_engine import PolicyEngine, PolicyDecision, PolicyEvaluationResult
from swx_core.services.policy.policy_registry import PolicyRegistry, register_system_policies
from swx_core.services.policy.actor import Actor, ActorType
from swx_core.services.policy.resource import Resource
from swx_core.services.policy.context import PolicyContext
from swx_core.services.policy.dependencies import require_policy

__all__ = [
    "PolicyEngine",
    "PolicyDecision",
    "PolicyEvaluationResult",
    "PolicyRegistry",
    "register_system_policies",
    "Actor",
    "ActorType",
    "Resource",
    "PolicyContext",
    "require_policy",
]
