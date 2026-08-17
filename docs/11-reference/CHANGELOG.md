# Changelog

**Version:** 2.21.0  
**Last Updated:** 2026-08-17

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

### Version 2.19.16 (2026-08-11)

**Entitlement Resolver — scalar_one_or_none() crash fix & code-clarity refactor**

#### Fixed

1. **P0 — `get_remaining_quota()` crashes with `MultipleResultsFound`** — `scalar_one_or_none()` on a multi-row `UsageRecord` query raised an exception when more than one record existed. Replaced with `func.coalesce(func.sum(UsageRecord.quantity), 0)` aggregation scoped to the subscription period.

#### Changed

2. **Extracted `_get_account_and_subscription()` private helper** — Eliminates duplicated 20-line account+subscription query block from `get_entitlement()` and `get_remaining_quota()`.

3. **Eliminated 6 redundant DB queries in `get_remaining_quota()`** — Previously called `get_entitlement()` which re-queried account+subscription. Now inlines the entitlement lookup, reducing total queries from 9 to 3.

4. **Replaced magic number `999999999`** with named constant `UNLIMITED_QUOTA = 999_999_999`.

5. **Extracted `_ACTIVE_STATUSES` frozenset** — `[SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]` was duplicated; now a module-level constant.

6. **Removed unused imports** — `Union`, `Dict`, `Any`, `Plan` were imported but never used.

7. **f-string → lazy logging** — `logger.warning(f"...")` → `logger.warning("...", feature_key)`.

---

### Version 2.17.0 (2026-07-30)

**OAuth Multi-Domain Support & Registration Bug Fix**

#### Fixed

1. **P0 — OAuth registration fails: password exceeds max_length** — `secrets.token_urlsafe(32)` generates 43 characters, exceeding `UserCreate.password` max_length of 40. Changed to `token_urlsafe(28)` (~38 chars). All new OAuth registrations were blocked.

2. **P1 — OAuth callback redirects to wrong domain** — Callbacks were hardcoded to `FRONTEND_HOST`, losing user context on subdomains. Added origin preservation via session (`oauth_origin`) so users on `chat.fastpii.com` return there instead of `fastpii.com`.

3. **P2 — Single redirect URI limitation** — Only one `GOOGLE_REDIRECT_URI` / `FACEBOOK_REDIRECT_URI` could be configured. Added `GOOGLE_REDIRECT_URIS` and `FACEBOOK_REDIRECT_URIS` (comma-separated lists) for multi-domain support, with `resolve_redirect_uri()` matching request origin against allowed URIs.

4. **P2 — OAuth URLs endpoint performance** — Added `@lru_cache(maxsize=1)` to `_get_oauth_urls_cached()` since URLs are static.

#### New Settings

| Setting | Default | Description |
|---|---|---|
| `GOOGLE_REDIRECT_URIS` | `[]` | Comma-separated allowed Google redirect URIs (takes precedence over `GOOGLE_REDIRECT_URI`) |
| `FACEBOOK_REDIRECT_URIS` | `[]` | Comma-separated allowed Facebook redirect URIs (takes precedence over `FACEBOOK_REDIRECT_URI`) |
| `{PROVIDER}_REDIRECT_URIS` | `[]` | Comma-separated allowed redirect URIs for any custom OAuth provider |

#### Backward Compatibility

Fully backward compatible. If `*_REDIRECT_URIS` is not set, the existing `*_REDIRECT_URI` single-URI behavior is used unchanged.

---

### Version 2.16.0 (2026-07-29)

**Notification System Enhancements — 7 features**

#### Added

1. **Email provider cost/limits/country routing** — 9 new fields on `EmailProviderConfig` (cost_per_email, daily/monthly/hourly limits, supported_countries, tracking controls, reply_to). Country-aware routing and preferred provider override in `provider_factory.py`.

2. **Hybrid template approach** — `render_template()` supports optional `base_template_path` for file-based Jinja2 base layout with `{% extends %}` + `{% block content %}`. Backward compatible.

3. **Email OTP service** — New `email_otp_service.py` with generate/verify/resend, bcrypt hashing, configurable rate limits/cooldown/max attempts, testing bypass, custom exception hierarchy.

4. **Notification preference escalation** — `reminder_time`, `escalation_enabled`, `escalation_hours` fields.

5. **Celery queue integration** — `send_notification(queue=True)` dispatches to Celery via `send_task()`. Falls back to synchronous if Celery not installed.

6. **Template variable enrichment** — Auto-injects `brand_name`, `brand_color`, `support_email`, `frontend_url` into every template context.

7. **Provider health check + statistics** — `test_email_provider()` and `get_provider_statistics()` in `management_service.py`.

---

### Version 2.15.6 (2026-07-29)

**P0 Circular Import Fix**

`import swx_core` crashed with `ImportError: cannot import name 'get_container'`. The v2.15.0 timezone refactor exposed a latent circular dependency: `utils/__init__.py` → `utils.dependencies` → `container.container.get_container` (already being initialized).

Fix: Made `get_container` import lazy in `dependencies.py` via `_get_container()` helper.

---

### Version 2.15.5 (2026-07-29)

**Round 3 Feedback — 5 fixes**

#### P1 Critical

1. **`ledger_service.py` ImportError** — dead `utc_now_naive` import removed, replaced with `utc_now` from `swx_core.utils.time`.
2. **`plan_helper.py` hardcoded "free"** — 4 places replaced with `settings.DEFAULT_PLAN_KEY`.
3. **Rate limit dual-path** — `RateLimitMiddleware` now accepts `exempt_namespaces: list[str]` to skip middleware rate limiting on routes using `enforce_limit()` exclusively.

#### P3 Minor

4. **JWT billing_plan fallback** — 2x `"free"` in `rate_limit_middleware.py` replaced with `settings.DEFAULT_PLAN_KEY`.

#### P2 Quality of Life

5. **Centralized JSON utility** — new `swx_core/utils/json.py` with `SwxJSONEncoder`, `dumps()`, `loads()`.

---

### Version 2.15.4 (2026-07-29)

**Dual-Format API Key Scopes + Code-Clarity Cleanup**

#### Added

1. **`ApiKeyCreate.scopes`** — accepts both `list[str]` (`["billing:read"]`) and `list[dict]` (`[{"resource": "billing", "action": "read"}]`). Normalized internally. No API contract break for migrating projects.
2. **`parse_scope_string()`** — new function in `api_key_scope_service.py`. Inverse of `expand_scopes()`.
3. **`_normalize_scopes()`** — internal normalization in `api_key_service.py`.

#### Code-Clarity Cleanup

4. Removed redundant `_utc_now()` / `_utc_now_naive()` wrappers in `api_key_service.py`, `subscription_service.py`, `job_runner.py`
5. Removed dead imports in `refresh_token_service.py`, `api_key_scope_repository.py`, `webhook_repository.py`

---

### Version 2.15.3 (2026-07-29)

**Per-Route Rate Limit API + Pluggable Config Resolver**

#### Added

1. **`enforce_limit()`** — New per-route rate limit enforcement API in `swx_core/services/rate_limit/enforce.py`. Route handlers can enforce rate limits with custom namespaces (e.g., `detection:detect:public` vs `detection:detect:team`). Resolves actor from JWT/request.state, checks Redis, raises `HTTPException(429)` if exceeded.

2. **Pluggable `SettingsService`** — `SettingsService.__init__()` accepts optional `model` parameter for custom config tables. Projects with existing config tables can use the framework's type-safe getters, TTL caching, and env fallback without a data migration.

---

### Version 2.15.2 (2026-07-29)

**SystemConfig JSONB + Metadata/Permissions JSONB**

Converted `SystemConfig.value` from VARCHAR(5000) to JSONB and metadata/permissions columns from JSON to JSONB.

#### Changes

1. **SystemConfig.value** — VARCHAR(5000) → JSONB. Values stored as native JSON types, returned as native Python types. No `json.loads()` on DB reads.
2. **SystemConfig.metadata** — JSON → JSONB (both SystemConfig and SystemConfigHistory tables)
3. **SystemConfigHistory.old_value / new_value** — VARCHAR(5000) → JSONB
4. **TeamRole.permissions** — JSON → JSONB
5. **settings_service.py** — `_convert_value()` handles native JSONB types from DB + strings from env vars
6. **settings_crud_service.py** — validation handles native types alongside strings
7. **Data migration** — `v2_15_2_convert_system_config_jsonb.py` for existing databases

#### Migration Guide

1. Install `swx-core>=2.15.2`
2. Copy `v2_15_2_convert_system_config_jsonb.py` to project's `migrations/versions/`
3. Set `down_revision` to current head
4. Run `alembic upgrade head`

---

### Version 2.15.1 (2026-07-29)

**Multi-Tenancy for Platform-Level Models**

Added optional team scoping to `LLMProviderConfig`, `Notification`, and `ApiKey` via nullable `team_id` FK to `swx_team.id`. `NULL` = platform-level, non-`NULL` = team-scoped. Backward compatible — existing rows get `NULL`.

#### Changes

1. **LLMProviderConfig** — nullable `team_id`, `get_all()` and `get_by_provider()` accept `team_id` filter
2. **Notification** — nullable `team_id`, `list_notifications()` and `count_notifications()` accept `team_id` filter
3. **ApiKey** — nullable `team_id`, `list_api_keys()` and `count_api_keys()` accept `team_id` filter
4. **Data migration** — `v2_15_1_add_team_id_to_platform_models.py` for existing databases
5. **Template migrations** — 3 template migrations updated with `team_id` column + FK + index
6. **Docs** — `MULTI_TENANT.md` and `MULTI_TENANT_MIGRATION.md` updated

#### Migration Guide

1. Install `swx-core>=2.15.1`
2. Copy `v2_15_1_add_team_id_to_platform_models.py` to project's `migrations/versions/`
3. Set `down_revision` to current head
4. Run `alembic upgrade head`

---

### Version 2.15.0 (2026-07-29)

**Timezone-Aware Timestamps — Breaking Change**

All timestamps are now timezone-aware. Requires database migration (`TIMESTAMP` → `TIMESTAMPTZ`).

#### Breaking Changes

1. **All timestamps now timezone-aware** — New `swx_core/utils/time.py` exports `utc_now()` returning `datetime.now(timezone.utc)`. Replaced 216 occurrences of naive-timestamp anti-patterns across 103 files: `def utc_now_naive()` (44 defs removed), `datetime.now(timezone.utc).replace(tzinfo=None)` (140 calls), `datetime.utcnow()` (7 production calls, Python 3.12 deprecated), and inline lambda default factories.

2. **Database columns changed** — All `Column(DateTime, ...)` changed to `Column(DateTime(timezone=True), ...)` across 49 model files, `mixins.py`, 15 template migrations, and 2 framework migrations. PostgreSQL creates `TIMESTAMPTZ` columns.

3. **Data migration required** — `swx_core/database/migrations/v2_15_0_convert_timestamptz.py` converts existing `TIMESTAMP WITHOUT TIME ZONE` columns to `TIMESTAMPTZ` using `AT TIME ZONE 'UTC'`. Copy to project migrations, set `down_revision`, run `alembic upgrade head`.

#### Migration Guide

1. Install `swx-core>=2.15.0`
2. Copy `v2_15_0_convert_timestamptz.py` to project's `migrations/versions/`
3. Set `down_revision` to current head
4. Run `alembic upgrade head`
5. Use `utc_now()` from `swx_core.utils.time` in custom code instead of `datetime.now(timezone.utc).replace(tzinfo=None)` or `datetime.utcnow()`
6. Change custom model `Column(DateTime, ...)` to `Column(DateTime(timezone=True), ...)`

---

### Version 2.14.4 (2026-07-29)

**Bug Fixes from FastPII Migration Feedback — 4 fixes**

Patch release fixing a P0 runtime crash and three P1 issues surfaced during the FastPII Platform migration from v2.7.44 → v2.14.3. All changes are backward compatible.

#### P0 Critical Fixes

1. **`SettingsService._convert_value()` NameError** — `settings_service.py` referenced `SystemConfigValueType` (a non-existent name) instead of the imported `SettingValueType`. Every typed getter (`get_int()`, `get_bool()`, `get_json()`) crashed at runtime. Only `get_string()` survived via the `else` fallthrough.

2. **Template migrations: branched chain (two heads)** — The 15 template migrations shipped with a branch at `cb96a87ddcc2` producing two alembic heads. Rewired `f38a4c8d9b12.down_revision` to `f7b6d8e0a2c4`, producing a single linear chain.

3. **`RateLimitMiddleware._get_user_billing_plan()` always returned `"free"`** — The stub hardcoded `return "free"` with dead `EntitlementResolver`/`AsyncSessionLocal` imports. Pro/Enterprise users got rate-limited as `free` when `request.state.current_user` was pre-resolved. Replaced with JWT claim decode.

4. **CSRF helpers hardcoded `CSRF_COOKIE_NAME`** — `get_csrf_token()` and `set_csrf_cookie()` used the module constant instead of the middleware instance's `cookie_name`. Added `cookie_name` parameter (backward-compatible default).

#### P3 Minor Fixes

5. **Dead `lru_cache` import** — `settings_service.py` imported `lru_cache` from `functools` but never used it. Removed.

---

### Version 2.14.3 (2026-07-28)

**Edge Case & Security Hardening — 27 fixes from comprehensive audit**

Security and robustness fixes across billing, LLM, notification, compliance, and config modules. All changes are backward compatible.

#### P0 Critical Fixes

1. **Sentry middleware: placeholder DSN crashes** — `setup_sentry_middleware()` now validates DSN format via `is_valid_dsn()` before initializing Sentry. Invalid/placeholder DSNs are rejected with a logged warning instead of crashing at runtime.

2. **Config resolver: multi-variable substitution bug** — `${HOST:-localhost}:${PORT:-5432}` now correctly resolves to `localhost:5432` instead of `localhost:localhost`. Single-colon syntax `${VAR:default}` also supported.

3. **Config cache: ValueError on missing env vars** — `resolve_config_value()` catches `ValueError` from `resolve_config()` when env vars are missing, returning the fallback instead of crashing.

4. **Stripe provider: mock key bypasses validation** — `get_stripe_provider()` validates `sk_live_`/`sk_test_` keys are not mock placeholders. Mock keys no longer pass truthiness checks.

5. **Webhook secret: mock secret bypasses validation** — `stripe_webhook.py` rejects `whsec_mock` and similar mock secrets via `is_valid_webhook_secret()`.

6. **Billing provider: Stripe key format validation** — `billing_provider.py` validates Stripe API key prefix and rejects placeholder patterns before making API calls.

#### P1 High Fixes

7. **Billing providers: HTTP error handling** — Flutterwave, Paystack, and Mpesa providers catch `httpx` transport/status errors, log with `logger.exception()`, and re-raise as `HTTPException(503)`.

8. **Subscription service: rollback on write failures** — All four `session.add()`/`session.commit()` paths wrap in `try/except`, call `await session.rollback()`, log, and re-raise.

9. **LLM providers: error logging in fallback** — OpenAI, Azure, Anthropic, and Ollama providers now log `logger.error()` inside `except Exception as exc` blocks instead of silently swallowing errors.

10. **Notification providers: graceful failure** — Twilio, SendGrid, Africa's Talking, and SMTP providers catch HTTP/SMTP transport errors, log stack traces, and return structured failure payloads instead of raising.

11. **Sentry middleware: init guard** — `SentryMiddleware.__init__()` wraps SDK init in `try/except` so misconfigured DSNs don't prevent app startup.

#### New Module

- **`swx_core/config/validation.py`** — Shared validation utilities: `is_valid_config_value()`, `is_valid_api_key()`, `is_valid_dsn()`, `is_valid_redis_url()`, `is_valid_webhook_secret()`. Checks that config values are not placeholders, mocks, or malformed. Exported via `swx_core.config`.

#### Changed Files

| File | Change |
|---|---|
| `swx_core/config/validation.py` | **New** — Shared config validation utilities |
| `swx_core/config/__init__.py` | Export validation functions |
| `swx_core/middleware/sentry_middleware.py` | DSN validation + try/except init guard |
| `swx_core/services/llm/config_resolver.py` | Multi-variable substitution fix, single-colon syntax |
| `swx_core/services/compliance/config_cache.py` | ValueError handling on missing env vars |
| `swx_core/services/billing/stripe_provider.py` | Mock key validation |
| `swx_core/providers/billing_provider.py` | Stripe API key format validation |
| `swx_core/webhooks/stripe_webhook.py` | Webhook secret mock rejection |
| `swx_core/services/billing/providers/flutterwave_provider.py` | HTTP error handling + logging |
| `swx_core/services/billing/providers/paystack_provider.py` | HTTP error handling + logging |
| `swx_core/services/billing/providers/mpesa_provider.py` | HTTP error handling + logging |
| `swx_core/services/billing/subscription_service.py` | Rollback on write failures + logging |
| `swx_core/services/llm/providers/openai_provider.py` | Error logging in fallback path |
| `swx_core/services/llm/providers/azure_provider.py` | Error logging in fallback path |
| `swx_core/services/llm/providers/anthropic_provider.py` | Error logging in fallback path |
| `swx_core/services/llm/providers/ollama_provider.py` | Error logging in fallback path |
| `swx_core/services/notifications/providers/twilio_provider.py` | Graceful failure handling + logging |
| `swx_core/services/notifications/providers/sendgrid_provider.py` | Graceful failure handling + logging |
| `swx_core/services/notifications/providers/africas_talking_provider.py` | Graceful failure handling + logging |
| `swx_core/services/notifications/providers/smtp_provider.py` | Graceful failure handling + logging |
| `swx_core/cli/commands/security_validation.py` | Strengthened identifier/keyword/path validation |

**Backward Compatibility:** Fully backward compatible. All fixes are defensive — they add validation, logging, and error handling without changing any public APIs or behavior for correctly configured systems.

---

### Version 2.14.2 (2026-07-28)

**Test Suite Hardening — 100% pass rate achieved (244 passed, 2 skipped)**

- Fixed `security_validation.py` Python identifier validation, keyword checking, and path traversal patterns
- Completed `SimpleNamespace` mock attributes for API key scoping tests
- Added `passlib` import skip for environments without passlib installed
- Exported `FEATURE_FLAG_CACHE_TTL` module-level constant from settings
- Fixed env var syntax in compliance service tests
- Fixed mask assertion in compliance event tests
- Fixed template key assertions in webhook service tests

---

### Version 2.14.1 (2026-07-28)

**Tier 3 Test Fixes**

- Fixed all Tier 3 feature test failures
- Corrected model field references, import paths, and test assertions

---

### Version 2.14.0 (2026-07-28)

**Tier 3 Feature Suite: 6 Enterprise Features**

Six production-grade features: Conversation State, AI Safety & Content Filtering, Enterprise SSO, Status Page, Data Export/Import, and Feature Flags & A/B Testing. All follow Repository → Service → Controller → Route pattern with event emission, caching, and database-driven configuration.

#### New Features

1. **Conversation State** — Persistent conversation tracking with message threading, soft-delete (archive/delete), metadata support, and user ownership scoping. Admin and user domain routes. Migration: `b2c1f3d5a7e9`.

2. **AI Safety & Content Filtering** — Content moderation pipeline with configurable filter types (regex, keyword, AI classifier, custom), severity levels, action policies (allow/flag/block/replace), and per-request safety checks with result logging. Migration: `c3d2e4f6b8a0`.

3. **Enterprise SSO** — SAML and OIDC identity provider configuration with provider management (CRUD), SSO session tracking, domain-based auto-detection, and session termination. Supports multiple active sessions per user. Migration: `d4e3f5a7c9b1`.

4. **Status Page** — Service component monitoring with operational status tracking, incident management with severity levels, incident timeline updates, and public status summary endpoint. Component grouping and sorting supported. Migration: `e5f4a6b8d0c2`.

5. **Data Export/Import** — GDPR-compliant user data export (JSON/CSV formats) and import with progress tracking, status management (pending/processing/completed/failed/expired), and per-user isolation. Migration: `f6a5b7c9e1d3`.

6. **Feature Flags & A/B Testing** — Feature flag management with percentage rollouts, variant assignment with deterministic hashing, sticky variants, time-windowed activation, and per-user evaluation tracking. Supports rule-based targeting via JSONB rules. Migration: `f7b6d8e0a2c4`.

#### New Settings

| Setting | Default | Description |
|---|---|---|
| `CONVERSATION_ENABLED` | `True` | Enable conversation state tracking |
| `CONVERSATION_DEFAULT_PAGE_SIZE` | `50` | Default page size for conversation listing |
| `CONVERSATION_MAX_MESSAGE_LENGTH` | `10000` | Maximum message content length |
| `CONVERSATION_CACHE_TTL` | `30` | Conversation config cache TTL |
| `SAFETY_ENABLED` | `True` | Enable AI safety and content filtering |
| `SAFETY_DEFAULT_ACTION` | `"flag"` | Default action when content flagged |
| `SAFETY_CACHE_TTL` | `60` | Safety filter config cache TTL |
| `SAFETY_MAX_CONTENT_LENGTH` | `50000` | Maximum content length for safety checks |
| `SAFETY_LOG_ALL_CHECKS` | `True` | Log all safety checks for audit |
| `SSO_ENABLED` | `True` | Enable enterprise SSO |
| `SSO_CACHE_TTL` | `60` | SSO provider config cache TTL |
| `SSO_SESSION_TIMEOUT` | `28800` | SSO session timeout (8 hours) |
| `SSO_ALLOW_MULTIPLE_SESSIONS` | `True` | Allow multiple active SSO sessions |
| `STATUS_ENABLED` | `True` | Enable status page |
| `STATUS_CACHE_TTL` | `30` | Status page cache TTL |
| `STATUS_DEFAULT_PAGE_SIZE` | `50` | Default page size for status listings |
| `DATA_TRANSFER_ENABLED` | `True` | Enable data export/import |
| `DATA_TRANSFER_CACHE_TTL` | `60` | Data transfer config cache TTL |
| `DATA_EXPORT_EXPIRY_DAYS` | `7` | Days before export files expire |
| `DATA_EXPORT_MAX_RECORDS` | `100000` | Maximum records per export |
| `DATA_IMPORT_MAX_FILE_SIZE` | `52428800` | Maximum import file size (50MB) |
| `FEATURE_FLAG_ENABLED` | `True` | Enable feature flags and A/B testing |
| `FEATURE_FLAG_CACHE_TTL` | `300` | Feature flag cache TTL |
| `FEATURE_FLAG_CACHE_L1_MAX_ENTRIES` | `200` | Maximum L1 cache entries |

#### New Database Migrations

| Migration | Feature |
|---|---|
| `b2c1f3d5a7e9` | Conversation State (swx_conversation, swx_conversation_message) |
| `c3d2e4f6b8a0` | AI Safety (swx_content_filter, swx_safety_check) |
| `d4e3f5a7c9b1` | Enterprise SSO (swx_sso_provider, swx_sso_session) |
| `e5f4a6b8d0c2` | Status Page (swx_service_component, swx_status_incident, swx_incident_update) |
| `f6a5b7c9e1d3` | Data Export/Import (swx_data_export, swx_data_import) |
| `f7b6d8e0a2c4` | Feature Flags (swx_feature_flag, swx_flag_evaluation) |

**Backward Compatibility:** Fully backward compatible. All new settings have safe defaults.

---

### Version 2.13.0 (2026-07-28)

**Tier 2 Feature Suite: 4 Enterprise Features**

Four production-grade features: Compliance Audit, Notification Factory, API Key Scoping, and Webhook System. All follow Repository → Service → Controller → Route pattern with event emission, caching, and database-driven configuration.

#### New Features

1. **Compliance Audit** — GDPR/CCPA audit logging with severity, data classification, field redaction, IP masking, retention policies, and data subject request handling (access, deletion, portability, rectification, restriction). Migration: `d1f6e4a9c3b2`.

2. **Notification Factory** — Multi-provider notifications (SMTP, SendGrid, Twilio, Africa's Talking) with circuit breaker fallback, Jinja2 templates, delivery tracking, and preference management. Migration: `e7a3c1b2d4f5`.

3. **API Key Scoping** — SHA-256 hashed API key management with resource:action scope patterns, wildcards, key rotation with grace period, and per-key rate limit overrides. Migration: `f8b2d5e7a1c3`.

4. **Webhook System** — Outbound webhook delivery with HMAC-SHA256 signing, circuit breaker per endpoint, exponential backoff retry with jitter, wildcard event subscription, and delivery status tracking. Migration: `a91c4e2f7b6d`.

#### New Settings

| Setting | Default | Description |
|---|---|---|
| `COMPLIANCE_ENABLED` | `True` | Enable compliance audit logging |
| `COMPLIANCE_DEFAULT_SEVERITY` | `"medium"` | Default audit log severity |
| `NOTIFICATION_ENABLED` | `True` | Enable notification system |
| `API_KEY_ROTATION_GRACE_HOURS` | `24` | Hours both keys valid during rotation |
| `WEBHOOK_ENABLED` | `True` | Enable outbound webhooks |
| `WEBHOOK_DEFAULT_RETRY_COUNT` | `3` | Default retry count per delivery |
| `WEBHOOK_CIRCUIT_BREAKER_THRESHOLD` | `5` | Failures before circuit opens |

#### New Documentation

- `docs/04-core-concepts/COMPLIANCE_AUDIT.md`
- `docs/04-core-concepts/NOTIFICATION_FACTORY.md`
- `docs/04-core-concepts/API_KEY_SCOPING.md`
- `docs/04-core-concepts/WEBHOOK_SYSTEM.md`

**Backward Compatibility:** Fully backward compatible. All new settings have safe defaults.

---

### Version 2.11.0 (2026-07-27)

**Rate Limiting Overhaul: 6 Bug Fixes + 2 Features**

#### Bug Fixes

1. **apply_middleware() ignores skip_paths** — `RateLimitMiddleware.__init__` now merges built-in defaults with the `RATE_LIMIT_SKIP_PATHS` setting, allowing downstream apps to exempt custom paths without subclassing.

2. **RATE_LIMIT_ENABLED never checked** — `dispatch()` now returns early when `RATE_LIMIT_ENABLED=False`, properly disabling rate limiting for local development.

3. **Fail-closed on Redis outage blocks ALL requests** — Added `RATE_LIMIT_FAIL_OPEN` setting (default `False`). When enabled, requests are allowed through with a warning log if Redis is unavailable, preventing total service blackout during Redis outages.

4. **decode_responses=False causes type mismatches** — Fixed Redis client creation in `apply_middleware()` to use `decode_responses=True`, consistent with the rest of the codebase.

5. **get_limit() returns 1 for missing registry entries** — Now falls back to the `free` plan's `api_requests` limits before returning the restrictive default of 1. Missing entries are logged at `ERROR` level instead of `WARNING`.

6. **_actor_from_bearer() hardcodes billing_plan="free"** — Now reads the `billing_plan` claim from the JWT payload with a `"free"` fallback, making billing-aware rate limiting functional.

#### Features

1. **Database-driven rate limit overrides** — Rate limits can now be overridden at runtime via SystemConfig entries with `RATE_LIMIT` category. Keys follow the pattern `rate_limit.{plan}.{feature}.{endpoint_class}.{limit_type}` (e.g., `rate_limit.pro.api_requests.read.burst`). Overrides are loaded lazily on first request and cached in-memory. Controlled by `RATE_LIMIT_OVERRIDE_ENABLED` setting (default `True`).

2. **Billing plan resolution in JWT** — Access tokens now include a `billing_plan` claim resolved from the user's active subscription at login time. The rate-limit middleware reads this claim to apply plan-correct limits. Plan resolution follows `BillingAccount → Subscription → Plan` via the repository layer.

#### New Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `RATE_LIMIT_SKIP_PATHS` | `[]` | Additional paths to skip rate limiting |
| `RATE_LIMIT_FAIL_OPEN` | `False` | Allow requests when Redis unavailable |
| `RATE_LIMIT_OVERRIDE_ENABLED` | `True` | Enable DB-driven overrides via SystemConfig |

#### New Files

- `swx_core/repositories/billing_repository.py` — Billing plan resolution queries
- `swx_core/repositories/system_config_repository.py` — SystemConfig rate limit queries
- `swx_core/services/billing/plan_helper.py` — `get_user_plan_key()` service
- `swx_core/services/rate_limit/rate_limit_override.py` — Override cache + resolver

#### Changed Files

- `swx_core/config/settings.py` — 3 new rate limit settings
- `swx_core/middleware/rate_limit_middleware.py` — Bug fixes 1-4, 6 + override integration
- `swx_core/services/rate_limit/rate_limiter.py` — Bug fix 3 (fail-open support)
- `swx_core/services/rate_limit/limit_registry.py` — Bug fix 5 (sensible fallback)
- `swx_core/services/rate_limit/__init__.py` — Export override functions
- `swx_core/auth/core/jwt.py` — `billing_plan` claim support in `create_token()`
- `swx_core/security/refresh_token_service.py` — `billing_plan` param in `create_access_token()`
- `swx_core/services/auth_service.py` — Plan resolution at all 3 token creation sites

**Backward Compatibility:** Fully backward compatible. All new settings have safe defaults. Existing JWT tokens without `billing_plan` claim default to `"free"`.

---

### Version 2.10.1 (2026-07-26)

**Bug Fix: Module Loader Topological Sort**

Fixed `dynamic_import` in `swx_core/utils/loader.py` to resolve module dependencies before loading, preventing `ImportError: partially initialized module` when cross-module imports exist.

**Root Cause:** `pkgutil.iter_modules` returns modules in filesystem (alphabetical) order. When module A imports from module B but A comes first alphabetically, `importlib.import_module(A)` would fail because B hasn't been loaded yet — especially during reload when `_loading_modules` guards prevent re-entrant imports.

**Fix:**
- Added `_extract_imports_from_file()` — AST-based parser that scans Python files for intra-package import dependencies
- Added `_topological_sort()` — Kahn's algorithm (BFS-based) that orders modules so dependencies load before dependents
- `dynamic_import()` now runs in three phases: (1) discover modules + build dep graph, (2) topological sort, (3) load in dependency-safe order
- Circular dependencies are handled gracefully — remaining modules after topological sort are appended in original order

**Changed Files:**
- `swx_core/utils/loader.py` — New `_extract_imports_from_file()`, `_topological_sort()`, and three-phase `dynamic_import()`

**Backward Compatibility:** Fully backward compatible. Same function signatures, same return types. Only changes the loading order.

### Version 2.10.0 (2026-07-23)

**Feature: Extended Caching — Feature Flags, Roles, and Settings**

Adds L1/L2 Redis-backed caching for feature flag lookups, role lookups, and runtime settings, following the same pattern as auth caching (v2.8.0). All caches are **disabled by default** for backward compatibility.

**New Files:**
- `swx_core/utils/runtime_cache.py` — RuntimeCache class for feature flags and settings (L1 process-local + L2 Redis)

**New Configuration:**
- `FEATURE_FLAG_CACHE_ENABLED` (default: False) — Enable feature flag caching
- `FEATURE_FLAG_CACHE_TTL` (default: 300) — TTL in seconds for cached feature flags
- `FEATURE_FLAG_CACHE_L1_MAX_ENTRIES` (default: 200) — Max L1 entries for feature flags
- `SETTINGS_CACHE_ENABLED` (default: False) — Enable runtime settings caching
- `SETTINGS_CACHE_TTL` (default: 60) — TTL in seconds for cached settings
- `SETTINGS_CACHE_L1_MAX_ENTRIES` (default: 500) — Max L1 entries for settings

**Changes:**
- `swx_core/rbac/helpers.py` — `get_user_roles()` now checks L1→L2→DB when `USER_CACHE_ENABLED=True`
- `swx_core/services/settings_helper.py` — `get_feature_flag()` now checks L1→L2→DB when `FEATURE_FLAG_CACHE_ENABLED=True`
- `swx_core/services/settings_helper.py` — New `get_setting_cached()` for L1/L2 settings lookups
- `swx_core/auth/auth_cache.py` — New `get_cached_roles()`, `set_cached_roles()`, `invalidate_user_roles()`, `invalidate_all_roles()`
- `swx_core/services/user_role_service.py` — Invalidates role cache on assign/remove
- `swx_core/services/role_service.py` — Invalidates role cache on update/delete
- `swx_core/services/settings_crud_service.py` — Invalidates feature flag and settings caches on create/update

**Backward Compatibility:** All new caches are opt-in (disabled by default). No behavior change unless explicitly enabled via environment variables.

### Version 2.9.0 (2026-07-22)

**CRITICAL SECURITY FIX: Cookie Login Token Leak**

Fixed critical vulnerability where `/auth/cookie/login` returned access token in response body, defeating httpOnly cookie security.

**Security Fixes:**

1. **Cookie Login Token Leak (CRITICAL)**
   - Removed access_token from cookie_login response
   - Tokens now ONLY accessible via httpOnly cookies
   - Prevents XSS token extraction

2. **Exception Handler Information Disclosure (MEDIUM)**
   - Changed to structured logging (exception type + request_id only)
   - Prevents database URLs, file paths, PII in logs
   - Response includes request_id for debugging

3. **Validation Error Handler (MEDIUM)**
   - Returns field-level error details
   - Improves API consumer experience
   - Uses WARNING level for client errors

**Documentation Added:**

- Rate limiting implementation guide
- CSRF protection patterns
- Security best practices for production

**Severity:** Critical (1), High (2), Medium (2), Low (1)

**Thanks:** FastPII Security Team for responsible disclosure

**Upgrade:** IMMEDIATE (critical security vulnerability)

### Version 2.7.35 (2026-07-02)

**CRITICAL FIX: OAuth Registration Event Emission**

Fixed critical bug where social auth users (Google, Facebook, custom OAuth) were missing billing accounts, user profiles, PII policies, onboarding steps, and welcome notifications.

**Root Cause:**
- OAuth registration bypassed `register_user_service()`
- `user.created` event never emitted for social auth users
- All event listeners skipped (billing, profile, notifications, etc.)

**Fix:**
- Extended `register_user_service()` with `auth_provider` and `provider_id` params
- OAuth routes now use `register_user_service()` for all registrations
- Ensures `user.created` event fires for both traditional and social auth

**Changes:**
- `swx_core/services/auth_service.py`: Added social auth parameters
- `swx_core/routes/access/oauth_route.py`: Use service layer for registration
- `swx_core/repositories/user_repository.py`: Type annotation fixes
- `docs/04-core-concepts/OAUTH_PROVIDERS.md`: Event emission documentation

**Impact:**
- Social auth users now receive complete account setup
- Billing accounts created
- User profiles initialized
- PII policies set up
- Onboarding steps configured
- Welcome notifications sent

**Breaking Changes:** None (backward compatible)

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