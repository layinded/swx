# SwX-Core Billing & Payments Implementation Plan

**Source:** AfCloud Platform Team feature request (`SWX_CORE_FEATURE_REQUEST.md`)
**Created:** 2026-08-22
**Status:** Planning
**Reference repo:** `swx-core-release` (SwX-API v2.22.3)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [SwX Pattern Constraints](#2-swx-pattern-constraints)
3. [Code-Clarity Principles](#3-code-clarity-principles)
4. [Key Discoveries](#4-key-discoveries)
5. [Dependency Graph](#5-dependency-graph)
6. [Execution Waves](#6-execution-waves)
7. [Ticket Tracker](#7-ticket-tracker)
8. [Per-Feature Specifications](#8-per-feature-specifications)
9. [Migration Strategy](#9-migration-strategy)
10. [Testing Strategy](#10-testing-strategy)

---

## 1. Executive Summary

This plan implements the AfCloud feature request for user-facing billing, payments, subscriptions, quota, and webhook capabilities in SwX-Core v2.22.3. The request identifies a **P0 security vulnerability** (client-supplied payment amounts) and a **session deadlock** in custom controllers that mix DB reads with outbound HTTP calls.

**Four priority waves:**

- **Wave 1 — P0 Security & Foundation** (4 items): Closes the amount-spoofing vulnerability with server-side price validation, ships the Paystack webhook handler, and provides the session-deadlock fix + currency conversion utility that everything else depends on.
- **Wave 2 — P1 Billing Surface** (9 items): User-facing transaction history, public plan catalog, subscription lifecycle endpoints, quota status, credit pack purchase, and the Flutterwave webhook.
- **Wave 3 — P2 Completeness** (12 items): Wallet debit/transfer user endpoints, Stripe webhook extension, webhook idempotency table, subscription renewal failure handling, usage metering, and developer-experience fixes/docs.
- **Wave 4 — P3 Advanced** (9 items): Referral system, dual-control adjustments, wallet priority, credit expiry, API key rotation, audit retention, GDPR export/deletion.

**Adjustments from the feature request:**

1. **6.5 (user-facing subscription status) merged into 3.3** — they are the same endpoint (`GET /api/user/billing/subscriptions/current`).
2. **6.1 / 6.2 (signature + session docs) folded into Wave 3** as developer-experience tasks, not separate deliverables.
3. **2.4 (webhook idempotency table) promoted ahead of 2.2** — the `swx_webhook_delivery` table is the durable idempotency store that Paystack/Flutterwave/Stripe handlers share; Redis-only idempotency (current Stripe pattern) is insufficient for at-least-once delivery guarantees.
4. **Session-deadlock fix (5.1) is Wave 1** — it is a hard dependency of 1.1 (server-side payment init) and every webhook handler that credits wallets.
5. **6.3 (currency conversion utility) is Wave 1** — 1.1 and 2.1 both depend on kobo→nano / major→nano conversion.

---

## 2. SwX Pattern Constraints

Every feature MUST respect these rules (confirmed against the v2.22.3 codebase):

| Rule | Enforcement |
|------|-------------|
| **CSR Architecture** | Route → Controller → Service → Repository → Model. No skipping layers. Routes call controllers; controllers call services; services call repositories. |
| **Domain Separation** | Admin `/admin/*` (uses `AdminUserDep` / `get_current_admin_user`), User `/user/*` (uses `UserDep`), Webhooks `/webhooks/*` (no auth, signature-verified). |
| **Controller Style** | Thin async functions in `swx_core/controllers/`, named `*_controller(session, ...)`. They do NOT contain business logic — they delegate to services. |
| **Service Style** | Business logic in `swx_core/services/billing/`. Functions take `AsyncSession` as first arg (e.g. `wallet_service.credit_wallet(session, ...)`). |
| **Repository Style** | Data access in `swx_core/repositories/`. Plain async functions taking `AsyncSession`. `BaseRepository[Model]` available for generic CRUD. |
| **Model Style** | SQLModel tables in `swx_core/models/`, `__tablename__` prefixed `swx_*`. Public schemas are `*Public(SQLModel)` with `class Config: from_attributes = True`. |
| **Error Hierarchy** | Raise `SwXError` subclasses from `swx_core/utils/errors.py` — NOT raw `HTTPException`. `QuotaExceededError`, `NotFoundError`, `ForbiddenError`, `ConflictError` already exist. FastAPI handler registered in `main.py`. |
| **Event-Driven** | Emit events for state changes via `swx_core.events.event_bus` (`await event_bus.dispatch("wallet.credit", payload={...})`). |
| **Settings** | All config in `swx_core/config/settings.py` via `Settings(BaseSettings)`. Payment secrets use `${ENV_VAR}` placeholder pattern resolved by `config_resolver.resolve_config()`. |
| **Route Registration** | User routes aggregated in `swx_core/routes/user/__init__.py`; admin in `swx_core/routes/admin/`; webhooks via `swx_core/webhooks/`. Top-level `swx_core/router.py` includes all. |
| **Payment Providers** | Local providers (Paystack/Flutterwave/Mpesa) implement `LocalPaymentProvider` ABC in `swx_core/services/billing/providers/`. Resolved via `get_local_payment_provider(name)`. Stripe uses `StripeProvider` (separate `BillingProvider` ABC). |
| **Webhook Pattern** | Follow `swx_core/webhooks/stripe_webhook.py`: signature verification → idempotency check → replay protection → process. Return `200` for duplicates (not error) to stop provider retries. |
| **Naming** | `snake_case` files and functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants. Controllers end `_controller`. Services are modules. |

---

## 3. Code-Clarity Principles

Applied to every implemented module (per `@code-clarity` skill):

1. **Remove redundancy** — no duplicate conditions, no dead code, no unreachable branches.
2. **Simplify logic** — reduce nested conditions, use early returns and guard clauses. No `if True:` blocks.
3. **Preserve behavior** — no unintended functionality changes; all edge cases handled. No signature changes without explicit request.
4. **Meaningful names** — no `data`, `value`, `temp`, `result` when a specific name fits. Names reflect intent.
5. **No type suppression** — no `# type: ignore`, no `as any`, no `@ts-ignore`. (Existing `pyright: ignore` comments in models are pre-existing and out of scope unless the file is edited.)
6. **No empty catches** — every `except` block logs, re-raises, or recovers meaningfully.
7. **Verify after edit** — run `lsp_diagnostics` on every changed file; run adjacent tests.

**Core rule:** *If a condition does nothing, it doesn't belong.* Every branch, check, and variable must serve a purpose.

---

## 4. Key Discoveries

### 4.1 The Session Deadlock Root Cause (Confirmed)

`UserDep` (`swx_core/auth/user/dependencies.py`) depends on `SessionDep`, which is `Annotated[AsyncSession, Depends(get_async_db)]`. `get_async_db()` yields a session that lives for the **entire request lifecycle**.

When a route handler:
1. Uses `SessionDep` (directly or via `UserDep` / `require_permission`), AND
2. Performs a DB read (e.g. `BaseRepository.find_by()` on the injected session), AND
3. Then makes an outbound HTTP call (e.g. Paystack `initialize_payment`)

… the DB connection is held open for the duration of the HTTP call. Under load: `pool_size × slow HTTP calls = connection pool exhaustion = deadlock`.

**Why the existing `POST /payments/initialize` works:** It takes `amount_nano` from the request body and calls the provider directly — it does **zero DB reads** after auth, so the `UserDep` session sits idle (no active transaction holding a connection during the HTTP call).

**Fix (Option C — native controller session management):** New server-side-validated controllers (`initialize_payment_for_plan_controller`, `initialize_payment_for_pack_controller`) manage their **own short-lived session** for the DB read, close it, THEN make the HTTP call. Route handlers for these do NOT take `SessionDep`.

### 4.2 Existing Capabilities (Do Not Rebuild)

| Capability | Location | Status |
|------------|----------|--------|
| `wallet_service.credit_wallet` | `services/billing/wallet_service.py` | Exists, exposed at `POST /user/billing/wallets/{currency}/credit` |
| `wallet_service.debit_wallet` | `services/billing/wallet_service.py` | Exists, **NOT exposed** as user endpoint |
| `wallet_service.transfer` | `services/billing/wallet_service.py` | Exists, **NOT exposed** (only `convert_wallets` is) |
| `SubscriptionService.create_subscription` | `services/billing/subscription_service.py` | Exists, **NOT exposed** as user endpoint |
| `SubscriptionService.cancel_subscription` | `services/billing/subscription_service.py` | Exists, **NOT exposed** as user endpoint |
| `billing_repository.get_active_subscription` | `repositories/billing_repository.py` | Exists, **NOT exposed** |
| `billing_repository.get_user_billing_account` | `repositories/billing_repository.py` | Exists, used internally |
| `ledger_service.get_entry_history` | `services/ledger_service.py` | Exists, exposed only at `GET /admin/ledger/{account_id}/entries` |
| `PaystackProvider` | `services/billing/providers/paystack_provider.py` | Exists: `initialize_payment`, `verify_payment`, `refund` |
| `FlutterwaveProvider` | `services/billing/providers/flutterwave_provider.py` | Exists: same interface |
| Stripe webhook handler | `webhooks/stripe_webhook.py` | Exists: signature verify + Redis idempotency + replay protection |
| `QuotaExceededError` | `utils/errors.py` | Already added in prior wave |
| `RedisCache` / `get_cache()` | `utils/cache.py` | Exists, prefix `swx:` |
| `Plan` model | `models/billing.py` | Has `key`, `amount`, `currency`, `is_public`, `is_active`, `billing_interval` — sufficient for server-side price validation |

### 4.3 Missing Pieces (Must Create)

| Piece | Why |
|-------|-----|
| `swx_core/utils/currency.py` | No `major_to_nano(amount, currency)` utility exists. Kobo→nano and major→nano conversion is hand-rolled per provider. |
| `swx_core/database/session_helpers.py` | No `with_read_session()` helper for the DB-read-then-HTTP pattern. |
| `swx_core/models/webhook_delivery.py` | No `swx_webhook_delivery` table for durable webhook idempotency. |
| `swx_core/models/credit_pack.py` | No credit pack model (buy tokens without upgrading plan). |
| `swx_core/services/billing/quota_service.py` | No quota/usage window tracking (Redis rolling window). |
| `swx_core/services/billing/usage_metering_service.py` | No token usage metering with model-based cost calculation. |
| `swx_core/webhooks/paystack_webhook.py` | No Paystack webhook handler. |
| `swx_core/webhooks/flutterwave_webhook.py` | No Flutterwave webhook handler. |
| User-facing subscription routes | No `POST/GET /user/billing/subscriptions*` endpoints. |
| User-facing transaction route | No `GET /user/billing/transactions`. |
| User-facing quota routes | No `GET /user/billing/quota/*` endpoints. |

### 4.4 Currency Conversion Math

Paystack sends amounts in **kobo** (1 NGN = 100 kobo). SwX wallet balance is in **nano** (1 NGN = 10,000,000 nano). The conversion: `nano = kobo × 100,000`.

| Currency | Major→Nano divisor | Provider unit | Provider→Nano |
|----------|-------------------|---------------|---------------|
| NGN | 10,000,000 | kobo (Paystack) | kobo × 100,000 |
| NGN | 10,000,000 | major (Flutterwave) | major × 10,000,000 |
| KES | 100 | major | major × 100 |
| ZAR | 100 | major | major × 100 |
| USD | 100 | major (Stripe) | major × 100 |

### 4.5 Idempotency: Redis vs Durable Table

The existing Stripe webhook uses **Redis-only** idempotency (`webhook:stripe:idempotency:{event_id}` with 7-day TTL). This is insufficient for at-least-once delivery guarantees — Redis eviction or restart can lose keys, causing duplicate processing.

**Decision:** Add a durable `swx_webhook_delivery` table (Wave 3, item 2.4) as the source of truth, with Redis as a fast-path cache. Paystack/Flutterwave handlers (Wave 1/2) use Redis idempotency initially (matching the Stripe pattern), then migrate to the durable table when 2.4 ships.

---

## 5. Dependency Graph

```
Wave 1 (P0 — Foundation):
  6.3  Currency utility ──────────── independent (no deps)
  5.1  Session helper (with_read_session) ── independent
  1.1  Server-side payment init ──── depends on 6.3, 5.1
  2.1  Paystack webhook ──────────── depends on 6.3 (kobo→nano)

Wave 2 (P1 — Billing Surface):
  3.1  Public plan listing ───────── independent
  3.3  Get current subscription ──── independent
  1.2  Transaction history ──────── independent
  3.2  Subscribe to plan ─────────── depends on 3.1 (plan lookup)
  3.5  Cancel subscription ────────── independent
  4.1  Quota status ──────────────── depends on 4.4 (usage metering, partial)
  4.3  Credit pack purchase ─────── depends on 1.1 (payment init pattern), 6.3
  2.2  Flutterwave webhook ──────── depends on 2.1 (pattern), 6.3

Wave 3 (P2 — Completeness):
  2.4  Webhook idempotency table ─── independent (migrates 2.1/2.2/2.3)
  1.3  Wallet debit (user) ──────── independent
  1.4  Wallet transfer (user) ───── independent
  2.3  Stripe webhook (extend) ───── depends on 2.4
  3.4  List my subscriptions ────── independent
  3.6  Renewal failure handling ──── independent
  4.2  Reset usage window ────────── depends on 4.1
  4.4  Usage metering service ────── independent
  6.1  Signature docs ────────────── independent
  6.2  BaseRepository session docs ── independent
  6.4  UserDep caching default ────── independent

Wave 4 (P3 — Advanced):
  7.1  Referral system ──────────── independent
  7.2  Dual-control adjustments ──── independent
  7.3  Wallet priority resolution ── independent
  7.4  Credit expiry ──────────────── independent
  7.5  API key rotation grace ────── independent
  7.6  Subscription renewal grace ── depends on 3.6
  7.7  Audit log retention ───────── independent
  7.8  GDPR data export ──────────── independent
  7.9  GDPR data deletion ────────── independent
```

---

## 6. Execution Waves

### Wave 1 — P0 Security & Foundation

| Order | Item | Files | Est. LOC | Breaking? |
|-------|------|-------|----------|-----------|
| 1 | 6.3 Currency conversion utility | `swx_core/utils/currency.py` (NEW) | ~60 | No |
| 2 | 5.1 Session helper + guidance | `swx_core/database/session_helpers.py` (NEW), `docs/04-core-concepts/SESSION_MANAGEMENT.md` (NEW) | ~80 | No |
| 3 | 1.1a Server-side payment init (plan) | `swx_core/controllers/billing_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD) | ~90 | No — additive |
| 4 | 1.1b Server-side payment init (pack) | `swx_core/controllers/billing_controller.py` (ADD), `swx_core/models/credit_pack.py` (NEW), migration | ~120 | No |
| 5 | 2.1 Paystack webhook handler | `swx_core/webhooks/paystack_webhook.py` (NEW), `swx_core/router.py` (ADD include) | ~180 | No |

### Wave 2 — P1 Billing Surface

| Order | Item | Files | Est. LOC | Breaking? |
|-------|------|-------|----------|-----------|
| 6 | 3.1 Public plan listing | `swx_core/controllers/billing_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD) | ~40 | No |
| 7 | 3.3 Get current subscription | `swx_core/controllers/subscription_controller.py` (NEW), `swx_core/routes/user/billing_route.py` (ADD) | ~60 | No |
| 8 | 1.2 Transaction history | `swx_core/controllers/billing_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD), `swx_core/repositories/ledger_repository.py` (ADD filtered query) | ~90 | No |
| 9 | 3.2 Subscribe to plan | `swx_core/controllers/subscription_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD) | ~70 | No |
| 10 | 3.5 Cancel subscription | `swx_core/controllers/subscription_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD) | ~60 | No |
| 11 | 4.1 Quota status | `swx_core/services/billing/quota_service.py` (NEW), `swx_core/controllers/quota_controller.py` (NEW), `swx_core/routes/user/billing_route.py` (ADD) | ~150 | No |
| 12 | 4.3 Credit pack purchase | `swx_core/controllers/billing_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD) | ~80 | No |
| 13 | 2.2 Flutterwave webhook | `swx_core/webhooks/flutterwave_webhook.py` (NEW), `swx_core/router.py` (ADD include) | ~160 | No |

### Wave 3 — P2 Completeness

| Order | Item | Files | Est. LOC | Breaking? |
|-------|------|-------|----------|-----------|
| 14 | 2.4 Webhook idempotency table | `swx_core/models/webhook_delivery.py` (NEW), `swx_core/repositories/webhook_delivery_repository.py` (NEW), `swx_core/services/webhook_idempotency_service.py` (NEW), migration | ~150 | No |
| 15 | 1.3 Wallet debit (user) | `swx_core/routes/user/billing_route.py` (ADD) | ~20 | No |
| 16 | 1.4 Wallet transfer (user) | `swx_core/routes/user/billing_route.py` (ADD) | ~20 | No |
| 17 | 2.3 Stripe webhook (extend) | `swx_core/webhooks/stripe_webhook.py` (MODIFY to use 2.4 table) | ~40 | No |
| 18 | 3.4 List my subscriptions | `swx_core/controllers/subscription_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD) | ~50 | No |
| 19 | 3.6 Renewal failure handling | `swx_core/services/billing/subscription_service.py` (ADD), `swx_core/models/billing.py` (ADD grace fields), migration | ~120 | No — additive |
| 20 | 4.2 Reset usage window | `swx_core/services/billing/quota_service.py` (ADD), `swx_core/controllers/quota_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD) | ~70 | No |
| 21 | 4.4 Usage metering service | `swx_core/services/billing/usage_metering_service.py` (NEW), `swx_core/models/billing.py` (ADD model pricing fields or table) | ~200 | No |
| 22 | 6.1 Signature docs | `docs/04-core-concepts/BILLING.md` (UPDATE) | ~40 | No |
| 23 | 6.2 BaseRepository session docs | `docs/04-core-concepts/BASE_CLASSES.md` (UPDATE) | ~30 | No |
| 24 | 6.4 UserDep caching default | `swx_core/config/settings.py` (CHANGE default), `docs/04-core-concepts/AUTHENTICATION.md` (UPDATE) | ~20 | **Yes** — default flip |

### Wave 4 — P3 Advanced

| Order | Item | Files | Est. LOC | Breaking? |
|-------|------|-------|----------|-----------|
| 25 | 7.1 Referral system | `swx_core/models/referral.py` (NEW), `swx_core/services/billing/referral_service.py` (NEW), `swx_core/controllers/referral_controller.py` (NEW), `swx_core/routes/user/referral_route.py` (NEW), migration | ~250 | No |
| 26 | 7.2 Dual-control adjustments | `swx_core/models/wallet_adjustment.py` (NEW), `swx_core/services/billing/wallet_adjustment_service.py` (NEW), `swx_core/controllers/admin/wallet_adjustment_controller.py` (NEW), `swx_core/routes/admin/wallet_adjustment_route.py` (NEW), migration | ~280 | No |
| 27 | 7.3 Wallet priority resolution | `swx_core/services/billing/wallet_service.py` (ADD `resolve_wallet_for_charge`), `swx_core/services/billing/usage_metering_service.py` (USE) | ~90 | No |
| 28 | 7.4 Credit expiry | `swx_core/models/credit_lot.py` (NEW), `swx_core/services/billing/credit_expiry_service.py` (NEW), migration, Celery beat | ~200 | No |
| 29 | 7.5 API key rotation grace | `swx_core/services/auth/api_key_service.py` (ADD), `swx_core/models/api_key.py` (ADD fields), migration | ~150 | No |
| 30 | 7.6 Subscription renewal grace | `swx_core/services/billing/subscription_service.py` (ADD), `swx_core/models/billing.py` (ADD fields), migration | ~130 | No |
| 31 | 7.7 Audit log retention | `swx_core/services/audit/audit_retention_service.py` (EXTEND — already exists), `swx_core/config/settings.py` (ADD per-type policies) | ~120 | No |
| 32 | 7.8 GDPR data export | `swx_core/services/data_transfer/gdpr_export_service.py` (NEW), `swx_core/controllers/user/gdpr_controller.py` (EXTEND), Celery job | ~220 | No |
| 33 | 7.9 GDPR data deletion | `swx_core/services/data_transfer/gdpr_deletion_service.py` (NEW), `swx_core/controllers/user/gdpr_controller.py` (EXTEND), Celery job | ~200 | No |

---

## 7. Ticket Tracker

### Legend
- `[ ]` Pending
- `[~]` In Progress
- `[x]` Completed
- `[!]` Blocked

### Wave 1 — P0 Security & Foundation

- `[x]` **[6.3]** `swx_core/utils/currency.py`: Create `major_to_nano(amount, currency)` + `kobo_to_nano(kobo)` + `NANO_DIVISORS` table — currency-aware nano conversion
- `[x]` **[5.1]** `swx_core/database/session_helpers.py`: Create `with_read_session()` async context manager for DB-read-then-HTTP pattern (short-lived session, closed before outbound calls)
- `[x]` **[5.1]** `docs/04-core-concepts/SESSION_MANAGEMENT.md`: Document the session deadlock problem + the three correct patterns (separate session, with_read_session helper, native controller session)
- `[x]` **[1.1a]** `swx_core/controllers/billing_controller.py`: Add `initialize_payment_for_plan_controller(plan_key, provider, callback_url, currency, email)` — looks up plan price on own session, converts to nano, calls provider
- `[x]` **[1.1b]** `swx_core/models/credit_pack.py`: Create `CreditPack` model (`key`, `name`, `tokens`, `price`, `currency`, `is_active`) + `CreditPackPublic` schema
- `[x]` **[1.1b]** Alembic migration: Create `swx_credit_pack` table
- `[x]` **[1.1b]** `swx_core/controllers/billing_controller.py`: Add `initialize_payment_for_pack_controller(pack_key, provider, callback_url, email)` — looks up pack price, converts to nano, calls provider
- `[x]` **[1.1]** `swx_core/routes/user/billing_route.py`: Add `POST /payments/initialize/plan` and `POST /payments/initialize/pack` routes (NO `SessionDep` — controller manages session)
- `[x]` **[2.1]** `swx_core/webhooks/paystack_webhook.py`: Create `PaystackWebhookHandler` — HMAC-SHA512 verify, kobo→nano conversion, user lookup by email, idempotent wallet credit, return 200
- `[x]` **[2.1]** `swx_core/router.py`: Include Paystack webhook router at `/webhooks/paystack` (via `bootstrap.py register_webhook_routes`)
- `[x]` **[2.1]** `swx_core/config/settings.py`: Add `PAYSTACK_WEBHOOK_SECRET` setting

### Wave 2 — P1 Billing Surface

- `[x]` **[3.1]** `swx_core/controllers/billing_controller.py`: Add `list_public_plans_controller()` — returns `is_public=True AND is_active=True` plans
- `[x]` **[3.1]** `swx_core/routes/user/billing_route.py`: Add `GET /plans` (public, no auth)
- `[x]` **[3.3]** `swx_core/controllers/subscription_controller.py`: Create `get_current_subscription_controller(session, user_id)` — resolves billing account, returns active/trialing sub or 404
- `[x]` **[3.3]** `swx_core/routes/user/billing_route.py`: Add `GET /subscriptions/current`
- `[x]` **[1.2]** `swx_core/repositories/ledger_repository.py`: Add `get_filtered_entries(session, account_id, entry_type, date_from, date_to, skip, limit)`
- `[x]` **[1.2]** `swx_core/controllers/billing_controller.py`: Add `list_transactions_controller(session, user_id, entry_type, date_from, date_to, skip, limit)` — resolves account_id internally
- `[x]` **[1.2]** `swx_core/routes/user/billing_route.py`: Add `GET /transactions` with query params
- `[x]` **[3.2]** `swx_core/controllers/subscription_controller.py`: Add `create_subscription_controller(session, user_id, plan_key)` — resolves account, calls `SubscriptionService.create_subscription`
- `[x]` **[3.2]** `swx_core/routes/user/billing_route.py`: Add `POST /subscriptions`
- `[x]` **[3.5]** `swx_core/controllers/subscription_controller.py`: Add `cancel_subscription_controller(session, user_id, subscription_id, immediate)` — ownership check, calls `SubscriptionService.cancel_subscription`
- `[x]` **[3.5]** `swx_core/routes/user/billing_route.py`: Add `POST /subscriptions/{subscription_id}/cancel`
- `[x]` **[4.1]** `swx_core/services/billing/usage_window_service.py`: Create `UsageWindowService` — Redis 5-hour rolling window, monthly quota, `get_status(account_id)`
- `[x]` **[4.1]** `swx_core/controllers/quota_controller.py`: Create `get_quota_status_controller(session, user_id)`
- `[x]` **[4.1]** `swx_core/routes/user/billing_route.py`: Add `GET /quota/status`
- `[x]` **[4.2]** `swx_core/routes/user/billing_route.py`: Add `POST /quota/reset-window`
- `[x]` **[4.3]** `swx_core/controllers/billing_controller.py`: Add `list_credit_packs_controller()` and `initialize_payment_for_pack_controller(pack_key, provider, callback_url, email)`
- `[x]` **[4.3]** `swx_core/routes/user/billing_route.py`: Add `GET /credit-packs` and `POST /credit-packs/{pack_key}/purchase`
- `[x]` **[3.4]** `swx_core/controllers/subscription_controller.py`: Add `list_subscriptions_controller(session, user_id, skip, limit)`
- `[x]` **[3.4]** `swx_core/routes/user/billing_route.py`: Add `GET /subscriptions` with pagination
- `[x]` **[2.2]** `swx_core/webhooks/flutterwave_webhook.py`: Create `FlutterwaveWebhookHandler` — HMAC-SHA256 verify, major→nano conversion, idempotent wallet credit
- `[x]` **[2.2]** `swx_core/bootstrap.py`: Include Flutterwave webhook router at `/webhooks/flutterwave`
- `[x]` **[2.2]** `swx_core/config/settings.py`: Add `FLUTTERWAVE_WEBHOOK_SECRET` setting

### Wave 3 — P2 Completeness

- `[ ]` **[2.4]** `swx_core/models/webhook_delivery.py`: Create `WebhookDelivery` model (`provider`, `event_id`, `reference`, `processed_at`, `payload_hash`)
- `[ ]` **[2.4]** `swx_core/repositories/webhook_delivery_repository.py`: Create `is_processed()`, `mark_processed()`, `cleanup_expired()`
- `[ ]` **[2.4]** `swx_core/services/webhook_idempotency_service.py`: Create `check_and_record(provider, event_id, reference)` — durable + Redis fast-path
- `[ ]` **[2.4]** Alembic migration: Create `swx_webhook_delivery` table
- `[ ]` **[1.3]** `swx_core/routes/user/billing_route.py`: Add `POST /wallets/{currency}/debit` (exposes existing `wallet_service.debit_wallet`)
- `[ ]` **[1.4]** `swx_core/routes/user/billing_route.py`: Add `POST /wallets/transfer` (exposes existing `wallet_service.transfer`)
- `[ ]` **[2.3]** `swx_core/webhooks/stripe_webhook.py`: Migrate Redis-only idempotency to durable table (2.4), add `checkout.session.completed` / `invoice.paid` / `invoice.payment_failed` handling via `SubscriptionService.sync_stripe_subscription`
- `[ ]` **[3.4]** `swx_core/controllers/subscription_controller.py`: Add `list_subscriptions_controller(session, user_id, skip, limit)`
- `[ ]` **[3.4]** `swx_core/routes/user/billing_route.py`: Add `GET /subscriptions` with pagination
- `[ ]` **[3.6]** `swx_core/models/billing.py`: Add `grace_period_ends_at`, `renewal_failure_count` fields to `Subscription`
- `[ ]` **[3.6]** `swx_core/services/billing/subscription_service.py`: Add `enter_grace_period()`, `extend_grace()`, `expire_grace()` methods
- `[ ]` **[3.6]** Alembic migration: Additive columns to `swx_billing_subscription`
- `[ ]` **[4.2]** `swx_core/services/billing/quota_service.py`: Add `reset_window(account_id)` with guardrails (max 1 per window, max 3 per day)
- `[ ]` **[4.2]** `swx_core/controllers/quota_controller.py`: Add `reset_window_controller(session, user_id)`
- `[ ]` **[4.2]** `swx_core/routes/user/billing_route.py`: Add `POST /quota/reset-window`
- `[ ]` **[4.4]** `swx_core/services/billing/usage_metering_service.py`: Create `UsageMeteringService` — record token usage, calculate cost by model pricing, idempotent wallet debit, quota enforcement (Free=429, Paid=402)
- `[ ]` **[4.4]** `swx_core/models/billing.py`: Add `ModelPricing` model (`model_key`, `input_price_per_nano`, `output_price_per_nano`) or use `SystemConfig`
- `[ ]` **[6.1]** `docs/04-core-concepts/BILLING.md`: Document `credit_wallet`/`debit_wallet` signatures + internal-call overload that auto-generates reference + idempotency_key
- `[ ]` **[6.2]** `docs/04-core-concepts/BASE_CLASSES.md`: Document `BaseRepository.find_by()` session context manager + `find_by_readonly()` guidance for HTTP-after-DB patterns
- `[ ]` **[6.4]** `swx_core/config/settings.py`: Change `USER_CACHE_ENABLED` default to `True`
- `[ ]` **[6.4]** `docs/04-core-concepts/AUTHENTICATION.md`: Document UserDep caching behavior + Redis requirement

### Wave 4 — P3 Advanced

- `[ ]` **[7.1]** `swx_core/models/referral.py`: Create `ReferralCode`, `ReferralEvent` models
- `[ ]` **[7.1]** `swx_core/services/billing/referral_service.py`: Create `ReferralService` — generate code, apply on signup, credit bonus tokens
- `[ ]` **[7.1]** `swx_core/controllers/referral_controller.py` + `swx_core/routes/user/referral_route.py`: `GET /referrals/code`, `GET /referrals/history`
- `[ ]` **[7.1]** Alembic migration: Create `swx_referral_code`, `swx_referral_event` tables
- `[ ]` **[7.2]** `swx_core/models/wallet_adjustment.py`: Create `WalletAdjustmentRequest` model (proposer, approver, status, amount, currency, reason)
- `[ ]` **[7.2]** `swx_core/services/billing/wallet_adjustment_service.py`: Create propose/approve/reject/execute flow with dual-control
- `[ ]` **[7.2]** `swx_core/routes/admin/wallet_adjustment_route.py`: `POST /admin/billing/adjustments` (propose), `POST /{id}/approve`, `POST /{id}/reject`, `GET /pending`
- `[ ]` **[7.2]** Alembic migration: Create `swx_wallet_adjustment_request` table
- `[ ]` **[7.3]** `swx_core/services/billing/wallet_service.py`: Add `resolve_wallet_for_charge(account_id, org_id)` — org/personal priority, never cross-charge, 402 on empty
- `[ ]` **[7.4]** `swx_core/models/credit_lot.py`: Create `CreditLot` model (per-credit tracking, `expires_at`, `source`, `consumed`)
- `[ ]` **[7.4]** `swx_core/services/billing/credit_expiry_service.py`: Create FIFO consumption (bonus first, purchased second), expiry sweep (Celery beat)
- `[ ]` **[7.4]** Alembic migration: Create `swx_credit_lot` table
- `[ ]` **[7.5]** `swx_core/services/auth/api_key_service.py`: Add rotation with grace period (Redis TTL), immediate revocation override
- `[ ]` **[7.5]** `swx_core/models/api_key.py`: Add `rotated_from`, `grace_expires_at` fields
- `[ ]` **[7.5]** Alembic migration: Additive columns to api key table
- `[ ]` **[7.6]** `swx_core/services/billing/subscription_service.py`: Add `handle_renewal_failure()`, `retry_renewal()` — 3-day grace, daily reminders, downgrade to free
- `[ ]` **[7.6]** `swx_core/models/billing.py`: Add `renewal_grace_ends_at` (distinct from 3.6's `grace_period_ends_at` if needed)
- `[ ]` **[7.6]** Alembic migration: Additive columns
- `[ ]` **[7.7]** `swx_core/services/audit/audit_retention_service.py`: Extend with per-log-type policies (auth, billing, admin, gateway, PII, usage), hot/cold/deletion tiers
- `[ ]` **[7.7]** `swx_core/config/settings.py`: Add `SWX_AUDIT_RETENTION_POLICIES` dict
- `[ ]` **[7.8]** `swx_core/services/data_transfer/gdpr_export_service.py`: Create async ZIP export job (profile, conversations, messages, usage, billing, API keys)
- `[ ]` **[7.8]** `swx_core/routes/user/gdpr_route.py`: Add `POST /gdpr/export` (enqueue), `GET /gdpr/export/{job_id}` (download link)
- `[ ]` **[7.9]** `swx_core/services/data_transfer/gdpr_deletion_service.py`: Create 30-day grace deletion job (deactivate, hard delete, anonymize audit/billing)
- `[ ]` **[7.9]** `swx_core/routes/user/gdpr_route.py`: Add `POST /gdpr/deletion`, `POST /gdpr/deletion/cancel`

### Cross-Cutting

- `[ ]` **[TESTS]** Create test suite for each new module
- `[ ]` **[CODE-CLARITY]** Apply code-clarity review to each implemented module
- `[ ]` **[DOCS]** Update `docs/04-core-concepts/BILLING.md` for each new feature

---

## 8. Per-Feature Specifications

### [6.3] Currency Conversion Utility

**File:** `swx_core/utils/currency.py` (NEW, ~60 LOC)

**What:** Currency-aware conversion between major units, provider minor units, and nano.

**SwX Pattern:** Pure utility module in `swx_core/utils/`. No side effects, no I/O.

**API:**
```python
NANO_DIVISORS: dict[str, int] = {
    "NGN": 10_000_000,
    "KES": 100,
    "ZAR": 100,
    "USD": 100,
    "GHS": 100,
}

def major_to_nano(amount: float, currency: str) -> int:
    """Convert major currency units to nano (integer)."""

def nano_to_major(amount_nano: int, currency: str) -> float:
    """Convert nano back to major units."""

def kobo_to_nano(kobo: int) -> int:
    """Paystack kobo → nano (1 NGN = 100 kobo = 10,000,000 nano)."""

def provider_amount_to_nano(amount: int, currency: str, provider: str) -> int:
    """Convert provider-reported amount to nano based on provider's unit."""
```

**Code-clarity:** Use a dispatch dict for provider unit detection, not nested ifs. `kobo_to_nano` is a one-liner delegating to `major_to_nano` semantics. Early return on unknown currency with `ValueError`.

---

### [5.1] Session Helper & Guidance

**Files:** `swx_core/database/session_helpers.py` (NEW, ~40 LOC), `docs/04-core-concepts/SESSION_MANAGEMENT.md` (NEW, ~80 LOC)

**What:** `with_read_session()` async context manager that yields a short-lived `AsyncSession`, committed and closed before the caller does any outbound I/O.

**SwX Pattern:** Lives in `swx_core/database/` next to `db.py`. Uses the existing `AsyncSessionLocal` factory.

**API:**
```python
from contextlib import asynccontextmanager
from swx_core.database.db import AsyncSessionLocal

@asynccontextmanager
async def with_read_session():
    """Yield a short-lived session for DB reads that must close before outbound HTTP."""
    async with AsyncSessionLocal() as session:
        yield session
```

**Usage pattern (the fix for 1.1):**
```python
async def initialize_payment_for_plan_controller(plan_key, provider, callback_url, email, currency=None):
    async with with_read_session() as session:
        plan = await billing_repository.get_plan_by_key(session, plan_key)
        if plan is None:
            raise NotFoundError("Plan", plan_key)
        amount_nano = major_to_nano(plan.amount, plan.currency)
    # Session is now CLOSED — safe to make outbound HTTP call
    return await get_local_payment_provider(provider).initialize_payment(
        amount_nano, plan.currency, email, reference, callback_url
    )
```

**Code-clarity:** Trivially simple helper. The docstring carries the guidance — no need for a complex wrapper. The companion doc explains the three patterns (separate session, this helper, native controller session).

---

### [1.1] Server-Side Validated Payment Initialization

**Files:** `swx_core/controllers/billing_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD), `swx_core/models/credit_pack.py` (NEW), migration

**What:** Two new endpoints that look up the price server-side (from `Plan` / `CreditPack`), convert to nano, then call the provider. **No `amount_nano` accepted from the client.**

**SwX Pattern:** Controller manages its own session via `with_read_session()` (5.1). Route handler takes only `UserDep` (for email) + body — NO `SessionDep`.

**Endpoints:**
```
POST /api/user/billing/payments/initialize/plan
  body: { plan_key, provider, callback_url, currency? }
  → Server looks up plan price from swx_billing_plan
  → Converts to nano using major_to_nano()
  → Calls provider (Paystack/Flutterwave/Stripe)
  → Returns { authorization_url, reference, access_code }

POST /api/user/billing/payments/initialize/pack
  body: { pack_key, provider, callback_url }
  → Server looks up pack price from swx_credit_pack
  → Converts to nano
  → Calls provider
  → Returns { authorization_url, reference, access_code }
```

**Controller signatures:**
```python
async def initialize_payment_for_plan_controller(
    plan_key: str, provider: str, callback_url: str, email: str, currency: str | None = None
) -> dict[str, object]:
    ...

async def initialize_payment_for_pack_controller(
    pack_key: str, provider: str, callback_url: str, email: str
) -> dict[str, object]:
    ...
```

**CreditPack model:**
```python
class CreditPack(Base, table=True):
    __tablename__ = "swx_credit_pack"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(unique=True, index=True)
    name: str
    description: str | None = None
    tokens: int = Field(nullable=False)
    amount: int = Field(nullable=False)  # major units
    currency: str = Field(default="usd", max_length=3)
    is_active: bool = Field(default=True, index=True)
    is_public: bool = Field(default=True)
    created_at: datetime = ...
    updated_at: datetime = ...
```

**Code-clarity:** Both controllers share the same shape — lookup, convert, call. Extract a private `_initialize_payment_for_item(item_amount, item_currency, provider, email, callback_url, reference)` helper to avoid duplication. Early return on not-found via `NotFoundError`. No `SessionDep` on the route — this is the deadlock fix.

---

### [2.1] Paystack Webhook Handler

**File:** `swx_core/webhooks/paystack_webhook.py` (NEW, ~180 LOC)

**What:** Verify HMAC-SHA512 signature, parse payload, convert kobo→nano, look up user by email, credit wallet idempotently.

**SwX Pattern:** Follow `stripe_webhook.py` structure: handler class + route + lazy `get_webhook_handler()`. Register at `/webhooks/paystack`. No auth dependency (signature is the auth).

**Endpoint:**
```
POST /api/webhooks/paystack
  headers: { x-paystack-signature }
  body: { event, data: { reference, amount, customer: { email }, status, ... } }
  → Verify HMAC-SHA512 signature
  → Parse amount (kobo → nano: kobo_to_nano())
  → Look up user by email
  → Credit wallet (idempotent by reference)
  → Return 200 { status: "success" }
```

**Handler structure:**
```python
class PaystackWebhookHandler:
    def __init__(self, secret_key: str, redis_client=None, session_factory=None):
        ...

    async def handle(self, payload: bytes, signature: str) -> WebhookResult:
        # 1. Verify HMAC-SHA512: hmac.new(secret, payload, sha512).hexdigest() == signature
        # 2. Parse event + data
        # 3. Idempotency check (Redis: webhook:paystack:idempotency:{reference})
        # 4. Only process "charge.success" events
        # 5. Convert kobo → nano via kobo_to_nano()
        # 6. Resolve user by email → billing account → wallet
        # 7. Credit wallet via wallet_service.credit_wallet (idempotent by reference)
        # 8. Return 200
```

**Code-clarity:** Signature verification is a pure function — extract `_verify_signature(payload, signature, secret) -> bool`. Event-type dispatch via a set of supported events (early return on unsupported). The wallet credit reuses the existing idempotency in `ledger_service.credit` (idempotency_key = reference) — do NOT add a second idempotency layer. Empty catch blocks forbidden — log and re-raise or return error result.

---

### [1.2] User-Scoped Transaction History

**Files:** `swx_core/repositories/ledger_repository.py` (ADD), `swx_core/controllers/billing_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD)

**What:** `GET /api/user/billing/transactions` — resolves current user's billing account_id internally, returns filtered ledger entries.

**SwX Pattern:** Route takes `SessionDep` + `UserDep` (this is a pure DB read, no outbound HTTP, so SessionDep is safe). Controller resolves account_id from user_id, calls repository.

**Repository addition:**
```python
async def get_filtered_entries(
    session: AsyncSession, account_id: UUID, *,
    entry_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = 0, limit: int = 100,
) -> list[LedgerEntry]:
    ...
```

**Code-clarity:** Filter conditions built incrementally — only apply `.where()` when the filter is not None (avoids always-false conditions). Pagination via `.offset().limit()`. Order by `created_at DESC`.

---

### [3.1] Public Plan Listing

**Files:** `swx_core/controllers/billing_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD)

**What:** `GET /api/user/billing/plans` — returns public, active plans. No auth required.

**SwX Pattern:** Public catalog endpoint. Controller queries `Plan` where `is_public=True AND is_active=True`. Returns `PlanPublic` list.

**Code-clarity:** Single query, no filtering logic needed. Return only the public-facing fields (key, name, description, amount, currency, billing_interval) — not internal fields like `stripe_price_id`.

---

### [3.2] Subscribe to Plan (User-Facing)

**Files:** `swx_core/controllers/subscription_controller.py` (NEW), `swx_core/routes/user/billing_route.py` (ADD)

**What:** `POST /api/user/billing/subscriptions` — resolves user's billing account, creates subscription.

**SwX Pattern:** New `subscription_controller.py` module (billing_controller is getting large). Controller resolves account via `billing_repository.get_user_billing_account` or `SubscriptionService.get_or_create_account`, then calls `SubscriptionService.create_subscription`.

**Code-clarity:** Ownership is implicit (resolved from `UserDep`, not from request body) — no ownership check needed. Plan existence is validated inside `create_subscription` (raises 404). Early return pattern.

---

### [3.3] Get Current Subscription

**Files:** `swx_core/controllers/subscription_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD)

**What:** `GET /api/user/billing/subscriptions/current` — returns active/trialing subscription or 404.

**SwX Pattern:** Controller resolves account, calls `billing_repository.get_active_subscription`. Returns 404 via `NotFoundError` if none.

**Code-clarity:** Two-line controller. No nested conditionals. This also satisfies 6.5 (user-facing subscription status).

---

### [3.5] Cancel Subscription (User-Facing)

**Files:** `swx_core/controllers/subscription_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD)

**What:** `POST /api/user/billing/subscriptions/{subscription_id}/cancel?immediate=bool` — ownership check, cancel.

**SwX Pattern:** Controller fetches subscription, verifies `subscription.account.owner_id == user_id` (ownership), calls `SubscriptionService.cancel_subscription`. Raises `ForbiddenError` on mismatch.

**Code-clarity:** Ownership check is a guard clause — early return/raise before the cancel call. No else-branch nesting.

---

### [4.1] Quota Status

**Files:** `swx_core/services/billing/quota_service.py` (NEW), `swx_core/controllers/quota_controller.py` (NEW), `swx_core/routes/user/billing_route.py` (ADD)

**What:** `GET /api/user/billing/quota/status` — returns monthly + 5-hour rolling window usage.

**SwX Pattern:** New `QuotaService` using Redis (`get_cache()` / `RedisCache`) for the rolling window. Monthly quota resolved from plan entitlements. Controller is thin.

**Response shape:**
```python
class QuotaStatus(SQLModel):
    monthly_quota: int
    monthly_used: int
    monthly_remaining: int
    window_quota: int
    window_used: int
    window_remaining: int
    window_resets_at: datetime
    window_resets_available: bool
```

**Code-clarity:** Rolling window = Redis `INCR` + `EXPIRE` on a key like `quota:{account_id}:window:{window_start}`. Window start computed from `utc_now()` floored to 5-hour boundary. No complex data structures.

---

### [4.3] Credit Pack Purchase

**Files:** `swx_core/controllers/billing_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD)

**What:** `GET /api/user/billing/credit-packs` + `POST /api/user/billing/credit-packs/{pack_key}/purchase`.

**SwX Pattern:** Listing is a public read. Purchase reuses the `initialize_payment_for_pack_controller` pattern from 1.1b. On webhook success, tokens are credited to wallet.

**Code-clarity:** Purchase endpoint delegates to the same payment-init helper as 1.1 — no duplication. The token credit happens in the webhook handler (2.1/2.2), not in the purchase endpoint.

---

### [2.2] Flutterwave Webhook Handler

**File:** `swx_core/webhooks/flutterwave_webhook.py` (NEW, ~160 LOC)

**What:** Same as Paystack but HMAC-SHA256 and amounts in major units.

**SwX Pattern:** Mirror `paystack_webhook.py` structure. Register at `/webhooks/flutterwave`.

**Code-clarity:** Extract shared webhook logic into a base `_LocalWebhookHandler` if the two handlers diverge enough to warrant it — but only after both exist (avoid premature abstraction). Conversion uses `provider_amount_to_nano(amount, currency, "flutterwave")`.

---

### [2.4] Webhook Idempotency Table

**Files:** `swx_core/models/webhook_delivery.py` (NEW), `swx_core/repositories/webhook_delivery_repository.py` (NEW), `swx_core/services/webhook_idempotency_service.py` (NEW), migration

**What:** Durable `swx_webhook_delivery` table as the source of truth for webhook idempotency, with Redis as a fast-path cache.

**Model:**
```python
class WebhookDelivery(Base, table=True):
    __tablename__ = "swx_webhook_delivery"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider: str = Field(max_length=20, index=True)  # paystack/flutterwave/stripe
    event_id: str = Field(max_length=255, index=True)
    reference: str | None = Field(default=None, max_length=255)
    payload_hash: str = Field(max_length=64)  # sha256
    processed_at: datetime = ...
    created_at: datetime = ...
    # Unique constraint on (provider, event_id)
```

**Service:**
```python
async def check_and_record(provider: str, event_id: str, payload: bytes) -> bool:
    """Returns True if this is a NEW delivery (should process), False if duplicate."""
```

**Code-clarity:** Redis fast-path: `EXISTS webhook:{provider}:idempotency:{event_id}` → if hit, return False (duplicate). On miss, check DB table. On DB miss, insert + set Redis key. TTL-based cleanup via a Celery beat job (delete rows older than `SWX_WEBHOOK_RETENTION_DAYS`).

---

### [1.3] Wallet Debit (User-Facing)

**File:** `swx_core/routes/user/billing_route.py` (ADD)

**What:** `POST /api/user/billing/wallets/{currency}/debit` — exposes existing `wallet_service.debit_wallet`.

**SwX Pattern:** Route takes `SessionDep` + `UserDep` + `WalletTransactionRequest` body. Calls `billing_controller.debit_wallet_controller` (new thin controller wrapping `wallet_service.debit_wallet`).

**Code-clarity:** The service already exists and is idempotent. The controller is a one-liner. No new logic.

---

### [1.4] Wallet Transfer (User-Facing)

**File:** `swx_core/routes/user/billing_route.py` (ADD)

**What:** `POST /api/user/billing/wallets/transfer` — exposes existing `wallet_service.transfer`.

**SwX Pattern:** Route takes `SessionDep` + `UserDep` + `ConvertRequest` body (reuse). Returns `tuple[WalletPublic, WalletPublic]`.

**Code-clarity:** Same as 1.3 — one-liner controller delegating to existing service.

---

### [2.3] Stripe Webhook (Extend)

**File:** `swx_core/webhooks/stripe_webhook.py` (MODIFY)

**What:** Migrate Redis-only idempotency to the durable table (2.4). Add explicit handling for `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed` via `SubscriptionService.sync_stripe_subscription`.

**Code-clarity:** Replace the inline Redis idempotency block with a call to `webhook_idempotency_service.check_and_record("stripe", event_id, payload)`. Keep the replay protection. The event-type dispatch becomes a match/dict, not a long if-chain.

---

### [3.4] List My Subscriptions

**Files:** `swx_core/controllers/subscription_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD)

**What:** `GET /api/user/billing/subscriptions` — all user's subscriptions (active, cancelled, expired) with pagination.

**SwX Pattern:** Controller resolves account, queries `Subscription` by `account_id` with pagination.

**Code-clarity:** Simple paginated query. Reuse `BaseRepository.find_by` if the model fits, else a direct `select`.

---

### [3.6] Subscription Renewal Failure Handling

**Files:** `swx_core/services/billing/subscription_service.py` (ADD), `swx_core/models/billing.py` (ADD fields), migration

**What:** When recurring payment fails: enter 3-day grace, daily reminders, downgrade to free after grace.

**Status transitions:**
```
active → past_due (renewal failed) → past_due + in_grace
past_due + in_grace → active (card updated, renewal succeeds)
past_due + grace_expired → cancelled (downgrade to free)
```

**Model additions:**
```python
# On Subscription
grace_period_ends_at: datetime | None = Field(default=None, ...)
renewal_failure_count: int = Field(default=0)
```

**Code-clarity:** State transitions are a method per transition (`enter_grace_period`, `extend_grace`, `expire_grace`). No giant if-chain. Each method emits an event.

---

### [4.2] Reset Usage Window

**Files:** `swx_core/services/billing/quota_service.py` (ADD), `swx_core/controllers/quota_controller.py` (ADD), `swx_core/routes/user/billing_route.py` (ADD)

**What:** `POST /api/user/billing/quota/reset-window` — guardrails: max 1 reset per 5-hour window, max 3 per day.

**SwX Pattern:** `QuotaService.reset_window(account_id)` checks Redis counters (`quota:{account_id}:resets:window`, `quota:{account_id}:resets:daily`) before resetting.

**Code-clarity:** Guardrails are two early-return checks before the reset. Raise `QuotaExceededError` (reuse — it's a quota guard) or `ConflictError` on limit hit.

---

### [4.4] Usage Metering Service

**File:** `swx_core/services/billing/usage_metering_service.py` (NEW, ~200 LOC)

**What:** Record token usage per request, calculate cost by model pricing, debit wallet idempotently, enforce quota tiers.

**SwX Pattern:** New service in `swx_core/services/billing/`. Uses `wallet_service.debit_wallet` (idempotent by `request_id`), `QuotaService` for enforcement.

**Code-clarity:** Cost calculation is a pure function: `calculate_cost(input_tokens, output_tokens, model_key) -> int_nano`. Model pricing from `SystemConfig` or a `ModelPricing` table. Quota enforcement: Free plan → `QuotaExceededError` (429), Paid plan → 402 with overflow message. No nested conditionals — dispatch on plan tier via dict.

---

### [6.1] Signature Documentation

**File:** `docs/04-core-concepts/BILLING.md` (UPDATE)

**What:** Document `credit_wallet` / `debit_wallet` signatures. Note the internal-call overload that auto-generates `reference` + `idempotency_key` (to be added to `wallet_service`).

**Code-clarity:** Add a `credit_wallet_internal(session, account_id, currency, amount_nano, description="")` convenience that generates `reference = f"internal:{uuid4()}"` and `idempotency_key = f"internal:{uuid4()}"`. This fixes the 6.1 bug where `wallet_adjustment_service` called `credit_wallet` with only 4 args.

---

### [6.2] BaseRepository Session Documentation

**File:** `docs/04-core-concepts/BASE_CLASSES.md` (UPDATE)

**What:** Document that `BaseRepository.find_by()` with an injected session should NOT be followed by long-running async operations (HTTP calls) on the same request. Recommend `with_read_session()` for that pattern.

---

### [6.4] UserDep Caching Default

**File:** `swx_core/config/settings.py` (CHANGE), `docs/04-core-concepts/AUTHENTICATION.md` (UPDATE)

**What:** Change `USER_CACHE_ENABLED` default from `False` to `True`.

**Breaking:** Yes — requires Redis to be configured. Document the migration: if Redis is unavailable, `user_auth_cache` falls back gracefully (verify the fallback path exists in `auth_cache.py`).

---

### [7.x] P3 Advanced Features

Each P3 item follows the same SwX CSR pattern. Specifications are abbreviated here — full specs written when the wave is started. Key notes:

- **7.2 (Dual-control):** Two-phase state machine (proposed → approved/rejected → executed). Audit trail via `created_by` / `approved_by` fields. No single-admin execution path.
- **7.3 (Wallet priority):** Pure resolution function `resolve_wallet_for_charge(account_id, org_id) -> Wallet`. Never cross-charge. 402 on empty.
- **7.4 (Credit expiry):** FIFO consumption (bonus first). Per-credit `CreditLot` rows, not balance deduction. Celery beat sweep.
- **7.5 (API key rotation):** Redis TTL for grace. Old key hash stored with `grace_expires_at`. Immediate revocation overrides.
- **7.8/7.9 (GDPR):** Async Celery jobs. Export produces ZIP with JSON+CSV. Deletion has 30-day grace with immediate deactivation.

---

## 9. Migration Strategy

### For Credit Packs (1.1b)

**New table migration:**
```sql
CREATE TABLE swx_credit_pack (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key VARCHAR(100) UNIQUE NOT NULL,
  name VARCHAR(200) NOT NULL,
  description TEXT,
  tokens BIGINT NOT NULL,
  amount INTEGER NOT NULL,
  currency VARCHAR(3) NOT NULL DEFAULT 'usd',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_public BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### For Webhook Idempotency (2.4)

**New table migration:**
```sql
CREATE TABLE swx_webhook_delivery (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider VARCHAR(20) NOT NULL,
  event_id VARCHAR(255) NOT NULL,
  reference VARCHAR(255),
  payload_hash VARCHAR(64) NOT NULL,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(provider, event_id)
);
CREATE INDEX idx_swx_webhook_delivery_provider_event ON swx_webhook_delivery(provider, event_id);
CREATE INDEX idx_swx_webhook_delivery_created ON swx_webhook_delivery(created_at);
```

### For Subscription Grace (3.6)

**Additive migration:**
```sql
ALTER TABLE swx_billing_subscription
  ADD COLUMN grace_period_ends_at TIMESTAMPTZ NULL,
  ADD COLUMN renewal_failure_count INTEGER NOT NULL DEFAULT 0;
```

### Migration Naming Convention

Follow existing pattern in `swx_core/database/migrations/`: `v{major}_{minor}_{patch}_{description}.py` (e.g. `v2_22_4_add_credit_pack.py`).

---

## 10. Testing Strategy

### Per-Module Test Requirements

Every new module requires:

1. **Unit tests** — test the module in isolation with mocks for external dependencies (DB, Redis, HTTP)
2. **Integration tests** — test the module wired into the SwX app (where applicable)
3. **Edge cases** — empty inputs, None values, boundary conditions, duplicate deliveries
4. **Backward compatibility** — existing tests must continue to pass

### Test File Mapping

| Module | Test File |
|--------|-----------|
| Currency utility | `tests/utils/test_currency.py` |
| Session helper | `tests/database/test_session_helpers.py` |
| Server-side payment init | `tests/controllers/test_billing_controller.py` |
| Credit pack model | `tests/models/test_credit_pack.py` |
| Paystack webhook | `tests/webhooks/test_paystack_webhook.py` |
| Flutterwave webhook | `tests/webhooks/test_flutterwave_webhook.py` |
| Public plan listing | `tests/routes/user/test_billing_route.py` |
| Transaction history | `tests/controllers/test_billing_controller.py` |
| Subscription controller | `tests/controllers/test_subscription_controller.py` |
| Quota service | `tests/services/billing/test_quota_service.py` |
| Quota controller | `tests/controllers/test_quota_controller.py` |
| Credit pack purchase | `tests/controllers/test_billing_controller.py` |
| Webhook idempotency | `tests/services/test_webhook_idempotency_service.py` |
| Wallet debit/transfer routes | `tests/routes/user/test_billing_route.py` |
| Stripe webhook (extended) | `tests/webhooks/test_stripe_webhook.py` |
| Renewal failure handling | `tests/services/billing/test_subscription_service.py` |
| Reset usage window | `tests/services/billing/test_quota_service.py` |
| Usage metering | `tests/services/billing/test_usage_metering_service.py` |
| Referral system | `tests/services/billing/test_referral_service.py` |
| Dual-control adjustments | `tests/services/billing/test_wallet_adjustment_service.py` |
| Wallet priority | `tests/services/billing/test_wallet_service.py` |
| Credit expiry | `tests/services/billing/test_credit_expiry_service.py` |
| API key rotation | `tests/services/auth/test_api_key_service.py` |
| GDPR export | `tests/services/data_transfer/test_gdpr_export_service.py` |
| GDPR deletion | `tests/services/data_transfer/test_gdpr_deletion_service.py` |

### Test Execution

```bash
# Run all tests
pytest tests/ -v

# Run Wave 1 tests only
pytest tests/utils/test_currency.py tests/database/test_session_helpers.py \
  tests/controllers/test_billing_controller.py tests/webhooks/test_paystack_webhook.py -v

# Run with coverage
pytest tests/ --cov=swx_core --cov-report=html
```

### Verification Checklist (Per Feature)

- [ ] `lsp_diagnostics` clean on every changed file
- [ ] Unit tests pass
- [ ] No `# type: ignore` added
- [ ] No empty catch blocks
- [ ] Code-clarity review passed (no redundancy, no dead code, meaningful names)
- [ ] SwX pattern followed (CSR layering, SwXError not HTTPException, events emitted)
- [ ] Migration created (if schema change)
- [ ] Docs updated

---

## Changelog

| Date | Wave | Item | Status |
|------|------|------|--------|
| 2026-08-22 | — | Plan created, 33 tickets defined across 4 waves | Done |
| 2026-08-22 | Wave 1 | 6.3 Currency conversion utility | Done |
| 2026-08-22 | Wave 1 | 5.1 Session helper (`with_read_session`) | Done |
| 2026-08-22 | Wave 1 | 1.1a Server-side payment init (plan) | Done |
| 2026-08-22 | Wave 1 | 1.1b Credit pack model + migration + payment init (pack) | Done |
| 2026-08-22 | Wave 1 | 2.1 Paystack webhook handler | Done |
| 2026-08-22 | Wave 1 | 5.1 SESSION_MANAGEMENT.md doc | Done |
| 2026-08-22 | Wave 2 | 3.1 Public plan listing | Done |
| 2026-08-22 | Wave 2 | 3.3 Get current subscription | Done |
| 2026-08-22 | Wave 2 | 1.2 Transaction history (filtered) | Done |
| 2026-08-22 | Wave 2 | 3.2 Subscribe to plan | Done |
| 2026-08-22 | Wave 2 | 3.5 Cancel subscription | Done |
| 2026-08-22 | Wave 2 | 3.4 List my subscriptions | Done |
| 2026-08-22 | Wave 2 | 4.1 Quota status (Redis rolling window) | Done |
| 2026-08-22 | Wave 2 | 4.2 Reset usage window | Done |
| 2026-08-22 | Wave 2 | 4.3 Credit pack listing + purchase | Done |
| 2026-08-22 | Wave 2 | 2.2 Flutterwave webhook handler | Done |
| 2026-08-22 | Wave 1-2 | CSR compliance — all controllers route through services, not repositories | Done |
| 2026-08-22 | Wave 1-2 | Code-clarity review — dead imports, empty catches, naming, duplication | Done |
