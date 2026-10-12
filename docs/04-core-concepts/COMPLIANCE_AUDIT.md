# Compliance Audit

**Version:** 1.0.0  
**Last Updated:** 2026-07-28

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Database Models](#database-models)
4. [Data Classification](#data-classification)
5. [Field Redaction](#field-redaction)
6. [IP Masking](#ip-masking)
7. [Retention Policies](#retention-policies)
8. [GDPR Data Subject Requests](#gdpr-data-subject-requests)
9. [Compliance Reports](#compliance-reports)
10. [API Endpoints](#api-endpoints)
11. [Events](#events)
12. [Best Practices](#best-practices)

---

## Overview

SwX-API includes a compliance audit framework extending the core audit log with GDPR compliance, data classification, field redaction, IP masking, retention policies, and data subject request handling.

- **Data classification** tags audit entries with PII, PHI, FINANCIAL, CONFIDENTIAL, or PUBLIC
- **Access results** track why access was denied (insufficient role, consent required, data classification, policy)
- **Field redaction** auto-redacts SSN, credit cards, emails, phone numbers, passwords, and DOB in audit context
- **IP masking** partially or fully masks IP addresses stored in audit logs
- **Retention policies** DB-driven rules for archiving, deleting, or anonymizing data past retention periods
- **GDPR data subject requests** full lifecycle for access, deletion, portability, rectification, and restriction requests
- **Compliance reports** aggregate audit data by severity, classification, access result, and outcome

---

## Configuration

Compliance settings are in `swx_core/config/settings.py` and serve as defaults. Runtime configuration is stored in the `swx_compliance_config` table for DB-driven flexibility.

```python
COMPLIANCE_ENABLED: bool = True
COMPLIANCE_DEFAULT_SEVERITY: str = "info"
COMPLIANCE_DEFAULT_DATA_CLASSIFICATION: str = "PUBLIC"
COMPLIANCE_DEFAULT_IP_MASKING: str = "partial"  # full | partial | none
COMPLIANCE_DEFAULT_RETENTION_DAYS: int = 365
COMPLIANCE_AUTO_MASK_IP: bool = True
COMPLIANCE_AUTO_REDACT_FIELDS: bool = True
COMPLIANCE_DATA_SUBJECT_REQUEST_EXPIRY_DAYS: int = 30
```

DB-driven config uses `${ENV_VAR}` credential resolution:
```json
{"key": "ip_masking_mode", "value": "${COMPLIANCE_IP_MASKING:partial}", "category": "masking"}
```

---

## Database Models

### `swx_compliance_config`

DB-driven compliance configuration with `${ENV_VAR}` resolution.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `key` | String(100) | Unique config key (indexed) |
| `value` | Text | Config value (JSON or `${ENV_VAR}`) |
| `category` | String(50) | Config category (indexed) |
| `description` | Text | Optional description |
| `is_active` | Boolean | Active flag (default: true) |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### `swx_data_subject_request`

GDPR data subject requests.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `user_id` | UUID | FK to swx_users (indexed) |
| `request_type` | String(50) | access, deletion, portability, rectification, restriction (indexed) |
| `status` | String(30) | pending, processing, completed, rejected, expired (indexed) |
| `description` | Text | Optional user description |
| `admin_notes` | Text | Optional admin notes |
| `requested_at` | DateTime | When request was made |
| `completed_at` | DateTime | When request was fulfilled |
| `expires_at` | DateTime | Request expiry |
| `verification_token` | String(255) | Unique verification token |
| `verified` | Boolean | Whether request is verified |

### `swx_retention_policy`

DB-driven data retention configuration per resource type.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `resource_type` | String(100) | Resource type (unique, indexed) |
| `retention_days` | Integer | Days to retain |
| `action_on_expiry` | String(30) | archive, delete, anonymize |
| `is_active` | Boolean | Active flag |
| `description` | Text | Optional description |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### Extended `swx_audit_log` columns

| Column | Type | Default | Description |
|---|---|---|---|
| `severity` | String(20) | "info" | info, warning, critical (indexed) |
| `data_classification` | String(50) | null | PII, PHI, FINANCIAL, CONFIDENTIAL, PUBLIC (indexed) |
| `access_result` | String(50) | null | ALLOWED, DENIED_* (indexed) |
| `masked_ip` | String(50) | null | IP after masking |

---

## Data Classification

The `DataClassification` enum defines sensitivity levels:

| Value | Description |
|---|---|
| `PUBLIC` | Publicly available data |
| `PII` | Personally Identifiable Information |
| `PHI` | Protected Health Information |
| `FINANCIAL` | Financial data (accounts, transactions) |
| `CONFIDENTIAL` | Business-confidential data |

The `check_data_access()` service evaluates classification access rules from DB config:
```python
result = await check_data_access(session, actor_type="user", data_classification="PHI")
# Returns: "ALLOWED" | "DENIED_DATA_CLASSIFICATION" | "DENIED_CONSENT_REQUIRED"
```

---

## Field Redaction

Auto-redacts sensitive fields in audit log context when `COMPLIANCE_AUTO_REDACT_FIELDS=True`.

| Field | Redaction Pattern |
|---|---|
| `ssn` | `***-**-****` |
| `password` | `[REDACTED]` |
| `credit_card` | `****-****-****-XXXX` |
| `email` | `u***@domain.com` |
| `phone` | `***-***-XXXX` |
| `dob` | `XX/XX/YYYY` |

Custom rules can be added via `add_redaction_rule()` or DB config.

---

## IP Masking

Auto-masks IP addresses in audit logs when `COMPLIANCE_AUTO_MASK_IP=True`.

| Mode | Example Input | Example Output |
|---|---|---|
| `full` | `192.168.1.100` | `0.0.0.0` |
| `partial` | `192.168.1.100` | `192.168.*.*` |
| `none` | `192.168.1.100` | `192.168.1.100` |

Mode is DB-driven via `swx_compliance_config` where `key="ip_masking_mode"`.

---

## Retention Policies

Retention policies are stored in DB and applied per resource type:

```python
# Create a retention policy
policy = await upsert_retention_policy(session, RetentionPolicyCreate(
    resource_type="audit_log",
    retention_days=365,
    action_on_expiry="anonymize"
))

# Apply retention (processes all active policies)
results = await apply_retention(session)
```

Supported `action_on_expiry` values:
- `anonymize` — Removes PII fields (actor_id, IP, user_agent, context) from audit logs
- `delete` — Deletes the records entirely
- `archive` — Marks for archival (implementation-specific)

---

## GDPR Data Subject Requests

Full lifecycle for GDPR compliance:

1. **Create** — User submits access/deletion/portability/rectification/restriction request
2. **Verify** — User confirms ownership via verification token
3. **Process** — Admin processes verified request (generates data export, schedules deletion)
4. **Complete** — Request marked as completed with admin notes

```python
# User creates a request
request = await create_data_subject_request(session, user_id, DataSubjectRequestCreate(
    request_type="access",
    description="I want a copy of my data"
))

# User verifies ownership
verified = await verify_request(session, request.id, request.verification_token)

# Admin processes
result = await process_data_subject_request(session, request.id, admin_notes="Data exported")

# User can also export their own data directly
data = await export_own_data(session, user_id)
```

---

## Compliance Reports

Generate aggregated compliance reports:

```python
report = await generate_compliance_report(session, start_date=start, end_date=end)
# Returns: {"total": N, "by_severity": {...}, "by_classification": {...},
#           "by_access_result": {...}, "by_outcome": {...}}
```

---

## API Endpoints

### Admin Endpoints (`/admin/compliance`)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/compliance/logs` | List compliance-augmented audit logs |
| GET | `/admin/compliance/report` | Generate compliance report |
| GET | `/admin/compliance/config` | List compliance configs |
| PUT | `/admin/compliance/config` | Upsert compliance config |
| GET | `/admin/compliance/retention-policies` | List retention policies |
| PUT | `/admin/compliance/retention-policies` | Upsert retention policy |
| POST | `/admin/compliance/retention/apply` | Apply retention policies |
| GET | `/admin/compliance/data-subject-requests` | List all data subject requests |
| POST | `/admin/compliance/data-subject-requests/{id}/process` | Process a request |

### User Endpoints (`/user/gdpr`)

| Method | Path | Description |
|---|---|---|
| GET | `/user/gdpr/requests` | List own data subject requests |
| POST | `/user/gdpr/requests` | Create data subject request |
| POST | `/user/gdpr/requests/{id}/verify` | Verify request ownership |
| POST | `/user/gdpr/requests/{id}/cancel` | Cancel own request |
| GET | `/user/gdpr/export` | Export own data |

---

## Events

| Event | Payload | Trigger |
|---|---|---|
| `compliance.data_accessed` | action, classification, access_result, actor_id | Compliance audit recorded |
| `compliance.consent_violation` | action, actor_id, resource_id | Access denied due to consent |
| `compliance.data_exported` | report/user_id, source | Report generated or data exported |
| `compliance.data_deleted` | request_id, user_id | Deletion request processed |
| `compliance.retention_policy_applied` | resource_type, action, affected | Retention policy executed |
| `compliance.retention_policy_updated` | resource_type | Retention policy upserted |
| `compliance.config_updated` | key, category | Compliance config upserted |
| `compliance.redaction_rule_updated` | key | Redaction rule added |
| `compliance.request_created` | request_id, user_id, request_type | Data subject request created |
| `compliance.request_verified` | request_id, user_id | Request verified |
| `compliance.request_processed` | request_id, user_id, request_type, status | Request processed |
| `compliance.request_cancelled` | request_id, user_id | Request cancelled |

---

## Best Practices

1. **Classify data early** — Tag all audit entries with `data_classification` to enable access control
2. **Use DB-driven config** — Store compliance settings in `swx_compliance_config` with `${ENV_VAR}` for secrets
3. **Auto-mask IPs** — Keep `COMPLIANCE_AUTO_MASK_IP=True` to comply with privacy regulations
4. **Auto-redact fields** — Keep `COMPLIANCE_AUTO_REDACT_FIELDS=True` to prevent PII leakage in audit context
5. **Set retention policies** — Define policies for each resource type to automate data lifecycle
6. **Verify before processing** — Always verify data subject requests before processing to prevent unauthorized access
7. **Monitor compliance reports** — Regularly generate reports to audit access patterns and violations