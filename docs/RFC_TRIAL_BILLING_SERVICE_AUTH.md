# RFC: Simplify Trial Billing and Service Auth for Multi-Account Workspaces

## Summary

New user registration creates a USER billing account with a 30-day trial, but does not create a TEAM billing account with trial. Quota enforcement and plan tier resolution check at the TEAM level, so new users on trial get `QuotaExceededError` and `plan_tier: "free"` instead of `"enterprise"`. Service-to-service auth also requires manual CSRF exemptions and env var wiring in every app.

## Problem

### 1. Trial billing gap between USER and TEAM accounts

**Current registration flow** (`default_hooks.py`):

1. `create_billing_account` hook → creates USER billing account + free subscription (no trial metadata)
2. `create_personal_team` hook → creates personal team, calls `get_or_create_account(TEAM)` but does **not** create a subscription with trial

**Result:** The TEAM billing account exists but has no subscription, no trial metadata. The app-level `BillingSetupService` adds trial metadata (`trial_ends_at`) to the USER subscription only.

**Where it breaks:**

- `quota_service.py` checks for an active subscription on the TEAM billing account → finds none → returns 0 remaining
- `service_auth_service._resolve_plan_tier()` checks TEAM subscription first → finds none → falls back to USER subscription → trial is active there but the quota engine already returned 0
- The Gateway's PII inspection calls the detection endpoint → quota check fails → `QuotaExceededError`
- The auth response returns `plan_tier: "free"` instead of `"enterprise"` because the TEAM subscription is missing

**Reproduction:**

1. Register a new user
2. Create an API key for that user
3. Call the Gateway (`POST /v1/chat/completions`)
4. Observe: `QuotaExceededError: Detection quota exceeded`
5. Check `POST /api/v1/internal/auth/verify-api-key` → `plan_tier: "free"`, `is_enterprise: false`
6. Check database: `swx_billing_account` has a USER row with trial subscription, TEAM row has no subscription

### 2. Trial is not a first-class billing concept

Trial is stored as ad-hoc JSON metadata (`subscription_metadata.trial_ends_at`) on the subscription. Every consumer (quota engine, plan tier resolver, Gateway auth) needs custom logic to detect and check it:

```python
# app-level trial_service.py — custom code every app must write
def is_trial_active(subscription, plan_key=None):
    if plan_key and plan_key != "free":
        return False
    metadata = subscription.subscription_metadata or {}
    trial_ends_at_str = metadata.get("trial_ends_at")
    # ... manual ISO parsing, timezone handling, comparison
```

The framework should make trial a first-class concept so consumers don't need custom detection logic.

### 3. Service-to-service auth requires manual CSRF exemptions

The framework's CSRF middleware bypasses validation when `X-API-Key` or `Authorization: Bearer` headers are present, but **not** for `X-Service-Token`. Every app that uses internal service routes (Gateway calling backend) must manually add CSRF exemptions:

```python
# Every app must add this manually
exempt_prefixes=[
    "/api/v1/webhooks",
    "/api/v1/internal",
    "/api/v1/detection/detect/internal",
    "/api/v1/detection/transform/internal",
    # ... grow with every new internal route
]
```

### 4. Service token env var naming inconsistency

The framework's `service_token_guard.py` reads `settings.SWX_SERVICE_TOKEN`. Apps that create their own service token guards read `settings.SERVICE_TOKEN` and `settings.GATEWAY_SERVICE_TOKEN` — different names, same purpose. The app-level guard falls back to `os.getenv()` which doesn't work because pydantic-settings loads `.env` into the settings object, not into `os.environ`.

## Implementation

### A. Auto-create TEAM billing account with trial during registration

**File:** `swx_core/core/default_hooks.py`

`create_personal_team` now creates a TEAM billing account with a trial subscription when `BILLING_ENABLED` and `TRIAL_DAYS > 0`:

```python
if settings.BILLING_ENABLED and settings.TRIAL_DAYS > 0:
    subscription_service = SubscriptionService(session)
    team_account = await subscription_service.get_or_create_account(
        owner_id=team.id,
        account_type=BillingAccountType.TEAM,
    )
    await subscription_service.create_trial_subscription(
        account_id=team_account.id,
        plan_key=settings.DEFAULT_PLAN_KEY,
        trial_days=settings.TRIAL_DAYS,
    )
```

### B. Make trial a first-class subscription concept

**`swx_core/models/billing.py`** — Added `trial_ends_at` column to `Subscription`:

```python
trial_ends_at: Optional[datetime] = Field(
    default=None,
    sa_column=Column(DateTime(timezone=True), nullable=True),
)
```

**`swx_core/services/billing/subscription_service.py`** — Added `create_trial_subscription()`:

```python
async def create_trial_subscription(
    self, account_id: UUID, plan_key: str, trial_days: int = 30,
) -> Subscription:
    subscription = await self.create_subscription(account_id=account_id, plan_key=plan_key)
    subscription.trial_ends_at = utc_now() + timedelta(days=trial_days)
    subscription.status = SubscriptionStatus.TRIALING
    await self._commit_or_rollback(subscription, ...)
    return subscription
```

Uses `_commit_or_rollback` (not bare `flush`) for consistency with all other mutation methods and proper error handling.

**`swx_core/services/billing/entitlement_resolver.py`** — Trial-aware entitlement resolution:

- `_get_account_and_subscription()` now matches subscriptions with `status in ACTIVE_STATUSES` OR an unexpired `trial_ends_at`, so trial subscriptions are found even before status is formally `TRIALING`.
- `_resolve_effective_plan_id()` resolves the plan ID that governs entitlements. During an active trial, it returns the `TRIAL_PLAN_KEY` plan's ID instead of the subscription's base plan ID. This is the key fix — without it, a user on a "free" plan in trial would get free-tier entitlements instead of enterprise entitlements.
- `get_entitlement()` and `get_remaining_quota()` now use `_resolve_effective_plan_id()` instead of `subscription.plan_id` directly.
- `_ACTIVE_STATUSES` expanded to include `SubscriptionStatus.TRIALING`.

### C. Auto-exempt service token routes from CSRF

**File:** `swx_core/middleware/csrf_middleware.py`

```python
has_service_token = b"x-service-token" in headers
skip_validation = has_bearer or has_api_key or has_service_token
```

This eliminates the need for every app to manually add internal route prefixes to CSRF exempt lists.

### D. Unify service token settings

**File:** `swx_core/config/settings.py`

```python
SWX_SERVICE_TOKEN: str | None = Field(
    default=None,
    description="Shared secret for service-to-service auth via X-Service-Token header",
    validation_alias=AliasChoices("SWX_SERVICE_TOKEN", "SERVICE_TOKEN", "GATEWAY_SERVICE_TOKEN"),
)
```

Also added:

```python
TRIAL_DAYS: int = Field(default=30, description="Trial duration in days for new accounts")
TRIAL_PLAN_KEY: str = Field(default="enterprise", description="Plan key whose entitlements apply during trial")
```

### E. Built-in plan tier resolution with trial support

**File:** `swx_core/services/billing/plan_resolver.py` (new)

```python
class PlanResolver:
    async def resolve_plan_tier(
        self, team_id: UUID | None = None, user_id: UUID | None = None,
    ) -> str:
        # 1. Check TEAM subscription first
        # 2. Fall back to USER subscription
        # 3. If trial is active → return TRIAL_PLAN_KEY
        # 4. Otherwise classify the plan key as enterprise/pro/free
```

Resolution order: TEAM → USER → trial check → plan key classification. Returns one of `"enterprise"`, `"pro"`, or `"free"`.

### F. Data migration for existing JSON metadata

**File:** `migrations/versions/g9c3d6f0e2a5_add_trial_ends_at_to_subscription.py`

- Adds `trial_ends_at` column (nullable, backwards compatible)
- Backfills from existing `subscription_metadata->>'trial_ends_at'` JSON data
- Downgrade preserves data back into JSON metadata before dropping the column

## Migration Path

1. **v2.20.0** (this release): All changes above deployed together. The `trial_ends_at` column is nullable so existing rows are unaffected. The data migration backfills from JSON metadata. Apps can begin removing custom `trial_service.py` and `BillingSetupService`.

## Impact

- **Apps:** Remove custom `BillingSetupService`, `trial_service.py`, app-level `service_token_guard.py`, and manual CSRF exempt entries
- **New users:** Automatically get TEAM billing account + trial subscription on registration, no manual database inserts needed
- **Gateway:** Works out of the box for trial users — no quota errors, correct `plan_tier: "enterprise"` resolution
- **Service auth:** `X-Service-Token` bypasses CSRF framework-wide, no per-route exemptions needed
- **Entitlements:** Trial users receive enterprise-tier entitlements during trial, not free-tier ones — this was the critical bug that the original RFC identified but the initial implementation missed in `get_entitlement()` and `get_remaining_quota()`

## Stripe Billing Portal

The Stripe billing portal is already handled by `BillingProvider.create_portal_session()` / `StripeProvider.create_portal_session()`. Portal URLs are created on demand — there is no persistent `portal_url` in the database. Trial subscriptions created by `create_trial_subscription` are framework-managed (no `stripe_subscription_id`). The portal only becomes relevant after a user converts from trial to paid via Stripe checkout, and that flow is unchanged.