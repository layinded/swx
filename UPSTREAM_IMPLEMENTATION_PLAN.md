# SwX-Core Upstream Capability Implementation Plan

**Source:** FastPII Platform Team upstream proposal (`SWX_CORE_UPSTREAM_PROPOSAL.md`)
**Created:** 2026-08-03
**Status:** In Progress
**Reference repo:** `github.com/layinded/swx` (SwX-API v2.18.0)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [SwX Pattern Constraints](#2-swx-pattern-constraints)
3. [Code-Clarity Principles](#3-code-clarity-principles)
4. [Key Discoveries](#4-key-discoveries)
5. [Dependency Graph](#5-dependency-graph)
6. [Execution Phases](#6-execution-phases)
7. [Ticket Tracker](#7-ticket-tracker)
8. [Per-Feature Specifications](#8-per-feature-specifications)
9. [Migration Strategy](#9-migration-strategy)
10. [Testing Strategy](#10-testing-strategy)

---

## 1. Executive Summary

This plan implements 15+ upstream capabilities proposed by the FastPII team for the SwX-Core framework. The proposal was generated from a five-stream parallel code audit comparing `swx_core/` (v2.18.0) against FastPII's `swx_app/` and `apps/gateway/` implementations.

**Three priority tiers:**

- **Wave 1 — Security Foundation** (5 items): Closes real at-rest security gaps (plaintext webhook secrets, SSO secrets, refresh tokens, LLM credentials) and modernizes security headers.
- **Wave 2 — LLM Layer Usability** (6 items): Makes SwX's existing `LLMProviderContract` usable out of the box with concrete adapters, structured SSE, BYOK, and real validation.
- **Wave 3 — Operational Maturity** (15 items): Async audit queue, three-tier cache, compliance reporting, onboarding, retention, and related plumbing.

**Adjustments from original proposal:**

1. **3.12 (circuit breaker lock) promoted to Phase 1** — it's a production race condition bug, not a feature.
2. **2.1 (LLM adapters)** — SwX already has providers; task changes to *validate and extend*.
3. **2.3 (structured SSE)** — Port only `SSEEvent` types + formatter, not the full `ChatStreamService`.
4. **3.2 (three-tier cache)** — Port the cache pattern only, not gateway-specific config accessors.
5. **3.9 (error hierarchy)** — Add ~5 generic errors to `swx_core/utils/errors.py`, not 21 domain-specific ones.
6. **2.2 (BYOK) prioritized before 2.5 (provider catalog)** — higher impact.
7. **Two bugs found** in FastPII reference code — fixed during porting.

---

## 2. SwX Pattern Constraints

Every feature MUST respect these rules from `swx-api-framework`:

| Rule | Enforcement |
|------|-------------|
| **CSR Architecture** | Controller → Service → Repository → Model. No skipping layers. |
| **Domain Separation** | Admin `/admin/*`, User `/user/*` or `/api/*`. Auth: `AdminDep`, `UserDep`, `require_permission()`. |
| **Base Classes** | `BaseRepository[Model]`, `BaseService[Model, Repository]`, `BaseController[Model, Create, Update, Public]`. |
| **Error Hierarchy** | `SwXError` subclasses from `swx_core/utils/errors.py` — not raw `HTTPException`. |
| **Event-Driven** | Emit events for state changes via `swx_core.events.event_bus`. |
| **Settings** | All config in `swx_core/config/settings.py` via `Settings(BaseSettings)`. |
| **Framework Code** | All new code lives in `swx_core/`. |
| **Contract Layer** | New abstractions get a `contracts/<domain>.py` ABC. |
| **Guard Pattern** | Auth guards extend `BaseGuard`, return `AuthenticatedUser`, register via `GuardManager`. |
| **Middleware Pattern** | Each middleware is a class with `apply_<name>(app: FastAPI)` function. |
| **Naming** | `snake_case` files, `PascalCase` classes, `UPPER_SNAKE_CASE` constants. |

---

## 3. Code-Clarity Principles

Applied to every implemented module:

1. **Remove redundancy** — no duplicate conditions, no dead code, no unreachable branches.
2. **Simplify logic** — reduce nested conditions, use early returns and guard clauses.
3. **Preserve behavior** — no unintended functionality changes, all edge cases handled.
4. **Meaningful names** — no `data`, `value`, `temp`. Names reflect intent.
5. **No type suppression** — no `as any`, `@ts-ignore`, or `# type: ignore`.
6. **No empty catches** — every `except` block does something meaningful.
7. **Verify after edit** — run `lsp_diagnostics` on every changed file.

---

## 4. Key Discoveries

### 4.1 SwX Already Has LLM Providers

The proposal states SwX ships "zero concrete implementations" — this is **outdated**. SwX already has:

```
swx_core/services/llm/providers/
├── openai_provider.py
├── anthropic_provider.py
├── azure_provider.py
├── ollama_provider.py
└── __init__.py  (BaseLLMProvider)
```

Plus `provider_factory.py` with in-memory caching and `config_resolver.py` with `${ENV_VAR}` resolution.

**Action:** Task 2.1 changes from "create adapters" to "validate existing adapters, add `validate_api_key()` and `list_models()` methods."

### 4.2 Bugs in FastPII Reference Code

| File | Bug | Fix |
|------|-----|-----|
| `config_regions.py:81` | `get_region()` uses module-level `regions` instead of calling `get_regions()`, so env-var overrides are ignored | Call `get_regions()` for dynamic resolution |
| `llm_provider_service.py:463` | Uses `utc_now()` without importing it | Add `from swx_core.utils.time import utc_now` |

### 4.3 High-Coupling Files Need Decomposition

| File | Coupling | Strategy |
|------|----------|----------|
| `chat_stream_service.py` (2.3) | HIGH — 11 internal service/model imports | Port only `SSEEvent` types + `_format_sse_event()`. PII pipeline stays in `swx_app/`. |
| `workspace_config_cache.py` (3.2) | HIGH — FastPII gateway config schema | Port three-tier cache pattern only. Config accessors stay in `swx_app/`. |
| `adapter_factory.py` (2.1) | HIGH — depends on FastPII domain model | Existing `provider_factory.py` covers this. Evaluate additions, don't port wholesale. |
| `llm_provider_service.py` (2.2) | MED-HIGH — BYOK concept portable, encryption coupling | Abstract encryption behind `KeyStore` protocol. Fix `utc_now` bug. |

### 4.4 Error Hierarchy — Pattern Only, Not Content

FastPII has 21 domain-specific error classes (`DetectionError`, `WaitlistError`, etc.) — none generic enough for upstream. What goes upstream:

- `EncryptionError` and `DecryptionError` (supporting 1.1)
- `QuotaExceededError` (supporting billing)
- `PolicyViolationError` (supporting RBAC/policy engine)
- A FastAPI exception handler that catches `SwXError` and returns structured JSON

### 4.5 Plaintext Security Gaps Confirmed

| Model | Field | Status |
|-------|-------|--------|
| `WebhookEndpoint` | `secret` (max 500) | **Plaintext in DB**. `secret_masked` exists on `WebhookEndpointPublic` but storage is unprotected. |
| `SSOProvider` | `client_secret` (max 1000), `certificate` (max 5000) | **Plaintext in DB**. `_to_public()` masks both to "***" but at-rest is unprotected. |
| `RefreshToken` | `token` | **Plaintext in DB**. JWT stored verbatim — replayable until expiry/revocation. |
| `LLMProviderConfig` | `credentials` (JSONB) | **Env-placeholder only** — no encrypted storage for BYOK. |

### 4.6 Security Headers Middleware Blocks SSE

Current `SecurityHeadersMiddleware` uses `BaseHTTPMiddleware` which consumes the response body, **breaking SSE streaming endpoints**. This is a production bug for any SwX app doing LLM streaming.

### 4.7 Circuit Breaker Has No Async Lock

`CircuitBreaker` in `resilience.py` has `allow_request()`, `record_success()`, `record_failure()` — all synchronous methods called from async contexts. Under high concurrency, multiple coroutines can read/write state simultaneously, causing inconsistent state transitions. This is a **real production bug**.

---

## 5. Dependency Graph

```
Phase 1 (Week 1):
  3.12 Circuit breaker lock ── independent (BUG FIX, do first)
  1.1  EncryptionService ─────┐
  1.2  Webhook secrets ───────┤── depends on 1.1
  1.3  SSO secrets ───────────┤── depends on 1.1
  1.4  Refresh tokens ────────┘── depends on 1.1
  1.5  Security headers + CSRF ── independent

Phase 2 (Week 2):
  2.1  LLM adapters (extend existing) ── independent
  2.2  CredentialSource / BYOK ──────────── depends on 1.1
  2.4  Provider validation ──────────────── depends on 2.1
  3.10 LazyProxy ────────────────────────── independent
  3.11 Rate limit headers ───────────────── independent

Phase 3 (Week 3):
  2.3  Structured SSE ────────── depends on 2.1
  2.5  Provider catalog ──────── depends on 2.1
  2.6  Prompt injection ──────── independent
  3.7  ServiceTokenGuard ─────── independent
  3.8  Combined auth guard ───── depends on existing guards
  3.5  Audit retention ────────── independent

Phase 4 (Week 4):
  3.3  CacheService ──────────── independent
  3.1  Audit event queue ─────── independent
  3.2  Three-tier cache ──────── depends on 3.3
  3.4  Compliance report ─────── independent
  3.6  Onboarding ────────────── independent
  3.9  Error hierarchy ───────── independent

Phase 5 (Rolling):
  3.13 Fallback chain ────── depends on 3.12
  3.14 Region routing ────── independent
  3.15 Auth rate limiting ─── independent
```

---

## 6. Execution Phases

### Phase 1 — Security & Bug Fix (Week 1)

| Order | Item | Files | Est. LOC | Breaking? |
|-------|------|-------|----------|-----------|
| 1 | 3.12 Circuit breaker lock | `swx_core/services/llm/resilience.py` | ~15 | No |
| 2 | 1.1 EncryptionService | `swx_core/security/encryption.py` (NEW), `settings.py`, `pyproject.toml`, `__init__.py` | ~190 | No |
| 3 | 1.2 Webhook secrets | `swx_core/services/webhook/`, `swx_core/models/webhook_endpoint.py` | ~40 | No |
| 4 | 1.3 SSO secrets | `swx_core/services/sso/`, `swx_core/models/sso_provider.py` | ~40 | No |
| 5 | 1.4 Refresh tokens | `swx_core/security/refresh_token_service.py`, `swx_core/models/refresh_token.py` | ~30 | No |
| 6 | 1.5a Security headers | `swx_core/middleware/security_headers_middleware.py` (REPLACE), `settings.py` (ADD config) | ~120 | **Yes** — replaces class |
| 7 | 1.5b CSRF lifecycle | `swx_core/middleware/csrf_middleware.py` (MODIFY) | ~80 | No — additive |

### Phase 2 — LLM + Quick Wins (Week 2)

| Order | Item | Files | Est. LOC | Breaking? |
|-------|------|-------|----------|-----------|
| 8 | 2.1 LLM adapter extension | `swx_core/services/llm/providers/__init__.py`, `contracts/llm.py` | ~80 | No — additive |
| 9 | 2.2 CredentialSource / BYOK | `swx_core/models/llm_provider_config.py`, `llm_service.py`, `config_resolver.py`, migration | ~120 | No — additive columns |
| 10 | 2.4 Provider validation | `swx_core/services/llm/llm_service.py`, route | ~60 | No |
| 11 | 3.10 LazyProxy | `swx_core/utils/lazy.py` (NEW) | ~60 | No |
| 12 | 3.11 Rate limit headers | `swx_core/middleware/rate_limit_headers.py` (NEW) | ~20 | No |

### Phase 3 — SSE + Guards + Retention (Week 3)

| Order | Item | Files | Est. LOC | Breaking? |
|-------|------|-------|----------|-----------|
| 13 | 2.3 Structured SSE | `swx_core/contracts/llm.py`, `llm_service.py`, all providers | ~100 | **Yes** — `stream()` return type |
| 14 | 2.5 Provider catalog | `swx_core/services/llm/provider_catalog.py` (NEW) | ~140 | No |
| 15 | 2.6 Prompt injection | `swx_core/services/safety/prompt_injection.py` (NEW) | ~130 | No |
| 16 | 3.7 ServiceTokenGuard | `swx_core/guards/service_token_guard.py` (NEW) | ~70 | No |
| 17 | 3.8 Combined auth guard | `swx_core/guards/combined_auth_guard.py` (NEW) | ~170 | No |
| 18 | 3.5 Audit retention | `swx_core/services/audit/audit_retention_service.py` (NEW) | ~60 | No |

### Phase 4 — Cache + Audit + Compliance (Week 4)

| Order | Item | Files | Est. LOC | Breaking? |
|-------|------|-------|----------|-----------|
| 19 | 3.3 CacheService | `swx_core/services/cache/cache_service.py` (NEW) | ~120 | No |
| 20 | 3.1 Audit event queue | `swx_core/services/audit/audit_event_queue.py` (NEW) | ~80 | No |
| 21 | 3.2 Three-tier cache | `swx_core/services/cache/tenant_config_cache.py` (NEW) | ~150 | No |
| 22 | 3.4 Compliance report | `swx_core/services/compliance/compliance_report_service.py` (NEW) | ~200 | No |
| 23 | 3.6 Onboarding | `swx_core/services/onboarding/` (NEW), `swx_core/models/onboarding.py` (NEW), migration | ~200 | No |
| 24 | 3.9 Error hierarchy | `swx_core/utils/errors.py` (EXTEND) | ~80 | No — additive |

### Phase 5 — Fallback + Routing + Rate Limiting (Rolling)

| Order | Item | Files | Est. LOC | Breaking? |
|-------|------|-------|----------|-----------|
| 25 | 3.13 Fallback chain | `swx_core/services/llm/fallback_service.py` (NEW) | ~170 | No |
| 26 | 3.14 Region routing | `swx_core/middleware/region_routing.py` (NEW) | ~80 | No |
| 27 | 3.15 Auth rate limiting | `swx_core/middleware/auth_rate_limit.py` (NEW) | ~130 | No |

---

## 7. Ticket Tracker

### Legend
- `[ ]` Pending
- `[~]` In Progress
- `[x]` Completed
- `[!]` Blocked

### Phase 1 — Security & Bug Fix

- `[x]` **[3.12]** swx_core/services/llm/resilience.py: Add `asyncio.Lock` to CircuitBreaker state transitions — thread-safe concurrent state changes
- `[x]` **[1.1]** swx_core/security/encryption.py: Create `EncryptionService` with versioned Fernet + PBKDF2 key derivation + key rotation
- `[x]` **[1.1]** swx_core/config/settings.py: Add `SWX_ENCRYPTION_KEY`, `SWX_ENCRYPTION_KEY_PREVIOUS`, `SWX_ENCRYPTION_SALT` settings
- `[x]` **[1.1]** pyproject.toml: Add `cryptography>=42.0.0` dependency
- `[x]` **[1.1]** swx_core/security/__init__.py: Export `encrypt_value`, `decrypt_value`, `encrypt_api_key`, `decrypt_api_key`
- `[x]` **[1.2]** swx_core/services/webhook/: Encrypt `WebhookEndpoint.secret` on write, decrypt on read using EncryptionService
- `[x]` **[1.3]** swx_core/services/sso/: Encrypt `SSOProvider.client_secret` and `certificate` on write, decrypt on read
- `[x]` **[1.4]** swx_core/security/refresh_token_service.py: Encrypt `RefreshToken.token` on create, decrypt on verify/revoke
- `[x]` **[1.5a]** swx_core/middleware/security_headers_middleware.py: Replace `BaseHTTPMiddleware` with pure ASGI impl + `SecurityHeadersConfig` + SSE-aware CORP + CSP split
- `[x]` **[1.5b]** swx_core/middleware/csrf_middleware.py: Add cookie lifecycle (set on login/refresh, delete on logout, skip for Bearer/API-key auth, lazy-set if missing)
- `[x]` **[1.x]** Admin CLI command `swx security:encrypt-secrets` for encrypting existing plaintext secrets (webhook, SSO, refresh tokens, LLM API keys)

### Phase 2 — LLM + Quick Wins

- `[x]` **[2.1]** swx_core/services/llm/providers/: Audit existing adapters, add `validate_api_key()` and `list_models()` methods to `BaseLLMProvider` contract
- `[x]` **[2.1]** swx_core/contracts/llm.py: Add `validate_api_key()` and `list_models()` to `LLMProviderContract` ABC
- `[x]` **[2.2]** swx_core/models/llm_provider_config.py: Add `credential_source` and `encrypted_api_key` columns
- `[x]` **[2.2]** swx_core/services/llm/llm_service.py: Add `resolve_api_key()` branching on `credential_source` + encrypt on create/update
- `[x]` **[2.2]** swx_core/services/llm/config_resolver.py: Update to handle `encrypted_db` credential source
- `[x]` **[2.2]** Alembic migration: Additive columns (`credential_source` default `env_placeholder`, `encrypted_api_key` nullable)
- `[x]` **[2.4]** swx_core/services/llm/llm_service.py: Add `validate_provider()` and `list_provider_models()` methods
- `[x]` **[2.4]** swx_core/routes/admin/llm_route.py: Add `POST /admin/llm/providers/{id}/validate` and `GET /admin/llm/providers/{id}/models` routes
- `[x]` **[3.10]** swx_core/utils/lazy.py: Create `LazyProxy` utility for deferred module imports
- `[x]` **[3.11]** swx_core/middleware/rate_limit_headers.py: Create middleware reading `X-RateLimit-*` from `request.state`

### Phase 3 — SSE + Guards + Retention

- `[x]` **[2.3]** swx_core/contracts/llm.py: Add `SSEEvent` dataclass with `text_delta`, `usage`, `error`, `done` types
- `[x]` **[2.3]** swx_core/services/llm/llm_service.py: Update `stream()` to yield `SSEEvent`, extract real usage from provider `usage` events
- `[x]` **[2.3]** swx_core/services/llm/providers/: Update all 4 providers to yield `SSEEvent`
- `[x]` **[2.5]** swx_core/services/llm/provider_catalog.py: Create `get_provider_catalog()` reading from `SystemConfig` + Redis cache + static fallback
- `[x]` **[2.6]** swx_core/services/safety/prompt_injection.py: Regex-based detector with 12 default patterns, risk scoring, `detect_injection()` + `PromptInjectionDetector` class, SystemConfig overrides with regex patterns + risk scoring
- `[x]` **[3.7]** swx_core/guards/service_token_guard.py: `ServicePrincipal` dataclass + `ServiceTokenDep` FastAPI dependency validating `X-Service-Token`
- `[x]` **[3.8]** swx_core/guards/combined_auth_guard.py: `AuthenticatedUserDep` (JWT→API-key fallback) + `OptionalAuthenticatedUserDep`, `auth_mode` metadata, normalizing to `AuthenticatedUser` with `auth_mode`
- `[x]` **[3.5]** swx_core/services/audit/audit_retention_service.py: Batch-delete audit rows older than `SWX_AUDIT_RETENTION_DAYS` with dry-run support with batch deletion + `SWX_AUDIT_RETENTION_DAYS` setting

### Phase 4 — Cache + Audit + Compliance

- `[x]` **[3.3]** swx_core/services/cache/cache_service.py: `CacheService` with Redis + in-memory fallback + `get_or_set` with async factory
- `[x]` **[3.1]** swx_core/services/audit/audit_event_queue.py: `AuditEventQueue` with `asyncio.Queue(maxsize=10_000)` + background drain worker + overflow drop + lifespan wiring
- `[x]` **[3.2]** swx_core/services/cache/tenant_config_cache.py: `TenantConfigCache` with L1/L2/L3 lookup + Redis pub/sub L1 invalidation
- `[x]` **[3.4]** swx_core/services/compliance/compliance_report_service.py: `ComplianceReport` with scored readiness reports for GDPR/HIPAA/CCPA/DORA/FERPA
- `[x]` **[3.6]** swx_core/services/onboarding/ + models/onboarding.py: Create `OnboardingService` with step tracking + completion percentage
- `[x]` **[3.6]** Alembic migration: Add `swx_onboarding_step` table
- `[x]` **[3.9]** swx_core/utils/errors.py: Extended with `EncryptionError`, `DecryptionError`, `QuotaExceededError`, `PolicyViolationError` + FastAPI exception handler in `main.py`

### Phase 5 — Fallback + Routing + Rate Limiting

- `[x]` **[3.13]** swx_core/services/llm/fallback_service.py: Create `FallbackChain` service with provider priority + retry/stop logic
- `[x]` **[3.14]** swx_core/middleware/region_routing.py: Create `RegionRoutingMiddleware` with configurable region definitions
- `[x]` **[3.15]** swx_core/middleware/auth_rate_limit.py: Create `RateLimitRule` dataclass + `AuthRateLimitMiddleware` with declarative per-path rules

### Cross-Cutting

- `[~]` **[TESTS]** Create test suite for all new modules (fallback_service done; remaining tests in progress)
- `[x]` **[CODE-CLARITY]** Apply code-clarity review to each implemented module
- `[x]` **[DOCS]** Update `docs/` for each new feature

---

## 8. Per-Feature Specifications

### [3.12] Async Circuit Breaker Lock

**File:** `swx_core/services/llm/resilience.py` (MODIFY)

**What:** Add `asyncio.Lock` to `CircuitBreaker` state transitions to prevent race conditions under high concurrency.

**Changes:**
- Add `self._lock = asyncio.Lock()` to `CircuitBreaker.__init__()`
- Make `allow_request()`, `record_success()`, `record_failure()` async
- Wrap state reads/writes with `async with self._lock:`
- Update all callers in `llm_service.py` and `retry_with_backoff()`

**Code-clarity:** Surgical change only. No refactoring of existing state machine logic.

**Tests:** Concurrent state transitions don't corrupt state.

---

### [1.1] EncryptionService

**File:** `swx_core/security/encryption.py` (NEW, ~190 LOC)

**What:** Versioned Fernet encryption with PBKDF2 key derivation and dual-key rotation window.

**SwX Pattern:** New module in `swx_core/security/`, reads from `swx_core.config.settings`.

**Port from:** `apps/backend/api/swx_app/security/encryption.py` (187 LOC)

**Changes from reference:**
- Remove `_LEGACY_SALT = b"fastpii-api-key-encryption"` → use `SWX_ENCRYPTION_SALT` default `b"swx-default-encryption-salt"`
- Remove fallback to `SECRET_KEY` in `_config_signature()` — encryption keys must be explicitly configured
- Add `SWX_` prefix to env vars: `SWX_ENCRYPTION_KEY`, `SWX_ENCRYPTION_KEY_PREVIOUS`, `SWX_ENCRYPTION_SALT`
- Replace `_setting()` dual lookup (settings attr then env var) with pydantic-settings directly
- Service raises `EncryptionError` on use if keys not configured (not on import)
- Export `encrypt_value`, `decrypt_value`, `encrypt_api_key`, `decrypt_api_key` from `__init__.py`

**Settings (settings.py):**
```python
SWX_ENCRYPTION_KEY: str | None = None
SWX_ENCRYPTION_KEY_PREVIOUS: str | None = None
SWX_ENCRYPTION_SALT: str = "swx-default-encryption-salt"
```

**Dependency:** `cryptography>=42.0.0` (already transitive via `passlib`)

**Tests:** Key rotation round-trip, empty ciphertext, missing key, version prefix parsing, dual-key decrypt window.

---

### [1.2] Encrypted Webhook Secrets

**Files:** `swx_core/services/webhook/` (MODIFY), `swx_core/models/webhook_endpoint.py` (MODIFY)

**What:** Encrypt `WebhookEndpoint.secret` on write, decrypt on read.

**SwX Pattern:** Encrypt in service layer before persist, decrypt on read. Column stays `str`.

**Pattern:**
```python
# In webhook service create/update
encrypted_secret = encrypt_value(data["secret"])
# In webhook service read
decrypted_secret = decrypt_value(instance.secret)
# In _to_public, mask the decrypted value
```

**Migration:** Alembic data migration iterating rows, detecting plaintext (non-Fernet-shaped), encrypting in-place.

**Code-clarity:** Detect plaintext vs encrypted using Fernet token prefix (`gAAAA`). If already encrypted, skip.

---

### [1.3] Encrypted SSO Secrets

**Files:** `swx_core/services/sso/sso_provider_service.py` (MODIFY), `swx_core/models/sso_provider.py` (MODIFY)

**What:** Encrypt `SSOProvider.client_secret` and `SSOProvider.certificate` at rest.

**Pattern:** Same as 1.2. Encrypt in `sso_provider_service.create()` and `update()`. Decrypt before masking in `_to_public()`.

---

### [1.4] Encrypted Refresh Tokens

**Files:** `swx_core/security/refresh_token_service.py` (MODIFY), `swx_core/models/refresh_token.py` (MODIFY)

**What:** Encrypt `RefreshToken.token` on create, decrypt on verify/revoke.

**Pattern:** Encrypt on create. On verify/revoke, detect if already encrypted (Fernet prefix) and decrypt before JWT validation.

**Code-clarity:** The token is a JWT string — Fernet handles it. Fernet-shape detection works for "already-encrypted vs plaintext" decision.

---

### [1.5a] ASGI Security Headers Middleware

**File:** `swx_core/middleware/security_headers_middleware.py` (REPLACE, ~120 LOC)

**What:** Replace `BaseHTTPMiddleware` with pure ASGI implementation. Add `SecurityHeadersConfig`, SSE-aware CORP, CSP split, COOP/COEP.

**Port from:** `apps/backend/api/swx_app/middleware/security_headers.py` (117 LOC)

**Changes from reference:**
- Remove `importlib.import_module("swx_app.config.security")` — use `swx_core.config.settings` directly
- Add `SecurityHeadersConfig` dataclass in `swx_core/config/settings.py`
- SSE response detection: `content-type.startswith("text/event-stream")` → `Cross-Origin-Resource-Policy: cross-origin`
- API route CSP: `default-src 'none'` with connect-src from config
- HTML docs route: no CSP (docs need inline scripts)
- `X-XSS-Protection: 0` (modern best practice — header is deprecated)
- Env-configurable via `SecurityHeadersConfig`

**Breaking:** Replaces `SecurityHeadersMiddleware` class. `setup_security_headers(app)` function signature stays the same.

---

### [1.5b] CSRF Cookie Lifecycle

**File:** `swx_core/middleware/csrf_middleware.py` (MODIFY, ~80 LOC added)

**What:** Extend existing CSRF middleware with lifecycle management:
1. Auto-set CSRF cookie on login / refresh-token paths
2. Auto-delete on logout
3. Skip validation when Bearer or API-key auth is present
4. Lazy-set if auth cookies exist but CSRF cookie is missing

**Port from:** `apps/backend/api/swx_app/middleware/csrf.py` (lines 59-82)

**Changes from reference:**
- Make cookie names configurable (remove hardcoded `swx_access_token`, `swx_refresh_token`)
- Make auth route paths configurable (remove hardcoded `/api/v1/auth/...`)
- Settings: `SWX_CSRF_LOGIN_PATHS`, `SWX_CSRF_LOGOUT_PATHS`, `SWX_CSRF_REFRESH_PATHS`

---

### [2.1] LLM Adapter Extension

**Files:** `swx_core/services/llm/providers/__init__.py`, `swx_core/contracts/llm.py`, all 4 providers

**What:** Add `validate_api_key()` and `list_models()` methods to `BaseLLMProvider` and `LLMProviderContract`. Update all 4 existing providers.

**Code-clarity:** Each provider returns `ValidateProviderResult(valid: bool, models: list[str], error: str | None)`. Pure function, no side effects.

---

### [2.2] CredentialSource / BYOK

**Files:** `swx_core/models/llm_provider_config.py` (MODIFY), `swx_core/services/llm/llm_service.py` (MODIFY), `swx_core/services/llm/config_resolver.py` (MODIFY), migration

**What:** Add `credential_source` and `encrypted_api_key` columns. Branch on `credential_source` in `resolve_api_key()`.

**Schema migration:**
```sql
ALTER TABLE swx_llm_provider_config ADD COLUMN credential_source VARCHAR(20) DEFAULT 'env_placeholder';
ALTER TABLE swx_llm_provider_config ADD COLUMN encrypted_api_key TEXT NULL;
```

**Code-clarity:** Use dispatch dict or match statement for `credential_source` resolution. No nested ifs.

---

### [2.3] Structured SSE Event Streaming

**Files:** `swx_core/contracts/llm.py` (MODIFY), `swx_core/services/llm/llm_service.py` (MODIFY), all providers (MODIFY)

**What:** Add `SSEEvent` dataclass. Change `stream()` return type from `AsyncGenerator[str, None]` to `AsyncGenerator[SSEEvent, None]`.

**SSEEvent types:**
- `text_delta` — chunk of completion text
- `usage` — token usage stats (prompt_tokens, completion_tokens, total_tokens)
- `error` — mid-stream error with code and message
- `done` — terminal event

**Breaking:** Changes `stream()` return type. Gate behind `settings.LLM_STRUCTURED_SSE: bool = True` for one release.

**Code-clarity:** Fix `llm_service.py:116` — currently logs `(0, 0, 0)` for streaming usage. Extract actual usage from provider chunk and emit `usage` event.

---

### [2.4] Provider Validation Without Save

**Files:** `swx_core/services/llm/llm_service.py` (ADD method), `swx_core/routes/admin/` (ADD route)

**What:** `validate_provider()` method that builds temporary adapter, validates key, lists models — without persisting.

**Route:** `POST /admin/llm/providers/validate` — requires `admin:llm:write` permission.

---

### [2.5] DB-Driven Provider Catalog

**File:** `swx_core/services/llm/provider_catalog.py` (NEW, ~140 LOC)

**What:** Read supported providers from `SystemConfig` (category `PROVIDER_CATALOG`), Redis-cached for 1 hour, fallback to static `LLM_PROVIDER_DEFAULTS`.

**Code-clarity:** Simple Redis TTL cache. No need for three-tier cache here — 1 hour TTL is sufficient for a provider catalog.

---

### [2.6] Prompt Injection Detector

**File:** `swx_core/services/safety/prompt_injection.py` (NEW, ~130 LOC)

**What:** Regex-based detector with 12 default patterns covering instruction override, role manipulation, jailbreak. Risk scoring: `MEDIUM` / `HIGH` / `CRITICAL`. Configurable patterns via `SystemConfig`.

**Port from:** `apps/gateway/gateway/inspection/injection_detector.py` (117 LOC)

**Changes:** Remove `WorkspaceConfigCache` dependency. Make pattern list a module-level default, overridable via `SystemConfig`. Export both `detect_injection(text, patterns=None)` function and `PromptInjectionDetector` class.

---

### [3.10] LazyProxy

**File:** `swx_core/utils/lazy.py` (NEW, ~60 LOC)

**What:** `_LazyProxy` class that defers module import until first attribute access. `lazy_controller("module.path", "ClassName")` convenience function.

**Port from:** `apps/backend/api/swx_app/utils/lazy.py` (56 LOC) — nearly drop-in, zero dependencies.

---

### [3.11] Rate Limit Headers Middleware

**File:** `swx_core/middleware/rate_limit_headers.py` (NEW, ~20 LOC)

**What:** Read `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` from `request.state` and attach to response.

**Code-clarity:** Trivially simple. 13 lines in reference, ~20 with docstrings.

---

### [3.7] ServiceTokenGuard

**File:** `swx_core/guards/service_token_guard.py` (NEW, ~70 LOC)

**What:** FastAPI dependency validating `X-Service-Token` header against `SWX_SERVICE_TOKEN` setting. Returns `ServicePrincipal` dataclass.

**Changes from reference:** Remove `GATEWAY_SERVICE_TOKEN` env var. Remove hardcoded `gateway` identity. Make scopes configurable via settings.

---

### [3.8] Combined JWT-or-API-key Guard

**File:** `swx_core/guards/combined_auth_guard.py` (NEW, ~170 LOC)

**What:** `get_authenticated_user()` that tries JWT first (via `get_jwt_user_optional`), falls back to API key. Normalizes to `AuthenticatedUser` with `auth_mode: Literal["jwt", "api_key"]`.

**Code-clarity:** Compose existing guards via `GuardManager`. Early return on success. No nested conditionals.

---

### [3.5] Audit Retention Service

**File:** `swx_core/services/audit/audit_retention_service.py` (NEW, ~60 LOC)

**What:** Batch-delete audit rows older than `SWX_AUDIT_RETENTION_DAYS`. Optional anonymization before deletion.

**Settings:** `SWX_AUDIT_RETENTION_DAYS: int | None = None` — when set, enables nightly scheduled job.

---

### [3.3] CacheService

**File:** `swx_core/services/cache/cache_service.py` (NEW, ~120 LOC)

**What:** `get()`, `set()`, `delete()`, `get_or_set(key, factory, ttl)` with async factory support. Redis primary, in-memory fallback when Redis is unreachable.

**Code-clarity:** `get_or_set` with async factory — check cache, if miss call factory, set result. Early return on cache hit.

---

### [3.1] Audit Event Queue

**File:** `swx_core/services/audit/audit_event_queue.py` (NEW, ~80 LOC)

**What:** `asyncio.Queue(maxsize=10_000)` with background drain worker. `put_nowait()` (drops on overflow). Wires into FastAPI lifespan.

**Code-clarity:** Background task lifecycle: start in lifespan startup, drain on shutdown. Document overflow tradeoff. Add `queue_depth` metric for alerting.

---

### [3.2] Three-tier Config Cache

**File:** `swx_core/services/cache/tenant_config_cache.py` (NEW, ~150 LOC)

**What:** L1 in-memory dict (<1ms) → L2 Redis (<5ms) → L3 DB/SettingsService (<30ms). Single source of truth for tenant/team/org config.

**Code-clarity:** L1 is per-process, L2 is shared, L3 is source of truth. Document per-process L1 consistency tradeoff. Redis pub/sub for L1 invalidation.

---

### [3.4] Compliance Report Service

**File:** `swx_core/services/compliance/compliance_report_service.py` (NEW, ~200 LOC)

**What:** Scored compliance readiness reports for GDPR/HIPAA/CCPA/DORA/FERPA. Reads from existing audit log tables. Each framework has sections scored from audit data.

**Naming:** "compliance readiness score" not "compliance score" — measuring evidence availability, not certification.

---

### [3.6] Onboarding Service

**Files:** `swx_core/services/onboarding/` (NEW), `swx_core/models/onboarding.py` (NEW), migration

**What:** Per-user onboarding step tracking. Initialize N steps, mark complete/skipped, compute completion percentage.

**Schema:** `swx_onboarding_step` table: `id`, `user_id`, `step_key`, `status` (pending/completed/skipped), `completed_at`, `created_at`.

**Code-clarity:** Step definitions registered, not hardcoded. `OnboardingService` uses `BaseService`.

---

### [3.9] Error Hierarchy Extension

**File:** `swx_core/utils/errors.py` (MODIFY)

**What:** Add to existing hierarchy:
- `EncryptionError(SwXError)` — status 500, code `ENCRYPTION_ERROR`
- `DecryptionError(EncryptionError)` — status 400, code `DECRYPTION_ERROR`
- `QuotaExceededError(SwXError)` — status 429, code `QUOTA_EXCEEDED`
- `PolicyViolationError(SwXError)` — status 403, code `POLICY_VIOLATION`

Plus FastAPI exception handler:
```python
@app.exception_handler(SwXError)
async def swx_error_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())
```

**Code-clarity:** Each class minimal — `__init__` with sensible defaults. No redundant nesting. Handler maps `SwXError.to_dict()` to `JSONResponse`.

---

### [3.13] Fallback Chain Service

**File:** `swx_core/services/llm/fallback_service.py` (NEW, ~170 LOC)

**What:** Try providers in priority order, retry on 5xx/timeout, stop on 4xx, enforce max attempts.

**Code-clarity:** Pure iteration with early return on success or 4xx. No nested conditions. Composes with `CircuitBreaker` from 3.12.

---

### [3.14] Region Routing Middleware

**File:** `swx_core/middleware/region_routing.py` (NEW, ~80 LOC)

**What:** `RegionRoutingMiddleware` + `resolve_region()` mapping workspace/country to target region. Opt-in: no-op if no regions configured.

**Settings:** `SWX_REGIONS: dict | None = None`, `SWX_REGION_HEADER: str = "CF-IPCountry"`.

**Code-clarity:** Early return if no regions configured. Region resolution is a pure function.

---

### [3.15] Path-aware Auth Rate Limiting

**File:** `swx_core/middleware/auth_rate_limit.py` (NEW, ~130 LOC)

**What:** `RateLimitRule` dataclass (`namespace`, `path_prefix`, `methods`, `exact_path`) with `matches(request)` method. `AuthRateLimitMiddleware` applying a list of rules.

**Port from:** `apps/backend/api/swx_app/middleware/auth_rate_limit.py` (118 LOC)

**Changes:** Make rule list configurable via settings. Don't hardcode FastPII-specific paths. Rule matching is a single expression per rule.

---

## 9. Migration Strategy

### For Encrypted Secrets (1.2, 1.3, 1.4)

**Recommended approach:** Admin command (`swx security:encrypt-secrets`) as primary path.

**Why:** An automatic Alembic data migration that encrypts rows in-place risks data loss if `SWX_ENCRYPTION_KEY` is misconfigured. An admin command is explicit and auditable.

**Fallback:** Optional Alembic hook that *verifies* the key is correct before encrypting.

**Plaintext detection:** Fernet tokens start with `gAAAA` and have a recognizable shape. Detect non-Fernet values to identify unencrypted rows.

```python
# Detection pattern
FERNET_TOKEN_PATTERN = re.compile(r'^gAAAA[A-Za-z0-9_-]+=*$')

def is_encrypted(value: str) -> bool:
    return bool(FERNET_TOKEN_PATTERN.match(value))
```

### For CredentialSource / BYOK (2.2)

**Additive migration** — nullable new columns with defaults:
```sql
ALTER TABLE swx_llm_provider_config
  ADD COLUMN credential_source VARCHAR(20) DEFAULT 'env_placeholder',
  ADD COLUMN encrypted_api_key TEXT NULL;
```

Existing rows keep working unchanged. `credential_source` defaults to `env_placeholder`.

### For Onboarding (3.6)

**New table migration:**
```sql
CREATE TABLE swx_onboarding_step (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES swx_user(id),
  step_key VARCHAR(100) NOT NULL,
  status VARCHAR(20) DEFAULT 'pending',
  completed_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, step_key)
);
```

### For Structured SSE (2.3)

**No schema migration.** The change is in the `stream()` return type. Gate behind `settings.LLM_STRUCTURED_SSE: bool = True` for one release. Consumers can opt in.

---

## 10. Testing Strategy

### Per-Module Test Requirements

Every new module requires:

1. **Unit tests** — test the module in isolation with mocks for external dependencies
2. **Integration tests** — test the module wired into the SwX app (where applicable)
3. **Edge cases** — empty inputs, None values, boundary conditions
4. **Backward compatibility** — existing tests must continue to pass

### Test File Mapping

| Module | Test File |
|--------|-----------|
| EncryptionService | `tests/security/test_encryption.py` |
| Webhook secret encryption | `tests/services/test_webhook_services.py` |
| SSO secret encryption | `tests/services/test_sso_services.py` |
| Refresh token encryption | `tests/security/test_refresh_token_service.py` |
| Security headers (ASGI) | `tests/middleware/test_security_headers.py` |
| CSRF lifecycle | `tests/middleware/test_csrf.py` |
| Circuit breaker lock | `tests/services/llm/test_resilience.py` |
| LLM adapter extension | `tests/services/llm/test_providers.py` |
| BYOK credentials | `tests/services/test_llm_events.py` |
| Structured SSE | `tests/services/llm/test_streaming.py` |
| Provider validation | `tests/services/llm/test_validation.py` |
| Provider catalog | `tests/services/llm/test_provider_catalog.py` |
| Prompt injection | `tests/services/safety/test_prompt_injection.py` |
| LazyProxy | `tests/utils/test_lazy.py` |
| Rate limit headers | `tests/middleware/test_rate_limit_headers.py` |
| ServiceTokenGuard | `tests/guards/test_service_token_guard.py` |
| Combined auth guard | `tests/guards/test_combined_auth_guard.py` |
| Audit retention | `tests/services/audit/test_audit_retention.py` |
| CacheService | `tests/services/cache/test_cache_service.py` |
| Audit event queue | `tests/services/audit/test_audit_event_queue.py` |
| Tenant config cache | `tests/services/cache/test_tenant_config_cache.py` |
| Compliance report | `tests/services/compliance/test_compliance_report_service.py` |
| Onboarding | `tests/services/onboarding/test_onboarding_service.py` |
| Error hierarchy | `tests/utils/test_errors.py` |
| Fallback chain | `tests/services/llm/test_fallback_service.py` |
| Region routing | `tests/middleware/test_region_routing.py` |
| Auth rate limiting | `tests/middleware/test_auth_rate_limit.py` |

### Test Execution

```bash
# Run all tests
pytest tests/ -v

# Run specific module tests
pytest tests/security/test_encryption.py -v

# Run with coverage
pytest tests/ --cov=swx_core --cov-report=html

# Run only new module tests
pytest tests/security/ tests/middleware/ tests/guards/ tests/services/llm/ tests/services/cache/ tests/services/audit/ tests/services/compliance/ tests/services/onboarding/ tests/services/safety/ tests/utils/ -v
```

---

## Changelog

| Date | Phase | Item | Status |
|------|-------|------|--------|
| 2026-08-03 | — | Plan created, tickets defined | Done |
| 2026-08-03 | Phase 4 | 3.6 Onboarding service + model + migration | Done |
| 2026-08-03 | Phase 5 | 3.13 Fallback chain service | Done |
| 2026-08-03 | Phase 5 | 3.14 Region routing middleware | Done |
| 2026-08-03 | Phase 5 | 3.15 Auth rate limiting middleware | Done |