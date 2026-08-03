# Region Routing

**Version:** 1.0.0  
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [How It Works](#how-it-works)
3. [Configuration](#configuration)
4. [Usage Examples](#usage-examples)
5. [Downstream Consumption](#downstream-consumption)

---

## Overview

The **Region Routing Middleware** resolves a geographic region from the incoming request (via a configurable header, defaulting to `CF-IPCountry` for CloudFront/Cloudflare) and stores it on `request.state.region` for downstream consumption.

Key features:

- **Opt-in** — when no `SWX_REGIONS` mapping is configured, the middleware is a no-op pass-through
- **Pure ASGI** — no `BaseHTTPMiddleware`, works correctly with SSE streaming
- **Configurable header** — supports any header (default: `CF-IPCountry`)
- **X-Forwarded-For fallback** — falls back to client IP if the header is missing

Module: `swx_core/middleware/region_routing.py`

---

## How It Works

```
Request → RegionRoutingMiddleware
  │
  ├─ No regions configured? → Pass through (no-op)
  │
  ├─ Read country from SWX_REGION_HEADER (default: CF-IPCountry)
  │
  ├─ Map country → region using SWX_REGIONS config
  │
  └─ Store on request.state.region (str | None)
```

### Region Resolution Logic

```python
# resolve_region("DE", {"eu": ["DE", "FR", "NL"], "us": ["US", "CA"]})
# → "eu"

# resolve_region("JP", {"eu": ["DE", "FR"], "us": ["US", "CA"]})
# → None  (country not in any region)
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SWX_REGIONS` | `None` | JSON mapping of region → list of country codes. Example: `{"eu":["DE","FR","NL"],"us":["US","CA","MX"]}` |
| `SWX_REGION_HEADER` | `CF-IPCountry` | HTTP header carrying the country code |

### Registration

```python
from swx_core.middleware.region_routing import apply_middleware
from fastapi import FastAPI

app = FastAPI()
apply_middleware(app)
```

Or add to your middleware stack manually:

```python
from swx_core.middleware.region_routing import RegionRoutingMiddleware, RegionRoutingConfig

config = RegionRoutingConfig(
    regions={"eu": ["DE", "FR", "NL"], "us": ["US", "CA", "MX"]},
    header_name="CF-IPCountry",
)
app.add_middleware(RegionRoutingMiddleware, config=config)
```

---

## Usage Examples

### Access Region in Route Handler

```python
from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/api/content")
async def get_content(request: Request):
    region = getattr(request.state, "region", None)
    if region == "eu":
        return {"content": "EU-specific content"}
    return {"content": "Default content"}
```

### Environment Configuration

```bash
# .env
SWX_REGIONS={"eu":["DE","FR","NL","ES","IT"],"us":["US","CA","MX"],"apac":["JP","KR","AU"]}
SWX_REGION_HEADER=CF-IPCountry
```

---

## Downstream Consumption

The `request.state.region` value can be used by:

- **Content localization** — serve different content per region
- **Compliance** — apply GDPR rules for EU users
- **Rate limiting** — per-region rate limit policies
- **Analytics** — track regional usage patterns
- **Feature flags** — enable features per region