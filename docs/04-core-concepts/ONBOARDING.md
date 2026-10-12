# Onboarding

**Version:** 1.0.0  
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Step Registration](#step-registration)
4. [API Reference](#api-reference)
5. [Configuration](#configuration)
6. [Database Schema](#database-schema)

---

## Overview

The **Onboarding Service** provides per-user step tracking for new-user onboarding flows. Steps are registered at application startup (not hardcoded), and the service computes completion percentage from the registered step keys.

Key features:

- **Registered steps** — step keys are defined at startup, not in the database
- **Idempotent initialization** — creating steps for a user skips existing steps
- **Completion tracking** — `complete_step()` and `skip_step()` with timestamps
- **Progress percentage** — computed from registered steps vs completed/skipped steps
- **Admin CLI** — `swx security:encrypt-secrets` for bulk operations

Module: `swx_core/services/onboarding/onboarding_service.py`  
Model: `swx_core/models/onboarding.py`

---

## Architecture

```
App Startup → register_onboarding_steps(["profile", "email_verify", "first_project"])
     │
User Signup → initialize_steps(session, user_id)
     │         → Creates pending rows for each registered step
     │
User Action → complete_step(session, user_id, "profile")
     │         → Marks step as completed with timestamp
     │
UI Query   → get_progress(session, user_id)
     │         → Returns { percentage, completed, skipped, steps }
```

---

## Step Registration

Register steps once at application startup:

```python
from swx_core.services.onboarding import register_onboarding_steps, get_registered_steps

# In your app startup (e.g., main.py lifespan)
register_onboarding_steps(["profile", "email_verify", "first_project", "team_setup"])
```

Steps are idempotent — calling `register_onboarding_steps` multiple times will not duplicate entries.

---

## API Reference

### `register_onboarding_steps(steps: list[str])`

Register onboarding step keys. Call once at startup.

### `get_registered_steps() -> list[str]`

Return the list of registered onboarding step keys.

### `initialize_steps(session: AsyncSession, user_id: UUID) -> list[OnboardingStepPublic]`

Create all registered onboarding steps for a new user. Skips existing steps (idempotent).

### `complete_step(session: AsyncSession, user_id: UUID, step_key: str) -> OnboardingStepPublic | None`

Mark a step as completed. Returns `None` if the step doesn't exist.

### `skip_step(session: AsyncSession, user_id: UUID, step_key: str) -> OnboardingStepPublic | None`

Mark a step as skipped. Returns `None` if the step doesn't exist.

### `get_progress(session: AsyncSession, user_id: UUID) -> dict`

Return completion percentage and per-step status:

```python
{
    "user_id": "uuid",
    "total_steps": 4,
    "completed": 2,
    "skipped": 1,
    "percentage": 75.0,
    "steps": [
        {"step_key": "profile", "status": "completed", "completed_at": "2026-08-03T12:00:00"},
        {"step_key": "email_verify", "status": "completed", "completed_at": "2026-08-03T12:05:00"},
        {"step_key": "first_project", "status": "skipped", "completed_at": "2026-08-03T14:00:00"},
        {"step_key": "team_setup", "status": "pending", "completed_at": None}
    ]
}
```

### `OnboardingService` (Class API)

A class-based API is also available for dependency injection:

```python
from swx_core.services.onboarding.onboarding_service import OnboardingService, onboarding

# Module-level singleton
result = await onboarding.initialize_user(session, user_id)

# Or create a new instance
service = OnboardingService()
service.register_steps("profile", "email_verify")
```

---

## Configuration

Onboarding uses the default step keys `["profile", "email_verify", "first_project"]` if no steps are registered. Override by calling `register_onboarding_steps()` during application startup.

No environment variables are required for basic onboarding.

---

## Database Schema

### `swx_onboarding_step`

| Column | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `user_id` | UUID | Foreign key to `swx_user.id` (CASCADE) |
| `step_key` | VARCHAR(100) | Step identifier (e.g., "profile") |
| `status` | VARCHAR(20) | One of: `pending`, `completed`, `skipped` |
| `completed_at` | TIMESTAMPTZ | When the step was completed/skipped |
| `created_at` | TIMESTAMPTZ | Row creation time |
| `updated_at` | TIMESTAMPTZ | Row update time |

**Unique constraint:** `(user_id, step_key)` — each user can only have one row per step.

### Migration

```bash
# Apply the onboarding step table migration
alembic upgrade head
```

Or manually:
```sql
CREATE TABLE swx_onboarding_step (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES swx_user(id) ON DELETE CASCADE,
    step_key VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, step_key)
);
```