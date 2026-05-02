"""
Actor Model
-----------
Represents the entity making the authorization request.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from enum import Enum
from pydantic import BaseModel


class ActorType(str, Enum):
    """Type of actor."""
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"


class Actor(BaseModel):
    """
    Actor represents the entity making the authorization request.
    
    Attributes:
        id: Actor's unique identifier
        type: Type of actor (USER, ADMIN, SYSTEM)
        roles: List of role names (from RBAC)
        permissions: List of permission names (from RBAC)
        team_id: Current team context (if applicable)
        is_superuser: Superuser flag
        attributes: Additional actor attributes
    """
    id: UUID
    type: ActorType
    roles: List[str] = []
    permissions: List[str] = []
    team_id: Optional[UUID] = None
    is_superuser: bool = False
    attributes: Dict[str, Any] = {}
    
    def get_attribute(self, path: str) -> Any:
        """
        Get attribute value by dot-notation path.
        
        Examples:
            actor.get_attribute("id") -> UUID
            actor.get_attribute("type") -> ActorType
            actor.get_attribute("attributes.email") -> str
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
