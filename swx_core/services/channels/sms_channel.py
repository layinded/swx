from swx_core.services.channels.base import AlertChannel
from swx_core.services.channels.models import Alert
from swx_core.middleware.logging_middleware import logger

class SmsChannel(AlertChannel):
    """
    SMS delivery channel placeholder.
    """
    
    def __init__(self):
        self.enabled = False

    async def send(self, alert: Alert) -> bool:
        """
        Stub implementation for SMS alerts.
        Integrate with Twilio or another provider here.
        """
        logger.info(f"SMS Alert (STUB): {alert.message}")
        return True

    async def health_check(self) -> bool:
        return False
