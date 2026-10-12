from swx_core.services.channels.base import AlertChannel
from swx_core.services.channels.models import Alert
from swx_core.email.email_service import send_email
from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger
import os

class EmailChannel(AlertChannel):
    """
    Email delivery channel for alerts.
    """
    
    def __init__(self):
        self.enabled = settings.emails_enabled and bool(os.getenv("ALERT_EMAIL_RECIPIENTS"))
        self.recipients = os.getenv("ALERT_EMAIL_RECIPIENTS", "").split(",")

    async def send(self, alert: Alert) -> bool:
        if not self.enabled:
            return False
            
        subject = f"[{alert.severity.upper()}] Alert: {alert.message[:50]}"
        
        body = f"""
        <h2>SwX-API Alert</h2>
        <p><strong>Message:</strong> {alert.message}</p>
        <p><strong>Severity:</strong> {alert.severity.value}</p>
        <p><strong>Source:</strong> {alert.source.value}</p>
        <p><strong>Event Type:</strong> {alert.event_type}</p>
        <p><strong>Environment:</strong> {alert.environment}</p>
        <p><strong>Timestamp:</strong> {alert.timestamp.isoformat()}</p>
        <p><strong>Alert ID:</strong> {alert.alert_id}</p>
        <hr>
        <h3>Metadata:</h3>
        <pre>{alert.metadata}</pre>
        """
        
        try:
            for recipient in self.recipients:
                send_email(
                    email_to=recipient.strip(),
                    subject=subject,
                    html_content=body
                )
            return True
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    async def health_check(self) -> bool:
        return self.enabled
