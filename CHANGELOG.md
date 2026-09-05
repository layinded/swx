# Changelog

All notable changes to this project will be documented in this file.

## [2.25.0] - 2026-09-05

### Added

- **Redis Pub/Sub event broadcasting** — New `RedisEventBridge` class
  (`swx_core.events.redis_bridge`) that extends the in-process `EventBus`
  to broadcast events across multiple worker processes via Redis Pub/Sub.
  When `REDIS_ENABLED=True` and `EVENT_BRIDGE_ENABLED=True` (the default),
  every `event_bus.dispatch()` call now:
  1. Runs local in-process listeners immediately (zero latency).
  2. Publishes the event to Redis so ALL workers receive it.

  Features:
  - Automatic activation — no code changes to existing `dispatch()` calls.
  - Loop prevention via `_broadcast_source="redis"` marker.
  - Configurable broadcast filter (`set_broadcast_filter()`) to select which
    events cross the wire.
  - Exclude prefixes (`add_exclude_prefix()`) for internal-only events.
  - Custom channel subscriptions (`subscribe()`/`unsubscribe()`) for
    SSE fan-out, WebSocket push, and notification systems.
  - Auto-reconnecting subscriber with configurable retry.
  - Health-check stats via `get_stats()`.

- **`EventBridgeServiceProvider`** — Registers `RedisEventBridge` in the IoC
  container (priority 35, after `RateLimitServiceProvider`) and patches
  `event_bus.dispatch` for transparent broadcasting.

- **`EVENT_BRIDGE_ENABLED`** setting (default: `True`) — Opt-in/opt-out
  toggle for cross-worker event broadcasting.

- **`EVENT_BRIDGE_CHANNEL_PREFIX`** setting (default: `"swx:events"`) —
  Configurable Redis channel prefix for environment isolation.

- **Lifecycle integration** — Bridge starts in `main.py` lifespan Step 12
  and stops gracefully on shutdown.

- **`docs/04-core-concepts/EVENT_BROADCASTING.md`** — Complete user guide
  covering automatic activation, filtering, custom channels, SSE integration,
  and multi-worker deployment.

### Fixed

- **pyright type error in `main.py`** — Fixed `list[asyncio.Task]` missing
  type argument to `list[asyncio.Task[None]]`.

## [2.24.0] - 2026-09-05

### Fixed

- **BaseHTTPMiddleware breaks SSE streaming** — Five middleware classes
  (`LoggingMiddleware`, `AuditMiddleware`, `RateLimitMiddleware`,
  `TenantContextMiddleware`, `MetricsMiddleware`) extended
  `starlette.middleware.base.BaseHTTPMiddleware`, which consumes the entire
  response body before forwarding it. For SSE (`text/event-stream`) responses,
  this caused indefinite buffering: connections appeared open (HTTP 200) but
  zero events reached the client. All five have been converted to pure ASGI
  middleware that intercepts `http.response.start` messages instead, preserving
  the streaming response body. The conversion follows the pattern already
  established by `SecurityHeadersMiddleware` and `CSRFMiddleware`.

- **Duplicate `set_app_info` in metrics_middleware** — Removed the duplicate
  function definition that was present in the original file.

### Changed

- `LoggingMiddleware` — Now pure ASGI. Logs on `http.response.start` instead of
  after `call_next()`. Extracts request context from `scope` instead of `Request`.
  Added `_extract_header()` and `_get_state_attr()` helpers.

- `AuditMiddleware` — Now pure ASGI. Sets `request_id` in `scope["state"]` before
  calling the app. Injects `X-Request-ID` header via `send` wrapper.

- `RateLimitMiddleware` — Now pure ASGI. Pre-request rate limit checks run from
  `scope`/headers before calling the app. Rejected requests send 429 directly via
  ASGI. Allowed requests inject `X-RateLimit-*` headers via `send` wrapper.

- `TenantContextMiddleware` — Now pure ASGI. Extracts headers from `scope["headers"]`,
  sets context variables before the app call, clears them in a `finally` block.

- `MetricsMiddleware` — Now pure ASGI. Captures status code from
  `http.response.start`. Tracks active request gauge with `inc()`/`dec()`
  around the app call. Records error metrics in exception handler.

## [2.23.5] - 2026-08-26

### Fixed

- **Sync engine async URL crash** — `_sync_database_url()` only stripped `+asyncpg`
  when `TESTING=True`. In production, `DATABASE_URL=postgresql+asyncpg://...` would
  pass the async URL to the sync engine, causing `QueuePool cannot be used with
  asyncio engine`. Added `DatabaseSettingsMixin._strip_async_drivers()` as the
  single source of truth for driver stripping; `_sync_database_url()` now delegates
  to it.

- **Duplicate endpoints in Swagger** — Auto-discovery registered both aggregated
  package routers (from `__init__.py`) and individual sub-module routers, causing
  every endpoint to appear twice. Fixed by: (1) including route packages in
  `dynamic_import()` return dict (removed `is_route_dir and is_pkg` filter),
  (2) adding `_dedup_aggregated_packages()` which identifies packages with
  `__path__` that have `router`/`websocket_router` and skips their sub-modules,
  and (3) extracting `_load_routes_dict()` helper to apply dedup consistently
  across core, versioned, and user route loading.

### Added

- **WebSocket auto-discovery** — `router_module()` now discovers `module.websocket_router`
  alongside `module.router`. Modules can expose a `websocket_router` attribute
  (an `APIRouter` with `@router.websocket(...)` handlers) and it will be
  auto-mounted with the same prefix/tag resolution as HTTP routers.

## [2.23.4] - 2026-08-26

### Fixed

- **Mixin shared-Column bug** — Mixin classes previously used `sa_column=Column(...)`
  directly in class bodies, which caused `Column object already assigned to Table 'X'`
  errors when two `table=True` models inherited the same mixin. All mixins now use
  pure `Field()` (Python-side defaults only). Factory functions (`make_id()`,
  `make_created_at()`, `make_updated_at()`, `make_is_deleted()`, `make_deleted_at()`,
  `make_created_by_id()`, `make_updated_by_id()`, `make_is_active()`, `make_slug()`,
  `make_metadata()`) are exported for models that need `server_default`, `onupdate`,
  or `index=True` Column kwargs.

- **FK name mismatch** — `wallet_adjustment.py` referenced `swx_admin_users.id` instead
  of the correct `swx_admin_user.id`. Fixed in model and migration `v2_22_8`.

### Breaking Changes (v2.23.4)

- **Mixin `sa_column=Column(...)` removed** — Models that relied on mixin-provided
  `server_default`, `onupdate`, or `index=True` must now override those fields with
  the corresponding `make_*()` factory function in their own class body. Pure
  `Field()` defaults (Python-side only) continue to work without changes.

## [2.23.3] - 2026-08-26

### Added — SWX-021: Payment Confirm-and-Apply Endpoint

- **`POST /payments/confirm`** — New endpoint for idempotent payment confirmation
  and wallet top-up. Accepts a `payment_reference`, verifies the transaction with
  the provider (Paystack/Flutterwave), and applies the payment to the user's wallet
  in a single atomic operation.

- **`payment_confirmation_service.py`** — Shared service containing:
  - `apply_payment()` — Atomic wallet top-up with transaction logging
  - `parse_reference_prefix()` — Extracts provider prefix from payment references
  - `find_user_by_email()` — Resolves user from payer email

- **Redis-based idempotency** — Prevents double-application of the same payment
  reference. Falls back to database check when Redis is unavailable.

- **Webhook refactoring** — Both Paystack and Flutterwave webhooks now use the
  shared `apply_payment()` / `parse_reference_prefix()` / `find_user_by_email()`
  functions, eliminating duplicated logic.

- **19 unit tests** — Full coverage for parse logic, payment application,
  confirm endpoint, idempotency, rollback on failure, and no-Redis fallback.

## [2.23.0] - 2026-08-25

### SOC 2 Type I Compliance — Full Implementation

This release implements all 9 code-level SOC 2 Type I trust service criteria
and includes critical bug fixes discovered during edge-case review.

#### CC6.1 — Access Management
- **API Key Lifecycle** (T-701, T-702a, T-702b): Full API key lifecycle with
  rotation (`POST /admin/api-keys/{key_id}/rotate`), expiry/inactive cleanup
  background worker, and `API_KEY_MAX_EXPIRY_DAYS` / `API_KEY_MAX_INACTIVE_DAYS`
  settings.
- **Session Management** (T-801, T-802): Concurrent session limits
  (`MAX_CONCURRENT_SESSIONS=5`), idle timeout (`SESSION_IDLE_TIMEOUT_MINUTES=60`),
  session listing/revocation endpoints (`GET/DELETE /user/sessions`), and hourly
  idle-session cleanup worker.

#### CC6.2/CC6.1 — Account Lifecycle & Access Review
- **Access Review** (T-301–T-303): Automated quarterly access review service
  with orphaned accounts, unused roles, stale tokens, and over-provisioned
  user detection.

#### CC6.5 — Data Retention & Erasure
- **Data Retention** (T-501–T-503): Retention purge scheduler, erasure
  certificate generation, and backup status verification service.

#### CC6.7 — Encryption at Rest
- **Encryption** (T-101–T-104): PII encryption at rest with key validation,
  token encryption/decryption, and fail-closed startup check.

#### CC7.1 — Vulnerability Management
- **Security Scanning** (T-901): GitHub Actions workflow for pip-audit CVE
  scanning (block on Critical/High) and Dependabot weekly updates.
- **Rate Limiting**: Password reset endpoint limited to 3 requests/hour.
- **Database SSL**: `DATABASE_SSL_MODE` setting with `_inject_ssl_mode()` URL
  helper.

#### CC7.2 — Audit Logging & SIEM
- **Tamper-Evident Audit Log** (T-201–T-203): SHA-256 hash-chained audit entries
  with `SELECT FOR UPDATE` concurrency protection, all security-relevant
  metadata fields (IP, user agent, request ID, context, data classification,
  access result) included in the canonical hash, and fail-closed startup
  verification.
- **SIEM Integration** (T-601–T-603): Batch SIEM webhook forwarding for
  critical and non-critical audit events, with bounded queue (10K max) to
  prevent memory leaks.

#### CC7.3/CC7.1 — Incident Response & Security Headers
- **Incident Response** (T-401–T-403): Incident severity classification,
  automated notification, and security response headers middleware.

### Bug Fixes (Edge-Case Review)

- **CRITICAL**: `refresh_token_service` used `scalar_one_or_none()` on queries
  that can return multiple rows (concurrent logins), causing `MultipleResultsFound`
  crashes. Replaced with `scalars().first()` + `order_by(created_at.desc())`.
- **CRITICAL**: Audit-integrity startup check ran before database migrations,
  causing `OperationalError` on fresh non-Dockerized installs. Moved check
  to after `setup_database()`. Also widened exception handling from
  `RuntimeError` only to `Exception`.
- **MEDIUM**: `backup_status_service.get_backup_status` did not guard
  `response.json()` — a non-JSON 200 response raised uncaught
  `JSONDecodeError`. Added `try/except (ValueError, TypeError)`.
- **MEDIUM**: Background cleanup tasks started with `asyncio.create_task()`
  but handles discarded — no cancellation on shutdown. Now tracked in
  `_bg_tasks` and cancelled during teardown.
- **MEDIUM**: Hardcoded cleanup intervals (86400s, 3600s) replaced with
  configurable settings `API_KEY_LIFECYCLE_INTERVAL_SECONDS` and
  `SESSION_IDLE_CLEANUP_INTERVAL_SECONDS`.
- **MEDIUM**: `main.py` startup had duplicate `except RuntimeError` and
  `except Exception` blocks with identical bodies. Consolidated to single
  `except Exception`.
- **MEDIUM**: SIEM `enqueue_siem_event`/`forward_to_siem`/`flush_siem_batch`
  had unused `session` parameter. Removed to clean up the API.
- **MEDIUM**: SIEM `_batch_queue` was unbounded — could grow without limit
  under sustained failure. Added `maxlen=10_000` cap (oldest entries dropped).
- **MEDIUM**: `_audit_revoked_keys` used `API_KEY_EXPIRED` for both expired
  and inactive-revoked keys. Added `API_KEY_INACTIVE_REVOKED` action.
- **MEDIUM**: `revoke_all_tokens` (password reset) had no audit event. Now
  emits `AUTH_SESSION_REVOKED` with context.
- **MEDIUM**: `revoke_refresh_token` (logout) had no audit event. Now emits
  `AUTH_LOGOUT`.
- **MEDIUM**: `find_idle_sessions` excluded sessions with `NULL`
  `last_activity_at`. Changed to treat `NULL` as idle-eligible (old sessions
  without activity tracking are now correctly expired).
- **MEDIUM**: Hash-chain `compute_log_hash` excluded IP, user agent, request
  ID, context, data classification, and access result from the canonical
  hash, allowing undetected metadata tampering. All fields now included.
- **MEDIUM**: Hash-chain `persist_log_hash` had a TOCTOU race under concurrent
  writes (two entries could read the same predecessor). Fixed with
  `SELECT FOR UPDATE (skip_locked)` to serialize hash computation.
- **MEDIUM**: `audit_logger.log_event` committed the entry before computing
  its hash — if hash computation failed, the entry had `log_hash=None`,
  breaking fail-closed integrity. Now removes unhashed entries on hash failure.
- **MEDIUM**: `create_api_key` in repository had no `IntegrityError` handling
  for duplicate `hashed_key`. Added rollback + re-raise for clean 409 mapping.
- **LOW**: `api_key_guard.validate_token` was a stub returning `valid: True`
  unconditionally. Now delegates to `validate_api_key` service.
- **LOW**: `session_timeout.py` had unused `from uuid import UUID` import.

### Architecture (SWX Pattern)

- **`refresh_token_service.py`**: Extracted `RefreshTokenRepository` following
  the SWX Controller → Service → Repository pattern. All direct
  `session.add/commit/execute/delete` calls replaced with repository functions.
- **SIEM service**: Removed `AsyncSession` parameter from `forward_to_siem`,
  `enqueue_siem_event`, and `flush_siem_batch` (no DB operations needed).

### Code Clarity
- Removed redundant audience re-check in `verify_mfa_token` (already enforced
  by `jwt.decode` with `audience=` parameter).
- Fixed `revoke_refresh_token` fallback path that silently returned `True`
  without deleting when encryption-at-rest is enabled.

### Changed Files

- `swx_core/security/refresh_token_service.py` — scalar_one_or_none fix,
  repository extraction, audit events, fallback fix, redundant aud check removal
- `swx_core/repositories/refresh_token_repository.py` — NEW: SWX-pattern
  repository for refresh token DB operations
- `swx_core/main.py` — startup reordering, duplicate except consolidation,
  background task tracking, configurable intervals
- `swx_core/services/compliance/backup_status_service.py` — JSON parse guard
- `swx_core/services/compliance/siem_service.py` — removed session param,
  bounded queue, no async_session in batch loop
- `swx_core/services/compliance/audit_integrity_service.py` — metadata fields
  in hash, SELECT FOR UPDATE, import cleanup
- `swx_core/repositories/audit_integrity_repository.py` —
  get_previous_hash_for_update with row lock
- `swx_core/services/audit_logger.py` — hash failure recovery (remove unhashed
  entries), SIEM call signature update
- `swx_core/services/compliance/api_key_lifecycle_service.py` — configurable
  interval, API_KEY_INACTIVE_REVOKED action
- `swx_core/services/auth/session_service.py` — configurable interval
- `swx_core/repositories/session_repository.py` — NULL idle activity handling
- `swx_core/repositories/api_key_scope_repository.py` — IntegrityError handling
- `swx_core/config/settings_compliance.py` — new interval settings
- `swx_core/auth/user/session_timeout.py` — removed unused import
- `swx_core/guards/api_key_guard.py` — validate_token delegates to service
- `swx_core/version.py` — 2.23.0
- `pyproject.toml` — 2.23.0

## [2.22.10] - 2026-08-24

### Fixed — SWX-023: Circular import broke entire `/api/auth/*` surface

Two circular-import chains prevented the auth module from loading at
application startup, making login (and every auth-dependent endpoint)
return 500:

1. `swx_core.security.password_security` → `swx_core.auth.core.jwt`
   → `swx_core.auth.user` → `swx_core.repositories.user_repository`
   → back to `password_security`

2. `swx_core.security.refresh_token_service` → `swx_core.auth.core.jwt`
   → `swx_core.auth.__init__` → `swx_core.auth.user.dependencies`
   → back to `refresh_token_service`

**Fix**: Replace top-level `from swx_core.auth.core.jwt import …` in
both `password_security.py` and `refresh_token_service.py` with lazy
imports inside the functions that use those symbols. This breaks the
cycle at module-load time while keeping the public API identical —
all symbols remain available via `from swx_core.security import …`.

Also fixed `AsyncAdaptedQueuePool` import in `db.py` (moved from
`sqlalchemy.ext.asyncio`, where it does not exist, to the correct
`sqlalchemy.pool`).

### Changed Files

- `swx_core/security/password_security.py` — lazy-import `create_token`, `decode_token`, `TokenAudience` inside `generate_password_reset_token()` and `verify_password_reset_token()`
- `swx_core/security/refresh_token_service.py` — lazy-import `create_token`, `TokenAudience` inside `create_access_token()`, `create_mfa_token()`, and `verify_mfa_token()`
- `swx_core/database/db.py` — `AsyncAdaptedQueuePool` import from `sqlalchemy.pool`
- `swx_core/version.py` — patch bump 6 → 10
- `pyproject.toml` — version 2.22.10

## [2.22.9] - 2026-08-24

### Fixed — SWX-022: Webhook paid-plan fulfilment broken by allow_paid gate

v2.22.8 (SWX-015) added `allow_paid: bool = False` to
`SubscriptionService.create_subscription()` to prevent users from
directly activating paid plans. This was correct, but both the
Paystack and Flutterwave webhooks call `create_subscription()`
without `allow_paid=True`, causing every legitimate paid-plan purchase
to raise HTTP 402 — which the webhook's catch-all `except` block
swallows and returns `{"status": "success", "message": "Processing failed"}`
to the payment provider (HTTP 200), preventing retries.

The user pays, the plan never activates, and the error is only visible
in application logs.

**Fix**: Pass `allow_paid=True` in both `paystack_webhook.py` and
`flutterwave_webhook.py` — these are verified payment flows that the
parameter's own docstring explicitly describes as the intended callers.

### Changed Files

- `swx_core/webhooks/paystack_webhook.py` — `allow_paid=True`
- `swx_core/webhooks/flutterwave_webhook.py` — `allow_paid=True`
- `pyproject.toml` — version bumped to 2.22.9

## [2.22.8] - 2026-08-24

### Security — GDPR Lifecycle Hardening & Code-Quality Audit

Post-implementation audit of the GDPR right-to-erasure pipeline. Five bugs
found and fixed; no remaining known issues.

#### Bug: Refresh tokens not deleted after user anonymization

`execute_erasure()` read `user.email` after calling `anonymize_user()`, which
overwrites the email to `erased_{id}@erased.invalid`. The refresh-token table
filters by `user_email`, so tokens were never found and never deleted. Fixed
by capturing email before anonymization via a new `get_user_email()` repository
function (CSR-compliant).

#### Bug: Conversation messages deleted after parent conversations

`delete_user_related_data()` listed `swx_conversations` in its hard-delete spec
before deleting conversation messages. Since messages have a foreign key to
conversations, the parent rows were deleted first, making the message deletion
a no-op. Fixed by moving conversation-message deletion to the front of the
batch (Step 1), before all other hard-deletes (Step 2).

#### Bug: N+1 queries in sole-owner guard

`find_sole_owned_organizations()` and `find_sole_owned_teams()` issued one
COUNT query per org/team — classic N+1. Rewritten as correlated scalar
subqueries (`SELECT ... WHERE member_count <= 1`) so each check is a single
SQL statement.

#### Bug: 27+ individual commits per erasure

`_delete_rows_by_column()` and `_anonymize_column_by_user_id()` each committed
independently, meaning one erasure operation produced 27+ database commits.
Refactored to batch all deletes/anonymizes into a single `session.commit()` at
the end of `delete_user_related_data()`. Conversation messages are included in
the same batch.

#### Bug: Unauthorized access to erasure certificates

`GET /user/gdpr/erasure-certificates/{certificate_id}` was missing the
`current_user: UserDep` dependency, allowing any authenticated user to view any
certificate by UUID. Added authentication dependency.

#### Fix: Audit log export incomplete

`gdpr_export_repository.get_user_audit_logs()` only queried by `actor_id`.
The erasure policy anonymizes both `actor_id` and `resource_id`. Added `OR`
condition so audit logs where the user is the `resource_id` are also exported.

#### Fix: Unprotected conversations export

The conversations section in `export_user_data_zip()` was not wrapped in
try/except, so a single table failure would crash the entire ZIP export.
Added error handling consistent with the other sections.

### Changed Files

- `swx_core/repositories/erasure_repository.py` — N+1→subquery, batch commit,
  FK-safe delete order, `get_user_email()`, `_anonymize_audit_logs()` (private)
- `swx_core/services/compliance/erasure_service.py` — email captured before
  anonymization via `get_user_email()`
- `swx_core/services/data_transfer/gdpr_service.py` — conversations wrapped
  in try/except
- `swx_core/repositories/gdpr_export_repository.py` — audit logs query both
  actor_id and resource_id
- `swx_core/routes/user/gdpr_route.py` — auth dependency on certificate endpoint
- `swx_core/security/__init__.py` — lazy imports to break circular dependency
- `tests/services/compliance/test_erasure_service.py` — updated for
  `get_user_email` mock
- `pyproject.toml` — version bumped to 2.22.8

## [2.22.7] - 2026-08-24

### Security — Phase 0 P0 Hardening

Six critical security fixes addressing authentication, authorization, and
billing integrity vulnerabilities identified in the v2.22.6 platform audit.

#### T-001: Remove user-facing wallet credit/debit/transfer/convert routes

Removed `POST /wallet/credit`, `POST /wallet/debit`, `POST /wallet/transfer`,
and `POST /wallet/convert` from `billing_route.py`. These endpoints allowed
any authenticated user to arbitrarily credit their own wallet. Wallet
mutations are now only available to internal services and webhook handlers.
Also added `UserDep` authentication to `/payments/verify`.

#### T-002: Gate subscription creation to free plans only

Added `allow_paid: bool = False` parameter to `SubscriptionService.create_subscription()`.
By default, paid-plan subscriptions are rejected with 402. Internal callers
(webhook handlers) must explicitly pass `allow_paid=True`. Plan lookup now
uses `billing_repository.get_plan_by_key()` (CSR-compliant).

#### T-003: Add token blacklist check to primary auth path

Added `_get_token_blacklist()` helper in `dependencies.py` that checks the
JTI against the blacklist table after JWT decode. Replaced raw `select(User)`
with `get_user_by_email()` from `user_repository` (CSR-compliant). Removed
unused `sqlmodel` import.

#### T-004: Add is_active checks to social login and refresh token

`login_social_user_service()` and `refresh_access_token_service()` now raise
HTTP 400 for inactive or anonymous users. Prevents disabled accounts from
obtaining valid access tokens.

#### T-005: Fix organization IDOR — add membership check

Added optional `user_id` parameter to `organization_service.get_organization()`.
When `user_id` is provided, `_require_member()` is called as defense-in-depth,
verifying the user belongs to the organization before returning data.

#### T-006: Make wallet operations atomic (single transaction)

Fixed a two-commit race condition in wallet credit/debit operations where
the ledger entry was committed separately from the balance update, allowing
concurrent requests to read stale balances (double-spend risk).

- Added `auto_commit=False` parameter to `ledger_service.credit()` and
  `ledger_service.debit()`, allowing callers to control transaction boundaries
- Added `wallet_repository.update_balance_no_commit()` (flush without commit)
- Added `wallet_repository.get_by_account_currency_for_update()` (SELECT … FOR
  UPDATE) for row-level locking during debit operations
- Rewrote `credit_wallet()` and `debit_wallet()` to use single `session.commit()`
- `transfer()` now debits + credits in one atomic transaction instead of two
  separate commits
- Fixed bug in `resolve_wallet_for_charge()` where `None` currency could be
  passed to `_wallet_entity()` instead of resolved `charge_currency`
- Removed dead code (`atomic_debit_no_commit` had pyright errors and no callers)
- Refactored subscription_service.py for CSR compliance: all direct queries
  moved to `billing_repository` (5 new repo functions added)

### Phase 1 — P1 Hardening (Partial)

#### T-016: Add billing audit logging

Added `AuditLogger.log_event()` calls to all wallet and subscription mutations,
creating an immutable audit trail for SOC 2 compliance. Every financial
operation now records actor type, actor ID, resource type, resource ID, and
structured context (amount, currency, reference).

- `wallet_service.py`: audit entries for credit, debit, transfer, convert
  (`wallet.credit`, `wallet.debit`, `wallet.transfer`). Actor defaults to
  `SYSTEM`; callers pass `actor_type=ActorType.USER, actor_id=str(user_id)`.
- `subscription_service.py`: audit entries for create, cancel, Stripe sync,
  grace enter/renewal/expire (`subscription.create`, `subscription.cancel`,
  `subscription.sync_stripe`, `subscription.create_stripe`,
  `subscription.grace_entered`, `subscription.renewal_succeeded`,
  `subscription.grace_expired`). User-initiated actions use `ActorType.USER`;
  webhook/system actions use `ActorType.SYSTEM`.

#### T-017: Add plan_key and plan_name to SubscriptionPublic

`SubscriptionPublic` now includes `plan_key: str` and `plan_name: Optional[str]`,
populated from the associated `Plan` via `billing_repository.get_plan_by_id()`.
API consumers can now determine the user's current plan without custom joins.

#### T-018: Add UserDep to /payments/verify (completed in T-001)

Already implemented during T-001 when vulnerable wallet routes were removed.

#### T-012: Add GDPR User columns + migration

Added `deactivated_at` (DateTime tz, nullable), `gdpr_deleted_at` (DateTime tz, nullable),
and `anonymous` (Boolean, NOT NULL, server_default=false) columns to `swx_users`.
Migration backfills `is_active = TRUE` where NULL and `anonymous = FALSE` where NULL.
These columns enable future GDPR erasure, deactivation tracking, and anonymous-user gating.

### Changed Files (Phase 1)

- `swx_core/services/billing/wallet_service.py` — audit logging + actor params
- `swx_core/services/billing/subscription_service.py` — audit logging
- `swx_core/models/billing.py` — SubscriptionPublic: added plan_id, plan_key, plan_name
- `swx_core/controllers/subscription_controller.py` — enriched with plan lookup
- `swx_core/models/user.py` — added deactivated_at, gdpr_deleted_at, anonymous columns
- `swx_core/database/migrations/v2_22_9_add_gdpr_user_columns.py` — Alembic migration

#### T-013: Add GDPR configuration settings

Added `GDPR_ENABLED`, `GDPR_DELETION_GRACE_DAYS`, `GDPR_EXPORT_FORMAT`,
`GDPR_ANONYMIZE_ON_DELETE`, `GDPR_SOLE_OWNER_BLOCK`, `GDPR_EXPORT_EXPIRY_DAYS`,
and `GDPR_MIN_VERIFICATION_DAYS` to `settings.py` as module-level constants
following the existing `COMPLIANCE_*` pattern. All have safe defaults and are
non-breaking.

#### T-014: Register compliance job handlers

Added `compliance_data_subject_delete_handler` and
`compliance_retention_apply_handler` to `handlers.py`, delegating to
`data_subject_service.process_data_subject_request()` and
`retention_service.apply_retention()` respectively. Added
`compliance_data_subject_delete` and `compliance_retention_apply` to the
`JobType` enum. Registered both handlers in `main.py` startup. DSR deletion
and retention jobs now execute when enqueued instead of silently failing.

#### T-032: Reduce access token lifetime to 15 minutes

Changed `ACCESS_TOKEN_EXPIRE_MINUTES` default from 10,080 (7 days) to 15
minutes across all fallback locations: `settings.py`,
`settings_service.py`, `auth_provider.py`, and `jwt_guard.py`. Refresh tokens
remain at 30 days. This aligns with industry best practices and complements
the token blacklist added in T-003.

### Changed Files

- `swx_core/routes/user/billing_route.py`
- `swx_core/services/billing/subscription_service.py`
- `swx_core/controllers/subscription_controller.py`
- `swx_core/auth/user/dependencies.py`
- `swx_core/services/auth_service.py`
- `swx_core/services/organization_service.py`
- `swx_core/repositories/billing_repository.py`
- `swx_core/services/billing/wallet_service.py`
- `swx_core/services/ledger_service.py`
- `swx_core/repositories/wallet_repository.py`
- `swx_core/config/settings.py` — T-013: GDPR settings, T-032: access token lifetime
- `swx_core/services/settings_service.py` — T-032: access token lifetime default
- `swx_core/providers/auth_provider.py` — T-032: access token fallback
- `swx_core/guards/jwt_guard.py` — T-032: access token fallback
- `swx_core/models/job.py` — T-014: compliance job types
- `swx_core/services/job/handlers.py` — T-014: compliance job handlers
- `swx_core/main.py` — T-014: handler registration, T-015: webhook bridge registration

#### T-007: Multi-Tenancy ADR

Architecture Decision Record for shared-database, tenant-column isolation.
Defines `BaseRepository.tenant_aware` flag, `TenantContextMiddleware` activation,
and the tenant data model. Located at `.omo/adr/multi-tenancy-architecture.md`.

#### T-008: Payment Convergence ADR

Architecture Decision Record for a unified `PaymentService.apply_payment()`
entry point. All payment confirmations (Stripe, Paystack, Flutterwave, M-Pesa)
go through one validated, idempotent path. Located at
`.omo/adr/payment-convergence-architecture.md`.

#### T-009: Domain Event Architecture ADR

Architecture Decision Record formalizing the event bus. Defines typed event
payloads, namespace convention (`billing.*`, `compliance.*`, `auth.*`),
webhook bridge (wildcard listener), and PII scrubbing. Located at
`.omo/adr/domain-event-architecture.md`.

#### T-010: MFA Architecture ADR

Architecture Decision Record for TOTP-based MFA with recovery codes and
step-up authentication. TOTP as primary; WebAuthn deferred to future phase.
Located at `.omo/adr/mfa-architecture.md`.

#### T-015: Wire webhook dispatcher to event bus

Added `WebhookBridgeListener` in `swx_core/events/listeners/webhook_bridge_listener.py`.
Bridges all domain events (except `webhook.*`) to outbound webhook delivery via
`webhook_dispatcher.dispatch_event()`. Includes PII scrubbing: removes passwords,
tokens, and secrets; masks email, IP, and phone fields. Registered as a wildcard
listener at `EventPriority.LOWEST` in `main.py` startup (step 5).

- `swx_core/events/listeners/webhook_bridge_listener.py` — new: webhook bridge + PII scrubbing
- `swx_core/events/listeners/__init__.py` — unchanged (auto-discovery loads it)
- `swx_core/main.py` — step 5: register webhook bridge

#### T-011: Register TenantContextMiddleware

Added `apply_middleware(app)` function to `tenant_middleware.py` so the dynamic
middleware loader registers it. The middleware reads `X-Tenant-ID` and `X-Team-ID`
headers and falls back to `user.tenant_id` / `user.current_team_id`. It is
gated by `ORGANIZATION_ENABLED` (skips registration when organization is disabled).
Closes SWX-019 (tenant middleware was dead code).

- `swx_core/middleware/tenant_middleware.py` — added `apply_middleware()`

#### T-026: TOTP MFA Service

Implemented TOTP-based multi-factor authentication per ADR-010. Added `mfa_enabled`,
`mfa_secret` (encrypted), and `mfa_verified_at` columns to `swx_users`. Created
`swx_mfa_recovery_codes` table for single-use recovery codes (bcrypt-hashed).

New files:
- `swx_core/models/mfa.py` — `MfaRecoveryCode` model + request/response schemas
- `swx_core/repositories/mfa_repository.py` — CRUD for MFA status and recovery codes
- `swx_core/services/auth/mfa_service.py` — TOTP enrollment, verification,
  recovery, and disable flows. Encrypts TOTP secrets with `EncryptionService`.
  Emits events: `mfa.enrollment_initiated`, `mfa.enrollment_verified`,
  `mfa.disabled`, `mfa.recovery_code_used`, `mfa.recovery_codes_regenerated`.
- `swx_core/database/migrations/v2_22_10_add_mfa_columns.py` — Alembic migration
  (nullable-first with server defaults, backfill, then NOT NULL constraint)

Dependencies added: `pyotp>=2.9.0`, `qrcode[pil]>=7.4`

#### T-028: MFA Verification in Login Flow

Modified the login flow to gate MFA-enabled users. When `user.mfa_enabled` is
true, `POST /auth/` now returns `LoginResponse(mfa_required=True, mfa_token=...)`
instead of full tokens. A new `POST /auth/mfa/verify` endpoint exchanges the
short-lived MFA challenge token + TOTP/recovery code for real tokens.

New/changed:
- `swx_core/auth/core/jwt.py` — added `TokenAudience.MFA`
- `swx_core/security/refresh_token_service.py` — added `create_mfa_token()`,
  `verify_mfa_token()` (short-lived JWT with audience="mfa")
- `swx_core/models/token.py` — added `LoginResponse` schema (mfa_required,
  mfa_token, access_token, refresh_token)
- `swx_core/services/auth_service.py` — `login_user_service()` now returns
  `LoginResponse`; branches on `user.mfa_enabled`. Added
  `verify_mfa_challenge_service()`.
- `swx_core/controllers/auth_controller.py` — added
  `verify_mfa_challenge_controller()`
- `swx_core/routes/access/mfa_route.py` — new: `POST /auth/mfa/verify`
- `swx_core/routes/user/mfa_route.py` — new: `POST /user/mfa/enroll`,
  `POST /user/mfa/verify-enrollment`, `GET /user/mfa/status`,
  `POST /user/mfa/disable`, `POST /user/mfa/recovery-codes/regenerate`
- `swx_core/routes/access/auth_route.py` — login returns `LoginResponse`;
  `cookie_login()` handles MFA-pending branch
- `swx_core/config/settings.py` — added `MFA_CHALLENGE_EXPIRE_MINUTES=5`

#### T-029: Step-Up Authentication

Added `require_recent_mfa` dependency (aliased as `RecentMfaDep`) that validates
a short-lived `X-Step-Up-Token` header for sensitive operations. Users call
`POST /auth/mfa/step-up` with a TOTP code to obtain the token, then pass it
on subsequent requests to operations like password change and account deletion.

New/changed:
- `swx_core/auth/user/dependencies.py` — added `StepUpTokenHeader`,
  `require_recent_mfa()`, `RecentMfaDep` type alias
- `swx_core/services/auth/mfa_service.py` — added `step_up()` function
- `swx_core/controllers/auth_controller.py` — added `step_up_mfa_controller()`
- `swx_core/routes/access/mfa_route.py` — added `POST /auth/mfa/step-up`
- `swx_core/routes/user/user_route.py` — `update_password` and
  `delete_user_me` now require `RecentMfaDep` (step-up auth)
- `swx_core/models/mfa.py` — added `MfaStepUpRequest`, `MfaStepUpResponse`

#### T-031: Email Verification Flow

Added email verification for local-auth registrations. Social auth users
(Google, Facebook) are auto-verified since their provider confirms email
ownership. When `EMAIL_VERIFICATION_ENABLED=True` (default), local users
must click the verification link before their email is considered verified.
When `False`, all local users are auto-verified on registration.

New/changed:
- `swx_core/models/user.py` — added `email_verified_at` column
- `swx_core/database/migrations/v2_22_11_add_email_verified_at.py` — Alembic
  migration
- `swx_core/config/settings.py` — added `EMAIL_VERIFICATION_ENABLED=True`,
  `EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=24`
- `swx_core/services/auth/email_verification_service.py` — new: token generation,
  verification, request, resend. `auto_verify_if_disabled()` and
  `mark_social_user_verified()` helpers
- `swx_core/services/auth_service.py` — `register_user_service()` now calls
  `auto_verify_if_disabled()` or `mark_social_user_verified()` after creation
- `swx_core/controllers/auth_controller.py` — added
  `request_email_verification_controller`, `verify_email_controller`,
  `resend_email_verification_controller`
- `swx_core/routes/access/auth_route.py` — added
  `POST /auth/email/verify/{email}`, `POST /auth/email/verify`,
  `POST /auth/email/resend-verification`
- `swx_core/email/email_service.py` — added `generate_verify_email()`
- `swx_core/email/templates/build/verify_email.html` — new: verification
  email template

#### T-030: Account Linking (Social Auth)

Added a `SocialAccount` model for linking multiple OAuth providers to a single
user. When a social login email matches an existing local account, the accounts
are linked (after email verification gate). New social users get an auto-created
account with `email_verified_at` set (providers verify email ownership).

Users can view, link, and unlink providers via `/user/accounts/` endpoints.
Unlinking is blocked if it would leave the user with no authentication method.

New/changed:
- `swx_core/models/social_account.py` — `SocialAccount` model + request/response
  schemas
- `swx_core/database/migrations/v2_22_12_add_social_accounts.py` — Alembic
  migration (unique constraint on provider+provider_id)
- `swx_core/repositories/social_account_repository.py` — CRUD for social accounts
- `swx_core/services/auth/account_linking_service.py` — `link_social_account`,
  `unlink_social_account`, `find_or_create_user_from_social`
- `swx_core/routes/user/account_linking_route.py` — `GET /user/accounts/linked`,
  `DELETE /user/accounts/unlink`
- `swx_core/config/settings.py` — added `SOCIAL_ACCOUNT_LINKING_ENABLED=True`

#### Post-implementation audit: event emissions + code-clarity

All state-changing operations across Phase 3 now emit events via `event_bus`.
Fixed 7 missing event emissions, normalized API inconsistency, removed unused
imports, fixed a security bug, and registered missing routes.

- `auth_service.py` — added `user.login`, `user.login.mfa_required`,
  `mfa.challenge_verified`, `user.logout`, `user.password_reset` events;
  normalized `emit(Event(...))` → `dispatch("event", payload={...})`
- `email_verification_service.py` — added `email.verified` to
  `auto_verify_if_disabled()` and `mark_social_user_verified()`
- `social_account_repository.py` — fixed `has_local_password()` bug:
  removed incorrect `auth_provider == "local"` check (would reject users who
  set a password after social auth signup)
- `models/social_account.py` — removed unused `Optional`, `Boolean`, `text`
  imports
- `models/mfa.py` — removed unused `Boolean`, `String`, `text` imports;
  added `# pyright: ignore[reportAssignmentType]` suppressor on `__tablename__`
- `services/auth/account_linking_service.py` — removed unused `Request` import
- `routes/access/__init__.py` — registered `mfa_route` (was missing)
- `routes/user/__init__.py` — registered `mfa_route` and
  `account_linking_route` (were missing)

#### T-033: ErasureService + ErasureCertificate

Added a proper GDPR right-to-erasure implementation with per-table erasure
policies, anonymization support, and cryptographic erasure certificates for
compliance proof. Replaced the naive `gdpr_service.execute_hard_deletion()`
(which just deleted the User row) with a proper ErasureService that:

1. Sets `deactivated_at` + `gdpr_deleted_at` on the User (T-012 columns)
2. When `GDPR_ANONYMIZE_ON_DELETE=True` (default), anonymizes PII instead of
   hard-deleting — sets email to `erased_{id}@erased.invalid`, clears password,
   sets `anonymous=True`
3. Creates an `ErasureCertificate` record documenting which tables were affected
   and the erasure type, providing compliance proof
4. Bridges the DSR system (`data_subject_service`) to the erasure system via
   `process_erasure_for_request()` — the T-014 handler now calls this instead
   of just marking the request completed
5. The `gdpr_service.request_deletion()` and `cancel_deletion()` now delegate
   to `erasure_service.request_erasure()` and `cancel_erasure()`, which properly
   set `gdpr_deleted_at` and `deactivated_at`

New/changed:
- `swx_core/models/erasure_certificate.py` — `ErasureCertificate` model +
  create/public schemas
- `swx_core/database/migrations/v2_22_13_add_erasure_certificates.py` — Alembic
  migration
- `swx_core/repositories/erasure_repository.py` — certificate CRUD, user
  anonymization, deletion marking, cancellation
- `swx_core/services/compliance/erasure_service.py` — `request_erasure`,
  `execute_erasure`, `cancel_erasure`, `get_erasure_certificate`,
  `list_erasure_certificates`, `process_erasure_for_request`
- `swx_core/services/data_transfer/gdpr_service.py` — refactored to delegate
  to erasure_service; removed `execute_hard_deletion()`
- `swx_core/services/job/handlers.py` — `compliance_data_subject_delete_handler`
  now calls `process_erasure_for_request()` instead of just marking completed
- `swx_core/controllers/gdpr_controller.py` — added certificate controller
  functions
- `swx_core/routes/user/gdpr_route.py` — added
  `GET /user/gdpr/erasure-certificates`,
  `GET /user/gdpr/erasure-certificates/{certificate_id}`
- `swx_core/config/settings.py` — T-013 GDPR settings now wired into
  erasure flow (grace days, anonymize-on-delete, etc.)

#### T-034: GDPR data export service (Article 20)

Added `GdprExportRepository` with 20 user-data fetch functions and rewrote
`GdprService.export_user_data_zip()` to collect all GDPR-relevant data into a
structured ZIP archive. Conversations are handled separately with a secondary
fetch for messages by conversation IDs.

- `swx_core/repositories/gdpr_export_repository.py` — 20 async fetch functions
  for all user data tables (social accounts, consents, notifications, API keys,
  devices, exports, imports, roles, team/org memberships, referrals, onboarding,
  flag evaluations, audit logs, conversations, conversation messages)
- `swx_core/services/data_transfer/gdpr_service.py` — full GDPR ZIP export with
  `_model_to_dict` / `_models_to_dicts` helpers, per-section error handling,
  and `gdpr.export_completed` event dispatch

#### T-035: GDPR controller + routes

Verified all GDPR endpoints wired correctly:
- `GET /user/gdpr/export` → `export_user_data`
- `POST /user/gdpr/request-deletion` → `request_deletion`
- `POST /user/gdpr/cancel-deletion` → `cancel_deletion`
- `GET /user/gdpr/erasure-certificates` → `list_certificates`
- `GET /user/gdpr/erasure-certificates/{id}` → `get_certificate`

#### T-036: Per-table erasure policy

Implemented per-table erasure policy with 23 hard-delete tables and 4 anonymize
tables, plus audit log anonymization. `erasure_repository.delete_user_related_data()`
now iterates all tables, applying the correct policy per table:
- **Hard delete** (23 tables): social_accounts, devices, api_keys,
  webhook_endpoints, conversation_messages, conversations, flag_evaluations,
  notifications, notification_preferences, onboarding_steps, org_memberships,
  referral_codes, referral_events, sso_sessions, team_members, user_consents,
  user_roles, data_exports, data_imports, user_sessions, password_reset_tokens,
  user_contacts, feature_usage
- **Anonymize** (4 tables): audit_logs (user_id → erased_{id}),
  user_notes (content wiped), feedback_entries (content wiped),
  search_history (query wiped)

#### T-037: Sole-owner guard for GDPR erasure

Added `_check_sole_owner()` to `erasure_service.py` that queries for
organizations and teams where the user is the sole owner (owner_id == user_id
AND member count ≤ 1). Both `request_erasure()` and `execute_erasure()` now
check sole ownership before proceeding:
- `request_erasure()` raises HTTP 409 with descriptive detail listing the
  org/team names if the user is a sole owner
- `execute_erasure()` returns `{"status": "blocked", "reason": ...}` if the
  user is a sole owner, preventing irreversible data loss
- `erasure_repository.py`: added `find_sole_owned_organizations()` and
  `find_sole_owned_teams()` queries

#### T-038: Auth cache invalidation + token revocation on erasure

Added `_revoke_auth_session()` to `erasure_service.py` that revokes all active
tokens and invalidates the auth cache for a user being erased. Called during
both `request_erasure()` (immediate deactivation) and `execute_erasure()`
(final deletion). This prevents erased users from continuing to use valid
tokens during the grace period or after deletion.

- `swx_core/security/__init__.py` — converted to lazy `__getattr__` imports to
  break circular dependency (`password_security` → `auth.core.jwt` →
  `user_repository` → `password_security`)

### Changed Files (GDPR Lifecycle)

- `swx_core/repositories/erasure_repository.py` — sole-owner queries, per-table
  erasure policy
- `swx_core/repositories/gdpr_export_repository.py` — 20 user-data fetch
  functions
- `swx_core/services/compliance/erasure_service.py` — sole-owner guard,
  `_revoke_auth_session()`, per-table erasure orchestration
- `swx_core/services/data_transfer/gdpr_service.py` — full ZIP export, lazy
  erasure imports, `_models_to_dicts` with Sequence type
- `swx_core/security/__init__.py` — lazy imports to break circular dependency
- `tests/services/compliance/test_erasure_service.py` — 16 tests
- `tests/services/data_transfer/test_gdpr_service.py` — 17 tests

---

## [2.22.6] - 2026-08-23

### Fixed — SWX-011: Paystack/Flutterwave webhook doesn't assign plans

Both webhook handlers treated all payments identically (wallet credit only).
Plan payments (`plan-{key}-{uuid}` reference prefix) never created a
subscription, so users stayed on the old plan after paying for an upgrade.

**Fix:** Added `_parse_reference_prefix()` to both handlers. References with
`plan-` prefix now call `SubscriptionService.create_subscription()`.
References with `pack-` prefix (or unrecognized) fall through to wallet credit.

Edge case fixed: keys containing hyphens (e.g. `plan-pro-v1-{uuid}`) are
parsed correctly — the UUID is the last segment, the key is everything between
the prefix and the UUID.

### Fixed — SWX-012: Settings ${ENV_VAR} placeholder not resolved when env var is unset

When `PAYSTACK_WEBHOOK_SECRET` (or `FLUTTERWAVE_WEBHOOK_SECRET`) env var was
not set, pydantic-settings returned the literal string `"${PAYSTACK_WEBHOOK_SECRET}"`
(truthy), so the `or` fallback to `PAYSTACK_SECRET_KEY` never fired.

**Fix:** Replaced `secret = settings.X or settings.Y` with
`_resolve_webhook_secret()` helper that checks `startswith("${")` on each
candidate before falling through. Returns `None` only when both are
placeholders or empty.

### Fixed — SWX-013: /quota/status uses hardcoded default instead of plan entitlement

`GET /quota/status` returned `monthly_quota` from
`settings.QUOTA_MONTHLY_DEFAULT_TOKENS` (1M) regardless of the user's plan.

**Fix:** Added `billing_service.get_plan_monthly_quota()` which uses
`EntitlementResolver.get_entitlement()` to look up `ai.tokens_per_month`
from the user's active subscription's plan. Falls back to the settings
default when no subscription or entitlement exists.

### Tests Added

- `TestReferencePrefixParsing` (14 tests) — plan/pack prefix routing, hyphen-in-key edge case, unrecognized references
- `TestWebhookSecretResolution` (7 tests) — placeholder fallback, both-placeholder, empty-string edge cases

---

## [2.22.5] - 2026-08-23

### Fixed — Paystack reference format bug (v2.22.4 regression)

Payment initialization references used colons (`plan:pro_v1:a1b2c3d4`) which
Paystack rejects. All references now use hyphens (`plan-pro_v1-a1b2c3d4`).

Affected files:
- `billing_controller._call_provider_with_amount` — `f"{prefix}:{item_key}:{uuid4().hex}"` → `f"{prefix}-{item_key}-{uuid4().hex}"`
- `usage_metering_service.record_and_charge` — `f"usage:{request_id}"` → `f"usage-{request_id}-{charge_key}"`
- `wallet_service.credit_wallet_internal` — `f"internal:{uuid4().hex}"` → `f"internal-{key}"`
- `wallet_adjustment_service._execute` — `f"adjustment:{request.id}"` → `f"adjustment-{request.id}"`

### Fixed — Removed all hardcoded values

All hardcoded currency strings, TTL values, and pricing tables now read
from `settings.py`:

| Setting | Default | Replaces |
|---------|---------|----------|
| `USAGE_METERING_DEFAULT_CURRENCY` | `"NGN"` | Hardcoded `"NGN"` in `record_and_charge` |
| `USAGE_METERING_DEFAULT_MODEL_KEY` | `"default"` | Hardcoded fallback key |
| `USAGE_METERING_MODEL_PRICING` | 7-model dict | Hardcoded `MODEL_PRICING_NANO` module constant |
| `QUOTA_MONTHLY_TTL_DAYS` | `32` | Hardcoded `32 * 24 * 3600` |
| `QUOTA_DAILY_TTL_HOURS` | `36` | Hardcoded `36 * 3600` |
| `QUOTA_WINDOW_TTL_BUFFER_HOURS` | `1` | Hardcoded `+ 3600` buffer |
| `WEBHOOK_IDEMPOTENCY_TTL` | `604800` | Hardcoded `604800` (7 days) in webhook handlers |
| `WEBHOOK_RETENTION_DAYS` | `30` | Hardcoded `retention_days=30` in cleanup |

Currency defaults (`"USD"`, `"NGN"`) in controllers and services now use
`settings.DEFAULT_BASE_CURRENCY` instead of hardcoded strings.

### Code Clarity

- Removed unused `description` parameter from `credit_wallet_internal`
- Fixed `reference` and `idempotency_key` in `credit_wallet_internal` to share the same UUID (traceability)
- Renamed `status` → `quota_status` in `record_and_charge` (avoid shadowing)
- Made `currency` parameter `str | None` in `resolve_wallet_for_charge` and `record_and_charge` (falls back to settings)
- Moved inline `settings` import to module level in `wallet_service.py`

---

## [2.22.4] - 2026-08-22

### Added — User-Facing Billing, Payments, Subscriptions, Quota & Webhooks

Complete user-facing billing surface with server-side validated payment
initialization, subscription lifecycle management, transaction history,
quota tracking, credit packs, and Paystack/Flutterwave webhook handlers.

#### Wave 1 — P0 Security & Foundation

| Item | Files |
|------|-------|
| Currency conversion utility (`major_to_nano`, `kobo_to_nano`, `provider_amount_to_nano`, `major_to_provider_amount`) | `swx_core/utils/currency.py` (NEW) |
| Session helper `with_read_session()` for DB-read-then-HTTP pattern | `swx_core/database/session_helpers.py` (NEW) |
| Session management documentation | `docs/04-core-concepts/SESSION_MANAGEMENT.md` (NEW) |
| Server-side validated payment init (plan) — `POST /payments/initialize/plan` | `swx_core/controllers/billing_controller.py` (ADD) |
| Credit pack model + migration | `swx_core/models/credit_pack.py` (NEW), `swx_core/database/migrations/v2_22_4_add_credit_pack.py` (NEW) |
| Server-side validated payment init (pack) — `POST /payments/initialize/pack` | `swx_core/controllers/billing_controller.py` (ADD) |
| Paystack webhook handler — HMAC-SHA512, kobo→nano, idempotent wallet credit | `swx_core/webhooks/paystack_webhook.py` (NEW) |
| Paystack webhook secret setting | `swx_core/config/settings.py` (ADD) |

#### Wave 2 — P1 Billing Surface

| Item | Files |
|------|-------|
| Public plan listing — `GET /plans` (no auth) | `swx_core/controllers/billing_controller.py`, `swx_core/routes/user/billing_route.py` |
| Get current subscription — `GET /subscriptions/current` | `swx_core/controllers/subscription_controller.py` (NEW) |
| List subscriptions — `GET /subscriptions` (paginated) | `swx_core/controllers/subscription_controller.py` |
| Subscribe to plan — `POST /subscriptions` | `swx_core/controllers/subscription_controller.py` |
| Cancel subscription — `POST /subscriptions/{id}/cancel` (ownership check) | `swx_core/controllers/subscription_controller.py` |
| Transaction history — `GET /transactions` (type/date filters + pagination) | `swx_core/controllers/billing_controller.py`, `swx_core/services/ledger_service.py`, `swx_core/repositories/ledger_repository.py` |
| Quota status — `GET /quota/status` (Redis 5hr rolling window + monthly) | `swx_core/services/billing/usage_window_service.py` (NEW), `swx_core/controllers/quota_controller.py` (NEW) |
| Reset usage window — `POST /quota/reset-window` (guardrails) | `swx_core/controllers/quota_controller.py` |
| Credit pack listing + purchase — `GET /credit-packs`, `POST /credit-packs/{key}/purchase` | `swx_core/controllers/billing_controller.py`, `swx_core/routes/user/billing_route.py` |
| Flutterwave webhook handler — HMAC-SHA256, major→nano, idempotent wallet credit | `swx_core/webhooks/flutterwave_webhook.py` (NEW) |
| Flutterwave webhook secret setting | `swx_core/config/settings.py` (ADD) |
| SubscriptionPublic schema | `swx_core/models/billing.py` (ADD) |

#### New Service Layer (CSR Compliance)

All controllers now route through services, never repositories directly:

| Service | File | Purpose |
|---------|------|---------|
| `billing_service` | `swx_core/services/billing/billing_service.py` (NEW) | Plan/credit pack/account lookups |
| `currency_service` | `swx_core/services/billing/currency_service.py` (NEW) | Currency CRUD |
| `UsageWindowService` | `swx_core/services/billing/usage_window_service.py` (NEW) | Redis-based quota tracking |
| `SubscriptionService` (extended) | `swx_core/services/billing/subscription_service.py` | Added `get_active_subscription`, `list_subscriptions`, `get_subscription_by_id` |
| `exchange_rate_service` (extended) | `swx_core/services/billing/exchange_rate_service.py` | Added `get_all_for_base` |

#### Settings Added

```env
PAYSTACK_WEBHOOK_SECRET=${PAYSTACK_WEBHOOK_SECRET}
FLUTTERWAVE_WEBHOOK_SECRET=${FLUTTERWAVE_WEBHOOK_SECRET}
QUOTA_WINDOW_HOURS=5
QUOTA_WINDOW_DEFAULT_TOKENS=100000
QUOTA_MONTHLY_DEFAULT_TOKENS=1000000
QUOTA_WINDOW_MAX_RESETS=1
QUOTA_DAILY_MAX_RESETS=3
```

### Fixed — CSR Violations in Pre-Existing Controllers

- `billing_controller.py`: currency/exchange-rate functions now route through
  `currency_service` and `exchange_rate_service` instead of calling
  `currency_repository` and `exchange_rate_repository` directly
- Replaced `HTTPException(status_code=404)` with `NotFoundError` (SwX error hierarchy)
- Removed dead `_currency_payload` helper (moved to `currency_service`)
- Removed dead `HTTPException` import

### Code Clarity

- Removed dead import (`billing_repository` in `paystack_webhook.py`)
- Fixed empty catch block (`except Exception: pass` → added `logger.debug`)
- Renamed misleading `idempotency_key` → `dedup_key` (Redis dedup vs ledger idempotency)
- Moved `_find_user_by_email` from method to module-level (unused `self`)
- Extracted `_call_provider_with_amount` helper (eliminated plan/pack duplication)
- Removed dead `pack_key` from `PaymentInitializePackRequest` (path param covers it)
- Fixed `record_usage` bug — `_incr` now accepts `amount` parameter (was ignoring `tokens`)
- Added event emission for `quota.window_reset` via `event_bus`
- Removed redundant `int(round())` casts (3 occurrences)
- Removed unused `# noqa: E712` directives

### Added — Wave 3 (P2 Completeness)

| Item | Files |
|------|-------|
| Durable webhook idempotency table (`swx_inbound_webhook_delivery`) | `swx_core/models/inbound_webhook_delivery.py` (NEW), `swx_core/repositories/inbound_webhook_delivery_repository.py` (NEW), `swx_core/services/webhook_idempotency_service.py` (NEW), migration `v2_22_5` |
| Wallet debit user endpoint — `POST /wallets/{currency}/debit` | `swx_core/controllers/billing_controller.py`, `swx_core/routes/user/billing_route.py` |
| Wallet transfer user endpoint — `POST /wallets/transfer` | `swx_core/controllers/billing_controller.py`, `swx_core/routes/user/billing_route.py` |
| Stripe webhook extended — durable idempotency + `sync_stripe_subscription` on checkout/invoice events | `swx_core/webhooks/stripe_webhook.py` (MODIFIED) |
| Subscription renewal failure handling — grace period fields + `enter_grace_period`, `retry_renewal`, `expire_grace`, `handle_renewal_failure`, `is_grace_expired` | `swx_core/models/billing.py`, `swx_core/services/billing/subscription_service.py`, migration `v2_22_6` |
| Usage metering service — `calculate_cost_nano` by model, `record_and_charge` with idempotent debit + quota enforcement | `swx_core/services/billing/usage_metering_service.py` (NEW) |
| `credit_wallet_internal()` convenience — auto-generates reference + idempotency_key | `swx_core/services/billing/wallet_service.py` |
| BaseRepository session docs — DB-read-then-HTTP deadlock warning | `docs/04-core-concepts/BASE_CLASSES.md` (UPDATED) |

### Changed — Breaking

- `USER_CACHE_ENABLED` default flipped from `False` to `True` — requires Redis for user auth lookups

### Added — Wave 4 (P3 Advanced)

| Item | Files |
|------|-------|
| Referral system — `ReferralCode` + `ReferralEvent` models, service, controller, user routes, migration | `swx_core/models/referral.py` (NEW), `swx_core/repositories/referral_repository.py` (NEW), `swx_core/services/billing/referral_service.py` (NEW), `swx_core/controllers/referral_controller.py` (NEW), `swx_core/routes/user/referral_route.py` (NEW), migration `v2_22_7` |
| Dual-control wallet adjustments — propose/approve/reject/execute flow with audit trail | `swx_core/models/wallet_adjustment.py` (NEW), `swx_core/services/billing/wallet_adjustment_service.py` (NEW), `swx_core/controllers/wallet_adjustment_controller.py` (NEW), `swx_core/routes/admin/wallet_adjustment_route.py` (NEW), migration `v2_22_8` |
| Wallet priority resolution — `resolve_wallet_for_charge()` (org/personal, never cross-charge, 402 on empty) | `swx_core/services/billing/wallet_service.py` |
| Credit expiry — `CreditLot` model with FIFO consumption (bonus first) + `expire_stale_lots()` | `swx_core/models/credit_lot.py` (NEW), `swx_core/services/billing/credit_expiry_service.py` (NEW), migration `v2_22_8` |
| API key rotation grace period — already existed (`rotate_api_key` + `API_KEY_ROTATION_GRACE_HOURS`) | Verified existing implementation in `swx_core/services/auth/api_key_service.py` |
| Subscription renewal grace — `handle_renewal_failure()` + `is_grace_expired()` | `swx_core/services/billing/subscription_service.py` |
| Audit log retention per-type policies — `SWX_AUDIT_RETENTION_POLICIES` setting | `swx_core/config/settings.py` |
| GDPR data export (ZIP) — `POST /user/gdpr/export/zip` | `swx_core/services/data_transfer/gdpr_service.py` (NEW), `swx_core/controllers/gdpr_controller.py` (NEW), `swx_core/routes/user/gdpr_route.py` (UPDATED) |
| GDPR data deletion — `POST /user/gdpr/deletion` (30-day grace + immediate deactivation) + cancel | `swx_core/services/data_transfer/gdpr_service.py`, `swx_core/routes/user/gdpr_route.py` |

### Fixed — Wave 4 Code Clarity

- Fixed BUG: `CreditLot.expires_at is not None` in SQLAlchemy filter → `.isnot(None)`
- Removed dead `_SOURCE_PRIORITY` dict (unused)
- Removed unnecessary try/except for stdlib `zipfile` import
- Moved inline imports to module level in `resolve_wallet_for_charge`
- Created `wallet_adjustment_controller.py` and `gdpr_controller.py` — routes now go through controllers (CSR compliance)
- Added missing events: `quota.usage_recorded`, `credit_lot.created`, `credit_lot.consumed`, `referral.applied`

### Tests Added

| File | Tests | Coverage |
|------|-------|----------|
| `tests/utils/test_currency.py` | 30 | Currency conversion pure functions |
| `tests/webhooks/test_webhook_handlers.py` | 25 | Signature verification + payload extraction |
| `tests/billing/test_usage_metering.py` | 10 | Cost calculation by model |
| `tests/billing/test_session_helpers.py` | 5 | `with_read_session` context manager |

---

## [2.22.3] - 2026-08-21

### Fixed — Double-wrapping bug in UserDep/AdminUserDep dependency injection

All route files using `User = Depends(UserDep)` or `dict/object = Depends(get_current_admin_user)`
were double-wrapping the dependency. `UserDep` is `Annotated[User, Depends(get_current_user)]` —
the `Depends()` is already embedded in the type alias. Writing `User = Depends(UserDep)` wraps it
a second time, which at best causes a FastAPI warning and at worst fails silently.

Changed all occurrences to the correct pattern:
- `user: User = Depends(UserDep)` → `user: UserDep` (5 user route files)
- `current_user: User = Depends(get_current_user)` → `current_user: UserDep` (team_invitation_route)
- `_admin: dict/object = Depends(get_current_admin_user)` → `_admin: AdminUserDep` (6 admin route files)

Also reordered parameters so `UserDep`/`AdminUserDep` comes before `session: AsyncSession = Depends(get_session)`
to prevent `SyntaxError: parameter without a default follows parameter with a default`.

### Code clarity

- Inlined `_current_user_id(user)` calls to `user.id` / `_admin.id` across all 5 user routes and
  6 admin routes — the helper was a one-liner wrapping `.id`, now inlined for clarity
- Removed `from swx_core.models.user import User` and `from uuid import UUID` where no longer needed
  (feature_flag_route, safety_route, conversation_route, data_transfer_route, sso_route)
- Removed unused `get_current_user` import from workspace_route.py
- Removed unused `HTTPException` import from admin route files where `AdminUserDep` replaced
  `Depends(get_current_admin_user)`
- `team_invitation_route.py`: migrated from `get_current_user` to `UserDep`, removed unused
  `HTTPException` and `User` imports, reordered params for consistency

| File | Change |
|---|---|
| `swx_core/routes/user/conversation_route.py` | `user: UserDep`, inlined `user.id`, removed `_current_user_id` and `User` import |
| `swx_core/routes/user/feature_flag_route.py` | `user: UserDep`, inlined `user.id`, removed `_current_user_id`, `User`, `UUID` imports |
| `swx_core/routes/user/safety_route.py` | `user: UserDep`, inlined `user.id`, removed `_current_user_id` and `User` import |
| `swx_core/routes/user/data_transfer_route.py` | `user: UserDep`, inlined `user.id`, removed `_current_user_id` and `User` import |
| `swx_core/routes/user/sso_route.py` | `user: UserDep`, inlined `user.id`, removed `_current_user_id`, `User`, `UUID` imports |
| `swx_core/routes/user/workspace_route.py` | Removed unused `get_current_user` import |
| `swx_core/routes/team_invitation_route.py` | Migrated to `UserDep`, removed `HTTPException` and `User` imports |
| `swx_core/routes/admin/conversation_route.py` | `AdminUserDep` type safety, param reorder |
| `swx_core/routes/admin/sso_route.py` | `AdminUserDep` type safety, param reorder |
| `swx_core/routes/admin/status_route.py` | `AdminUserDep`, removed `dict["id"]` hack |
| `swx_core/routes/admin/data_transfer_route.py` | `AdminUserDep` type safety, param reorder |
| `swx_core/routes/admin/safety_route.py` | `AdminUserDep` type safety, param reorder |
| `swx_core/routes/admin/feature_flag_route.py` | `AdminUserDep` type safety, param reorder |

---

## [2.22.2] - 2026-08-21

### Fixed — SWX-011: Missing `Any` import crashed module load; SWX-012: Admin/user route prefix collision

**SWX-011** (`NameError: name 'Any' is not defined`): The migration of
`feature_flag_route.py` to `UserDep` in v2.22.1 removed the `from typing
import Any` import without adding it back, causing `NameError` at import
time. Since `swx_core.routes.user` is a package, this crashed the entire
user routes module, preventing all user endpoints (including
`/api/conversations`) from loading.

**SWX-012** (admin/user route prefix collision): Six admin routes
(`/conversations`, `/sso`, `/status`, `/data-transfer`, `/safety`,
`/feature-flags`) used prefixes without the `/admin/` segment, colliding
with the corresponding user routes. Because the admin router is registered
first, admin auth middleware intercepted user requests to these paths,
rejecting user tokens with `INVALID_ADMIN_TOKEN` / "Audience doesn't
match".

**Fix**: Added `/admin/` prefix to all six colliding admin routes. Also
removed duplicate `sso_router` includes from both `admin/__init__.py`
and `user/__init__.py`.

### Fixed — Code clarity: AdminUserDep type safety, deprecated module removal

- Replaced `_admin: dict = Depends(get_current_admin_user)` and
  `_admin: object = Depends(get_current_admin_user)` with
  `_admin: AdminUserDep` in all 6 admin routes (conversation, sso, status,
  data_transfer, safety, feature_flag). This eliminates the
  `UUID(_admin["id"]) if isinstance(_admin, dict) else _admin.id` hack
  in `status_route.py`, using `_admin.id` directly since `AdminUserDep`
  returns `AdminUser`.
- Reordered parameters so `_admin: AdminUserDep` comes before
  `session: AsyncSession = Depends(get_session)` in all affected routes,
  preventing `SyntaxError: parameter without a default follows parameter
  with a default`.
- Removed `swx_core/security/dependencies.py` (deprecated module). All
  consumers have been migrated to `swx_core.auth.user.dependencies` and
  `swx_core.auth.admin.dependencies`.

| File | Change |
|---|---|
| `swx_core/routes/user/feature_flag_route.py` | Added `from typing import Any` (SWX-011) |
| `swx_core/routes/admin/conversation_route.py` | Prefix → `/admin/conversations`; `AdminUserDep` type safety |
| `swx_core/routes/admin/sso_route.py` | Prefix → `/admin/sso`; `AdminUserDep` type safety |
| `swx_core/routes/admin/status_route.py` | Prefix → `/admin/status`; `AdminUserDep`; removed `dict["id"]` hack |
| `swx_core/routes/admin/data_transfer_route.py` | Prefix → `/admin/data-transfer`; `AdminUserDep` type safety |
| `swx_core/routes/admin/safety_route.py` | Prefix → `/admin/safety`; `AdminUserDep` type safety |
| `swx_core/routes/admin/feature_flag_route.py` | Prefix → `/admin/feature-flags`; `AdminUserDep` type safety |
| `swx_core/routes/admin/__init__.py` | Removed duplicate `sso_router` include |
| `swx_core/routes/user/__init__.py` | Removed duplicate `sso_router` include |
| `swx_core/security/dependencies.py` | Removed (deprecated, zero consumers) |

---

## [2.22.1] - 2026-08-20

### Fixed — SWX-010: InvalidAudienceError on PyJWT v2+ in deprecated get_current_user; migrated 5 routes to new auth module

**SWX-010** (`InvalidAudienceError`): PyJWT v2 validates the `aud` claim by
default when it's present in the token. The deprecated
`swx_core.security.dependencies.get_current_user` called `jwt.decode()`
without specifying `audience` or `options={"verify_aud": False}`, causing
`jwt.InvalidAudienceError` for any token that includes an `aud` claim (which
all tokens created by `create_token()` do since v2.0).

The same bug existed in:
- `security/refresh_token_service.py` — two `jwt.decode` calls on refresh
  tokens (fragile: currently works because refresh tokens lack `aud`, but
  would break if `aud` were ever added)
- `guards/jwt_guard.py` — `validate_token()` called `jwt.decode()` without
  `audience`, causing `InvalidAudienceError` before the manual audience
  check could run

**Fix**: Added `options={"verify_aud": False}` to all three affected
`jwt.decode` call sites, matching the pattern already used in
`rate_limit_middleware.py` and `enforce.py`.

**Route migration**: Migrated all 5 user routes from the deprecated
`swx_core.security.dependencies.get_current_user` to the new
`swx_core.auth.user.dependencies.UserDep`, which supports both Bearer
headers and httpOnly cookies via `BearerOrCookieAuth`.

| File | Change |
|---|---|
| `swx_core/security/dependencies.py` | Added `options={"verify_aud": False}` to `jwt.decode` |
| `swx_core/security/refresh_token_service.py` | Added `options={"verify_aud": False}` to both `jwt.decode` calls |
| `swx_core/guards/jwt_guard.py` | Added `options={"verify_aud": False}` to `validate_token`; removed unused `HTTPException`/`status` imports |
| `swx_core/routes/user/conversation_route.py` | Migrated to `UserDep`; simplified `_current_user_id` |
| `swx_core/routes/user/feature_flag_route.py` | Migrated to `UserDep`; simplified `_current_user_id` |
| `swx_core/routes/user/safety_route.py` | Migrated to `UserDep`; simplified `_current_user_id` |
| `swx_core/routes/user/data_transfer_route.py` | Migrated to `UserDep`; simplified `_current_user_id` |
| `swx_core/routes/user/sso_route.py` | Migrated to `UserDep`; simplified `_current_user_id` |

---

## [2.22.0] - 2026-08-19

### Fixed — SWX-007: MissingGreenlet on ApiKeyPublic.model_validate; SWX-009: naive-vs-aware datetime comparison causes async hang

**SWX-007** (`validate_api_key`): `ApiKeyPublic.model_validate(key)` triggers
`MissingGreenlet` because SQLAlchemy attempts lazy attribute access on a
detached ORM object outside the async session context. The fix constructs
`ApiKeyPublic` from explicit attributes instead of `model_validate`, which
also eliminates any risk of lazy-loaded relationship access.

**SWX-009** (async hang / `TypeError` in Python 3.12+): PostgreSQL
`TIMESTAMP WITHOUT TIME ZONE` columns load as naive datetimes even when
SQLModel declares `DateTime(timezone=True)`. Comparing a naive value with
`utc_now()` (timezone-aware) raises `TypeError` in Python 3.12+. Inside an
async context this `TypeError` doesn't propagate — it deadlocks the event
loop, causing endpoints to hang indefinitely.

**Fix**: Added `ensure_aware()` to `swx_core.utils.time` — a single helper
that coerces naive datetimes to UTC-aware and passes aware datetimes through
unchanged. All `expires_at` comparison sites now use `ensure_aware()` before
comparing with `utc_now()`.

| File | Change |
|---|---|
| `swx_core/utils/time.py` | Added `ensure_aware(dt)` helper |
| `swx_core/services/auth/api_key_service.py` | Build `ApiKeyPublic` from explicit attrs (SWX-007); `ensure_aware` on `expires_at` and `last_used_at` (SWX-009) |
| `swx_core/services/team_invitation_service.py` | `ensure_aware` on `invitation.expires_at` |
| `swx_core/services/sso/sso_session_service.py` | `ensure_aware` on `sso_session.expires_at` |
| `swx_core/services/consent_service.py` | `ensure_aware` on `consent.expires_at` (3 sites) |
| `swx_core/services/organization_service.py` | `ensure_aware` on `invitation.expires_at` |
| `swx_core/security/refresh_token_service.py` | Replaced manual `tzinfo` check with `ensure_aware` |
| `swx_core/guards/api_key_guard.py` | Replaced manual `tzinfo` check with `ensure_aware` |

Code-clarity improvements:
- Removed unused `from datetime import datetime` from `consent_service.py`
- Removed unused `datetime` from `organization_service.py` import
- Removed unused `timezone` from `refresh_token_service.py` import

### Added — N+1 query optimisations and LSP error fixes (from previous session)

- 14 N+1 query fixes across repositories and services (bulk queries, eager loads, removed redundant refresh loops)
- 18 files with pre-existing LSP type errors fixed (typed `Dict` annotations, `Optional` for nullable params, `pyright: ignore` for SQLAlchemy column access patterns)
- `eager_loads` parameter added to `BaseRepository.find_one_by` and `BaseService` passthrough
- `lazy="selectin"` on `BillingAccount.subscriptions` and `Subscription.account` relationships

---

## [2.21.4] - 2026-08-18

### Fixed — SWX-009 validation handler now uses SwxJSONEncoder for final serialization (root cause)

The v2.21.1–2.21.3 fixes wrapped `exc.body` and `exc.errors()` in
`jsonable_encoder()` but the response was still constructed via
`JSONResponse`, which calls `json.dumps()` with the standard encoder.
If `jsonable_encoder` returns a dict containing objects the standard
encoder can't handle (e.g., nested `UploadFile` attributes), the 500
crash persists.

**Root cause**: `JSONResponse` uses `json.JSONEncoder`, not `SwxJSONEncoder`.

**Fix**: The handler now serializes the response through `swx_dumps()`
(which uses `SwxJSONEncoder`) and returns a `Response` with the
pre-serialized JSON body. The fallback path uses `JSONResponse` with
only primitive string values extracted from `exc.errors()`, guaranteeing
no serialization crash.

Additional code-clarity improvements:
- Removed dead `import os` from `main.py`
- Removed unused `import functools`, `Union`, `timedelta`, and `TypeVar("T")` from `cache.py`
- Simplified handler docstring to one-line summary

---

## [2.21.3] - 2026-08-18

### Fixed — Code clarity and type safety across JSON/cache/auth modules

Applied code-clarity cleanup and resolved all LSP type errors across the four
files touched by SWX-009.

| File | Change |
|---|---|
| `swx_core/main.py` | Replaced f-string logger calls with lazy `%s` formatting; simplified `safe_detail` logic (try/except directly assigns instead of assigning then validating separately) |
| `swx_core/utils/json.py` | Added `from __future__ import annotations`; typed `SwxJSONEncoder.default(o)` as `object → Union[str, list[Any]]` with `# type: ignore[override]`; added docstring explaining fallback behavior |
| `swx_core/utils/cache.py` | Fixed `_REDIS_AVAILABLE` → `_redis_available` (constant redefinition); `from __future__ import annotations` + `TYPE_CHECKING` guard for `redis.asyncio`; `ttl: int = None` → `Optional[int]`; `Callable` → `Callable[..., Any]`; lazy `%s` logger calls; `assert` guard for `_redis_mod` in `_get_client` |
| `swx_core/auth/auth_cache.py` | Simplified `_serialize_user` — manual UUID/datetime conversion removed (central `SwxJSONEncoder` handles it); replaced all `json.loads` with `swx_loads`; removed unused `import json` and `from datetime import datetime` |

---

## [2.21.2] - 2026-08-18

### Fixed — Validation error handler crashes on FormData (SWX-009)

`validation_exception_handler` in `main.py` serialized `exc.body` directly
into `JSONResponse`. When the request content type was
`application/x-www-form-urlencoded`, `exc.body` was a `FormData` object which
is not JSON-serializable, turning 422 validation errors into 500 internal
server errors. This broke all form-data auth endpoints (login, OAuth2).

Fix: wrap `exc.body` in `jsonable_encoder()` with `TypeError`/`ValueError`
fallback, and guard `exc.errors()` output similarly (Pydantic v2 error `input`
values can also be non-serializable for multipart/form-data requests).

### Hardened — Central JSON serializer handles non-serializable types

`SwxJSONEncoder` now falls back to `str()` for `bytes`, `set`, and any other
non-JSON-native types instead of raising `TypeError`. This hardens all
callers — cache, auth_cache, webhook signer/dispatcher, and CLI exports —
against `FormData`, `UploadFile`, `bytes`, `Decimal`, and similar types.

`utils/cache.py` and `auth/auth_cache.py` now use `swx_core.utils.json.dumps`
instead of raw `json.dumps`, gaining UUID/datetime/bytes handling and the
safe fallback automatically.

| File | Change |
|---|---|
| `swx_core/main.py` | Guard `exc.body` and `exc.errors()` in validation handler |
| `swx_core/utils/json.py` | `SwxJSONEncoder` falls back to `str()` for non-serializable types |
| `swx_core/utils/cache.py` | Use `swx_dumps`/`swx_loads` instead of raw `json.dumps`/`json.loads` |
| `swx_core/auth/auth_cache.py` | Use `swx_dumps` instead of raw `json.dumps` |

---

## [2.21.1] - 2026-08-18

### Fixed — Validation error handler crashes on FormData requests (SWX-009)

`validation_exception_handler` in `main.py` serialized `exc.body` directly
into the JSON response. When the request content type was
`application/x-www-form-urlencoded`, FastAPI stores the parsed body as a
`starlette.datastructures.FormData` object — which is not JSON-serializable.
This turned 422 validation errors into 500 internal server errors, breaking
all form-data auth endpoints (`POST /api/auth/`, OAuth2 login, etc.).

Fix: wrap `exc.body` in `jsonable_encoder()` with a `TypeError`/`ValueError`
fallback that sets `body` to `None` for non-serializable types like `FormData`.

| File | Change |
|---|---|
| `swx_core/main.py` | Safe `exc.body` serialization in `validation_exception_handler` |

---

## [2.21.0] - 2026-08-17

### Added — Test-friendly database configuration (SWX-008)

SWX's `async_engine` was created at module import time, binding it to the
first event loop and making test isolation nearly impossible. This release
introduces lazy engine initialization, configurable pool class, test database
URL override, and a pytest fixture for transaction-rollback-per-test isolation.

**New settings:**

| Setting | Default | Purpose |
|---|---|---|
| `TESTING` | `False` | Enable test mode (lazy init, TEST_DATABASE_URL) |
| `TEST_DATABASE_URL` | `None` | Override DATABASE_URL in test mode |
| `DB_POOL_CLASS` | `"QueuePool"` | SQLAlchemy pool class name (`NullPool` for tests) |

**New public API in `swx_core.database.db`:**

| Symbol | Purpose |
|---|---|
| `get_async_engine()` | Lazy-init async engine (creates on first call) |
| `get_engine()` | Lazy-init sync engine (creates on first call) |
| `reset_engine()` | Dispose engines and clear cached refs (test teardown) |
| `async_engine` | Lazy proxy — backward-compatible drop-in for the old module-level engine |
| `engine` | Lazy proxy — backward-compatible drop-in for the old sync engine |

**New pytest fixtures in `swx_core.testing.fixtures`:**

| Fixture | Scope | Purpose |
|---|---|---|
| `db_session` | per-test | Transaction-rollback async session for perfect test isolation |
| `_reset_engine_fixture` | session (autouse) | Disposes engines after test session ends |

**Usage in `conftest.py`:**

```python
pytest_plugins = ["swx_core.testing.fixtures"]
```

Or with env-based config:

```python
@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("DB_POOL_CLASS", "NullPool")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://.../myapp_test")
```

**Backward compatibility:** All existing imports (`from swx_core.database.db import async_engine`,
`AsyncSessionLocal`, `engine`, etc.) continue to work unchanged. The lazy proxy
delegates attribute access to the real engine, which is created on first use.

| File | Change |
|---|---|
| `swx_core/config/settings.py` | Added `TESTING`, `TEST_DATABASE_URL`, `DB_POOL_CLASS` settings |
| `swx_core/database/db.py` | Lazy engine init via `get_async_engine()`/`get_engine()`; `reset_engine()`; `_LazyAsyncEngine`/`_LazySyncEngine` proxies; `NullPool` support; `TEST_DATABASE_URL` override |
| `swx_core/database/__init__.py` | Export `get_async_engine`, `get_engine`, `reset_engine` |
| `swx_core/providers/database_provider.py` | Use `get_async_engine()` instead of inline `create_async_engine` |
| `swx_core/testing/__init__.py` | New package |
| `swx_core/testing/fixtures.py` | New: `db_session` rollback fixture, `_reset_engine_fixture` session teardown |

---

## [2.20.2] - 2026-08-17

### Fixed — API key validation crashes with MissingGreenlet (SWX-007)

`validate_api_key()` called `update_last_used()` (which does `session.commit()`,
expiring all ORM objects) before `ApiKeyPublic.model_validate(key)`. When
Pydantic tried to access attributes on the expired `key` object, the lazy
load triggered `MissingGreenlet` because async attribute refresh requires an
active greenlet context.

Fix: build the `ApiKeyPublic` result before `update_last_used()` so all
attributes are accessed while the ORM object is still bound to the session.

| File | Change |
|---|---|
| `swx_core/services/auth/api_key_service.py` | Moved `model_validate` before `update_last_used` |

---

## [2.20.1] - 2026-08-17

### Fixed — API key timezone bug: offset-naive vs offset-aware datetime (SWX-005)

`utc_now()` returns `datetime.now(timezone.utc)` (timezone-aware), but
`swx_api_key.expires_at`, `swx_api_key.last_used_at`, and
`swx_onboarding_step.completed_at` were defined as `TIMESTAMP WITHOUT TIME ZONE`.
asyncpg refuses to insert timezone-aware values into timezone-naive columns,
causing a 500 error on API key creation.

**Root cause:** `Optional[datetime] = Field(default=None)` without an explicit
`sa_column=Column(DateTime(timezone=True))` defaults to `TIMESTAMP WITHOUT TIME ZONE`
in PostgreSQL, while `utc_now()` produces timezone-aware datetimes.

**Fix:** Added explicit `sa_column=Column(DateTime(timezone=True), nullable=True)` to
all three columns so they are `TIMESTAMPTZ`.

| File | Change |
|---|---|
| `swx_core/models/api_key_scope.py` | `expires_at` and `last_used_at` → `DateTime(timezone=True)` |
| `swx_core/models/onboarding.py` | `completed_at` → `DateTime(timezone=True)` |
| `migrations/versions/h0a1b2c3d4e5_...py` | Alembic migration: ALTER COLUMN to TIMESTAMPTZ with `USING ... AT TIME ZONE 'UTC'` |

---

## [2.20.0] - 2026-08-11

### Added — Trial billing, service auth CSRF bypass, and plan resolution

This release makes trial a first-class billing concept, fixes the TEAM trial gap that caused `QuotaExceededError` for new users, unifies service token env vars, and adds framework-level CSRF bypass for `X-Service-Token`.

**Trial as a first-class concept (RFC: Trial Billing & Service Auth)**

| Change | Detail |
|---|---|
| `Subscription.trial_ends_at` column | New nullable `DateTime(timezone=True)` column on `swx_billing_subscription`. Replaces ad-hoc JSON metadata `subscription_metadata.trial_ends_at`. Data migration backfills from existing JSON. |
| `SubscriptionService.create_trial_subscription()` | New method that creates a subscription in `TRIALING` status with `trial_ends_at` set to `now + trial_days`. Uses `_commit_or_rollback` for consistent error handling. |
| `EntitlementResolver._resolve_effective_plan_id()` | New method that resolves the plan ID governing entitlements. During an active trial, returns the `TRIAL_PLAN_KEY` plan's ID instead of the subscription's base plan ID. This is the critical fix — without it, trial users on a "free" plan received free-tier entitlements instead of enterprise entitlements. |
| `EntitlementResolver` trial-aware subscription lookup | `_get_account_and_subscription()` now matches subscriptions with `status IN (ACTIVE, TRIALING, PAST_DUE)` OR an unexpired `trial_ends_at`, so trial subscriptions are found even before status is formally `TRIALING`. |
| `PlanResolver` service | New `swx_core/services/billing/plan_resolver.py` — resolves effective plan tier (enterprise/pro/free) with trial awareness. TEAM-first, USER-fallback resolution order. |
| `create_personal_team` hook creates TEAM trial | When `BILLING_ENABLED` and `TRIAL_DAYS > 0`, the registration hook now creates a TEAM billing account with a trial subscription. This fixes the root cause where quota checks at the TEAM level found no subscription. |
| `TRIAL_DAYS` setting | Default: `30`. Number of days for new account trials. Set to `0` to disable. |
| `TRIAL_PLAN_KEY` setting | Default: `"enterprise"`. Plan key whose entitlements apply during the trial period. |
| Alembic migration `g9c3d6f0e2a5` | Adds `trial_ends_at` column + backfills from `subscription_metadata->>'trial_ends_at'`. Downgrade preserves data back to JSON. |

**Service auth CSRF bypass**

| Change | Detail |
|---|---|
| `X-Service-Token` CSRF bypass | CSRF middleware now skips validation when `X-Service-Token` header is present, eliminating the need for per-app internal route CSRF exemptions. |
| `SWX_SERVICE_TOKEN` alias choices | `SERVICE_TOKEN` and `GATEWAY_SERVICE_TOKEN` now map to `SWX_SERVICE_TOKEN` via `AliasChoices`. Apps using either env var name work without code changes. |

---

## [2.19.16] - 2026-08-11

### Fixed — Entitlement resolver: scalar_one_or_none() crash on multi-row query, redundant DB queries, unused imports

`get_remaining_quota()` called `scalar_one_or_none()` on a query that can return
multiple `UsageRecord` rows (one per feature per billing period). When more than
one record existed, SQLAlchemy raised `MultipleResultsFound`. Replaced with
`func.coalesce(func.sum(UsageRecord.quantity), 0)` to aggregate correctly.

Additional improvements during code-clarity review:

| Change | Detail |
|---|---|
| Extracted `_get_account_and_subscription()` | Eliminates duplicated 20-line account+subscription query block that appeared in both `get_entitlement()` and `get_remaining_quota()` |
| Eliminated redundant DB queries in `get_remaining_quota()` | Previously called `get_entitlement()` which re-queried account+subscription (6 extra queries). Now inlines the entitlement lookup, reducing queries from 9 to 3 |
| Replaced magic number `999999999` | Named constant `UNLIMITED_QUOTA = 999_999_999` |
| Extracted `_ACTIVE_STATUSES` frozenset | `[SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]` was duplicated; now a module-level constant |
| Removed unused imports | `Union`, `Dict`, `Any`, `Plan` were imported but never used |
| f-string → lazy logging | `logger.warning(f"...")` → `logger.warning("...", feature_key)` |

---

## [2.19.15] - 2026-08-11

### Fixed — Defensive session.add() for model mutations in hooks, invitations, settings, onboarding

The `create_personal_team` hook set `user.tenant_id = team.id` without calling
`session.add(user)`, so SQLAlchemy didn't track the change and `tenant_id` stayed
NULL in the database. This was the root-cause bug reported.

Audit of the same pattern across the codebase found three more files with the same
risk — model objects mutated after a `session.commit()` or `session.flush()` without
explicit `session.add()` to re-register them as dirty:

| File | Mutation | Fix |
|---|---|---|
| `swx_core/core/default_hooks.py` | `user.tenant_id = team.id` | Added `session.add(user)` after line 125 |
| `swx_core/services/team_invitation_service.py` | 5 status transitions | Added `self.session.add(invitation)` after each mutation |
| `swx_core/services/settings_crud_service.py` | Config value/description/active updates | Added `session.add(config)` before `session.add(history)` |
| `swx_core/repositories/onboarding_repository.py` | `complete_step` and `skip_step` | Added `session.add(step)` before `session.commit()` |

---

## [2.19.14] - 2026-08-11

### Fixed — tenant_id not persisted after create_personal_team hook

`create_personal_team` in `default_hooks.py` set `user.tenant_id = team.id` on the
Python object but didn't call `session.add(user)`. SQLAlchemy doesn't track mutations
on objects that have been expunged from the session or aren't marked dirty, so
`tenant_id` stayed NULL in the database even though the team was created successfully.

Added `session.add(user)` after the mutation so SQLAlchemy includes the UPDATE in
the current transaction's flush.

| File | Change |
|---|---|
| `swx_core/core/default_hooks.py` | Added `session.add(user)` after `user.tenant_id = team.id` |

---

## [2.19.13] - 2026-08-11

### Fixed — Alembic config path not passed to subprocess calls

All Alembic subprocess invocations (`alembic upgrade head`, `alembic downgrade`, `alembic revision`) across the codebase called the `alembic` CLI without specifying a config path. In container environments where `alembic.ini` is not in the CWD (e.g. `/app/migrations/alembic.ini`), this produces `No 'script_location' key found in configuration`, causing:

- `db_setup.run_alembic_migrations()` fails silently — migrations never run
- Superuser seeding is skipped (it runs after migrations)
- `swx db migrate`, `swx db downgrade`, `swx db revision` all fail in containers
- `swx setup` and `swx upgrade` silently skip migrations

Added `ALEMBIC_CONFIG_PATH` setting (default: `"alembic.ini"`) and passed `-c <path>` to every `alembic` subprocess call.

| File | Change |
|---|---|
| `swx_core/config/settings.py` | Added `ALEMBIC_CONFIG_PATH` setting (default `"alembic.ini"`) |
| `swx_core/database/db_setup.py` | Added `_alembic_cmd()` helper; `run_alembic_migrations()` now passes `-c` |
| `swx_core/cli/commands/db.py` | Added `_alembic_cmd()` helper; all 3 commands pass `-c` |
| `swx_core/cli/commands/framework.py` | `_setup_database()` and `upgrade()` now pass `-c` |
| `swx_core/cli/commands/make.py` | `migration()` and scaffold migration now pass `-c` |

**Container deployment**: Set `ALEMBIC_CONFIG_PATH=/app/alembic.ini` in your `.env` or environment.

---

## [2.19.12] - 2026-08-11

### Fixed — Circular FK (swx_users ↔ swx_team) and broken JSONB server_default

**Circular FK:** `swx_users.tenant_id` referenced `swx_team.id` via ForeignKey, while `swx_team.owner_id` referenced `swx_users.id`. This circular dependency prevented `metadata.create_all()` from creating either table — both FKs are unsatisfiable during DDL because neither table exists yet.

The fix removes the ForeignKey from `UserBase.tenant_id` while keeping the column as an indexed UUID. The relationship is already enforced at the application level via `create_personal_team`, and `swx_team.owner_id → swx_users.id` remains intact as the authoritative FK direction.

**Broken JSONB default:** `ApiKeyScopeBase.metadata_` and `ApiKeyScopeBase.is_active` had bare-string `server_default` values (`"'{}'::jsonb"` and `"true"`). SQLAlchemy treats plain-string server_defaults as literals to be SQL-quoted, producing triple-quoted output (`'''{}''::jsonb'`) that PostgreSQL rejects for JSONB columns. Fixed by wrapping with `text()`: `server_default=text("'{}'::jsonb")` and `server_default=text("true")`, which tells SQLAlchemy these are SQL expressions, not literal strings.

| File | Change |
|---|---|
| `swx_core/models/user.py` | Removed `ForeignKey("swx_team.id", ondelete="SET NULL")` from `tenant_id`; removed unused `ForeignKey` import |
| `swx_core/models/api_key_scope.py` | Changed `server_default="'{}'::jsonb"` → `text("'{}'::jsonb")` and `server_default="true"` → `text("true")`; added `text` import |

---

## [2.19.11] - 2026-08-11

### Fixed — Template migration also had swx_user (singular) FK reference

The project scaffold template `e8c1f3d5a9b2_add_onboarding_step_table.py` used
`ForeignKeyConstraint(["user_id"], ["swx_user.id"])` (singular) instead of
`["swx_users.id"]` (plural). This caused `NoReferencedTableError` for projects
generated via `swx new` that then ran `metadata.create_all()`.

Also confirmed via full FK audit: all 62 ForeignKey references in swx_core/models/
are correct (use `swx_users` plural). No other singular/plural mismatches exist.

| File | Change |
|---|---|
| `swx_core/template/project/migrations/versions/e8c1f3d5a9b2_add_onboarding_step_table.py` | `["swx_user.id"]` → `["swx_users.id"]` |

---

## [2.19.10] - 2026-08-11

### Fixed — FK table name mismatch: `swx_onboarding_step.user_id` referenced `swx_user.id` (singular) instead of `swx_users.id` (plural)

`OnboardingStep.user_id` declared `ForeignKey('swx_user.id')` but the User model's
`__tablename__` is `swx_users` (plural). This caused SQLAlchemy's
`metadata.create_all()` to raise `NoReferencedTableError`, blocking 32 of 66
SWX tables from being created (including `swx_team`, `swx_organization`,
`swx_conversation`, `swx_llm_provider_config`, `swx_notification`, and 28 others).

The same incorrect reference existed in the Alembic migration
`v2_19_0_add_onboarding_step.py`.

| File | Change |
|---|---|
| `swx_core/models/onboarding.py` | `ForeignKey("swx_user.id")` → `ForeignKey("swx_users.id")` |
| `swx_core/database/migrations/v2_19_0_add_onboarding_step.py` | `sa.ForeignKey("swx_user.id")` → `sa.ForeignKey("swx_users.id")` |

---

## [2.19.9] - 2026-08-10

### Fixed — Post-register hooks used separate sessions, causing silent failures (create_personal_team never ran)

All three default post-register hooks (`assign_default_role`, `create_billing_account`, `create_personal_team`) opened their own `AsyncSessionLocal()` session instead of using the parent registration session. This caused two bugs:

1. **Lazy-load / MissingGreenlet errors** — Hooks accessed `user.full_name`, `user.email`, etc. on the parent session's `user` object from within a separate session context, triggering `DetachedInstanceError` or `MissingGreenlet` exceptions that were silently swallowed by the `combined_post_hook` wrapper.
2. **Non-atomic registration** — If a hook failed, the user was still created but without a team/role/billing account (half-baked user).

The fix changes the `PostRegisterHook` signature from `(user, context)` to `(user, session, context)`. Hooks now receive the parent `AsyncSession` and share the same transaction. If any hook fails, the entire registration rolls back — no more half-baked users.

**Breaking change for custom post-register hooks:** Any custom hooks registered via `add_post_register()` must add an `AsyncSession` parameter as the second argument:

```python
# Before (v2.19.8 and earlier)
async def my_hook(user: User, context: dict) -> User: ...

# After (v2.19.9+)
async def my_hook(user: User, session: AsyncSession, context: dict) -> User: ...
```

Also removes the redundant bulk `UPDATE` in `create_personal_team` (setting `tenant_id` via `update(UserModel)` in a separate session). Now that the hook uses the parent session, `user.tenant_id = team.id` is sufficient — it persists on the caller's commit.

| File | Change |
|---|---|
| `swx_core/core/hooks.py` | `PostRegisterHook` type now includes `AsyncSession` parameter; `combined_post_hook` forwards session |
| `swx_core/core/default_hooks.py` | All three hooks rewritten to use parent session; removed `AsyncSessionLocal()` and `session.commit()` calls; `create_personal_team` no longer uses bulk `UPDATE` |
| `swx_core/services/auth_service.py` | `post_register_hook` signature updated; call site now passes `session` |
| `docs/04-core-concepts/REGISTRATION_HOOKS.md` | Updated all examples to new `(user, session, context)` signature |

---

## [2.19.8] - 2026-08-07

### Fixed — OAuth registration bypasses default hooks (role assignment, billing account, personal team)

All three OAuth callback handlers (`google_auth_callback`, `facebook_auth_callback`, `provider_auth_callback`) in `oauth_route.py` called `register_user_service()` directly without passing `pre_register_hook` and `post_register_hook`. This meant users registered via social login never ran the default registration hooks registered by `_register_default_hooks()` in `bootstrap.py`:

- `create_personal_team` — no personal team created
- `assign_default_role` — no default role assigned
- `create_billing_account` — no billing account created

Meanwhile, email registration via `register_controller` correctly wired these hooks. The fix adds `registration_hooks.pre_register` and `registration_hooks.post_register` to all three OAuth call sites, ensuring consistent behavior across all registration paths.

| File | Change |
|---|---|
| `swx_core/routes/access/oauth_route.py` | Added `from swx_core.core.hooks import registration_hooks`; passed `pre_register_hook` and `post_register_hook` in all three OAuth callbacks |

---

## [2.19.7] - 2026-08-04

### Fixed — `sync_stripe_subscription` duplicate active subscriptions, checkout-session no-op, 10 edge-case bugs

#### P0 — `sync_stripe_subscription` creates duplicate ACTIVE subscriptions (from bug report)

`sync_stripe_subscription` inserted a new `Subscription` row when a Stripe webhook fired for a subscription with no local match (by `stripe_subscription_id`). It did **not** deactivate existing active subscriptions for the same billing account before inserting, producing multiple `ACTIVE` rows. This crashed `GET /billing/subscription` because `BillingController.get_subscription` uses `scalar_one_or_none()` → `MultipleResultsFound`.

The sibling method `create_subscription` already implemented the correct deactivation pattern. `sync_stripe_subscription` now does the same before insert, using a shared `_deactivate_active_subscriptions()` helper.

| File | Change |
|---|---|
| `swx_core/services/billing/subscription_service.py` | Added `_deactivate_active_subscriptions()` helper; called before insert in `sync_stripe_subscription` and `create_subscription` |

---

#### P1 — `checkout.session.completed` webhook sync was a silent no-op

The webhook handler called `sync_stripe_subscription(event_data)` for `checkout.session.completed` events. A Stripe Checkout Session object does **not** contain `current_period_start` or `current_period_end` fields — those exist only on the Subscription object. The method silently returned without syncing anything, while the handler reported "subscription synchronized" to Stripe.

**Fix:** When period fields are missing but a `subscription` field (string ID) is present, `_sync_from_checkout_session()` fetches the full subscription object from Stripe via the provider and retries the sync. Recursion depth guard prevents infinite loops.

| File | Change |
|---|---|
| `swx_core/services/billing/subscription_service.py` | Added `_sync_from_checkout_session()` method with recursion depth guard |

---

#### Edge cases fixed (12 total)

| # | Severity | Edge Case | Fix |
|---|---|---|---|
| 1 | High | Update branch missing `ended_at` when status becomes CANCELED | Set `ended_at` on cancellation in update branch |
| 2 | High | Insert branch creates ghost CANCELED/EXPIRED rows for never-synced subs | Skip insert when `status in TERMINAL_STATUSES` |
| 3 | High | Update branch missing `canceled_at` when `cancel_at_period_end=True` | Set `canceled_at` on `cancel_at_period_end` in update branch |
| 4 | Medium | `_sync_from_checkout_session` unguarded recursion | Added `depth` parameter, abort at `depth >= 2` |
| 5 | High | `_deactivate_active_subscriptions` didn't cancel `PAST_DUE` subs (entitlement resolver treats PAST_DUE as active) | Added `PAST_DUE` to `ACTIVE_STATUSES` canonical constant |
| 6 | High | Deactivation event fired before commit — listeners saw uncommitted data | Helper returns canceled IDs; callers emit event after commit |
| 7 | High | `create_subscription` event ordering — deactivation event before creation event, both before commit | Deactivation event now fires after commit, before creation event |
| 8 | Medium | Update branch overwrote `ended_at` on every CANCELED webhook resend | Only set `ended_at` if `subscription.ended_at is None` |
| 9 | Low | `_from_stripe_timestamp` accepted `bool` (bool is subclass of int) | Added `_is_numeric_timestamp()` TypeGuard, excludes bool |
| 10 | Medium | `cancel_subscription` not idempotent — double-call emitted duplicate events | Added `already_canceled` check, skip if already canceled at period end |
| 11 | Medium | Insert branch missing `canceled_at` when `cancel_at_period_end=True` | Added `canceled_at` to insert constructor |
| 12 | Medium | `_get_stripe_price_id` returned Plan ID from legacy `plan` field, not Price ID | Removed legacy `plan` field path; only `items.data[0].price.id` used |

---

#### Code clarity

| Change |
|---|
| Extracted `_commit_or_rollback()` helper — 5 duplicate try/commit/except/rollback blocks eliminated |
| Extracted `_update_existing_subscription()` and `_create_subscription_from_stripe()` from `sync_stripe_subscription` |
| `sync_stripe_subscription` reduced from 120 lines to 41 lines (pure orchestration) |
| Extracted `_is_numeric_timestamp()` with `TypeGuard[int | float]` for type-safe timestamp validation |
| Added `ACTIVE_STATUSES` and `TERMINAL_STATUSES` canonical constants to `billing.py` |
| `billing_repository.py` now imports canonical `ACTIVE_STATUSES` instead of private `_ACTIVE_STATUSES` |

---

#### Events added

`subscription_service.py` previously emitted **zero** events. Now emits:

| Method | Event | Payload |
|---|---|---|
| `_deactivate_active_subscriptions` (via callers) | `subscription.deactivated` | `account_id`, `canceled_subscription_ids[]` |
| `create_subscription` | `subscription.created` | `subscription_id`, `account_id`, `plan_key`, `status` |
| `cancel_subscription` | `subscription.canceled` | `subscription_id`, `immediate`, `cancel_at_period_end` |
| `sync_stripe_subscription` (update) | `subscription.updated` | `subscription_id`, `stripe_subscription_id`, `status`, `source` |
| `sync_stripe_subscription` (insert) | `subscription.created` | `subscription_id`, `account_id`, `stripe_subscription_id`, `status`, `source` |

All events fire **after** successful commit, never before.

---

### Changed

| File | Change |
|---|---|
| `swx_core/models/billing.py` | Added `ACTIVE_STATUSES`, `TERMINAL_STATUSES` constants, `__all__` export list |
| `swx_core/repositories/billing_repository.py` | Replaced private `_ACTIVE_STATUSES` with canonical import |
| `swx_core/services/billing/subscription_service.py` | All fixes, edge cases, events, code clarity |

---

## [2.19.5] - 2026-08-04

### Fixed — MissingGreenlet crash on registration, dead code removal, lazy-loading fixes

#### P0 — `MissingGreenlet` crash on `/api/auth/register` (from v2.19.4)

`create_personal_team` hook updates `User.tenant_id` via a bulk `UPDATE` statement in a separate session, triggering `onupdate=func.now()` on `updated_at` in the DB. The in-memory `user` object never picks up the new `updated_at` value, so FastAPI's response serialization triggers a lazy-load on `AsyncSession` → `MissingGreenlet` → 500.

**Fix:** Added `await session.refresh(user)` after post-register hooks in `auth_service.py` to reload all DB-generated columns.

| File | Change |
|---|---|
| `swx_core/services/auth_service.py` | Added `await session.refresh(user)` after hook block |

---

#### P1 — Silent exception swallowing in `auto_accept_invitation` hook

`except (ValueError, Exception): pass` catches **all** exceptions (including programming errors) and silently discards them. `ValueError` from invalid UUID format is expected; other exceptions should be logged.

**Fix:** Split into `except ValueError:` (logged warning) and `except Exception:` (logged with traceback).

| File | Change |
|---|---|
| `swx_core/hooks/invitation_auto_accept.py` | Split bare `except` into typed handlers with logging |

---

#### P2 — `Relationship()` without `lazy=` causes `MissingGreenlet` on attribute access

Three model fields used bare `Relationship()` which defaults to `lazy="select"` (lazy loading). On `AsyncSession`, accessing these attributes outside the session context crashes with `MissingGreenlet`.

**Fix:** Added `lazy="selectin"` to eagerly load these relationships within the same query.

| File | Change |
|---|---|
| `swx_core/models/device.py` | `user: "User" = Relationship()` → `Relationship(lazy="selectin")` |
| `swx_core/models/team_member.py` | `user` and `team_role` → `Relationship(lazy="selectin")` |

---

#### Removed — Dead code

| File | Change |
|---|---|
| `swx_core/repositories/token_repository.py` | Deleted — not imported anywhere, superseded by `refresh_token_service.py` |

---

## [2.19.4] - 2026-08-04

### Fixed — MissingGreenlet crash on registration (hotfix)

#### P0 — `create_personal_team` post-register hook crashes with `MissingGreenlet`

Same root cause as v2.19.5 P0 but without the `session.refresh()` fix. This version was superseded by v2.19.5 within minutes.

---

## [2.19.3] - 2026-08-04

### Fixed — `session.exec()` on AsyncSession (6 instances), CSRF token length, code-clarity

#### P0 — `session.exec()` on `AsyncSession` — crashes every call site

`AsyncSession` has no `.exec()` method (that's SQLModel's `Session`). Six call sites used it, causing `AttributeError` at runtime.

| File | Change |
|---|---|
| `swx_core/core/default_hooks.py` | `await session.exec()` → `await session.execute()` |
| `swx_core/services/team_permission_checker.py` | 4× `await self.session.exec()` → `await self.session.execute()` |
| `swx_core/security/dependencies.py` | `session.exec()` → `(await session.execute()).scalars().first()` |

#### P1 — `get_current_user` was sync but uses `AsyncSession`

`get_current_user` in `security/dependencies.py` was a sync function receiving `AsyncSession` via `SessionDep`. Calling `.execute()` on `AsyncSession` requires `await`. Made the function `async`.

| File | Change |
|---|---|
| `swx_core/security/dependencies.py` | `def get_current_user` → `async def get_current_user` |

#### P2 — CSRF token generation produces 10,800-byte tokens

`_get_or_create_csrf_token()` used `config.cookie_max_age // 8` (= 10,800) as the token byte length instead of `CSRF_TOKEN_LENGTH` (= 32).

| File | Change |
|---|---|
| `swx_core/middleware/csrf_middleware.py` | `secrets.token_urlsafe(config.cookie_max_age // 8)` → `secrets.token_urlsafe(CSRF_TOKEN_LENGTH)` |

#### Code-clarity

| File | Change |
|---|---|
| `swx_core/security/dependencies.py` | Merged duplicate docstrings, removed redundant comment |
| `swx_core/version.py` | Removed unused `Optional` import, fixed bare `tuple` → `tuple[int, ...]` |

---

## [2.19.2] - 2026-08-03

### Fixed — CSRF token length bug (hotfix)

`_get_or_create_csrf_token()` used `cookie_max_age // 8` (10,800 bytes) instead of `CSRF_TOKEN_LENGTH` (32 bytes). Same fix as v2.19.3 P2, released separately for urgency.

---

## [2.19.1] - 2026-08-03

### Fixed — Backward-compatibility breaks from v2.19.0

#### P0 — `ImportError: cannot import name 'async_session'` kills audit subsystem

`audit_event_queue.py` and `security.py` imported `async_session` from `swx_core.database.db`, but the symbol was removed in v2.19.0. Added backward-compat alias.

| File | Change |
|---|---|
| `swx_core/database/db.py` | Added `async_session = AsyncSessionLocal` alias |
| `swx_core/database/__init__.py` | Added `async_session` to exports |

#### P1 — `ImportError: cannot import name 'CSRF_HEADER_NAME'`

`CSRF_HEADER_NAME`, `CSRF_TOKEN_LENGTH`, and `CSRF_COOKIE_NAME` were module-level constants removed in v2.19.0's CSRF rewrite. Restored for backward compatibility.

| File | Change |
|---|---|
| `swx_core/middleware/csrf_middleware.py` | Restored `CSRF_HEADER_NAME`, `CSRF_TOKEN_LENGTH`, `CSRF_COOKIE_NAME` as module-level constants |

#### P2 — Stale `__version__` attribute (2.17.0 instead of 2.19.0)

`swx_core/version.py` had `VERSION_MINOR = 17, VERSION_PATCH = 0` while `pyproject.toml` said `2.19.0`.

| File | Change |
|---|---|
| `swx_core/version.py` | Updated version to match `pyproject.toml` |

#### P3 — `stream_controller` return type mismatch

`llm_controller.stream_controller` had `AsyncGenerator[str, None]` but `llm_service.stream()` yields `SSEEvent`.

| File | Change |
|---|---|
| `swx_core/controllers/llm_controller.py` | Fixed return type to `AsyncGenerator[SSEEvent, None]`, renamed `chunk` → `event` |

---

## [2.19.0] - 2026-08-03

### Added — 40 upstream implementation tickets

(See UPSTREAM_IMPLEMENTATION_PLAN.md for full details.)

New modules: fallback chain, region routing, auth rate limiting, onboarding, provider catalog, cache service, tenant config cache, audit retention, audit event queue, compliance report, prompt injection, encryption, security headers, CSRF, service token guard, combined auth guard, lazy import, error hierarchy.

---

## [2.18.0] - 2026-07-30

### Added — System Config Value Type: FLOAT + Wrapped-Scalar Unwrapping

Extends `SettingValueType` with `FLOAT` and alias values (`INTEGER`, `BOOLEAN`), and updates `SettingsService._convert_value()` to unwrap single-key dict values for scalar types. Unblocks FastPII production seeding.

---

#### New: `FLOAT` value type + `INTEGER`/`BOOLEAN` aliases

The `SettingValueType` enum and the PostgreSQL `settingvaluetype` enum now include `float`, `integer`, and `boolean`. `INTEGER` and `BOOLEAN` are semantic aliases for `INT` and `BOOL`.

| File | Change |
|---|---|
| `swx_core/models/system_config.py` | Added `FLOAT`, `INTEGER`, `BOOLEAN` to `SettingValueType` |
| `swx_core/database/migrations/v2_18_0_add_setting_value_type_float.py` | New migration: `ALTER TYPE settingvaluetype ADD VALUE` for `float`, `integer`, `boolean` |

---

#### New: `SettingsService.get_float()`

```python
threshold = await service.get_float("detection.confidence_threshold", default=0.7)
```

| File | Change |
|---|---|
| `swx_core/services/settings_service.py` | Added `get_float()` method |

---

#### Fixed: `_convert_value()` unwraps single-key dicts for scalar types

FastPII wraps scalar config values in single-key JSON objects (e.g. `{"threshold": 0.7}`). Previously, `int({"max_length": 50000})` silently returned `0`, causing detection requests to fail. Now `_unwrap_scalar()` extracts the inner value before conversion.

| File | Change |
|---|---|
| `swx_core/services/settings_service.py` | Added `_unwrap_scalar()` helper + `_SCALAR_VALUE_TYPES`; updated `_convert_value()` to unwrap and handle `FLOAT`/aliases |
| `swx_core/services/settings_crud_service.py` | Updated `validate_setting_value()` to handle `FLOAT` and `INTEGER`/`BOOLEAN` aliases |

---

### Migration Required

Copy `swx_core/database/migrations/v2_18_0_add_setting_value_type_float.py` to your project's `migrations/versions/` directory, set `down_revision`, and run `alembic upgrade head`. See `MIGRATION_GUIDE_v2.18.0.md` for details.

### Backward Compatibility

- All existing `INT`, `BOOL`, `STRING`, `JSON` configs work unchanged.
- Bare scalar values are not affected by the unwrapping logic.
- The migration `downgrade()` is a no-op — PostgreSQL cannot remove individual enum values.

---

## [2.17.0] - 2026-07-30

### Fixed — OAuth Multi-Domain Support & Registration Bug

3 fixes from FastPII Platform production deployment. Includes a P0 registration-breaking bug, a P1 multi-domain redirect issue, and a P2 configuration gap for multi-redirect-URI support.

---

#### P0 — OAuth registration fails: `secrets.token_urlsafe(32)` generates 43-char password exceeding `UserCreate.password` max_length of 40

When a new user registers via OAuth (Google, Facebook, or any custom provider), `secrets.token_urlsafe(32)` generates a 43-character string that exceeds `UserCreate.password`'s `max_length=40`, causing a Pydantic validation error. This blocks **all new OAuth user registrations**.

**Fix:** Changed all three OAuth callback handlers to use `secrets.token_urlsafe(28)` (~38 chars, within the 40-char limit).

| File | Change |
|---|---|
| `swx_core/routes/access/oauth_route.py` | `token_urlsafe(32)` → `token_urlsafe(28)` in Google, Facebook, and generic provider callbacks |

---

#### P1 — OAuth callback redirects to `FRONTEND_HOST` instead of preserving origin domain

OAuth callbacks were hardcoded to redirect to `FRONTEND_HOST` regardless of which subdomain the user started from. Users on `chat.fastpii.com` would be redirected to `fastpii.com` after login, losing their context.

**Fix:** Added origin preservation through the OAuth flow:
- `store_pkce_session()` captures `origin` from query params or `Referer` header, stores in session as `oauth_origin`
- `complete_oauth_login()` reads `oauth_origin` from session and redirects to the origin domain
- `clear_oauth_session()` cleans up `oauth_origin`

| File | Change |
|---|---|
| `swx_core/routes/access/oauth_route.py` | Origin capture in `store_pkce_session()`, origin-based redirect in `complete_oauth_login()`, cleanup in `clear_oauth_session()` |

---

#### P2 — Single redirect URI limitation for multi-domain deployments

Only a single `GOOGLE_REDIRECT_URI` / `FACEBOOK_REDIRECT_URI` could be configured, forcing all OAuth flows through one domain. Multi-domain applications (chat.fastpii.com, app.fastpii.com, fastpii.com) needed separate redirect URIs registered with each OAuth provider.

**Fix:** Added multi-redirect-URI support with origin-based matching:

- `GOOGLE_REDIRECT_URIS` / `FACEBOOK_REDIRECT_URIS` — comma-separated list of allowed redirect URIs (takes precedence over single `*_REDIRECT_URI`)
- `{PROVIDER}_REDIRECT_URIS` — same for custom providers via `OAuthProviderSettings`
- `resolve_redirect_uri()` — matches request `Origin`/`Referer` header against allowed URIs, falls back to single configured URI

| File | Change |
|---|---|
| `swx_core/config/social_settings.py` | Added `GOOGLE_REDIRECT_URIS: list[str]` and `FACEBOOK_REDIRECT_URIS: list[str]` fields |
| `swx_core/core/oauth_providers.py` | Added `redirect_uris: list[str]` to `OAuthProviderConfig`, parses `{PROVIDER}_REDIRECT_URIS` from env |
| `swx_core/routes/access/oauth_route.py` | Added `resolve_redirect_uri()` helper; updated `google_login`, `facebook_login`, `provider_login` to use it |
| `.env.example` | Added `GOOGLE_REDIRECT_URIS` and `FACEBOOK_REDIRECT_URIS` examples |

---

#### P2 — OAuth URLs endpoint performance

`GET /api/oauth/urls` was rebuilding provider URLs on every request despite configuration being static.

**Fix:** Added `@lru_cache(maxsize=1)` to `_get_oauth_urls_cached()`.

| File | Change |
|---|---|
| `swx_core/routes/access/oauth_route.py` | Wrapped URL builder in `lru_cache` |

---

### Configuration

| Setting | Default | Description |
|---|---|---|
| `GOOGLE_REDIRECT_URIS` | `[]` | Comma-separated list of allowed redirect URIs for Google OAuth. Takes precedence over `GOOGLE_REDIRECT_URI`. |
| `FACEBOOK_REDIRECT_URIS` | `[]` | Comma-separated list of allowed redirect URIs for Facebook OAuth. Takes precedence over `FACEBOOK_REDIRECT_URI`. |
| `{PROVIDER}_REDIRECT_URIS` | `[]` | Comma-separated list of allowed redirect URIs for any custom OAuth provider. Takes precedence over `{PROVIDER}_REDIRECT_URI`. |

### Backward Compatibility

- **Fully backward compatible.** If `*_REDIRECT_URIS` is not set (empty list), the existing `*_REDIRECT_URI` single-URI behavior is used unchanged.
- Origin-based redirect matching only activates when the `Origin` or `Referer` header matches an allowed URI.
- The `secrets.token_urlsafe(28)` change only affects the placeholder password for OAuth registrations — regular email/password registrations are unaffected.

---

## [2.16.1] - 2026-07-29

### Added — NeuronaHealth Production Patterns

7 framework-level features adopted from NeuronaHealth's production deployment. All backward compatible.

---

#### #1 — Security Headers Middleware

New `swx_core/middleware/security_headers_middleware.py`. Adds X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy, and HSTS (production only) to all responses.

```python
from swx_core.middleware.security_headers_middleware import setup_security_headers
setup_security_headers(app)
```

#### #2 — Device Registration Model

New `swx_core/models/device.py` for push notification token management. Platform enum (ios/android/web), FCM token, device metadata, status (active/inactive/unregistered), is_primary, last_used_at, extra_data (JSONB).

#### #3 — String-Based Rate Limit Parsing

New `parse_rate_limit("5/minute")` → `(5, 60)` and `enforce_rate_limit(request, limit="5/minute", namespace="auth:login")` in `enforce.py`. Human-readable rate strings for route handlers — no need to look up integer limits from the registry.

#### #4 — Trusted Proxy IP Extraction

New `get_client_ip(request)` in `enforce.py`. Handles X-Forwarded-For chains with `TRUSTED_PROXIES` validation — walks the chain backwards to find the first untrusted IP. Fixes rate limiting accuracy behind reverse proxies.

#### #5 — DB-Driven OTP Bypass with Per-Email Whitelist

`email_otp_service.py` now supports `OTP_BYPASS_EMAILS` setting (comma-separated whitelist). When `OTP_BYPASS_FOR_TESTING=True` and the email is in the whitelist (or whitelist is empty = all emails), OTP is bypassed. New `is_email_bypassed(email)` function. Also adds `OtpInvalidError`, `OtpRateLimitError`, `OtpDeliveryError` exception classes.

#### #6 — Redis-Backed Config Cache for Cross-Worker Invalidation

`SettingsService` now checks Redis before hitting the DB, and writes to Redis on DB miss. `invalidate_cache()` clears both in-process and Redis caches. Uses the container's `redis.client` singleton. Falls back to in-process-only when Redis is unavailable.

#### #7 — SystemConfig Defaults Registry

New `DEFAULT_SYSTEM_CONFIGS` list in `system_config.py` with 10 default config entries (auth token expiry, rate limit toggles, feature flags, job limits, audit retention, password policy, email toggle, maintenance mode). Services can reference these as fallback when DB has no entry.

---

### New Settings

| Setting | Default | Description |
|---|---|---|
| `OTP_BYPASS_EMAILS` | `""` | Comma-separated email whitelist for OTP bypass |
| `TRUSTED_PROXIES` | `""` | Comma-separated trusted proxy IPs for X-Forwarded-For parsing |

---

## [2.16.0] - 2026-07-29

### Added — Notification System Enhancements (Round 5 Feedback)

7 enhancements to the notification and email system, informed by NeuronaHealth's production deployment patterns. All changes are backward compatible.

---

#### #2 (P1) — Email Provider Cost/Limits/Country Routing

`EmailProviderConfig` now supports financial and operational control fields:

| Field | Type | Purpose |
|---|---|---|
| `cost_per_email` | `float \| None` | Cost tracking per send |
| `daily_limit` | `int \| None` | Max emails per day per provider |
| `monthly_limit` | `int \| None` | Max emails per month |
| `rate_limit_per_hour` | `int \| None` | Burst protection |
| `supported_countries` | `list[str]` | Country codes for regional routing (GDPR, data residency) |
| `tracking_enabled` | `bool` | Per-provider analytics control |
| `open_tracking` | `bool` | Track email opens |
| `click_tracking` | `bool` | Track link clicks |
| `reply_to` | `str \| None` | Reply-to address |

`provider_factory.py` adds:
- `get_email_provider_for_country(session, country)` — filters by `supported_countries`
- `send_via_email(session, notification, preferred_provider=...)` — force a specific provider

#### #1 (P2) — Hybrid Template Approach

`template_service.py` supports optional file-based base templates via `base_template_path` parameter. When provided, DB body content is rendered inside a file-based Jinja2 base layout using `{% extends %}` + `{% block content %}`. Uses `FileSystemLoader` from a configurable `NOTIFICATION_TEMPLATE_DIR` directory. Backward compatible — without `base_template_path`, the existing simple `Template(body).render(context)` path is used.

#### #3 (P2) — Email OTP Authentication Service

New `swx_core/services/auth/email_otp_service.py` with:
- `generate_otp(email)` — 6-digit OTP via `secrets.randbelow`, bcrypt-hashed
- `verify_otp(email, code)` — verifies against stored hash, tracks attempts
- `resend_otp(email)` — new OTP with cooldown enforcement
- Custom exception hierarchy: `OtpError` → `OtpInvalidError`, `OtpResendCooldownError`, `OtpRateLimitError`, `OtpDeliveryError`
- Configurable: `OTP_LENGTH`, `OTP_EXPIRY_MINUTES`, `OTP_MAX_ATTEMPTS`, `OTP_RESEND_COOLDOWN_SECONDS`, `OTP_BYPASS_FOR_TESTING`
- Bypass mode for testing environments

#### #4 (P2) — Notification Preference Escalation/Reminder Fields

`NotificationPreference` adds:
- `reminder_time: str | None` — preferred notification time (HH:MM)
- `escalation_enabled: bool` — retry undelivered critical notifications via alternate channel
- `escalation_hours: int | None` — hours before escalating

#### #5 (P2) — Celery Queue Integration

`send_notification()` accepts optional `queue: bool = False`. When `queue=True`, dispatches to a Celery task via `send_task()` instead of sending synchronously. Falls back to synchronous if Celery is not installed. Configurable task path via `NOTIFICATION_CELERY_TASK_PATH` setting.

#### #6 (P3) — Template Variable Enrichment

`render_template()` auto-injects brand defaults into every template context:
- `{{ brand_name }}` — from `NOTIFICATION_DEFAULT_FROM_NAME` or `PROJECT_NAME`
- `{{ brand_color }}` — from `NOTIFICATION_BRAND_COLOR`
- `{{ support_email }}` — from `NOTIFICATION_SUPPORT_EMAIL`
- `{{ frontend_url }}` — from `FRONTEND_HOST`

User context overrides defaults.

#### #7 (P3) — Provider Health Check and Statistics

`management_service.py` adds:
- `test_email_provider(session, provider_name)` — sends a test email, returns status
- `get_provider_statistics(session, days=30)` — aggregates delivery stats per provider

---

### Changed Files

| File | Change |
|---|---|
| `swx_core/models/email_provider_config.py` | 9 new fields + schema updates |
| `swx_core/models/notification_preference.py` | 3 new fields + schema updates |
| `swx_core/services/notifications/provider_factory.py` | Country routing + preferred provider |
| `swx_core/services/notifications/template_service.py` | Hybrid templates + brand enrichment |
| `swx_core/services/notifications/notification_service.py` | Queue parameter + Celery dispatch |
| `swx_core/services/notifications/management_service.py` | Health check + statistics |
| `swx_core/services/auth/email_otp_service.py` | **New** — Email OTP service |
| `swx_core/services/notifications/tasks.py` | **New** — Celery task fallback |
| `swx_core/config/settings.py` | New notification/OTP settings |

---

## [2.15.6] - 2026-07-29

### Fixed — P0 Circular Import

**`import swx_core` crashed with `ImportError: cannot import name 'get_container'`** — the package was completely unusable.

The v2.15.0 timezone refactor added `from swx_core.utils.time import utc_now` to `repositories/base.py`, which triggered `swx_core/utils/__init__.py` for the first time in the container init chain. `utils/__init__.py` eagerly imports `utils.dependencies` which imports `get_container` from `container.container` at module level — creating a circular dependency since `container.container` was still being initialized.

**Fix:** Made `get_container` import lazy in `dependencies.py` — moved from module-level import to a `_get_container()` helper that imports inside the function body. All call sites updated to use `_get_container()`.

---

## [2.15.5] - 2026-07-29

### Fixed — Round 3 Feedback

5 issues from the FastPII Platform round 3 audit. Includes a P1 runtime crash fix, DEFAULT_PLAN_KEY consistency, rate limit dual-path prevention, and a centralized JSON utility.

---

#### P1 — Runtime Crash

- **`ledger_service.py` ImportError** — Dead import of `utc_now_naive` from `swx_core.models.ledger` (removed in v2.15.0 timezone refactor). Any code importing `ledger_service` would crash at import time. Replaced with `from swx_core.utils.time import utc_now`.

#### P1 — Incomplete Fixes

- **`plan_helper.py` hardcoded "free"** — 4 places returned `"free"` instead of `settings.DEFAULT_PLAN_KEY`. Rate limiting and entitlement checks for users without subscriptions ignored the configured default plan. All 4 replaced with `settings.DEFAULT_PLAN_KEY`.

- **Rate limit dual-path double counting** — `RateLimitMiddleware` now accepts `exempt_namespaces: list[str]` parameter. Routes matching these glob patterns skip middleware rate limiting, letting `enforce_limit()` handle them exclusively. Prevents double counting when both paths are used. Sets `request.state.rate_limit_handled = True` on exempt routes.

#### P3 — Minor

- **JWT billing_plan fallback** — Both `payload.get("billing_plan", "free")` calls in `rate_limit_middleware.py` replaced with `settings.DEFAULT_PLAN_KEY` for consistency.

#### P2 — Quality of Life

- **Centralized JSON utility** — New `swx_core/utils/json.py` with `SwxJSONEncoder` (UUID + datetime support), `dumps()`, and `loads()`. Available for incremental adoption across the codebase.

---

### Changed Files

| File | Change |
|---|---|
| `swx_core/services/ledger_service.py` | Replace dead `utc_now_naive` import with `utc_now` |
| `swx_core/services/billing/plan_helper.py` | Replace 4x `"free"` with `settings.DEFAULT_PLAN_KEY` |
| `swx_core/middleware/rate_limit_middleware.py` | Add `exempt_namespaces` param + 2x `"free"` → `settings.DEFAULT_PLAN_KEY` |
| `swx_core/utils/json.py` | **New** — centralized JSON encoder + dumps/loads |

---

## [2.15.4] - 2026-07-29

### Added — Dual-Format API Key Scopes + Code-Clarity Cleanup

`ApiKeyCreate.scopes` now accepts both `list[str]` (`["billing:read"]`) and `list[dict]` (`[{"resource": "billing", "action": "read"}]`) formats. Projects migrating from flat-string scope formats no longer need to change their API clients.

---

#### What Changed

- **`ApiKeyCreate.scopes`** — type changed from `list[dict[str, str]]` to `list[str] | list[dict[str, str]]`. Both formats are normalized internally to `swx_api_key_scope` rows.

- **`parse_scope_string()`** — new function in `api_key_scope_service.py`. Parses `"resource:action"` strings into `(resource, action)` tuples. Inverse of the existing `expand_scopes()`.

- **`_normalize_scopes()`** — new internal function in `api_key_service.py`. Normalizes mixed scope formats before persisting. Called automatically in `create_api_key()`.

- **Code-clarity cleanup** — removed redundant `_utc_now()` / `_utc_now_naive()` wrappers in `api_key_service.py`, `subscription_service.py`, and `job_runner.py` (all now call `utc_now()` directly). Removed dead imports across 4 files.

---

#### Backward Compatibility

- Existing clients sending `list[dict]` are unaffected
- New clients can send `list[str]` without any changes
- Storage format unchanged — still normalized rows in `swx_api_key_scope`
- Key generation and validation unchanged

---

## [2.15.3] - 2026-07-29

### Added — Per-Route Rate Limit API + Pluggable Config Resolver

Two new features that unblock projects with fine-grained rate limit namespaces and custom config tables.

---

#### #9 — Per-Route Rate Limit Enforcement API

New `enforce_limit()` function in `swx_core/services/rate_limit/enforce.py` allows route handlers to enforce rate limits with custom namespaces that cannot be inferred from the URL path alone.

```python
from swx_core.services.rate_limit.enforce import enforce_limit

@router.post("/detect/public")
async def detect_public(request: Request):
    await enforce_limit(request, namespace="detection:detect:public")
    ...
```

Resolves the actor from JWT/request.state, looks up the limit from the registry, checks Redis, and raises `HTTPException(429)` with standard rate limit headers if exceeded. Supports `custom_limit` parameter to bypass the registry entirely.

#### #7 — Pluggable SettingsService

`SettingsService.__init__()` now accepts an optional `model` parameter. Projects with their own config table can pass their custom SQLModel class instead of using the default `SystemConfig`:

```python
from swx_core.services.settings_service import SettingsService
from my_app.models import MyConfig

service = SettingsService(session, model=MyConfig)
```

The custom model must have `key` (str, unique), `value` (JSONB), `value_type` (SettingValueType), and `is_active` (bool) fields. This enables projects with existing config tables to use the framework's type-safe getters, TTL caching, and env fallback without a data migration.

---

### Changed Files

| File | Change |
|---|---|
| `swx_core/services/rate_limit/enforce.py` | **New** — `enforce_limit()` per-route API |
| `swx_core/services/settings_service.py` | Add `model` parameter to `__init__`, use `self.model` in `_get_from_db` |
| `docs/04-core-concepts/RATE_LIMITING.md` | Document `enforce_limit()` API with parameters table |
| `docs/04-core-concepts/SETTINGS.md` | Document custom config table usage |

---

## [2.15.2] - 2026-07-29

### Changed — SystemConfig JSONB + Metadata/Permissions JSONB

`SystemConfig.value` converted from `VARCHAR(5000)` to PostgreSQL `JSONB`. Metadata and permissions columns converted from generic `JSON` to `JSONB`. This enables GIN indexing, PostgreSQL JSON operators (`->`, `->>`, `@>`), and eliminates `json.loads()` on every DB read.

---

#### What Changed

- **`SystemConfig.value`** — changed from `VARCHAR(5000)` to `JSONB`. Values are now stored as native JSON types (strings, ints, bools, objects) and returned as native Python types via SQLAlchemy. No more `json.loads()` on DB reads. The `value_type` field is retained for env var fallback (where values are always strings) and validation.

- **`SystemConfig.metadata`** — changed from `JSON` to `JSONB` (both `SystemConfig` and `SystemConfigHistory` tables).

- **`SystemConfigHistory.old_value` / `new_value`** — changed from `VARCHAR(5000)` to `JSONB`.

- **`TeamRole.permissions`** — changed from `JSON` to `JSONB`.

- **`settings_service.py`** — `_convert_value()` updated to handle native JSONB types from DB (returns directly) AND string values from env vars (parses). `get_json()` simplified — DB values are already dicts from JSONB.

- **`settings_crud_service.py`** — `validate_setting_value()` and `validate_security_guards()` updated to handle native types (int, bool, dict) alongside string inputs.

- **Data migration** — `swx_core/database/migrations/v2_15_2_convert_system_config_jsonb.py` converts existing VARCHAR/JSON columns to JSONB using `USING ...::jsonb`.

---

#### Backward Compatibility

- Existing string values are automatically valid JSONB (a string is valid JSON)
- The data migration uses `USING column::jsonb` which handles existing VARCHAR data
- `value_type` field retained — env var fallback still needs type conversion
- API responses now return native types instead of strings (e.g., `10080` instead of `"10080"`)

---

## [2.15.1] - 2026-07-29

### Added — Multi-Tenancy for Platform-Level Models

Three platform-level models now support optional team scoping via a nullable `team_id` foreign key to `swx_team.id`. This enables multi-tenant projects to adopt these native models without forking.

---

#### What Changed

- **`LLMProviderConfig`** — Added nullable `team_id` FK. `NULL` = platform-level default provider (visible to all teams). Non-`NULL` = team-specific provider override. Repository functions `get_all()` and `get_by_provider()` accept an optional `team_id` parameter for filtering.

- **`Notification`** — Added nullable `team_id` FK. `NULL` = platform announcement (all users). Non-`NULL` = team-scoped notification. Repository functions `list_notifications()` and `count_notifications()` accept an optional `team_id` parameter.

- **`ApiKey`** — Added nullable `team_id` FK. `NULL` = platform-wide key (admin/service key). Non-`NULL` = team-scoped key. Repository functions `list_api_keys()` and `count_api_keys()` accept an optional `team_id` parameter.

- **Data migration** — `swx_core/database/migrations/v2_15_1_add_team_id_to_platform_models.py` adds the `team_id` column + FK + index to existing databases. Copy to project migrations, set `down_revision`, run `alembic upgrade head`.

- **Template migrations** — The 3 template migrations that create these tables now include the `team_id` column, FK, and index.

- **Docs** — `docs/04-core-concepts/MULTI_TENANT.md` and `docs/07-extending/MULTI_TENANT_MIGRATION.md` updated with the new team-scoping semantics, query patterns, and migration instructions.

---

#### Design Rationale

This follows the industrial-standard nullable `team_id` pattern (used by Stripe, Supabase, GitHub) and matches the existing `UserRole` model in swx-core which already uses nullable `team_id`. The existing `TenantAwareRepository` class and `core/tenant.py` context infrastructure provide automatic tenant filtering for projects that prefer class-based repositories.

---

#### Backward Compatibility

- Existing rows get `team_id = NULL` (platform-level) — behavior unchanged
- All repository functions default `team_id = None` — no filtering when not provided
- No breaking change to existing API responses

---

## [2.15.0] - 2026-07-29

### Changed — Timezone-Aware Timestamps (Breaking)

All timestamps are now timezone-aware. This is a **breaking change** requiring a database migration (`TIMESTAMP WITHOUT TIME ZONE` → `TIMESTAMP WITH TIME ZONE`).

---

#### What Changed

- **New shared utility:** `swx_core/utils/time.py` exports `utc_now()` which returns `datetime.now(timezone.utc)` (timezone-aware). All framework code now imports and uses this instead of stripping timezone info.

- **Eliminated anti-patterns (103 files, 216 occurrences):**
  - Removed all 44 `def utc_now_naive()` helper definitions across model, repository, and service files
  - Replaced all 140 `datetime.now(timezone.utc).replace(tzinfo=None)` calls with `utc_now()`
  - Replaced all 7 production `datetime.utcnow()` calls (Python 3.12 deprecated) with `utc_now()`
  - Removed all inline `lambda: datetime.now(timezone.utc).replace(tzinfo=None)` default factories

- **Database columns:** Changed all `Column(DateTime, ...)` to `Column(DateTime(timezone=True), ...)` across 49 model files, `swx_core/utils/mixins.py`, 15 template migrations, and 2 framework migrations. This creates `TIMESTAMPTZ` columns in PostgreSQL.

- **Data migration:** Added `swx_core/database/migrations/v2_15_0_convert_timestamptz.py` — a dynamic PL/pgSQL migration that converts all existing `TIMESTAMP WITHOUT TIME ZONE` columns in `swx_*` tables to `TIMESTAMPTZ` using `AT TIME ZONE 'UTC'`. Copy to your project's migrations directory, set `down_revision`, and run `alembic upgrade head`.

---

#### Why

Naive timestamps cannot distinguish UTC from local time. If the server timezone changes (container migration, daylight saving, cloud region change), existing timestamps become ambiguous. This affects:

- **Data integrity:** Compliance/audit trails (GDPR, CCPA, SOC 2) require unambiguous timestamps
- **Rate limiting:** Sliding window comparisons assume UTC but nothing enforced it
- **Cache invalidation:** TTL comparisons between cache write and read could shift on timezone mismatch
- **Token expiration:** Token revocation/expiration timestamps could be valid longer than intended

---

#### Migration Guide

1. **Update code:** Install `swx-core>=2.15.0` — all Python code now returns aware datetimes
2. **Run data migration:** Copy `v2_15_0_convert_timestamptz.py` to your project's `migrations/versions/`, set `down_revision` to your current head, run `alembic upgrade head`
3. **Test comparisons:** If your application code compares datetimes from the DB with `datetime.now()`, ensure you use `utc_now()` (or `datetime.now(timezone.utc)`) — comparing aware with naive datetimes raises `TypeError`
4. **Check custom models:** If you have custom models with `Column(DateTime, ...)`, change them to `Column(DateTime(timezone=True), ...)`

---

### Changed Files

| Area | Files | Change |
|---|---|---|
| `swx_core/utils/time.py` | 1 (new) | Shared `utc_now()` utility |
| `swx_core/models/*.py` | 44 | Remove `utc_now_naive`/inline lambdas, import `utc_now`, `Column(DateTime(timezone=True))` |
| `swx_core/utils/mixins.py` | 1 | `FullModelMixin`/`SoftDeleteMixin` use `utc_now`, `DateTime(timezone=True)` |
| `swx_core/repositories/*.py` | 8 | Replace naive timestamp calls with `utc_now()` |
| `swx_core/services/**/*.py` | ~25 | Replace naive timestamp calls with `utc_now()` |
| `swx_core/security/*.py` | 2 | `token_blacklist.py`, `refresh_token_service.py` use `utc_now()` |
| `swx_core/utils/*.py` | 3 | `health.py`, `response.py`, `mixins.py` use `utc_now()` |
| `swx_core/events/*.py` | 2 | `dispatcher.py`, `typed_event.py` use `utc_now()` |
| `swx_core/contracts/*.py` | 1 | `events.py` uses `utc_now()` |
| `swx_core/guards/*.py` | 1 | `api_key_guard.py` uses `utc_now()` |
| `swx_core/cli/commands/resource_templates.py` | 1 | Template string uses `utc_now` |
| `swx_core/services/channels/models.py` | 1 | Uses `utc_now()` |
| Template migrations | 15 | `sa.DateTime()` → `sa.DateTime(timezone=True)` |
| Framework migrations | 2 | `sa.DateTime()` → `sa.DateTime(timezone=True)` |
| `swx_core/database/migrations/v2_15_0_convert_timestamptz.py` | 1 (new) | Data migration: TIMESTAMP → TIMESTAMPTZ |
| `swx_core/version.py` | 1 | Version bump |
| `pyproject.toml` | 1 | Version bump |

---

## [2.14.4] - 2026-07-29

### Fixed — Bug Fixes from FastPII Migration Feedback

Patch release fixing a P0 runtime crash and three P1 issues surfaced during the FastPII Platform migration from v2.7.44 → v2.14.3. All changes are backward compatible.

---

#### P0 Critical

- **`SettingsService._convert_value()` NameError** — `settings_service.py` referenced `SystemConfigValueType` (a non-existent name) instead of the imported `SettingValueType` on lines 165/170/174. Every typed getter (`get_int()`, `get_bool()`, `get_json()`) crashed at runtime. Only `get_string()` survived via the `else` fallthrough. Replaced with the correct `SettingValueType`.

---

#### P1 High

- **Template migrations: branched chain (two heads)** — The 15 template migrations shipped with a branch at `cb96a87ddcc2` producing two alembic heads. Projects copying these migrations had to manually linearize the chain. Rewired `f38a4c8d9b12.down_revision` from `cb96a87ddcc2` to `f7b6d8e0a2c4`, producing a single linear chain with one root and one head.

- **`RateLimitMiddleware._get_user_billing_plan()` always returned `"free"`** — The middleware had two code paths for billing plan resolution: `_actor_from_bearer()` (correctly read the JWT `billing_plan` claim) and `_get_user_billing_plan()` (a stub that hardcoded `return "free"` with dead `EntitlementResolver`/`AsyncSessionLocal` imports). When `request.state.current_user` was pre-resolved by a dependency, the stub path was taken — Pro/Enterprise users got rate-limited as `free`. Replaced the stub with JWT claim decode, consistent with `_actor_from_bearer()`.

- **CSRF helper functions hardcoded `CSRF_COOKIE_NAME`** — `get_csrf_token()` and `set_csrf_cookie()` used the module constant `CSRF_COOKIE_NAME` instead of the middleware instance's `cookie_name`. Projects configuring `CSRFMiddleware(cookie_name="my_csrf_token")` got silent cookie name mismatches when using the helpers. Added a `cookie_name: str = CSRF_COOKIE_NAME` parameter to both helpers (backward-compatible default).

---

#### P3 Minor

- **Dead `lru_cache` import** — `settings_service.py` imported `lru_cache` from `functools` but never used it. Removed.

---

### Changed Files

| File | Change |
|---|---|
| `swx_core/services/settings_service.py` | Replace `SystemConfigValueType` → `SettingValueType` (3 sites); remove dead `lru_cache` import |
| `swx_core/template/project/migrations/versions/f38a4c8d9b12_add_organization_tables.py` | Rewire `down_revision` to `f7b6d8e0a2c4` (linearize chain) |
| `swx_core/middleware/rate_limit_middleware.py` | Replace stubbed `_get_user_billing_plan()` with JWT claim decode |
| `swx_core/middleware/csrf_middleware.py` | Parameterize `cookie_name` on `get_csrf_token()` and `set_csrf_cookie()` |

---

## [2.14.3] - 2026-07-28

### Fixed — Edge Case & Security Hardening (27 issues from comprehensive audit)

Security and robustness fixes across billing, LLM, notification, compliance, and config modules. All changes are backward compatible.

---

#### P0 Critical

- **Sentry middleware: placeholder DSN crashes** — `setup_sentry_middleware()` now validates DSN format via `is_valid_dsn()` before initializing Sentry. Invalid or placeholder DSNs (e.g., `<YOUR_DSN>`) are rejected with a logged warning instead of crashing at runtime.

- **Config resolver: multi-variable substitution bug** — `${HOST:-localhost}:${PORT:-5432}` now correctly resolves to `localhost:5432` instead of `localhost:localhost`. The `_substitute()` method was replaced with a per-match callback in `_resolve_value()` that processes each `${…}` placeholder independently.

- **Config resolver: single-colon default syntax** — `${VAR:default}` (single colon, no dash) is now supported alongside `${VAR:-default}`.

- **Config cache: ValueError on missing env vars** — `resolve_config_value()` in `config_cache.py` now catches `ValueError` from `resolve_config()` when environment variables are missing, returning the fallback value instead of crashing.

- **Stripe provider: mock key bypasses validation** — `get_stripe_provider()` now validates that `sk_live_`/`sk_test_` keys are not mock placeholders (e.g., `sk_test_mock...`). Mock keys no longer pass truthiness checks.

- **Webhook secret: mock secret bypasses validation** — `stripe_webhook.py` webhook handler now rejects `whsec_mock` and similar mock secrets via `is_valid_webhook_secret()`.

- **Billing provider: Stripe key format validation** — `billing_provider.py` now validates Stripe API key prefix (`sk_live_`/`sk_test_`) and rejects placeholder patterns before making API calls.

---

#### P1 High

- **Billing providers: HTTP error handling** — Flutterwave, Paystack, and Mpesa providers now catch `httpx` transport and HTTP status errors, log them with `logger.exception()`, and re-raise as `HTTPException(503)` for consistent upstream error handling.

- **Subscription service: rollback on write failures** — All four `session.add()`/`session.commit()` write paths in `subscription_service.py` now wrap operations in `try/except`, call `await session.rollback()`, log the error, and re-raise.

- **LLM providers: error logging in fallback paths** — `openai_provider.py`, `azure_provider.py`, `anthropic_provider.py`, and `ollama_provider.py` now log `logger.error()` inside their existing `except Exception as exc` blocks instead of silently swallowing errors during fallback.

- **Notification providers: graceful failure handling** — `twilio_provider.py`, `sendgrid_provider.py`, `africas_talking_provider.py`, and `smtp_provider.py` now catch HTTP/SMTP transport errors, log stack traces, and return structured failure payloads instead of raising exceptions upstream.

- **Sentry middleware: init guard** — `SentryMiddleware.__init__()` now wraps SDK initialization in `try/except` so a misconfigured DSN or network failure doesn't prevent the entire app from starting.

---

#### P2 Infrastructure

- **New module: `swx_core/config/validation.py`** — Shared validation utilities (`is_valid_config_value`, `is_valid_api_key`, `is_valid_dsn`, `is_valid_redis_url`, `is_valid_webhook_secret`) for checking that config values are not placeholders, mocks, or malformed. Exported via `swx_core.config.__init__`.

- **Security validation strengthened** — `security_validation.py` Python identifier checks, keyword detection, and path traversal patterns improved for stricter input validation.

---

### Changed Files

| File | Change |
|---|---|
| `swx_core/config/validation.py` | **New** — Shared config validation utilities |
| `swx_core/config/__init__.py` | Export validation functions |
| `swx_core/middleware/sentry_middleware.py` | DSN validation + try/except init guard |
| `swx_core/services/llm/config_resolver.py` | Multi-variable substitution fix, single-colon syntax support |
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

## [2.14.2] - 2026-07-28

### Fixed — Test Suite Hardening

- **244 tests passing, 2 skipped (passlib) — 100% pass rate**
- Fixed `security_validation.py` Python identifier validation, keyword checking, and path traversal patterns
- Completed `SimpleNamespace` mock attributes for API key scoping tests
- Added `passlib` import skip for environments without passlib installed
- Exported `FEATURE_FLAG_CACHE_TTL` module-level constant from settings
- Fixed env var syntax in compliance service tests (`${VAR}` → `${VAR}`)
- Fixed mask assertion in compliance event tests
- Fixed template key assertions in webhook service tests

---

## [2.14.1] - 2026-07-28

### Fixed — Tier 3 Test Fixes

- Fixed all Tier 3 feature test failures (Conversation State, AI Safety, Enterprise SSO, Status Page, Data Transfer, Feature Flags)
- Corrected model field references, import paths, and test assertions

---

## [2.14.0] - 2026-07-28

### Added — Tier 3 Feature Suite (6 enterprise features)

Six production-grade features following the SwX Repository → Service → Controller → Route pattern with event emission, caching, and database-driven configuration.

#### 10. Conversation State
#### 11. AI Safety & Content Filtering
#### 12. Enterprise SSO
#### 13. Status Page
#### 14. Data Export/Import
#### 15. Feature Flags & A/B Testing

*(See v2.14.0 detailed changelog in docs/11-reference/CHANGELOG.md)*

---

## [2.13.0] - 2026-07-28

### Added — Tier 2 Feature Suite (4 enterprise features)

Four production-grade features following the SwX Repository → Service → Controller → Route pattern with event emission, caching where appropriate, database-driven configuration, and full documentation.

---

#### 6. Compliance Audit

GDPR/CCPA-compliant audit logging with severity levels, data classification, field redaction, IP masking, retention policies, and data subject request handling (access, deletion, portability, rectification, restriction).

**New tables:** `swx_compliance_config`, `swx_data_subject_request`, `swx_retention_policy`

**Extended models:** AuditLog gains `severity`, `data_classification`, `access_result`, `masked_ip` fields. AuditOutcome enum gains `DENIED_INSUFFICIENT_ROLE`, `DENIED_CONSENT_REQUIRED`, `DENIED_DATA_CLASSIFICATION`, `DENIED_POLICY`.

**Events:** `compliance.data_accessed`, `compliance.consent_violation`, `compliance.data_exported`, `compliance.config_updated`, `compliance.data_subject_request_created`

**Caching:** Compliance config cached with 30s TTL, invalidated on CRUD.

**Auto-masking:** AuditLogger automatically masks IPs and redacts sensitive fields based on compliance config.

**Endpoints:** Admin (`/admin/compliance/*`), User GDPR (`/user/gdpr/*`)

**Files:** 6 new service modules, 3 models, 1 repository, 2 controllers, 4 route modules. Migration: `d1f6e4a9c3b2`.

---

#### 7. Notification Factory

Multi-provider notification system with circuit breaker fallback, Jinja2 template rendering, delivery tracking, and preference management. Supports SMTP, SendGrid, Twilio, and Africa's Talking.

**New tables:** `swx_email_provider_config`, `swx_sms_provider_config`, `swx_notification`, `swx_notification_preference`, `swx_notification_template`

**Events:** `notification.sent`, `notification.failed`, `notification.template_created`, `notification.preference_updated`

**Caching:** Provider configs cached indefinitely (keyed by config hash). Templates cached with 30s TTL.

**Provider fallback:** Circuit breaker per provider with automatic failover to next provider in chain.

**Endpoints:** Admin (`/admin/notifications/*`), User (`/user/notifications/*`)

**Files:** 7 service modules + 4 provider implementations, 5 models, 1 repository, 1 controller, 4 route modules. Migration: `e7a3c1b2d4f5`.

---

#### 8. API Key Scoping

SHA-256 hashed API key management with resource:action scope patterns, wildcards, key rotation with grace period, and per-key rate limit overrides.

**New tables:** `swx_api_key`, `swx_api_key_scope`

**Events:** `api_key.created`, `api_key.revoked`, `api_key.rotated`, `api_key.scope_changed`

**Key rotation:** Grace period (`API_KEY_ROTATION_GRACE_HOURS`, default 24h) allows both old and new keys during transition.

**Scope patterns:** `resource:action` (e.g., `users:read`), `resource:*` (all actions), `*:read` (read across resources), `*:*` (full access).

**Endpoints:** Admin (`/admin/api-keys/*`), User (`/user/api-keys/*`)

**Files:** 2 models, 1 repository, 2 services, 1 controller, 4 route modules. Migration: `f8b2d5e7a1c3`.

---

#### 9. Webhook System

Outbound webhook delivery with HMAC-SHA256 signature verification, circuit breaker per endpoint, exponential backoff retry with jitter, wildcard event subscription matching, and delivery status tracking.

**New tables:** `swx_webhook_endpoint`, `swx_webhook_delivery`, `swx_webhook_event`

**Events:** `webhook.endpoint_created`, `webhook.endpoint_updated`, `webhook.endpoint_deleted`, `webhook.delivery_created`, `webhook.delivery_delivered`, `webhook.delivery_retrying`, `webhook.delivery_failed`, `webhook.delivery_retry_requested`, `webhook.subscription_updated`

**Signing:** HMAC-SHA256 with `${ENV_VAR}` secret resolution via config_resolver.

**Retry:** Exponential backoff with jitter, configurable retry count/delay/timeout per endpoint. Circuit breaker per endpoint using existing resilience module.

**Wildcard matching:** `user.*` matches `user.created`, `user.updated`, etc. `*` matches all events.

**Endpoints:** Admin (`/admin/webhooks/*`), User (`/user/webhooks/*`)

**Files:** 4 service modules, 3 models, 1 repository, 1 controller, 4 route modules. Migration: `a91c4e2f7b6d`.

---

### Migration Chain

```
d1f6e4a9c3b2 (compliance audit)
  → e7a3c1b2d4f5 (notification factory)
    → f8b2d5e7a1c3 (api key scoping)
      → a91c4e2f7b6d (webhook system)
```

### Configuration

All new settings use database-driven defaults with `${ENV_VAR}` credential resolution:

| Setting | Default | Description |
|---|---|---|
| `COMPLIANCE_ENABLED` | `True` | Enable compliance audit logging |
| `COMPLIANCE_DEFAULT_SEVERITY` | `"medium"` | Default audit log severity |
| `COMPLIANCE_DEFAULT_DATA_CLASSIFICATION` | `"internal"` | Default data classification |
| `COMPLIANCE_IP_MASKING_ENABLED` | `True` | Auto-mask IPs in audit logs |
| `COMPLIANCE_FIELD_REDACTION_ENABLED` | `True` | Auto-redact sensitive fields |
| `NOTIFICATION_ENABLED` | `True` | Enable notification system |
| `NOTIFICATION_DEFAULT_PROVIDER_CHAIN` | `"smtp"` | Default provider fallback chain |
| `NOTIFICATION_CIRCUIT_BREAKER_THRESHOLD` | `5` | Failures before circuit opens |
| `NOTIFICATION_TEMPLATE_CACHE_TTL` | `30` | Template cache TTL in seconds |
| `API_KEY_ROTATION_GRACE_HOURS` | `24` | Hours both keys valid during rotation |
| `WEBHOOK_ENABLED` | `True` | Enable outbound webhooks |
| `WEBHOOK_DEFAULT_RETRY_COUNT` | `3` | Default retry count per delivery |
| `WEBHOOK_DEFAULT_RETRY_DELAY` | `60` | Default retry delay in seconds |
| `WEBHOOK_DEFAULT_TIMEOUT` | `30` | Default HTTP timeout in seconds |
| `WEBHOOK_MAX_RETRIES` | `10` | Maximum retries across all deliveries |
| `WEBHOOK_CIRCUIT_BREAKER_THRESHOLD` | `5` | Failures before circuit opens |

### Documentation

New docs added under `docs/04-core-concepts/`:
- `COMPLIANCE_AUDIT.md`
- `NOTIFICATION_FACTORY.md`
- `API_KEY_SCOPING.md`
- `WEBHOOK_SYSTEM.md`

### Tests

New test files:
- `tests/services/test_compliance_events.py`
- `tests/services/test_compliance_services.py`
- `tests/services/test_api_key_scoping.py`
- `tests/services/test_webhook_services.py`
- `tests/bootstrap/test_webhook_routes.py`

## [2.12.0] - 2026-07-28

### Added — Tier 1 Feature Suite (5 enterprise features)

Five production-grade features requested by AFCloud AI, each following the SwX Repository → Service → Controller → Route pattern with event emission, caching where appropriate, database-driven configuration, and full documentation.

---

#### 1. Consent Management

GDPR/CCPA-compliant consent tracking with configurable consent types, versioning, and enforcement hooks.

**New tables:** `swx_consent_type`, `swx_user_consent`, `swx_consent_version`

**Events:** `consent.granted`, `consent.withdrawn`, `consent.expired`

**Caching:** Consent enforcement checks cached with 30s TTL, invalidated on grant/withdraw.

**Endpoints:** Admin (manage types, view all consents), User (grant, withdraw, view status).

**Files:** 9 new, 3 modified. Migration: `cb96a87ddcc2`.

---

#### 2. Organization Model

Multi-tenant organization support with roles (Owner/Admin/Member), invitations, and member management.

**New tables:** `swx_organization`, `swx_organization_member`, `swx_organization_invitation`

**Events:** `organization.created`, `organization.updated`, `organization.deleted`, `organization.invitation_sent`, `organization.member_joined`, `organization.member_removed`, `organization.member_role_changed`

**Endpoints:** Admin (view all), User (create, update, delete, invite, accept, reject, members, roles).

**Files:** 8 new, 3 modified. Migration: `f38a4c8d9b12`.

---

#### 3. Append-Only Ledger

Immutable financial ledger with running balances, idempotency, refunds, transfers, and reconciliation.

**New tables:** `swx_ledger_entry`, `swx_ledger_balance`, `swx_ledger_idempotency`

**Events:** `ledger.credit`, `ledger.debit`, `ledger.refund`, `ledger.transfer`

**Design:** All entries immutable (insert-only). Amounts in nano-units (int). `LedgerBalance` table serves as a cached balance. `metadata_` column name avoids SQLAlchemy reserved word collision while serializing as `metadata` in API responses.

**Endpoints:** Admin (credit, debit, refund, transfer, balance, history, reconcile).

**Files:** 6 new, 2 modified. Migration: `9b2f6c1d4a7e`.

---

#### 4. LLM Provider Service

Multi-provider LLM abstraction with circuit breaker, retry with jitter, timeout enforcement, and provider fallback chains. Supports OpenAI, Azure, Anthropic, and Ollama.

**New tables:** `swx_llm_provider_config`, `swx_llm_usage_log`

**Events:** `llm.generate`, `llm.provider_failed`

**Caching:** Provider instances cached indefinitely (keyed by config hash). Provider chain cached per phase with 60s TTL, invalidated on any provider config CRUD.

**DB-driven configuration:** Per-provider resilience settings (timeout, retries, circuit breaker threshold/reset, rate limits, daily token limits) stored in database with global settings fallback.

**Credential resolution:** `${ENV_VAR}` (required) and `${ENV_VAR:-default}` (optional) placeholder patterns resolved at runtime.

**Files:** ~20 new, 3 modified. Migration: `c41b7a8e2f10`.

---

#### 5. Multi-Currency Billing

Multi-currency wallet system with 3 African payment providers, exchange rate management, and jurisdiction-specific tax calculation.

**New tables:** `swx_currency`, `swx_exchange_rate`, `swx_wallet`

**Events:** `wallet.credit`, `wallet.debit`, `wallet.transfer`

**Wallet ↔ Ledger integration:** Each wallet uses its `wallet.id` as the ledger `account_id`, ensuring per-currency balance isolation.

**Payment providers:** Paystack (NG, GH), Flutterwave (NG, KE, ZA, GH), M-Pesa (KE). All use `${ENV_VAR}` credential resolution.

**Exchange rate resolution:** Three-tier fallback (direct → inverse → pivot through base currency).

**Tax engine:** NG 7.5%, KE 16%, ZA 15%, GH 15%, US 0%, GB 20%.

**Default currencies:** USD (base), NGN, KES, ZAR, GHS.

**Files:** 16 new, 3 modified. Migration: `b7e1c2d3f4a5`.

---

### Migration Chain

```
cb96a87ddcc2 (consent)
  → f38a4c8d9b12 (organization)
    → 9b2f6c1d4a7e (ledger)
      → c41b7a8e2f10 (llm)
        → b7e1c2d3f4a5 (multi-currency)
```

### Documentation

New docs added under `docs/04-core-concepts/`:
- `CONSENT_MANAGEMENT.md`
- `ORGANIZATIONS.md`
- `LEDGER.md`
- `LLM_PROVIDER.md`
- `MULTI_CURRENCY.md`

## [2.9.0] - 2026-07-22

### Added - Database Engine Configuration via Environment Variables

**Configurable connection pooling and statement timeout** — allows production deployments to tune database connections without forking swx-core.

Previously, all pool parameters were hardcoded in `db.py` with no way to adjust them for production workloads. This caused connection exhaustion under high concurrency.

**New settings:**

| Setting | Default | Description |
|---|---|---|
| `DB_POOL_SIZE` | `20` | Base connection pool size for async engine |
| `DB_MAX_OVERFLOW` | `10` | Max overflow connections beyond pool_size |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for a connection from pool |
| `DB_POOL_RECYCLE` | `3600` | Seconds before recycling a connection |
| `DB_POOL_USE_LIFO` | `False` | Use LIFO connection reuse (warmer connections) |
| `DB_STATEMENT_TIMEOUT_MS` | `0` | PostgreSQL statement timeout in ms (0 = disabled) |
| `DB_SYNC_POOL_SIZE` | `5` | Base pool size for sync engine (Celery workers) |
| `DB_SYNC_MAX_OVERFLOW` | `5` | Max overflow for sync engine |

**Backward compatible:** All defaults match the previous hardcoded values. No changes needed for existing deployments.

**Recommended production values for high-concurrency:**

```env
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
DB_POOL_USE_LIFO=true
DB_STATEMENT_TIMEOUT_MS=30000
```

**Files Changed:**
- `swx_core/config/settings.py` - MODIFIED: Added 8 database pool configuration settings
- `swx_core/database/db.py` - MODIFIED: Async and sync engines now use configurable pool settings, added statement_timeout support

## [2.8.0] - 2026-07-22

### Added - User Auth Caching (L1/L2 Redis)

**Redis-backed two-level cache for auth lookups** — dramatically reduces database queries on every authenticated request.

- L1 cache: process-local dict with timestamp-based TTL (zero Redis round-trip)
- L2 cache: Redis with structured key naming `{env}:{app}:{scope}:{resource}:{identifier}:{version}`
- Cacheable fields exclude `hashed_password` for security
- Graceful degradation: if Redis is unavailable, falls back to L1-only then DB
- Backward compatible: `USER_CACHE_ENABLED=False` (default) = no caching

**New settings:**

| Setting | Default | Description |
|---|---|---|
| `USER_CACHE_ENABLED` | `False` | Enable L1/L2 cache for user auth lookups |
| `USER_CACHE_TTL` | `300` | TTL in seconds for cached user profiles |
| `USER_PERMISSIONS_CACHE_TTL` | `120` | TTL in seconds for cached user permissions |
| `USER_CACHE_L1_MAX_ENTRIES` | `1000` | Maximum entries in process-local L1 cache |
| `ADMIN_CACHE_ENABLED` | `False` | Enable L1/L2 cache for admin auth lookups |
| `ADMIN_CACHE_TTL` | `300` | TTL in seconds for cached admin profiles |

**Cached paths:**

- `get_current_user()` — checks L1 → L2 → DB, populates L1+L2 on miss
- `get_current_admin_user()` — checks L1 → L2 → DB, populates L1+L2 on miss
- `get_user_permissions()` — checks L1 → L2 → DB, populates L1+L2 on miss

**Cache invalidation hooks:**

- `update_user_profile_service()` → invalidates user profile cache (by id + email)
- `update_password_service()` → invalidates user profile cache
- `delete_user_service()` → invalidates user profile cache
- `assign_role_to_user_service()` → invalidates user permissions cache
- `remove_role_from_user_service()` → invalidates user permissions cache
- `assign_permission_to_role_service()` → invalidates ALL permission caches
- `remove_permission_from_role_service()` → invalidates ALL permission caches

**Files Changed:**
- `swx_core/config/settings.py` - MODIFIED: Added auth cache configuration settings
- `swx_core/auth/auth_cache.py` - NEW: AuthCache class with L1/L2, invalidation functions
- `swx_core/auth/user/dependencies.py` - MODIFIED: get_current_user() now checks cache first
- `swx_core/auth/admin/dependencies.py` - MODIFIED: get_current_admin_user() now checks cache first
- `swx_core/rbac/helpers.py` - MODIFIED: get_user_permissions() now checks cache first
- `swx_core/services/user_service.py` - MODIFIED: Added cache invalidation after profile/password/delete
- `swx_core/services/user_role_service.py` - MODIFIED: Added cache invalidation after role assign/remove
- `swx_core/services/role_service.py` - MODIFIED: Added cache invalidation after permission assign/remove
- `docs/04-core-concepts/AUTHENTICATION.md` - MODIFIED: Added auth caching documentation

## [2.7.45] - 2026-07-22

### Added - Admin Auth: Refresh Tokens, Cookie Routes, and Modular Architecture

**Admin login now returns refresh tokens** (previously returned `refresh_token: null`):

- `POST /api/admin/auth/` now returns both `access_token` and `refresh_token`
- `POST /api/admin/auth/refresh` — new endpoint to refresh admin access tokens
- `POST /api/admin/auth/revoke` — new endpoint to revoke admin refresh tokens (logout)

**Admin cookie-based authentication** (BFF pattern for browser admin panels):

- `POST /api/admin/auth/cookie/login` — authenticate and set httpOnly cookies
- `POST /api/admin/auth/cookie/refresh` — refresh tokens via httpOnly cookies
- `POST /api/admin/auth/cookie/logout` — clear httpOnly auth cookies

**Architecture: Refactored admin auth into Repository-Service-Controller-Route pattern:**

- `swx_core/repositories/admin_user_repository.py` — `get_admin_by_email()`, `authenticate_admin()`
- `swx_core/services/admin_auth_service.py` — `login_admin_service()`, `refresh_admin_token_service()`, `logout_admin_service()`, `verify_admin_cookie_refresh()`, `set_auth_cookies()`, `clear_auth_cookies()`
- `swx_core/controllers/admin_auth_controller.py` — Thin delegation layer
- `swx_core/routes/admin/auth_route.py` — Core auth endpoints (login, refresh, revoke)
- `swx_core/routes/admin/auth_cookie_route.py` — Cookie auth endpoints (cookie/login, cookie/refresh, cookie/logout)

**Documentation:**

- Updated AUTHENTICATION.md with admin refresh token flow, admin cookie auth endpoints, and frontend examples

**Files Changed:**
- `swx_core/repositories/admin_user_repository.py` - NEW: Admin user repository
- `swx_core/services/admin_auth_service.py` - NEW: Admin auth business logic
- `swx_core/controllers/admin_auth_controller.py` - NEW: Admin auth controller
- `swx_core/routes/admin/auth_route.py` - MODIFIED: Refactored to use controller/service, added refresh/revoke endpoints
- `swx_core/routes/admin/auth_cookie_route.py` - NEW: Admin cookie auth endpoints
- `swx_core/routes/admin/__init__.py` - MODIFIED: Added auth_cookie_router
- `docs/04-core-concepts/AUTHENTICATION.md` - MODIFIED: Updated admin auth docs

## [2.7.44] - 2026-07-13

### Fixed - router_module() Doubles /api/v1 Prefix for Versioned Routes

**Priority:** Medium — causes incorrect URL paths for production API endpoints

#### BUG: router_module() doubles /api/v1 prefix and cannot produce root-level API paths

**Problem:** `router_module()` composes final URL paths as `include_prefix + router.prefix + route.path`. For versioned routes, `include_prefix` is `/api/v1`. If a route module sets `prefix="/api/v1"` on its APIRouter, the result is a doubled prefix: `/api/v1/api/v1/detect/batch`. Additionally, auto-generated prefixes for versioned routes included a duplicate version segment (`/api/v1/v1/detection_api/detect`), and there was no way to opt out of prefix generation for root-level paths.

**Fix:** Three changes to `router_module()`:

1. **Strip `/api/{version}` from user-defined prefix** for versioned routes — prevents doubling when a module sets `prefix="/api/v1"`
2. **Strip version segment from auto-generated prefix** — auto-generated prefixes for versioned routes no longer include the version segment since it's already in `include_prefix`
3. **Support module-level `ROUTE_PREFIX` attribute** — allows explicit empty prefix opt-out via `ROUTE_PREFIX = ""` for root-level versioned paths

**Files Changed:**
- `swx_core/router.py` - Fixed prefix composition logic in `router_module()`

**URL path resolution examples (after fix):**

| Module | Router Prefix | Result Path |
|---|---|---|
| `app/routes/v1/auth.py` | `prefix=""` | `/api/v1/auth` |
| `app/routes/v1/auth.py` | `prefix="/auth"` | `/api/v1/auth` |
| `app/routes/v1/auth.py` | `prefix="/api/v1/auth"` | `/api/v1/auth` (stripped) |
| `app/routes/v1/detect.py` | `ROUTE_PREFIX="/"` | `/api/v1` (root-level) |
| `app/routes/v1/detect.py` | `ROUTE_PREFIX=""` | `/api/v1/detect` (auto) |

## [2.7.43] - 2026-07-12

### Fixed - BillingServiceProvider Boot Failure

**Priority:** P0 (Prevents billing from booting on startup)

#### BUG: FeatureRegistry.register() called with keyword arguments instead of FeatureDefinition object

**Problem:** `BillingServiceProvider._register_default_features()` called `registry.register()` with keyword arguments (`key=`, `name=`, `default_value=`, etc.), but `FeatureRegistry.register()` expects a single `FeatureDefinition` positional argument. Additionally, `default_value` is not a field on `FeatureDefinition`. This caused the entire billing service to fail to boot when `BILLING_ENABLED=true`.

**Symptoms:**
- Error: `FeatureRegistry.register() got an unexpected keyword argument 'key'`
- No billing provider initialized
- No subscription service available
- All billing API endpoints return errors

**Fix:** Replaced keyword argument calls with `FeatureDefinition` objects, removed nonexistent `default_value`, added `unit` for QUOTA features, and added deduplication check to avoid overwriting app-specific features.

**Files Changed:**
- `swx_core/providers/billing_provider.py` - `_register_default_features` now creates `FeatureDefinition` objects and deduplicates against existing registrations

## [2.7.42] - 2026-07-12

### Fixed - Critical Stripe Billing Bugs

**Priority:** P0 (Production checkout is broken without these fixes)

#### BUG-1: create_checkout_session passes database UUID as Stripe price ID

**Problem:** `StripeProvider.create_checkout_session()` passed `plan_id` (a database UUID like `550e8400-e29b-41d4-a716-446655440000`) to Stripe's `price` field, which expects a `price_xxx` identifier. Every checkout attempt failed with `resource_missing` error.

**Fix:** Added `stripe_price_id` and `stripe_product_id` columns to the `Plan` model. Renamed the provider parameter from `plan_id` to `price_id` across all billing interfaces. The controller now resolves the Plan's `stripe_price_id` before passing it to Stripe.

**Files Changed:**
- `swx_core/models/billing.py` - Added `stripe_price_id`, `stripe_product_id`, `amount`, `currency` to Plan model
- `swx_core/services/billing/stripe_provider.py` - `create_checkout_session` now takes `price_id` instead of `plan_id`
- `swx_core/services/billing/billing_provider_base.py` - Updated interface: `plan_id` → `price_id`
- `swx_core/providers/billing_provider.py` - Updated MockBillingProvider interface

**Migration Required:** Add `stripe_price_id`, `stripe_product_id`, `amount`, `currency` columns to `swx_billing_plan` table.

#### BUG-2: sync_stripe_subscription cannot create new subscriptions from webhooks

**Problem:** When Stripe sent `customer.subscription.created`, the webhook handler silently dropped the event because no local subscription existed yet. Only subscriptions created via direct DB seeding persisted.

**Fix:** `sync_stripe_subscription` now creates a local `Subscription` record when no existing match is found. It resolves the Stripe price ID to a local Plan via `stripe_price_id` and the Stripe customer ID to a local BillingAccount.

**Files Changed:**
- `swx_core/services/billing/subscription_service.py` - Added subscription creation from webhook events with Plan and BillingAccount resolution

#### BUG-3: create_portal_session returns stub response

**Problem:** `StripeProvider` had no `create_portal_session` implementation. Users couldn't manage subscriptions (cancel, upgrade, update payment method) without admin intervention.

**Fix:** Implemented `create_portal_session` in both `StripeProvider` and `MockBillingProvider` using `stripe.billing_portal.Session.create`.

**Files Changed:**
- `swx_core/services/billing/stripe_provider.py` - Added `create_portal_session` method
- `swx_core/services/billing/billing_provider_base.py` - Added `create_portal_session` to interface
- `swx_core/providers/billing_provider.py` - Added `create_portal_session` to MockBillingProvider

#### BUG-4: Missing checkout.session.completed webhook handler

**Problem:** The webhook handler only processed `customer.subscription.created`, `customer.subscription.updated`, and `customer.subscription.deleted`. The `checkout.session.completed` event was missing, causing delayed subscription sync.

**Fix:** Added `checkout.session.completed` handling in the webhook job handler. It extracts the subscription ID from the checkout session and syncs the full Stripe subscription data.

**Files Changed:**
- `swx_core/services/job/handlers.py` - Added `checkout.session.completed` event handling

### Code Clarity Applied

Extracted helper functions to eliminate repeated logic:
- `_utc_now_naive()` in `billing.py` for timestamp defaults
- `_serialize_metadata()` in `stripe_provider.py` for Stripe metadata normalization
- `_naive_utc_from_timestamp()` and `_resolve_stripe_price_id()` in `subscription_service.py`
- `SUBSCRIPTION_SYNC_EVENT_TYPES` constant in `handlers.py`

## [2.7.41] - 2026-07-05

### Fixed - Critical Bugs from v2.7.40

**Priority:** P0 (Critical production bugs)

#### BUG-1: InvitationStatus StrEnum Case Mismatch with PostgreSQL ENUM

**Problem:** `InvitationStatus` enum used lowercase values (`"pending"`, `"accepted"`, etc.) but PostgreSQL ENUM columns are case-sensitive. When asyncpg binds parameters, it uses the enum's `.name` attribute which is UPPERCASE (`PENDING`, `ACCEPTED`), causing PostgreSQL to reject values.

**Symptoms:**
- All `TeamInvitationService` queries filtering by `InvitationStatus.PENDING` failed with HTTP 500
- Error: `invalid input value for enum invitationstatus: "PENDING"`

**Fix:** Changed `InvitationStatus` enum values to uppercase to match PostgreSQL ENUM expectations:
```python
# BEFORE
class InvitationStatus(str, Enum):
    PENDING = "pending"    # lowercase
    ACCEPTED = "accepted"  # lowercase

# AFTER
class InvitationStatus(str, Enum):
    PENDING = "PENDING"    # uppercase
    ACCEPTED = "ACCEPTED"  # uppercase
```

**Migration Required:** If you created PostgreSQL enums with lowercase values:
```sql
DROP TYPE IF EXISTS invitationstatus CASCADE;
CREATE TYPE invitationstatus AS ENUM ('PENDING', 'ACCEPTED', 'REJECTED', 'EXPIRED', 'REVOKED');
```

**Files Changed:**
- `swx_core/models/team_invitation.py` - Updated InvitationStatus enum values

#### BUG-2: swx_team_member.role_id NOT NULL Constraint Violation

**Problem:** The v2.7.40 model removed `role_id` from `TeamMember` (replaced by `team_role_id`), but the database column still exists as `NOT NULL` with no default. Creating team members only provides `team_role_id`, leaving `role_id` as NULL - which violates the constraint.

**Symptoms:**
- POST `/admin/team/member` failed with HTTP 500
- Error: `null value in column "role_id" of relation "swx_team_member" violates not-null constraint`

**Fix:** Users need to run a migration to make `role_id` nullable or drop the column entirely.

**Migration Required:** See `MIGRATION_GUIDE_v2.7.41.md` for detailed migration steps:
```python
# Migration: make_team_member_role_id_nullable
def upgrade() -> None:
    op.alter_column(
        'swx_team_member',
        'role_id',
        existing_type=sa.UUID(),
        nullable=True
    )
```

**Workaround Applied:** Users who already fixed this can skip the migration.

**Files Changed:**
- `MIGRATION_GUIDE_v2.7.41.md` - Added comprehensive migration guide
- No model changes (model is correct, database needs migration)

### Migration Guide

See [MIGRATION_GUIDE_v2.7.41.md](./MIGRATION_GUIDE_v2.7.41.md) for:
- Detailed migration steps
- Verification procedures
- Rollback instructions
- Database schema changes

### Breaking Changes

**None** - These are pure bug fixes with no breaking API changes.

### Verification Steps

1. **InvitationStatus Fix:**
   ```bash
   curl -X POST http://localhost:8001/api/admin/team/invite \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"team_id": "...", "invitee_email": "test@example.com", "team_role_id": "..."}'
   # Should return 200 OK, not 500
   ```

2. **Team Member Creation:**
   ```bash
   curl -X POST http://localhost:8001/api/admin/team/member \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"team_id": "...", "user_id": "...", "team_role_id": "..."}'
   # Should return 200 OK, not 500
   ```

## [2.7.40] - 2026-07-05

### Added - Enterprise Dashboard Features

**Priority:** P2 (4 feature requests from FastPII Integration)

#### FEATURE-1: User-Scoped Workspace Endpoints

**Added:** New workspace endpoints for Enterprise Dashboard with user-scoped filtering.

**Endpoints:**
- `GET /api/v1/workspaces` - List workspaces for current user
- `GET /api/v1/workspaces/{workspace_id}` - Get workspace detail
- `POST /api/v1/workspaces` - Create workspace
- `PUT /api/v1/workspaces/{workspace_id}` - Update workspace
- `DELETE /api/v1/workspaces/{workspace_id}` - Archive workspace

**Implementation:**
- New route: `swx_core/routes/user/workspace_route.py`
- New controller: `swx_core/controllers/workspace_controller.py`
- User filtering: Lists only teams where `current_user.id` is a member via TeamMember
- Uses existing Team model and TeamService
- Authentication: `Depends(get_current_user)`

**Use Case:** Enterprise Dashboard workspace management with user-specific workspace list.

#### FEATURE-2: Enriched Team Member Endpoint

**Added:** New endpoint returning team members with full user and role details.

**Endpoint:**
- `GET /api/admin/team/{team_id}/members/enriched` - List members with enriched details

**Response Schema:**
```json
{
  "id": "...",
  "team_id": "...",
  "user": {
    "id": "...",
    "email": "...",
    "full_name": "...",
    "avatar_url": "..."
  },
  "team_role": {
    "id": "...",
    "key": "owner",
    "name": "Team Owner",
    "permissions": {...}
  },
  "created_at": "..."
}
```

**Implementation:**
- New schema: `TeamMemberWithDetails` (swx_core/models/team_member.py)
- Uses `joinedload(User)` and `joinedload(TeamRole)` for eager loading
- Original endpoint preserved: `GET /api/admin/team/{team_id}/members` (IDs only)

**Use Case:** Enterprise Dashboard team member management with full user context.

#### FEATURE-3: Team Invitation Auto-Accept on Registration

**Added:** Auto-accept team invitations when users register through invitation links.

**Flow:**
1. User receives invitation email with link
2. User clicks link → redirected to registration
3. Frontend passes `invitation_token` in registration request
4. Backend creates user account
5. `post_register_hook` automatically accepts invitation
6. User added to team immediately

**Implementation:**
- New hook: `swx_core/hooks/invitation_auto_accept.py`
- Registered in `swx_core/core/hooks.py` via `registration_hooks.add_post_register()`
- `UserCreate` schema accepts optional `invitation_token` field
- `register_user_service` passes token through `event_context`
- Hook validates email match (invitation.invitee_email == user.email)
- Error handling: Hook failures log warning but don't block registration

**Security:**
- Email validation enforced by TeamInvitationService
- Token expiration enforced (7 days default)
- Invitation must have status PENDING

**Use Case:** Seamless onboarding when inviting new users to teams.

#### FEATURE-4: Team Invitation Event Emission

**Added:** Event emission for team invitation creation to enable email notifications.

**Event Bus:**
- Location: `swx_core/event_bus.py` (AsyncEventBus)
- Event type: `team.invitation.created`
- Event class: `TeamInvitationCreatedEvent`

**Event Payload:**
```json
{
  "invitation_id": "uuid",
  "team_id": "uuid",
  "inviter_id": "uuid",
  "invitee_email": "string",
  "token": "string",
  "metadata": {"invitation_code": "string"}
}
```

**Implementation:**
- TeamInvitationService.create_invitation() emits event after successful creation
- Event emission is asynchronous (doesn't block invitation creation)
- FastPII can subscribe to `team.invitation.created` for email sending

**Example Handler (FastPII):**
```python
@event_bus.subscribe("team.invitation.created")
async def send_invitation_email(event):
    await send_email(
        to=event.invitee_email,
        template="team_invitation",
        data={"team_name": event.team_name, "token": event.token}
    )
```

**Use Case:** Enable FastPII email notification system for team invitations.

### Files Modified

- `swx_core/routes/user/workspace_route.py` - NEW: User-scoped workspace endpoints
- `swx_core/controllers/workspace_controller.py` - NEW: Workspace controller
- `swx_core/models/team_member.py` - NEW: TeamMemberWithDetails schema
- `swx_core/routes/admin/team_route.py` - NEW: Enriched members endpoint
- `swx_core/hooks/invitation_auto_accept.py` - NEW: Auto-accept hook
- `swx_core/core/hooks.py` - UPDATED: Hook registration
- `swx_core/services/team_invitation_service.py` - UPDATED: Event emission
- `swx_core/events/__init__.py` - UPDATED: TeamInvitationCreatedEvent
- `swx_core/main.py` - UPDATED: Route registration

### Migration Guide

**No database migrations required** - all changes are code additions.

**Configuration:**
1. Import and register workspace routes in your app:
   ```python
   from swx_core.routes.user.workspace_route import router as workspace_router
   app.include_router(workspace_router, prefix="/api/v1/workspaces")
   ```

2. Register auto-accept hook at startup:
   ```python
   from swx_core.hooks.invitation_auto_accept import auto_accept_invitation
   from swx_core.core.hooks import registration_hooks
   registration_hooks.add_post_register(auto_accept_invitation)
   ```

3. Subscribe to invitation events (FastPII):
   ```python
   from swx_core.event_bus import event_bus
   
   @event_bus.subscribe("team.invitation.created")
   async def send_invitation_email(event):
       # Your email logic
   ```

### Breaking Changes

None - all changes are additive and backward compatible.

---

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
