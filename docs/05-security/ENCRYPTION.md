# Encryption Service

**Version:** 1.0.0  
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [How It Works](#how-it-works)
3. [Key Rotation](#key-rotation)
4. [Configuration](#configuration)
5. [API Reference](#api-reference)
6. [Usage Examples](#usage-examples)

---

## Overview

The **Encryption Service** (`swx_core/security/encryption.py`) provides versioned Fernet encryption with key rotation for sensitive fields (webhook secrets, SSO client secrets, refresh tokens, LLM API keys).

Key features:

- **Versioned ciphertext** — each encrypted value is prefixed with `v1:` or `v2:` for correct key selection on decrypt
- **Dual-key rotation** — supports `SWX_ENCRYPTION_KEY` (current) and `SWX_ENCRYPTION_KEY_PREVIOUS` (legacy) for zero-downtime key rollover
- **PBKDF2 derivation** — keys are derived using PBKDF2-HMAC-SHA256 with 480,000 iterations (OWASP 2023 recommendation)
- **Thread-safe** — key resolution uses `RLock` for safe concurrent access
- **Convenience aliases** — `encrypt_value`, `decrypt_value`, `encrypt_api_key`, `decrypt_api_key`

---

## How It Works

```
Plaintext → EncryptionService.encrypt()
  │
  ├─ Resolve key versions from settings (cached until config changes)
  ├─ Derive Fernet key via PBKDF2(master_key, salt)
  ├─ Encrypt plaintext with current version key
  └─ Return "v2:<ciphertext>"

Ciphertext → EncryptionService.decrypt()
  │
  ├─ Parse version prefix (e.g. "v2:")
  ├─ Select key version for decryption
  ├─ Try primary Fernet key, then legacy fallback
  └─ Return plaintext
```

---

## Key Rotation

When you need to rotate the encryption key:

1. Set `SWX_ENCRYPTION_KEY` to the new key
2. Set `SWX_ENCRYPTION_KEY_PREVIOUS` to the old key
3. Deploy — new encrypts with `v2:`, old ciphertext still decrypts
4. After all old ciphertext is re-encrypted, remove `SWX_ENCRYPTION_KEY_PREVIOUS`

The service automatically detects the dual-key configuration and creates two key versions:

- **v1**: uses `SWX_ENCRYPTION_KEY_PREVIOUS` (legacy), with fallback to `SWX_ENCRYPTION_KEY` derived with the default salt
- **v2**: uses `SWX_ENCRYPTION_KEY` (current), no fallback

---

## Configuration

| Setting | Default | Description |
|---|---|---|
| `SWX_ENCRYPTION_KEY` | *(required)* | Current master key for encryption |
| `SWX_ENCRYPTION_KEY_PREVIOUS` | `None` | Previous master key for rotation |
| `SWX_ENCRYPTION_SALT` | `swx-default-encryption-salt` | PBKDF2 salt bytes |

---

## API Reference

### Module-Level Functions

```python
from swx_core.security.encryption import encrypt_value, decrypt_value, is_encrypted

# Encrypt
ciphertext = encrypt_value("my-secret-api-key")
# Returns: "v2:gAAAAA..."

# Decrypt
plaintext = decrypt_value(ciphertext)
# Returns: "my-secret-api-key"

# Check if a value looks like versioned ciphertext
is_encrypted(ciphertext)  # True
is_encrypted("plain-text")  # False
```

### `EncryptionService` (Class API)

```python
from swx_core.security.encryption import EncryptionService

service = EncryptionService()
ciphertext = service.encrypt("my-secret")
plaintext = service.decrypt(ciphertext)
```

---

## Usage Examples

### Encrypting LLM API Keys

```python
from swx_core.security.encryption import encrypt_api_key, decrypt_api_key

# On provider config creation
encrypted = encrypt_api_key(raw_api_key)
config.credentials = {"api_key": encrypted}

# On provider config resolution
raw_key = decrypt_api_key(config.credentials["api_key"])
```

### Key Rotation

```bash
# Step 1: Set both keys
SWX_ENCRYPTION_KEY=new-master-key-abc123
SWX_ENCRYPTION_KEY_PREVIOUS=old-master-key-xyz789

# Step 2: Deploy — new values use v2, old values still decrypt

# Step 3: After re-encrypting all old values, remove the previous key
SWX_ENCRYPTION_KEY=new-master-key-abc123
# SWX_ENCRYPTION_KEY_PREVIOUS is no longer set
```