from typing import List, Dict, Any, Optional
import asyncio
import os
from swx_core.services.channels.models import Alert, AlertSeverity, AlertSource, AlertActorType
from swx_core.services.channels.base import AlertChannel
from swx_core.services.channels.log_channel import LogChannel
from swx_core.services.channels.slack_channel import SlackChannel
from swx_core.services.channels.email_channel import EmailChannel
from swx_core.services.channels.sms_channel import SmsChannel
from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger

class AlertEngine:
    """
    Central alert engine for dispatching alerts across multiple channels.
    """
    
    def __init__(self):
        self.environment = settings.ENVIRONMENT
        self.channels: Dict[str, AlertChannel] = {
            "log": LogChannel(),
            "slack": SlackChannel(),
            "email": EmailChannel(),
            "sms": SmsChannel()
        }

    async def emit(
        self,
        severity: AlertSeverity,
        source: AlertSource,
        event_type: str,
        message: str,
        actor_type: AlertActorType = AlertActorType.NONE,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Emits an alert. Structured details go into metadata.
        """
        # 1. Create Alert object
        alert = Alert(
            severity=severity,
            source=source,
            event_type=event_type,
            message=message,
            environment=self.environment,
            actor_type=actor_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=self._filter_sensitive_data(metadata or {})
        )

        # 2. Determine target channels based on policy
        target_channels = self._get_target_channels(alert)

        # 3. Dispatch to channels asynchronously without blocking the caller
        # We use background tasks or fire-and-forget for this in production.
        # Since this is a service, we'll create a task for it.
        asyncio.create_task(self._dispatch(alert, target_channels))

    async def _dispatch(self, alert: Alert, target_channel_names: List[str]) -> None:
        """
        Actually sends the alert to the selected channels.
        """
        tasks = []
        for name in target_channel_names:
            channel = self.channels.get(name)
            if channel:
                tasks.append(self._send_to_channel(name, channel, alert))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_to_channel(self, name: str, channel: AlertChannel, alert: Alert) -> None:
        try:
            success = await channel.send(alert)
            if not success:
                logger.warning(f"Failed to send alert to channel: {name}")
        except Exception as e:
            logger.error(f"Error dispatching alert to channel {name}: {e}")

    def _get_target_channels(self, alert: Alert) -> List[str]:
        """
        Policy-driven routing logic.
        """
        targets = ["log"]  # Always log
        
        # Critical alerts go everywhere possible
        if alert.severity == AlertSeverity.CRITICAL:
            targets.extend(["slack", "email"])
        
        # Production errors go to Slack
        elif alert.severity == AlertSeverity.ERROR and self.environment == "production":
            targets.append("slack")
            
        # Security alerts (RBAC/Auth) go to Slack regardless of environment if Warning+
        elif alert.source in [AlertSource.AUTH, AlertSource.RBAC, AlertSource.POLICY] and alert.severity >= AlertSeverity.WARNING:
            if "slack" not in targets:
                targets.append("slack")
                
        return list(set(targets))

    def _filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively filters sensitive keys from metadata.
        """
        sensitive_keys = {
            "password", "hashed_password", "token", "access_token", "refresh_token",
            "secret", "secret_key", "client_secret", "authorization", "cookie"
        }
        
        filtered = {}
        for k, v in data.items():
            if k.lower() in sensitive_keys:
                filtered[k] = "[REDACTED]"
            elif isinstance(v, dict):
                filtered[k] = self._filter_sensitive_data(v)
            else:
                filtered[k] = v
        return filtered

    async def get_health_status(self) -> Dict[str, bool]:
        status = {}
        for name, channel in self.channels.items():
            try:
                status[name] = await channel.health_check()
            except Exception:
                status[name] = False
        return status

# Singleton instance
alert_engine = AlertEngine()
