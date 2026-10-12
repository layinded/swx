"""
Webhook Contract.

Defines the interface for webhook handlers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class WebhookResult:
    """Result of webhook processing."""
    received: bool
    processed: bool = False
    event_id: str = None
    event_type: str = None
    job_id: str = None
    message: str = None


class WebhookHandlerInterface(ABC):
    """
    Abstract interface for webhook handlers.
    
    Implement this interface to handle webhooks from different providers.
    """
    
    @property
    @abstractmethod
    def provider(self) -> str:
        """
        Webhook provider name (e.g., "stripe", "paypal").
        
        Returns:
            str: Provider name
        """
        pass
    
    @property
    def path(self) -> str:
        """
        URL path for webhook endpoint.
        
        Returns:
            str: Path (e.g., "/webhooks/stripe")
        """
        return f"/webhooks/{self.provider}"
    
    @abstractmethod
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify webhook signature.
        
        Args:
            payload: Raw request body
            signature: Signature header
            
        Returns:
            bool: True if valid
        """
        pass
    
    @abstractmethod
    def parse_event(self, payload: bytes) -> Dict[str, Any]:
        """
        Parse webhook event from payload.
        
        Args:
            payload: Raw request body
            
        Returns:
            Dict: Event data
        """
        pass
    
    @abstractmethod
    async def handle(self, payload: bytes, signature: str) -> WebhookResult:
        """
        Handle webhook request.
        
        Args:
            payload: Raw request body
            signature: Signature header
            
        Returns:
            WebhookResult: Processing result
        """
        pass
    
    @abstractmethod
    async def is_duplicate(self, event_id: str) -> bool:
        """
        Check if event has already been processed.
        
        Args:
            event_id: Event identifier
            
        Returns:
            bool: True if duplicate
        """
        pass
    
    @abstractmethod
    async def is_replay(self, event_timestamp: int) -> bool:
        """
        Check if event is a replay of old event.
        
        Args:
            event_timestamp: Event timestamp
            
        Returns:
            bool: True if replay
        """
        pass
    
    @abstractmethod
    async def enqueue_processing(self, event: Dict[str, Any]) -> str:
        """
        Enqueue event for async processing.
        
        Args:
            event: Event data
            
        Returns:
            str: Job ID
        """
        pass