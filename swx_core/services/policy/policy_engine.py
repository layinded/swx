"""
Policy Engine Core
------------------
Central policy evaluation engine for ABAC authorization.

This engine evaluates policies to determine if an action should be
ALLOW or DENY based on actor, action, resource, and context.
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, or_

from swx_core.models.policy import Policy, PolicyEffect, ConditionOperator
from swx_core.services.policy.actor import Actor
from swx_core.services.policy.resource import Resource
from swx_core.services.policy.context import PolicyContext
from swx_core.middleware.logging_middleware import logger


class PolicyDecision(str, Enum):
    """Policy evaluation decision."""
    ALLOW = "allow"
    DENY = "deny"


class PolicyEvaluationResult:
    """Result of policy evaluation."""
    
    def __init__(
        self,
        decision: PolicyDecision,
        policy_id: Optional[str] = None,
        evaluations: Optional[List[Dict[str, Any]]] = None,
        reason: Optional[str] = None
    ):
        self.decision = decision
        self.policy_id = policy_id
        self.evaluations = evaluations or []
        self.reason = reason
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "decision": self.decision.value,
            "policy_id": self.policy_id,
            "evaluations": self.evaluations,
            "reason": self.reason
        }


class PolicyEngine:
    """
    Policy evaluation engine.
    
    Rules:
    - Fail closed (DENY if no policy matches)
    - Deterministic (same inputs = same output)
    - No side effects
    - Fast execution
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def evaluate(
        self,
        actor: Actor,
        action: str,
        resource: Resource,
        context: PolicyContext,
    ) -> PolicyEvaluationResult:
        """
        Evaluate policies for an authorization request.
        
        Args:
            actor: The entity making the request
            action: The action being attempted (e.g., "team:update")
            resource: The resource being accessed
            context: Environmental context
            
        Returns:
            PolicyEvaluationResult with decision (ALLOW or DENY)
        """
        # 1. Find all applicable policies
        policies = await self._find_policies(action, resource.type)
        
        if not policies:
            logger.debug(f"No policies found for action={action}, resource_type={resource.type}")
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY,
                reason="No policies found - fail closed"
            )
        
        # 2. Sort by priority (highest first)
        policies.sort(key=lambda p: p.priority, reverse=True)
        
        evaluations = []
        allow_policy_matched = False
        
        # 3. Evaluate each policy
        for policy in policies:
            if not policy.enabled:
                continue
            
            # Check if action matches pattern
            if not self._matches_action(action, policy.action_pattern):
                continue
            
            # Get effect (handle both Policy objects and system policy dicts)
            if hasattr(policy, 'effect'):
                effect_value = policy.effect.value if isinstance(policy.effect, PolicyEffect) else policy.effect
            else:
                effect_value = policy.effect
            
            # Get policy_id
            policy_id = getattr(policy, 'policy_id', 'unknown')
            
            # Evaluate conditions
            conditions = getattr(policy, 'conditions', [])
            condition_results = await self._evaluate_conditions(
                conditions, actor, resource, context
            )
            
            all_conditions_passed = all(
                result["result"] for result in condition_results
            )
            
            evaluation = {
                "policy_id": policy_id,
                "effect": effect_value,
                "conditions": condition_results,
                "matched": all_conditions_passed
            }
            evaluations.append(evaluation)
            
            # DENY policies take precedence
            if effect_value == PolicyEffect.DENY.value and all_conditions_passed:
                logger.warning(
                    f"Policy {policy_id} DENIED access for "
                    f"actor={actor.id}, action={action}, resource={resource.id}"
                )
                return PolicyEvaluationResult(
                    decision=PolicyDecision.DENY,
                    policy_id=policy_id,
                    evaluations=evaluations,
                    reason=f"Policy {policy_id} explicitly denied"
                )
            
            # ALLOW or CONDITIONAL_ALLOW policies
            if effect_value in (PolicyEffect.ALLOW.value, PolicyEffect.CONDITIONAL_ALLOW.value):
                if all_conditions_passed:
                    allow_policy_matched = True
                    logger.debug(
                        f"Policy {policy_id} ALLOWED access for "
                        f"actor={actor.id}, action={action}, resource={resource.id}"
                    )
        
        # 4. Final decision
        if allow_policy_matched:
            return PolicyEvaluationResult(
                decision=PolicyDecision.ALLOW,
                evaluations=evaluations,
                reason="At least one ALLOW policy matched"
            )
        else:
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY,
                evaluations=evaluations,
                reason="No ALLOW policies matched - fail closed"
            )
    
    async def _find_policies(
        self,
        action: str,
        resource_type: str
    ) -> List[Policy]:
        """Find all policies that might apply to this action and resource type."""
        from swx_core.services.policy.policy_registry import PolicyRegistry
        
        policies = []
        
        # 1. Get database policies (matching resource_type or wildcard)
        stmt = select(Policy).where(
            and_(
                or_(
                    Policy.resource_type == resource_type,
                    Policy.resource_type == "*"
                ),
                Policy.enabled == True
            )
        )
        result = await self.session.execute(stmt)
        db_policies = list(result.scalars().all())
        
        # 2. Get system policies from registry (matching resource_type or wildcard)
        system_policy_defs = PolicyRegistry.list_all()
        
        # 3. Convert system policy definitions to Policy objects (for evaluation)
        for policy_def in system_policy_defs:
            policy_resource_type = policy_def.get("resource_type", "")
            policy_action_pattern = policy_def.get("action_pattern", "")
            
            # Check if resource type matches (exact or wildcard)
            if policy_resource_type not in (resource_type, "*"):
                continue
            
            # Check if action matches pattern
            if not self._matches_action(action, policy_action_pattern):
                continue
            
            # Create a Policy-like object from the definition
            class SystemPolicy:
                def __init__(self, policy_def):
                    self.policy_id = policy_def.get("policy_id")
                    self.effect = policy_def.get("effect")
                    self.action_pattern = policy_def.get("action_pattern")
                    self.resource_type = policy_def.get("resource_type")
                    self.conditions = policy_def.get("conditions", [])
                    self.priority = policy_def.get("priority", 100)
                    self.enabled = True  # System policies are always enabled
            
            policies.append(SystemPolicy(policy_def))
        
        # 4. Add database policies (already filtered by resource_type)
        for db_policy in db_policies:
            if self._matches_action(action, db_policy.action_pattern):
                policies.append(db_policy)
        
        return policies
    
    def _matches_action(self, action: str, pattern: str) -> bool:
        """
        Check if an action matches a pattern.
        
        Supports:
        - Exact match: "team:update"
        - Wildcard suffix: "team:*"
        - Wildcard prefix: "*:update"
        - Full wildcard: "*"
        """
        if pattern == "*":
            return True
        
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return action.startswith(prefix)
        
        if pattern.startswith("*"):
            suffix = pattern[1:]
            return action.endswith(suffix)
        
        return action == pattern
    
    async def _evaluate_conditions(
        self,
        conditions: List[Dict[str, Any]],
        actor: Actor,
        resource: Resource,
        context: PolicyContext
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all conditions in a policy.
        
        Returns list of condition evaluation results.
        """
        results = []
        
        for condition in conditions:
            attribute_path = condition.get("attribute", "")
            operator = condition.get("operator", "")
            value = condition.get("value")
            
            # Get actual attribute value
            actual_value = self._get_attribute_value(
                attribute_path, actor, resource, context
            )
            
            # Resolve reference values (e.g., "resource.team_id")
            comparison_value = self._resolve_value(
                value, actor, resource, context
            )
            
            # Evaluate condition
            result = self._evaluate_condition(
                actual_value, operator, comparison_value
            )
            
            results.append({
                "attribute": attribute_path,
                "operator": operator,
                "expected": comparison_value,
                "actual": actual_value,
                "result": result
            })
        
        return results
    
    def _get_attribute_value(
        self,
        path: str,
        actor: Actor,
        resource: Resource,
        context: PolicyContext
    ) -> Any:
        """Get attribute value from actor, resource, or context."""
        if path.startswith("actor."):
            return actor.get_attribute(path[6:])  # Remove "actor." prefix
        elif path.startswith("resource."):
            return resource.get_attribute(path[9:])  # Remove "resource." prefix
        elif path.startswith("context."):
            return context.get_attribute(path[8:])  # Remove "context." prefix
        else:
            logger.warning(f"Unknown attribute path: {path}")
            return None
    
    def _resolve_value(
        self,
        value: Any,
        actor: Actor,
        resource: Resource,
        context: PolicyContext
    ) -> Any:
        """
        Resolve a value that might be a reference (e.g., "resource.team_id").
        
        If value is a string starting with "actor.", "resource.", or "context.",
        resolve it as an attribute path. Otherwise, return as-is.
        """
        if isinstance(value, str):
            if value.startswith(("actor.", "resource.", "context.")):
                return self._get_attribute_value(value, actor, resource, context)
        
        return value
    
    def _evaluate_condition(
        self,
        actual: Any,
        operator: str,
        expected: Any
    ) -> bool:
        """Evaluate a single condition."""
        try:
            op_enum = ConditionOperator(operator)
        except ValueError:
            logger.warning(f"Unknown operator: {operator}")
            return False
        
        if actual is None and op_enum not in (ConditionOperator.EXISTS, ConditionOperator.NOT_EXISTS):
            return False
        
        if op_enum == ConditionOperator.EQUALS:
            return actual == expected
        
        elif op_enum == ConditionOperator.NOT_EQUALS:
            return actual != expected
        
        elif op_enum == ConditionOperator.IN:
            if not isinstance(expected, list):
                return False
            return actual in expected
        
        elif op_enum == ConditionOperator.NOT_IN:
            if not isinstance(expected, list):
                return False
            return actual not in expected
        
        elif op_enum == ConditionOperator.GREATER_THAN:
            return actual > expected
        
        elif op_enum == ConditionOperator.GREATER_THAN_OR_EQUAL:
            return actual >= expected
        
        elif op_enum == ConditionOperator.LESS_THAN:
            return actual < expected
        
        elif op_enum == ConditionOperator.LESS_THAN_OR_EQUAL:
            return actual <= expected
        
        elif op_enum == ConditionOperator.CONTAINS:
            if isinstance(actual, (list, str)):
                return expected in actual
            return False
        
        elif op_enum == ConditionOperator.STARTS_WITH:
            if isinstance(actual, str):
                return actual.startswith(expected)
            return False
        
        elif op_enum == ConditionOperator.EXISTS:
            return actual is not None
        
        elif op_enum == ConditionOperator.NOT_EXISTS:
            return actual is None
        
        else:
            logger.warning(f"Unhandled operator: {operator}")
            return False
