"""
Policy Registry
--------------
Central registry for system policies.

System policies are defined in code and loaded at startup.
They cannot be modified via API but can be disabled.
"""

from typing import Dict, List, Optional
from swx_core.models.policy import Policy, PolicyEffect, ConditionOperator
from swx_core.middleware.logging_middleware import logger


class PolicyRegistry:
    """
    Central registry for system policies.
    
    Policies are declared in one place with clear ownership.
    No inline lambda policies in routes.
    """
    
    _policies: Dict[str, Dict] = {}
    _action_index: Dict[str, List[str]] = {}  # action -> [policy_ids]
    _resource_index: Dict[str, List[str]] = {}  # resource_type -> [policy_ids]
    
    @classmethod
    def register(cls, policy_def: Dict) -> None:
        """
        Register a system policy.
        
        Args:
            policy_def: Policy definition dictionary with keys:
                - policy_id: Unique identifier
                - name: Human-readable name
                - description: Policy description
                - effect: "allow" | "deny" | "conditional"
                - action_pattern: Action pattern (e.g., "team:update")
                - resource_type: Resource type (e.g., "team")
                - conditions: List of condition dictionaries
                - priority: Evaluation priority (default: 100)
                - owner: Module/team that owns this policy
                - tags: List of tags
        """
        policy_id = policy_def.get("policy_id")
        if not policy_id:
            raise ValueError("Policy definition must include 'policy_id'")
        
        if policy_id in cls._policies:
            logger.warning(f"Policy {policy_id} already registered, overwriting")
        
        cls._policies[policy_id] = policy_def
        
        # Index by action
        action_pattern = policy_def.get("action_pattern", "")
        if action_pattern not in cls._action_index:
            cls._action_index[action_pattern] = []
        cls._action_index[action_pattern].append(policy_id)
        
        # Index by resource type
        resource_type = policy_def.get("resource_type", "")
        if resource_type not in cls._resource_index:
            cls._resource_index[resource_type] = []
        cls._resource_index[resource_type].append(policy_id)
        
        logger.debug(f"Registered policy: {policy_id}")
    
    @classmethod
    def get(cls, policy_id: str) -> Optional[Dict]:
        """Get a policy definition by ID."""
        return cls._policies.get(policy_id)
    
    @classmethod
    def list_all(cls) -> List[Dict]:
        """List all registered policies."""
        return list(cls._policies.values())
    
    @classmethod
    def get_by_action(cls, action: str) -> List[Dict]:
        """Get policies that might match an action."""
        matching = []
        for policy_id, policy_def in cls._policies.items():
            pattern = policy_def.get("action_pattern", "")
            if cls._matches_pattern(action, pattern):
                matching.append(policy_def)
        return matching
    
    @classmethod
    def get_by_resource_type(cls, resource_type: str) -> List[Dict]:
        """Get policies for a resource type."""
        policy_ids = cls._resource_index.get(resource_type, [])
        return [cls._policies[pid] for pid in policy_ids if pid in cls._policies]
    
    @classmethod
    def _matches_pattern(cls, action: str, pattern: str) -> bool:
        """Check if action matches pattern."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return action.startswith(pattern[:-1])
        if pattern.startswith("*"):
            return action.endswith(pattern[1:])
        return action == pattern


# System Policies
# These are loaded at startup and cannot be modified via API

def register_system_policies():
    """Register all system policies."""
    
    # Team Ownership Policy
    PolicyRegistry.register({
        "policy_id": "team.update.owner",
        "name": "Team Owner Update",
        "description": "Only team owners can update team settings",
        "effect": PolicyEffect.ALLOW.value,
        "action_pattern": "team:update",
        "resource_type": "team",
        "conditions": [
            {
                "attribute": "actor.team_id",
                "operator": ConditionOperator.EQUALS.value,
                "value": "resource.team_id"
            },
            {
                "attribute": "actor.roles",
                "operator": ConditionOperator.CONTAINS.value,
                "value": "team.owner"
            }
        ],
        "priority": 100,
        "owner": "swx_core.services.policy",
        "tags": ["team", "ownership"]
    })
    
    # Resource Ownership Policy
    PolicyRegistry.register({
        "policy_id": "resource.update.own",
        "name": "Update Own Resources",
        "description": "Users can update their own resources",
        "effect": PolicyEffect.ALLOW.value,
        "action_pattern": "*:update",
        "resource_type": "*",
        "conditions": [
            {
                "attribute": "actor.id",
                "operator": ConditionOperator.EQUALS.value,
                "value": "resource.owner_id"
            }
        ],
        "priority": 100,
        "owner": "swx_core.services.policy",
        "tags": ["ownership", "self-service"]
    })
    
    # Superuser Bypass Policy
    PolicyRegistry.register({
        "policy_id": "superuser.bypass",
        "name": "Superuser Bypass",
        "description": "Superusers bypass all policy checks",
        "effect": PolicyEffect.ALLOW.value,
        "action_pattern": "*",
        "resource_type": "*",
        "conditions": [
            {
                "attribute": "actor.is_superuser",
                "operator": ConditionOperator.EQUALS.value,
                "value": True
            }
        ],
        "priority": 1000,  # Highest priority
        "owner": "swx_core.services.policy",
        "tags": ["superuser", "bypass"]
    })
    
    logger.info(f"Registered {len(PolicyRegistry.list_all())} system policies")
