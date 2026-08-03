# Auth Guards

**Version:** 1.0.0  
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [Guard Manager](#guard-manager)
3. [JWT Guard](#jwt-guard)
4. [API Key Guard](#api-key-guard)
5. [Service Token Guard](#service-token-guard)
6. [Combined Auth Guard](#combined-auth-guard)
7. [Usage Examples](#usage-examples)

---

## Overview

SwX-Core provides multiple **auth guards** as FastAPI dependencies for authentication:

- **JWT Guard** — validates `Authorization: Bearer <token>` headers
- **API Key Guard** — validates `X-Api-Key` headers against database keys
- **Service Token Guard** — validates `X-Service-Token` headers for service-to-service calls
- **Combined Auth Guard** — tries JWT first, then falls back to API key

All guards return an `AuthenticatedUser` dataclass for consistent downstream handling.

Module: `swx_core/guards/`

---

## Guard Manager

The `GuardManager` (`swx_core/guards/guard_manager.py`) composes guards and provides a unified `authenticate()` method:

```python
from swx_core.guards.guard_manager import get_guard_manager

manager = get_guard_manager()
user = await manager.authenticate(request, guard="jwt")        # JWT only
user = await manager.authenticate(request, guard="api_key")   # API key only
```

---

## JWT Guard

Validates JWT tokens from the `Authorization: Bearer <token>` header.

- Verifies token signature, expiration, audience, and issuer
- Returns `AuthenticatedUser` with user details from token claims
- Raises `HTTPException(401)` on invalid or expired tokens

---

## API Key Guard

Validates API keys from the `X-Api-Key` header.

- Looks up the key hash in the database
- Returns `AuthenticatedUser` with API key owner details
- Raises `HTTPException(401)` on missing or invalid keys

---

## Service Token Guard

Validates the `X-Service-Token` header against the `SWX_SERVICE_TOKEN` setting.

```python
from swx_core.guards.service_token_guard import ServiceTokenDep

@router.post("/internal/sync")
async def sync_endpoint(svc: ServiceTokenDep):
    # svc is a ServicePrincipal with service_name and scopes
    return {"synced_by": svc.service_name}
```

| Header | Required | Description |
|---|---|---|
| `X-Service-Token` | Yes | Must match `SWX_SERVICE_TOKEN` setting |
| `X-Service-Name` | No | Service identity (defaults to `"service"`) |

Returns a `ServicePrincipal` with `service_name` and `scopes` (from `SWX_SERVICE_TOKEN_SCOPES`).

---

## Combined Auth Guard

Tries JWT authentication first, then falls back to API key. Returns `AuthenticatedUser` with `auth_mode` metadata (`"jwt"` or `"api_key"`).

```python
from swx_core.guards.combined_auth_guard import AuthenticatedUserDep, OptionalAuthenticatedUserDep

# Required: raises 401 if neither guard succeeds
@router.get("/me")
async def get_me(user: AuthenticatedUserDep):
    return {"id": user.id, "auth_mode": user.metadata["auth_mode"]}

# Optional: returns None if unauthenticated
@router.get("/public-feed")
async def public_feed(user: OptionalAuthenticatedUserDep):
    if user:
        return personalized_feed(user)
    return default_feed()
```

---

## Usage Examples

### Requiring Authentication

```python
from swx_core.guards.combined_auth_guard import AuthenticatedUserDep

@router.delete("/users/{user_id}")
async def delete_user(user_id: UUID, user: AuthenticatedUserDep):
    # user is guaranteed to be authenticated (JWT or API key)
    ...
```

### Service-to-Service Auth

```python
from swx_core.guards.service_token_guard import ServiceTokenDep

@router.post("/internal/batch-process")
async def batch_process(svc: ServiceTokenDep):
    logger.info("Batch process triggered by %s", svc.service_name)
    ...
```

### Guard-Specific Auth

```python
from swx_core.guards.guard_manager import get_guard_manager

# In a custom dependency
async def require_jwt(request: Request):
    manager = get_guard_manager()
    user = await manager.authenticate(request, guard="jwt")
    if user is None:
        raise HTTPException(401, "JWT authentication required")
    return user
```