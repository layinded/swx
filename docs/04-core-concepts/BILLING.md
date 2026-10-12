# Billing & Entitlements

**Version:** 2.20.0  
**Last Updated:** 2026-08-11

---

## Table of Contents

1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [Billing Architecture](#billing-architecture)
4. [Entitlement Resolution](#entitlement-resolution)
5. [Feature Types](#feature-types)
6. [Usage Examples](#usage-examples)
7. [Stripe Integration](#stripe-integration)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

SwX-API includes a **comprehensive billing and entitlement system** that decouples monetization logic from business features. It supports:

- **Multi-tenant billing** (User, Team, Organization)
- **Flexible plans** (Free, Pro, Enterprise)
- **Feature-based entitlements** (Boolean, Quota, Metered)
- **Stripe integration** (extensible to other providers)
- **Usage tracking** for quota-based features

### Key Principles

1. **Feature-First:** Features are declared independently of plans
2. **Entitlement-Driven:** Plans grant entitlements to features
3. **Fail-Closed:** Paid features denied if billing unavailable
4. **Usage Tracking:** Quota and metered features tracked automatically

---

## Core Concepts

### 1. Feature

**Definition:** A gateable capability in the system

**Examples:**
- `"api.calls"` - API request quota
- `"llm.tokens"` - LLM token usage
- `"advanced.analytics"` - Advanced analytics access
- `"team.collaboration"` - Team collaboration features

**Model:**
```python
class Feature(SQLModel, table=True):
    id: UUID
    key: str  # "api.calls"
    name: str  # "API Calls"
    description: str
    feature_type: FeatureType  # BOOLEAN, QUOTA, METERED
    unit: Optional[str]  # "requests", "tokens"
```

### 2. Plan

**Definition:** A collection of entitlements offered at a price point

**Examples:**
- `"free"` - Free tier with basic features
- `"pro"` - Pro tier with advanced features
- `"enterprise"` - Enterprise tier with all features

**Model:**
```python
class Plan(SQLModel, table=True):
    id: UUID
    key: str  # "pro_v1"
    name: str  # "Pro Plan"
    description: str
    is_active: bool
    is_public: bool
    billing_interval: BillingInterval  # "weekly", "monthly", or "yearly" (default: "monthly")
```

#### BillingInterval Enum

As of v2.7.22, the `Plan` model includes a `billing_interval` field that controls subscription duration:

```python
class BillingInterval(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

BILLING_INTERVAL_DAYS = {
    BillingInterval.WEEKLY: 7,
    BillingInterval.MONTHLY: 30,
    BillingInterval.YEARLY: 365,
}
```

When creating a subscription, `SubscriptionService.create_subscription()` uses `BILLING_INTERVAL_DAYS` to calculate `current_period_end` based on the plan's `billing_interval` instead of a hardcoded 30 days.

### 3. Entitlement

**Definition:** The bridge between a Plan and a Feature, defining access level

**Examples:**
- Plan "Pro" → Feature "api.calls" → Entitlement: 10,000 requests/month
- Plan "Free" → Feature "advanced.analytics" → Entitlement: false (not available)

**Model:**
```python
class PlanEntitlement(SQLModel, table=True):
    plan_id: UUID
    feature_id: UUID
    value: str  # "true", "1000", or JSON config
```

### 4. BillingAccount

**Definition:** The entity that is billed (User, Team, or Organization)

**Model:**
```python
class BillingAccount(SQLModel, table=True):
    id: UUID
    account_type: BillingAccountType  # USER, TEAM, ORGANIZATION
    owner_id: UUID  # ID of User or Team
    stripe_customer_id: Optional[str]
    billing_email: Optional[str]
```

### 5. Subscription

**Definition:** Active link between a BillingAccount and a Plan

**Model:**
```python
class Subscription(SQLModel, table=True):
    id: UUID
    account_id: UUID
    plan_id: UUID
    status: SubscriptionStatus  # ACTIVE, TRIALING, PAST_DUE, etc.
    current_period_start: datetime
    current_period_end: datetime
    trial_ends_at: Optional[datetime]  # When the trial period ends (v2.20.0)
    stripe_subscription_id: Optional[str]
    subscription_metadata: Dict[str, Any]
```

As of v2.20.0, `trial_ends_at` is a first-class column on `Subscription`. During an active trial (`trial_ends_at > now`), the entitlement resolver and plan resolver use the `TRIAL_PLAN_KEY` plan's entitlements instead of the subscription's base plan. This means a user on a "free" plan in trial receives enterprise-tier features automatically.

### 6. UsageRecord

**Definition:** Tracks consumption of quota-based features

**Model:**
```python
class UsageRecord(SQLModel, table=True):
    id: UUID
    account_id: UUID
    feature_id: UUID
    subscription_id: UUID
    quantity: int
    period_start: datetime
    period_end: datetime
```

---

## Billing Architecture

### Data Model

```
BillingAccount
  └── Subscription (active link)
       └── Plan
            └── PlanEntitlement (mapping)
                 └── Feature
                      └── UsageRecord (consumption tracking)
```

### Account Types

1. **User Account** (`BillingAccountType.USER`)
   - Individual user billing
   - `owner_id` = User ID
   - Personal subscriptions

2. **Team Account** (`BillingAccountType.TEAM`)
   - Team-based billing
   - `owner_id` = Team ID
   - Shared subscriptions

3. **Organization Account** (`BillingAccountType.ORGANIZATION`)
   - Enterprise billing
   - `owner_id` = Organization ID
   - Enterprise subscriptions

---

## Entitlement Resolution

### Resolution Flow

```
1. Business code calls: entitlements.has(account_id, account_type, feature_key)

2. Resolver identifies BillingAccount
   └── Find account by owner_id and account_type

3. Resolver fetches active Subscription
   └── Get subscription with status = ACTIVE or TRIALING

4. Resolver checks Plan entitlements
   └── Get PlanEntitlement for feature_key

5. If quota-based, check UsageRecord
   └── Compare usage vs. limit

6. Return True/False or remaining quota
```

### EntitlementResolver

**Usage:**
```python
from swx_core.services.billing.entitlement_resolver import EntitlementResolver
from swx_core.models.billing import BillingAccountType

resolver = EntitlementResolver(session)

# Check if account has feature
has_access = await resolver.has(
    owner_id=user.id,
    account_type=BillingAccountType.USER,
    feature_key="api.calls"
)

# Get remaining quota
remaining = await resolver.get_remaining_quota(
    owner_id=team.id,
    account_type=BillingAccountType.TEAM,
    feature_key="api.calls"
)
```

### Trial-Aware Entitlement Resolution (v2.20.0)

When a subscription has `trial_ends_at` set and the trial has not expired, the entitlement resolver automatically resolves entitlements from the `TRIAL_PLAN_KEY` plan (default: `"enterprise"`) instead of the subscription's base plan.

**How it works:**

1. `_get_account_and_subscription()` finds subscriptions with `status IN (ACTIVE, TRIALING, PAST_DUE)` **or** an unexpired `trial_ends_at`
2. `_resolve_effective_plan_id()` checks if the trial is active:
   - **Active trial** → looks up the `TRIAL_PLAN_KEY` plan and returns its `plan_id`
   - **No trial / expired trial** → returns `subscription.plan_id`
3. `get_entitlement()` and `get_remaining_quota()` use the effective plan ID to fetch entitlements

This means a user on a "free" plan with an active trial automatically receives enterprise-tier entitlements — no custom `trial_service.py` needed.

### PlanResolver (v2.20.0)

The `PlanResolver` resolves the effective plan tier for a user or team, accounting for trial periods:

```python
from swx_core.services.billing.plan_resolver import PlanResolver

resolver = PlanResolver(session)

# Resolve for a team (checks TEAM first, falls back to USER)
tier = await resolver.resolve_plan_tier(team_id=team.id, user_id=user.id)
# Returns: "enterprise", "pro", or "free"

# During an active trial, returns TRIAL_PLAN_KEY (default: "enterprise")
# After trial expires, returns the actual plan tier
```

**Resolution order:**
1. If `team_id` is provided → look up TEAM subscription
2. If no TEAM subscription and `user_id` provided → look up USER subscription
3. If an active trial is found → return `TRIAL_PLAN_KEY`
4. Otherwise classify the plan key as `"enterprise"`, `"pro"`, or `"free"`

### Creating Trial Subscriptions

```python
from swx_core.services.billing.subscription_service import SubscriptionService
from swx_core.config.settings import settings

service = SubscriptionService(session)

# Create a trial subscription (used by create_personal_team hook)
subscription = await service.create_trial_subscription(
    account_id=team_account.id,
    plan_key=settings.DEFAULT_PLAN_KEY,  # "free"
    trial_days=settings.TRIAL_DAYS,       # default: 30
)
# subscription.status == SubscriptionStatus.TRIALING
# subscription.trial_ends_at == now + 30 days
```

**Configuration (`.env`):**
```bash
TRIAL_DAYS=30              # Trial duration in days (0 disables trial)
TRIAL_PLAN_KEY=enterprise  # Plan key whose entitlements apply during trial
```

### Feature Registry

**Registering Features:**
```python
from swx_core.services.billing.feature_registry import FeatureRegistry

FeatureRegistry.register({
    "key": "api.calls",
    "name": "API Calls",
    "description": "Number of API calls per month",
    "feature_type": FeatureType.QUOTA,
    "unit": "requests"
})
```

---

## Feature Types

### 1. Boolean Features

**Definition:** Yes/No access to a feature

**Example:**
- Feature: `"advanced.analytics"`
- Entitlement: `"true"` (has access) or `"false"` (no access)

**Usage:**
```python
has_access = await resolver.has(account_id, account_type, "advanced.analytics")
if has_access:
    # Show advanced analytics
    ...
```

### 2. Quota Features

**Definition:** Fixed limit per period

**Example:**
- Feature: `"api.calls"`
- Entitlement: `"10000"` (10,000 requests/month)

**Usage:**
```python
# Check if under quota
has_access = await resolver.has(account_id, account_type, "api.calls")
if has_access:
    # Make API call
    await record_usage(account_id, "api.calls", quantity=1)
```

**Usage Tracking:**
```python
from swx_core.services.billing.subscription_service import record_usage

await record_usage(
    account_id=account.id,
    feature_key="api.calls",
    quantity=1,
    subscription_id=subscription.id
)
```

### 3. Metered Features

**Definition:** Pay-as-you-go consumption

**Example:**
- Feature: `"llm.tokens"`
- Entitlement: Unlimited (tracked for billing)

**Usage:**
```python
# Track usage (billed separately)
await record_usage(
    account_id=account.id,
    feature_key="llm.tokens",
    quantity=1000,
    subscription_id=subscription.id
)
```

---

## Usage Examples

### Enforcing Entitlements

**In Route Handler:**
```python
from swx_core.services.billing.enforcement import enforce_entitlement

@router.post("/api/advanced/analytics")
async def get_advanced_analytics(
    user: UserDep,
    session: SessionDep,
    request: Request,
):
    # Enforce entitlement
    await enforce_entitlement(
        request=request,
        feature_key="advanced.analytics",
        session=session,
        current_user=user,
    )
    
    # Return advanced analytics
    return await get_analytics(session, user.id)
```

**In Service:**
```python
from swx_core.services.billing.entitlement_resolver import EntitlementResolver
from swx_core.models.billing import BillingAccountType

async def process_api_request(
    session: AsyncSession,
    user: User,
    request_data: dict,
):
    resolver = EntitlementResolver(session)
    
    # Check entitlement
    has_access = await resolver.has(
        owner_id=user.id,
        account_type=BillingAccountType.USER,
        feature_key="api.calls"
    )
    
    if not has_access:
        raise HTTPException(403, "API call quota exceeded")
    
    # Process request
    result = await process_request(request_data)
    
    # Record usage
    await record_usage(
        account_id=user.billing_account_id,
        feature_key="api.calls",
        quantity=1
    )
    
    return result
```

### Team Billing

**Team-scoped entitlements:**
```python
# Check team entitlement
has_access = await resolver.has(
    owner_id=team.id,
    account_type=BillingAccountType.TEAM,
    feature_key="team.collaboration"
)

# Record team usage
await record_usage(
    account_id=team.billing_account_id,
    feature_key="team.collaboration",
    quantity=1
)
```

### Checking Quota

**Get remaining quota:**
```python
remaining = await resolver.get_quota(
    owner_id=user.id,
    account_type=BillingAccountType.USER,
    feature_key="api.calls"
)

if remaining <= 0:
    raise HTTPException(403, "Quota exceeded")
```

---

## Stripe Integration

### Setup

**Environment Variables:**
```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### Creating Subscriptions

**Via Stripe Provider:**
```python
from swx_core.services.billing.stripe_provider import StripeProvider

provider = StripeProvider()

# Create customer
customer = await provider.create_customer(
    email=user.email,
    name=user.name
)

# Create subscription
subscription = await provider.create_subscription(
    customer_id=customer.id,
    plan_id=plan.stripe_price_id
)
```

### Webhook Handling

**Stripe webhooks:**
```python
from swx_core.services.billing.stripe_provider import StripeProvider

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    provider = StripeProvider()
    
    # Verify webhook signature
    event = provider.verify_webhook(request)
    
    # Handle event
    if event.type == "customer.subscription.updated":
        await handle_subscription_update(event.data)
    elif event.type == "invoice.payment_failed":
        await handle_payment_failed(event.data)
    
    return {"status": "ok"}
```

---

## Best Practices

### ✅ DO

1. **Register features early**
   ```python
   # ✅ Good - Register at startup
   FeatureRegistry.register({
       "key": "api.calls",
       "name": "API Calls",
       "feature_type": FeatureType.QUOTA,
   })
   ```

2. **Check entitlements before expensive operations**
   ```python
   # ✅ Good
   if not await resolver.has(account_id, account_type, "feature.key"):
       raise HTTPException(403, "Feature not available")
   
   # Expensive operation
   result = await expensive_operation()
   ```

3. **Record usage immediately**
   ```python
   # ✅ Good - Record after successful operation
   await process_request()
   await record_usage(account_id, "api.calls", quantity=1)
   ```

4. **Use appropriate account types**
   ```python
   # ✅ Good - Team features use team billing
   await resolver.has(team_id, BillingAccountType.TEAM, "team.feature")
   
   # ✅ Good - User features use user billing
   await resolver.has(user_id, BillingAccountType.USER, "user.feature")
   ```

### ❌ DON'T

1. **Don't skip entitlement checks**
   ```python
   # ❌ Bad - No entitlement check
   await expensive_operation()
   
   # ✅ Good - Check first
   if await resolver.has(...):
       await expensive_operation()
   ```

2. **Don't forget to record usage**
   ```python
   # ❌ Bad - Usage not recorded
   await process_api_request()
   
   # ✅ Good - Usage recorded
   await process_api_request()
   await record_usage(...)
   ```

3. **Don't hardcode feature keys**
   ```python
   # ❌ Bad
   if feature_key == "api.calls":
   
   # ✅ Good
   FEATURE_API_CALLS = "api.calls"
   if feature_key == FEATURE_API_CALLS:
   ```

---

## Troubleshooting

### Common Issues

**1. "Feature not available" error**
- Check if feature is registered in FeatureRegistry
- Verify plan has entitlement for feature
- Check subscription is active

**2. Quota exceeded but should have access**
- Check UsageRecord for current period
- Verify quota limit in PlanEntitlement
- Check subscription period dates

**3. Team billing not working**
- Verify BillingAccount exists for team
- Check account_type is TEAM
- Verify subscription is active

**4. Stripe webhook not working**
- Verify webhook secret in .env
- Check webhook URL in Stripe dashboard
- Verify webhook signature validation

### Debugging

**Check entitlements:**
```python
resolver = EntitlementResolver(session)

# Check if has access
has_access = await resolver.has(account_id, account_type, feature_key)
print(f"Has access: {has_access}")

# Get quota
remaining = await resolver.get_quota(account_id, account_type, feature_key)
print(f"Remaining: {remaining}")
```

**List all features:**
```python
from swx_core.services.billing.feature_registry import FeatureRegistry

features = FeatureRegistry.list_all()
for feature in features:
    print(f"{feature['key']}: {feature['name']}")
```

---

## User-Facing Billing Endpoints (v2.22.4)

### Overview

SwX Core v2.22.4 adds a complete user-facing billing surface: server-side
validated payment initialization, subscription lifecycle management,
transaction history, quota tracking, credit packs, and webhook handlers
for Paystack and Flutterwave.

All new endpoints follow the **CSR pattern** (Controller → Service →
Repository) strictly. Controllers never call repositories directly.

### Server-Side Validated Payment Initialization

The previous `POST /user/billing/payments/initialize` accepted `amount_nano`
from the client — a P0 security vulnerability. Two new endpoints replace
it with server-side price validation:

| Endpoint | Body | Server Action |
|----------|------|---------------|
| `POST /user/billing/payments/initialize/plan` | `{ plan_key, provider, callback_url, currency? }` | Looks up plan price from `swx_billing_plan`, converts to provider unit, calls provider |
| `POST /user/billing/payments/initialize/pack` | `{ pack_key, provider, callback_url }` | Looks up pack price from `swx_credit_pack`, converts to provider unit, calls provider |

**Key:** The client sends only `plan_key` / `pack_key` — never an amount.
The controller uses `with_read_session()` to look up the price on a
short-lived session, closes the session, THEN calls the payment provider.
This prevents the session deadlock described in
[Session Management](./SESSION_MANAGEMENT.md).

**Currency conversion** uses `swx_core.utils.currency`:
- `major_to_provider_amount(amount, currency, provider)` — converts plan price to the provider's expected unit (kobo for Paystack NGN, cents for Stripe USD, major for Flutterwave)
- `provider_amount_to_nano(amount, currency, provider)` — converts webhook amounts back to nano for wallet credits

### Credit Packs

Credit packs allow users to buy tokens without upgrading their plan.

**Model:** `swx_credit_pack` table (`swx_core/models/credit_pack.py`)

| Endpoint | Description |
|----------|-------------|
| `GET /user/billing/credit-packs` | List public, active credit packs |
| `POST /user/billing/credit-packs/{pack_key}/purchase` | Initialize payment for a credit pack |

On webhook success, tokens are credited to the user's wallet via
`wallet_service.credit_wallet()` (idempotent by reference).

### Subscription Lifecycle

| Endpoint | Description |
|----------|-------------|
| `GET /user/billing/plans` | Public plan catalog (no auth required) |
| `GET /user/billing/subscriptions/current` | Current active/trialing subscription (404 if none) |
| `GET /user/billing/subscriptions` | All subscriptions (paginated: `skip`, `limit`) |
| `POST /user/billing/subscriptions` | Subscribe to a plan (`{ plan_key }`) |
| `POST /user/billing/subscriptions/{id}/cancel` | Cancel subscription (`?immediate=true` for immediate cancel) |

The cancel endpoint performs an **ownership check** — the subscription's
`account.owner_id` must match the current user's ID. Raises `ForbiddenError`
on mismatch.

All subscription operations go through `SubscriptionService` which emits
events (`subscription.created`, `subscription.canceled`,
`subscription.updated`) via `event_bus`.

### Transaction History

| Endpoint | Query Params | Description |
|----------|-------------|-------------|
| `GET /user/billing/transactions` | `entry_type`, `date_from`, `date_to`, `skip`, `limit` | User-scoped ledger entries (credits, debits, refunds, adjustments) |

The controller resolves the user's billing account internally via
`billing_service.get_user_billing_account()`, then queries
`ledger_service.get_filtered_entry_history()` which delegates to
`ledger_repository.get_filtered_entries()`.

### Quota & Usage Windows

| Endpoint | Description |
|----------|-------------|
| `GET /user/billing/quota/status` | Monthly + 5-hour rolling window usage |
| `POST /user/billing/quota/reset-window` | Reset the rolling window (guardrails: max 1/window, max 3/day) |

**UsageWindowService** (`swx_core/services/billing/usage_window_service.py`):
- Redis primary store with in-memory fallback
- Monthly counter: `quota:{account_id}:monthly:{YYYYMM}` (32-day TTL)
- Window counter: `quota:{account_id}:window:{window_start_ts}` (5hr + 1hr TTL)
- Reset guardrails: `QUOTA_WINDOW_MAX_RESETS` (default 1), `QUOTA_DAILY_MAX_RESETS` (default 3)
- Emits `quota.window_reset` event on reset

**Settings:**
```env
QUOTA_WINDOW_HOURS=5
QUOTA_WINDOW_DEFAULT_TOKENS=100000
QUOTA_MONTHLY_DEFAULT_TOKENS=1000000
QUOTA_WINDOW_MAX_RESETS=1
QUOTA_DAILY_MAX_RESETS=3
```

### Webhook Handlers

| Endpoint | Provider | Signature | Amount Unit |
|----------|----------|-----------|-------------|
| `POST /webhooks/paystack` | Paystack | HMAC-SHA512 (`x-paystack-signature`) | Kobo (1 NGN = 100 kobo) |
| `POST /webhooks/flutterwave` | Flutterwave | HMAC-SHA256 (`verif-hash`) | Major units |
| `POST /webhooks/stripe` | Stripe | Stripe-Signature | Cents |

All webhook handlers follow the same pattern:
1. Verify signature
2. Resolve webhook secret (handles `${ENV_VAR}` placeholders, falls back to API key)
3. Check Redis idempotency (`webhook:{provider}:idempotency:{reference}`)
4. Only process supported events (`charge.success` / `charge.completed`)
5. Parse reference prefix to route the payment:
   - `plan-{key}-{uuid}` → call `SubscriptionService.create_subscription(account_id, key)`
   - `pack-{key}-{uuid}` → credit wallet (tokens purchased without plan upgrade)
   - Unrecognized → credit wallet (generic payment)
6. Convert amount to nano via `provider_amount_to_nano()` or `kobo_to_nano()`
7. Look up user by email
8. Ensure billing account exists (`SubscriptionService.get_or_create_account`)
9. Execute the routed action (subscription creation or wallet credit)
10. Mark as processed in Redis
11. Return `200 { status: "success" }` (even for duplicates — prevents provider retries)

**Settings:**
```env
# Quota
QUOTA_WINDOW_HOURS=5
QUOTA_WINDOW_DEFAULT_TOKENS=100000
QUOTA_MONTHLY_DEFAULT_TOKENS=1000000
QUOTA_WINDOW_MAX_RESETS=1
QUOTA_DAILY_MAX_RESETS=3
QUOTA_MONTHLY_TTL_DAYS=32
QUOTA_DAILY_TTL_HOURS=36
QUOTA_WINDOW_TTL_BUFFER_HOURS=1

# Usage metering
USAGE_METERING_DEFAULT_CURRENCY=NGN
USAGE_METERING_DEFAULT_MODEL_KEY=default
USAGE_METERING_MODEL_PRICING={"gpt-4":{"input":30000,"output":60000},...}

# Webhooks
PAYSTACK_WEBHOOK_SECRET=${PAYSTACK_WEBHOOK_SECRET}
FLUTTERWAVE_WEBHOOK_SECRET=${FLUTTERWAVE_WEBHOOK_SECRET}
WEBHOOK_IDEMPOTENCY_TTL=604800
WEBHOOK_RETENTION_DAYS=30
```

### New Service Layer

All new controllers route through services, never repositories directly:

| Service | File | Wraps |
|---------|------|------|
| `billing_service` | `services/billing/billing_service.py` | Plan/credit pack/account lookups |
| `currency_service` | `services/billing/currency_service.py` | Currency CRUD |
| `UsageWindowService` | `services/billing/usage_window_service.py` | Redis-based quota tracking |
| `SubscriptionService` (extended) | `services/billing/subscription_service.py` | Added `get_active_subscription`, `list_subscriptions`, `get_subscription_by_id` |
| `exchange_rate_service` (extended) | `services/billing/exchange_rate_service.py` | Added `get_all_for_base` |

### Session Management

See [Session Management](./SESSION_MANAGEMENT.md) for the deadlock problem
and the three correct patterns for routes that mix DB reads with outbound
HTTP calls.

**Key rule:** Routes that call payment providers must NOT take `SessionDep`.
The controller manages its own short-lived session via `with_read_session()`.

---

## Next Steps

- Read [Rate Limiting Documentation](./RATE_LIMITING.md) for plan-based limits
- Read [API Usage Guide](../06-api-usage/API_USAGE.md) for API examples
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production setup

---

**Status:** Billing system documented, ready for implementation.

**Version:** 2.22.4  
**Last Updated:** 2026-08-22
