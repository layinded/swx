# Changelog

**Version:** 2.7.34  
**Last Updated:** 2026-07-01

---

## Table of Contents

1. [Overview](#overview)
2. [Version History](#version-history)
3. [Breaking Changes](#breaking-changes)
4. [Deprecations](#deprecations)

---

## Overview

This document tracks **version history and changes** for SwX-API. All notable changes are documented here.

### Version Format

**Semantic Versioning:** `MAJOR.MINOR.PATCH`

- **MAJOR** - Breaking changes
- **MINOR** - New features, backward compatible
- **PATCH** - Bug fixes, backward compatible

---

## Version History

### Version 2.7.34 (2026-07-01)

**HTTP-only Cookie Authentication - BFF Pattern Extension**

Extended cookie-based authentication for all auth flows.

**Cookie Authentication for All Flows**
- Dual authentication support - Authorization header AND HTTP-only cookies
- Priority-based extraction - Header first, cookie fallback
- New authentication scheme - `BearerOrCookieAuth` class
- Backward compatible - Existing Authorization header auth unchanged

**New Endpoints**
- `GET /api/auth/me` - Check authentication state
- `POST /api/auth/cookie/login` - Email/password login with cookies
- `POST /api/auth/cookie/refresh` - Token refresh via cookies
- `POST /api/auth/cookie/logout` - Clear auth cookies (from v2.7.33)

**Security Benefits**
- XSS-resistant HTTP-only cookies
- SameSite CSRF protection
- Automatic cookie management
- No client-side token handling

**Frontend Integration**
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
```

**Changes**
- New: `swx_core/auth/core/bearer_or_cookie.py`
- Updated: `swx_core/auth/user/dependencies.py`
- Updated: `swx_core/auth/admin/dependencies.py`
- Updated: `swx_core/routes/access/auth_route.py`

**Documentation**
- Comprehensive cookie authentication guide in AUTHENTICATION.md
- Frontend integration examples
- Migration guide from header to cookie auth

### Version 2.7.33 (2026-07-01)

**OAuth 2.0 Security Overhaul - BFF Pattern + PKCE**

Major security upgrade following RFC 9700 best practices.

**PKCE Support (RFC 7636)**
- All OAuth flows now use PKCE with S256 challenge method
- Session-stored verifier for secure code exchange
- Mandatory for all providers (Google, Facebook, custom)

**Backend-for-Frontend (BFF) Pattern**
- HTTP-only cookies for XSS-resistant token storage
- Callbacks redirect to frontend instead of returning JSON
- Tokens never exposed to client-side JavaScript

**New Cookie Settings**
- `COOKIE_ACCESS_TOKEN_NAME` (default: `swx_access_token`)
- `COOKIE_REFRESH_TOKEN_NAME` (default: `swx_refresh_token`)
- `COOKIE_SECURE` (auto-adjusts for local dev)
- `COOKIE_SAMESITE` (default: `lax`)
- `COOKIE_DOMAIN` (optional)

**New Endpoint**
- `POST /api/auth/cookie/logout` - Clears HTTP-only auth cookies

**New Event**
- `user.login.social` - Emitted on OAuth login with payload: `{email, user_id, provider, is_new_user}`

**Frontend Migration Required**
- Add `credentials: 'include'` to all API requests
- Remove localStorage token management
- Use `/api/auth/cookie/logout` for logout

### Version 2.7.32 (2026-07-01)

**Feature Request - FR1: OAuth Provider Extensibility**

- New `swx_core.core.oauth_providers` module for custom auth providers
- Add GitHub, LinkedIn, Apple, etc. via configuration (no code changes)
- Dynamic provider loading based on `OAUTH_PROVIDERS` env variable

**OAuth Configuration Example:**

```bash
OAUTH_PROVIDERS=github,linkedin

GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx
GITHUB_REDIRECT_URI=http://localhost:8001/api/oauth/github/callback
GITHUB_AUTH_URL=https://github.com/login/oauth/authorize
GITHUB_TOKEN_URL=https://github.com/login/oauth/access_token
GITHUB_USER_INFO_URL=https://api.github.com/user
GITHUB_SCOPE=user:email
```

### Version 2.7.27 (2026-06-30)

**Critical Fix - Bug #7/29**

- Users no longer forced into teams — auto-creates personal team on registration
- New `AUTO_CREATE_PERSONAL_TEAM` setting (default: True)
- `create_personal_team()` hook creates team and sets `tenant_id`
- No more 500 errors for users without `tenant_id`

**New Settings**

- `AUTO_CREATE_PERSONAL_TEAM`: Auto-create personal team on registration (default: True)

### Version 2.7.26 (2026-06-30)

**New Features**

- Bug #25: Team-scoped roles (TeamRole model) — Separate from system RBAC
- Bug #26: Team invitation system — Create, accept, reject, revoke with expiration

**Bug Fixes**

- Bug #25: TeamMember now uses team_role_id instead of role_id

**New Models**

- TeamRole — Team-scoped roles with permissions dict
- TeamInvitation — Team invitations with audit trail

**New Services**

- TeamPermissionChecker — Check team-scoped permissions
- TeamInvitationService — Manage invitation lifecycle

**New Routes**

- POST /team-invitations/ — Create invitation
- POST /team-invitations/{token}/accept — Accept invitation
- POST /team-invitations/{token}/reject — Reject invitation
- DELETE /team-invitations/{id} — Revoke invitation
- GET /team-invitations/team/{team_id} — List team invitations
- GET /team-invitations/me — List my invitations

**Migration Required**

- `v2_7_26_team_roles_invitations.py`: Creates swx_team_role table, adds team_role_id to swx_team_member, creates swx_team_invitation table

### Version 2.7.25 (2026-06-30)

**Bug Fixes**

- Bug #16: Invalid `X-Tenant-ID` and `X-Team-ID` headers now log warnings instead of silently ignoring
- Bug #17: Added `LOG_DIR` setting for configurable log directory (default: `"logs"`)
- Bug #21: `get_entitlement()` now validates `current_period_end >= now()` to prevent expired subscriptions from granting access
- Bug #23: Added `UniqueConstraint("team_id", "user_id")` on `TeamMember` to prevent duplicate team memberships

**New Settings**

- `LOG_DIR`: Configurable log directory path (default: `"logs"`)

**Database Migration Required**

- `v2_7_24_add_team_member_unique.py`: Adds composite unique constraint on `swx_team_member(team_id, user_id)`

### Version 2.4.0 (2026-04-27)

**Breaking Changes**

- ⚠️ **Table Prefix Migration** - All framework tables now use `swx_` prefix to differentiate from user-defined tables
- 21 framework tables renamed (e.g., `users` → `swx_users`, `role` → `swx_role`)
- All foreign key references updated to use new table names
- Migration script provided at `swx_core/database/migrations/add_swx_prefix.py`

**New Features**

- ✅ Added table prefix documentation to `CUSTOM_MODELS.md` explaining:
  - How users can extend framework tables (4 patterns)
  - Using one-to-one extension tables
  - Model inheritance patterns
  - Service layer composition
  - Custom mixins for user tables
- ✅ Migration template for existing deployments to rename tables

**Table Changes (21 tables renamed)**

| Old Name | New Name |
|----------|----------|
| `users` | `swx_users` |
| `admin_user` | `swx_admin_user` |
| `role` | `swx_role` |
| `permission` | `swx_permission` |
| `team` | `swx_team` |
| `user_role` | `swx_user_role` |
| `team_member` | `swx_team_member` |
| `role_permission` | `swx_role_permission` |
| `audit_log` | `swx_audit_log` |
| `job` | `swx_job` |
| `language` | `swx_language` |
| `refresh_token` | `swx_refresh_token` |
| `policy` | `swx_policy` |
| `system_config` | `swx_system_config` |
| `system_config_history` | `swx_system_config_history` |
| `billing_account` | `swx_billing_account` |
| `billing_feature` | `swx_billing_feature` |
| `billing_plan` | `swx_billing_plan` |
| `billing_plan_entitlement` | `swx_billing_plan_entitlement` |
| `billing_subscription` | `swx_billing_subscription` |
| `billing_usage_record` | `swx_billing_usage_record` |

### Version 2.3.16 (2026-04-24)

**Bug Fixes**

- ✅ Fixed circular import during module reload - Added `_loading_modules` tracking set to prevent re-entrant `importlib.reload()` calls when modules have mutual import dependencies (e.g., Route → Controller → Service → Repository → Model)
- Modules being reloaded are now tracked in a global set, preventing recursive reload attempts that caused `ImportError` when partially-initialized modules tried to import from each other

### Version 2.3.15 (2026-04-24)

**Security**

- ✅ Fixed Redis config not respecting environment variables - Redis settings now properly read from environment variables instead of hardcoded defaults

### Version 2.3.14 (2026-03-31)

**Bug Fixes**

- ✅ Fixed duplicate prefix in routes - strips router's prefix from each route path before registering to avoid duplication
- Example: `v1/hospitals.py` with `prefix="/hospitals"` now correctly maps to `/api/v1/hospitals/` instead of `/api/v1/hospitals/hospitals/`

### Version 2.3.13 (2026-03-31)

**Bug Fixes**

- ✅ Fixed route mounting check - now properly checks if route paths from core_router are already registered in app before including

### Version 2.3.12 (2026-03-31)

**Bug Fixes**

- ✅ Fixed duplicate route registration in swagger - `bootstrap_app()` was registering same router as `app.include_router(router)`, causing routes to appear twice in OpenAPI docs

### Version 2.3.11 (2026-03-31)

**Bug Fixes**

- ✅ Fixed version prefix being stripped when routes define explicit prefix - versioned routes now ALWAYS get `/v1/` prefix regardless of explicit prefix setting

### Version 2.3.10 (2026-03-31)

**Bug Fixes**

- ✅ Fixed duplicate route registration - `load_user_routes()` now skips versioned directories (v1, v2, etc.) to avoid loading same routes twice
- ✅ Removed broken path stripping logic that could break valid routes
- ✅ Added `STRICT_ROUTE_LOADING` setting to raise errors for missing routers instead of warnings

**Improvements**

- ✅ Versioned routes now show version in tags (e.g., "v1 - User API")

### Version 2.3.9 (2026-03-31)

**Bug Fixes**

- ✅ Fixed EventBus.emit() method missing - Added `emit()` method as alias to `dispatch()` for backward compatibility
- ✅ Fixed BaseController accepting dicts for backward compatibility in create() and update() methods

### Version 2.3.8 (2026-03-31)

**Bug Fixes**

- ✅ Fixed BaseController.list() Query parameter issue - removed Query() wrapper from method default parameters to avoid passing Query objects to repository

### Version 2.3.7 (2026-03-31)

**Bug Fixes**

- ✅ Fixed BaseRepository session handling - Changed from `get_session()` (async generator) to `AsyncSessionLocal()` (session factory) in all 18 methods

### Version 2.3.6 (2026-03-31)

**Bug Fixes**

- ✅ Fixed dynamic_import path in router.py - was passing package name instead of filesystem path
- ✅ Fixed empty `__init__.py` files in route modules - populated all exports so routers are accessible
- ✅ Fixed migration NullType rendering - alembic was generating sa.NullType() which doesn't exist
- ✅ Fixed provider instantiation errors - discovery was returning module names instead of class names
- ✅ Fixed bootstrap_app() route registration - core routes weren't being registered with FastAPI app
- ✅ Added FIRST_ADMIN_EMAIL backward compatibility alias in settings

**Impact:** All core routes (auth, user, admin, utils) that were silently failing to load are now working.

### Version 2.3.5 (2026-03-30)

**Documentation**

- ✅ Updated FAQ with auth route auto-registration info
- ✅ Added NullType migration error troubleshooting

### Version 2.3.4 (2026-03-30)

**Bug Fixes**

- ✅ Fixed migration NullType rendering - maps NullType to DateTime() in Alembic autogenerate
- ✅ Fixed user_route.py: Removed invalid policy dependency that referenced path parameter at module level
- ✅ Fixed AuthServiceProvider boot recursion error - added graceful error handling
- ✅ Routes properly auto-registered: 84 total routes including /api/auth/*, /api/user/profile/*

**Note:** The auth routes ARE auto-registered at /api/auth/ - they were always working. The issue reported was based on incorrect testing.

### Version 2.3.3 (2026-03-30)

**Bug Fixes**

- ✅ Fixed REDIS_URL property conflict - renamed env var to REDIS_URL_OVERRIDE
- ✅ Fixed DATABASE_URL override precedence
- ✅ Fixed cache.py global declaration order syntax error

### Version 2.3.2 (2026-03-30)

**Bug Fixes**

- ✅ Fixed REDIS_URL property conflict - renamed env var to REDIS_URL_OVERRIDE

### Version 2.3.1 (2026-03-30)

**Bug Fixes**

- ✅ Added `render_item()` function in migrations/env.py for SQLModel type rendering (fixes AutoString/NullType errors)
- ✅ Fixed DATABASE_URL override - now takes precedence over computed DB_HOST, DB_PORT, etc.
- ✅ Fixed REDIS_URL override - now takes precedence over computed REDIS_HOST, REDIS_PORT
- ✅ Exported password utilities from `swx_core.security` (get_password_hash, verify_password)
- ✅ Added test conftest.py for required environment variables
- ✅ Fixed syntax error in cache.py (global declaration order)

**Documentation**
- ✅ Added DEPENDENCIES.md - Optional dependencies guide
- ✅ Added RESERVED_FIELD_NAMES.md - Document SQLModel reserved field names (metadata, registry, etc.)
- ✅ Updated GETTING_STARTED.md with new installation commands

### Version 2.3.0 (2026-03-30)

**Dependencies Restructuring**

- ✅ Removed unused dependencies (gunicorn, celery, rich, psutil, email-validator, prometheus-client, pgai)
- ✅ Moved optional features to extras (billing, monitoring, jobs, ai, prod)
- ✅ Fixed sentry-sdk version conflict (removed upper bound)

**Feature Flags (Optional Features)**

- ✅ Added BILLING_ENABLED, MONITORING_ENABLED, JOBS_ENABLED, AI_ENABLED settings
- ✅ Added is_billing_available, is_monitoring_available, is_jobs_available, is_ai_available properties
- ✅ Added lazy imports for stripe, sentry_sdk, redis, celery, pgai
- ✅ Made BillingServiceProvider conditional on BILLING_ENABLED
- ✅ Made RateLimitServiceProvider conditional on REDIS_ENABLED
- ✅ Added BILLING_ENABLED env var check to stripe webhook endpoint
- ✅ Added MONITORING_ENABLED env var check to sentry middleware

**Installation**

```bash
# Minimal (19 packages)
pip install swx-core

# With extras
pip install swx-core[billing,monitoring,jobs,ai,prod]
```

### Version 2.1.0 (2026-03-07)

**Framework Improvements**

**New Utilities:**
- ✅ Unit of Work pattern (`UnitOfWork`, `UnitOfWorkManager`, `@transactional` decorator) - Transaction management with automatic commit/rollback
MS|- ✅ Filter Builder (`FilterBuilder`, `SortBuilder`, `FilterParams`) - Fluent query filtering and sorting
TJ|- ✅ Database resilience (`pool_pre_ping`, `pool_recycle` settings) - Connection health checks and recycling
- ✅ API Versioning helpers (`VersionedRouter`, `deprecated_version`, `negotiate_version`) - Version management and deprecation
**Middleware Improvements:**
- ✅ Fixed CORS middleware auto-loading (`apply_middleware` hook)
- ✅ Fixed Sentry middleware auto-loading (`apply_middleware` hook)
- ✅ Fixed Metrics middleware auto-loading (`apply_middleware` hook)
- ✅ Updated middleware `__init__.py` exports for clean imports

**CLI Improvements:**
- ✅ Added `BASE_TEMPLATES` for modern BaseController/BaseService/BaseRepository patterns
- ✅ Added `--base` flag to `swx make:resource` command for modern scaffolding
- ✅ Scaffolding now supports both legacy (`swx make:resource Product`) and modern patterns (`swx make:resource Product --base`)

**Documentation:**
- ✅ Added USAGE_EXAMPLES.md with complete code examples for all base classes
- ✅ Added MIGRATION_GUIDE.md for v1.x to v2.0 migration
- ✅ Updated README.md with v2.0 base classes section

**Technical Details:**
- `swx_core/utils/unit_of_work.py` - UnitOfWork, UnitOfWorkManager, @transactional decorator
- `swx_core/utils/filters.py` - FilterBuilder, SortBuilder, FilterParams, FilterOperator
- `swx_core/database/db.py` - Added pool_pre_ping=True, pool_recycle=3600
- `swx_core/middleware/__init__.py` - Fixed exports, added apply_middleware functions
RQ|- `swx_core/cli/commands/resource_templates.py` - Added BASE_TEMPLATES dictionary
NQ|- `swx_core/cli/commands/make.py` - Added --base flag
- `swx_core/utils/versioning.py` - VersionedRouter, deprecated_version, negotiate_version, list_versions
- `tests/cli/test_make_commands.py` - CLI scaffolding tests

---

### Version 2.0.0 (2026-01-26)

**Base Classes Release**

**New Features:**
- ✅ BaseController - Full CRUD endpoints in minutes with hooks and events
- ✅ BaseService - Business logic with validation hooks and DTOs
- ✅ BaseRepository - Data access with pagination, filtering, soft-delete
- ✅ Comprehensive documentation (BASE_CLASSES.md, UTILITIES.md)

**Core Features (from v1.0.0):**
- ✅ Authentication (Admin, User, System domains)
- ✅ RBAC (Permission-first, team-scoped)
- ✅ Policy Engine (ABAC)
- ✅ Billing & Entitlements
- ✅ Rate Limiting
- ✅ Audit Logging
- ✅ Alerting System
- ✅ Background Jobs
- ✅ Runtime Settings
- ✅ Async Model
- ✅ Comprehensive Documentation

**Security:**
- ✅ Domain separation
- ✅ Token security
- ✅ Secrets management
- ✅ Security best practices

**Operations:**
- ✅ Docker deployment
- ✅ Health checks
- ✅ Monitoring
- ✅ Backup & recovery

**Testing:**
- ✅ Unit tests
- ✅ Integration tests
- ✅ Acceptance tests
- ✅ Simulation tools

---

### Version 1.0.0 (2026-01-15)

**Initial Release**

**Features:**
- ✅ Authentication (Admin, User, System domains)
- ✅ RBAC (Permission-first, team-scoped)
- ✅ Policy Engine (ABAC)
- ✅ Billing & Entitlements
- ✅ Rate Limiting
- ✅ Audit Logging
- ✅ Alerting System
- ✅ Background Jobs
- ✅ Runtime Settings
- ✅ Async Model
- ✅ Comprehensive Documentation

**Security:**
- ✅ Domain separation
- ✅ Token security
- ✅ Secrets management
- ✅ Security best practices

**Operations:**
- ✅ Docker deployment
- ✅ Health checks
- ✅ Monitoring
- ✅ Backup & recovery

**Testing:**
- ✅ Unit tests
- ✅ Integration tests
- ✅ Acceptance tests
- ✅ Simulation tools

---

## Breaking Changes

### Version 2.0.0

**Recommended Changes (Non-Breaking):**
- Replace static CRUD functions with BaseController/BaseService/BaseRepository pattern
- Update CLI commands to use `--base` flag for modern scaffolding

### Version 1.0.0

**No breaking changes** - Initial release.

---

## Deprecations

### Version 2.1.0

**Deprecated:**
- Static CRUD scaffolding (use `--base` flag for modern patterns)

### Version 1.0.0

**No deprecations** - Initial release.

---

## Migration Notes

### Version 2.0.0

**Upgrading from v1.x:**
- Read [Migration Guide](../07-extending/MIGRATION_GUIDE.md) for step-by-step instructions
- No breaking changes - existing code continues to work
- Optionally migrate to BaseController/BaseService/BaseRepository pattern

### Version 1.0.0

**Initial Setup:**
- Run migrations: `alembic upgrade head`
- Seed system: `python scripts/seed_system.py`
- Configure environment: Set required `.env` variables

---

## Next Steps

- Read [Migration Guide](../07-extending/MIGRATION_GUIDE.md) for v1.x to v2.0 migration
- Read [Base Classes](../04-core-concepts/BASE_CLASSES.md) for BaseController/BaseService/BaseRepository usage
- Read [Utilities](../04-core-concepts/UTILITIES.md) for all utility modules
- Read [Usage Examples](../04-core-concepts/USAGE_EXAMPLES.md) for complete code examples
- Read [Overview](../01-overview/OVERVIEW.md) for framework introduction

---

**Status:** Changelog updated for v2.1.0 release.