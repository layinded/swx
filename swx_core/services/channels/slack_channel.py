import httpx
from swx_core.services.channels.base import AlertChannel
from swx_core.services.channels.models import Alert, AlertSeverity
from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger
import os

class SlackChannel(AlertChannel):
    """
    Slack webhook channel for alerts.
    """
    
    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)

    async def send(self, alert: Alert) -> bool:
        if not self.enabled:
            return False
            
        color = self._get_severity_color(alert.severity)
        
        payload = {
            "attachments": [
                {
                    "fallback": f"[{alert.severity.upper()}] {alert.message}",
                    "color": color,
                    "pretext": f"*Alert from {alert.environment.upper()}*",
                    "title": alert.message,
                    "fields": [
                        {"title": "Source", "value": alert.source.value, "short": True},
                        {"title": "Event Type", "value": alert.event_type, "short": True},
                        {"title": "Severity", "value": alert.severity.value, "short": True},
                        {"title": "Timestamp", "value": alert.timestamp.isoformat(), "short": True},
                    ],
                    "text": f"*Metadata:* \n```\n{alert.metadata}\n```",
                    "footer": f"Alert ID: {alert.alert_id}"
                }
            ]
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    async def health_check(self) -> bool:
        return self.enabled

    def _get_severity_color(self, severity: AlertSeverity) -> str:
        if severity == AlertSeverity.CRITICAL:
            return "#FF0000"  # Red
        if severity == AlertSeverity.ERROR:
            return "#E06666"  # Light Red
        if severity == AlertSeverity.WARNING:
            return "#F1C232"  # Yellow
        return "#999999"  # Grey
