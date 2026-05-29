# Registration Hooks & Extension Points

**Version:** 1.0.0
**Last Updated:** 2026-05-29

---

## Overview

swx-core provides multiple extension points for customizing user registration:

1. **Lifecycle Hooks** - `pre_register_hook` and `post_register_hook` parameters
2. **Event System** - Subscribe to `user.created` event
3. **Service Override** - Create custom registration service

---

## 1. Lifecycle Hooks (Recommended)

The `register_user_service` function accepts optional hook parameters for fine-grained control:

### Function Signature

```python
async def register_user_service(
    session: AsyncSession,
    user_in: UserCreate,
    request: Request,
    event_context: dict[str, Any] | None = None,
    pre_register_hook: Callable[[UserCreate, dict], Awaitable[UserCreate]] | None = None,
    post_register_hook: Callable[[User, dict], Awaitable[User | None]] | None = None,
) -> User
```

### pre_register_hook

Called **before** user creation. Use for:
- Validation
- Tenant assignment
- Data enrichment
- Conditional logic

**Example: Auto-assign tenant:**

```python
from swx_core.models.user import UserCreate
from swx_core.services.auth_service import register_user_service

async def assign_tenant(user_in: UserCreate, context: dict) -> UserCreate:
    # Access tenant from context or request
    tenant_id = context.get("tenant_id")
    if tenant_id:
        user_in.tenant_id = tenant_id
    return user_in

# In your controller
user = await register_user_service(
    session=session,
    user_in=user_data,
    request=request,
    event_context={"tenant_id": request.headers.get("X-Tenant-ID")},
    pre_register_hook=assign_tenant,
)
```

**Example: Validate invitation:**

```python
async def validate_invitation(user_in: UserCreate, context: dict) -> UserCreate:
    invitation_code = context.get("invitation_code")
    if not await is_valid_invitation(invitation_code):
        raise HTTPException(status_code=400, detail="Invalid invitation code")
    return user_in
```

### post_register_hook

Called **after** user creation. Use for:
- Organization/team setup
- Welcome emails
- Audit logging
- Default data creation

**Example: Create organization:**

```python
async def setup_organization(user: User, context: dict) -> User:
    from my_app.services.organization import create_organization
    
    org_name = context.get("organization_name", f"{user.full_name}'s Organization")
    org = await create_organization(
        owner_id=user.id,
        name=org_name,
    )
    
    # Optionally update user with org reference
    user.organization_id = org.id
    return user

# In your controller
user = await register_user_service(
    session=session,
    user_in=user_data,
    request=request,
    event_context={"organization_name": form_data.org_name},
    post_register_hook=setup_organization,
)
```

**Example: Send welcome email:**

```python
async def send_welcome(user: User, context: dict) -> None:
    from my_app.services.email import send_welcome_email
    await send_welcome_email(user.email, user.full_name)
    return None  # Return None to not modify user
```

### Hook Execution Order

```
1. pre_register_hook (modify UserCreate)
   ↓
2. Check existing user (skip if already exists)
   ↓
3. create_user (database insert)
   ↓
4. post_register_hook (side effects)
   ↓
5. Emit user.created event
   ↓
6. Return user
```

### Combining Hooks

```python
user = await register_user_service(
    session=session,
    user_in=user_data,
    request=request,
    event_context={
        "tenant_id": tenant_id,
        "organization_name": org_name,
        "invitation_code": code,
    },
    pre_register_hook=validate_and_assign,
    post_register_hook=setup_and_notify,
)
```

---

## 2. Event-Based Extension

Subscribe to the `user.created` event for decoupled post-registration logic:

### Using Listener Class

```python
# swx_app/listeners/registration_listener.py
from swx_core.events import Listener

class SetupTenantListener(Listener):
    event = "user.created"
    priority = 75  # Higher priority runs first

    async def handle(self, event):
        user_id = event.payload["id"]
        context = event.payload.get("context", {})
        
        tenant_id = context.get("tenant_id")
        if tenant_id:
            await assign_user_to_tenant(user_id, tenant_id)
```

### Using Event Bus Directly

```python
from swx_core.events.dispatcher import event_bus

@event_bus.subscribe("user.created")
async def on_user_created(event):
    user_data = event.payload["data"]
    context = event.payload.get("context", {})
    
    await create_default_settings(event.payload["id"])
    await send_welcome_email(user_data["email"])
```

### Event Payload Structure

```python
{
    "id": "user-uuid-123",
    "data": {
        "email": "user@example.com",
        "full_name": "John Doe",
        "auth_provider": "local",
    },
    "context": {  # Optional, from event_context parameter
        "tenant_id": "tenant-456",
        "source": "mobile_app",
    }
}
```

---

## 3. Service Override

For complete control, create a custom registration service:

```python
# swx_app/services/custom_auth.py
from swx_core.services.auth_service import register_user_service as base_register

async def register_user_service(
    session: AsyncSession,
    user_in: UserCreate,
    request: Request,
    **kwargs,
) -> User:
    # Pre-processing
    await validate_business_rules(user_in)
    
    # Call base registration
    user = await base_register(
        session=session,
        user_in=user_in,
        request=request,
        event_context=kwargs.get("event_context"),
        post_register_hook=setup_everything,
    )
    
    # Post-processing
    await notify_admins(user)
    
    return user
```

---

## When to Use Which Approach

| Approach | Best For | Coupling |
|----------|----------|----------|
| `pre_register_hook` | Validation, data modification | Tight (requires parameter) |
| `post_register_hook` | Side effects, user updates | Tight (requires parameter) |
| Event listener | Decoupled side effects | Loose (no parameter needed) |
| Service override | Complete custom flow | Tight (replaces function) |

---

## Common Patterns

### Multi-Tenant Registration

```python
async def assign_tenant(user_in: UserCreate, context: dict) -> UserCreate:
    tenant_id = context.get("tenant_id") or await create_default_tenant()
    user_in.tenant_id = tenant_id
    return user_in

async def setup_tenant_resources(user: User, context: dict) -> None:
    await create_tenant_defaults(user.tenant_id)
    await provision_tenant_storage(user.tenant_id)

user = await register_user_service(
    session=session,
    user_in=user_data,
    request=request,
    event_context={"tenant_id": request.headers.get("X-Tenant-ID")},
    pre_register_hook=assign_tenant,
    post_register_hook=setup_tenant_resources,
)
```

### Invitation-Based Registration

```python
async def validate_invitation(user_in: UserCreate, context: dict) -> UserCreate:
    code = context.get("invitation_code")
    invitation = await get_invitation(code)
    
    if not invitation or invitation.used:
        raise HTTPException(status_code=400, detail="Invalid invitation")
    
    user_in.team_id = invitation.team_id
    user_in.role = invitation.role
    return user_in

async def mark_invitation_used(user: User, context: dict) -> None:
    await mark_invitation_as_used(context.get("invitation_code"), user.id)
```

### Enterprise SSO Registration

```python
async def sync_from_idp(user_in: UserCreate, context: dict) -> UserCreate:
    # Override name from SSO claims
    user_in.full_name = context.get("sso_name", user_in.full_name)
    user_in.auth_provider = "sso"
    return user_in

async def sync_groups(user: User, context: dict) -> User:
    sso_groups = context.get("sso_groups", [])
    await sync_user_groups(user.id, sso_groups)
    return user
```

---

## Migrating from Event-Only Pattern

If you're currently using only events:

```python
# Before: Only event listener
@event_bus.subscribe("user.created")
async def handle_registration(event):
    user_id = event.payload["id"]
    await setup_tenant(user_id)  # Can't modify user_before creation
    await assign_defaults(user_id)

# After: Lifecycle hooks for better control
user = await register_user_service(
    session=session,
    user_in=user_data,
    request=request,
    event_context={"source": "migration"},
    pre_register_hook=validate_input,
    post_register_hook=setup_everything,
)
```

---

## Related Documentation

- [Event System](EVENT_SYSTEM.md) - Full event system reference
- [Authentication](AUTHENTICATION.md) - Auth flows and token security
- [Multi-Tenant](MULTI_TENANT.md) - Multi-tenancy implementation