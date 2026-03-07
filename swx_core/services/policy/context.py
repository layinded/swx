"""
Policy Context Model
--------------------
Represents environmental and request-specific conditions.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class PolicyContext(BaseModel):
    """
    Context represents environmental and request-specific conditions.
    
    Attributes:
        timestamp: Request timestamp
        ip_address: Client IP address
        user_agent: Client user agent
        environment: Environment name (local, staging, production)
        tenant_id: Multi-tenant context
        request_id: Request correlation ID
        metadata: Additional context data
    """
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    environment: str = "local"
    tenant_id: Optional[UUID] = None
    request_id: str = ""
    metadata: Dict[str, Any] = {}
    
    def get_attribute(self, path: str) -> Any:
        """
        Get attribute value by dot-notation path.
        
        Examples:
            context.get_attribute("timestamp") -> datetime
            context.get_attribute("timestamp.hour") -> int
            context.get_attribute("ip_address") -> str
        """
        parts = path.split(".")
        value = self
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None
            
            if value is None:
                return None
            
            # Handle datetime attributes
            if isinstance(value, datetime):
                if part == "hour":
                    return value.hour
                elif part == "minute":
                    return value.minute
                elif part == "weekday":
                    return value.weekday()
                elif part == "day":
                    return value.day
                elif part == "month":
                    return value.month
                elif part == "year":
                    return value.year
        
        return value
