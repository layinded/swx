# Adding Policies

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Policy Types](#policy-types)
3. [System Policies](#system-policies)
4. [Custom Policies](#custom-policies)
5. [Policy Conditions](#policy-conditions)
6. [Policy Evaluation](#policy-evaluation)
7. [Best Practices](#best-practices)

---

## Overview

SwX-API includes a **policy engine (ABAC)** that provides fine-grained authorization beyond RBAC. Policies evaluate conditions on actors, actions, resources, and context to make authorization decisions.

### Key Concepts

- **Policy** - Authorization rule with conditions
- **Effect** - ALLOW, DENY, or CONDITIONAL_ALLOW
- **Conditions** - Attribute-based checks
- **Priority** - Evaluation order (higher = evaluated first)
- **System Policies** - Defined in code, always active
- **Custom Policies** - Defined via API, runtime configurable

---

## Policy Types

### System Policies

**Characteristics:**
- Defined in code (`PolicyRegistry`)
- Always active
- Cannot be disabled
- High priority

**Use Cases:**
- Core security rules
- Framework-level policies
- Critical authorization rules

### Custom Policies

**Characteristics:**
- Defined via API or database
- Can be enabled/disabled
- Runtime configurable
- Lower priority (by default)

**Use Cases:**
- Business-specific rules
- Tenant-specific policies
- Dynamic authorization rules

---

## System Policies

### Registering System Policies

**Policy Registry:**
```python
# swx_core/services/policy/policy_registry.py
from swx_core.services.policy.policy_registry import PolicyRegistry

# Register system policy
PolicyRegistry.register({
    "policy_id": "team.update.owner",
    "name": "Team Update Owner Only",
    "description": "Only team owners can update teams",
    "effect": "allow",
    "action_pattern": "team:update",
    "resource_type": "team",
    "conditions": [
        {
            "attribute": "actor.team_role",
            "operator": "eq",
            "value": "owner"
        },
        {
            "attribute": "resource.team_id",
            "operator": "eq",
            "value": "actor.team_id"
        }
    ],
    "priority": 200,  # High priority
    "owner": "swx_core"
})
```

### Policy Definition

**Required Fields:**
- `policy_id` - Unique identifier
- `name` - Human-readable name
- `effect` - ALLOW, DENY, or CONDITIONAL_ALLOW
- `action_pattern` - Action pattern (e.g., "team:update", "team:*")
- `resource_type` - Resource type (e.g., "team", "user")

**Optional Fields:**
- `description` - Policy description
- `conditions` - List of conditions
- `priority` - Evaluation priority (default: 100)
- `owner` - Policy owner (module/team)
- `tags` - Policy tags

---

## Custom Policies

### Creating via API

**POST `/api/admin/policy/`**
```bash
POST /api/admin/policy/
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "policy_id": "product.delete.owner",
  "name": "Product Delete Owner Only",
  "description": "Only product owners can delete products",
  "effect": "allow",
  "action_pattern": "product:delete",
  "resource_type": "product",
  "conditions": [
    {
      "attribute": "resource.user_id",
      "operator": "eq",
      "value": "actor.id"
    }
  ],
  "priority": 150,
  "enabled": true
}
```

### Creating via Code

**Database Insert:**
```python
from swx_core.models.policy import Policy, PolicyEffect, ConditionOperator

policy = Policy(
    policy_id="product.delete.owner",
    name="Product Delete Owner Only",
    description="Only product owners can delete products",
    effect=PolicyEffect.ALLOW,
    action_pattern="product:delete",
    resource_type="product",
    conditions=[
        {
            "attribute": "resource.user_id",
            "operator": ConditionOperator.EQUALS.value,
            "value": "actor.id"
        }
    ],
    priority=150,
    enabled=True
)

session.add(policy)
await session.commit()
```

---

## Policy Conditions

### Condition Structure

**Condition Format:**
```json
{
  "attribute": "actor.team_id",
  "operator": "eq",
  "value": "resource.team_id",
  "logical_op": "AND"
}
```

**Fields:**
- `attribute` - Attribute path (e.g., "actor.team_id", "resource.user_id")
- `operator` - Comparison operator (eq, ne, in, gt, etc.)
- `value` - Comparison value or reference (e.g., "resource.team_id")
- `logical_op` - Logical operator for compound conditions (AND, OR)

### Available Operators

**Equality:**
- `eq` - Equals
- `ne` - Not equals

**Membership:**
- `in` - In list
- `not_in` - Not in list

**Comparison:**
- `gt` - Greater than
- `gte` - Greater than or equal
- `lt` - Less than
- `lte` - Less than or equal

**String:**
- `contains` - Contains substring
- `starts_with` - Starts with string

**Existence:**
- `exists` - Attribute exists
- `not_exists` - Attribute does not exist

### Attribute Paths

**Actor Attributes:**
- `actor.id` - Actor ID
- `actor.email` - Actor email
- `actor.team_id` - Actor's team ID
- `actor.team_role` - Actor's team role

**Resource Attributes:**
- `resource.id` - Resource ID
- `resource.user_id` - Resource owner ID
- `resource.team_id` - Resource team ID
- `resource.created_at` - Resource creation date

**Context Attributes:**
- `context.ip_address` - Request IP address
- `context.user_agent` - Request user agent
- `context.time_of_day` - Request time

### Value References

**Static Values:**
```json
{
  "attribute": "actor.team_role",
  "operator": "eq",
  "value": "owner"  # Static value
}
```

**Dynamic References:**
```json
{
  "attribute": "resource.user_id",
  "operator": "eq",
  "value": "actor.id"  # Reference to actor attribute
}
```

---

## Policy Evaluation

### Evaluation Flow

**1. Find Matching Policies**
- Policies matching action pattern
- Policies matching resource type
- Enabled policies only

**2. Sort by Priority**
- Higher priority evaluated first
- System policies typically higher priority

**3. Evaluate Conditions**
- Check each condition
- All conditions must pass (AND logic)
- OR logic supported via `logical_op`

**4. Apply Effect**
- ALLOW - Access granted
- DENY - Access denied (stops evaluation)
- CONDITIONAL_ALLOW - Access granted with conditions

**5. Final Decision**
- DENY takes precedence
- If no DENY, ALLOW wins
- If no match, default DENY (fail-closed)

### Using Policies

**In Routes:**
```python
from swx_core.services.policy.dependencies import require_policy

@router.delete("/{product_id}")
async def delete_product(
    product_id: UUID,
    session: SessionDep,
    current_user: UserDep,
    _policy: None = Depends(require_policy("product:delete", "product")),
):
    """Delete product - policy enforced."""
    ...
```

**In Code:**
```python
from swx_core.services.policy.policy_engine import PolicyEngine

engine = PolicyEngine(session)

# Evaluate policy
result = await engine.evaluate(
    actor=current_user,
    action="product:delete",
    resource=product,
    context={"ip_address": request.client.host}
)

if result.decision == PolicyDecision.ALLOW:
    # Allow operation
    ...
else:
    raise HTTPException(403, "Policy denied")
```

---

## Best Practices

### ✅ DO

1. **Use descriptive policy IDs**
   ```python
   # ✅ Good - Descriptive ID
   policy_id="team.update.owner"
   
   # ❌ Bad - Vague ID
   policy_id="policy1"
   ```

2. **Document policy purpose**
   ```python
   # ✅ Good - Clear description
   description="Only team owners can update teams"
   ```

3. **Use appropriate priority**
   ```python
   # ✅ Good - System policies high priority
   priority=200  # System policy
   
   # ✅ Good - Custom policies lower priority
   priority=100  # Custom policy
   ```

4. **Test policy conditions**
   ```python
   # ✅ Good - Test conditions
   result = await engine.evaluate(actor, action, resource, context)
   assert result.decision == PolicyDecision.ALLOW
   ```

5. **Use fail-closed default**
   ```python
   # ✅ Good - Fail-closed
   if result.decision != PolicyDecision.ALLOW:
       raise HTTPException(403, "Policy denied")
   ```

### ❌ DON'T

1. **Don't create overly complex conditions**
   ```python
   # ❌ Bad - Too complex
   conditions=[
       {"attribute": "actor.team_id", "operator": "eq", "value": "resource.team_id"},
       {"attribute": "actor.team_role", "operator": "eq", "value": "owner"},
       {"attribute": "resource.status", "operator": "ne", "value": "deleted"},
       # ... 10 more conditions
   ]
   
   # ✅ Good - Simple conditions
   conditions=[
       {"attribute": "resource.user_id", "operator": "eq", "value": "actor.id"}
   ]
   ```

2. **Don't duplicate RBAC checks**
   ```python
   # ❌ Bad - Duplicate RBAC
   # Policy checks permission that RBAC already checks
   
   # ✅ Good - Policy for complex rules
   # Policy checks ownership, RBAC checks permission
   ```

---

## Next Steps

- Read [Policy Engine Documentation](../04-core-concepts/POLICY_ENGINE.md) for policy details
- Read [Adding Features](./ADDING_FEATURES.md) for feature development
- Read [Adding Entitlements](./ADDING_ENTITLEMENTS.md) for billing integration

---

**Status:** Adding policies guide documented, ready for implementation.
