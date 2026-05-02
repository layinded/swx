# Adding Entitlements

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Feature Types](#feature-types)
3. [Registering Features](#registering-features)
4. [Creating Plans](#creating-plans)
5. [Checking Entitlements](#checking-entitlements)
6. [Usage Tracking](#usage-tracking)
7. [Best Practices](#best-practices)

---

## Overview

SwX-API includes a **billing and entitlement system** that controls feature access based on subscription plans. This guide covers how to add new entitlements and integrate them with features.

### Key Concepts

- **Feature** - A capability or resource (e.g., "api_requests", "export_data")
- **Plan** - A subscription tier (e.g., "free", "pro", "enterprise")
- **Entitlement** - Plan's access to a feature (e.g., "free" plan has "api_requests: 1000")
- **Usage** - Tracking actual usage for quota/metered features

---

## Feature Types

### 1. Boolean Features

**Purpose:** On/off features

**Examples:**
- `enable_export` - Can export data
- `enable_api_access` - Can use API
- `enable_advanced_search` - Can use advanced search

**Usage:**
```python
# Check if feature enabled
if await entitlement_resolver.has(user_id, account_type, "enable_export"):
    # Allow export
    ...
```

### 2. Quota Features

**Purpose:** Limited quantity features

**Examples:**
- `api_requests` - Number of API requests
- `storage_gb` - Storage in GB
- `exports_per_month` - Exports per month

**Usage:**
```python
# Check if quota available
remaining = await entitlement_resolver.get_remaining_quota(
    user_id, account_type, "api_requests"
)
if remaining > 0:
    # Allow request
    ...
```

### 3. Metered Features

**Purpose:** Pay-per-use features

**Examples:**
- `api_calls` - API calls (billed per call)
- `data_processed` - Data processed (billed per GB)
- `emails_sent` - Emails sent (billed per email)

**Usage:**
```python
# Record usage
await usage_service.record_usage(
    user_id, account_type, "api_calls", quantity=1
)
```

---

## Registering Features

### Step 1: Register Feature

**Feature Registry:**
```python
# swx_core/services/billing/feature_registry.py
from swx_core.services.billing.feature_registry import FeatureRegistry, FeatureType

# Register boolean feature
FeatureRegistry.register(
    key="enable_export",
    feature_type=FeatureType.BOOLEAN,
    description="Enable data export feature"
)

# Register quota feature
FeatureRegistry.register(
    key="api_requests",
    feature_type=FeatureType.QUOTA,
    description="Number of API requests per month",
    unit="requests"
)

# Register metered feature
FeatureRegistry.register(
    key="api_calls",
    feature_type=FeatureType.METERED,
    description="API calls (billed per call)",
    unit="calls"
)
```

### Step 2: Seed Feature

**Seed Script:**
```python
# scripts/seed_system.py
features = [
    {
        "key": "enable_export",
        "name": "Enable Export",
        "description": "Enable data export feature",
        "feature_type": "boolean"
    },
    {
        "key": "api_requests",
        "name": "API Requests",
        "description": "Number of API requests per month",
        "feature_type": "quota",
        "unit": "requests"
    }
]
```

---

## Creating Plans

### Step 1: Create Plan

**Seed Script:**
```python
# scripts/seed_system.py
plans = [
    {
        "key": "free",
        "name": "Free Plan",
        "description": "Free tier with basic features"
    },
    {
        "key": "pro",
        "name": "Pro Plan",
        "description": "Pro tier with advanced features"
    }
]
```

### Step 2: Create Plan Entitlements

**Seed Script:**
```python
# scripts/seed_system.py
plan_entitlements = [
    # Free plan
    {
        "plan_key": "free",
        "feature_key": "enable_export",
        "value": "false"  # Boolean feature
    },
    {
        "plan_key": "free",
        "feature_key": "api_requests",
        "value": "1000"  # Quota feature
    },
    # Pro plan
    {
        "plan_key": "pro",
        "feature_key": "enable_export",
        "value": "true"  # Boolean feature
    },
    {
        "plan_key": "pro",
        "feature_key": "api_requests",
        "value": "10000"  # Quota feature
    }
]
```

---

## Checking Entitlements

### Boolean Features

**Check Access:**
```python
from swx_core.services.billing.entitlement_resolver import EntitlementResolver

resolver = EntitlementResolver(session)

# Check if feature enabled
has_export = await resolver.has(
    user_id=user.id,
    account_type=BillingAccountType.USER,
    feature_key="enable_export"
)

if has_export:
    # Allow export
    ...
else:
    raise HTTPException(403, "Export feature not available on your plan")
```

### Quota Features

**Check Quota:**
```python
# Check if quota available
remaining = await resolver.get_remaining_quota(
    user_id=user.id,
    account_type=BillingAccountType.USER,
    feature_key="api_requests"
)

if remaining > 0:
    # Allow request
    ...
else:
    raise HTTPException(403, "API request quota exceeded")
```

**Use Quota:**
```python
# Record usage
await usage_service.record_usage(
    owner_id=user.id,
    account_type=BillingAccountType.USER,
    feature_key="api_requests",
    quantity=1
)
```

### Metered Features

**Record Usage:**
```python
# Record metered usage
await usage_service.record_usage(
    owner_id=user.id,
    account_type=BillingAccountType.USER,
    feature_key="api_calls",
    quantity=1
)
```

---

## Usage Tracking

### Recording Usage

**Usage Service:**
```python
from swx_core.services.billing.usage_service import UsageService

usage_service = UsageService(session)

# Record usage
await usage_service.record_usage(
    owner_id=user.id,
    account_type=BillingAccountType.USER,
    feature_key="api_requests",
    quantity=1,
    metadata={"endpoint": "/api/user/profile"}
)
```

### Getting Usage

**Get Current Usage:**
```python
# Get current usage
usage = await usage_service.get_usage(
    owner_id=user.id,
    account_type=BillingAccountType.USER,
    feature_key="api_requests",
    period_start=datetime.utcnow().replace(day=1),  # Start of month
    period_end=datetime.utcnow()  # Now
)

print(f"Used: {usage}, Remaining: {remaining}")
```

---

## Best Practices

### ✅ DO

1. **Register features before use**
   ```python
   # ✅ Good - Register feature
   FeatureRegistry.register(
       key="enable_export",
       feature_type=FeatureType.BOOLEAN
   )
   ```

2. **Check entitlements before operations**
   ```python
   # ✅ Good - Check entitlement
   if await resolver.has(user_id, account_type, "enable_export"):
       # Allow export
   ```

3. **Track usage for quota features**
   ```python
   # ✅ Good - Track usage
   await usage_service.record_usage(
       owner_id=user.id,
       account_type=account_type,
       feature_key="api_requests",
       quantity=1
   )
   ```

4. **Provide clear error messages**
   ```python
   # ✅ Good - Clear error
   raise HTTPException(
       403,
       "Export feature not available on your plan. Upgrade to Pro."
   )
   ```

### ❌ DON'T

1. **Don't skip entitlement checks**
   ```python
   # ❌ Bad - No entitlement check
   # Allow export without checking
   
   # ✅ Good - Check entitlement
   if await resolver.has(...):
       # Allow export
   ```

2. **Don't forget to track usage**
   ```python
   # ❌ Bad - No usage tracking
   # Allow request without tracking
   
   # ✅ Good - Track usage
   await usage_service.record_usage(...)
   ```

---

## Next Steps

- Read [Adding Features](./ADDING_FEATURES.md) for feature development
- Read [Billing Documentation](../04-core-concepts/BILLING.md) for billing details
- Read [Adding Policies](./ADDING_POLICIES.md) for policy creation

---

**Status:** Adding entitlements guide documented, ready for implementation.
