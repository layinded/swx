# Consent Management

**Version:** 1.0.0  
**Last Updated:** 2026-07-27

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Database Models](#database-models)
4. [Consent Status Lifecycle](#consent-status-lifecycle)
5. [API Endpoints](#api-endpoints)
6. [Usage Examples](#usage-examples)
7. [Events](#events)
8. [Enforcement](#enforcement)
9. [Best Practices](#best-practices)

---

## Overview

SwX-API includes a consent management framework for recording user permission decisions and enforcing consent dependent features. It exists to support privacy and compliance workflows for regulations such as GDPR, NDPR, and POPIA.

- **Configurable consent types** with stable keys such as `privacy_policy` or `marketing_emails`
- **Status tracking** across `pending`, `granted`, `withdrawn`, and `expired`
- **Enforcement helpers** for single consent checks and required consent checks
- **Version support** through stored version strings and dedicated consent version records
- **Audit friendly metadata** including IP address, user agent, source, notes, and timestamps
- **Events** emitted on grant and withdrawal actions

---

## Configuration

Consent behavior is controlled in `swx_core/config/settings.py`.

```python
CONSENT_ENABLED: bool = Field(
    default=True, description="Enable consent management framework"
)
CONSENT_AUTO_EXPIRE_DAYS: int = Field(
    default=0, description="Auto-expire consents after N days (0 = disabled)"
)
```

- **`CONSENT_ENABLED`**: Enables the framework at the application level.
- **`CONSENT_AUTO_EXPIRE_DAYS`**: Defines a default expiration window. A value of `0` disables automatic expiration. Expiration enforcement is handled by consent checks and the `check_expired_consents()` helper.

---

## Database Models

### `swx_consent_type`
Defines the types of consent the platform can request.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `key` | string | Unique lookup key, indexed, max length 50 |
| `name` | string | Human readable label, max length 100 |
| `description` | text, nullable | Longer explanation shown to admins or users |
| `is_required` | bool | Marks the consent as required for access checks |
| `is_active` | bool | Controls whether the consent type is available |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

### `swx_user_consent`
Stores each user consent decision.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `user_id` | UUID | References `swx_users.id`, indexed |
| `consent_type_id` | UUID | References `swx_consent_type.id`, indexed |
| `status` | string | Current status, defaults to `pending` |
| `version` | string | Consent document version accepted or tracked |
| `granted_at` | datetime, nullable | When consent was granted |
| `withdrawn_at` | datetime, nullable | When consent was withdrawn |
| `expires_at` | datetime, nullable | Expiration timestamp |
| `ip_address` | string, nullable | Captured client IP, max length 50 |
| `user_agent` | text, nullable | Captured client user agent |
| `source` | string, nullable | Origin of the action, max length 50 |
| `notes` | text, nullable | Extra admin or system notes |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

Indexes:
- `idx_swx_user_consent_user_type` on `user_id`, `consent_type_id`
- `idx_swx_user_consent_status` on `status`

### `swx_consent_version`
Stores version records for consent text or linked documents.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `consent_type_id` | UUID | References `swx_consent_type.id`, indexed |
| `version` | string | Version label, max length 20 |
| `document_url` | string, nullable | External document location, max length 500 |
| `document_text` | text, nullable | Inline consent content snapshot |
| `is_active` | bool | Marks whether the version can be used |
| `effective_date` | datetime | When the version becomes effective |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

Index:
- `idx_swx_consent_version_type_active` on `consent_type_id`, `is_active`

---

## Consent Status Lifecycle

The framework defines four statuses in `ConsentStatus`:

```text
PENDING -> GRANTED -> WITHDRAWN
                  \
                   -> EXPIRED
```

- **`pending`**: Default state for a consent record before a user grants it.
- **`granted`**: Active consent. `grant_consent()` sets `granted_at`.
- **`withdrawn`**: Revoked consent. `withdraw_consent()` sets `withdrawn_at`.
- **`expired`**: Previously granted consent that is no longer valid because `expires_at` has passed.

`check_expired_consents()` scans granted records and changes them to `expired` when `expires_at <= now`.

---

## API Endpoints

### User Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/user/consent/` | Get `ConsentSummary` counts for the current user |
| `GET` | `/user/consent/types` | List active consent types available to the user |
| `POST` | `/user/consent/grant` | Grant a consent type using `UserConsentCreate` |
| `POST` | `/user/consent/withdraw/{consent_type_key}` | Withdraw the latest consent record for a consent type |

### Admin Endpoints

All admin consent routes require `get_current_admin_user`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/consent/types` | List all consent types, including inactive ones |
| `POST` | `/admin/consent/types` | Create a new consent type |
| `POST` | `/admin/consent/versions` | Create a new consent version record |
| `GET` | `/admin/consent/users/{user_id}` | List all consent records for a specific user |

---

## Usage Examples

### Granting Consent
```python
from uuid import UUID

from swx_core.services import consent_service

user_id = UUID("11111111-1111-1111-1111-111111111111")

consent = await consent_service.grant_consent(
    session=session,
    user_id=user_id,
    consent_type_key="privacy_policy",
    version="2026.07",
    ip="203.0.113.10",
    user_agent="Mozilla/5.0",
    source="signup",
)
```

### Checking Consent
```python
from swx_core.services import consent_enforcement_service

await consent_enforcement_service.enforce_consent(
    session=session,
    user_id=current_user.id,
    consent_type_key="privacy_policy",
)
```

For a boolean check without raising an HTTP error:

```python
from swx_core.services import consent_service

has_privacy_consent = await consent_service.has_consent(
    session=session,
    user_id=current_user.id,
    consent_type_key="privacy_policy",
)
```

### Creating Consent Types (Admin)
```python
from swx_core.models.consent import ConsentTypeCreate
from swx_core.services import consent_service

consent_type = await consent_service.create_consent_type(
    session,
    ConsentTypeCreate(
        key="marketing_emails",
        name="Marketing Emails",
        description="Allow product updates and promotional email campaigns.",
        is_required=False,
        is_active=True,
    ),
)
```

### Consent Versioning
Consent version records live in `swx_consent_version`, while each user decision also stores a `version` string on `swx_user_consent`.

```python
from swx_core.models.consent import ConsentVersionCreate
from swx_core.services import consent_service

version = await consent_service.create_consent_version(
    session,
    ConsentVersionCreate(
        consent_type_id=consent_type.id,
        version="2026.07",
        document_url="https://example.com/legal/privacy-policy-2026-07",
        document_text="Privacy Policy version 2026.07",
        is_active=True,
        effective_date=consent_service.utc_now_naive(),
    ),
)
```

The repository also exposes `get_active_consent_version(session, consent_type_id)`, which returns the latest active version whose `effective_date` is in the past. The grant flow does not auto resolve that record. `grant_consent()` stores the version string passed by the caller.

---

## Events

The consent service dispatches events through `swx_core.events.event_bus`.

| Event name | Payload | When emitted |
|---|---|---|
| `consent.granted` | `{"user_id": str(user_id), "consent_type_key": consent_type_key, "consent_id": str(consent.id), "version": version}` | After `grant_consent()` creates a granted record |
| `consent.withdrawn` | `{"user_id": str(user_id), "consent_type_key": consent_type_key, "consent_id": str(updated.id), "version": updated.version}` | After `withdraw_consent()` updates the latest record to `withdrawn` |

---

## Enforcement

Use the enforcement service in routes, guards, or feature entry points when a workflow depends on a granted consent.

```python
from fastapi import APIRouter

from swx_core.auth.user.dependencies import UserDep
from swx_core.database.db import SessionDep
from swx_core.services import consent_enforcement_service

router = APIRouter()

@router.get("/user/export-data")
async def export_user_data(session: SessionDep, current_user: UserDep):
    await consent_enforcement_service.enforce_consent(
        session=session,
        user_id=current_user.id,
        consent_type_key="privacy_policy",
    )
    return {"status": "ok"}
```

To block access until every active required consent is granted:

```python
await consent_enforcement_service.enforce_required_consents(
    session=session,
    user_id=current_user.id,
)
```

`enforce_required_consents()` loads all active consent types, filters to `is_required=True`, and raises `HTTPException(status_code=403, detail=f"Consent '{consent_type.key}' is required")` for the first missing required consent.

---

## Best Practices

- Create a stable `key` for each consent type and avoid changing it after release.
- Record a real document version in every grant call so historical user decisions stay traceable.
- Use `source`, `ip_address`, and `user_agent` to support investigations and compliance reviews.
- Run `check_expired_consents()` from a scheduled job if you use `expires_at`.
- Use `enforce_required_consents()` at login completion or before protected workflows.
- Keep required consents active and versioned before exposing them in user facing flows.

---

**Status:** Consent management documented, ready for use.
