# Audit Logging

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [What Is Logged](#what-is-logged)
3. [What Is Not Logged](#what-is-not-logged)
4. [Immutability Guarantees](#immutability-guarantees)
5. [Access Controls](#access-controls)
6. [Querying Audit Logs](#querying-audit-logs)
7. [Usage Examples](#usage-examples)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

SwX-API includes a **comprehensive audit logging system** that records all security-relevant and business-relevant events. Audit logs provide:

- **Complete accountability** - Who did what, when, and why
- **Compliance support** - Immutable records for regulatory requirements
- **Security monitoring** - Track suspicious activities
- **Debugging** - Trace request flows and failures

### Key Features

- ✅ **Immutable** - Records cannot be modified or deleted
- ✅ **Append-only** - New records only, no updates
- ✅ **Structured** - JSON context for querying
- ✅ **Filtered** - Sensitive data automatically redacted
- ✅ **Indexed** - Fast queries by actor, action, resource
- ✅ **Complete** - All security and business events logged

---

## What Is Logged

### Security-Relevant Events

#### Authentication

**Login Success:**
```python
await audit.log_event(
    action="auth.login",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    outcome=AuditOutcome.SUCCESS,
    context={"email": user.email},
    request=request
)
```

**Login Failure:**
```python
await audit.log_event(
    action="auth.login",
    actor_type=ActorType.USER,
    actor_id=email,  # Email if known
    outcome=AuditOutcome.FAILURE,
    context={"reason": "Invalid credentials"},
    request=request
)
```

**Token Refresh:**
```python
await audit.log_event(
    action="auth.token.refresh",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    outcome=AuditOutcome.SUCCESS,
    request=request
)
```

**Password Reset:**
```python
await audit.log_event(
    action="auth.password.reset",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    outcome=AuditOutcome.SUCCESS,
    request=request
)
```

#### Authorization

**Permission Denied:**
```python
await audit.log_event(
    action="permission.denied",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    resource_type="user",
    resource_id=str(target_user.id),
    outcome=AuditOutcome.FAILURE,
    context={"permission": "user:delete"},
    request=request
)
```

**Policy Denied:**
```python
await audit.log_event(
    action="policy.denied",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    resource_type="team",
    resource_id=str(team.id),
    outcome=AuditOutcome.FAILURE,
    context={"policy_id": "team.update.owner", "reason": "Not team owner"},
    request=request
)
```

**Rate Limit Exceeded:**
```python
await audit.log_event(
    action="rate_limit.exceeded",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    resource_type="rate_limit",
    resource_id="api_requests:read",
    outcome=AuditOutcome.FAILURE,
    context={"limit": 10000, "feature": "api_requests", "endpoint_class": "read"},
    request=request
)
```

### Business-Relevant Events

#### Identity Lifecycle

**User Creation:**
```python
await audit.log_event(
    action="user.create",
    actor_type=ActorType.ADMIN,
    actor_id=str(admin.id),
    resource_type="user",
    resource_id=str(user.id),
    outcome=AuditOutcome.SUCCESS,
    context={"email": user.email},
    request=request
)
```

**User Update:**
```python
await audit.log_event(
    action="user.update",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    resource_type="user",
    resource_id=str(user.id),
    outcome=AuditOutcome.SUCCESS,
    context={"fields_updated": ["name", "email"]},
    request=request
)
```

**User Deletion:**
```python
await audit.log_event(
    action="user.delete",
    actor_type=ActorType.ADMIN,
    actor_id=str(admin.id),
    resource_type="user",
    resource_id=str(user.id),
    outcome=AuditOutcome.SUCCESS,
    context={"email": user.email},
    request=request
)
```

#### RBAC Lifecycle

**Role Creation:**
```python
await audit.log_event(
    action="role.create",
    actor_type=ActorType.ADMIN,
    actor_id=str(admin.id),
    resource_type="role",
    resource_id=str(role.id),
    outcome=AuditOutcome.SUCCESS,
    context={"name": role.name, "domain": role.domain},
    request=request
)
```

**Permission Assignment:**
```python
await audit.log_event(
    action="role.permission.assign",
    actor_type=ActorType.ADMIN,
    actor_id=str(admin.id),
    resource_type="role",
    resource_id=str(role.id),
    outcome=AuditOutcome.SUCCESS,
    context={"permission_id": str(permission.id)},
    request=request
)
```

**User-Role Assignment:**
```python
await audit.log_event(
    action="user.role.assign",
    actor_type=ActorType.ADMIN,
    actor_id=str(admin.id),
    resource_type="user",
    resource_id=str(user.id),
    outcome=AuditOutcome.SUCCESS,
    context={"role_id": str(role.id), "team_id": str(team.id) if team_id else None},
    request=request
)
```

#### Team Events

**Team Creation:**
```python
await audit.log_event(
    action="team.create",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    resource_type="team",
    resource_id=str(team.id),
    outcome=AuditOutcome.SUCCESS,
    context={"name": team.name},
    request=request
)
```

**Team Member Added:**
```python
await audit.log_event(
    action="team.member.add",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    resource_type="team",
    resource_id=str(team.id),
    outcome=AuditOutcome.SUCCESS,
    context={"member_id": str(member.id), "role": member.role},
    request=request
)
```

#### Billing Events

**Subscription Created:**
```python
await audit.log_event(
    action="billing.subscription.create",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    resource_type="subscription",
    resource_id=str(subscription.id),
    outcome=AuditOutcome.SUCCESS,
    context={"plan_id": str(plan.id), "stripe_subscription_id": subscription.stripe_subscription_id},
    request=request
)
```

**Plan Changed:**
```python
await audit.log_event(
    action="billing.plan.change",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    resource_type="subscription",
    resource_id=str(subscription.id),
    outcome=AuditOutcome.SUCCESS,
    context={"old_plan": old_plan.key, "new_plan": new_plan.key},
    request=request
)
```

#### System Events

**Settings Updated:**
```python
await audit.log_event(
    action="system_config.update",
    actor_type=ActorType.ADMIN,
    actor_id=str(admin.id),
    resource_type="system_config",
    resource_id=str(config.id),
    outcome=AuditOutcome.SUCCESS,
    context={"key": config.key, "old_value": old_value, "new_value": config.value},
    request=request
)
```

**Policy Evaluated:**
```python
await audit.log_event(
    action="policy.evaluate",
    actor_type=ActorType.USER,
    actor_id=str(user.id),
    resource_type="policy",
    resource_id=policy_id,
    outcome=AuditOutcome.SUCCESS if allowed else AuditOutcome.FAILURE,
    context={"action": action, "decision": decision, "evaluations": evaluations},
    request=request
)
```

---

## What Is Not Logged

### Sensitive Data

**Automatically Filtered:**
- Passwords (hashed or plaintext)
- Tokens (access, refresh, reset)
- Secrets (API keys, client secrets)
- Authorization headers
- Cookies

**Filtering:**
```python
def _filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
    sensitive_keys = {
        "password", "hashed_password", "token", "access_token", "refresh_token",
        "secret", "secret_key", "client_secret", "authorization", "cookie"
    }
    # Recursively filter sensitive keys
    # Replace with "[REDACTED]"
```

### High-Volume Events

**Not Logged:**
- Every API request (use access logs instead)
- Health check requests
- Static asset requests
- Metrics collection requests

**Logged:**
- Security events (auth, authorization)
- Business events (user creation, billing)
- Administrative actions (settings, policies)

---

## Immutability Guarantees

### Database Constraints

**No Updates:**
- Audit logs cannot be updated (no UPDATE statements)
- Database constraints prevent modifications

**No Deletes:**
- Audit logs cannot be deleted (no DELETE statements)
- Database constraints prevent deletions

**Append-Only:**
- Only INSERT operations allowed
- No modifications to existing records

### Application-Level Protection

**No Update Methods:**
```python
# ❌ No update method exists
# audit.update_log(...)  # Does not exist

# ✅ Only create method
await audit.log_event(...)
```

**No Delete Methods:**
```python
# ❌ No delete method exists
# audit.delete_log(...)  # Does not exist

# ✅ Only create method
await audit.log_event(...)
```

### Retention Policy

**Configurable Retention:**
- Default: 365 days (configurable via settings)
- Older logs can be archived (not deleted)
- Compliance requirements may extend retention

**Settings:**
```python
# Runtime setting
audit.retention_days = 365  # Configurable in database
```

---

## Access Controls

### Admin-Only Access

**Audit logs are admin-only:**
```python
from swx_core.auth.admin.dependencies import AdminUserDep

@router.get("/admin/audit/")
async def list_audit_logs(
    admin: AdminUserDep,
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
):
    # Only admin users can access
    ...
```

### Filtering

**By Actor:**
```python
# Get logs for specific user
logs = await get_audit_logs(
    session,
    actor_id=str(user.id),
    skip=0,
    limit=100
)
```

**By Action:**
```python
# Get all login attempts
logs = await get_audit_logs(
    session,
    action="auth.login",
    skip=0,
    limit=100
)
```

**By Resource:**
```python
# Get all events for a team
logs = await get_audit_logs(
    session,
    resource_type="team",
    resource_id=str(team.id),
    skip=0,
    limit=100
)
```

**By Time Range:**
```python
# Get logs from last 24 hours
from datetime import datetime, timedelta

logs = await get_audit_logs(
    session,
    start_time=datetime.utcnow() - timedelta(days=1),
    end_time=datetime.utcnow(),
    skip=0,
    limit=100
)
```

---

## Querying Audit Logs

### Via API

**List Audit Logs:**
```bash
GET /api/admin/audit/?skip=0&limit=100&actor_id=user-123&action=auth.login
```

**Get Specific Log:**
```bash
GET /api/admin/audit/{log_id}
```

**Filter by Multiple Criteria:**
```bash
GET /api/admin/audit/?actor_type=user&resource_type=team&outcome=success
```

### Via Code

**Using Repository:**
```python
from swx_core.repositories.audit_log_repository import get_audit_logs

logs = await get_audit_logs(
    session,
    actor_id=str(user.id),
    action="auth.login",
    skip=0,
    limit=100
)
```

**Direct Query:**
```python
from swx_core.models.audit_log import AuditLog
from sqlmodel import select, and_

stmt = select(AuditLog).where(
    and_(
        AuditLog.actor_id == str(user.id),
        AuditLog.action == "auth.login"
    )
).order_by(AuditLog.timestamp.desc()).limit(100)

result = await session.execute(stmt)
logs = result.scalars().all()
```

---

## Usage Examples

### Logging in Route Handler

```python
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome

@router.post("/users")
async def create_user(
    user_in: UserCreate,
    admin: AdminUserDep,
    session: SessionDep,
    request: Request,
):
    audit = get_audit_logger(session)
    
    try:
        user = await create_user_service(session, user_in)
        
        await audit.log_event(
            action="user.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(admin.id),
            resource_type="user",
            resource_id=str(user.id),
            outcome=AuditOutcome.SUCCESS,
            context={"email": user.email},
            request=request
        )
        
        return user
    except Exception as e:
        await audit.log_event(
            action="user.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(admin.id),
            resource_type="user",
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise
```

### Logging in Service

```python
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome

async def update_user_service(
    session: AsyncSession,
    user: User,
    user_update: UserUpdate,
    request: Request,
):
    audit = get_audit_logger(session)
    
    # Update user
    updated_user = await update_user_repository(session, user, user_update)
    
    # Log event
    await audit.log_event(
        action="user.update",
        actor_type=ActorType.USER,
        actor_id=str(user.id),
        resource_type="user",
        resource_id=str(user.id),
        outcome=AuditOutcome.SUCCESS,
        context={"fields_updated": list(user_update.model_dump(exclude_unset=True).keys())},
        request=request
    )
    
    return updated_user
```

### Automatic Logging via Middleware

**Audit middleware automatically logs:**
- All authenticated requests
- All authorization decisions
- All policy evaluations
- All rate limit events

**No manual logging required for these events.**

---

## Best Practices

### ✅ DO

1. **Log all security events**
   ```python
   # ✅ Good - Log auth failures
   await audit.log_event(
       action="auth.login",
       outcome=AuditOutcome.FAILURE,
       context={"reason": "Invalid password"}
   )
   ```

2. **Log business-critical events**
   ```python
   # ✅ Good - Log user creation
   await audit.log_event(
       action="user.create",
       resource_type="user",
       resource_id=str(user.id),
       outcome=AuditOutcome.SUCCESS
   )
   ```

3. **Include context**
   ```python
   # ✅ Good - Include relevant context
   await audit.log_event(
       action="team.member.add",
       context={"member_id": str(member.id), "role": member.role}
   )
   ```

4. **Log both success and failure**
   ```python
   # ✅ Good - Log both outcomes
   try:
       result = await operation()
       await audit.log_event(..., outcome=AuditOutcome.SUCCESS)
   except Exception as e:
       await audit.log_event(..., outcome=AuditOutcome.FAILURE, context={"error": str(e)})
   ```

5. **Use consistent action names**
   ```python
   # ✅ Good - Consistent naming
   "user.create", "user.update", "user.delete"
   "team.create", "team.update", "team.delete"
   ```

### ❌ DON'T

1. **Don't log sensitive data**
   ```python
   # ❌ Bad - Password in context
   await audit.log_event(
       context={"password": user.password}  # Will be filtered, but don't include
   )
   
   # ✅ Good - No sensitive data
   await audit.log_event(
       context={"email": user.email}
   )
   ```

2. **Don't log high-volume events**
   ```python
   # ❌ Bad - Log every API request
   @router.get("/api/data")
   async def get_data():
       await audit.log_event(action="api.request")  # Too verbose
   
   # ✅ Good - Use access logs for this
   ```

3. **Don't skip failure logging**
   ```python
   # ❌ Bad - Only log success
   try:
       result = await operation()
       await audit.log_event(..., outcome=AuditOutcome.SUCCESS)
   except Exception:
       pass  # Failure not logged
   
   # ✅ Good - Log both
   try:
       result = await operation()
       await audit.log_event(..., outcome=AuditOutcome.SUCCESS)
   except Exception as e:
       await audit.log_event(..., outcome=AuditOutcome.FAILURE, context={"error": str(e)})
   ```

4. **Don't use inconsistent action names**
   ```python
   # ❌ Bad - Inconsistent
   "create_user", "updateUser", "delete-user"
   
   # ✅ Good - Consistent
   "user.create", "user.update", "user.delete"
   ```

---

## Troubleshooting

### Common Issues

**1. Audit logs not appearing**
- Check if audit logging is enabled
- Verify database connection
- Check for errors in application logs
- Verify actor information is correct

**2. Sensitive data in logs**
- Check if filtering is working
- Verify sensitive keys are in filter list
- Review context data before logging

**3. Performance issues**
- Check database indexes
- Verify query filters are used
- Consider archiving old logs
- Monitor query performance

**4. Missing events**
- Verify audit logging is called
- Check for exceptions in audit logger
- Review application logs for errors

### Debugging

**Check audit log entries:**
```python
from swx_core.repositories.audit_log_repository import get_audit_logs

logs = await get_audit_logs(session, actor_id=str(user.id), limit=10)
for log in logs:
    print(f"{log.timestamp}: {log.action} - {log.outcome}")
```

**Query directly:**
```sql
-- Get recent audit logs
SELECT * FROM audit_log
WHERE actor_id = 'user-123'
ORDER BY timestamp DESC
LIMIT 100;

-- Get failed login attempts
SELECT * FROM audit_log
WHERE action = 'auth.login'
AND outcome = 'failure'
ORDER BY timestamp DESC
LIMIT 100;
```

---

## Next Steps

- Read [Alerting Documentation](./ALERTING.md) for alert integration
- Read [Security Model](../05-security/SECURITY_MODEL.md) for security details
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production setup

---

**Status:** Audit logging documented, ready for implementation.
