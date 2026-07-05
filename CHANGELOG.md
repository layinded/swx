# Changelog

All notable changes to this project will be documented in this file.

## [2.7.39] - 2026-07-05

### Fixed - CRITICAL TeamInvitationService Session Method Bug

**Severity:** Critical (ALL team invitation endpoints blocked)

#### CRITICAL-4: TeamInvitationService Uses session.exec() on AsyncSession

**Fixed:** Replaced all `.exec()` calls with `.execute()` for SQLAlchemy AsyncSession compatibility.

**Issue:** TeamInvitationService used `.exec()` (SQLModel sync method) but routes inject raw SQLAlchemy AsyncSession which doesn't have .exec() method. This caused AttributeError on all team invitation endpoints.

**Affected Endpoints:**
- POST /api/team-invitations/ — Internal Server Error
- GET /api/team-invitations/me — Internal Server Error
- GET /api/team-invitations/team/{team_id} — Internal Server Error
- POST /api/team-invitations/{token}/accept — Internal Server Error
- POST /api/team-invitations/{token}/reject — Internal Server Error
- DELETE /api/team-invitations/{invitation_id} — Internal Server Error

**Error:**
```
AttributeError: 'AsyncSession' object has no attribute 'exec'
```

**Root Cause:**
- Routes inject: `AsyncSession` (via `Depends(get_session)`)
- Service expected: SQLModel Session with `.exec()` method
- AsyncSession only has `.execute()` method

**Changes:**
- Lines 190, 197, 210, 214, 218, 222, 228, 236, 246, 258: `.exec()` → `.execute()`
- Lines 193, 205: `.all()` → `.scalars().all()`
- All helper methods: `.scalar_one_or_none()` unchanged (compatible)

**Before:**
```python
result = await self.session.exec(select(TeamInvitation).where(...))
return list(result.all())
```

**After:**
```python
result = await self.session.execute(select(TeamInvitation).where(...))
return list(result.scalars().all())
```

### Files Modified

- `swx_core/services/team_invitation_service.py` - Fixed all .exec() calls to use .execute()

### Migration Required

None - this is a code bug fix, not a schema change.

### Breaking Changes

None - all changes are internal implementation fixes.

---

## [2.7.38] - 2026-07-05

### Fixed - Critical Schema and API Bugs

**Severity:** Critical (3 schema fixes, 1 API bug fix)

#### CRITICAL-1: Team Model Missing Columns (Migration Fix)

**Fixed:** Added migration for missing `swx_team` columns required by model.

**Issue:** v2.7.37 Team model expected `owner_id`, `created_at`, `updated_at` columns that didn't exist in database.

**Resolution:**
- v2_7_22_schema_changes.py migration already exists (adds columns + FK cascades)
- Verified migration is correct and complete
- Created migration guide for FastPII team

**Migration adds:**
- `swx_team.owner_id` (UUID, nullable, FK → swx_users.id ON DELETE SET NULL)
- `swx_team.created_at` (TIMESTAMP, default NOW())
- `swx_team.updated_at` (TIMESTAMP, default NOW())
- FK cascade updates on swx_user_role, swx_team_member, swx_users, etc.

#### CRITICAL-2: TeamMember Missing Columns (NEW Migration)

**Fixed:** Created v2_7_38_team_member_timestamps.py migration.

**Issue:** TeamMember model expected `created_at` and `updated_at` columns that didn't exist in database.

**Resolution:**
- Created new migration: v2_7_38_team_member_timestamps.py
- Adds `swx_team_member.created_at` (TIMESTAMP, default NOW())
- Adds `swx_team_member.updated_at` (TIMESTAMP, default NOW())
- UniqueConstraint(team_id, user_id) already in v2_7_24 migration

**Migration:**
```python
# v2_7_38_team_member_timestamps.py
def upgrade() -> None:
    op.add_column("swx_team_member", sa.Column("created_at", ...))
    op.add_column("swx_team_member", sa.Column("updated_at", ...))
```

#### CRITICAL-3: API Field Name Bug

**Fixed:** `role_id` → `team_role_id` in team member endpoints.

**Issue:** TeamMemberPublic responses returned `role_id` (legacy system role) instead of `team_role_id` (team-scoped role).

**Before:**
```python
# team_route.py line 225
return [TeamMemberPublic(id=m.id, ..., role_id=m.role_id) for m in members]

# team_controller.py line 27
return TeamMemberPublic(id=member.id, ..., role_id=member.role_id)
```

**After:**
```python
# team_route.py line 225
return [TeamMemberPublic(
    id=m.id,
    team_id=m.team_id,
    user_id=m.user_id,
    team_role_id=m.team_role_id,
    created_at=m.created_at,
) for m in members]

# team_controller.py line 27
return TeamMemberPublic(
    id=member.id,
    team_id=member.team_id,
    user_id=member.user_id,
    team_role_id=member.team_role_id,
    created_at=member.created_at,
)
```

**Impact:**
- ✅ Correct field name (`team_role_id`)
- ✅ Added missing `created_at` field
- ✅ Breaking change: clients must update to use `team_role_id`

#### MEDIUM-1: Model Exports (Already Fixed)

**Status:** ✅ Already fixed in v2.7.37

All models properly exported in `swx_core/models/__init__.py`:
- TeamRole, TeamRoleCreate, TeamRoleUpdate, TeamRolePublic, DEFAULT_TEAM_ROLES
- TeamInvitation, TeamInvitationCreate, TeamInvitationPublic, InvitationStatus
- TeamMemberUpdate

**Usage:**
```python
from swx_core.models import TeamRole, TeamInvitation, TeamMemberUpdate
```

### Files Modified

- `swx_core/database/migrations/v2_7_38_team_member_timestamps.py` - NEW: TeamMember timestamp columns
- `swx_core/routes/admin/team_route.py` - Fixed role_id → team_role_id
- `swx_core/controllers/team_controller.py` - Fixed role_id → team_role_id
- `MIGRATION_GUIDE_v2.7.38.md` - NEW: Comprehensive migration guide

### Migration Chain

**Required Order:**
```
v2_7_22_schema_changes.py          # Team columns + FK cascades
    ↓
v2_7_24_team_member_unique.py      # TeamMember unique constraint
    ↓
v2_7_38_team_member_timestamps.py  # TeamMember timestamps
```

**Apply Migrations:**
```bash
alembic upgrade head
```

### Breaking Changes

**API Response Field Change:**
- `TeamMemberPublic.role_id` → `TeamMemberPublic.team_role_id`
- Clients must update to use `team_role_id` field
- Added `created_at` field to responses

**Database Schema:**
- New non-nullable columns with default values (safe migration)
- No data loss or transformation required
- Existing rows get `NOW()` as default timestamps

### Documentation

**Added:** `MIGRATION_GUIDE_v2.7.38.md` with:
- Complete migration chain
- Verification SQL queries
- Rollback procedures
- Breaking change details

### For FastPII Team

**Action Required:**
1. Upgrade to v2.7.38
2. Apply migrations in order:
   ```bash
   alembic upgrade v2_7_22_schema_changes
   alembic upgrade v2_7_24_team_member_unique
   alembic upgrade v2_7_38_team_member_timestamps
   ```
3. Update API clients to use `team_role_id` instead of `role_id`
4. See `MIGRATION_GUIDE_v2.7.38.md` for detailed instructions

## [2.7.37] - 2026-07-02

### Added - Rate Limiting & CSRF Implementation

**Severity:** High (2 security enhancements implemented)

#### Rate Limiting Implementation

**Added:** Built-in rate limiting for all authentication endpoints using `@rate_limit_by_ip` decorator.

**Protected Endpoints:**
| Endpoint | Rate Limit | Window | Action |
|----------|-----------|--------|--------|
| `/auth/login` | 5 requests | 1 minute | `login` |
| `/auth/register` | 3 requests | 1 hour | `register` |
| `/auth/password/recover/{email}` | 3 requests | 1 hour | `password_recover` |
| `/auth/cookie/login` | 5 requests | 1 minute | `cookie_login` |
| `/auth/cookie/refresh` | 10 requests | 1 minute | `cookie_refresh` |

**Implementation:**
- Applied `@rate_limit_by_ip` decorator to all auth endpoints
- Uses existing Redis-backed rate limiting middleware
- Configuration via settings: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_LOGIN_MAX`, etc.
- Protects against brute force, account spam, SMTP abuse

**Configuration:**
```python
# settings.py
RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_LOGIN_MAX: int = 5           # 5 req/min
RATE_LIMIT_REGISTER_MAX: int = 3        # 3 req/hour
RATE_LIMIT_PASSWORD_RECOVER_MAX: int = 3  # 3 req/hour
RATE_LIMIT_COOKIE_AUTH_MAX: int = 5    # 5 req/min
```

#### CSRF Protection Implementation

**Added:** CSRF middleware for cookie-based authentication using Double Submit Cookie pattern.

**Implementation:**
- Created `swx_core/middleware/csrf_middleware.py`
- Token stored in cookie (httpOnly=False, readable by JS)
- Token validated against `X-CSRF-Token` header
- Protects POST, PUT, PATCH, DELETE methods
- Exempt paths for health checks, metrics, public APIs

**Configuration:**
```python
# settings.py
CSRF_ENABLED: bool = True
CSRF_TOKEN_LENGTH: int = 32
CSRF_COOKIE_NAME: str = "csrf_token"
CSRF_HEADER_NAME: str = "X-CSRF-Token"
CSRF_COOKIE_MAX_AGE: int = 86400  # 24 hours
```

**CSRF Token Flow:**
1. Backend generates CSRF token, sets in cookie
2. Frontend reads token from cookie
3. Frontend includes token in `X-CSRF-Token` header
4. Backend validates token matches
5. State-changing requests protected

**Middleware Registration (Required):**
```python
from swx_core.middleware.csrf_middleware import CSRFMiddleware

app.add_middleware(
    CSRFMiddleware,
    cookie_name="csrf_token",
    header_name="X-CSRF-Token",
)
```

### Fixed - Type Safety

**Fixed:** Type annotation issues in settings and CSRF middleware:
- Fixed `all_cors_origins` type handling for `str | list[str]`
- Added proper generic type hints for `set[str]` and `list[str]`
- Improved code clarity

### Files Modified

- `swx_core/routes/access/auth_route.py` - Added rate limit decorators to auth endpoints
- `swx_core/middleware/csrf_middleware.py` - NEW: CSRF protection middleware
- `swx_core/config/settings.py` - Added CSRF and rate limit configuration, fixed type handling
- `docs/05-security/SECURITY_BEST_PRACTICES.md` - Updated with implementation details

### Migration Guide

**No migration required** - all changes are backward compatible.

**Recommended Actions:**
1. ✅ Upgrade to v2.7.37 for rate limiting and CSRF protection
2. ✅ Register CSRF middleware in your application (if using cookie-based auth)
3. ✅ Configure rate limits via environment variables (optional, defaults provided)
4. ✅ Update frontend to include CSRF token in request headers

## [2.7.36] - 2026-07-02

### Fixed - CRITICAL Security Vulnerabilities (FastPII Security Report)

**Severity:** Critical (1), High (2), Medium (2), Low (1)

#### Bug 1: CRITICAL - Cookie Login Token Leak

**Fixed:** `/auth/cookie/login` endpoint was returning access_token in response body, defeating httpOnly cookie security.

**Impact:**
- Access tokens were XSS-extractable from response body
- httpOnly cookies provided zero protection when same token available in JSON
- Frontend apps could accidentally store token in localStorage

**Fix:**
- Removed `access_token` and `token_type` from cookie_login response
- Response now returns only `{"email": "...", "message": "Authentication successful"}`
- Tokens accessible ONLY via httpOnly cookies (proper BFF pattern)

**Security Posture:**
| Before | After |
|--------|-------|
| Token in response body + cookie | Token ONLY in httpOnly cookie |
| XSS-extractable | XSS-resistant |
| Frontend can store in localStorage | Frontend MUST use cookies |

#### Bug 4: MEDIUM - Exception Handler Information Disclosure

**Fixed:** Generic exception handler was logging full exception strings including potentially sensitive data.

**Impact:**
- Database connection strings in logs
- File paths from IOError
- Internal service URLs from ConnectionError
- PII from custom exception messages

**Fix:**
- Changed to structured logging with `exc_type`, `path`, `request_id`
- Response includes `request_id` for debugging
- Uses `exc_info=True` for structured log aggregation systems
- No sensitive data in logs or responses

#### Bug 5: MEDIUM - Validation Error Handler Strips Details

**Fixed:** Validation errors returned generic message with no field details.

**Impact:**
- API consumers couldn't debug validation failures
- Increased support burden
- Poor developer experience

**Fix:**
- Returns structured validation errors: `{"detail": [...], "body": ...}`
- Field-level error details help consumers fix issues
- Uses WARNING level (appropriate for client errors)
- Standard FastAPI pattern (expected by clients)

#### Documentation: Rate Limiting & CSRF Protection

**Added:** Comprehensive security guidance in `docs/05-security/SECURITY_BEST_PRACTICES.md`

**Rate Limiting:**
- ⚠️ **swx-core does NOT include built-in rate limiting**
- Documented infrastructure-level implementations (Nginx, Redis)
- Provided application-level examples (slowapi)
- Listed recommended rate limits for auth endpoints

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/auth/login` | 5 requests | 1 minute |
| `/auth/register` | 3 requests | 1 hour |
| `/auth/password/recover` | 3 requests | 1 hour |
| `/auth/cookie/login` | 5 requests | 1 minute |

**CSRF Protection:**
- Documented SameSite=Lax default protection
- Explained CSRF token implementation patterns
- Warned about SameSite=None configuration risks
- Provided production security best practices

### Files Modified

- `swx_core/routes/access/auth_route.py` - Removed token from cookie_login response
- `swx_core/main.py` - Fixed exception and validation handlers
- `docs/05-security/SECURITY_BEST_PRACTICES.md` - Added rate limiting and CSRF guidance

### Migration Guide

**No migration required** - all changes are backward compatible.

**Recommended Actions:**
1. ✅ Upgrade to v2.7.36 immediately (critical security fix)
2. ✅ Implement rate limiting at infrastructure or application level
3. ✅ Review CSRF protection if using cookie-based auth
4. ✅ Update frontend to NOT expect `access_token` in cookie_login response

**Frontend Changes:**
```javascript
// ❌ Before: Token in response (INSECURE)
const { access_token } = await response.json();

// ✅ After: Token ONLY in cookie (SECURE)
const { email, message } = await response.json();
// Token automatically sent via httpOnly cookie
```

### Security Acknowledgments

Thanks to the FastPII Security Team for the responsible disclosure.

## [2.7.35] - 2026-07-02

### Fixed - CRITICAL: OAuth registration skips user.created event

**Severity:** High  
**Impact:** Social auth users received no billing, profile, PII policy, onboarding, notifications, or email verification.

**Root Cause:**  
OAuth registration called `create_social_user()` at repository layer directly, bypassing `register_user_service()` — the only place where `user.created` event is emitted.

**What Was Skipped:**
- NotificationListener (welcome notification)
- UserCreatedBillingListener (billing setup, profile, PII policy, onboarding)
- UserCreatedAuditListener (audit log)
- All custom `user.created` event listeners

**Fix:**
Extended `register_user_service()` to support social auth parameters:
- Added `auth_provider` parameter (defaults to `"local"`)
- Added `provider_id` parameter for provider-specific user IDs
- Updated OAuth routes (Google, Facebook, custom) to use `register_user_service()`
- Ensures all lifecycle hooks and events fire for social auth users

**Changes:**
- `swx_core/services/auth_service.py`: Added `auth_provider` and `provider_id` params
- `swx_core/routes/access/oauth_route.py`: Replaced `create_social_user()` with `register_user_service()`
- `swx_core/repositories/user_repository.py`: Added type annotations
- `docs/04-core-concepts/OAUTH_PROVIDERS.md`: Documented event emission

**Breaking Changes:** None  
- Parameters have sensible defaults
- Existing email/password registration unchanged
- `create_social_user()` kept for backward compatibility

**Event Flow:**
```python
# Before: No events
OAuth → create_social_user() → database INSERT

# After: Full lifecycle
OAuth → register_user_service()
       → pre_register_hook
       → create_user (with auth_provider/provider_id)
       → post_register_hook
       → emit user.created
       → all listeners fire
```

**Migration:** None required. All OAuth registrations now emit `user.created` event.

## [2.7.34] - 2026-07-01

### Added - HTTP-only Cookie Authentication (BFF Pattern)

Extended cookie-based authentication support for all auth flows, enabling XSS-resistant browser authentication.

#### Cookie Authentication for All Flows

- **Dual authentication support** - Authorization header AND HTTP-only cookies work simultaneously
- **Priority-based extraction** - Header first, cookie fallback for maximum compatibility
- **New authentication scheme** - `BearerOrCookieAuth` class extracts JWT from both sources
- **Backward compatible** - Existing Authorization header auth continues to work unchanged

#### New Endpoints

- `GET /api/auth/me` - Check current authentication state (works with cookies)
- `POST /api/auth/cookie/login` - Email/password login with HTTP-only cookies
- `POST /api/auth/cookie/refresh` - Token refresh using HTTP-only cookie
- `POST /api/auth/cookie/logout` - Clear auth cookies (added in v2.7.33, now documented)

#### Security Benefits

| Before | After |
|--------|-------|
| localStorage tokens (XSS vulnerable) | HTTP-only cookies (XSS resistant) |
| Manual token attachment | Automatic cookie inclusion |
| Client-side token management | Server-side cookie management |
| No CSRF protection | SameSite attribute protection |

#### Configuration

Same cookie settings introduced in v2.7.33 OAuth BFF pattern:
- `COOKIE_ACCESS_TOKEN_NAME` (default: `swx_access_token`)
- `COOKIE_REFRESH_TOKEN_NAME` (default: `swx_refresh_token`)
- `COOKIE_SECURE` (auto-adjusts for local dev)
- `COOKIE_SAMESITE` (default: `lax`)
- `COOKIE_DOMAIN` (optional)

#### Frontend Integration

```javascript
// Login with cookies
await fetch('/api/auth/cookie/login', {
  method: 'POST',
  body: `username=${email}&password=${password}`,
  credentials: 'include'
})

// Check auth state
const user = await fetch('/api/auth/me', {
  credentials: 'include'
}).then(r => r.json())

// All requests include cookies automatically
await fetch('/api/user/profile', {
  credentials: 'include'
})
```

#### Changes

- **New file**: `swx_core/auth/core/bearer_or_cookie.py` - Authentication scheme
- **Updated**: `swx_core/auth/user/dependencies.py` - Uses `BearerOrCookieAuth`
- **Updated**: `swx_core/auth/admin/dependencies.py` - Uses `BearerOrCookieAuth`
- **Updated**: `swx_core/routes/access/auth_route.py` - Added cookie endpoints

#### Documentation

- **Updated**: `docs/04-core-concepts/AUTHENTICATION.md` - Added comprehensive cookie authentication section with:
  - Cookie-based authentication overview
  - Frontend integration examples
  - Migration guide from header to cookie auth
  - Security considerations
  - Endpoint reference

### Migration from v2.7.33

No migration required. The new cookie authentication is additive and fully backward compatible with existing Authorization header authentication.

## [2.7.33] - 2026-07-01

### Added - OAuth 2.0 Security Overhaul (BFF Pattern + PKCE)

Major security upgrade for OAuth authentication following RFC 9700 best practices.

#### PKCE Support (RFC 7636)

- **All OAuth flows now use PKCE** - Mandatory per RFC 9700 for all clients
- **S256 challenge method** - SHA-256 based code challenge (never 'plain')
- **Session-stored verifier** - PKCE verifier stored in server-side session
- **Applies to**: Google, Facebook, and all custom OAuth providers

#### Backend-for-Frontend (BFF) Pattern

- **HTTP-only cookies for tokens** - XSS-resistant token storage
- **No tokens in response body** - Callbacks redirect to frontend with cookies
- **Automatic token rotation** - Fresh tokens set on each OAuth login
- **Cookie configuration settings**:
  - `COOKIE_ACCESS_TOKEN_NAME` (default: `swx_access_token`)
  - `COOKIE_REFRESH_TOKEN_NAME` (default: `swx_refresh_token`)
  - `COOKIE_SECURE` (auto-adjusts for local dev)
  - `COOKIE_SAMESITE` (default: `lax`)
  - `COOKIE_DOMAIN` (optional)

#### New Endpoints

- `POST /api/auth/cookie/logout` - Clears HTTP-only auth cookies

#### Events

- **`user.login.social` event** - Emitted on social login with payload:
  ```json
  {
    "email": "user@example.com",
    "user_id": "uuid",
    "provider": "google",
    "is_new_user": false
  }
  ```

### Changed

- **OAuth callbacks now redirect** - Instead of returning JSON tokens, callbacks redirect to `{FRONTEND_HOST}/auth/callback`
- **Error handling via redirect** - OAuth errors redirect with `?error=...` parameter
- **Refactored oauth_route.py** - Extracted common logic into helper functions:
  - `generate_pkce_verifier()` / `generate_pkce_challenge()`
  - `validate_oauth_state()` - CSRF protection
  - `store_pkce_session()` / `clear_oauth_session()`
  - `set_auth_cookies()` - HTTP-only cookie management
  - `complete_oauth_login()` - Shared login completion logic

### Security Improvements

| Before | After |
|--------|-------|
| Tokens in JSON response | Tokens in HTTP-only cookies |
| No PKCE | PKCE mandatory (S256) |
| XSS vulnerable (localStorage) | XSS resistant (httpOnly) |
| Manual token management | Automatic via cookies |

### Migration Guide

#### Frontend Changes Required

1. **Remove localStorage token management** - Cookies are automatic
2. **Add `credentials: 'include'`** to all API requests:
   ```javascript
   fetch('/api/user/profile', {
     credentials: 'include'  // Send cookies automatically
   })
   ```
3. **Update OAuth callback handling**:
   - Old: Parse tokens from URL or response body
   - New: Just redirect to dashboard, cookies already set
4. **Use `/api/auth/cookie/logout`** for logout (clears cookies)

#### Environment Variables

```bash
FRONTEND_HOST=http://localhost:3003  # Required for redirects
COOKIE_SECURE=true                    # False for local dev
COOKIE_SAMESITE=lax                   # or 'strict' for stricter CSRF
```

### Documentation

- Updated `docs/04-core-concepts/AUTHENTICATION.md` - BFF pattern docs
- Updated `docs/04-core-concepts/OAUTH_PROVIDERS.md` - PKCE and redirect flow

## [2.7.32] - 2026-07-01

### Fixed - CRITICAL: Timezone-aware datetime database incompatibility

Massive fix for datetime timezone issues causing asyncpg `DataError: can't subtract offset-naive and offset-aware datetimes`.

**Root Cause**: PostgreSQL `TIMESTAMP WITHOUT TIME ZONE` columns received timezone-aware `datetime.now(timezone.utc)` objects, causing asyncpg to fail when comparing/inserting datetimes.

**Solution**: All datetime objects passed to database columns now use `.replace(tzinfo=None)` to create naive UTC datetimes.

### Changed Files (60+ locations):

**Models (default_factory fixes):**
- `swx_core/utils/mixins.py` - TimestampMixin.created_at, updated_at, SoftDeleteMixin.soft_delete()
- `swx_core/models/billing.py` - All 11 timestamp fields (BillingAccount, Feature, Plan, PlanEntitlement, Subscription, UsageRecord)
- `swx_core/models/team_member.py` - created_at, updated_at
- `swx_core/models/team_role.py` - created_at, updated_at
- `swx_core/models/team_invitation.py` - created_at, updated_at, expires_at
- `swx_core/models/team.py` - created_at, updated_at
- `swx_core/models/admin_user.py` - created_at
- `swx_core/models/policy.py` - created_at, updated_at
- `swx_core/models/refresh_token.py` - created_at (already fixed in 2.7.31)
- `swx_core/utils/response.py` - 7 response model timestamp fields
- `swx_core/events/typed_event.py` - timestamp field
- `swx_core/events/dispatcher.py` - Event.timestamp field
- `swx_core/contracts/events.py` - EventInterface.timestamp field
- `swx_core/utils/health.py` - HealthCheckResult.timestamp field + business logic
- `swx_core/services/channels/models.py` - Alert.timestamp field
- `swx_core/cli/commands/resource_templates.py` - Generated model timestamps

**Services (business logic fixes):**
- `swx_core/services/job/job_runner.py` - completed_at, scheduled_at assignments (already had _utc_now_naive() fix)
- `swx_core/services/billing/subscription_service.py` - 5 timestamp assignments
- `swx_core/services/team_invitation_service.py` - accepted_at, rejected_at, created_at assignments
- `swx_core/services/rate_limit/rate_limiter.py` - reset_at assignments
- `swx_core/services/job/handlers.py` - subscription.ended_at assignments
- `swx_core/services/settings_service.py` - cache timestamp assignments
- `swx_core/services/job/job_dispatcher.py` - completed_at assignment
- `swx_core/services/settings_crud_service.py` - updated_at assignment
- `swx_core/services/policy/dependencies.py` - event timestamp assignment

**Repositories:**
- `swx_core/repositories/base.py` - 5 created_at/updated_at assignments
- `swx_core/repositories/tenant_aware.py` - updated_at assignment

**Security:**
- `swx_core/security/token_blacklist.py` - internal dict timestamp

**FastPII App (user application):**
- `apps/backend/api/swx_app/models/detection.py` - created_at, updated_at
- `apps/backend/api/swx_app/models/api_key.py` - created_at, updated_at

### Impact

This fix resolves ALL datetime insertion failures in applications using swx-core with PostgreSQL `TIMESTAMP WITHOUT TIME ZONE` columns (the default).

## [2.7.31] - 2026-07-01

### Fixed
- **RefreshToken created_at timezone mismatch** — `created_at` field was using timezone-aware
  datetime (`datetime.now(timezone.utc)`) but the database column is `TIMESTAMP WITHOUT TIME ZONE`,
  causing asyncpg errors during OAuth callback. Now correctly uses naive datetime with
  `.replace(tzinfo=None)`.

## [2.7.30] - 2026-07-01

### Fixed
- **OAuth routes missing error logging** — Exceptions in OAuth login/callback handlers were silently
  swallowed without logging, making OAuth failures impossible to debug. Now all OAuth routes log
  exceptions with full traceback before raising HTTPException.

### Changed
- All OAuth exception handlers now re-raise `HTTPException` directly (prevents double-wrapping)
- Added `logger` to oauth_route.py with error logging on all exception paths

## [2.7.29] - 2026-07-01

### Fixed
- **Job runner datetime mismatch** — `_utc_now_naive()` was returning timezone-aware datetime
  instead of naive, causing asyncpg errors when comparing with `TIMESTAMP WITHOUT TIME ZONE`
  columns. Now correctly returns naive datetime with `.replace(tzinfo=None)`.

## [2.7.28] - 2026-06-30

### Fixed - Bug #7/29: Users Forced to Belong to a Team

- **Auto-create personal team on registration** — New users now get a personal team with `tenant_id` set automatically
- **`AUTO_CREATE_PERSONAL_TEAM` setting** — Default `True`, creates personal team and assigns `owner` role
- **No more 500 errors** — Users without `tenant_id` no longer crash tenant-aware endpoints

### Added

- `create_personal_team()` hook — Creates team `{user}'s Team` and sets `user.tenant_id`
- `AUTO_CREATE_PERSONAL_TEAM` setting — Controls automatic team creation (default: True)
- Migration `v2_7_27_personal_team_backfill.py` — Backfills existing users without tenant_id

### Fixed - Bug #14: Alembic Migration Rollback Handling

- All migrations now have proper `downgrade()` functions
- Migration `v2_7_27_personal_team_backfill.py` includes rollback support

### Added - FR1: Extensibility for Custom Social Auth Providers

- **OAuth Provider Registry** — `swx_core.core.oauth_providers` module
- **Configuration-based providers** — Add GitHub, LinkedIn, Apple, etc. via `.env`
- **Dynamic provider loading** — No code changes needed to add new providers

#### Usage:

```bash
# .env
OAUTH_PROVIDERS=github,linkedin

GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx
GITHUB_REDIRECT_URI=http://localhost:8001/api/oauth/github/callback
GITHUB_AUTH_URL=https://github.com/login/oauth/authorize
GITHUB_TOKEN_URL=https://github.com/login/oauth/access_token
GITHUB_USER_INFO_URL=https://api.github.com/user
GITHUB_SCOPE=user:email

LINKEDIN_CLIENT_ID=xxx
LINKEDIN_CLIENT_SECRET=xxx
LINKEDIN_REDIRECT_URI=http://localhost:8001/api/oauth/linkedin/callback
LINKEDIN_AUTH_URL=https://www.linkedin.com/oauth/v2/authorization
LINKEDIN_TOKEN_URL=https://www.linkedin.com/oauth/v2/accessToken
LINKEDIN_USER_INFO_URL=https://api.linkedin.com/v2/me
LINKEDIN_SCOPE=r_emailaddress r_liteprofile
```

### Documentation

- New `docs/04-core-concepts/OAUTH_PROVIDERS.md` — OAuth extensibility guide
- Updated `docs/04-core-concepts/REGISTRATION_HOOKS.md` — Added personal team hook docs

## [2.7.27] - 2026-06-30

### Added - Bug #25: Separate Team Roles from System RBAC

- **TeamRole model** — New model for team-scoped roles (owner, editor, viewer) separate from system RBAC
- **TeamPermissionChecker service** — Check team-scoped permissions based on TeamRole.permissions dict
- **DEFAULT_TEAM_ROLES** — Seeded roles: owner (full control), editor (can edit), viewer (read-only)
- **Migration v2_7_26** — Creates swx_team_role table and migrates TeamMember.role_id to team_role_id

### Changed - Bug #25

- **TeamMember.team_role_id** — Now uses team_role_id (FK to swx_team_role) instead of role_id (FK to swx_role)
- **TeamMemberCreate** — Uses team_role_id instead of role_id
- **TeamMemberUpdate** — New schema for updating team role
- **team_service.py** — Updated to use TeamRole instead of system Role

### Added - Bug #26: Team Invitation System

- **TeamInvitation model** — Invitation with status (pending, accepted, rejected, expired, revoked)
- **TeamInvitationService** — Full CRUD: create, accept, reject, revoke with permission checks
- **TeamInvitation routes** — API endpoints: POST /, POST /{token}/accept, POST /{token}/reject, DELETE /{id}
- **7-day expiration** — Invitations expire after 7 days by default
- **Secure tokens** — 64-character random tokens for invitation acceptance

### New Models

- `swx_team_role` — Team-scoped roles with permissions dict
- `swx_team_invitation` — Team invitations with audit trail

### New Services

- `TeamPermissionChecker` — Check team-scoped permissions
- `TeamInvitationService` — Manage invitation lifecycle

### New Routes

- `/team-invitations/` — Create invitation
- `/team-invitations/{token}/accept` — Accept invitation
- `/team-invitations/{token}/reject` — Reject invitation
- `/team-invitations/{id}` (DELETE) — Revoke invitation
- `/team-invitations/team/{team_id}` — List team invitations
- `/team-invitations/me` — List my invitations

## [2.7.25] - 2026-06-30

### Fixed
- **Bug 16: Invalid UUID headers silently ignored** — `X-Tenant-ID` and `X-Team-ID` headers with
  invalid UUIDs were silently dropped. Now logs a warning for debugging.
- **Bug 17: Hardcoded log directory** — Log file path was hardcoded to `"logs/swx_core.log"`.
  Added `LOG_DIR` setting (default: `"logs"`) for configurable log directory.
- **Bug 21: Expired subscriptions granted access** — `get_entitlement()` checked subscription status
  but not `current_period_end`. Now requires `current_period_end >= now()` to grant entitlements.
- **Bug 23: Duplicate team membership allowed** — `TeamMember` lacked composite unique constraint,
  allowing same user to be added to same team multiple times. Added `UniqueConstraint("team_id", "user_id")`.

### Added
- `LOG_DIR` setting for configurable log directory path.
- Migration `v2_7_24_add_team_member_unique.py` for TeamMember unique constraint.

### Changed
- `TeamMember.__table_args__` now includes `UniqueConstraint("team_id", "user_id")`.

## [2.7.23] - 2026-06-29

### Added
- **Default role assignment on registration** — New `AUTO_ASSIGN_DEFAULT_ROLE` (default: `True`) and
  `DEFAULT_USER_ROLE` (default: `"user"`) settings. When enabled, newly registered users automatically
  receive the specified role via a post-registration hook. Requires `seed_system.py` to have created
  the role.
- **Billing account creation on registration** — New `AUTO_CREATE_BILLING_ACCOUNT` (default: `True`)
  setting. When enabled (and `BILLING_ENABLED=True`), a USER billing account and free-tier subscription
  are created automatically for newly registered users.
- **Multi-hook registration system** — `RegistrationHookRegistry` now supports multiple post-register
  hooks via `add_post_register()`. `set_post_register()` still works but replaces all hooks. Both
  default hooks (role assignment, billing) are registered via `add_post_register()`.
- **`swx_core/core/default_hooks.py`** — New module with `assign_default_role()` and
  `create_billing_account()` post-registration hooks.
- **`_register_default_hooks()` in bootstrap** — Automatically registers default hooks based on settings
  during `bootstrap_app()` (Phase 2.5).
- **Alembic migration template** — `swx_core/database/migrations/v2_7_22_schema_changes.py` covering
  all v2.7.22 schema changes (new columns on `swx_team`, `billing_interval` on `swx_billing_plan`,
  FK `ondelete` clauses on 17 foreign keys).

### Changed
- `RegistrationHookRegistry._post_hook` changed from single hook to `_post_hooks: List[PostRegisterHook]`.
- `registration_hooks.post_register` property now returns a combined coroutine that runs all hooks
  sequentially, catching and logging exceptions per hook.

## [2.7.22] - 2026-06-29

### Fixed - CRITICAL
- **Bug 8: Un awaited `get_password_hash()` in `user_repository.py`** — `hashed_password = get_password_hash(password)`
  was called without `await`, silently returning a coroutine object instead of a hash.
- **Bug 1: No session injection in BaseRepository** — Added optional `session` parameter to
  `BaseRepository.__init__()` and `_session_context()` async context manager. Callers can now
  inject a session for Unit of Work / multi-operation transactions. Without a session, behavior
  is unchanged (auto-created per-operation session).

### Fixed - HIGH
- **Bug 12: Tenant filter leak** — `_apply_tenant_filter()` in `tenant_aware.py` returned the
  unfiltered query when no tenant context was available, exposing all records. Now returns
  `query.where(sa_false())` (no rows) instead.
- **Bug 10: Insecure CORS defaults** — `setup_cors_middleware()` defaulted to `allow_origins=["*"]`
  with `allow_credentials=True`, which browsers reject and is insecure. Changed default to
  `allow_origins=[]` with `allow_credentials=False`; credentials enabled only when origins
  are explicitly configured.
- **Bug 9: Rate-limit skip paths too broad** — Removed `/api/admin/`, `/api/auth`,
  `/api/user/profile`, `/api/qa_article`, `/api/oauth` from skip_paths. Only health/docs
  endpoints remain unrate-limited.
- **Bug 20: Subscription race condition** — Added `.with_for_update()` to the active-subscription
  SELECT in `subscription_service.py`, preventing concurrent subscription creation under load.
- **Bug 28: ValueError in subscription service** — Changed `raise ValueError(...)` to
  `raise HTTPException(status_code=404, ...)` in `SubscriptionService.create_subscription()`
  so invalid plan keys return a proper 404 instead of an unhandled 500.

### Fixed - MEDIUM
- **Bug 13: Inactive user password recovery** — Added `is_active` check in
  `recover_password_service()` — inactive users can no longer request password resets.
- **Bug 15: AlertEngine fire-and-forget with no error handling** — Added `_pending_tasks` set
  and `_handle_task_error` callback to `AlertEngine.emit()`. Unhandled task exceptions are now
  logged instead of silently swallowed.
- **Bug 5: Deprecated `datetime.utcnow()` across 51 call sites in 37 files** — Replaced all
  `datetime.utcnow()` calls with `datetime.now(timezone.utc)` and added `timezone` import
  where needed.
- **Bug 22: Foreign keys missing `ondelete`** — Added explicit `ondelete` clauses
  (`CASCADE`, `RESTRICT`, `SET NULL`) to all FK columns in `team_member`, `user`, `user_role`,
  `role_permission`, `billing`, `system_config`, and `team` models using
  `sa_column=Column(PG_UUID(...), ForeignKey(..., ondelete=...))`.

### Fixed - LOW
- **Bug 27: Hardcoded 30-day billing interval** — Added `BillingInterval` enum and
  `BILLING_INTERVAL_DAYS` dict to `billing.py`. Plan model now has a `billing_interval` field.
  `SubscriptionService.create_subscription()` uses `BILLING_INTERVAL_DAYS` instead of a
  hardcoded 30.
- **Bug 24: Team model missing owner and timestamps** — Added `owner_id` (FK to `swx_users.id`
  with `ondelete="SET NULL"`), `created_at`, and `updated_at` to `Team` model.
- **Bug 18: No billing account on team creation** — `create_team_service()` now creates a
  `TEAM` billing account via `SubscriptionService.get_or_create_account()`.
- **Bug 19: Orphan billing data on team deletion** — `delete_team_service()` now deletes
  related `UsageRecord`, `Subscription`, and `BillingAccount` rows before deleting the team.

### Changed
- `BaseRepository.__init__()` now accepts an optional `session: AsyncSession` parameter.
- `_session_context()` async context manager yields injected session or auto-creates one.
- All FK fields in models now use `sa_column=Column(PG_UUID(as_uuid=True), ForeignKey(..., ondelete=...))`
  instead of `Field(foreign_key=...)`.
- `tenant_aware.py`: `sa_false` import moved from inline to module-level.

## [2.7.21] - 2026-06-16

### Fixed - CRITICAL
- **v2.7.20 regression: routes not mounted (404)** - The v2.7.20 `hasattr(r, "path")`
  guard prevented the crash but silently skipped all `_IncludedRouter` objects,
  leaving `core_paths` empty. Since `set().issubset(...)` is always `True`,
  `app.include_router(core_router)` was never called and all endpoints returned 404.
  Replaced both inline comprehensions (lines 119 and 123) with a new
  `_extract_route_paths()` helper that recursively drills into
  `_IncludedRouter.original_router` to collect real path strings.

### Added
- **`_extract_route_paths()` helper** in `bootstrap.py` - Recursively extracts route
  paths from a router/app, handling both plain routes (`.path`) and FastAPI 0.115.0+
  `_IncludedRouter` wrappers (`.original_router`).

### Tests
- 8 new tests in `tests/bootstrap/test_bootstrap_routes.py` covering:
  - Plain route extraction
  - Nested `_IncludedRouter` recursive extraction
  - Deeply nested routers (3+ levels)
  - Empty router edge case
  - Full FastAPI app with included sub-routers
  - Core routes actually mounted on fresh app (v2.7.20 regression)
  - No double-registration on repeated `bootstrap_app` calls
  - `core_router` yields real paths (not empty)

## [2.7.20] - 2026-06-16

### Fixed - CRITICAL
- **`bootstrap_app()` crash on FastAPI 0.115.0+** - Fixed `AttributeError: '_IncludedRouter'
  object has no attribute 'path'` on line 123 of `bootstrap.py`. FastAPI 0.115.0+ wraps
  included sub-routers in `_IncludedRouter` objects that lack a `.path` attribute. Added
  the same `hasattr(r, "path")` guard that line 119 already had, safely skipping wrapper
  objects. Without this fix, the server crashes on every startup when using
  `include_router()` with FastAPI >= 0.115.0.

## [2.7.19] - 2026-05-29

### Fixed
- **Post-registration hook exception handling** - Hook failures no longer mask successful
  user creation with a 400 error. Post-hook exceptions are now caught and logged as
  warnings, and the `user.created` event is always emitted regardless of hook outcome.
  Previously, a failing post-hook would prevent the event from firing and return a 400
  error even though the user was successfully created.

## [2.7.18] - 2026-05-29

### Fixed - CRITICAL
- **Core routes not mounted** - Fixed `dynamic_import` returning package `__init__.py` modules
  alongside individual route files, causing double registration and 404 errors.
  Package modules in route directories are now skipped; only leaf route files are registered.
- **Auth route prefix doubling** - Fixed `/api/auth/auth/` double prefix caused by `__init__.py`
  aggregation routers being processed alongside individual route files.
- **Misleading "No core routes found" warning** - Fixed `for...else` bug in `router.py` that
  printed "No core routes found" even when routes were successfully loaded.

### Added
- **Registration Hook Registry** - `swx_core.core.hooks.registration_hooks` singleton for
  configuring pre/post registration hooks at app startup. The auth route endpoint now
  automatically uses registered hooks, solving the "hooks not exposed via HTTP API" issue.
- **Explicit tenant_id in TenantAwareRepository** - New `explicit_tenant_id` and `explicit_team_id`
  constructor parameters allow bypassing context vars for apps that pass tenant explicitly:
  ```python
  repo = TenantAwareRepository(Product, explicit_tenant_id="tenant-123")
  ```

### Changed
- **TenantAwareRepository** - `_apply_tenant_filter` now respects explicit tenant/team IDs over
  context vars. Super-admin bypass only applies when no explicit ID is set.
- **Auth controller** - `register_controller` now passes `registration_hooks.pre_register` and
  `registration_hooks.post_register` to `register_user_service`.

## [2.7.17] - 2026-05-29

### Added - Registration Extension Points
- **Lifecycle Hooks for Registration** - `register_user_service()` now accepts hook parameters:
  - `pre_register_hook` - Async function called BEFORE user creation for validation/tenant assignment
  - `post_register_hook` - Async function called AFTER user creation for organization setup/side effects
  - Hook execution order: pre → create → post → emit event → return user
  - Both hooks receive `event_context` for passing custom data
- **CORE_ROUTE_PREFIX Setting** - Configurable prefix for core framework routes:
  - Default: `""` (empty string) - core routes at `/api/auth`
  - Set to `"/v1"` for `/api/v1/auth` to match versioned app routes
  - Enables apps to mount core routes consistently with their API versioning

### New Documentation
- **Registration Hooks** - `docs/04-core-concepts/REGISTRATION_HOOKS.md`
  - Complete guide to registration extension points
  - Examples: multi-tenant registration, invitation-based signup, enterprise SSO
  - Comparison of hooks vs events vs service override approaches
- **Route Configuration** - `docs/02-getting-started/ROUTE_CONFIGURATION.md`
  - Route prefix configuration explained
  - Migration guide for swx_app compatibility
  - Troubleshooting common routing issues

### Changed
- **Router** - Core routes respect `CORE_ROUTE_PREFIX` setting for URL mounting
- **Settings** - Added `CORE_ROUTE_PREFIX` field with default empty string
- **GETTING_STARTED.md** - Added `CORE_ROUTE_PREFIX` to environment variables documentation

## [2.7.16] - 2026-05-29

### Added - Multi-Tenant Support
- **TenantAwareRepository** - Base repository with automatic tenant filtering via context variables
  - Automatically filters queries by `tenant_id` or `team_id` from request context
  - Supports super-admin bypass for accessing all tenants
  - Auto-injects tenant context on create operations
- **TenantContextMiddleware** - Middleware for extracting and setting tenant context
  - Extracts tenant from `X-Tenant-ID` header or authenticated user
  - Implements context cleanup in finally block to prevent leakage
  - Exempts auth and health endpoints
- **TenantAwareController** - Base controller with tenant context injection
  - Extends BaseController with automatic tenant data injection
  - Works with TenantAwareRepository for full tenant isolation
- **EntitlementService** - Service for quota enforcement and feature entitlements
  - `require_quota()` - Check if owner has remaining quota
  - `require_feature()` - Check access to boolean features
  - `QuotaExceededError` exception with feature/limit/current details
  - Dependency helpers: `require_quota_dependency()`, `require_feature_dependency()`
- **PostgreSQL RLS Support** - Row-Level Security integration
  - `swx_core/database/rls.py` - SQLAlchemy event listeners for RLS
  - `swx_core/database/migrations/rls_template.sql` - Migration template for enabling RLS

### Changed
- **User Model** - Added `tenant_id` field to `UserBase` for multi-tenant support
- **Auth Dependencies** - `get_current_user()` now sets tenant context for downstream use
- **Repositories** - Added `TenantAwareRepository` export to `__init__.py`
- **Controllers** - Added `TenantAwareController` export to `__init__.py`
- **Middleware** - Added `TenantContextMiddleware` export to `__init__.py`

### New Modules
- `swx_core/core/tenant.py` - ContextVar-based tenant context management
- `swx_core/core/__init__.py` - Core module exports
- `swx_core/repositories/tenant_aware.py` - TenantAwareRepository implementation
- `swx_core/controllers/tenant_aware.py` - TenantAwareController implementation
- `swx_core/middleware/tenant_middleware.py` - TenantContextMiddleware implementation
- `swx_core/services/billing/quota_service.py` - EntitlementService implementation

## [2.7.15] - 2026-05-29

### Fixed - CRITICAL
- **Routes Not Mounted** - Fixed routes not accessible despite being logged as registered
  - Root cause: `__init__.py` files in routes subdirectories only imported routers but didn't create module-level `router` variable
  - Fix: Added `router = APIRouter()` + `router.include_router()` aggregations in each `__init__.py`
  - Affected files: `swx_core/routes/access/__init__.py`, `swx_core/routes/admin/__init__.py`, `swx_core/routes/user/__init__.py`, `swx_core/routes/utils/__init__.py`
  - Impact: All routes from swx_core/routes/* now properly accessible

### Fixed
- **Router Prefix Handling** - Fixed v2.7.14 bug where router prefixes were incorrectly stripped
- **User Model Timestamps** - Added `created_at` and `updated_at` fields to User model
- **Timezone-Aware DateTime** - Fixed `datetime.now(timezone.utc)` causing PostgreSQL errors for TIMESTAMP WITHOUT TIME ZONE columns
  - Changed to `datetime.utcnow()` for naive datetime compatibility

### Documentation
- **Router Module Pattern** - Documented requirement for module-level `router` variable in route `__init__.py` files

## [2.7.8] - 2026-05-01

### Fixed - CRITICAL
- **Job Runner SQL Bug** - Fixed unqualified column reference `job.status` → `swx_job.status` in PostgreSQL query
  - Error: `missing FROM-clause entry for table "job"` in PostgreSQL
  - File: `swx_core/services/job/job_runner.py:202`
  - Fix: Changed `text("job.status = ANY(...)")` → `text("swx_job.status = ANY(...)")`
  - Impact: Background job processing was completely broken, workers spammed errors

### Fixed
- **get_current_user Export** - Added `get_current_user` and `UserDep` to `swx_core.auth.__init__.py`
  - Users can now: `from swx_core.auth import get_current_user`
  - Previously required workaround: `from swx_core.auth.user import get_current_user`

### Documentation
- **AdminUser Import Path** - Confirmed correct path: `from swx_core.models import AdminUser`
  - No `swx_core.models.admin` module exists - AdminUser is in `admin_user.py`

## [2.7.7] - 2026-05-01

### Fixed - CRITICAL
- **SyntaxError in ai_exports/graph.py** - Removed corrupt prefixes (#MY|, #NS|, etc.) causing unterminated string literal
- **SyntaxError in ai_exports/contracts.py** - Same corruption fix
- **swx CLI now works** - Fixed blocking import error

### Changed
- Removed autogenerate from `swx setup` to prevent issues with existing projects
- `swx setup` now provides manual instructions instead of auto-generating migrations
- Safer for projects with custom tables that reference core tables

### Bug Fixes
- ai_exports files no longer have corrupt line prefixes
- Existing projects with migrations can safely run `swx setup`

## [2.7.6] - 2026-05-01

### Fixed - Database Migration Auto-Generation
- **swx_job Table Not Created** - Setup command now auto-generates initial migration if none exist
  - `swx setup` detects empty migrations/versions/ directory
  - Automatically runs `alembic revision --autogenerate -m "initial"`
  - Creates all framework tables including `swx_job`, `swx_users`, `swx_role`, etc.
  
### Changed
- `_setup_database()` in `framework.py` now generates initial migration on fresh projects
- Users no longer need to manually run `swx db revision "initial"` first

## [2.7.5] - 2026-05-01

### Fixed - Import/Module Issues
- **Broken Import in CLI Framework** - Fixed `swx_core/cli/commands/framework.py:239` importing from non-existent `swx_core.database.core`. Changed to `swx_core.database.db`.
- **Database Module Exports** - Added exports to `swx_core/database/__init__.py` for cleaner imports:
  - `AsyncSessionLocal`, `SessionLocal` - session factories
  - `async_engine`, `engine` - database engines
  - `get_async_db`, `get_db`, `get_session` - dependency injectors
  - `SessionDep`, `SyncSessionDep` - type annotations

### Documentation
- Confirmed cache functions are correctly located at `swx_core.utils.cache` (not `swx_core.cache`)
- Confirmed BaseRepository is at `swx_core.repositories.base` (not `swx_core.repository`)

## [2.7.4] - 2026-04-29

### Fixed - CRITICAL
- **All Services: Local EventBus Instance Bug** - Fixed ALL services creating local `EventBus()` instances instead of using the global `event_bus` singleton. This affected:
  - `role_service.py` (5 occurrences)
  - `user_service.py` (3 occurrences)
  - `permission_service.py` (3 occurrences)
  - `team_service.py` (5 occurrences)
  - `user_role_service.py` (2 occurrences)
  - `policy_service.py` (3 occurrences)
  - `base.py` (BaseService class)
  
  **Impact**: ALL events emitted by these services were going to empty buses with NO registered listeners. Fix ensures all events go to the global singleton where listeners are registered.

### Changed
- All services now import and use `event_bus` singleton from `swx_core.events.dispatcher`
- BaseService now stores reference to global `event_bus` instead of creating new instance

## [2.7.3] - 2026-04-29

### Fixed - CRITICAL
- **user.created Event Not Emitted** - Fixed `register_user_service()` creating a local `EventBus()` instance instead of using the global `event_bus` singleton. Events are now emitted to the correct bus where listeners are registered.
- **Event Context Empty Dict Handling** - Changed `if event_context:` to `if event_context is not None:` to correctly handle empty dict.

### Added
- **Discovery Diagnostic Logging** - Added DEBUG-level logs explaining why Phase 3 listener registration might be skipped
- **diagnose_discovery() Function** - New helper to debug discovery configuration:
  ```python
  from swx_core.bootstrap import diagnose_discovery
  diagnose_discovery()  # Returns app_exists, has_listeners, phase_3_will_run
  ```

### Changed
- **Bootstrap Phase 3** - Now logs DEBUG message when skipping listener registration, showing which directory is missing

## [2.7.2] - 2026-04-29

### Added
- **Event Dispatch Logging** - INFO-level logging for event dispatch with listener count, execution times, and completion status
- **Listener Registration Logging** - INFO-level logging when listeners are registered with pattern, priority, and queueable details
- **Event Debug Utilities** - New `swx_core.events.debug` module with inspection tools:
  - `list_all_listeners()` - List all registered listeners grouped by event
  - `test_pattern()` - Test wildcard pattern matching
  - `trace_event()` - Trace which listeners receive an event
  - `print_event_bus_status()` - Print comprehensive event bus status
  - `get_listener_count()` - Count registered listeners
  - `verify_listener_registered()` - Verify a listener is registered
- **Example Listeners** - Template project includes example listener implementations in `swx_app/listeners/example_listeners.py`

### Changed
- **Listener registration logging** - Changed from DEBUG to INFO level for visibility
- **Event dispatch logging** - Added detailed timing and listener invocation logging

### Fixed
- **Listener visibility** - Listeners now log at INFO level when registered during bootstrap

### Documentation
- **Event System Guide** - Added troubleshooting section to `docs/04-core-concepts/EVENT_SYSTEM.md`
- **Debug utilities documentation** - Documented all debug utilities with examples
- **Pattern matching examples** - Added wildcard pattern examples and tests

## [2.7.1] - 2026-04-29

### Fixed
- **Critical: Event Hashability** - Fixed `unhashable type: 'Event'` bug by adding `__hash__` method to Event class
- **Critical: TypedEvent Hashability** - Added `__hash__` method to TypedEvent class for use in sets/dicts
- **Wildcard Pattern Matching** - Fixed bug where `user.*` pattern matched all events instead of only `user.created`, `user.deleted`, etc.
- **Event Context Handling** - Fixed empty dict `event_context={}` being treated as `None` (now correctly adds `"context": {}` to payload)

### Added
- **TypedEvent `__hash__` method** - TypedEvent objects can now be used in sets and as dict keys
- **ListenerRegistration.pattern field** - Stores pattern for wildcard listeners (supports `*`, `user.*`, `*.created`)
- **EventBus._matches_pattern()** - Pattern matching logic for wildcard event listeners
- **Comprehensive edge case tests** - 25 new tests for event emission edge cases

### Changed
- **Event context parameter** - Changed from `if event_context else` to `if event_context is not None else` across all services to correctly handle empty dict

## [2.7.0] - 2026-04-28

### Added
- **Comprehensive Event Emission**: All SwX services now emit domain events for CRUD operations
- **Event Context Parameter**: All service methods accept `event_context` parameter for additional metadata
- **Typed Event Base Classes**: New `TypedEvent` base class for type-safe event handling

### Services with Event Emission

#### Authentication & User Management
- **auth_service.py**: `register_user_service()` now emits `user.created` event
- **user_service.py**: 
  - `update_user_profile_service()` emits `user.updated` event
  - `update_password_service()` emits `user.password_changed` event
  - `delete_user_service()` emits `user.deleted` event

#### Role & Permission Management
- **role_service.py**:
  - `create_role_service()` emits `role.created` event
  - `update_role_service()` emits `role.updated` event
  - `delete_role_service()` emits `role.deleted` event
  - `assign_permission_to_role_service()` emits `role.permission_assigned` event
  - `remove_permission_from_role_service()` emits `role.permission_removed` event

- **permission_service.py**:
  - `create_permission_service()` emits `permission.created` event
  - `update_permission_service()` emits `permission.updated` event
  - `delete_permission_service()` emits `permission.deleted` event

#### Team Management
- **team_service.py**:
  - `create_team_service()` emits `team.created` event
  - `update_team_service()` emits `team.updated` event
  - `delete_team_service()` emits `team.deleted` event
  - `add_team_member_service()` emits `team.member_added` event
  - `remove_team_member_service()` emits `team.member_removed` event

#### User-Role Management
- **user_role_service.py**:
  - `assign_role_to_user_service()` emits `user_role.assigned` event
  - `remove_role_from_user_service()` emits `user_role.removed` event

#### Policy Management
- **policy_service.py**:
  - `create_policy_service()` emits `policy.created` event
  - `update_policy_service()` emits `policy.updated` event
  - `delete_policy_service()` emits `policy.deleted` event

### Event Payload Structure

All events follow a consistent payload structure:

```python
# Create/Update/Delete events
{
    "id": "uuid-string",
    "data": {"field": "value"},           # Resource data
    "context": {"key": "value"}            # Optional context
}

# Update events (additional fields)
{
    "id": "uuid-string",
    "old_values": {"field": "old_value"},
    "new_values": {"field": "new_value"},
    "context": {"key": "value"}            # Optional context
}
```

### Example Usage

```python
# User registration with context
user = await register_controller(
    session=session,
    user_in=user_create,
    request=request,
    event_context={
        "user_type": "patient",
        "hospital_id": hospital_id,
        "registration_source": "mobile_app",
    },
)

# Role creation with context
role = await create_role_service(
    session=session,
    role_in=role_create,
    event_context={"created_by": admin_id},
)
```

### Tests
- **New Tests**: `tests/services/test_service_event_emissions.py` with comprehensive event tests
- **New Tests**: `tests/services/test_user_created_event.py` for user registration events
- **Coverage**: 23 tests covering all service event emissions

### Breaking Changes
- None - all changes are backward compatible

### Migration Guide
No migration required. Event emission is automatic. To receive additional context:

1. Pass `event_context` parameter to any service method:
   ```python
   await create_role_service(session, role_in, event_context={"created_by": user_id})
   ```

2. Listen for events using EventBus:
   ```python
   from swx_core.events import EventBus
   
   @EventBus.on("role.created")
   async def on_role_created(event):
       role_id = event.payload["id"]
       context = event.payload.get("context", {})
       created_by = context.get("created_by")
   ```

## [2.6.0] - 2026-04-28

### Added
- **Event Context Enhancement**: BaseService CRUD methods now accept `event_context` parameter for additional context in event payloads
- **before_emit Hook**: Async hook called before event emission to enhance payload with computed/async context
- **after_emit Hook**: Async hook called after event emission for side effects
- **Structured Event Payloads**: Events now support `{"id": ..., "data": ..., "context": ...}` structure

### Changed
- **BaseService.create()**: Added `event_context: Dict[str, Any] | None` parameter
- **BaseService.update()**: Added `event_context` parameter
- **BaseService.delete()**: Added `event_context` parameter
- **BaseService.soft_delete()**: Added `event_context` parameter
- **BaseService.restore()**: Added `event_context` parameter
- **BaseService.bulk_create()**: Added `event_context` parameter

### Example Usage
```python
# Before: Workaround with duplicate events
user = await user_service.create(data)
await event_bus.dispatch("user.created", payload={...context...})

# After: Single event with context
user = await user_service.create(
    data={"email": "user@example.com", "password": "secret"},
    event_context={
        "user_type": "patient",
        "hospital_id": hospital_id,
        "registration_source": "mobile_app",
    },
)

# With before_emit hook for computed context
class UserService(BaseService[User]):
    async def before_emit(self, event_name, payload, instance):
        if event_name == "user.created" and instance:
            payload["context"] = {
                **payload.get("context", {}),
                "user_type": await self._determine_user_type(instance),
            }
        return payload
```

### Industrial Standard Compliance
- Follows Django Signals pattern (`sender + **kwargs`)
- Follows Flask/Blinker pattern (explicit context injection)
- Follows SQLAlchemy event hooks (before/after pattern)
- Follows production SaaS patterns (aden-hive/hive, ricequant/rqalpha)

### Tests
- **New Tests**: `tests/services/test_base_service_event_context.py` with 10 comprehensive tests
- **Coverage**: event_context propagation, before_emit/after_emit hooks, backward compatibility

## [2.5.0] - 2025-04-28

### Added
- **Event Listener Auto-Discovery**: Listeners in `swx_core/events/listeners/` and `swx_app/listeners/` are automatically discovered and registered during bootstrap
- **Listener Auto-Registration**: No manual EventServiceProvider registration needed - listeners self-register
- **Wildcard Pattern Support**: Listeners can use wildcard patterns like `user.*`, `emergency.*`, or `*` for all events
- **Priority-Based Execution**: Listeners execute in priority order (highest first)
- **Queueable Listeners**: Support for background queue processing with `queueable=True`
- **New Functions in `swx_core.events`**:
  - `discover_listeners(module)`: Find all Listener subclasses in a module
  - `register_listener(listener_class)`: Register a listener with EventBus
  - `load_listeners_from_path(base_path, package_name)`: Load listeners from directory
  - `load_all_listeners()`: Load and register all core and app listeners
- **New Module**: `swx_core/events/listener_loader.py` with auto-discovery implementation
- **New Directory**: `swx_core/events/listeners/` for core framework listeners
- **New Tests**: `tests/events/test_listener_loader.py` with comprehensive coverage
- **New Documentation**: `docs/04-core-concepts/EVENT_SYSTEM.md` with examples and best practices

### Fixed
- **Bootstrap Integration**: `register_event_listeners()` now properly called during bootstrap (Phase 3)
- **Import Exports**: All listener_loader functions now properly exported in `swx_core/events/__init__.py`
- **Path Handling**: Fixed `path_exists` issue in listener_loader using `Path.exists()` directly

### Changed
- **EventListener Pattern**: Now follows Laravel's EventServiceProvider pattern for auto-discovery
- **Bootstrap Phases**: Added Phase 3 for listener registration after provider boot

## [2.4.0] - 2025-04-27

### Added
- **Table Prefix**: All framework tables now use `swx_` prefix to differentiate core tables from user tables
- **Migration Support**: Migration script to rename existing tables with `swx_` prefix
- **Foreign Key Updates**: All 16 foreign key references updated to use prefixed table names

### Changed
- **Table Names**: 21 core tables renamed with `swx_` prefix
- **Raw SQL**: Updated 5 raw SQL queries to use prefixed table names

## [2.3.16] - 2025-04-27

### Fixed
- **Circular Import**: Fixed circular import in `loader.py` when SwX loader tries to reload modules
- **Module Loading**: Added `_loading_modules` tracking to prevent recursive loading

## [2.0.0] - 2024-03-XX

### Added
- **Base Classes Pattern**: BaseController, BaseService, BaseRepository for rapid development
- **Domain Separation**: Admin, User, and System domains completely isolated
- **OAuth2 + JWT**: Secure token-based authentication with refresh tokens
- **Permission-First RBAC**: Fine-grained access control with team scoping
- **Policy Engine (ABAC)**: Attribute-based access control with conditions
- **Billing & Entitlements**: Feature registry, plan management, Stripe integration
- **Rate Limiting**: Plan-based rate limits with burst protection
- **Audit Logging**: Immutable security and business event logs
- **Background Jobs**: Asynchronous job processing with retries
- **CLI Tools**: `swx` command for scaffolding with `--base` flag
