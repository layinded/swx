# Adding Alert Channels

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Channel Interface](#channel-interface)
3. [Creating a Channel](#creating-a-channel)
4. [Registering a Channel](#registering-a-channel)
5. [Channel Configuration](#channel-configuration)
6. [Example: Discord Channel](#example-discord-channel)
7. [Best Practices](#best-practices)

---

## Overview

SwX-API supports **multiple alert channels** for delivering alerts. This guide covers how to create and register custom alert channels.

### Built-in Channels

- **Log Channel** - Always enabled, logs all alerts
- **Slack Channel** - Slack webhook integration
- **Email Channel** - SMTP email delivery
- **SMS Channel** - Twilio SMS delivery

### Custom Channels

You can add custom channels for:
- Discord webhooks
- Microsoft Teams
- PagerDuty
- Custom webhooks
- Any other notification service

---

## Channel Interface

### Base Channel Class

**Interface:**
```python
from swx_core.services.channels.base import AlertChannel
from swx_core.services.channels.models import Alert

class AlertChannel(ABC):
    @abstractmethod
    async def send(self, alert: Alert) -> bool:
        """Send alert to channel."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if channel is healthy."""
        pass
```

### Alert Model

**Alert Structure:**
```python
class Alert(BaseModel):
    alert_id: UUID
    timestamp: datetime
    source: AlertSource  # API, AUTH, RBAC, etc.
    event_type: str  # LOGIN_FAILURE, etc.
    severity: AlertSeverity  # INFO, WARNING, ERROR, CRITICAL
    environment: str  # dev, staging, prod
    actor_type: AlertActorType  # SYSTEM, ADMIN, USER, NONE
    actor_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    message: str  # Human-readable message
    metadata: Dict[str, Any]  # Structured context
```

---

## Creating a Channel

### Step 1: Create Channel Class

**Channel Implementation:**
```python
# swx_app/services/channels/discord_channel.py
from swx_core.services.channels.base import AlertChannel
from swx_core.services.channels.models import Alert, AlertSeverity
from swx_core.middleware.logging_middleware import logger
import httpx
import os

class DiscordChannel(AlertChannel):
    """Discord webhook channel for alerts."""
    
    def __init__(self):
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)
    
    async def send(self, alert: Alert) -> bool:
        """Send alert to Discord."""
        if not self.enabled:
            return False
        
        # Format Discord message
        color = self._get_severity_color(alert.severity)
        
        payload = {
            "embeds": [
                {
                    "title": alert.message,
                    "description": f"**Source:** {alert.source.value}\n**Event:** {alert.event_type}",
                    "color": color,
                    "timestamp": alert.timestamp.isoformat(),
                    "fields": [
                        {"name": "Severity", "value": alert.severity.value, "inline": True},
                        {"name": "Environment", "value": alert.environment, "inline": True},
                    ],
                    "footer": {"text": f"Alert ID: {alert.alert_id}"}
                }
            ]
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if Discord channel is healthy."""
        if not self.enabled:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.webhook_url)
                return response.status_code == 200
        except Exception:
            return False
    
    def _get_severity_color(self, severity: AlertSeverity) -> int:
        """Get Discord embed color for severity."""
        colors = {
            AlertSeverity.INFO: 0x3498db,      # Blue
            AlertSeverity.WARNING: 0xf39c12,   # Orange
            AlertSeverity.ERROR: 0xe74c3c,     # Red
            AlertSeverity.CRITICAL: 0x8b0000,  # Dark red
        }
        return colors.get(severity, 0x95a5a6)  # Default gray
```

### Step 2: Register Channel

**Register in Alert Engine:**
```python
# swx_core/services/alert_engine.py
from swx_app.services.channels.discord_channel import DiscordChannel

class AlertEngine:
    def __init__(self):
        self.channels = {
            "log": LogChannel(),
            "slack": SlackChannel(),
            "email": EmailChannel(),
            "sms": SmsChannel(),
            "discord": DiscordChannel(),  # Add custom channel
        }
```

### Step 3: Update Routing

**Update Routing Logic:**
```python
# swx_core/services/alert_engine.py
def _get_target_channels(self, alert: Alert) -> List[str]:
    targets = ["log"]  # Always log
    
    if alert.severity == AlertSeverity.CRITICAL:
        targets.extend(["slack", "email", "discord"])  # Include custom channel
    elif alert.severity == AlertSeverity.ERROR:
        targets.append("discord")  # Include custom channel
    
    return targets
```

---

## Registering a Channel

### Method 1: Code Registration

**At Startup:**
```python
# swx_core/main.py
from swx_app.services.channels.discord_channel import DiscordChannel
from swx_core.services.alert_engine import alert_engine

# Register channel
alert_engine.channels["discord"] = DiscordChannel()
```

### Method 2: Configuration-Based

**Via Settings:**
```python
# swx_core/services/alert_engine.py
def __init__(self):
    self.channels = {
        "log": LogChannel(),
        "slack": SlackChannel(),
        "email": EmailChannel(),
        "sms": SmsChannel(),
    }
    
    # Load custom channels from configuration
    custom_channels = self._load_custom_channels()
    self.channels.update(custom_channels)
```

---

## Channel Configuration

### Environment Variables

**Discord Webhook:**
```bash
# .env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR/WEBHOOK/URL
```

**Microsoft Teams:**
```bash
# .env
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/YOUR/WEBHOOK/URL
```

**PagerDuty:**
```bash
# .env
PAGERDUTY_INTEGRATION_KEY=your-integration-key
```

### Configuration Validation

**Check Configuration:**
```python
def __init__(self):
    self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not self.webhook_url:
        logger.warning("Discord webhook URL not configured")
    self.enabled = bool(self.webhook_url)
```

---

## Example: Discord Channel

### Complete Implementation

**Discord Channel:**
```python
# swx_app/services/channels/discord_channel.py
from swx_core.services.channels.base import AlertChannel
from swx_core.services.channels.models import Alert, AlertSeverity
from swx_core.middleware.logging_middleware import logger
import httpx
import os

class DiscordChannel(AlertChannel):
    """Discord webhook channel for alerts."""
    
    def __init__(self):
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)
    
    async def send(self, alert: Alert) -> bool:
        if not self.enabled:
            return False
        
        color = self._get_severity_color(alert.severity)
        
        payload = {
            "embeds": [
                {
                    "title": alert.message,
                    "description": f"**Source:** {alert.source.value}\n**Event:** {alert.event_type}",
                    "color": color,
                    "timestamp": alert.timestamp.isoformat(),
                    "fields": [
                        {"name": "Severity", "value": alert.severity.value, "inline": True},
                        {"name": "Environment", "value": alert.environment, "inline": True},
                    ]
                }
            ]
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False
    
    async def health_check(self) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.webhook_url)
                return response.status_code == 200
        except Exception:
            return False
    
    def _get_severity_color(self, severity: AlertSeverity) -> int:
        colors = {
            AlertSeverity.INFO: 0x3498db,
            AlertSeverity.WARNING: 0xf39c12,
            AlertSeverity.ERROR: 0xe74c3c,
            AlertSeverity.CRITICAL: 0x8b0000,
        }
        return colors.get(severity, 0x95a5a6)
```

**Register Channel:**
```python
# swx_core/services/alert_engine.py
from swx_app.services.channels.discord_channel import DiscordChannel

class AlertEngine:
    def __init__(self):
        self.channels = {
            "log": LogChannel(),
            "slack": SlackChannel(),
            "email": EmailChannel(),
            "sms": SmsChannel(),
            "discord": DiscordChannel(),  # Register custom channel
        }
```

**Update Routing:**
```python
def _get_target_channels(self, alert: Alert) -> List[str]:
    targets = ["log"]
    
    if alert.severity == AlertSeverity.CRITICAL:
        targets.extend(["slack", "email", "discord"])
    elif alert.severity == AlertSeverity.ERROR:
        targets.append("discord")
    
    return targets
```

---

## Best Practices

### ✅ DO

1. **Implement both methods**
   ```python
   # ✅ Good - Both methods implemented
   async def send(self, alert: Alert) -> bool:
       ...
   
   async def health_check(self) -> bool:
       ...
   ```

2. **Handle errors gracefully**
   ```python
   # ✅ Good - Error handling
   try:
       response = await client.post(url, json=payload)
       response.raise_for_status()
       return True
   except Exception as e:
       logger.error(f"Failed to send alert: {e}")
       return False
   ```

3. **Check configuration**
   ```python
   # ✅ Good - Configuration check
   def __init__(self):
       self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
       self.enabled = bool(self.webhook_url)
   ```

4. **Use async HTTP client**
   ```python
   # ✅ Good - Async client
   async with httpx.AsyncClient(timeout=10.0) as client:
       response = await client.post(url, json=payload)
   ```

### ❌ DON'T

1. **Don't block the event loop**
   ```python
   # ❌ Bad - Blocking
   import requests
   response = requests.post(url, json=payload)  # DON'T DO THIS
   
   # ✅ Good - Async
   async with httpx.AsyncClient() as client:
       response = await client.post(url, json=payload)
   ```

2. **Don't ignore errors**
   ```python
   # ❌ Bad - Errors ignored
   try:
       await send_alert(alert)
   except:
       pass  # DON'T DO THIS
   
   # ✅ Good - Log errors
   except Exception as e:
       logger.error(f"Failed to send alert: {e}")
       return False
   ```

---

## Next Steps

- Read [Alerting Documentation](../04-core-concepts/ALERTING.md) for alerting details
- Read [Extending Guide](./EXTENDING_SWX.md) for extension patterns
- Read [Adding Features](./ADDING_FEATURES.md) for feature development

---

**Status:** Adding alert channels guide documented, ready for implementation.
