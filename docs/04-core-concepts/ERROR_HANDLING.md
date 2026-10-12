# Error Handling

**Version:** 1.0.0  
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [Error Hierarchy](#error-hierarchy)
3. [SwXError Base Class](#swxerror-base-class)
4. [Error Classes](#error-classes)
5. [Encryption Errors](#encryption-errors)
6. [Convenience Functions](#convenience-functions)
7. [Usage Examples](#usage-examples)

---

## Overview

SwX-Core provides a **structured error hierarchy** (`swx_core/utils/errors.py`) with consistent error codes, HTTP status codes, and JSON-serializable error details. All custom exceptions inherit from `SwXError`, which maps to standard HTTP status codes.

---

## Error Hierarchy

```
Exception
├── SwXError (base, 400)
│   ├── ValidationError (422)
│   ├── NotFoundError (404)
│   ├── UnauthorizedError (401)
│   ├── ForbiddenError (403)
│   ├── ConflictError (409)
│   ├── RateLimitError (429)
│   ├── ServiceUnavailableError (503)
│   ├── DatabaseError (500)
│   ├── ExternalServiceError (502)
│   ├── ConfigurationError (500)
│   ├── QuotaExceededError (429)
│   └── PolicyViolationError (403)
└── EncryptionError (ValueError)
    └── DecryptionError
```

---

## SwXError Base Class

```python
class SwXError(Exception):
    def __init__(
        self,
        message: str = "An error occurred",
        code: str = "ERROR",
        details: Dict[str, Any] = None,
        status_code: int = 400,
    ):
        ...

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to structured JSON response."""
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
        }
```

---

## Error Classes

| Class | Code | Status | Purpose |
|---|---|---|---|
| `ValidationError` | `VALIDATION_ERROR` | 422 | Input validation failures |
| `NotFoundError` | `NOT_FOUND` | 404 | Resource not found |
| `UnauthorizedError` | `UNAUTHORIZED` | 401 | Authentication required |
| `ForbiddenError` | `FORBIDDEN` | 403 | Permission denied |
| `ConflictError` | `CONFLICT` | 409 | Resource conflict |
| `RateLimitError` | `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded |
| `ServiceUnavailableError` | `SERVICE_UNAVAILABLE` | 503 | Service down |
| `DatabaseError` | `DATABASE_ERROR` | 500 | Database operation failed |
| `ExternalServiceError` | `EXTERNAL_SERVICE_ERROR` | 502 | External service failed |
| `ConfigurationError` | `CONFIGURATION_ERROR` | 500 | Configuration error |
| `QuotaExceededError` | `QUOTA_EXCEEDED` | 429 | Quota/rate limit exceeded |
| `PolicyViolationError` | `POLICY_VIOLATION` | 403 | Policy rule violation |

---

## Encryption Errors

Separate from `SwXError`, the encryption module uses `ValueError` subclasses:

| Class | Purpose |
|---|---|
| `EncryptionError` | Invalid encryption config or encryption failure |
| `DecryptionError` | Ciphertext cannot be decrypted (subclass of `EncryptionError`) |

---

## Convenience Functions

```python
from swx_core.utils.errors import (
    not_found, unauthorized, forbidden,
    bad_request, conflict, rate_limited, service_unavailable,
)

# Each raises the corresponding exception:
not_found("User", user_id)                    # → NotFoundError(404)
unauthorized("Token expired")                  # → UnauthorizedError(401)
forbidden("Not allowed", permission="admin")   # → ForbiddenError(403)
bad_request("Invalid input")                   # → SwXError(400)
conflict("Already exists", resource="user")    # → ConflictError(409)
rate_limited(60)                               # → RateLimitError(429)
service_unavailable("database")                # → ServiceUnavailableError(503)
```

---

## Usage Examples

### In Route Handlers

```python
from swx_core.utils.errors import NotFoundError, ForbiddenError

@router.get("/users/{user_id}")
async def get_user(user_id: UUID, session: SessionDep, user: AuthenticatedUserDep):
    db_user = await session.get(User, user_id)
    if db_user is None:
        raise NotFoundError("User", str(user_id))
    if db_user.tenant_id != user.tenant_id:
        raise ForbiddenError("Cannot access user from different tenant")
    return db_user
```

### Error Response Format

All `SwXError` subclasses produce a consistent JSON response:

```json
{
    "success": false,
    "error": {
        "code": "NOT_FOUND",
        "message": "User with id 'abc-123' not found",
        "details": {}
    }
}
```