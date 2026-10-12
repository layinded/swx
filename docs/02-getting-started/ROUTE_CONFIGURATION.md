# Route Configuration

**Version:** 1.0.0
**Last Updated:** 2026-05-29

---

## Overview

swx-core provides flexible route mounting with configurable prefixes for both core framework routes and application routes.

---

## Configuration Settings

### ROUTE_PREFIX

**Type:** `str`
**Default:** `/api`
**Description:** Base prefix for all routes.

```env
ROUTE_PREFIX=/api
```

### CORE_ROUTE_PREFIX

**Type:** `str`
**Default:** `""` (empty string)
**Description:** Prefix for core framework routes (auth, admin, etc.).

| Value | Core Auth Endpoint | Use Case |
|-------|-------------------|----------|
| `""` (empty) | `/api/auth` | Default, core routes at root |
| `/v1` | `/api/v1/auth` | Consistent with versioned app routes |
| `/core` | `/api/core/auth` | Separate core namespace |

```env
# Example: Mount core routes under /api/v1/
CORE_ROUTE_PREFIX=/v1
```

### API_VERSIONS

**Type:** `List[str]`
**Default:** `["v1", "v2"]`
**Description:** Supported API versions for app routes.

```env
API_VERSIONS=v1,v2,v3
```

---

## Route Structure

### Default Behavior

```
Core Routes:
  /api/auth/login           # User auth
  /api/admin/auth/login     # Admin auth
  /api/oauth/google         # OAuth

App Routes (versioned):
  /api/v1/users             # User resources
  /api/v1/products          # Product resources
  /api/v2/analytics         # V2 endpoints
```

### With CORE_ROUTE_PREFIX="/v1"

```
Core Routes:
  /api/v1/auth/login        # Core auth now versioned
  /api/v1/admin/auth/login  # Admin auth versioned
  /api/v1/oauth/google      # OAuth versioned

App Routes (versioned):
  /api/v1/users             # Still at /api/v1/
  /api/v1/products
  /api/v2/analytics
```

### With CORE_ROUTE_PREFIX="/core"

```
Core Routes:
  /api/core/auth/login      # Core routes in /core namespace
  /api/core/admin/auth/login
  /api/core/oauth/google

App Routes:
  /api/v1/users
  /api/v2/products
```

---

## Migration Guide

### For Existing swx_app Projects

**Problem:** swx_core mounts at `/api/auth` while swx_app expects `/api/v1/auth`.

**Solution 1: Set CORE_ROUTE_PREFIX (Recommended)**

```env
# .env
CORE_ROUTE_PREFIX=/v1
```

Now core routes match app routes:
```
/api/v1/auth/login      # Core
/api/v1/users           # App
```

**Solution 2: Dual Route Mounting (Backward Compatible)**

Mount core routes under both prefixes:

```python
# app/main.py
from swx_core.router import router as core_router

# Core routes already mounted at /api/auth by default
# Add additional mount at /api/v1/auth
app.include_router(
    core_router,
    prefix="/api/v1",
    tags=["Core API (Legacy Path)"]
)
```

**Solution 3: No Changes (Just Documentation)**

Document that core routes are at `/api/auth` while app routes use `/api/v1/`. This is the simplest approach if clients can be updated.

---

## Route Discovery

### How Routes Are Found

1. **Core routes** - Scanned from `swx_core/routes/`
2. **App routes** - Scanned from `swx_app/routes/` (via `discovery`)

```python
# Route discovery order
swx_core/routes/access/auth_route.py     → /api/auth
swx_core/routes/admin/auth_route.py      → /api/admin/auth
swx_app/routes/v1/users/                 → /api/v1/users
swx_app/routes/v2/analytics/             → /api/v2/analytics
```

### Custom Route Discovery

Override discovery paths in your app:

```python
from swx_core.config.discovery import discovery

# Check where swx_core looks for routes
print(discovery.app_routes_path)      # /path/to/app/routes
print(discovery.app_routes_module)    # app.routes
```

---

## Advanced Configuration

### Multiple API Gateway Patterns

```env
# External API Gateway strips /api prefix
# Configure for direct path access
ROUTE_PREFIX=

# Routes become:
# /auth/login
# /v1/users
# /v2/analytics
```

### Namespace Isolation

```env
# Isolate core routes from app routes
CORE_ROUTE_PREFIX=/core

# Routes become:
# /api/core/auth/login     # Core
# /api/v1/users             # App
# No conflict between core and app
```

### Multi-Tenant Routing

For multi-tenant applications, route prefixes remain global:

```
/api/auth/login           # Auth is shared across tenants
/api/v1/users             # Users filtered by tenant context
```

Tenant isolation is handled by middleware, not routing. See [Multi-Tenant](../04-core-concepts/MULTI_TENANT.md).

---

## Troubleshooting

### Routes Not Found

**Check:**
1. `ROUTE_PREFIX` is set correctly
2. Module has `router` attribute
3. Routes are in `routes/` directory

```bash
# Debug route registration
python -c "from swx_core.router import router; print([r.path for r in router.routes])"
```

### Duplicate Route Prefixes

**Problem:** Routes show double prefix like `/api/api/auth`

**Solution:** Router prefix is empty or already includes `/api`

```python
# Wrong - prefix already includes /api
router = APIRouter(prefix="/api/auth")

# Correct - just the route segment
router = APIRouter(prefix="/auth")
```

### Version Not Loading

**Problem:** `v1` routes not registered

**Solution:** Ensure `API_VERSIONS` includes the version

```env
API_VERSIONS=v1,v2  # v1 must be in the list
```

---

## Related Documentation

- [Getting Started](GETTING_STARTED.md) - Initial setup
- [Architecture](../03-architecture/ARCHITECTURE.md) - System design
- [Multi-Tenant](../04-core-concepts/MULTI_TENANT.md) - Tenant isolation