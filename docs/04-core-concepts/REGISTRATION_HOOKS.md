# Registration Hooks & Extension Points

**Version:** 2.20.0
**Last Updated:** 2026-08-11

---

## Overview

swx-core provides multiple extension points for customizing user registration:

1. **Lifecycle Hooks** - `pre_register_hook` and `post_register_hook` parameters, plus built-in default hooks
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
    post_register_hook: Callable[[User, AsyncSession, dict], Awaitable[User | None]] | None = None,
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
from sqlalchemy.ext.asyncio import AsyncSession
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
async def setup_organization(user: User, session: AsyncSession, context: dict) -> User:
    from my_app.services.organization import create_organization
    
    org_name = context.get("organization_name", f"{user.full_name}'s Organization")
    org = await create_organization(
        owner_id=user.id,
        name=org_name,
        session=session,
    )
    
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
async def send_welcome(user: User, session: AsyncSession, context: dict) -> None:
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

## 2.5 Default Registration Hooks

swx-core provides built-in hooks that run automatically after registration:

### Auto-Assigned Default Role

When `AUTO_ASSIGN_DEFAULT_ROLE=True` (default), newly registered users receive the role specified by `DEFAULT_USER_ROLE` (default: `"user"`).

**Configuration (`.env`):**
```bash
AUTO_ASSIGN_DEFAULT_ROLE=true
DEFAULT_USER_ROLE=user
```

The role must exist in the `swx_role` table. Run `python scripts/seed_system.py` to create default roles.

### Auto-Created Billing Account

When `AUTO_CREATE_BILLING_ACCOUNT=True` (default) and `BILLING_ENABLED=True`, a `USER` billing account with a subscription to the `DEFAULT_PLAN_KEY` plan (default: `"free"`) is created for each new user.

**Configuration (`.env`):**
```bash
AUTO_CREATE_BILLING_ACCOUNT=true
DEFAULT_PLAN_KEY=free
BILLING_ENABLED=true
```

### Auto-Created Personal Team (v2.7.27)

When `AUTO_CREATE_PERSONAL_TEAM=True` (default), each new user gets a personal team with `tenant_id` set automatically. This ensures users always have a valid `tenant_id` for multi-tenant operations.

As of v2.20.0, this hook also creates a TEAM billing account with a trial subscription when `BILLING_ENABLED=True` and `TRIAL_DAYS > 0`. This fixes the issue where quota enforcement and plan tier resolution checked at the TEAM level but found no subscription, causing `QuotaExceededError` for new trial users.

**Configuration (`.env`):**
```bash
AUTO_CREATE_PERSONAL_TEAM=true
BILLING_ENABLED=true
TRIAL_DAYS=30
TRIAL_PLAN_KEY=enterprise
DEFAULT_PLAN_KEY=free
```

**What happens on registration:**
1. Creates a `Team` with `name="{user}'s Team"` and `owner_id=user.id`
2. Adds user as team member with `owner` role
3. Sets `user.tenant_id = team.id`
4. Creates a TEAM `BillingAccount` via `SubscriptionService.get_or_create_account()`
5. Creates a trial subscription via `SubscriptionService.create_trial_subscription()` with status `TRIALING` and `trial_ends_at = now + TRIAL_DAYS`

**Disable trial (still creates team, no billing):**
```bash
BILLING_ENABLED=false
# or
TRIAL_DAYS=0
```

### Disabling Default Hooks

To disable any hook, set the corresponding environment variable to `false`:

```bash
AUTO_ASSIGN_DEFAULT_ROLE=false
AUTO_CREATE_BILLING_ACCOUNT=false
AUTO_CREATE_PERSONAL_TEAM=false
```

### OAuth / Social Login Hooks (v2.19.8)

> **Bug fix:** Prior to v2.19.8, OAuth callbacks (Google, Facebook, generic provider) called `register_user_service()` directly **without** passing `pre_register_hook` or `post_register_hook`. This meant social-login users never received the default hooks — no personal team, no default role, no billing account. This is now fixed: all three OAuth callbacks pass `registration_hooks.pre_register` and `registration_hooks.post_register`, matching the email-registration path through `register_controller`.

If you have custom OAuth routes that call `register_user_service()` directly, make sure to pass the hooks:

```python
from swx_core.core.hooks import registration_hooks
from swx_core.services.auth_service import register_user_service

user = await register_user_service(
    session=session,
    user_in=user_in,
    request=request,
    auth_provider="google",
    provider_id=provider_id,
    event_context={"social_provider": "google"},
    pre_register_hook=registration_hooks.pre_register,
    post_register_hook=registration_hooks.post_register,
)
```

### Custom Hooks Alongside Defaults

You can register additional hooks alongside the defaults using `add_post_register()`:

```python
from swx_core.core.hooks import registration_hooks

async def send_welcome_email(user: User, session: AsyncSession, context: dict) -> User:
    await send_email(user.email, "Welcome!", "...")
    return user

# This adds to the hook chain, it does NOT replace the default hooks
registration_hooks.add_post_register(send_welcome_email)
```

---

## 2.6 Multi-Hook Registration System

As of v2.7.23, `RegistrationHookRegistry` supports multiple post-register hooks:

```python
from swx_core.core.hooks import registration_hooks

# add_post_register() — appends to the hook chain
registration_hooks.add_post_register(hook_a)
registration_hooks.add_post_register(hook_b)
registration_hooks.add_post_register(hook_c)

# set_post_register() — replaces ALL hooks with a single hook
registration_hooks.set_post_register(hook_x)  # Removes hook_a, hook_b, hook_c
```

Hooks run sequentially in registration order. If a hook raises an exception, it is logged and the next hook continues. The `user` object passed to each hook is always the original registered user (hooks are side-effect handlers, not transformers).

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

async def setup_tenant_resources(user: User, session: AsyncSession, context: dict) -> None:
    await create_tenant_defaults(user.tenant_id, session=session)
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

async def mark_invitation_used(user: User, session: AsyncSession, context: dict) -> None:
    await mark_invitation_as_used(context.get("invitation_code"), user.id, session=session)
```

### Enterprise SSO Registration

```python
async def sync_from_idp(user_in: UserCreate, context: dict) -> UserCreate:
    # Override name from SSO claims
    user_in.full_name = context.get("sso_name", user_in.full_name)
    user_in.auth_provider = "sso"
    return user_in

async def sync_groups(user: User, session: AsyncSession, context: dict) -> User:
    sso_groups = context.get("sso_groups", [])
    await sync_user_groups(user.id, sso_groups, session=session)
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