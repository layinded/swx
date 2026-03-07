# Authentication

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Domain Separation](#domain-separation)
3. [Token Types](#token-types)
4. [Authentication Flows](#authentication-flows)
5. [Token Security](#token-security)
6. [OAuth Integration](#oauth-integration)
7. [Usage Examples](#usage-examples)

---

## Overview

SwX-API uses **JWT (JSON Web Tokens)** for authentication with **domain separation** to ensure security. The framework supports three authentication domains:

1. **Admin Domain** - System administrators
2. **User Domain** - Application users
3. **System Domain** - Internal system operations

Each domain has:
- Separate authentication endpoints
- Separate token audiences
- Separate user models
- Isolated access control

---

## Domain Separation

### Why Domain Separation?

Domain separation prevents **privilege escalation** and **cross-domain access**:

- ✅ Admin users cannot access user domain resources
- ✅ User tokens cannot access admin endpoints
- ✅ System operations are isolated from user/admin

### Admin Domain

**Model:** `AdminUser`  
**Endpoint:** `/api/admin/auth/`  
**Token Audience:** `"admin"`  
**Routes:** `/api/admin/*`

**Characteristics:**
- Separate database table (`admin_user`)
- Separate authentication flow
- Admin-only access
- Cannot access user domain

**Example:**
```python
from swx_core.auth.admin.dependencies import AdminUserDep

@router.get("/admin/users")
async def list_all_users(admin: AdminUserDep):
    # Only admin tokens can access
    return await get_all_users()
```

### User Domain

**Model:** `User`  
**Endpoint:** `/api/auth/`  
**Token Audience:** `"user"`  
**Routes:** `/api/user/*`, `/api/*`

**Characteristics:**
- User database table (`user`)
- User authentication flow
- Team-based isolation
- Cannot access admin domain

**Example:**
```python
from swx_core.auth.user.dependencies import UserDep

@router.get("/user/profile")
async def get_profile(user: UserDep):
    # Only user tokens can access
    return user
```

### System Domain

**Purpose:** Internal system operations  
**Token Audience:** `"system"`  
**Routes:** None (internal only)

**Characteristics:**
- Background jobs
- CLI commands
- System-to-system communication
- No HTTP endpoints

---

## Token Types

### Access Tokens

**Purpose:** Short-lived tokens for API access

**Characteristics:**
- **Lifetime:** Configurable (default: 7 days)
- **Storage:** Client-side (browser, mobile app)
- **Audience:** `"admin"` or `"user"`
- **Scopes:** Permission scopes (optional)

**Structure:**
```json
{
  "sub": "user@example.com",
  "aud": "user",
  "exp": 1234567890,
  "scope": "user:read user:write",
  "auth_provider": "local"
}
```

### Refresh Tokens

**Purpose:** Long-lived tokens for obtaining new access tokens

**Characteristics:**
- **Lifetime:** Configurable (default: 30 days)
- **Storage:** Database (`refresh_token` table)
- **Revocation:** On password change, logout
- **Security:** Separate secret key

**Usage:**
```python
POST /api/auth/refresh
{
  "refresh_token": "eyJ..."
}
```

### Password Reset Tokens

**Purpose:** One-time tokens for password reset

**Characteristics:**
- **Lifetime:** Configurable (default: 48 hours)
- **Storage:** Not stored (JWT only)
- **Audience:** `"user"`
- **Security:** Separate secret key

---

## Authentication Flows

### Admin Login Flow

```
1. Client → POST /api/admin/auth/
   {
     "username": "admin@example.com",
     "password": "securepassword"
   }

2. Server validates credentials
   - Checks AdminUser table
   - Verifies password hash
   - Validates user is active

3. Server generates access token
   - Audience: "admin"
   - Subject: admin email
   - Expiration: 7 days (configurable)

4. Server returns token
   {
     "access_token": "eyJ...",
     "token_type": "bearer"
   }

5. Client stores token
   - Use in Authorization header
   - Authorization: Bearer eyJ...
```

**Code Example:**
```python
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from swx_core.models.token import Token
from swx_core.auth.admin.dependencies import get_current_admin_user

router = APIRouter(prefix="/admin/auth")

@router.post("/", response_model=Token)
async def login_admin(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: SessionDep,
):
    # Validate credentials
    admin = await authenticate_admin(session, form_data.username, form_data.password)
    
    # Generate token
    access_token = create_token(
        subject=admin.email,
        audience=TokenAudience.ADMIN,
        expires_delta=timedelta(days=7),
    )
    
    return Token(access_token=access_token, token_type="bearer")
```

### User Login Flow

```
1. Client → POST /api/auth/
   {
     "username": "user@example.com",
     "password": "securepassword"
   }

2. Server validates credentials
   - Checks User table
   - Verifies password hash
   - Validates user is active

3. Server generates tokens
   - Access token (audience: "user")
   - Refresh token (stored in DB)

4. Server returns tokens
   {
     "access_token": "eyJ...",
     "refresh_token": "eyJ...",
     "token_type": "bearer"
   }

5. Client stores tokens
   - Access token: Memory/localStorage
   - Refresh token: Secure storage
```

**Code Example:**
```python
from swx_core.services.auth_service import login_service

@router.post("/auth/", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: SessionDep,
    request: Request,
):
    token = await login_service(
        session=session,
        email=form_data.username,
        password=form_data.password,
        request=request,
    )
    return token
```

### Token Refresh Flow

```
1. Client → POST /api/auth/refresh
   {
     "refresh_token": "eyJ..."
   }

2. Server validates refresh token
   - Checks signature
   - Validates expiration
   - Verifies token in database
   - Checks user is active

3. Server generates new tokens
   - New access token
   - New refresh token (updates DB)

4. Server returns new tokens
   {
     "access_token": "eyJ...",
     "refresh_token": "eyJ...",
     "token_type": "bearer"
   }
```

**Code Example:**
```python
from swx_core.services.auth_service import refresh_access_token_service

@router.post("/auth/refresh", response_model=Token)
async def refresh_token(
    request_data: TokenRefreshRequest,
    session: SessionDep,
    request: Request,
):
    token = await refresh_access_token_service(
        session=session,
        request_data=request_data,
        request=request,
    )
    return token
```

---

## Token Security

### Audience Validation

**Purpose:** Prevent cross-domain token usage

**Implementation:**
```python
from swx_core.auth.core.jwt import decode_token, TokenAudience

# User token validation
payload = decode_token(token, TokenAudience.USER)  # ✅ Valid
payload = decode_token(token, TokenAudience.ADMIN)  # ❌ Raises InvalidAudienceError

# Admin token validation
payload = decode_token(token, TokenAudience.ADMIN)  # ✅ Valid
payload = decode_token(token, TokenAudience.USER)  # ❌ Raises InvalidAudienceError
```

**Security Guarantee:**
- Admin tokens **cannot** access user routes
- User tokens **cannot** access admin routes
- System tokens are **internal only**

### Token Expiration

**Configurable via runtime settings:**

```python
# Database settings (runtime configurable)
auth.access_token_expire_minutes = 10080  # 7 days
auth.refresh_token_expire_days = 30
auth.email_reset_token_expire_hours = 48

# Fallback to .env if DB setting missing
ACCESS_TOKEN_EXPIRE_MINUTES=10080
REFRESH_TOKEN_EXPIRE_DAYS=30
```

**Usage:**
```python
from swx_core.services.settings_helper import get_token_expiration

access_token_expires = await get_token_expiration(session, "access")
refresh_token_expires = await get_token_expiration(session, "refresh")
```

### Token Revocation

**Refresh tokens are revoked on:**
- Password change
- Explicit logout
- User deactivation
- Security incident

**Implementation:**
```python
from swx_core.security.refresh_token_service import revoke_all_tokens

# Revoke all tokens for user
await revoke_all_tokens(session, user_email)
```

### Secret Keys

**Separate secrets for each token type:**
- `SECRET_KEY` - Access tokens
- `REFRESH_SECRET_KEY` - Refresh tokens
- `PASSWORD_RESET_SECRET_KEY` - Password reset tokens

**Security:**
- Secrets stored in `.env` (never in database)
- Different secrets prevent token type confusion
- Rotate secrets periodically

---

## OAuth Integration

### Social Login Support

SwX-API supports OAuth providers:
- Google
- Facebook
- GitHub (configurable)

### OAuth Flow

```
1. Client → GET /api/oauth/{provider}/authorize
   - Redirects to OAuth provider

2. User authenticates with provider
   - Provider redirects back with code

3. Server exchanges code for token
   - Validates code
   - Gets user info from provider

4. Server creates/updates user
   - Creates user if new
   - Updates auth_provider field

5. Server generates tokens
   - Access token
   - Refresh token

6. Server returns tokens
   {
     "access_token": "eyJ...",
     "refresh_token": "eyJ...",
     "token_type": "bearer"
   }
```

**Code Example:**
```python
from swx_core.services.auth_service import login_social_user_service

@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    session: SessionDep,
):
    # Exchange code for user info
    user_info = await exchange_oauth_code(provider, code)
    
    # Create/update user
    user = await get_or_create_social_user(session, user_info)
    
    # Generate tokens
    token = await login_social_user_service(session, user.email)
    return token
```

---

## Usage Examples

### Protecting Routes

**User Domain:**
```python
from swx_core.auth.user.dependencies import UserDep

@router.get("/user/profile")
async def get_profile(user: UserDep):
    return user
```

**Admin Domain:**
```python
from swx_core.auth.admin.dependencies import AdminUserDep

@router.get("/admin/dashboard")
async def admin_dashboard(admin: AdminUserDep):
    return {"message": "Admin only"}
```

### Getting Current User

**In Route Handler:**
```python
@router.get("/user/profile")
async def get_profile(user: UserDep):
    return {
        "id": str(user.id),
        "email": user.email,
        "team_id": str(user.team_id) if user.team_id else None,
    }
```

**In Service:**
```python
async def get_user_profile_service(session: AsyncSession, user_id: UUID):
    user = await get_user_by_id(session, user_id)
    return user
```

### Token Validation

**Manual Validation:**
```python
from swx_core.auth.core.jwt import decode_token, TokenAudience

try:
    payload = decode_token(token, TokenAudience.USER)
    email = payload.get("sub")
except InvalidTokenError:
    raise HTTPException(401, "Invalid token")
```

---

## Security Best Practices

### ✅ DO

- Use HTTPS in production
- Store tokens securely (httpOnly cookies, secure storage)
- Validate token audience
- Check token expiration
- Revoke tokens on password change
- Use separate secrets for each token type
- Rotate secrets periodically

### ❌ DON'T

- Store tokens in localStorage (XSS risk)
- Share tokens between domains
- Use same secret for all token types
- Ignore token expiration
- Skip audience validation
- Log tokens in plain text

---

## Troubleshooting

### Common Issues

**1. "Invalid token" error**
- Check token expiration
- Verify token audience matches route
- Ensure token signature is valid

**2. "User not found" error**
- Verify user exists in database
- Check user is active
- Ensure email matches token subject

**3. "Invalid audience" error**
- Admin token used on user route (or vice versa)
- Use correct token for domain

**4. Token expiration too short**
- Update `auth.access_token_expire_minutes` in settings
- Or set `ACCESS_TOKEN_EXPIRE_MINUTES` in .env

---

## Next Steps

- Read [RBAC Documentation](./RBAC.md) for authorization
- Read [Security Model](../05-security/SECURITY_MODEL.md) for security details
- Read [API Usage Guide](../06-api-usage/API_USAGE.md) for API examples

---

**Status:** Authentication documented, ready for implementation.
