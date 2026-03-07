# Token Security

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Token Types](#token-types)
3. [Token Structure](#token-structure)
4. [Token Validation](#token-validation)
5. [Token Expiration](#token-expiration)
6. [Token Revocation](#token-revocation)
7. [Security Best Practices](#security-best-practices)
8. [Common Vulnerabilities](#common-vulnerabilities)
9. [Troubleshooting](#troubleshooting)

---

## Overview

SwX-API uses **JWT (JSON Web Tokens)** for authentication. Tokens are cryptographically signed, include audience validation, and support scopes for fine-grained permissions.

### Key Security Features

- ✅ **Cryptographic Signing** - HMAC-SHA256 signatures
- ✅ **Audience Validation** - Domain separation enforced
- ✅ **Expiration** - Time-limited tokens
- ✅ **Scopes** - Permission-based access
- ✅ **Separate Secrets** - Different secrets per token type
- ✅ **Refresh Tokens** - Long-lived refresh, short-lived access

---

## Token Types

### 1. Access Tokens

**Purpose:** Short-lived tokens for API access

**Characteristics:**
- Short expiration (default: 7 days, configurable)
- Contains user identity (email)
- Contains scopes (permissions)
- Audience-specific (admin/user/system)
- Stored in memory (client-side)

**Usage:**
```python
# Create access token
access_token = create_token(
    subject=user.email,
    audience=TokenAudience.USER,
    expires_delta=timedelta(days=7),
    scopes=["user:read", "user:write"]
)

# Use in requests
headers = {"Authorization": f"Bearer {access_token}"}
```

**Security:**
- Short expiration limits exposure window
- Scopes limit access to specific permissions
- Audience validation prevents cross-domain use

### 2. Refresh Tokens

**Purpose:** Long-lived tokens for obtaining new access tokens

**Characteristics:**
- Long expiration (default: 30 days, configurable)
- Stored in database (revocable)
- Single-use (optional, can be reused)
- No scopes (only used for refresh)
- Audience-specific

**Usage:**
```python
# Create refresh token
refresh_token = await create_refresh_token(
    session,
    user.email,
    expires_delta=timedelta(days=30)
)

# Refresh access token
new_access_token = await refresh_access_token_service(
    session,
    refresh_token
)
```

**Security:**
- Database storage enables revocation
- Long expiration reduces login frequency
- Separate from access tokens

### 3. Password Reset Tokens

**Purpose:** Time-limited tokens for password reset

**Characteristics:**
- Short expiration (default: 48 hours, configurable)
- Separate secret key
- Single-use (optional)
- User audience only
- Email-based subject

**Usage:**
```python
# Generate reset token
reset_token = await generate_password_reset_token(
    session,
    email=user.email
)

# Verify reset token
email = verify_password_reset_token(reset_token)
```

**Security:**
- Separate secret prevents confusion with access tokens
- Short expiration limits exposure
- Email-based validation

---

## Token Structure

### JWT Payload

**Access Token:**
```json
{
  "exp": 1706284800,           // Expiration timestamp
  "sub": "user@example.com",   // Subject (email)
  "aud": "user",               // Audience (admin/user/system)
  "auth_provider": "local",    // Auth provider
  "scope": "user:read user:write"  // Permissions (optional)
}
```

**Refresh Token:**
```json
{
  "exp": 1708876800,           // Expiration timestamp
  "sub": "user@example.com",   // Subject (email)
  "aud": "user",               // Audience
  "auth_provider": "local"     // Auth provider
  // No scopes (refresh only)
}
```

**Password Reset Token:**
```json
{
  "exp": 1706371200,           // Expiration timestamp
  "sub": "user@example.com",   // Subject (email)
  "aud": "user",               // Audience
  "auth_provider": "local"     // Auth provider
  // No scopes (reset only)
}
```

### Token Signature

**Algorithm:** HMAC-SHA256 (HS256)

**Secret Keys:**
- Access tokens: `SECRET_KEY` (or domain-specific)
- Refresh tokens: `REFRESH_SECRET_KEY` (or same as access)
- Password reset: `PASSWORD_RESET_SECRET_KEY` (separate)

**Signature Verification:**
```python
# Token is signed with secret key
signature = HMAC-SHA256(header + payload, secret_key)

# Verification
payload = jwt.decode(
    token,
    secret_key,
    algorithms=["HS256"],
    audience="user"  # Audience validation
)
```

---

## Token Validation

### Validation Steps

**1. Signature Verification**
```python
# Verify token signature
try:
    payload = jwt.decode(
        token,
        secret_key,
        algorithms=["HS256"]
    )
except jwt.InvalidSignatureError:
    # Token signature invalid
    raise HTTPException(401, "Invalid token")
```

**2. Audience Validation**
```python
# Verify audience matches expected domain
if payload.get("aud") != expected_audience:
    raise jwt.InvalidAudienceError("Token audience mismatch")
```

**3. Expiration Check**
```python
# JWT library automatically checks expiration
# If expired, raises jwt.ExpiredSignatureError
```

**4. Scope Validation (Optional)**
```python
# Extract scopes from token
scopes = payload.get("scope", "").split()

# Check if required scope present
if "user:write" not in scopes:
    raise HTTPException(403, "Insufficient permissions")
```

### Complete Validation Flow

```python
async def get_current_user(token: str):
    try:
        # 1. Decode and validate signature
        payload = decode_token(token, TokenAudience.USER)
        
        # 2. Extract subject (email)
        email = payload.get("sub")
        if not email:
            raise HTTPException(401, "Invalid token payload")
        
        # 3. Lookup user
        user = await get_user_by_email(session, email)
        if not user:
            raise HTTPException(404, "User not found")
        
        # 4. Check active status
        if not user.is_active:
            raise HTTPException(400, "User inactive")
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
```

---

## Token Expiration

### Expiration Times

**Access Tokens:**
- Default: 7 days (configurable via settings)
- Runtime configurable (database settings)
- Short expiration limits exposure

**Refresh Tokens:**
- Default: 30 days (configurable via settings)
- Runtime configurable (database settings)
- Long expiration reduces login frequency

**Password Reset Tokens:**
- Default: 48 hours (configurable via settings)
- Runtime configurable (database settings)
- Short expiration for security

### Expiration Configuration

**Via Settings:**
```python
# Runtime settings (database)
auth.access_token_expire_minutes = 10080  # 7 days
auth.refresh_token_expire_days = 30
auth.email_reset_token_expire_hours = 48
```

**Via Code:**
```python
from swx_core.services.settings_helper import get_token_expiration

# Get expiration from settings
access_expires = await get_token_expiration(session, "access")
refresh_expires = await get_token_expiration(session, "refresh")
reset_expires = await get_token_expiration(session, "password_reset")
```

---

## Token Revocation

### Refresh Token Revocation

**Revoke Single Token:**
```python
# Revoke specific refresh token
await revoke_refresh_token(session, refresh_token)
```

**Revoke All Tokens:**
```python
# Revoke all refresh tokens for user
await revoke_all_tokens(session, user.email)
```

**Revocation Storage:**
- Refresh tokens stored in database
- Revocation marked in database
- Revoked tokens cannot be used

### Access Token Revocation

**Access tokens are stateless (JWT):**
- Cannot be revoked individually
- Relies on expiration
- Use refresh token revocation for immediate effect

**Best Practice:**
```python
# On logout, revoke refresh token
await revoke_refresh_token(session, refresh_token)

# Access token will expire naturally
# Or user must refresh to get new access token
```

---

## Security Best Practices

### ✅ DO

1. **Use separate secrets per domain**
   ```python
   # ✅ Good - Separate secrets
   SECRET_KEY=admin-secret
   USER_SECRET_KEY=user-secret
   SYSTEM_SECRET_KEY=system-secret
   ```

2. **Use short access token expiration**
   ```python
   # ✅ Good - Short expiration
   access_token_expires = timedelta(days=7)  # 7 days
   ```

3. **Store refresh tokens securely**
   ```python
   # ✅ Good - Database storage
   refresh_token = await create_refresh_token(session, email)
   # Stored in database, can be revoked
   ```

4. **Validate audience on every request**
   ```python
   # ✅ Good - Audience validation
   payload = decode_token(token, TokenAudience.USER)
   # Ensures token cannot cross domains
   ```

5. **Use HTTPS in production**
   ```python
   # ✅ Good - HTTPS enforced
   # Tokens transmitted over encrypted connection
   ```

6. **Revoke tokens on logout**
   ```python
   # ✅ Good - Revoke on logout
   await revoke_refresh_token(session, refresh_token)
   ```

### ❌ DON'T

1. **Don't store tokens in localStorage**
   ```javascript
   // ❌ Bad - localStorage vulnerable to XSS
   localStorage.setItem("token", token);
   
   // ✅ Good - httpOnly cookies (if possible)
   // Or memory storage
   ```

2. **Don't log tokens**
   ```python
   # ❌ Bad - Token in logs
   logger.info(f"Token: {token}")
   
   # ✅ Good - No token in logs
   logger.info(f"User authenticated: {email}")
   ```

3. **Don't use long access token expiration**
   ```python
   # ❌ Bad - Long expiration
   access_token_expires = timedelta(days=365)  # Too long
   
   # ✅ Good - Short expiration
   access_token_expires = timedelta(days=7)
   ```

4. **Don't reuse secrets across environments**
   ```python
   # ❌ Bad - Same secret everywhere
   SECRET_KEY=shared-secret  # Dev, staging, prod
   
   # ✅ Good - Different secrets per environment
   SECRET_KEY=dev-secret     # Dev
   SECRET_KEY=staging-secret # Staging
   SECRET_KEY=prod-secret    # Prod
   ```

5. **Don't include sensitive data in tokens**
   ```python
   # ❌ Bad - Sensitive data in token
   payload = {
       "sub": user.email,
       "password": user.password  # DON'T DO THIS
   }
   
   # ✅ Good - Only necessary data
   payload = {
       "sub": user.email,
       "scope": "user:read"
   }
   ```

---

## Common Vulnerabilities

### 1. Token Theft

**Threat:** Stolen JWT tokens

**Mitigation:**
- Short expiration limits exposure window
- Refresh tokens enable revocation
- HTTPS prevents interception
- Audience validation prevents cross-domain use

**Detection:**
- Audit logging of token usage
- Alert on unusual access patterns
- Monitor for token reuse

### 2. Token Replay

**Threat:** Reusing expired or revoked tokens

**Mitigation:**
- Expiration enforced by JWT library
- Refresh token revocation in database
- Short access token expiration

**Detection:**
- Audit logging of token validation failures
- Monitor for expired token usage

### 3. Audience Confusion

**Threat:** Using admin token on user endpoints

**Mitigation:**
- Audience validation on every request
- Separate secrets per domain (optional)
- Domain-specific dependencies

**Detection:**
- Audit logging of audience mismatches
- Alert on cross-domain attempts

### 4. Token Forgery

**Threat:** Creating fake tokens

**Mitigation:**
- Cryptographic signature verification
- Secret key protection
- Strong secret keys

**Detection:**
- Invalid signature errors
- Alert on signature validation failures

---

## Troubleshooting

### Common Issues

**1. "Invalid token" errors**
- Check token signature
- Verify secret key matches
- Check token expiration
- Verify audience matches

**2. "Token expired" errors**
- Check token expiration time
- Verify system clock is correct
- Refresh token if expired

**3. "Audience mismatch" errors**
- Verify token audience matches endpoint
- Check domain separation
- Verify token type (admin vs user)

**4. "Invalid signature" errors**
- Verify secret key matches
- Check for secret key rotation
- Verify algorithm matches (HS256)

### Debugging

**Decode token (for debugging):**
```python
import jwt

# Decode without verification (for debugging only)
payload = jwt.decode(token, options={"verify_signature": False})
print(payload)
```

**Check token expiration:**
```python
import jwt
from datetime import datetime

payload = jwt.decode(token, options={"verify_signature": False})
exp = payload.get("exp")
exp_time = datetime.fromtimestamp(exp)
print(f"Token expires: {exp_time}")
```

**Verify secret key:**
```python
# Check if secret key matches
try:
    payload = jwt.decode(token, secret_key, algorithms=["HS256"])
    print("Token signature valid")
except jwt.InvalidSignatureError:
    print("Token signature invalid - secret key mismatch")
```

---

## Next Steps

- Read [Secrets Management Documentation](./SECRETS_MANAGEMENT.md) for secret key handling
- Read [Security Best Practices](./SECURITY_BEST_PRACTICES.md) for production security
- Read [Security Model Documentation](./SECURITY_MODEL.md) for overall security architecture

---

**Status:** Token security documented, ready for implementation.
