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

## Proposed Changes

### A. Framework: Auto-create TEAM billing account with trial during registration

**File:** `swx_core/core/default_hooks.py`

`create_personal_team` should also create a TEAM billing account with a subscription that includes trial metadata, mirroring what `create_billing_account` does for the USER account.

```python
async def create_personal_team(user: User, session: AsyncSession, _context: dict) -> User:
    # ... existing team creation code ...

    # Create TEAM billing account with trial subscription
    subscription_service = SubscriptionService(session)
    team_account = await subscription_service.get_or_create_account(
        owner_id=team.id,
        account_type=BillingAccountType.TEAM,
    )
    try:
        subscription = await subscription_service.create_subscription(
            account_id=team_account.id,
            plan_key=settings.DEFAULT_PLAN_KEY,
        )
        if settings.TRIAL_DAYS > 0:
            trial_ends_at = utc_now() + timedelta(days=settings.TRIAL_DAYS)
            subscription.subscription_metadata = {
                **(subscription.subscription_metadata or {}),
                "trial_ends_at": trial_ends_at.isoformat(),
            }
            session.add(subscription)
            await session.flush()
    except Exception as e:
        logger.warning(f"Could not create team subscription: {e}")

    return user
```

**New settings:**

```python
TRIAL_DAYS: int = Field(default=30, description="Trial duration in days for new accounts")
TRIAL_PLAN_KEY: str = Field(default="enterprise", description="Plan key applied during trial")
```

### B. Framework: Make trial a first-class subscription concept

**File:** `swx_core/models/billing.py`

Add `trial_ends_at` as a proper column on `Subscription` instead of relying on JSON metadata:

```python
class Subscription(Base, table=True):
    # ... existing fields ...
    trial_ends_at: datetime | None = Field(default=None, nullable=True)
```

**File:** `swx_core/services/billing/subscription_service.py`

Add a `create_trial_subscription` method:

```python
async def create_trial_subscription(
    self,
    account_id: UUID,
    plan_key: str,
    trial_days: int = 30,
) -> Subscription:
    subscription = await self.create_subscription(account_id=account_id, plan_key=plan_key)
    subscription.trial_ends_at = utc_now() + timedelta(days=trial_days)
    return subscription
```

**File:** `swx_core/services/billing/quota_service.py`

Add trial detection to quota calculation:

```python
async def _get_remaining_quota(self, owner_id, account_type, feature_key) -> int:
    # ... existing limit lookup ...
    if limit == -1:
        return 999_999_999

    # If trial is active, use trial plan's entitlements
    if subscription and subscription.trial_ends_at:
        if subscription.trial_ends_at > utc_now():
            trial_limit = await self._get_trial_entitlement(feature_key)
            if trial_limit == -1:
                return 999_999_999
            limit = max(limit, trial_limit)

    # ... existing usage calculation ...
```

### C. Framework: Auto-exempt service token routes from CSRF

**File:** `swx_core/middleware/csrf_middleware.py`

Add `X-Service-Token` to the CSRF bypass check:

```python
has_api_key = b"x-api-key" in headers
has_service_token = b"x-service-token" in headers
skip_validation = has_bearer or has_api_key or has_service_token
```

This eliminates the need for every app to manually add internal route prefixes to CSRF exempt lists.

### D. Framework: Unify service token settings

**File:** `swx_core/config/settings.py`

Add `SERVICE_TOKEN` and `GATEWAY_SERVICE_TOKEN` as aliases that map to `SWX_SERVICE_TOKEN`:

```python
SWX_SERVICE_TOKEN: str | None = Field(
    default=None,
    description="Shared secret for service-to-service auth via X-Service-Token header",
    validation_alias=AliasChoices("SWX_SERVICE_TOKEN", "SERVICE_TOKEN", "GATEWAY_SERVICE_TOKEN"),
)
```

This way apps that set `SERVICE_TOKEN` or `GATEWAY_SERVICE_TOKEN` in their `.env` files automatically work with the framework's service token guard.

### E. Framework: Built-in plan tier resolution with trial support

**File:** `swx_core/services/billing/plan_resolver.py` (new)

```python
class PlanResolver:
    async def resolve_plan_tier(
        self,
        session: AsyncSession,
        team_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> str:
        subscription = await self._find_subscription(session, team_id, user_id)
        if not subscription:
            return "free"

        plan = await session.get(Plan, subscription.plan_id)
        if not plan:
            return "free"

        if subscription.trial_ends_at and subscription.trial_ends_at > utc_now():
            return settings.TRIAL_PLAN_KEY

        plan_key = str(plan.key or plan.name or "").lower()
        if "enterprise" in plan_key:
            return "enterprise"
        if "pro" in plan_key:
            return "pro"
        return "free"
```

This replaces the app-level `_resolve_plan_tier` that uses `cast(Any, ...)` workarounds and silently catches exceptions.

## Migration Path

1. **v2.20.0**: Add `trial_ends_at` column to `Subscription` model (nullable, backwards compatible). Add `TRIAL_DAYS` and `TRIAL_PLAN_KEY` settings. Add `X-Service-Token` CSRF bypass. Add `SERVICE_TOKEN`/`GATEWAY_SERVICE_TOKEN` alias choices.
2. **v2.21.0**: Update `create_personal_team` hook to create TEAM subscription with trial. Add `PlanResolver` service. Add `create_trial_subscription` method.
3. **v2.22.0**: Update `quota_service` to check trial entitlements. Deprecate JSON metadata-based trial detection. Apps can remove custom `trial_service.py` and `BillingSetupService`.

## Impact

- **Apps:** Remove custom `BillingSetupService`, `trial_service.py`, app-level `service_token_guard.py`, and manual CSRF exempt entries
- **New users:** Automatically get TEAM billing account + trial subscription on registration, no manual database inserts needed
- **Gateway:** Works out of the box for trial users — no quota errors, correct `plan_tier: "enterprise"` resolution
- **Service auth:** `X-Service-Token` bypasses CSRF framework-wide, no per-route exemptions needed