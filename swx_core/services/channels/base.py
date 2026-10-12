from abc import ABC, abstractmethod
from swx_core.services.channels.models import Alert

class AlertChannel(ABC):
    """
    Base interface for all alert delivery channels.
    """
    
    @abstractmethod
    async def send(self, alert: Alert) -> bool:
        """
        Sends the alert to the delivery channel.
        
        Returns:
            True if sent successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Checks if the channel is healthy and properly configured.
        """
        pass
