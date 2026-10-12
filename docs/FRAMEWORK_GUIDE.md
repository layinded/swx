# SWX Framework Guide

**Version:** 1.0.0  
**Last Updated:** 2024

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Authentication & Authorization](#authentication--authorization)
4. [RBAC System](#rbac-system)
5. [Domain Separation](#domain-separation)
6. [Token Management](#token-management)
7. [Database Models](#database-models)
8. [Best Practices](#best-practices)
9. [Migration Guide](#migration-guide)

---

## Overview

SWX is a production-ready FastAPI framework with:
- **Permission-first RBAC** - Fine-grained access control
- **Domain Separation** - Admin, User, and System domains
- **Multi-tenant Support** - Team-based isolation
- **Secure Token Handling** - Audience validation and scopes
- **Clean Architecture** - Separation of concerns

---

## Architecture

### Directory Structure

```
swx_api/
├── core/                    # Framework core
│   ├── auth/               # Authentication modules
│   │   ├── core/           # Shared JWT utilities
│   │   ├── admin/          # Admin domain auth
│   │   └── user/           # User domain auth
│   ├── models/             # Database models
│   │   ├── permission.py   # Permission model
│   │   ├── role.py         # Role model
│   │   ├── user.py         # User model
│   │   ├── admin_user.py   # AdminUser model
│   │   └── team.py         # Team model
│   ├── rbac/               # RBAC helpers
│   │   ├── helpers.py      # Permission checking
│   │   └── dependencies.py # FastAPI dependencies
│   ├── routes/             # API routes
│   │   ├── admin/          # Admin routes
│   │   └── user/           # User routes
│   └── security/           # Security utilities
└── app/                     # Application code (example)
```

### Domain Separation

The framework enforces three distinct domains:

1. **System Domain** - Internal system users, CLI, background jobs
2. **Admin Domain** - Admin users with admin-only access
3. **User Domain** - Regular application users with team-based access

Each domain has:
- Separate authentication flows
- Separate token audiences
- Separate models (AdminUser vs User)
- Isolated routes

---

## Authentication & Authorization

### User Domain Authentication

```python
from fastapi import APIRouter, Depends
from swx_api.core.auth.user.dependencies import get_current_user, UserDep

router = APIRouter(prefix="/api/user")

@router.get("/profile")
def get_profile(current_user: UserDep):
    """Only user domain tokens can access this."""
    return current_user
```

### Admin Domain Authentication

```python
from fastapi import APIRouter, Depends
from swx_api.core.auth.admin.dependencies import get_current_admin_user, AdminUserDep

router = APIRouter(prefix="/api/admin")

@router.get("/dashboard")
def admin_dashboard(admin: AdminUserDep):
    """Only admin domain tokens can access this."""
    return {"message": "Admin dashboard"}
```

### Token Audiences

Tokens are issued with explicit audiences:
- `"admin"` - Admin domain tokens
- `"user"` - User domain tokens
- `"system"` - System domain tokens

Tokens cannot be used across domains - admin tokens cannot access user endpoints and vice versa.

---

## RBAC System

### Permission-First Design

The framework uses a **permission-first** RBAC model:

1. **Permissions** are atomic actions (e.g., `"user:read"`, `"article:delete"`)
2. **Roles** are collections of permissions (e.g., `"admin"`, `"editor"`)
3. **Users** are assigned roles, which grant permissions

### Creating Permissions

```python
from swx_api.core.models.permission import Permission, PermissionCreate
from swx_api.core.database.db import SessionDep

def create_permission(session: SessionDep, permission: PermissionCreate):
    """Create a new permission."""
    db_permission = Permission(**permission.model_dump())
    session.add(db_permission)
    session.commit()
    return db_permission

# Example
permission = PermissionCreate(
    name="user:read",
    description="Read user information",
    resource_type="user",
    action="read"
)
```

### Creating Roles

```python
from swx_api.core.models.role import Role, RoleCreate
from swx_api.core.models.role_permission import RolePermission

def create_role_with_permissions(
    session: SessionDep,
    role_name: str,
    permission_names: list[str]
):
    """Create a role and assign permissions."""
    # Create role
    role = Role(
        name=role_name,
        description=f"{role_name} role",
        domain="user",
        is_system_role=False
    )
    session.add(role)
    session.flush()
    
    # Assign permissions
    for perm_name in permission_names:
        permission = session.exec(
            select(Permission).where(Permission.name == perm_name)
        ).first()
        if permission:
            role_perm = RolePermission(
                role_id=role.id,
                permission_id=permission.id
            )
            session.add(role_perm)
    
    session.commit()
    return role
```

### Assigning Roles to Users

```python
from swx_api.core.models.user_role import UserRole

def assign_role_to_user(
    session: SessionDep,
    user_id: UUID,
    role_name: str,
    team_id: Optional[UUID] = None
):
    """Assign a role to a user (optionally scoped to a team)."""
    role = session.exec(
        select(Role).where(Role.name == role_name)
    ).first()
    
    user_role = UserRole(
        user_id=user_id,
        role_id=role.id,
        team_id=team_id  # None for global role
    )
    session.add(user_role)
    session.commit()
    return user_role
```

### Using Permissions in Routes

```python
from swx_api.core.rbac.dependencies import require_permission

@router.get("/users", dependencies=[Depends(require_permission("user:read"))])
def list_users():
    """Requires 'user:read' permission."""
    ...

@router.post("/users", dependencies=[Depends(require_permission("user:write"))])
def create_user():
    """Requires 'user:write' permission."""
    ...

@router.delete("/users/{user_id}", dependencies=[Depends(require_permission("user:delete"))])
def delete_user(user_id: UUID):
    """Requires 'user:delete' permission."""
    ...
```

### Using Roles in Routes

```python
from swx_api.core.rbac.dependencies import require_role

@router.get("/admin", dependencies=[Depends(require_role("admin", domain="admin"))])
def admin_panel():
    """Requires 'admin' role in admin domain."""
    ...
```

### Team-Scoped Permissions

```python
from swx_api.core.rbac.dependencies import require_team_permission

@router.get("/teams/{team_id}/members", dependencies=[Depends(require_team_permission(team_id, "team:read"))])
def list_team_members(team_id: UUID):
    """Requires 'team:read' permission in the specific team."""
    ...
```

### Checking Permissions Programmatically

```python
from swx_api.core.rbac.helpers import has_permission, has_role

def some_business_logic(session: SessionDep, user: User, team_id: UUID):
    """Check permissions in business logic."""
    if has_permission(session, user, "article:edit", team_id=team_id):
        # User can edit articles in this team
        ...
    
    if has_role(session, user, "editor", team_id=team_id):
        # User has editor role in this team
        ...
```

---

## Domain Separation

### Admin Domain

**Model:** `AdminUser`  
**Auth Module:** `swx_api.core.auth.admin`  
**Token Audience:** `"admin"`  
**Routes:** `/api/admin/*`

```python
from swx_api.core.models.admin_user import AdminUser, AdminUserCreate
from swx_api.core.auth.admin.dependencies import AdminUserDep

# Admin routes
@router.get("/admin/users")
def list_all_users(admin: AdminUserDep):
    """Only admin users can access."""
    ...
```

### User Domain

**Model:** `User`  
**Auth Module:** `swx_api.core.auth.user`  
**Token Audience:** `"user"`  
**Routes:** `/api/user/*`

```python
from swx_api.core.models.user import User
from swx_api.core.auth.user.dependencies import UserDep

# User routes
@router.get("/user/profile")
def get_profile(user: UserDep):
    """Only regular users can access."""
    ...
```

### System Domain

**Purpose:** CLI, background jobs, internal system operations  
**No HTTP session assumption**  
**Explicit scopes only**

---

## Token Management

### Token Creation

Tokens are created with explicit audience and scopes:

```python
from swx_api.core.auth.core.jwt import create_token, TokenAudience
from datetime import timedelta

# Create user token with permissions
token = create_token(
    subject=user.email,
    audience=TokenAudience.USER,
    expires_delta=timedelta(hours=1),
    scopes=["user:read", "user:write"],  # User's permissions
    auth_provider="local"
)
```

### Token Validation

Tokens are validated with audience checking:

```python
from swx_api.core.auth.core.jwt import decode_token, TokenAudience

# Validate user token
payload = decode_token(token, TokenAudience.USER)

# This will fail if token has wrong audience
try:
    payload = decode_token(token, TokenAudience.ADMIN)  # Raises exception
except jwt.InvalidAudienceError:
    # Token is not for admin domain
    ...
```

### Token Scopes

Token scopes contain the user's permissions:

```python
from swx_api.core.auth.core.jwt import get_token_scopes

payload = decode_token(token, TokenAudience.USER)
scopes = get_token_scopes(payload)  # ["user:read", "user:write", ...]
```

---

## Database Models

### Core Models

#### Permission
```python
class Permission(SQLModel, table=True):
    id: UUID
    name: str  # e.g., "user:read"
    description: str
    resource_type: str  # e.g., "user"
    action: str  # e.g., "read"
```

#### Role
```python
class Role(SQLModel, table=True):
    id: UUID
    name: str  # e.g., "admin"
    description: str
    is_system_role: bool
    domain: Literal["admin", "user", "system"]
```

#### UserRole
```python
class UserRole(SQLModel, table=True):
    id: UUID
    user_id: UUID
    role_id: UUID
    team_id: Optional[UUID]  # For team-scoped roles
    resource_id: Optional[UUID]  # For resource-scoped roles
```

#### Team
```python
class Team(SQLModel, table=True):
    id: UUID
    name: str
    description: Optional[str]
    tenant_id: Optional[UUID]  # For multi-tenant support
```

#### TeamMember
```python
class TeamMember(SQLModel, table=True):
    id: UUID
    team_id: UUID
    user_id: UUID
    role_id: UUID  # Role within the team
```

---

## Best Practices

### 1. Always Use Explicit Dependencies

**❌ Bad:**
```python
# Implicit protection (removed from framework)
if "admin" in path:
    add_admin_protection()
```

**✅ Good:**
```python
from swx_api.core.auth.admin.dependencies import AdminUserDep

@router.get("/admin/endpoint")
def admin_endpoint(admin: AdminUserDep):
    ...
```

### 2. Use Permission Checks, Not Role Checks

**❌ Bad:**
```python
if user.is_superuser:
    # Too broad
    ...
```

**✅ Good:**
```python
from swx_api.core.rbac.dependencies import require_permission

@router.delete("/users/{id}", dependencies=[Depends(require_permission("user:delete"))])
def delete_user(id: UUID):
    ...
```

### 3. Scope Permissions to Teams When Needed

**❌ Bad:**
```python
# Global permission check
if has_permission(session, user, "article:edit"):
    # User can edit ANY article
    ...
```

**✅ Good:**
```python
# Team-scoped permission check
if has_permission(session, user, "article:edit", team_id=article.team_id):
    # User can edit articles in this team only
    ...
```

### 4. Separate Admin and User Operations

**❌ Bad:**
```python
# Same route for admin and user
@router.get("/users/{id}")
def get_user(id: UUID, current_user: User):
    if current_user.is_superuser:
        # Admin logic
    else:
        # User logic
```

**✅ Good:**
```python
# Separate routes
@router.get("/admin/users/{id}")
def admin_get_user(id: UUID, admin: AdminUserDep):
    # Admin logic
    ...

@router.get("/user/profile")
def user_get_profile(user: UserDep):
    # User logic
    ...
```

### 5. Use Token Scopes for Performance

**❌ Bad:**
```python
# Check database on every request
permissions = get_user_permissions(session, user.id)
if "user:read" in permissions:
    ...
```

**✅ Good:**
```python
# Check token scopes (already in token)
from swx_api.core.auth.core.jwt import get_token_scopes

scopes = get_token_scopes(payload)
if "user:read" in scopes:
    ...
```

---

## Migration Guide

### From Old Auth System

#### Step 1: Update Imports

**Old:**
```python
from swx_api.core.security.dependencies import get_current_user, CurrentUser
```

**New:**
```python
from swx_api.core.auth.user.dependencies import get_current_user, UserDep
```

#### Step 2: Update Admin Routes

**Old:**
```python
from swx_api.core.security.dependencies import get_current_active_superuser, AdminUser

@router.get("/admin/endpoint")
def admin_endpoint(admin: AdminUser):
    ...
```

**New:**
```python
from swx_api.core.auth.admin.dependencies import get_current_admin_user, AdminUserDep

@router.get("/admin/endpoint")
def admin_endpoint(admin: AdminUserDep):
    ...
```

#### Step 3: Replace Role Checks with Permissions

**Old:**
```python
from swx_api.core.security.dependencies import require_roles

@router.get("/admin", dependencies=[Depends(require_roles("admin"))])
def admin_dashboard():
    ...
```

**New:**
```python
from swx_api.core.rbac.dependencies import require_permission

@router.get("/admin", dependencies=[Depends(require_permission("admin:dashboard"))])
def admin_dashboard():
    ...
```

#### Step 4: Run Database Migrations

```bash
alembic upgrade head
```

This will create:
- RBAC tables (permission, role, role_permission, user_role)
- Team tables (team, team_member)
- AdminUser table

#### Step 5: Seed Default Permissions and Roles

Create a migration or script to seed:
- Default permissions (e.g., "user:read", "user:write", "user:delete")
- Default roles (e.g., "admin", "editor", "viewer")
- Role-permission mappings

---

## Common Patterns

### Pattern 1: Resource Ownership Check

```python
@router.delete("/articles/{article_id}")
def delete_article(
    article_id: UUID,
    user: UserDep,
    session: SessionDep
):
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    
    # Check if user owns the article OR has delete permission
    if article.owner_id != user.id:
        if not has_permission(session, user, "article:delete", team_id=article.team_id):
            raise HTTPException(403, "Not authorized")
    
    session.delete(article)
    session.commit()
    return {"message": "Deleted"}
```

### Pattern 2: Team-Based Access Control

```python
@router.get("/teams/{team_id}/articles")
def list_team_articles(
    team_id: UUID,
    user: UserDep,
    session: SessionDep
):
    # Check team membership
    team_member = session.exec(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user.id
        )
    ).first()
    
    if not team_member:
        raise HTTPException(403, "Not a team member")
    
    # Check permission
    if not has_permission(session, user, "article:read", team_id=team_id):
        raise HTTPException(403, "No read permission")
    
    articles = session.exec(
        select(Article).where(Article.team_id == team_id)
    ).all()
    
    return articles
```

### Pattern 3: Admin-Only Operations

```python
@router.post("/admin/users")
def create_user_admin(
    user_data: UserCreate,
    admin: AdminUserDep,
    session: SessionDep
):
    """Only admin users can create users."""
    # Admin can create users with any role
    user = create_user(session, user_data)
    
    # Assign default role
    default_role = session.exec(
        select(Role).where(Role.name == "user")
    ).first()
    
    if default_role:
        user_role = UserRole(
            user_id=user.id,
            role_id=default_role.id
        )
        session.add(user_role)
        session.commit()
    
    return user
```

---

## Security Considerations

### 1. Token Audience Validation

Always validate token audience - tokens from one domain cannot access another domain's endpoints.

### 2. Permission Granularity

Create specific permissions rather than broad ones:
- ✅ `"user:read"`, `"user:write"`, `"user:delete"`
- ❌ `"user:all"`

### 3. Team Isolation

Always check team membership before allowing team-scoped operations.

### 4. Superuser Backward Compatibility

The `is_superuser` flag still works for backward compatibility, but new code should use RBAC.

---

## Troubleshooting

### Issue: "Token audience mismatch"

**Cause:** Using a token from the wrong domain.

**Solution:** Ensure you're using the correct dependency:
- User routes → `UserDep`
- Admin routes → `AdminUserDep`

### Issue: "Permission denied"

**Cause:** User doesn't have the required permission.

**Solution:** 
1. Check if user has the role with the permission
2. Check if role has the permission assigned
3. For team-scoped operations, check team membership

### Issue: "Admin user not found"

**Cause:** Admin user doesn't exist in `admin_user` table.

**Solution:** Create admin user in `admin_user` table (separate from `users` table).

---

## Additional Resources

- [Architecture Audit](AUDIT_ARCHITECTURE.md)
- [Security Audit](AUDIT_SECURITY.md)
- [RBAC Audit](AUDIT_RBAC.md)
- [Progress Update](PROGRESS_UPDATE.md)
- [Final Status](FINAL_STATUS.md)

---

**Framework Version:** 1.0.0  
**Last Updated:** 2024
