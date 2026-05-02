# Billing & Entitlements

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

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
```

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
    stripe_subscription_id: Optional[str]
```

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
remaining = await resolver.get_quota(
    owner_id=team.id,
    account_type=BillingAccountType.TEAM,
    feature_key="api.calls"
)
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

## Next Steps

- Read [Rate Limiting Documentation](./RATE_LIMITING.md) for plan-based limits
- Read [API Usage Guide](../06-api-usage/API_USAGE.md) for API examples
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production setup

---

**Status:** Billing system documented, ready for implementation.
