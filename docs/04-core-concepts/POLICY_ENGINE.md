# Policy Engine (ABAC)

**Version:** 1.0.0  
**Last Updated:** 2026-01-26  
**Updated:** Real-world policy examples added, environment from settings

---

## Table of Contents

1. [Overview](#overview)
2. [Why Policies?](#why-policies)
3. [Policy Architecture](#policy-architecture)
4. [Policy Evaluation](#policy-evaluation)
5. [Writing Policies](#writing-policies)
6. [System Policies](#system-policies)
7. [Custom Policies](#custom-policies)
8. [Usage Examples](#usage-examples)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The **Policy Engine** provides **Attribute-Based Access Control (ABAC)** as the final authorization layer in SwX-API. It answers the question: **"Under which conditions should access be granted?"**

### Authorization Layers

```
┌─────────────────────────────────────┐
│   Policy Engine (ABAC)              │  ← Final authorization layer
│   "Under which conditions?"         │
├─────────────────────────────────────┤
│   Billing Entitlements               │  ← "What features?"
├─────────────────────────────────────┤
│   RBAC (Permissions & Roles)         │  ← "Who has what?"
├─────────────────────────────────────┤
│   Authentication                     │  ← "Who are you?"
└─────────────────────────────────────┘
```

**Evaluation Order:**
1. **Authentication** - Who is making the request?
2. **RBAC** - Does the user have the required permission?
3. **Billing** - Is the user entitled to this feature?
4. **Policy Engine** - Under which conditions is access allowed?

### Key Features

- ✅ **Conditional Access** - Access based on attributes (team membership, ownership, time, etc.)
- ✅ **Fail Closed** - DENY if no policy matches
- ✅ **Deterministic** - Same inputs = same output
- ✅ **Fast** - In-memory evaluation
- ✅ **Auditable** - Every decision logged
- ✅ **Flexible** - Supports complex conditions

---

## Why Policies?

### RBAC Limitations

**RBAC answers:** "Does the user have permission X?"

**But cannot answer:**
- "Can the user update this team?" (need to check team membership)
- "Can the user delete this article?" (need to check ownership)
- "Can the user access during business hours?" (need to check time)
- "Can the user access from this IP?" (need to check location)

### Policy Engine Solution

**Policies answer:** "Under which conditions should access be granted?"

**Examples:**
- ✅ "User can update team if they are team owner"
- ✅ "User can delete article if they are the author"
- ✅ "User can access during business hours (9 AM - 5 PM)"
- ✅ "User can access from whitelisted IP addresses"

---

## Policy Architecture

### Policy Components

A policy consists of:

1. **Policy ID** - Unique identifier (e.g., `"team.update.owner"`)
2. **Effect** - `ALLOW`, `DENY`, or `CONDITIONAL_ALLOW`
3. **Action Pattern** - Action to match (e.g., `"team:update"`, `"team:*"`)
4. **Resource Type** - Resource type (e.g., `"team"`, `"*"`)
5. **Conditions** - List of conditions to evaluate
6. **Priority** - Evaluation order (higher = evaluated first)

### Policy Model

```python
class Policy(SQLModel, table=True):
    id: UUID
    policy_id: str  # "team.update.owner"
    name: str
    description: str
    effect: PolicyEffect  # ALLOW, DENY, CONDITIONAL_ALLOW
    action_pattern: str  # "team:update"
    resource_type: str  # "team"
    conditions: List[Dict]  # Condition definitions
    priority: int  # 100 (higher = evaluated first)
    enabled: bool
    owner: str  # Module/team that owns this policy
    tags: List[str]
```

### Condition Model

```python
class Condition:
    attribute: str  # "actor.team_id"
    operator: ConditionOperator  # "eq", "in", "gt", etc.
    value: Any  # Comparison value or reference
```

### Supported Operators

- `eq` - Equals
- `ne` - Not equals
- `in` - In list
- `not_in` - Not in list
- `gt` - Greater than
- `gte` - Greater than or equal
- `lt` - Less than
- `lte` - Less than or equal
- `contains` - Contains value
- `starts_with` - Starts with value
- `exists` - Attribute exists
- `not_exists` - Attribute does not exist

---

## Policy Evaluation

### Evaluation Flow

```
1. Find applicable policies
   └── Match action pattern and resource type

2. Sort by priority (highest first)

3. Evaluate each policy
   ├── Check if action matches pattern
   ├── Evaluate all conditions
   └── Determine if policy matches

4. Apply effect
   ├── DENY policies take precedence
   └── At least one ALLOW policy must match

5. Return decision
   └── ALLOW or DENY
```

### Evaluation Rules

1. **Fail Closed:** If no policies match, DENY
2. **DENY Precedence:** DENY policies override ALLOW policies
3. **Priority Order:** Higher priority policies evaluated first
4. **All Conditions Must Pass:** All conditions in a policy must be true
5. **At Least One ALLOW:** At least one ALLOW policy must match for access

### Example Evaluation

**Request:**
- Actor: `alice@example.com` (team_id: `team-123`, role: `team.owner`)
- Action: `"team:update"`
- Resource: `team-123` (team_id: `team-123`)

**Policies:**
1. `team.update.owner` (priority: 100)
   - Effect: ALLOW
   - Conditions:
     - `actor.team_id == resource.team_id` ✅ (team-123 == team-123)
     - `actor.roles contains "team.owner"` ✅ (alice has role)
   - Result: **MATCHES** → ALLOW

2. `team.update.member` (priority: 50)
   - Effect: ALLOW
   - Conditions:
     - `actor.team_id == resource.team_id` ✅
     - `actor.roles contains "team.member"` ❌ (alice has owner, not member)
   - Result: **NO MATCH**

**Final Decision:** ALLOW (policy 1 matched)

---

## Writing Policies

### Policy Structure

```python
{
    "policy_id": "team.update.owner",
    "name": "Team Owner Update",
    "description": "Only team owners can update team settings",
    "effect": "allow",
    "action_pattern": "team:update",
    "resource_type": "team",
    "conditions": [
        {
            "attribute": "actor.team_id",
            "operator": "eq",
            "value": "resource.team_id"
        },
        {
            "attribute": "actor.roles",
            "operator": "contains",
            "value": "team.owner"
        }
    ],
    "priority": 100,
    "owner": "swx_core.services.policy",
    "tags": ["team", "ownership"]
}
```

### Action Patterns

**Exact Match:**
```python
"action_pattern": "team:update"  # Matches only "team:update"
```

**Wildcard Suffix:**
```python
"action_pattern": "team:*"  # Matches "team:update", "team:delete", etc.
```

**Wildcard Prefix:**
```python
"action_pattern": "*:update"  # Matches "team:update", "user:update", etc.
```

**Full Wildcard:**
```python
"action_pattern": "*"  # Matches all actions
```

### Resource Types

**Specific Resource:**
```python
"resource_type": "team"  # Matches only team resources
```

**Wildcard:**
```python
"resource_type": "*"  # Matches all resource types
```

### Conditions

**Attribute Paths:**
- `actor.*` - Actor attributes (user, admin)
- `resource.*` - Resource attributes
- `context.*` - Context attributes (time, IP, etc.)

**Common Attributes:**
- `actor.id` - User/Admin ID
- `actor.email` - User/Admin email
- `actor.team_id` - User's team ID
- `actor.roles` - User's roles (list)
- `actor.is_superuser` - Is superuser
- `resource.id` - Resource ID
- `resource.team_id` - Resource's team ID
- `resource.owner_id` - Resource owner ID
- `context.time` - Current time
- `context.ip` - Request IP address

**Value References:**
- `"resource.team_id"` - Reference to resource attribute
- `"actor.id"` - Reference to actor attribute
- `"context.time"` - Reference to context attribute

**Literal Values:**
- `"team-123"` - String literal
- `123` - Number literal
- `true` / `false` - Boolean literal
- `["role1", "role2"]` - List literal

### Example Policies

**1. Team Ownership Policy:**
```python
{
    "policy_id": "team.update.owner",
    "effect": "allow",
    "action_pattern": "team:update",
    "resource_type": "team",
    "conditions": [
        {
            "attribute": "actor.team_id",
            "operator": "eq",
            "value": "resource.team_id"
        },
        {
            "attribute": "actor.roles",
            "operator": "contains",
            "value": "team.owner"
        }
    ]
}
```

**2. Resource Ownership Policy:**
```python
{
    "policy_id": "resource.update.own",
    "effect": "allow",
    "action_pattern": "*:update",
    "resource_type": "*",
    "conditions": [
        {
            "attribute": "actor.id",
            "operator": "eq",
            "value": "resource.owner_id"
        }
    ]
}
```

**3. Time-Based Policy:**
```python
{
    "policy_id": "access.business_hours",
    "effect": "allow",
    "action_pattern": "*",
    "resource_type": "*",
    "conditions": [
        {
            "attribute": "context.time.hour",
            "operator": "gte",
            "value": 9
        },
        {
            "attribute": "context.time.hour",
            "operator": "lte",
            "value": 17
        }
    ]
}
```

**4. IP Whitelist Policy:**
```python
{
    "policy_id": "access.whitelisted_ip",
    "effect": "allow",
    "action_pattern": "*",
    "resource_type": "*",
    "conditions": [
        {
            "attribute": "context.ip",
            "operator": "in",
            "value": ["192.168.1.0/24", "10.0.0.0/8"]
        }
    ]
}
```

**5. DENY Policy:**
```python
{
    "policy_id": "team.delete.prevent",
    "effect": "deny",
    "action_pattern": "team:delete",
    "resource_type": "team",
    "conditions": [
        {
            "attribute": "resource.member_count",
            "operator": "gt",
            "value": 0
        }
    ],
    "priority": 1000  # High priority to ensure DENY takes precedence
}
```

---

## System Policies

### What Are System Policies?

**System policies** are defined in code and loaded at startup. They cannot be modified via API but can be disabled.

**Location:** `swx_core/services/policy/policy_registry.py`

### Registering System Policies

```python
from swx_core.services.policy.policy_registry import PolicyRegistry
from swx_core.models.policy import PolicyEffect, ConditionOperator

def register_system_policies():
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
```

### Built-in System Policies

1. **Team Owner Update** (`team.update.owner`)
   - Allows team owners to update their teams

2. **Resource Ownership** (`resource.update.own`)
   - Allows users to update their own resources

3. **Superuser Bypass** (`superuser.bypass`)
   - Allows superusers to bypass all policy checks

---

## Custom Policies

### Creating Custom Policies

**Via API:**
```bash
POST /api/admin/policy/
{
  "policy_id": "article.delete.author",
  "name": "Article Delete by Author",
  "description": "Only article authors can delete their articles",
  "effect": "allow",
  "action_pattern": "article:delete",
  "resource_type": "article",
  "conditions": [
    {
      "attribute": "actor.id",
      "operator": "eq",
      "value": "resource.author_id"
    }
  ],
  "priority": 100
}
```

**Via Code:**
```python
from swx_core.models.policy import Policy, PolicyEffect, ConditionOperator

policy = Policy(
    policy_id="article.delete.author",
    name="Article Delete by Author",
    description="Only article authors can delete their articles",
    effect=PolicyEffect.ALLOW,
    action_pattern="article:delete",
    resource_type="article",
    conditions=[
        {
            "attribute": "actor.id",
            "operator": ConditionOperator.EQUALS.value,
            "value": "resource.author_id"
        }
    ],
    priority=100,
    enabled=True
)

session.add(policy)
await session.commit()
```

### Updating Policies

**Via API:**
```bash
PATCH /api/admin/policy/{policy_id}
{
  "enabled": false,  # Disable policy
  "priority": 200,  # Change priority
  "conditions": [...]  # Update conditions
}
```

---

## Usage Examples

### Protecting Routes

**Using `require_policy()` dependency:**
```python
from swx_core.services.policy.dependencies import require_policy

@router.patch("/teams/{team_id}", dependencies=[Depends(require_policy("team:update"))])
async def update_team(
    team_id: UUID,
    team_update: TeamUpdate,
    user: UserDep,
    session: SessionDep,
):
    # Policy evaluated automatically
    # Access granted if policy allows
    ...
```

**Real-world Example - User Profile Access:**
```python
# swx_core/routes/user/user_route.py
from swx_core.services.policy.dependencies import require_policy

@router.get("/{user_id}", response_model=UserPublic)
async def read_user_by_id(
    user_id: UUID,
    session: SessionDep,
    current_user: UserDep,
    request: Request,
    _policy: None = Depends(
        require_policy(
            action="user:read",
            resource_type="user",
            resource_id=user_id,
            resource_owner_id=user_id
        )
    ),
) -> Any:
    """
    Retrieve user details by their unique ID.
    
    Policy ensures user can only read their own profile
    (unless they have admin permissions via policy).
    """
    return await get_user_by_id_service(session, str(user_id), current_user, request)
```

**Before (Manual Check):**
```python
# ❌ Old approach - Manual check
@router.get("/{user_id}")
async def read_user_by_id(user_id: UUID, current_user: UserDep):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return await get_user_by_id_service(session, str(user_id), current_user)
```

**After (Policy-Based):**
```python
# ✅ New approach - Policy-based
@router.get("/{user_id}")
async def read_user_by_id(
    user_id: UUID,
    current_user: UserDep,
    _policy: None = Depends(require_policy("user:read", "user", resource_id=user_id))
):
    # Policy automatically enforces access rules
    # Supports complex conditions (ownership, team membership, etc.)
    return await get_user_by_id_service(session, str(user_id), current_user)
```

### Manual Policy Evaluation

**In route handler:**
```python
from swx_core.services.policy.policy_engine import PolicyEngine
from swx_core.services.policy.actor import Actor
from swx_core.services.policy.resource import Resource
from swx_core.services.policy.context import PolicyContext

@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: UUID,
    user: UserDep,
    session: SessionDep,
    request: Request,
):
    # Get article
    article = await get_article(session, article_id)
    
    # Build actor
    actor = Actor.from_user(user)
    
    # Build resource
    resource = Resource(
        id=str(article.id),
        type="article",
        attributes={
            "author_id": str(article.author_id),
            "team_id": str(article.team_id) if article.team_id else None,
        }
    )
    
    # Build context
    context = PolicyContext.from_request(request)
    
    # Evaluate policy
    engine = PolicyEngine(session)
    result = await engine.evaluate(
        actor=actor,
        action="article:delete",
        resource=resource,
        context=context,
    )
    
    if result.decision != PolicyDecision.ALLOW:
        raise HTTPException(403, "Policy denied access")
    
    # Delete article
    await delete_article_service(session, article_id)
```

### Checking Policy in Service

```python
from swx_core.services.policy.policy_engine import PolicyEngine

async def transfer_team_ownership(
    session: AsyncSession,
    user: User,
    team_id: UUID,
    new_owner_id: UUID,
):
    # Build actor and resource
    actor = Actor.from_user(user)
    resource = Resource(
        id=str(team_id),
        type="team",
        attributes={"team_id": str(team_id)}
    )
    
    # Evaluate policy
    engine = PolicyEngine(session)
    result = await engine.evaluate(
        actor=actor,
        action="team:transfer_ownership",
        resource=resource,
        context=PolicyContext(),
    )
    
    if result.decision != PolicyDecision.ALLOW:
        raise HTTPException(403, "Policy denied: cannot transfer ownership")
    
    # Transfer ownership
    ...
```

---

## Best Practices

### ✅ DO

1. **Use descriptive policy IDs**
   ```python
   # ✅ Good
   "policy_id": "team.update.owner"
   
   # ❌ Bad
   "policy_id": "policy1"
   ```

2. **Set appropriate priorities**
   ```python
   # ✅ Good
   "priority": 1000  # DENY policies should be high priority
   "priority": 100   # Normal ALLOW policies
   
   # ❌ Bad
   "priority": 0  # Too low, might not be evaluated
   ```

3. **Use specific action patterns**
   ```python
   # ✅ Good
   "action_pattern": "team:update"  # Specific
   
   # ❌ Bad
   "action_pattern": "*"  # Too broad (unless intentional)
   ```

4. **Document policies**
   ```python
   # ✅ Good
   {
       "policy_id": "team.update.owner",
       "name": "Team Owner Update",
       "description": "Only team owners can update team settings",
       ...
   }
   ```

5. **Test policies thoroughly**
   ```python
   # Test with different actors, resources, contexts
   # Verify DENY policies work
   # Verify ALLOW policies work
   # Verify edge cases
   ```

### ❌ DON'T

1. **Don't create conflicting policies**
   ```python
   # ❌ Bad - Conflicting priorities
   Policy 1: ALLOW, priority 100
   Policy 2: DENY, priority 50  # DENY should be higher priority
   ```

2. **Don't use policies for authentication**
   ```python
   # ❌ Bad - Use authentication, not policies
   {
       "conditions": [
           {"attribute": "actor.is_authenticated", "operator": "eq", "value": true}
       ]
   }
   ```

3. **Don't create overly complex conditions**
   ```python
   # ❌ Bad - Too complex, hard to debug
   {
       "conditions": [
           # 20+ conditions...
       ]
   }
   
   # ✅ Good - Split into multiple policies
   ```

4. **Don't ignore policy evaluation results**
   ```python
   # ❌ Bad
   result = await engine.evaluate(...)
   # Ignore result and proceed anyway
   
   # ✅ Good
   if result.decision != PolicyDecision.ALLOW:
       raise HTTPException(403, "Policy denied")
   ```

---

## Troubleshooting

### Common Issues

**1. Policy not matching**
- Check action pattern matches action
- Check resource type matches resource
- Verify all conditions pass
- Check policy is enabled

**2. DENY policy not working**
- Verify DENY policy has higher priority than ALLOW policies
- Check DENY policy conditions are correct
- Verify policy is enabled

**3. Policy evaluation always DENY**
- Check if any ALLOW policies match
- Verify conditions are correct
- Check attribute paths are valid
- Verify value references resolve correctly

**4. Performance issues**
- Reduce number of policies
- Optimize condition evaluation
- Use specific action patterns (not wildcards)
- Cache policy evaluation results if possible

### Debugging

**Enable debug logging:**
```python
import logging
logging.getLogger("swx_core.services.policy").setLevel(logging.DEBUG)
```

**Check policy evaluation:**
```python
result = await engine.evaluate(...)
print(result.to_dict())
# Shows: decision, policy_id, evaluations, reason
```

**List all policies:**
```python
from swx_core.services.policy.policy_registry import PolicyRegistry

# System policies
system_policies = PolicyRegistry.list_all()

# Database policies
db_policies = await get_all_policies(session)
```

---

## Next Steps

- Read [RBAC Documentation](./RBAC.md) for permission-based access
- Read [Security Model](../05-security/SECURITY_MODEL.md) for security details
- Read [API Usage Guide](../06-api-usage/API_USAGE.md) for API examples

---

**Status:** Policy Engine documented, ready for implementation.
