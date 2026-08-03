# Security Headers Middleware

**Version:** 1.0.0  
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [Headers Applied](#headers-applied)
3. [Configuration](#configuration)
4. [SSE Compatibility](#sse-compatibility)
5. [Usage Examples](#usage-examples)

---

## Overview

The **Security Headers Middleware** (`swx_core/middleware/security_headers_middleware.py`) is a pure-ASGI middleware that injects security response headers without buffering the response body. It replaces the previous `BaseHTTPMiddleware` implementation which broke Server-Sent Events streaming.

Key features:

- **Pure ASGI** — streams responses through without consuming the body
- **SSE-aware** — uses `cross-origin` for `text/event-stream` and `same-origin` otherwise
- **Environment-aware** — adds HSTS headers only in production
- **Docs-path exemption** — relaxes CSP on `/docs`, `/redoc`, `/openapi.json`

---

## Headers Applied

| Header | Value | Condition |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Always (if `content_type_nosniff=True`) |
| `X-Frame-Options` | `DENY` (default) | Always |
| `X-XSS-Protection` | `0` (modern best practice) | Always |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Always |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Always |
| `Cross-Origin-Resource-Policy` | `cross-origin` (SSE) / `same-origin` (other) | Content-type dependent |
| `Cross-Origin-Opener-Policy` | `same-origin` | Always |
| `Cross-Origin-Embedder-Policy` | `require-corp` | Always |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` | Not on docs paths |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` | Production only |

---

## Configuration

```python
from swx_core.middleware.security_headers_middleware import SecurityHeadersConfig, SecurityHeadersMiddleware

config = SecurityHeadersConfig(
    hsts_max_age=63072000,
    hsts_include_subdomains=True,
    hsts_preload=True,
    content_type_nosniff=True,
    frame_options="DENY",
    referrer_policy="strict-origin-when-cross-origin",
    permissions_policy="geolocation=(), microphone=(), camera=()",
    xss_protection="0",
    corp_for_sse="cross-origin",
    corp_default="same-origin",
    csp_api="default-src 'none'; frame-ancestors 'none'",
    environment="production",
)
```

---

## SSE Compatibility

This middleware is **pure ASGI** — it does NOT use `BaseHTTPMiddleware`. It intercepts only the `http.response.start` message to inject headers, then passes the response body through untouched. This preserves SSE streaming endpoints which require chunked transfer encoding.

---

## Usage Examples

### Registration

```python
from swx_core.middleware.security_headers_middleware import setup_security_headers
from fastapi import FastAPI

app = FastAPI()
setup_security_headers(app)
```

### Custom Configuration

```python
from swx_core.middleware.security_headers_middleware import SecurityHeadersMiddleware, SecurityHeadersConfig

config = SecurityHeadersConfig(
    frame_options="SAMEORIGIN",
    csp_api="default-src 'self'; script-src 'self'",
)
app.add_middleware(SecurityHeadersMiddleware, config=config)
```