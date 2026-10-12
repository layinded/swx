# Feature Flags & A/B Testing

**Version:** 1.0.0
**Last Updated:** 2026-07-28

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Database Models](#database-models)
4. [Flag Management](#flag-management)
5. [Flag Evaluation](#flag-evaluation)
6. [A/B Testing](#ab-testing)
7. [API Endpoints](#api-endpoints)
8. [Events](#events)
9. [Best Practices](#best-practices)

---

## Overview

SwX-API includes a feature flag system with A/B testing support, enabling gradual rollouts, user targeting, and variant assignment. Flags support time-based scheduling, sticky evaluations, and weighted variant distribution.

- **Feature flags** — Enable/disable features per environment
- **A/B testing** — Weighted variant distribution with deterministic user assignment
- **Time-based scheduling** — Start and end dates for flag availability
- **Sticky evaluations** — Consistent variant assignment per user
- **Default values** — Fallback values when flag is disabled or expired
- **Evaluation history** — Full audit trail of flag evaluations
- **Caching** — Redis-backed flag cache with configurable TTL

---

## Configuration

Feature flag settings in `swx_core/config/settings.py`:

```python
FEATURE_FLAG_ENABLED: bool = True
FEATURE_FLAG_DEFAULT_PAGE_SIZE: int = 50
FEATURE_FLAG_MAX_PAGE_SIZE: int = 200
FEATURE_FLAG_CACHE_TTL: int = 60
FEATURE_FLAG_EVALUATION_HISTORY_LIMIT: int = 100
```

---

## Database Models

### `swx_feature_flag`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `key` | String(200) | Unique flag key (e.g., "dark-mode") |
| `name` | String(200) | Display name |
| `description` | Text | Optional description |
| `enabled` | Boolean | Active flag |
| `default_value` | JSONB | Default value when disabled |
| `rules` | JSONB | Targeting rules |
| `variants` | JSONB | A/B test variants |
| `sticky` | Boolean | Persist user variant assignment |
| `start_date` | DateTime | Optional activation date |
| `end_date` | DateTime | Optional expiration date |
| `metadata_` | JSONB | Arbitrary metadata |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### `swx_flag_evaluation`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `flag_id` | UUID | FK to swx_feature_flag |
| `user_id` | UUID | FK to swx_users (optional) |
| `variant` | String(100) | Assigned variant name |
| `value` | JSONB | Resolved value |
| `reason` | String(50) | enabled, disabled, not_found, variant_assigned, not_started, expired |
| `context` | JSONB | Evaluation context |
| `created_at` | DateTime | Evaluation timestamp |

---

## Flag Management

```python
from swx_core.services.feature_flag.feature_flag_service import (
    create_flag,
    get_flag,
    get_flag_by_key,
    list_flags,
    update_flag,
    delete_flag,
)

# Create a feature flag
flag = await create_flag(session, FeatureFlagCreate(
    key="dark-mode",
    name="Dark Mode",
    description="Enable dark mode UI",
    enabled=True,
))

# Create with A/B variants
flag = await create_flag(session, FeatureFlagCreate(
    key="checkout-flow",
    name="New Checkout Flow",
    enabled=True,
    variants={
        "options": [
            {"name": "control", "value": {"flow": "old"}, "weight": 80},
            {"name": "variant_a", "value": {"flow": "new"}, "weight": 20},
        ]
    },
))

# Get flag by key
flag = await get_flag_by_key(session, "dark-mode")

# Update a flag
flag = await update_flag(session, flag_id, FeatureFlagUpdate(enabled=True))

# Delete a flag
flag = await delete_flag(session, flag_id)
```

---

## Flag Evaluation

```python
from swx_core.services.feature_flag.feature_flag_evaluation_service import (
    evaluate_flag,
    evaluate_flags_for_user,
    get_flag_evaluations,
    get_user_evaluations,
)

# Evaluate a single flag for a user
result = await evaluate_flag(session, "dark-mode", user_id=user_id)
# Returns: {"flag_key": "dark-mode", "enabled": True, "variant": None, "value": None, "reason": "enabled"}

# Evaluate with context
result = await evaluate_flag(session, "checkout-flow", user_id=user_id, context={"country": "US"})
# Returns: {"flag_key": "checkout-flow", "enabled": True, "variant": "variant_a", "value": {"flow": "new"}, "reason": "variant_assigned"}

# Evaluate all enabled flags for a user
results = await evaluate_flags_for_user(session, user_id=user_id)

# Get evaluation history
evaluations = await get_flag_evaluations(session, flag_id, skip=0, limit=50)
```

### Evaluation Reasons

| Reason | Description |
|---|---|
| `enabled` | Flag is on, no variants |
| `disabled` | Flag is off, returns `default_value` |
| `not_found` | Flag key doesn't exist |
| `variant_assigned` | A/B variant was assigned |
| `not_started` | `start_date` is in the future |
| `expired` | `end_date` is in the past |

---

## A/B Testing

Variants use deterministic hashing based on `flag_key:user_id` to ensure consistent assignment:

```python
# Variant distribution example
variants = {
    "options": [
        {"name": "control", "value": {"button": "blue"}, "weight": 70},
        {"name": "variant_a", "value": {"button": "green"}, "weight": 20},
        {"name": "variant_b", "value": {"button": "red"}, "weight": 10},
    ]
}
```

- **Deterministic** — Same user always gets same variant (MD5 hash of `flag_key:user_id`)
- **Weighted** — Variants are distributed by weight
- **No user** — Returns first variant when no `user_id` is provided

---

## API Endpoints

### Admin Endpoints (`/admin/feature-flags`)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/feature-flags` | List all flags |
| POST | `/admin/feature-flags` | Create flag |
| GET | `/admin/feature-flags/{id}` | Get flag detail |
| PUT | `/admin/feature-flags/{id}` | Update flag |
| DELETE | `/admin/feature-flags/{id}` | Delete flag |
| GET | `/admin/feature-flags/{id}/evaluations` | Get evaluation history |

### User Endpoints (`/user/feature-flags`)

| Method | Path | Description |
|---|---|---|
| GET | `/user/feature-flags` | List enabled flags |
| POST | `/user/feature-flags/evaluate` | Evaluate flag(s) |
| GET | `/user/feature-flags/evaluations` | Get own evaluations |

---

## Events

| Event | Payload | Trigger |
|---|---|---|
| `feature_flag.created` | flag_id, key | Flag created |
| `feature_flag.updated` | flag_id, key | Flag updated |
| `feature_flag.deleted` | flag_id, key | Flag deleted |
| `feature_flag.evaluated` | flag_key, flag_id, reason | Flag evaluated |

---

## Best Practices

1. **Use unique, descriptive keys** — `dark-mode`, `checkout-v2`, `api-rate-limiting`
2. **Set start/end dates** — Schedule flags for time-limited campaigns
3. **Use sticky for A/B tests** — Set `sticky=True` to maintain consistent variant per user
4. **Set default values** — Always provide `default_value` for graceful degradation
5. **Monitor evaluation reasons** — Track `not_found` and `disabled` to find misconfigurations
6. **Clean up old flags** — Delete flags that are permanently enabled or disabled
7. **Weight variants carefully** — Ensure weights sum to 100 (or the total desired weight)