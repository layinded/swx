# Alerting System

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Alert Model](#alert-model)
3. [Alert Channels](#alert-channels)
4. [Routing Rules](#routing-rules)
5. [Usage Examples](#usage-examples)
6. [Adding Custom Channels](#adding-custom-channels)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Overview

SwX-API includes a **multi-channel alerting system** that dispatches alerts to appropriate channels based on severity and source. Alerts are:

- **Structured** - Consistent alert format
- **Multi-channel** - Slack, Email, SMS, Logs
- **Policy-driven** - Routing based on severity and source
- **Fail-safe** - Alert failures don't block requests
- **Filtered** - Sensitive data automatically redacted

### Key Features

- ✅ **Multiple Channels** - Slack, Email, SMS, Logs
- ✅ **Severity Levels** - INFO, WARNING, ERROR, CRITICAL
- ✅ **Source Tracking** - API, Auth, RBAC, System, etc.
- ✅ **Policy Routing** - Automatic channel selection
- ✅ **Sensitive Data Filtering** - Automatic redaction
- ✅ **Non-blocking** - Async dispatch, doesn't block requests

---

## Alert Model

### Alert Structure

```python
class Alert(BaseModel):
    alert_id: UUID
    timestamp: datetime
    source: AlertSource  # API, AUTH, RBAC, SYSTEM, etc.
    event_type: str  # LOGIN_FAILURE, PERMISSION_DENIED, etc.
    severity: AlertSeverity  # INFO, WARNING, ERROR, CRITICAL
    environment: str  # dev, staging, prod
    actor_type: AlertActorType  # SYSTEM, ADMIN, USER, NONE
    actor_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    message: str  # Human-readable message
    metadata: Dict[str, Any]  # Structured context (no secrets)
```

### Severity Levels

1. **INFO** - Normal but significant events
   - Channels: Logs only
   - Example: User registration, successful login

2. **WARNING** - Potential issues that don't block service
   - Channels: Logs, Slack (low priority)
   - Example: Rate limit approaching, permission denied

3. **ERROR** - Errors that affect a single request or user
   - Channels: Logs, Slack
   - Example: API request failure, authentication error

4. **CRITICAL** - System-wide issues or security breaches
   - Channels: Logs, Slack, Email, SMS
   - Example: Database connection lost, security breach

### Alert Sources

- `API` - General API request handling errors
- `AUTH` - Authentication failures, token issues
- `RBAC` - Authorization denials, permission escalations
- `POLICY` - Policy evaluation denials
- `AUDIT` - Failures in the audit logging system
- `SYSTEM` - Lifecycle events (startup, shutdown, background tasks)
- `INFRA` - Infrastructure issues (database connectivity, cache failure)

---

## Alert Channels

### 1. Log Channel

**Purpose:** Always-on logging

**Characteristics:**
- Always enabled
- All alerts logged
- Structured JSON format
- No configuration required

**Usage:**
```python
# Automatically included in all alerts
# No explicit configuration needed
```

### 2. Slack Channel

**Purpose:** Real-time team notifications

**Configuration:**
```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_CHANNEL=#alerts
```

**Usage:**
```python
# Automatically used for WARNING+ alerts in production
# Or ERROR+ alerts in any environment
```

### 3. Email Channel

**Purpose:** Critical alerts via email

**Configuration:**
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@example.com
SMTP_PASSWORD=your-password
ALERT_EMAIL_TO=ops@example.com
```

**Usage:**
```python
# Automatically used for CRITICAL alerts
```

### 4. SMS Channel

**Purpose:** Critical alerts via SMS

**Configuration:**
```env
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=+1234567890
ALERT_SMS_TO=+1234567890
```

**Usage:**
```python
# Automatically used for CRITICAL alerts
# (if configured)
```

---

## Routing Rules

### Default Routing

**Always Log:**
- All alerts go to log channel

**CRITICAL Alerts:**
- Logs ✅
- Slack ✅
- Email ✅
- SMS ✅ (if configured)

**ERROR Alerts (Production):**
- Logs ✅
- Slack ✅

**WARNING Alerts (Security):**
- Logs ✅
- Slack ✅ (if AUTH, RBAC, or POLICY source)

**INFO Alerts:**
- Logs ✅ only

### Custom Routing

**Modify routing logic:**
```python
# swx_core/services/alert_engine.py

def _get_target_channels(self, alert: Alert) -> List[str]:
    targets = ["log"]  # Always log
    
    # Custom routing logic
    if alert.severity == AlertSeverity.CRITICAL:
        targets.extend(["slack", "email", "sms"])
    elif alert.event_type == "SECURITY_BREACH":
        targets.extend(["slack", "email"])
    # ... more rules
    
    return targets
```

---

## Usage Examples

### Emitting Alerts

**Basic Alert:**
```python
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource, AlertActorType

await alert_engine.emit(
    severity=AlertSeverity.WARNING,
    source=AlertSource.AUTH,
    event_type="LOGIN_FAILURE_BURST",
    message="Multiple failed login attempts detected",
    actor_type=AlertActorType.USER,
    actor_id=email,
    metadata={"attempts": 5, "ip": request.client.host}
)
```

**Critical Alert:**
```python
await alert_engine.emit(
    severity=AlertSeverity.CRITICAL,
    source=AlertSource.INFRA,
    event_type="DATABASE_CONNECTION_LOST",
    message="Database connection lost - all requests failing",
    actor_type=AlertActorType.SYSTEM,
    metadata={"error": str(e), "retry_count": 3}
)
```

**Security Alert:**
```python
await alert_engine.emit(
    severity=AlertSeverity.ERROR,
    source=AlertSource.RBAC,
    event_type="PERMISSION_DENIED_SENSITIVE",
    message=f"User {user.email} denied access to sensitive resource",
    actor_type=AlertActorType.USER,
    actor_id=str(user.id),
    resource_type="billing",
    resource_id=str(account.id),
    metadata={"permission": "billing:read", "path": request.url.path}
)
```

### Common Alert Patterns

**Authentication Failures:**
```python
# In auth service
if failed_attempts > 5:
    await alert_engine.emit(
        severity=AlertSeverity.WARNING,
        source=AlertSource.AUTH,
        event_type="LOGIN_FAILURE_BURST",
        message=f"Multiple failed login attempts for {email}",
        actor_type=AlertActorType.USER,
        actor_id=email,
        metadata={"attempts": failed_attempts, "ip": request.client.host}
    )
```

**Rate Limit Abuse:**
```python
# In rate limit middleware
if burst_abuse_detected:
    await alert_engine.emit(
        severity=AlertSeverity.WARNING,
        source=AlertSource.API,
        event_type="RATE_LIMIT_ABUSE",
        message=f"Rate limit abuse detected for {actor_id}",
        actor_type=AlertActorType.USER,
        actor_id=actor_id,
        metadata={"feature": feature, "limit": limit, "usage": usage}
    )
```

**Policy Denials:**
```python
# In policy engine
if sensitive_action_denied:
    await alert_engine.emit(
        severity=AlertSeverity.WARNING,
        source=AlertSource.POLICY,
        event_type="POLICY_DENIAL_SENSITIVE",
        message=f"Policy denied {action} for {actor_id}",
        actor_type=AlertActorType.USER,
        actor_id=str(actor.id),
        resource_type=resource_type,
        resource_id=str(resource.id),
        metadata={"policy_id": policy_id, "reason": reason}
    )
```

**System Failures:**
```python
# In system startup
if database_setup_failed:
    await alert_engine.emit(
        severity=AlertSeverity.CRITICAL,
        source=AlertSource.SYSTEM,
        event_type="STARTUP_FAILURE_DB",
        message="Application failed to start due to database setup error",
        actor_type=AlertActorType.SYSTEM,
        metadata={"error": str(e)}
    )
```

---

## Adding Custom Channels

### Creating a Channel

**1. Create Channel Class:**
```python
# swx_core/services/channels/custom_channel.py

from swx_core.services.channels.base import AlertChannel
from swx_core.services.channels.models import Alert

class CustomChannel(AlertChannel):
    async def send(self, alert: Alert) -> bool:
        """Send alert via custom channel."""
        try:
            # Your custom sending logic
            await self._send_to_custom_service(alert)
            return True
        except Exception as e:
            logger.error(f"Failed to send alert via custom channel: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if channel is healthy."""
        # Verify connectivity
        return True
```

**2. Register Channel:**
```python
# swx_core/services/alert_engine.py

from swx_core.services.channels.custom_channel import CustomChannel

class AlertEngine:
    def __init__(self):
        self.channels = {
            "log": LogChannel(),
            "slack": SlackChannel(),
            "email": EmailChannel(),
            "sms": SmsChannel(),
            "custom": CustomChannel(),  # Add custom channel
        }
```

**3. Update Routing:**
```python
def _get_target_channels(self, alert: Alert) -> List[str]:
    targets = ["log"]
    
    if alert.severity == AlertSeverity.CRITICAL:
        targets.extend(["slack", "email", "custom"])  # Include custom channel
    
    return targets
```

---

## Best Practices

### ✅ DO

1. **Use appropriate severity levels**
   ```python
   # ✅ Good - Correct severity
   await alert_engine.emit(
       severity=AlertSeverity.CRITICAL,  # System-wide issue
       source=AlertSource.INFRA,
       event_type="DATABASE_DOWN",
       message="Database connection lost"
   )
   
   # ❌ Bad - Wrong severity
   await alert_engine.emit(
       severity=AlertSeverity.CRITICAL,  # Too high for single user issue
       source=AlertSource.API,
       event_type="USER_REQUEST_FAILED",
       message="Single user request failed"
   )
   ```

2. **Include relevant metadata**
   ```python
   # ✅ Good - Useful metadata
   await alert_engine.emit(
       ...,
       metadata={
           "user_id": str(user.id),
           "ip": request.client.host,
           "path": request.url.path,
           "error_code": "RATE_LIMIT_EXCEEDED"
       }
   )
   ```

3. **Use descriptive event types**
   ```python
   # ✅ Good - Descriptive
   event_type="LOGIN_FAILURE_BURST"
   
   # ❌ Bad - Vague
   event_type="ERROR"
   ```

4. **Don't include sensitive data**
   ```python
   # ❌ Bad - Sensitive data (will be filtered, but don't include)
   await alert_engine.emit(
       ...,
       metadata={"password": user.password, "token": token}
   )
   
   # ✅ Good - No sensitive data
   await alert_engine.emit(
       ...,
       metadata={"user_id": str(user.id), "action": "login"}
   )
   ```

### ❌ DON'T

1. **Don't alert on every error**
   ```python
   # ❌ Bad - Too noisy
   await alert_engine.emit(
       severity=AlertSeverity.ERROR,
       event_type="API_ERROR",
       message="Every API error"
   )
   
   # ✅ Good - Alert on significant errors only
   if error_count > threshold:
       await alert_engine.emit(...)
   ```

2. **Don't block requests for alerts**
   ```python
   # ❌ Bad - Blocking
   await alert_engine.emit(...)  # If this fails, request fails
   
   # ✅ Good - Non-blocking (automatic)
   await alert_engine.emit(...)  # Fire-and-forget, doesn't block
   ```

---

## Troubleshooting

### Common Issues

**1. Alerts not reaching Slack**
- Verify `SLACK_WEBHOOK_URL` is set
- Check Slack webhook is valid
- Verify routing rules include Slack
- Check application logs for errors

**2. Alerts not reaching Email**
- Verify SMTP settings in .env
- Check email service is configured
- Verify routing rules include Email
- Check application logs for errors

**3. Too many alerts**
- Review routing rules
- Adjust severity thresholds
- Use alert aggregation
- Filter by environment

**4. Missing alerts**
- Check alert engine is initialized
- Verify channels are registered
- Check application logs for errors
- Verify alert emission is called

### Debugging

**Check channel health:**
```python
from swx_core.services.alert_engine import alert_engine

status = await alert_engine.get_health_status()
print(status)
# {"log": True, "slack": True, "email": False, "sms": False}
```

**Test alert:**
```python
await alert_engine.emit(
    severity=AlertSeverity.INFO,
    source=AlertSource.SYSTEM,
    event_type="TEST_ALERT",
    message="Test alert to verify channels",
    metadata={"test": True}
)
```

---

## Next Steps

- Read [Audit Logs Documentation](./AUDIT_LOGS.md) for audit integration
- Read [Background Jobs Documentation](./BACKGROUND_JOBS.md) for job-based alerts
- Read [Operations Guide](../08-operations/OPERATIONS.md) for production setup

---

**Status:** Alerting system documented, ready for implementation.
