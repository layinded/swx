import json
from swx_core.services.channels.base import AlertChannel
from swx_core.services.channels.models import Alert, AlertSeverity
from swx_core.middleware.logging_middleware import logger

class LogChannel(AlertChannel):
    """
    Structured JSON log channel for alerts.
    """
    
    async def send(self, alert: Alert) -> bool:
        log_data = alert.model_dump()
        # Convert UUID and DateTime to string for JSON serialization
        log_data["alert_id"] = str(log_data["alert_id"])
        log_data["timestamp"] = log_data["timestamp"].isoformat()
        
        log_msg = json.dumps(log_data)
        
        if alert.severity == AlertSeverity.CRITICAL:
            logger.critical(f"ALERT: {log_msg}")
        elif alert.severity == AlertSeverity.ERROR:
            logger.error(f"ALERT: {log_msg}")
        elif alert.severity == AlertSeverity.WARNING:
            logger.warning(f"ALERT: {log_msg}")
        else:
            logger.info(f"ALERT: {log_msg}")
            
        return True

    async def health_check(self) -> bool:
        return True
