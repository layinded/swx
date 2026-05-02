# Runtime Settings System

**Version:** 1.0.0  
**Last Updated:** 2026-01-26  
**Updated:** Policy context integration documented

---

## Table of Contents

1. [Overview](#overview)
2. [Settings Architecture](#settings-architecture)
3. [Settings Access](#settings-access)
4. [Admin Management](#admin-management)
5. [Settings Categories](#settings-categories)
6. [Usage Examples](#usage-examples)
7. [Migration Guide](#migration-guide)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

SwX-API includes a **runtime settings system** that allows configuration changes without redeployment. Settings are:

- **Database-backed** - Stored in PostgreSQL
- **Type-safe** - Enforced value types (int, bool, string, json)
- **Cached** - In-memory caching for performance
- **Audited** - All changes logged
- **Validated** - Security guards prevent invalid values

### Key Principles

1. **.env for secrets** - Secrets remain in .env files
2. **Database for runtime config** - Non-secret settings in database
3. **Fail-closed** - Missing critical settings use safe defaults
4. **Type-safe** - Values validated against declared type
5. **No redeploy** - Settings changes apply immediately

---

## Settings Architecture

### Priority Order

**Settings resolution order:**
```
1. Database (system_config table)
   ↓ (if not found)
2. Environment variable (.env)
   ↓ (if not found)
3. Code default (hardcoded fallback)
```

### Data Model

**SystemConfig:**
```python
class SystemConfig(SQLModel, table=True):
    id: UUID
    key: str  # "auth.access_token_expire_minutes"
    value: str  # "10080" (stored as string)
    value_type: SettingValueType  # INT, BOOL, STRING, JSON
    category: SettingCategory  # SECURITY, RATE_LIMIT, etc.
    description: str
    is_sensitive: bool  # Always False (secrets never in DB)
    is_active: bool
    updated_by: str  # Admin email or "system"
    updated_at: datetime
    metadata: Dict[str, Any]
```

**SystemConfigHistory:**
```python
class SystemConfigHistory(SQLModel, table=True):
    id: UUID
    config_id: UUID
    key: str
    old_value: Optional[str]
    new_value: str
    updated_by: str
    updated_at: datetime
    change_reason: Optional[str]
    metadata: Dict[str, Any]
```

---

## Settings Access

### Settings Service

**Get Settings Service:**
```python
from swx_core.services.settings_service import get_settings_service

service = get_settings_service(session)
```

**Type-Safe Getters:**
```python
# Get integer setting
minutes = await service.get_int("auth.access_token_expire_minutes", default=10080)

# Get boolean setting
enabled = await service.get_bool("feature.enable_social_login", default=True)

# Get string setting
email = await service.get_string("email.from_email", default="noreply@example.com")

# Get JSON setting
config = await service.get_json("system.policy_config", default={})
```

### Settings Helper

**Token Expiration:**
```python
from swx_core.services.settings_helper import get_token_expiration

# Get access token expiration
access_expires = await get_token_expiration(session, "access")

# Get refresh token expiration
refresh_expires = await get_token_expiration(session, "refresh")

# Get password reset token expiration
reset_expires = await get_token_expiration(session, "password_reset")
```

**Feature Flags:**
```python
from swx_core.services.settings_helper import get_feature_flag

# Check feature flag
google_enabled = await get_feature_flag(session, "enable_google_login", default=True)
```

---

## Admin Management

### API Endpoints

**List Settings:**
```bash
GET /api/admin/settings/?category=security&limit=100
```

**Get Setting:**
```bash
GET /api/admin/settings/key/auth.access_token_expire_minutes
```

**Create Setting:**
```bash
POST /api/admin/settings/
{
  "key": "auth.access_token_expire_minutes",
  "value": "10080",
  "value_type": "int",
  "category": "security",
  "description": "Access token expiration in minutes"
}
```

**Update Setting:**
```bash
PATCH /api/admin/settings/key/auth.access_token_expire_minutes
{
  "value": "14400"  # 10 days
}
```

**Get History:**
```bash
GET /api/admin/settings/key/auth.access_token_expire_minutes/history
```

### Via Code

**Create Setting:**
```python
from swx_core.models.system_config import SystemConfig, SystemConfigCreate

setting = SystemConfigCreate(
    key="auth.access_token_expire_minutes",
    value="10080",
    value_type=SettingValueType.INT,
    category=SettingCategory.SECURITY,
    description="Access token expiration in minutes"
)

await settings_crud_service.create_setting_service(
    session,
    setting,
    updated_by="admin@example.com"
)
```

**Update Setting:**
```python
from swx_core.models.system_config import SystemConfigUpdate

update = SystemConfigUpdate(value="14400")

await settings_crud_service.update_setting_service(
    session,
    "auth.access_token_expire_minutes",
    update,
    updated_by="admin@example.com"
)
```

---

## Settings Categories

### Security Settings

**Category:** `SECURITY`

**Examples:**
- `auth.access_token_expire_minutes` - Access token expiration
- `auth.refresh_token_expire_days` - Refresh token expiration
- `auth.email_reset_token_expire_hours` - Password reset expiration

### Rate Limit Settings

**Category:** `RATE_LIMIT`

**Examples:**
- `rate_limit.free.read.burst` - Free plan read burst limit
- `rate_limit.pro.write.sustained` - Pro plan write sustained limit

### Feature Flags

**Category:** `FEATURE_FLAG`

**Examples:**
- `feature.enable_social_login` - Enable social login
- `feature.enable_google_login` - Enable Google OAuth
- `feature.enable_facebook_login` - Enable Facebook OAuth

### Email Settings

**Category:** `EMAIL`

**Examples:**
- `email.from_email` - Default from email address
- `email.from_name` - Default from name

### Job Settings

**Category:** `JOBS`

**Examples:**
- `job.default_max_attempts` - Default job retry attempts
- `job.default_retry_delay_seconds` - Default retry delay
- `job.default_timeout_seconds` - Default job timeout

### Audit Settings

**Category:** `AUDIT`

**Examples:**
- `audit.retention_days` - Audit log retention period

### Policy Settings

**Category:** `POLICY`

**Examples:**
- `policy.default_priority` - Default policy priority
- `system.environment` - Environment name (used in policy context)

**Policy Context Integration:**
The policy engine automatically uses the `system.environment` setting for policy evaluation context:

```python
# Policy evaluation context includes environment from settings
from swx_core.services.policy.dependencies import require_policy

@router.get("/resource/{id}")
async def get_resource(
    id: UUID,
    _policy: None = Depends(require_policy("resource:read", "resource", resource_id=id))
):
    # Policy context automatically includes:
    # - environment: from settings.service.get_string("system.environment")
    # - timestamp: current time
    # - ip_address: from request
    # - user_agent: from request headers
    ...
```

### General Settings

**Category:** `GENERAL`

**Examples:**
- `system.maintenance_mode` - Enable maintenance mode

---

## Usage Examples

### Reading Settings

**In Route Handler:**
```python
from swx_core.services.settings_helper import get_token_expiration

@router.post("/auth/login")
async def login(session: SessionDep, ...):
    # Get token expiration from settings
    access_expires = await get_token_expiration(session, "access")
    refresh_expires = await get_token_expiration(session, "refresh")
    
    # Create tokens
    access_token = create_token(..., expires_delta=access_expires)
    refresh_token = await create_refresh_token(..., expires_delta=refresh_expires)
    
    return Token(access_token=access_token, refresh_token=refresh_token)
```

**In Service:**
```python
from swx_core.services.settings_service import get_settings_service

async def process_job(session: AsyncSession, job: Job):
    service = get_settings_service(session)
    
    # Get job settings
    max_attempts = await service.get_int("job.default_max_attempts", default=3)
    timeout = await service.get_int("job.default_timeout_seconds", default=300)
    
    # Use settings
    if job.attempts >= max_attempts:
        raise Exception("Max attempts reached")
    
    # Process with timeout
    ...
```

### Updating Settings

**Runtime Update:**
```python
# Update setting via API
PATCH /api/admin/settings/key/auth.access_token_expire_minutes
{
  "value": "14400"  # 10 days
}

# Setting applies immediately (cache invalidated)
# No redeploy required
```

**Cache Invalidation:**
```python
# Cache automatically invalidated on update
# Next read will fetch from database
# Cache refreshed with new value
```

---

## Migration Guide

### Migrating from .env to Database

**Step 1: Identify Settings to Migrate**

**Migrate to DB:**
- Token expiration values
- Rate limit values
- Feature flags
- Email from address
- Job settings
- Audit retention

**Keep in .env:**
- Secrets (passwords, API keys)
- Infrastructure config (database URL, Redis URL)
- Build-time config (environment name)

**Step 2: Create Settings**

**Via Seed Script:**
```python
# scripts/seed_settings.py
DEFAULT_SETTINGS = [
    {
        "key": "auth.access_token_expire_minutes",
        "value": str(settings.ACCESS_TOKEN_EXPIRE_MINUTES),  # From .env
        "value_type": "int",
        "category": "security",
    },
    # ... more settings
]
```

**Step 3: Update Code**

**Before:**
```python
from swx_core.config.settings import settings

access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
```

**After:**
```python
from swx_core.services.settings_helper import get_token_expiration

access_token_expires = await get_token_expiration(session, "access")
```

**Step 4: Test**

**Verify settings work:**
- Update setting via API
- Verify change applies immediately
- Verify cache invalidation works
- Verify audit log created

---

## Best Practices

### ✅ DO

1. **Use settings service for runtime config**
   ```python
   # ✅ Good - Runtime configurable
   timeout = await service.get_int("job.timeout", default=300)
   ```

2. **Keep secrets in .env**
   ```python
   # ✅ Good - Secret in .env
   SECRET_KEY=your-secret-key  # In .env
   
   # ❌ Bad - Secret in database
   # Never store secrets in system_config
   ```

3. **Use type-safe getters**
   ```python
   # ✅ Good - Type-safe
   value = await service.get_int("setting.key", default=100)
   
   # ❌ Bad - Manual parsing
   value_str = await service.get("setting.key", default="100")
   value = int(value_str)  # Error-prone
   ```

4. **Provide safe defaults**
   ```python
   # ✅ Good - Safe default
   value = await service.get_int("critical.setting", default=60)
   
   # ❌ Bad - No default
   value = await service.get_int("critical.setting")  # May fail
   ```

5. **Document settings**
   ```python
   # ✅ Good - Documented
   {
       "key": "auth.access_token_expire_minutes",
       "description": "Access token expiration in minutes",
       "category": "security"
   }
   ```

### ❌ DON'T

1. **Don't store secrets in database**
   ```python
   # ❌ Bad - Secret in database
   {
       "key": "stripe.secret_key",
       "value": "sk_live_..."  # DON'T DO THIS
   }
   
   # ✅ Good - Secret in .env
   STRIPE_SECRET_KEY=sk_live_...  # In .env
   ```

2. **Don't skip validation**
   ```python
   # ❌ Bad - No validation
   await service.set("key", "invalid_value")
   
   # ✅ Good - Validated
   # Validation happens automatically in settings service
   ```

3. **Don't forget cache invalidation**
   ```python
   # ✅ Good - Automatic invalidation
   # Cache invalidated on update automatically
   ```

---

## Troubleshooting

### Common Issues

**1. Setting not found**
- Check if setting exists in database
- Verify setting key is correct
- Check if setting is active
- Verify fallback to .env works

**2. Setting not applying**
- Check cache invalidation
- Verify setting update succeeded
- Check if setting is active
- Review cache TTL

**3. Invalid value error**
- Check value type matches setting type
- Verify value format (int, bool, string, json)
- Check validation guards
- Review error message

**4. Cache not invalidating**
- Verify cache invalidation is called
- Check cache TTL (default: 60 seconds)
- Manually invalidate cache if needed
- Review cache implementation

### Debugging

**Check setting value:**
```python
from swx_core.services.settings_service import get_settings_service

service = get_settings_service(session)
value = await service.get("auth.access_token_expire_minutes")
print(f"Value: {value}")
```

**Check cache:**
```python
# Cache is internal, but you can check via service
# Cache automatically refreshes every 60 seconds
```

**List all settings:**
```python
from swx_core.repositories.system_config_repository import get_all_settings

settings = await get_all_settings(session)
for setting in settings:
    print(f"{setting.key} = {setting.value}")
```

---

## Next Steps

- Read [Settings Architecture](../docs/SETTINGS_ARCHITECTURE.md) for detailed design
- Read [Settings Quick Reference](../docs/SETTINGS_QUICK_REFERENCE.md) for quick lookup
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production setup

---

**Status:** Runtime settings system documented, ready for implementation.
