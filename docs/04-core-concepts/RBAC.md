# RBAC (Role-Based Access Control)

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Permission-First Design](#permission-first-design)
3. [Core Concepts](#core-concepts)
4. [Team-Scoped Roles](#team-scoped-roles)
5. [Domain Separation](#domain-separation)
6. [Usage Examples](#usage-examples)
7. [Defining Permissions](#defining-permissions)
8. [Common Patterns](#common-patterns)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

SwX-API uses a **permission-first RBAC system** that provides fine-grained access control with support for:

- **Permissions** - Atomic actions (e.g., `"user:read"`, `"article:delete"`)
- **Roles** - Collections of permissions (e.g., `"admin"`, `"editor"`)
- **Team Scoping** - Roles can be scoped to specific teams
- **Domain Separation** - Roles belong to domains (admin, user, system)

### Key Principles

1. **Permission-First:** Permissions are explicit strings, roles are collections
2. **Least Privilege:** Grant minimum permissions needed
3. **Team Isolation:** Roles can be team-scoped for multi-tenancy
4. **Domain Separation:** Admin and user roles are separate

---

## Permission-First Design

### Why Permission-First?

**Traditional RBAC:**
- Roles are checked directly
- Hard to audit what permissions a role has
- Difficult to implement fine-grained control

**Permission-First RBAC:**
- Permissions are explicit and auditable
- Roles are collections of permissions
- Easy to check specific permissions
- Supports least-privilege principle

### Model Hierarchy

```
User
  └── UserRole (assignment)
       └── Role
            └── RolePermission (association)
                 └── Permission
```

**Flow:**
1. User has roles (via `UserRole`)
2. Roles have permissions (via `RolePermission`)
3. Permissions grant access to actions

---

## Core Concepts

### Permissions

**Definition:** Atomic actions that can be performed on resources

**Format:** `"{resource_type}:{action}"`

**Examples:**
- `"user:read"` - Read users
- `"user:write"` - Create/update users
- `"user:delete"` - Delete users
- `"article:read"` - Read articles
- `"article:write"` - Create/update articles
- `"team:manage"` - Manage team settings

**Model:**
```python
class Permission(SQLModel, table=True):
    id: UUID
    name: str  # "user:read"
    description: str
    resource_type: str  # "user"
    action: str  # "read"
```

### Roles

**Definition:** Collections of permissions

**Examples:**
- `"admin"` - All permissions
- `"editor"` - Read and write permissions
- `"viewer"` - Read-only permissions
- `"team_owner"` - Team management permissions

**Model:**
```python
class Role(SQLModel, table=True):
    id: UUID
    name: str  # "admin"
    description: str
    domain: str  # "admin", "user", "system"
    is_system_role: bool  # Cannot be deleted
```

### User-Role Assignment

**Definition:** Assignment of roles to users

**Scoping:**
- **Global roles:** `team_id = None` (applies to all teams)
- **Team-scoped roles:** `team_id = <uuid>` (applies to specific team)

**Model:**
```python
class UserRole(SQLModel, table=True):
    user_id: UUID
    role_id: UUID
    team_id: Optional[UUID]  # None = global, UUID = team-scoped
```

---

## Team-Scoped Roles

### Why Team Scoping?

**Multi-tenant applications** need:
- Users can have different roles in different teams
- Team owners can manage team members
- Team isolation for security

### Example Scenario

**User:** `alice@example.com`

**Global Role:**
- `"viewer"` (read-only access globally)

**Team-Scoped Roles:**
- Team A: `"team_owner"` (full access in Team A)
- Team B: `"editor"` (read/write in Team B)

**Result:**
- Alice can read resources globally
- Alice can manage Team A completely
- Alice can edit resources in Team B

### Implementation

```python
# Global role
user_role_global = UserRole(
    user_id=alice.id,
    role_id=viewer_role.id,
    team_id=None  # Global
)

# Team-scoped role
user_role_team_a = UserRole(
    user_id=alice.id,
    role_id=team_owner_role.id,
    team_id=team_a.id  # Scoped to Team A
)
```

### Permission Resolution

**Order of precedence:**
1. **Team-scoped permissions** (if user is team member)
2. **Global permissions** (fallback)

**Code:**
```python
async def check_team_permission(
    session: AsyncSession,
    user: User,
    team_id: UUID,
    permission_name: str,
) -> bool:
    # 1. Check team-scoped permission
    if await has_permission(session, user, permission_name, team_id=team_id):
        return True
    
    # 2. Fallback to global permission
    return await has_permission(session, user, permission_name, team_id=None)
```

---

## Domain Separation

### Domains

SwX-API supports three domains:

1. **Admin Domain** (`domain="admin"`)
   - Admin-only roles
   - System administration
   - Cannot access user domain

2. **User Domain** (`domain="user"`)
   - Application user roles
   - Team-based access
   - Cannot access admin domain

3. **System Domain** (`domain="system"`)
   - Internal system roles
   - Background jobs
   - No HTTP endpoints

### Role Domains

**Admin Roles:**
```python
admin_role = Role(
    name="super_admin",
    domain="admin",
    is_system_role=True
)
```

**User Roles:**
```python
user_role = Role(
    name="team_owner",
    domain="user",
    is_system_role=False
)
```

**System Roles:**
```python
system_role = Role(
    name="job_runner",
    domain="system",
    is_system_role=True
)
```

### Domain Isolation

**Guarantee:** Roles from one domain cannot access resources from another domain

**Enforcement:**
- Token audience validation
- Domain filtering in permission checks
- Separate authentication flows

---

## Usage Examples

### Protecting Routes with Permissions

**Require specific permission:**
```python
from swx_core.rbac.dependencies import require_permission

@router.get("/users", dependencies=[Depends(require_permission("user:read"))])
async def list_users():
    """Only users with 'user:read' permission can access."""
    ...
```

**Require team-scoped permission:**
```python
@router.get("/teams/{team_id}/members", 
           dependencies=[Depends(require_team_permission(team_id, "team:read"))])
async def list_team_members(team_id: UUID):
    """Only users with 'team:read' permission in this team can access."""
    ...
```

### Checking Permissions in Code

**In route handler:**
```python
from swx_core.rbac.helpers import has_permission

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    user: UserDep,
    session: SessionDep,
):
    # Check permission
    if not await has_permission(session, user, "user:delete"):
        raise HTTPException(403, "Permission denied")
    
    # Delete user
    ...
```

**In service:**
```python
from swx_core.rbac.helpers import check_team_permission

async def delete_team_resource(
    session: AsyncSession,
    user: User,
    team_id: UUID,
    resource_id: UUID,
):
    # Check team permission
    if not await check_team_permission(session, user, team_id, "resource:delete"):
        raise HTTPException(403, "Team permission denied")
    
    # Delete resource
    ...
```

### Getting User Permissions

**Get all permissions:**
```python
from swx_core.rbac.helpers import get_user_permissions

permissions = await get_user_permissions(session, user.id)
permission_names = [p.name for p in permissions]
# ["user:read", "user:write", "article:read"]
```

**Get team-scoped permissions:**
```python
team_permissions = await get_user_permissions(
    session, 
    user.id, 
    team_id=team_id
)
```

**Get domain-specific permissions:**
```python
user_permissions = await get_user_permissions(
    session,
    user.id,
    domain="user"
)
```

---

## Defining Permissions

### Creating Permissions

**Via API:**
```bash
POST /api/admin/permission/
{
  "name": "article:read",
  "description": "Read articles",
  "resource_type": "article",
  "action": "read"
}
```

**Via code:**
```python
from swx_core.models.permission import Permission, PermissionCreate

permission = PermissionCreate(
    name="article:read",
    description="Read articles",
    resource_type="article",
    action="read"
)

# Create via service
await permission_service.create_permission_service(session, permission)
```

### Permission Naming Convention

**Format:** `"{resource_type}:{action}"`

**Resource Types:**
- `user` - User management
- `article` - Article management
- `team` - Team management
- `billing` - Billing operations

**Actions:**
- `read` - View resource
- `write` - Create/update resource
- `delete` - Delete resource
- `manage` - Full management (read, write, delete)

**Examples:**
- `"user:read"` ✅
- `"article:write"` ✅
- `"team:manage"` ✅
- `"read_user"` ❌ (wrong format)
- `"user"` ❌ (missing action)

### Creating Roles

**Via API:**
```bash
POST /api/admin/role/
{
  "name": "editor",
  "description": "Can read and write articles",
  "domain": "user"
}
```

**Assign permissions to role:**
```bash
POST /api/admin/role/{role_id}/permissions
{
  "permission_ids": ["article:read", "article:write"]
}
```

**Via code:**
```python
from swx_core.models.role import Role, RoleCreate

role = RoleCreate(
    name="editor",
    description="Can read and write articles",
    domain="user"
)

# Create role
created_role = await role_service.create_role_service(session, role)

# Assign permissions
await role_service.assign_permissions(
    session,
    created_role.id,
    ["article:read", "article:write"]
)
```

### Assigning Roles to Users

**Via API:**
```bash
POST /api/admin/user/{user_id}/roles
{
  "role_id": "role-uuid",
  "team_id": null  # Global role
}

# Or team-scoped
POST /api/admin/user/{user_id}/roles
{
  "role_id": "team-owner-uuid",
  "team_id": "team-uuid"  # Team-scoped
}
```

**Via code:**
```python
from swx_core.models.user_role import UserRole

# Global role
user_role = UserRole(
    user_id=user.id,
    role_id=viewer_role.id,
    team_id=None
)

# Team-scoped role
team_user_role = UserRole(
    user_id=user.id,
    role_id=team_owner_role.id,
    team_id=team.id
)

session.add(user_role)
session.add(team_user_role)
await session.commit()
```

---

## Common Patterns

### Pattern 1: Resource Ownership

**Check if user owns resource:**
```python
@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: UUID,
    user: UserDep,
    session: SessionDep,
):
    # Get article
    article = await get_article(session, article_id)
    
    # Check ownership or permission
    if article.author_id != user.id:
        # Not owner, check permission
        if not await has_permission(session, user, "article:delete"):
            raise HTTPException(403, "Permission denied")
    
    # Delete article
    await delete_article_service(session, article_id)
```

### Pattern 2: Team Membership Check

**Check team membership before permission:**
```python
async def get_team_resource(
    session: AsyncSession,
    user: User,
    team_id: UUID,
    resource_id: UUID,
):
    # Check team membership
    team_member = await get_team_member(session, team_id, user.id)
    if not team_member:
        raise HTTPException(403, "Not a team member")
    
    # Check permission
    if not await check_team_permission(session, user, team_id, "resource:read"):
        raise HTTPException(403, "Permission denied")
    
    # Get resource
    return await get_resource(session, resource_id)
```

### Pattern 3: Superuser Fallback

**Backward compatibility:**
```python
async def has_permission(
    session: AsyncSession,
    user: User,
    permission_name: str,
    team_id: Optional[UUID] = None,
) -> bool:
    # Superusers have all permissions (backward compatibility)
    if user.is_superuser:
        return True
    
    # Check RBAC permissions
    permissions = await get_user_permissions(session, user.id, team_id=team_id)
    return permission_name in [p.name for p in permissions]
```

---

## Best Practices

### ✅ DO

1. **Use explicit permissions**
   ```python
   # ✅ Good
   @router.get("/users", dependencies=[Depends(require_permission("user:read"))])
   
   # ❌ Bad
   @router.get("/users", dependencies=[Depends(require_role("admin"))])
   ```

2. **Follow naming convention**
   ```python
   # ✅ Good
   "user:read", "article:write", "team:manage"
   
   # ❌ Bad
   "read_user", "writeArticle", "manageTeam"
   ```

3. **Use team scoping for multi-tenancy**
   ```python
   # ✅ Good
   UserRole(user_id=user.id, role_id=role.id, team_id=team.id)
   
   # ❌ Bad
   UserRole(user_id=user.id, role_id=role.id, team_id=None)  # If team-specific
   ```

4. **Check permissions early**
   ```python
   # ✅ Good
   if not await has_permission(session, user, "resource:delete"):
       raise HTTPException(403, "Permission denied")
   
   # ❌ Bad
   # Check permission after expensive operation
   ```

5. **Use domain separation**
   ```python
   # ✅ Good
   admin_role = Role(name="admin", domain="admin")
   user_role = Role(name="editor", domain="user")
   
   # ❌ Bad
   mixed_role = Role(name="admin", domain="user")  # Confusing
   ```

### ❌ DON'T

1. **Don't use role checks for permissions**
   ```python
   # ❌ Bad
   if await has_role(session, user, "admin"):
       # Do something
   
   # ✅ Good
   if await has_permission(session, user, "resource:manage"):
       # Do something
   ```

2. **Don't hardcode permission strings**
   ```python
   # ❌ Bad
   if "user:read" in permission_names:
   
   # ✅ Good
   PERMISSION_USER_READ = "user:read"
   if PERMISSION_USER_READ in permission_names:
   ```

3. **Don't skip team membership checks**
   ```python
   # ❌ Bad
   if await has_permission(session, user, "team:read"):
       # Access team resource (but user might not be team member!)
   
   # ✅ Good
   if await check_team_permission(session, user, team_id, "team:read"):
       # Access team resource (membership + permission checked)
   ```

---

## Troubleshooting

### Common Issues

**1. "Permission denied" but user has role**
- Check if role has the required permission
- Verify `RolePermission` associations exist
- Check if permission name matches exactly

**2. Team-scoped permission not working**
- Verify `UserRole.team_id` is set (not `None`)
- Check user is team member (`TeamMember` exists)
- Verify team-scoped role has the permission

**3. Global permission not working**
- Check `UserRole.team_id` is `None` for global roles
- Verify role has the permission
- Check domain matches (admin vs user)

**4. Permission check always returns False**
- Verify user has roles assigned
- Check roles have permissions assigned
- Ensure `RolePermission` associations exist

### Debugging

**Check user permissions:**
```python
from swx_core.rbac.helpers import get_user_permissions

permissions = await get_user_permissions(session, user.id)
print([p.name for p in permissions])
```

**Check user roles:**
```python
from swx_core.rbac.helpers import get_user_roles

roles = await get_user_roles(session, user.id)
print([r.name for r in roles])
```

**Check role permissions:**
```python
from swx_core.repositories.role_permission_repository import get_role_permissions

permissions = await get_role_permissions(session, role.id)
print([p.name for p in permissions])
```

---

## Next Steps

- Read [Policy Engine Documentation](./POLICY_ENGINE.md) for ABAC policies
- Read [Security Model](../05-security/SECURITY_MODEL.md) for security details
- Read [API Usage Guide](../06-api-usage/API_USAGE.md) for API examples

---

**Status:** RBAC documented, ready for implementation.
