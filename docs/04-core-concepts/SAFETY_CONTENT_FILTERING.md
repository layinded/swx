# AI Safety & Content Filtering

**Version:** 1.0.0
**Last Updated:** 2026-07-28

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Database Models](#database-models)
4. [Content Filters](#content-filters)
5. [Safety Checks](#safety-checks)
6. [Filter Types](#filter-types)
7. [API Endpoints](#api-endpoints)
8. [Events](#events)
9. [Best Practices](#best-practices)

---

## Overview

SwX-API includes an AI safety and content filtering system for screening user input and LLM output through configurable filters with multiple match strategies, severity levels, and action policies.

- **Keyword filters** — Match against configurable keyword lists with case-insensitive support
- **Regex filters** — Pattern-based matching with configurable flags (case-insensitive, multiline, dotall)
- **Severity levels** — low, medium, high, critical classification
- **Action policies** — block, flag, or replace matched content
- **Caching** — Redis-backed filter cache with configurable TTL
- **Conversation integration** — Safety checks linked to conversation context
- **Audit trail** — Complete safety check history with verdict tracking

---

## Configuration

Safety settings in `swx_core/config/settings.py`:

```python
SAFETY_ENABLED: bool = True
SAFETY_MAX_CONTENT_LENGTH: int = 10000
SAFETY_CACHE_TTL: int = 60
SAFETY_CHECK_HISTORY_LIMIT: int = 100
```

---

## Database Models

### `swx_content_filter`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | String(200) | Filter name |
| `description` | Text | Optional description |
| `filter_type` | String(50) | keyword, regex |
| `config` | JSONB | Filter configuration |
| `severity` | String(20) | low, medium, high, critical |
| `action` | String(20) | block, flag, replace |
| `enabled` | Boolean | Active flag |
| `category` | String(100) | Optional category |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### `swx_safety_check`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `content_type` | String(50) | input, output |
| `content_hash` | String(64) | SHA-256 hash of content |
| `content_preview` | String(200) | Length + hash prefix |
| `source` | String(100) | direct, api, conversation |
| `user_id` | UUID | FK to swx_users |
| `conversation_id` | UUID | FK to swx_conversation (optional) |
| `filter_results` | JSONB | Per-filter match results |
| `overall_verdict` | String(20) | safe, flagged, blocked |
| `action_taken` | String(20) | none, flagged, blocked, replaced |
| `metadata_` | JSONB | Additional metadata |
| `created_at` | DateTime | Check timestamp |

---

## Content Filters

```python
from swx_core.services.safety.safety_service import (
    create_filter,
    get_filter,
    list_filters,
    update_filter,
    delete_filter,
)

# Create a keyword filter
filter_obj = await create_filter(session, ContentFilterCreate(
    name="profanity-filter",
    filter_type="keyword",
    config={"keywords": ["badword1", "badword2"], "case_sensitive": False},
    severity="high",
    action="block",
))

# Create a regex filter
regex_filter = await create_filter(session, ContentFilterCreate(
    name="email-filter",
    filter_type="regex",
    config={"pattern": r"\b[\w.-]+@[\w.-]+\.\w+\b", "flags": "i"},
    severity="medium",
    action="flag",
    category="pii",
))
```

---

## Safety Checks

```python
from swx_core.services.safety.safety_check_service import run_safety_check

# Run a safety check on user input
result = await run_safety_check(
    session,
    content="Hello, how are you?",
    content_type="input",
    user_id=user_id,
    source="direct",
)

# Check with conversation context
result = await run_safety_check(
    session,
    content="This might be bad content",
    content_type="input",
    user_id=user_id,
    source="conversation",
    conversation_id=conversation_id,
)
```

The check result includes:
- `overall_verdict`: safe, flagged, or blocked
- `action_taken`: none, flagged, blocked, or replaced
- `filter_results`: Details of each filter that matched

---

## Filter Types

### Keyword Filter

Matches against a list of keywords:

```json
{
  "keywords": ["badword1", "badword2"],
  "case_sensitive": false
}
```

### Regex Filter

Matches using a regular expression pattern:

```json
{
  "pattern": "\\b[\\w.-]+@[\\w.-]+\\.\\w+\\b",
  "flags": "i"
}
```

Flags: `i` (case-insensitive), `m` (multiline), `s` (dotall)

---

## API Endpoints

### Admin Endpoints (`/admin/safety`)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/safety/filters` | List all filters |
| POST | `/admin/safety/filters` | Create filter |
| GET | `/admin/safety/filters/{id}` | Get filter detail |
| PUT | `/admin/safety/filters/{id}` | Update filter |
| DELETE | `/admin/safety/filters/{id}` | Delete filter |
| GET | `/admin/safety/checks` | List all safety checks |

### User Endpoints (`/user/safety`)

| Method | Path | Description |
|---|---|---|
| POST | `/user/safety/check` | Run safety check |
| GET | `/user/safety/checks` | List own safety checks |
| GET | `/user/safety/checks/{id}` | Get own check detail |

---

## Events

| Event | Payload | Trigger |
|---|---|---|
| `safety.filter_created` | filter_id, name | Filter created |
| `safety.filter_updated` | filter_id | Filter updated |
| `safety.filter_deleted` | filter_id, name | Filter deleted |
| `safety.check_completed` | check_id, user_id, overall_verdict, action_taken | Safety check completed |

---

## Best Practices

1. **Layer your filters** — Use keyword filters for simple matches, regex for complex patterns
2. **Set appropriate severity** — Reserve `critical` + `block` for harmful content only
3. **Use `replace` action** — For PII/-sensitive data that should be redacted, not rejected
4. **Monitor check results** — Track `overall_verdict` trends to tune filter sensitivity
5. **Cache filter configs** — Filters are cached with `SAFETY_CACHE_TTL`; reduce for rapid changes
6. **Link to conversations** — Always pass `conversation_id` when checking conversation content