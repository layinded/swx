# CSRF Protection

**Version:** 1.0.0  
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [How It Works](#how-it-works)
3. [Cookie Lifecycle](#cookie-lifecycle)
4. [Configuration](#configuration)
5. [Usage Examples](#usage-examples)

---

## Overview

The **CSRF Middleware** (`swx_core/middleware/csrf_middleware.py`) protects against Cross-Site Request Forgery attacks for cookie-based authentication using the Double Submit Cookie pattern. It is a pure-ASGI implementation compatible with SSE streaming.

Key features:

- **Double Submit Cookie** — validates `csrf_token` cookie against `X-CSRF-Token` header
- **Cookie lifecycle management** — auto-sets on login/refresh, auto-deletes on logout
- **Bearer/API-key bypass** — skips validation when `Authorization: Bearer` or `X-Api-Key` is present
- **Lazy cookie set** — sets CSRF cookie if auth cookies exist but CSRF cookie is missing
- **Path exemptions** — health checks, OpenAPI docs, and other utility paths are exempt
- **Pure ASGI** — no `BaseHTTPMiddleware`, preserves SSE streaming

---

## How It Works

```
Request → CSRFMiddleware
  │
  ├─ Bearer or API-key auth? → Skip validation, set cookie if needed
  │
  ├─ GET/HEAD/OPTIONS? → Skip validation, set cookie if needed
  │
  ├─ Path exempt? → Skip validation
  │
  ├─ Login/refresh path? → Generate/set CSRF cookie, skip validation
  │
  ├─ Logout path? → Delete CSRF cookie
  │
  ├─ Protected method (POST/PUT/PATCH/DELETE)?
  │   ├─ Cookie + header match? → Allow
  │   ├─ Missing cookie or header? → 403
  │   └─ Mismatch? → 403
  │
  └─ Otherwise → Pass through
```

---

## Cookie Lifecycle

| Path | Action |
|---|---|
| `/api/auth/login` | Set CSRF cookie |
| `/api/auth/social/login` | Set CSRF cookie |
| `/api/auth/refresh` | Set CSRF cookie |
| `/api/auth/logout` | Delete CSRF cookie |
| Auth cookie present, no CSRF cookie | Lazy-set CSRF cookie |

---

## Configuration

| Setting | Default | Description |
|---|---|---|
| `CSRF_ENABLED` | `True` (prod), `False` (local) | Enable/disable CSRF protection |
| `CSRF_COOKIE_NAME` | `csrf_token` | Cookie name |
| `CSRF_HEADER_NAME` | `X-CSRF-Token` | Header name |
| `CSRF_COOKIE_MAX_AGE` | `86400` | Cookie max age in seconds |
| `CSRF_TOKEN_LENGTH` | `32` | Token length in bytes |

### Exempt Paths

```python
exempt_paths = {"/docs", "/openapi.json", "/redoc", "/"}
exempt_prefixes = ["/api/utils/health", "/api/utils/language"]
```

---

## Usage Examples

### Registration

```python
from swx_core.middleware.csrf_middleware import apply_middleware
from fastapi import FastAPI

app = FastAPI()
apply_middleware(app)
```

### Client-Side Usage

```javascript
// Include CSRF token in all state-changing requests
const token = document.cookie
  .split('; ')
  .find(row => row.startsWith('csrf_token='))
  ?.split('=')[1];

fetch('/api/resource', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': token,
  },
  body: JSON.stringify(data),
});
```

### Programmatic Token Generation

```python
from swx_core.middleware.csrf_middleware import generate_csrf_token, get_csrf_token, set_csrf_cookie
from fastapi import Request, Response

@router.get("/csrf-token")
async def csrf_token_endpoint(request: Request, response: Response):
    token = await get_csrf_token(request)
    set_csrf_cookie(response, token)
    return {"csrf_token": token}
```