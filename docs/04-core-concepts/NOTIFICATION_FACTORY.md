# Notification Factory

**Version:** 1.0.0  
**Last Updated:** 2026-07-28

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Database Models](#database-models)
4. [Provider Factory](#provider-factory)
5. [Templates](#templates)
6. [User Preferences](#user-preferences)
7. [Delivery Tracking](#delivery-tracking)
8. [API Endpoints](#api-endpoints)
9. [Events](#events)
10. [Best Practices](#best-practices)

---

## Overview

SwX-API includes a DB-driven notification factory supporting multi-channel delivery with provider fallback, Jinja2 templates, per-user preferences, and delivery tracking.

- **Email providers**: SMTP, SendGrid (extensible)
- **SMS providers**: Twilio, Africa's Talking (extensible)
- **Push providers**: Firebase (extensible)
- **In-app notifications**: Stored in DB, queryable per user
- **Provider chains**: Priority-ordered fallback with circuit breaker
- **Jinja2 templates**: DB-stored templates with variable interpolation
- **Per-user preferences**: Channel-level opt-in/out, quiet hours, digest mode
- **Delivery tracking**: Full lifecycle (pending → queued → sent → delivered/failed)
- **Rate limiting**: Configurable daily/hourly limits per channel
- **`${ENV_VAR}` resolution**: Secrets resolved from environment variables

---

## Configuration

Notification settings in `swx_core/config/settings.py` (defaults, overridden by DB config):

```python
NOTIFICATION_ENABLED: bool = True
NOTIFICATION_DEFAULT_FROM_EMAIL: str = "noreply@example.com"
NOTIFICATION_DEFAULT_FROM_NAME: str = "SwX App"
NOTIFICATION_DEFAULT_RETRY_COUNT: int = 3
NOTIFICATION_DEFAULT_TIMEOUT: int = 30
NOTIFICATION_PROVIDER_CACHE_TTL: int = 30
NOTIFICATION_TEMPLATE_CACHE_TTL: int = 30
NOTIFICATION_RATE_LIMIT_DAILY: int = 100
NOTIFICATION_RATE_LIMIT_HOURLY: int = 20

# v2.16.0 additions
NOTIFICATION_TEMPLATE_DIR: str = "templates"
NOTIFICATION_BRAND_COLOR: str = "#3c42b6"
NOTIFICATION_SUPPORT_EMAIL: str = "support@example.com"
NOTIFICATION_CELERY_TASK_PATH: str = "swx_core.services.notifications.tasks.send_notification_task"
OTP_LENGTH: int = 6
OTP_EXPIRY_MINUTES: int = 10
OTP_MAX_ATTEMPTS: int = 3
OTP_RESEND_COOLDOWN_SECONDS: int = 60
OTP_BYPASS_FOR_TESTING: bool = False
```

DB-driven provider config uses `${ENV_VAR}` credential resolution:
```json
{"key": "api_key", "value": "${SENDGRID_API_KEY}"}
```

---

## Database Models

### `swx_email_provider_config`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | String(50) | Unique provider name (e.g., "sendgrid") |
| `provider_type` | String(30) | "smtp" or "api" |
| `host` | String(255) | SMTP host |
| `port` | Integer | SMTP port |
| `username` | String(255) | SMTP username |
| `password` | String(500) | SMTP password (`${ENV_VAR}`) |
| `api_key` | String(500) | API key (`${ENV_VAR}`) |
| `from_email` | String(255) | Sender email |
| `from_name` | String(100) | Sender name |
| `is_ssl` | Boolean | Use SSL/TLS |
| `is_active` | Boolean | Active flag |
| `priority` | Integer | Lower = higher priority |
| `max_retries` | Integer | Max retry attempts |
| `timeout_seconds` | Integer | Request timeout |
| `extra_config` | JSONB | Provider-specific settings |
| `cost_per_email` | Float | Cost per send (v2.16.0) |
| `daily_limit` | Integer | Max emails per day (v2.16.0) |
| `monthly_limit` | Integer | Max emails per month (v2.16.0) |
| `rate_limit_per_hour` | Integer | Max emails per hour (v2.16.0) |
| `supported_countries` | JSONB | Country codes for regional routing (v2.16.0) |
| `tracking_enabled` | Boolean | Email tracking toggle (v2.16.0) |
| `open_tracking` | Boolean | Track opens (v2.16.0) |
| `click_tracking` | Boolean | Track clicks (v2.16.0) |
| `reply_to` | String(255) | Reply-to address (v2.16.0) |

### `swx_sms_provider_config`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | String(50) | Unique provider name (e.g., "twilio") |
| `provider_type` | String(30) | "twilio", "africas_talking", "vonage", "sns" |
| `account_sid` | String(255) | Account SID (`${ENV_VAR}`) |
| `auth_token` | String(500) | Auth token (`${ENV_VAR}`) |
| `api_key` | String(500) | API key |
| `from_number` | String(20) | Sender phone number |
| `is_active` | Boolean | Active flag |
| `priority` | Integer | Lower = higher priority |
| `max_retries` | Integer | Max retry attempts |
| `timeout_seconds` | Integer | Request timeout |
| `extra_config` | JSONB | Provider-specific settings |

### `swx_notification`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `user_id` | UUID | FK to swx_users (indexed) |
| `channel` | String(20) | email, sms, push, in_app |
| `notification_type` | String(50) | verification, alert, billing, etc. |
| `subject` | String(500) | Notification subject |
| `body` | Text | Notification body |
| `status` | String(20) | pending, queued, sent, delivered, failed |
| `provider_config_id` | UUID | Which provider was used |
| `provider_name` | String(50) | Provider name |
| `provider_response` | JSONB | Provider response data |
| `retry_count` | Integer | Number of retry attempts |
| `scheduled_at` | DateTime | When to send |
| `sent_at` | DateTime | When sent |
| `delivered_at` | DateTime | When delivered |

### `swx_notification_preference`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `user_id` | UUID | FK to swx_users (unique) |
| `email_enabled` | Boolean | Email channel enabled |
| `sms_enabled` | Boolean | SMS channel enabled |
| `push_enabled` | Boolean | Push channel enabled |
| `in_app_enabled` | Boolean | In-app channel enabled |
| `quiet_hours_start` | String(5) | e.g., "22:00" |
| `quiet_hours_end` | String(5) | e.g., "08:00" |
| `digest_enabled` | Boolean | Digest mode |
| `digest_frequency` | String(20) | daily, weekly |
| `reminder_time` | String(5) | Preferred notification time HH:MM (v2.16.0) |
| `escalation_enabled` | Boolean | Retry undelivered via alternate channel (v2.16.0) |
| `escalation_hours` | Integer | Hours before escalating (v2.16.0) |

### `swx_notification_template`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `key` | String(100) | Unique template key (e.g., "email.verification") |
| `channel` | String(20) | Template channel |
| `subject_template` | String(500) | Jinja2 subject |
| `body_template` | Text | Jinja2 body |
| `is_active` | Boolean | Active flag |

---

## Provider Factory

The notification factory selects providers based on priority and health:

```python
from swx_core.services.notifications.provider_factory import send_via_email, send_via_sms

# Send email with automatic provider selection and fallback
result = await send_via_email(session, to="user@example.com", subject="Welcome", body="...")

# Send SMS with automatic provider selection and fallback
result = await send_via_sms(session, to="+1234567890", body="Your code is 123456")
```

Provider selection logic:
1. Load active providers from DB (cached 30s)
2. Resolve `${ENV_VAR}` credentials
3. Check circuit breaker state
4. Try highest-priority active provider first
5. Fallback to next provider on failure
6. Track delivery status in `swx_notification`

### Country-Specific Routing (v2.16.0)

Filter providers by `supported_countries` for GDPR compliance and data residency:

```python
from swx_core.services.notifications.provider_factory import get_email_provider_for_country

# Get a provider that supports EU users
provider, config = await get_email_provider_for_country(session, country="EU")

# Automatic country routing in send_via_email — pass country in notification dict
result = await send_via_email(session, {"to": "...", "country": "EU", ...})
```

### Preferred Provider Override (v2.16.0)

Force a specific provider regardless of priority:

```python
result = await send_via_email(session, notification, preferred_provider="brevo")
```

### Provider Health Check and Statistics (v2.16.0)

```python
from swx_core.services.notifications.management_service import test_email_provider, get_provider_statistics

# Test provider connectivity
status = await test_email_provider(session, "sendgrid")

# Get delivery stats per provider
stats = await get_provider_statistics(session, days=30)
```

---

## Templates

Jinja2 templates are stored in the database with variable interpolation:

```python
from swx_core.services.notifications.template_service import render_template

subject, body = await render_template(session, "email.verification", {"code": "123456"})
```

### Hybrid Templates (v2.16.0)

Use file-based base layouts with DB-stored body content:

```python
# Render DB body inside a file-based base.html from templates/ directory
result = await render_template(
    session, "email.verification", {"code": "123456"},
    base_template_path="base.html"
)
```

The file-based base uses Jinja2 `{% block content %}` — the DB body is injected into the block. Requires `NOTIFICATION_TEMPLATE_DIR` setting (default: `templates/`).

### Brand Variable Enrichment (v2.16.0)

Every template automatically receives brand defaults:

| Variable | Source Setting | Default |
|---|---|---|
| `{{ brand_name }}` | `NOTIFICATION_DEFAULT_FROM_NAME` / `PROJECT_NAME` | "App" |
| `{{ brand_color }}` | `NOTIFICATION_BRAND_COLOR` | "#3c42b6" |
| `{{ support_email }}` | `NOTIFICATION_SUPPORT_EMAIL` | "support@example.com" |
| `{{ frontend_url }}` | `FRONTEND_HOST` | "http://localhost:3000" |

User-provided context variables override the defaults.

---

## Email OTP Authentication (v2.16.0)

Passwordless email authentication via one-time codes:

```python
from swx_core.services.auth.email_otp_service import generate_otp, verify_otp, resend_otp

# Generate and send OTP
code = await generate_otp("user@example.com")

# Verify OTP
valid = await verify_otp("user@example.com", "123456")

# Resend with cooldown
new_code = await resend_otp("user@example.com")
```

Configuration via settings: `OTP_LENGTH`, `OTP_EXPIRY_MINUTES`, `OTP_MAX_ATTEMPTS`, `OTP_RESEND_COOLDOWN_SECONDS`, `OTP_BYPASS_FOR_TESTING`.

---

## Async Queue Delivery (v2.16.0)

Dispatch notifications to Celery workers for bulk sends:

```python
# Synchronous (default)
notification = await send_notification(session, user_id=..., channel="email", ...)

# Queued via Celery
notification = await send_notification(session, user_id=..., channel="email", ..., queue=True)
```

Requires Celery installed (`pip install swx-core[jobs]`). Falls back to synchronous if Celery is not available.

Jinja2 templates stored in DB for dynamic content:

```python
from swx_core.services.notifications.template_service import render_template

# Render a template with context variables
subject, body = await render_template(session, "email.verification", {
    "user_name": "John",
    "verification_code": "123456",
    "app_name": "SwX App"
})
```

Template example in DB:
```
key: "email.verification"
subject_template: "Welcome to {{ app_name }}"
body_template: "Hello {{ user_name }}, your verification code is {{ verification_code }}."
```

---

## User Preferences

Per-user channel preferences:

```python
from swx_core.services.notifications.management_service import get_user_preferences, update_user_preferences

# Get preferences (auto-creates defaults if not exists)
prefs = await get_user_preferences(session, user_id)

# Update preferences
updated = await update_user_preferences(session, user_id, {
    "email_enabled": True,
    "sms_enabled": False,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00"
})
```

---

## Delivery Tracking

Full notification lifecycle tracking:

```python
from swx_core.services.notifications.delivery_tracker import track_notification, update_notification_status

# Create notification record
notification = await track_notification(session, {
    "user_id": user_id,
    "channel": "email",
    "notification_type": "verification",
    "subject": "Welcome",
    "body": "..."
})

# Update status after provider response
await update_notification_status(session, notification.id, "sent", provider_name="sendgrid", provider_response=response)
```

---

## API Endpoints

### Admin Endpoints (`/admin/notifications`)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/notifications/providers/email` | List email providers |
| PUT | `/admin/notifications/providers/email` | Upsert email provider |
| GET | `/admin/notifications/providers/sms` | List SMS providers |
| PUT | `/admin/notifications/providers/sms` | Upsert SMS provider |
| GET | `/admin/notifications/templates` | List templates |
| PUT | `/admin/notifications/templates` | Upsert template |
| GET | `/admin/notifications` | List all notifications |

### User Endpoints (`/user/notifications`)

| Method | Path | Description |
|---|---|---|
| GET | `/user/notifications` | List own notifications |
| GET | `/user/notifications/{id}` | Get notification status |
| GET | `/user/notifications/preferences` | Get own preferences |
| PUT | `/user/notifications/preferences` | Update own preferences |

---

## Events

| Event | Payload | Trigger |
|---|---|---|
| `notification.sent` | notification_id, channel, provider | Notification sent successfully |
| `notification.delivered` | notification_id, channel | Notification delivered |
| `notification.failed` | notification_id, channel, error | Notification delivery failed |
| `notification.preference_changed` | user_id, channel, enabled | User preference updated |
| `notification.template_updated` | key, channel | Template upserted |
| `notification.provider_updated` | provider_type, name, priority | Provider config upserted |

---

## Best Practices

1. **Store credentials as `${ENV_VAR}`** — Never hardcode API keys or passwords in DB
2. **Set provider priorities** — Lower number = higher priority; system tries providers in order
3. **Use templates** — Store all notification content in templates for easy editing without code changes
4. **Respect user preferences** — Always check preferences before sending; skip channels the user disabled
5. **Monitor delivery status** — Use the delivery tracker to identify failed sends and provider issues
6. **Set rate limits** — Configure daily/hourly limits per channel to prevent abuse
7. **Use circuit breakers** — Provider health is tracked automatically; failing providers are skipped