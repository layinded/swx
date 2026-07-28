# Enterprise SSO

**Version:** 1.0.0
**Last Updated:** 2026-07-28

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Database Models](#database-models)
4. [Provider Management](#provider-management)
5. [SSO Sessions](#sso-sessions)
6. [API Endpoints](#api-endpoints)
7. [Events](#events)
8. [Best Practices](#best-practices)

---

## Overview

SwX-API includes an enterprise SSO system supporting SAML-based single sign-on with provider management, session lifecycle tracking, and automatic expired session cleanup.

- **Multi-provider support** — Configure multiple SSO providers (SAML, OIDC)
- **Provider management** — Create, update, delete, enable/disable providers
- **Session lifecycle** — Initiate, complete, and terminate SSO sessions
- **`${ENV_VAR}` resolution** — Client secrets and certificates resolved from environment variables
- **Secret masking** — Sensitive credentials masked in API responses
- **Caching** — Redis-backed provider cache with configurable TTL
- **Automatic cleanup** — Expired sessions marked automatically

---

## Configuration

SSO settings in `swx_core/config/settings.py`:

```python
SSO_ENABLED: bool = True
SSO_DEFAULT_SESSION_EXPIRY_HOURS: int = 24
SSO_MAX_CONCURRENT_SESSIONS: int = 5
SSO_PROVIDER_CACHE_TTL: int = 60
```

Provider secrets use `${ENV_VAR}` resolution:
```json
{"client_secret": "${SSO_CLIENT_SECRET}", "certificate": "${SSO_CERTIFICATE}"}
```

---

## Database Models

### `swx_sso_provider`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `provider_type` | String(20) | saml, oidc |
| `name` | String(200) | Display name |
| `client_id` | String(500) | SP entity ID / client ID |
| `client_secret` | String(500) | Secret (`${ENV_VAR}`) |
| `authorization_url` | String(2000) | Authorization endpoint |
| `issuer_url` | String(2000) | Issuer/entity ID |
| `sso_url` | String(2000) | SSO endpoint |
| `certificate` | String(5000) | X.509 certificate (`${ENV_VAR}`) |
| `domain` | String(200) | Allowed email domain |
| `scopes` | JSONB | Requested scopes |
| `enabled` | Boolean | Active flag |
| `metadata_` | JSONB | Provider-specific metadata |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### `swx_sso_session`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `user_id` | UUID | FK to swx_users |
| `provider_id` | UUID | FK to swx_sso_provider |
| `status` | String(20) | active, completed, expired, terminated |
| `saml_request_id` | String(500) | SAML request ID |
| `saml_response` | Text | SAML response data |
| `expires_at` | DateTime | Session expiration |
| `metadata_` | JSONB | Session metadata |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

---

## Provider Management

```python
from swx_core.services.sso.sso_provider_service import (
    create_provider,
    get_provider,
    list_providers,
    update_provider,
    delete_provider,
)

# Create a SAML provider
provider = await create_provider(session, SSOProviderCreate(
    provider_type="saml",
    name="Corporate SSO",
    client_id="spn-client-id",
    client_secret="${SSO_CLIENT_SECRET}",
    authorization_url="https://sso.example.com/auth",
    issuer_url="https://sso.example.com",
    sso_url="https://sso.example.com/sso",
    domain="example.com",
))

# List enabled providers
providers = await list_providers(session, enabled_only=True)
```

Secrets are automatically masked in responses: `${SSO_CLIENT_SECRET}` → `***`

---

## SSO Sessions

```python
from swx_core.services.sso.sso_session_service import (
    initiate_sso,
    complete_sso_login,
    terminate_session,
    get_active_sessions,
    cleanup_expired_sessions,
)

# Initiate SSO login
result = await initiate_sso(session, user_id, provider_id)
# Returns: session_id, authorization_url, issuer_url, scopes, domain

# Complete SSO login
sso_session = await complete_sso_login(session, sso_session_id, SSOSessionUpdate(
    status="completed",
    saml_response="response-data",
))

# Cleanup expired sessions
expired = await cleanup_expired_sessions(session)
```

---

## API Endpoints

### Admin Endpoints (`/admin/sso`)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/sso/providers` | List all providers |
| POST | `/admin/sso/providers` | Create provider |
| GET | `/admin/sso/providers/{id}` | Get provider detail |
| PUT | `/admin/sso/providers/{id}` | Update provider |
| DELETE | `/admin/sso/providers/{id}` | Delete provider |
| GET | `/admin/sso/sessions` | List all sessions |

### User Endpoints (`/user/sso`)

| Method | Path | Description |
|---|---|---|
| GET | `/user/sso/providers` | List enabled providers |
| POST | `/user/sso/providers/{id}/initiate` | Initiate SSO login |
| POST | `/user/sso/sessions/{id}/complete` | Complete SSO login |
| POST | `/user/sso/sessions/{id}/terminate` | Terminate session |
| GET | `/user/sso/sessions` | List own sessions |

---

## Events

| Event | Payload | Trigger |
|---|---|---|
| `sso.provider_created` | provider_id, provider_type | Provider created |
| `sso.provider_updated` | provider_id, provider_type | Provider updated |
| `sso.provider_deleted` | provider_id, provider_type | Provider deleted |
| `sso.session_initiated` | session_id, user_id, provider_id | SSO session initiated |
| `sso.session_completed` | session_id, user_id, provider_id | SSO login completed |
| `sso.session_terminated` | session_id, user_id, provider_id | SSO session terminated |

---

## Best Practices

1. **Store secrets as `${ENV_VAR}`** — Never hardcode client secrets or certificates in DB
2. **Set session expiry** — Use `SSO_DEFAULT_SESSION_EXPIRY_HOURS` to control session lifetime
3. **Monitor active sessions** — Track `sso.session_initiated` and `sso.session_completed` events
4. **Run cleanup regularly** — Call `cleanup_expired_sessions()` periodically
5. **Limit concurrent sessions** — Use `SSO_MAX_CONCURRENT_SESSIONS` to prevent session sprawl
6. **Verify domains** — Set `domain` on providers to restrict SSO to specific email domains