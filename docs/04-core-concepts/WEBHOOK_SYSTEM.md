# Webhook System

**Version:** 1.0.0
**Last Updated:** 2026-07-28

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Database Models](#database-models)
4. [Event Subscription](#event-subscription)
5. [Webhook Signing](#webhook-signing)
6. [Delivery & Retry](#delivery-and-retry)
7. [API Endpoints](#api-endpoints)
8. [Events](#events)
9. [Best Practices](#best-practices)

---

## Overview

SwX-API includes an outbound webhook system allowing users to configure endpoints that receive event payloads via HTTP POST with HMAC-SHA256 signature verification, exponential backoff retry, and full delivery tracking.

- **User-configured endpoints** — Register URLs that receive event payloads
- **Event subscription** — Subscribe to specific event types with wildcard support (`user.*`, `billing.*`)
- **HMAC-SHA256 signing** — Cryptographic signatures for tamper detection
- **Circuit breaker** — Per-endpoint circuit breaker using the existing resilience module
- **Exponential backoff retry** — Configurable retry with jitter
- **Delivery tracking** — Full lifecycle: pending → delivered / failed / retrying
- **`${ENV_VAR}` resolution** — Webhook secrets resolved from environment variables
- **Custom headers** — Per-endpoint custom HTTP headers

---

## Configuration

Webhook settings are configured in `swx_core/config/settings.py`:

```python
WEBHOOK_ENABLED: bool = True
WEBHOOK_DEFAULT_RETRY_COUNT: int = 3
WEBHOOK_DEFAULT_RETRY_DELAY: int = 60
WEBHOOK_DEFAULT_TIMEOUT: int = 30
WEBHOOK_MAX_RETRIES: int = 5
WEBHOOK_CIRCUIT_BREAKER_THRESHOLD: int = 5
```

Endpoint secrets support `${ENV_VAR}` resolution:
```json
{"secret": "${WEBHOOK_SIGNING_SECRET}"}
```

---

## Database Models

### `swx_webhook_endpoint`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | String(100) | Descriptive name |
| `url` | String(2000) | Target URL |
| `secret` | String(500) | HMAC signing secret (`${ENV_VAR}`) |
| `description` | Text | Optional description |
| `is_active` | Boolean | Active flag |
| `user_id` | UUID | FK to swx_users |
| `event_types` | JSONB | Event type patterns |
| `headers` | JSONB | Custom headers |
| `retry_count` | Integer | Max retries |
| `retry_delay_seconds` | Integer | Base delay between retries |
| `timeout_seconds` | Integer | Request timeout |

### `swx_webhook_delivery`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `endpoint_id` | UUID | FK to endpoint |
| `event_type` | String(255) | Event type |
| `payload` | JSONB | Event payload |
| `status` | String(20) | pending, delivered, failed, retrying |
| `attempt_count` | Integer | Number of attempts |
| `last_attempt_at` | DateTime | Last attempt timestamp |
| `next_retry_at` | DateTime | Next scheduled retry |
| `response_status_code` | Integer | HTTP status code |
| `response_body` | Text | Response body |
| `error_message` | Text | Error message |

### `swx_webhook_event`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `endpoint_id` | UUID | FK to endpoint |
| `event_type` | String(255) | Subscribed event type |
| `is_active` | Boolean | Active flag |

---

## Event Subscription

Users subscribe endpoints to event types using patterns:

| Pattern | Matches |
|---|---|
| `user.created` | Only `user.created` |
| `user.*` | `user.created`, `user.updated`, `user.deleted` |
| `billing.*` | All billing events |
| `*` | All events |

When `dispatch_event()` is called, the system:
1. Finds all active endpoints whose event subscriptions match the event type
2. Builds the payload with signature
3. Delivers via HTTP POST to each matching endpoint
4. Tracks delivery status and schedules retries for failures

---

## Webhook Signing

Each payload is signed using HMAC-SHA256:

```python
from swx_core.services.webhook.webhook_signer import sign_payload, verify_signature

# Sign outgoing webhook
signature = sign_payload(payload_bytes, secret)

# Verify incoming webhook (for testing)
is_valid = verify_signature(payload_bytes, signature, secret)
```

The signature is included in the `X-Webhook-Signature` header. Secrets are resolved from `${ENV_VAR}` patterns.

---

## Delivery & Retry

Webhook delivery uses the existing resilience module:

- **Circuit breaker** — Per-endpoint circuit breaker via `CircuitBreakerRegistry`
- **Exponential backoff** — `retry_with_backoff()` with configurable base delay and max delay
- **Jitter** — Random jitter added to prevent thundering herd
- **Timeout** — `call_with_timeout()` for request-level timeouts
- **Max retries** — Configurable per-endpoint (default: 3, max: 5)

Delivery lifecycle:
1. **pending** → Created when event dispatched
2. **retrying** → Failed delivery scheduled for retry
3. **delivered** → Successful HTTP 2xx response
4. **failed** → All retries exhausted

---

## API Endpoints

### Admin Endpoints (`/admin/webhooks`)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/webhooks/endpoints` | List all endpoints |
| GET | `/admin/webhooks/endpoints/{id}` | Get endpoint detail |
| DELETE | `/admin/webhooks/endpoints/{id}` | Deactivate endpoint |
| GET | `/admin/webhooks/deliveries` | List all deliveries |

### User Endpoints (`/user/webhooks`)

| Method | Path | Description |
|---|---|---|
| GET | `/user/webhooks/endpoints` | List own endpoints |
| POST | `/user/webhooks/endpoints` | Create endpoint |
| GET | `/user/webhooks/endpoints/{id}` | Get endpoint detail |
| PUT | `/user/webhooks/endpoints/{id}` | Update endpoint |
| DELETE | `/user/webhooks/endpoints/{id}` | Delete own endpoint |
| POST | `/user/webhooks/endpoints/{id}/subscribe` | Subscribe to events |
| POST | `/user/webhooks/endpoints/{id}/unsubscribe` | Unsubscribe from events |
| GET | `/user/webhooks/deliveries` | List own deliveries |
| POST | `/user/webhooks/deliveries/{id}/retry` | Retry failed delivery |

---

## Events

| Event | Payload | Trigger |
|---|---|---|
| `webhook.endpoint_created` | endpoint_id, user_id, name, url | Endpoint created |
| `webhook.endpoint_updated` | endpoint_id, name | Endpoint updated |
| `webhook.endpoint_deleted` | endpoint_id | Endpoint deleted |
| `webhook.subscription_updated` | endpoint_id, event_types | Subscriptions changed |
| `webhook.delivery_succeeded` | delivery_id, endpoint_id, event_type | Delivery succeeded |
| `webhook.delivery_failed` | delivery_id, endpoint_id, error | Delivery failed |
| `webhook.delivery_retry` | delivery_id, endpoint_id, attempt | Delivery retried |

---

## Best Practices

1. **Store secrets as `${ENV_VAR}`** — Never hardcode signing secrets in DB
2. **Use wildcards carefully** — `*` subscribes to ALL events; be selective
3. **Set appropriate timeouts** — Match your endpoint's expected response time
4. **Monitor delivery status** — Check failed deliveries and circuit breaker states
5. **Verify signatures** — Always validate `X-Webhook-Signature` on the receiving end
6. **Handle retries idempotently** — Use `X-Webhook-Delivery-ID` to deduplicate
7. **Set retry limits** — Balance between reliability and endpoint protection