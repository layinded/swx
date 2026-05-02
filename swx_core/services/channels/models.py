from enum import Enum
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertSource(str, Enum):
    API = "api"
    AUTH = "auth"
    RBAC = "rbac"
    AUDIT = "audit"
    SYSTEM = "system"
    INFRA = "infra"
    POLICY = "policy"

class AlertActorType(str, Enum):
    SYSTEM = "system"
    ADMIN = "admin"
    USER = "user"
    NONE = "none"

class Alert(BaseModel):
    alert_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: AlertSource
    event_type: str
    severity: AlertSeverity
    environment: str
    actor_type: AlertActorType = AlertActorType.NONE
    actor_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
