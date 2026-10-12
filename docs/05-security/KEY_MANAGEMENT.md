# Key Management

**Version:** 1.0.0
**Last Updated:** 2026-08-24
**SOC 2 Reference:** CC6.7 — Encryption at Rest

---

## Table of Contents

1. [Overview](#overview)
2. [Key Generation](#key-generation)
3. [Key Rotation](#key-rotation)
4. [Failure Mode — Fail-Closed Startup](#failure-mode--fail-closed-startup)
5. [Data Classification](#data-classification)
6. [Ciphertext Prefixes](#ciphertext-prefixes)
7. [Dual-Write Migration Strategy](#dual-write-migration-strategy)
8. [CLI Backfill](#cli-backfill)
9. [Environment Variables](#environment-variables)

---

## Overview

SwX-API uses a single `EncryptionService` (Fernet + PBKDF2-HMAC-SHA256, 480k iterations) for all at-rest encryption. The same master key (`SWX_ENCRYPTION_KEY`) encrypts multiple data domains, each identified by a ciphertext prefix so auditors can distinguish them in the database.

See [ENCRYPTION.md](./ENCRYPTION.md) for the full EncryptionService API reference.

---

## Key Generation

Generate a 32-byte base64 key for `SWX_ENCRYPTION_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

This produces a 43-character URL-safe base64 string (256 bits of entropy). Store it in your `.env` file or secrets manager — **never in code or version control**.

For key rotation, generate a second key for `SWX_ENCRYPTION_KEY_PREVIOUS`.

---

## Key Rotation

Zero-downtime rotation using dual-key support:

### Step-by-Step

1. **Generate new key:**
   ```bash
   NEW_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   ```

2. **Set both keys in `.env`:**
   ```bash
   # Current key becomes previous
   SWX_ENCRYPTION_KEY_PREVIOUS=<old-key>
   SWX_ENCRYPTION_KEY=<new-key>
   ```

3. **Deploy / restart the application.** New encryptions use `v2:<new-key>`. Old ciphertext (`v1:<old-key>`) still decrypts.

4. **Backfill existing rows** to re-encrypt with the new key:
   ```bash
   swx security:encrypt-secrets
   ```
   This CLI command re-encrypts all plaintext and `v1:`-prefixed rows to `v2:`.

5. **After all rows are re-encrypted**, remove `SWX_ENCRYPTION_KEY_PREVIOUS`:
   ```bash
   # Remove from .env
   # SWX_ENCRYPTION_KEY_PREVIOUS=  ← delete this line
   ```

6. **Deploy again.** Application now runs with a single key.

### What Happens During Rotation

| Phase | `SWX_ENCRYPTION_KEY` | `SWX_ENCRYPTION_KEY_PREVIOUS` | Encrypt | Decrypt |
|---|---|---|---|---|
| Normal | key-A | *(unset)* | `v1:key-A` | `v1:key-A` |
| Dual-key | key-B | key-A | `v2:key-B` | `v1:key-A`, `v2:key-B` |
| Final | key-B | *(unset)* | `v2:key-B` | `v2:key-B` |

---

## Failure Mode — Fail-Closed Startup

When `PII_ENCRYPTION_ENABLED=True`, the application **refuses to start** if `SWX_ENCRYPTION_KEY` is missing or invalid. This is enforced in `swx_core/main.py` lifespan:

```python
# Step 0: Fail-closed validation
if settings.PII_ENCRYPTION_ENABLED:
    validate_encryption_key()  # Raises EncryptionError if key is missing/invalid
```

**Why fail-closed?** If the key is missing and PII encryption is enabled, the application would silently write plaintext PII into columns that should be encrypted — a data classification violation. Refusing to start ensures this never happens silently.

**Production recommendation:** Always set `PII_ENCRYPTION_ENABLED=True` in production. Leave it `False` in development for easier local testing.

---

## Data Classification

Each encrypted field in the database carries a **ciphertext prefix** that identifies its data classification domain. This allows auditors and data-classification tools to distinguish PII ciphertext from webhook-secret ciphertext without decrypting.

| Prefix | Domain | Example Column | Service |
|---|---|---|---|
| `pii:` | Personally Identifiable Information | `swx_users.email_encrypted`, `swx_users.full_name_encrypted` | `pii_encryption_service` |
| `v1:` / `v2:` | General secrets (webhooks, SSO, refresh tokens, LLM keys) | `swx_refresh_token.token`, `swx_webhook_endpoint.secret`, `swx_sso_provider.client_secret` | `encryption.py` |

### PII Fields (Encrypted at Rest)

| Table | Column | Classification | Dual-Write |
|---|---|---|---|
| `swx_users` | `email_encrypted` | PII | Yes — plaintext `email` column retained |
| `swx_users` | `full_name_encrypted` | PII | Yes — plaintext `full_name` column retained |

### Secret Fields (Encrypted at Rest)

| Table | Column | Classification | Service |
|---|---|---|---|
| `swx_refresh_token` | `token` | Secret | `refresh_token_service._encrypt_token` |
| `swx_webhook_endpoint` | `secret` | Secret | `webhook_service._encrypt_secret` |
| `swx_sso_provider` | `client_secret` | Secret | `sso_provider_service._encrypt_field` |
| `swx_sso_provider` | `certificate` | Secret | `sso_provider_service._encrypt_field` |
| `swx_llm_provider_config` | `encrypted_api_key` | Secret | `llm_service` |
| `swx_email_provider_config` | `password` | Secret | `management_service._encrypt_field` |
| `swx_email_provider_config` | `api_key` | Secret | `management_service._encrypt_field` |
| `swx_sms_provider_config` | `auth_token` | Secret | `management_service._encrypt_field` |
| `swx_sms_provider_config` | `api_key` | Secret | `management_service._encrypt_field` |
| `swx_users` | `mfa_secret` | Secret | `mfa_service` |

### Hashed Fields (Not Reversible — No Encryption Needed)

| Table | Column | Algorithm |
|---|---|---|
| `swx_users` | `hashed_password` | bcrypt |
| `swx_admin_user` | `hashed_password` | bcrypt |
| `swx_api_key` | `hashed_key` | SHA-256 |
| `swx_mfa_recovery_code` | `code_hash` | bcrypt |

### Key Rotation Tracking

| Table | Column | Purpose |
|---|---|---|
| `swx_api_key` | `rotated_from_id` | FK to the previous key when an API key is rotated |

---

## Ciphertext Prefixes

### General Secrets: `v1:` / `v2:`

The core `EncryptionService` prefixes ciphertext with a version label:

```
v1:gAAAAABk...  ← encrypted with SWX_ENCRYPTION_KEY_PREVIOUS
v2:gAAAAABk...  ← encrypted with SWX_ENCRYPTION_KEY (current)
```

During dual-key rotation, `v1:` ciphertext decrypts with the previous key, `v2:` with the current key. New encryptions always produce `v2:`.

### PII Fields: `pii:v2:gAAAAABk...`

PII ciphertext carries an additional `pii:` prefix **before** the version label:

```python
from swx_core.security.encryption import encrypt_pii_field, decrypt_pii_field

ciphertext = encrypt_pii_field("user@example.com")
# "pii:v2:gAAAAABk..."

plaintext = decrypt_pii_field(ciphertext)
# "user@example.com"
```

The `pii:` prefix:
- Makes PII ciphertext immediately identifiable in database audits
- Allows data-classification tools to tag PII columns without decryption
- Is stripped transparently by `decrypt_pii_field` before Fernet decryption

---

## Dual-Write Migration Strategy

PII fields use a **dual-write** pattern to support zero-downtime migration:

### Phase 1: Add Encrypted Columns (Current)

```
swx_users:
  email              = "user@example.com"          ← plaintext, still in use
  email_encrypted    = "pii:v2:gAAAAABk..."        ← encrypted, also populated
  full_name          = "Jane Doe"                   ← plaintext, still in use
  full_name_encrypted = "pii:v2:gAAAAABk..."       ← encrypted, also populated
```

- When `PII_ENCRYPTION_ENABLED=True`:
  - **Writes**: Both plaintext and encrypted columns are populated
  - **Reads**: Queries use `email_encrypted` for lookups; `decrypt_user_pii()` overwrites the in-memory `email` with the decrypted value
  - **Queries**: `WHERE email_encrypted = encrypt_pii_field(input_email)` instead of `WHERE email = input_email`

- When `PII_ENCRYPTION_ENABLED=False`:
  - **Writes**: Encrypted columns are left NULL (no-op)
  - **Reads**: Plaintext columns are used directly
  - **Queries**: Standard `WHERE email = input_email`

### Phase 2: Backfill (Manual)

```bash
swx security:encrypt-secrets
```

Re-encrypts any plaintext rows and ensures all existing data has encrypted copies.

### Phase 3: Drop Plaintext Columns (Next Major Version)

In a future major version, the plaintext `email` and `full_name` columns will be dropped. All lookups will use `email_encrypted` exclusively.

---

## CLI Backfill

The `swx security:encrypt-secrets` command encrypts any plaintext secret columns that should be encrypted:

```bash
# Encrypt all plaintext secrets across all tables
swx security:encrypt-secrets

# Dry run (show what would be encrypted)
swx security:encrypt-secrets --dry-run
```

Affected tables:
- `swx_refresh_token.token`
- `swx_webhook_endpoint.secret`
- `swx_sso_provider.client_secret` and `certificate`
- `swx_llm_provider_config.encrypted_api_key`
- `swx_email_provider_config.password` and `api_key`
- `swx_sms_provider_config.auth_token` and `api_key`
- `swx_users.mfa_secret`

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SWX_ENCRYPTION_KEY` | Yes (production) | Current Fernet master key (32-byte base64) |
| `SWX_ENCRYPTION_KEY_PREVIOUS` | No | Previous master key for rotation |
| `SWX_ENCRYPTION_SALT` | No | PBKDF2 salt (defaults to `swx-default-encryption-salt`) |
| `PII_ENCRYPTION_ENABLED` | No | Enable PII dual-write encryption (default: `False`) |

### Production Recommendation

```bash
# .env.production
SWX_ENCRYPTION_KEY=<strong-random-key>
PII_ENCRYPTION_ENABLED=True
```

### Development

```bash
# .env (development)
# PII_ENCRYPTION_ENABLED=False  ← default, plaintext for easier debugging
SWX_ENCRYPTION_KEY=dev-encryption-key-change-me-in-prod
```

---

## Next Steps

- [ENCRYPTION.md](./ENCRYPTION.md) — EncryptionService API reference
- [SECRETS_MANAGEMENT.md](./SECRETS_MANAGEMENT.md) — Environment variable management
- [SECURITY_MODEL.md](./SECURITY_MODEL.md) — Overall security architecture

---

**Status:** Key management documented. SOC 2 CC6.7 — Encryption at Rest.