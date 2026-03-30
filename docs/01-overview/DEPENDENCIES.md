# Dependencies

SwX uses optional dependencies to keep the core lightweight. Install only what you need.

## Installation Options

### Minimal Install (Default)

```bash
pip install swx-core
```

Core only (~19 packages):
- FastAPI, Uvicorn
- SQLModel, SQLAlchemy, Alembic, asyncpg, psycopg
- Pydantic, pydantic-settings
- Passlib, bcrypt, PyJWT, authlib
- Redis, httpx, tenacity, jinja2, click

### Extended (Most Applications)

```bash
pip install swx-core[extended]
```

Adds: httpx (if not already included)

### With Billing (Stripe)

```bash
pip install swx-core[billing]
```

Adds: stripe

Then enable in `.env`:
```bash
BILLING_ENABLED=true
STRIPE_API_KEY=sk_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

### With Monitoring (Sentry + Prometheus)

```bash
pip install swx-core[monitoring]
```

Adds: sentry-sdk, prometheus-client

Then enable in `.env`:
```bash
MONITORING_ENABLED=true
SENTRY_DSN=https://xxx@sentry.io/xxx
```

### With Background Jobs (Celery)

```bash
pip install swx-core[jobs]
```

Adds: celery

Then enable in `.env`:
```bash
JOBS_ENABLED=true
```

### With AI (Vector Embeddings)

```bash
pip install swx-core[ai]
```

Adds: pgai

Then enable in `.env`:
```bash
AI_ENABLED=true
```

### Production

```bash
pip install swx-core[prod]
```

Adds: gunicorn

### Full Installation

```bash
pip install swx-core[billing,monitoring,jobs,ai,prod]
```

## Feature Flags

Each optional feature has a corresponding environment variable:

| Feature | Flag | Required Env Vars |
|---------|------|-------------------|
| Billing | `BILLING_ENABLED` | `STRIPE_API_KEY` |
| Monitoring | `MONITORING_ENABLED` | `SENTRY_DSN` |
| Jobs | `JOBS_ENABLED` | - |
| AI | `AI_ENABLED` | - |
| Redis | `REDIS_ENABLED` (default: true) | `REDIS_HOST`, `REDIS_PORT` |

## Import Behavior

When an optional package is not installed:
- Import attempts fail gracefully with `None`
- Features are disabled even if flag is set to `true`
- No errors unless you explicitly use the feature

## Package Size Comparison

| Install Type | Packages | Approx Size |
|--------------|----------|-------------|
| `swx-core` | ~19 | ~40MB |
| `swx-core[extended]` | ~20 | ~45MB |
| `swx-core[billing]` | ~25 | ~55MB |
| `swx-core[full]` | ~50 | ~110MB |

Compare to previous version: ~50 packages required for any install.