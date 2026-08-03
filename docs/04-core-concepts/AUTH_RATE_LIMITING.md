# Auth Rate Limiting

**Version:** 1.0.0  
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [How It Works](#how-it-works)
3. [RateLimitRule Reference](#ratelimitrule-reference)
4. [Configuration](#configuration)
5. [Usage Examples](#usage-examples)
6. [SSE Compatibility](#sse-compatibility)

---

## Overview

The **Auth Rate Limit Middleware** provides declarative, per-path rate limiting for authentication endpoints. It's a pure-ASGI implementation (no `BaseHTTPMiddleware`) that works correctly with Server-Sent Events streaming.

Key features:

- **Declarative rules** — define rate limits as a JSON configuration
- **Per-namespace tracking** — each rule has a unique namespace for independent counting
- **Sliding window** — in-memory sliding window counter with per-IP granularity
- **Path matching** — prefix or exact path matching with HTTP method filtering
- **SSE-compatible** — pure ASGI, doesn't buffer response bodies
- **Opt-in** — when no rules are configured, the middleware is a no-op

Module: `swx_core/middleware/auth_rate_limit.py`

---

## How It Works

```
Request → AuthRateLimitMiddleware
  │
  ├─ No rules configured? → Pass through
  │
  ├─ For each rule:
  │   ├─ Rule doesn't match (path/method)? → Skip
  │   ├─ Rule matches → Check rate limit for client IP
  │   │   ├─ Under limit → Pass through, increment counter
  │   │   └─ Over limit → Return 429 with Retry-After header
  │   └─ No rule matched → Pass through
```

---

## RateLimitRule Reference

```python
@dataclass(frozen=True)
class RateLimitRule:
    namespace: str          # Unique name (e.g., "auth:login")
    path_prefix: str = ""  # Path prefix to match (e.g., "/api/auth/login")
    exact_path: str = ""    # Exact path to match (e.g., "/api/auth/verify")
    methods: tuple = ()     # HTTP methods (e.g., ("POST",)), empty = all
    max_requests: int = 5   # Max requests in the window
    window_seconds: int = 60 # Time window in seconds
```

### Rule Matching Logic

```python
rule.matches(method, path)
# 1. If methods is set and method not in methods → False
# 2. If exact_path is set → path == exact_path
# 3. If path_prefix is set → path.startswith(path_prefix)
# 4. Otherwise → False (rule doesn't match)
```

---

## Configuration

### Environment Variable

```bash
# .env
SWX_AUTH_RATE_LIMIT_RULES=[
  {"namespace":"auth:login","path_prefix":"/api/auth/login","methods":["POST"],"max_requests":5,"window_seconds":60},
  {"namespace":"auth:register","path_prefix":"/api/auth/register","methods":["POST"],"max_requests":3,"window_seconds":3600},
  {"namespace":"auth:refresh","exact_path":"/api/auth/refresh","methods":["POST"],"max_requests":10,"window_seconds":60},
  {"namespace":"auth:password","path_prefix":"/api/auth/password-recover","methods":["POST"],"max_requests":3,"window_seconds":3600}
]
```

### Registration

```python
from swx_core.middleware.auth_rate_limit import apply_middleware
from fastapi import FastAPI

app = FastAPI()
apply_middleware(app)
```

Or add rules programmatically:

```python
from swx_core.middleware.auth_rate_limit import AuthRateLimitMiddleware, RateLimitRule

rules = [
    RateLimitRule(namespace="auth:login", path_prefix="/api/auth/login", methods=("POST",), max_requests=5, window_seconds=60),
    RateLimitRule(namespace="auth:register", path_prefix="/api/auth/register", methods=("POST",), max_requests=3, window_seconds=3600),
]
app.add_middleware(AuthRateLimitMiddleware, rules=rules)
```

---

## Usage Examples

### 429 Response Format

When rate limited, the middleware returns:

```json
{
    "success": false,
    "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "Rate limit exceeded for auth:login.",
        "details": {
            "namespace": "auth:login",
            "retry_after": 45
        }
    }
}
```

With headers:
- `Retry-After: 45`
- `X-RateLimit-Limit: 5`

---

## SSE Compatibility

This middleware is a **pure-ASGI** implementation — it does NOT use `BaseHTTPMiddleware`, which buffers response bodies and breaks SSE streaming endpoints. It reads `request.state` attributes set by upstream rate limiting and attaches headers to the response without consuming the body.