"""
Resource Model
--------------
Represents the resource being accessed.
"""

from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel


class Resource(BaseModel):
    """
    Resource represents the entity being accessed.
    
    Attributes:
        type: Resource type (e.g., "team", "user", "article")
        id: Resource ID (None for collection operations)
        owner_id: Resource owner ID
        team_id: Associated team ID
        attributes: Additional resource attributes
    """
    type: str
    id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    attributes: Dict[str, Any] = {}
    
    def get_attribute(self, path: str) -> Any:
        """
        Get attribute value by dot-notation path.
        
        Examples:
            resource.get_attribute("id") -> UUID
            resource.get_attribute("type") -> str
            resource.get_attribute("attributes.status") -> str
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
        
        return value
