# Authentication

**Version:** 2.8.0  
**Last Updated:** 2026-07-22

---

## Table of Contents

1. [Overview](#overview)
2. [Domain Separation](#domain-separation)
3. [Token Types](#token-types)
4. [Authentication Flows](#authentication-flows)
5. [Token Security](#token-security)
6. [Auth Caching](#auth-caching)
7. [OAuth Integration](#oauth-integration)
8. [Usage Examples](#usage-examples)

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
**Endpoints:** `/api/admin/auth/`  
**Token Audience:** `"admin"`  
**Routes:** `/api/admin/*`

**Available Endpoints:**

| Endpoint | Method | Description |
|---|---|---|
| `/api/admin/auth/` | POST | Login (returns access + refresh tokens) |
| `/api/admin/auth/refresh` | POST | Refresh access token |
| `/api/admin/auth/revoke` | POST | Revoke refresh token (logout) |
| `/api/admin/auth/cookie/login` | POST | Login with httpOnly cookies (BFF pattern) |
| `/api/admin/auth/cookie/refresh` | POST | Refresh tokens via httpOnly cookies |
| `/api/admin/auth/cookie/logout` | POST | Clear httpOnly auth cookies |

**Characteristics:**
- Separate database table (`admin_user`)
- Separate authentication flow
- Admin-only access
- Cannot access user domain
- Supports both token and cookie-based authentication

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

3. Server generates tokens
   - Access token (audience: "admin")
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
from swx_core.controllers.admin_auth_controller import login_admin_controller
from swx_core.models.token import Token

@router.post("/admin/auth/", response_model=Token)
async def login_admin(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: SessionDep,
    request: Request,
):
    return await login_admin_controller(session, form_data, request)
```

### Admin Token Refresh Flow

```
1. Client → POST /api/admin/auth/refresh
   {
     "refresh_token": "eyJ..."
   }

2. Server validates refresh token
   - Checks signature and expiration
   - Verifies token exists in database
   - Confirms admin user is active

3. Server returns new tokens
   {
     "access_token": "eyJ...",
     "refresh_token": "eyJ...",
     "token_type": "bearer"
   }
```

### Admin Cookie-Based Authentication

Admin auth also supports HTTP-only cookies for browser-based admin panels (BFF pattern):

#### Login with Cookies

```http
POST /api/admin/auth/cookie/login
Content-Type: application/x-www-form-urlencoded

username=admin@example.com&password=securepassword
```

**Response:**
```json
{
  "email": "admin@example.com",
  "message": "Admin authentication successful"
}
```

**Cookies Set:**
- `swx_access_token` - HTTP-only, secure, path `/`
- `swx_refresh_token` - HTTP-only, secure, path `/api`

#### Refresh Tokens via Cookies

```http
POST /api/admin/auth/cookie/refresh
```

**Cookies Updated:**
- New `swx_access_token` cookie
- New `swx_refresh_token` cookie

#### Logout via Cookies

```http
POST /api/admin/auth/cookie/logout
```

**Cookies Cleared:**
- `swx_access_token` cookie deleted
- `swx_refresh_token` cookie deleted

**Frontend Example (Next.js Admin Panel):**
```javascript
async function adminLogin(email, password) {
  const response = await fetch('/api/admin/auth/cookie/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `username=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`,
    credentials: 'include'
  })

  if (response.ok) {
    window.location.href = '/admin/dashboard'
  }
}

async function adminRefresh() {
  const response = await fetch('/api/admin/auth/cookie/refresh', {
    method: 'POST',
    credentials: 'include'
  })
  return response.ok
}

async function adminLogout() {
  await fetch('/api/admin/auth/cookie/logout', {
    method: 'POST',
    credentials: 'include'
  })
  window.location.href = '/admin/login'
}
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

## Cookie-Based Authentication

SwX-API supports **HTTP-only cookie authentication** for browser-based applications following the **Backend-for-Frontend (BFF) pattern**.

### Why Cookie-Based Auth?

| Method | XSS Resistant | CSRF Resistant | Auto-Attach | Token Management |
|--------|---------------|----------------|-------------|------------------|
| Authorization Header | ❌ No* | ✅ Yes | ❌ Manual | ❌ Client-side |
| HTTP-only Cookie | ✅ Yes | ✅ With SameSite | ✅ Automatic | ✅ Server-side |

*Authorization header is secure if stored correctly, but vulnerable if stored in localStorage.

**Benefits:**
- **XSS Protection**: JavaScript cannot access HTTP-only cookies
- **Automatic Token Handling**: Browser automatically includes cookies with requests
- **CSRF Protection**: SameSite attribute prevents cross-origin attacks
- **Simpler Frontend**: No token storage or management code needed

### Cookie Configuration

```bash
# .env
COOKIE_ACCESS_TOKEN_NAME=swx_access_token
COOKIE_REFRESH_TOKEN_NAME=swx_refresh_token
COOKIE_SECURE=true                 # False for local dev (http://)
COOKIE_SAMESITE=lax                # 'strict' or 'lax'
COOKIE_DOMAIN=                     # Optional, for subdomain sharing
```

**Cookie Security Settings:**
- `httponly=True` - Prevents JavaScript access (XSS protection)
- `secure=True` - Only sent over HTTPS (production only)
- `samesite=lax` - CSRF protection while allowing top-level navigations

### Cookie-Based Endpoints

#### 1. Login with Cookies

```http
POST /api/auth/cookie/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=securepassword
```

**Response:**
```json
{
  "email": "user@example.com",
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Cookies Set:**
- `swx_access_token` - HTTP-only, secure, path `/`
- `swx_refresh_token` - HTTP-only, secure, path `/api`

**Frontend Example:**
```javascript
async function login(email, password) {
  const response = await fetch('/api/auth/cookie/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `username=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`,
    credentials: 'include'  // Required for cookies
  })
  
  if (response.ok) {
    // Cookies automatically set by browser
    window.location.href = '/dashboard'
  }
}
```

#### 2. Get Current User

```http
GET /api/auth/me
```

**Response:**
```json
{
  "id": "uuid-string",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "team_id": "uuid-string"
}
```

**Frontend Example:**
```javascript
async function getCurrentUser() {
  const response = await fetch('/api/auth/me', {
    credentials: 'include'  // Required for cookies
  })
  
  if (response.ok) {
    return await response.json()
  }
  
  return null  // Not authenticated
}

// Check auth state on app boot
const user = await getCurrentUser()
if (user) {
  showDashboard()
} else {
  showLogin()
}
```

#### 3. Refresh Tokens

```http
POST /api/auth/cookie/refresh
```

**Response:**
```json
{
  "status": "ok"
}
```

**Cookies Updated:**
- New `swx_access_token` cookie
- New `swx_refresh_token` cookie

**Frontend Example:**
```javascript
let refreshPromise = null

async function refreshAccessToken() {
  // Prevent concurrent refresh requests
  if (refreshPromise) {
    return refreshPromise
  }
  
  refreshPromise = fetch('/api/auth/cookie/refresh', {
    method: 'POST',
    credentials: 'include'
  })
  
  try {
    await refreshPromise
  } finally {
    refreshPromise = null
  }
}

// Auto-refresh on 401
fetch('/api/user/profile', { credentials: 'include' })
  .then(response => {
    if (response.status === 401) {
      return refreshAccessToken().then(() => fetch('/api/user/profile'))
    }
    return response
  })
```

#### 4. Logout

```http
POST /api/auth/cookie/logout
```

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

**Cookies Cleared:**
- `swx_access_token` cookie deleted
- `swx_refresh_token` cookie deleted

**Frontend Example:**
```javascript
async function logout() {
  await fetch('/api/auth/cookie/logout', {
    method: 'POST',
    credentials: 'include'
  })
  
  // Cookies cleared by backend
  window.location.href = '/login'
}
```

### Dual Authentication Support

SwX-API supports **both** Authorization header and cookie-based authentication simultaneously:

```python
from swx_core.auth.user.dependencies import UserDep

@router.get("/user/profile")
async def get_profile(user: UserDep):
    # Works with both:
    # 1. Authorization: Bearer <token>
    # 2. Cookie: swx_access_token=<token>
    return user
```

**Priority Order:**
1. Authorization header (if present)
2. Cookie (if header not present)

**Implementation:**
```python
from swx_core.auth.core.bearer_or_cookie import BearerOrCookieAuth

# Automatically checks both sources
user_auth = BearerOrCookieAuth()

async def get_current_user(
    session: SessionDep,
    token: HTTPAuthorizationCredentials | None = Depends(user_auth),
    request: Request
) -> User:
    # Token extracted from:
    # 1. Authorization header
    # 2. HTTP-only cookie
    
    if not token:
        raise HTTPException(401, "Authentication required")
    
    # Validate token...
```

### Migration from Header to Cookie

**Before (Authorization Header):**
```javascript
// Store token in localStorage (XSS vulnerable)
localStorage.setItem('token', response.access_token)

// Manually attach to every request
fetch('/api/user/profile', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
```

**After (HTTP-only Cookie):**
```javascript
// No token storage needed - browser handles it
fetch('/api/auth/cookie/login', {
  method: 'POST',
  body: form,
  credentials: 'include'  // Cookies automatically included
})

// All subsequent requests include cookies automatically
fetch('/api/user/profile', {
  credentials: 'include'
})
```

### Security Considerations

**Cookie Security:**
- ✅ HTTP-only prevents JavaScript access (XSS protection)
- ✅ Secure flag ensures HTTPS-only transmission
- ✅ SameSite=Lax prevents CSRF attacks
- ✅ Path restrictions limit cookie scope

**Best Practices:**
1. Use `credentials: 'include'` in all fetch requests
2. Configure CORS to allow credentials: `allow_credentials=True`
3. Set `COOKIE_SECURE=true` in production (false for local dev)
4. Use `SameSite=Lax` for OAuth flows, `SameSite=Strict` for pure cookie auth

---

## OAuth Integration

### Social Login Support

SwX-API supports OAuth providers with **PKCE** and **Backend-for-Frontend (BFF) pattern**:
- Google
- Facebook
- GitHub, LinkedIn, Apple, etc. (configurable)

### OAuth 2.0 Security

SwX-API implements **OAuth 2.0 Authorization Code Flow with PKCE** following RFC 9700 best practices:

| Feature | Implementation |
|---------|----------------|
| **PKCE** | Mandatory for all providers (S256 method) |
| **CSRF Protection** | State parameter validation |
| **Token Storage** | HTTP-only cookies (XSS resistant) |
| **Token Delivery** | Server-side, never exposed to client |

### OAuth Flow (BFF Pattern)

```
1. Frontend → GET /api/oauth/{provider}
   - Backend generates PKCE challenge
   - Stores verifier in session
   - Redirects to OAuth provider

2. User authenticates with provider
   - Provider redirects back with code + state

3. Backend → GET /api/oauth/{provider}/callback?code=...&state=...
   - Validates state (CSRF protection)
   - Exchanges code + PKCE verifier for tokens
   - Gets user info from provider
   - Creates/updates user

4. Backend sets HTTP-only cookies and redirects
   - Sets: swx_access_token (httpOnly, secure)
   - Sets: swx_refresh_token (httpOnly, secure)
   - Redirects to: {FRONTEND_HOST}/auth/callback

5. Frontend receives redirect
   - Cookies already set (no token handling needed)
   - Redirect to dashboard
```

### HTTP-Only Cookie Authentication

**Why cookies over localStorage?**

| Storage | XSS Resistant | CSRF Resistant | Auto-Attach |
|---------|---------------|----------------|-------------|
| localStorage | ❌ No | ✅ Yes | ❌ Manual |
| HTTP-only Cookie | ✅ Yes | ✅ With SameSite | ✅ Automatic |

**Cookie Configuration:**

```bash
# .env
COOKIE_ACCESS_TOKEN_NAME=swx_access_token
COOKIE_REFRESH_TOKEN_NAME=swx_refresh_token
COOKIE_SECURE=true                 # False for local dev
COOKIE_SAMESITE=lax                # 'strict' or 'lax'
COOKIE_DOMAIN=                     # Optional, for subdomain sharing
```

### Frontend Integration

#### API Requests with Cookies

```javascript
// All API requests automatically include cookies
fetch('/api/user/profile', {
  credentials: 'include'  // Required for cookies
})

// Or with axios
axios.get('/api/user/profile', {
  withCredentials: true
})
```

#### OAuth Callback Page

```javascript
// /auth/callback page - no token parsing needed!
async function handleOAuthCallback() {
  // Cookies already set by backend
  // Just redirect to dashboard
  window.location.href = '/dashboard'
}

// Handle errors
const urlParams = new URLSearchParams(window.location.search)
const error = urlParams.get('error')
if (error) {
  // Show error: csrf_mismatch, token_fetch_failed, missing_email
  showError(error)
}
```

#### Logout with Cookies

```javascript
async function logout() {
  await fetch('/api/auth/cookie/logout', {
    method: 'POST',
    credentials: 'include'
  })
  // Cookies cleared by backend
  window.location.href = '/login'
}
```

### Events

OAuth logins emit `user.login.social` event:

```python
from swx_core.events import event_bus, Event

@event_bus.on("user.login.social")
async def on_social_login(event: Event):
    email = event.payload["email"]
    provider = event.payload["provider"]  # google, facebook, etc.
    is_new_user = event.payload["is_new_user"]
    
    # Send welcome email for new users
    if is_new_user:
        await send_welcome_email(email, provider)
```

**Event Payload:**
```json
{
  "email": "user@example.com",
  "user_id": "uuid-string",
  "provider": "google",
  "is_new_user": false,
  "context": {
    "provider": "google",
    "is_new_user": false
  }
}
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
- Store tokens in HTTP-only cookies (XSS resistant)
- Use `credentials: 'include'` for cookie-based auth
- Validate token audience
- Check token expiration
- Revoke tokens on password change
- Use separate secrets for each token type
- Rotate secrets periodically
- Configure `COOKIE_SAMESITE=lax` or `strict`

### ❌ DON'T

- Store tokens in localStorage (XSS risk)
- Share tokens between domains
- Use same secret for all token types
- Ignore token expiration
- Skip audience validation
- Log tokens in plain text
- Disable PKCE for OAuth flows

---

## Auth Caching

SwX-API v2.8.0 introduces **L1/L2 auth caching** to reduce database queries on every authenticated request.

### Architecture

```
Request → L1 Cache (process-local) → L2 Cache (Redis) → Database
                ↓ hit                  ↓ hit                ↓ miss
             return user          return user          query + populate L1+L2
```

- **L1 cache**: In-process Python dict with timestamp-based TTL. Zero network round-trip.
- **L2 cache**: Redis with structured key naming. Shared across processes.
- **Graceful degradation**: If Redis is unavailable, falls back to L1-only, then database.

### Key Naming

Cache keys follow the pattern: `{env}:{app}:{scope}:{resource}:{identifier}:{version}`

Examples:
- `prod:nh:user:profile:user@example.com:v1` — cached user profile
- `prod:nh:user:profile:550e8400:v1` — cached user profile by ID
- `prod:nh:user:permissions:550e8400:v1` — cached user permissions
- `prod:nh:admin:profile:admin@example.com:v1` — cached admin profile

### Cached Fields

**User profile** (excludes `hashed_password`):
`id`, `email`, `full_name`, `is_active`, `is_superuser`, `auth_provider`, `provider_id`, `avatar_url`, `preferred_language`, `tenant_id`, `created_at`, `updated_at`

**Admin profile** (excludes `hashed_password`):
`id`, `email`, `full_name`, `is_active`, `auth_provider`, `provider_id`, `created_at`

**User permissions**:
`id`, `name`, `description`, `resource_type`, `action`

### Configuration

| Setting | Default | Description |
|---|---|---|
| `USER_CACHE_ENABLED` | `False` | Enable L1/L2 cache for user auth lookups |
| `USER_CACHE_TTL` | `300` | TTL in seconds for cached user profiles (5 min) |
| `USER_PERMISSIONS_CACHE_TTL` | `120` | TTL in seconds for cached user permissions (2 min) |
| `USER_CACHE_L1_MAX_ENTRIES` | `1000` | Maximum entries in process-local L1 cache |
| `ADMIN_CACHE_ENABLED` | `False` | Enable L1/L2 cache for admin auth lookups |
| `ADMIN_CACHE_TTL` | `300` | TTL in seconds for cached admin profiles (5 min) |

**Enable caching in `.env`:**

```env
USER_CACHE_ENABLED=true
ADMIN_CACHE_ENABLED=true
USER_CACHE_TTL=300
USER_PERMISSIONS_CACHE_TTL=120
```

### Invalidation Hooks

Cache invalidation is automatic on data mutations:

| Event | Invalidation |
|---|---|
| User profile update | Profile cache (by id + email) |
| Password change | Profile cache (by id + email) |
| User deletion | Profile cache (by id + email) |
| Role assigned to user | Permissions cache (by user_id) |
| Role removed from user | Permissions cache (by user_id) |
| Permission assigned to role | ALL permission caches |
| Permission removed from role | ALL permission caches |

### Manual Invalidation

For programmatic cache control:

```python
from swx_core.auth.auth_cache import (
    invalidate_user_cache,
    invalidate_user_permissions,
    invalidate_admin_cache,
    invalidate_all_permissions,
)

# Invalidate all cached data for a user
await invalidate_user_cache(user_id="550e8400...", email="user@example.com")

# Invalidate only permissions for a user
await invalidate_user_permissions(user_id="550e8400...")

# Invalidate all cached data for an admin
await invalidate_admin_cache(admin_id="...", email="admin@example.com")

# Invalidate ALL cached permissions (bulk invalidation)
await invalidate_all_permissions()
```

### Backward Compatibility

- **Default is OFF**: `USER_CACHE_ENABLED=False` and `ADMIN_CACHE_ENABLED=False` means no caching. All requests hit the database as before.
- **No migration required**: No database schema changes. Simply enable the settings to activate caching.
- **Redis optional**: If Redis is unavailable, L1 cache still works (per-process only).

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
