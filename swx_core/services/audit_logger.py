"""
Audit Logging Service
----------------------
This module provides a centralized audit logging service for SwX-API.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Any, Dict, Union
from enum import Enum

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.audit_log import AuditLog
from swx_core.config.settings import COMPLIANCE_AUTO_MASK_IP, COMPLIANCE_AUTO_REDACT_FIELDS
from swx_core.middleware.logging_middleware import logger
from swx_core.services.compliance.field_redaction_service import redact_fields
from swx_core.services.compliance.ip_masking_service import mask_ip


class ActorType(str, Enum):
    SYSTEM = "system"
    ADMIN = "admin"
    USER = "user"


class AuditOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED_INSUFFICIENT_ROLE = "denied_insufficient_role"
    DENIED_CONSENT_REQUIRED = "denied_consent_required"
    DENIED_DATA_CLASSIFICATION = "denied_data_classification"
    DENIED_POLICY = "denied_policy"


class AuditLogger:
    """
    Centralized service for recording audit logs.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_event(
        self,
        action: str,
        actor_type: Union[ActorType, str],
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        outcome: Union[AuditOutcome, str] = AuditOutcome.SUCCESS,
        context: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        severity: str = "info",
        data_classification: Optional[str] = None,
        access_result: Optional[str] = None,
    ) -> None:
        """
        Records an audit log entry asynchronously.

        Args:
            action: The specific action performed (e.g., 'auth.login').
            actor_type: Type of actor performing the action.
            actor_id: Unique identifier of the actor.
            resource_type: Type of resource affected.
            resource_id: Unique identifier of the affected resource.
            outcome: Result of the action (success or failure).
            context: Additional structured metadata (secrets will be filtered).
            request: Optional FastAPI request to extract IP, User-Agent, and Request-ID.
        """
        try:
            ip_address = None
            user_agent = None
            request_id = None

            if request:
                client = request.client
                ip_address = client.host if client else None
                user_agent = request.headers.get("user-agent")
                request_id = getattr(request.state, "request_id", None)

            # Filter sensitive data from context
            safe_context = self._filter_sensitive_data(context or {})
            if COMPLIANCE_AUTO_REDACT_FIELDS:
                safe_context = await redact_fields(self.session, safe_context, data_classification)
            masked_ip = await mask_ip(self.session, ip_address) if COMPLIANCE_AUTO_MASK_IP else None

            audit_entry = AuditLog(
                actor_type=actor_type.value if isinstance(actor_type, ActorType) else actor_type,
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=outcome.value if isinstance(outcome, AuditOutcome) else outcome,
                severity=severity,
                data_classification=data_classification,
                access_result=access_result,
                ip_address=ip_address,
                masked_ip=masked_ip,
                user_agent=user_agent,
                request_id=request_id,
                context=safe_context,
            )

            self.session.add(audit_entry)
            await self.session.commit()
            logger.debug(f"Audit log recorded: {action} by {actor_type}:{actor_id}")

        except Exception as e:
            # Audit logging should not crash the main request flow, but it must be logged.
            logger.error(f"Failed to record audit log: {e}", exc_info=True)
            await self.session.rollback()

    def _filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively filters sensitive keys from metadata.
        """
        sensitive_keys = {
            "password", "hashed_password", "token", "access_token", "refresh_token",
            "secret", "secret_key", "client_secret", "authorization", "cookie"
        }

        return {
            key: "[REDACTED]"
            if key.lower() in sensitive_keys
            else self._filter_sensitive_data(value)
            if isinstance(value, dict)
            else value
            for key, value in data.items()
        }


def get_audit_logger(session: AsyncSession) -> AuditLogger:
    """
    Dependency helper to get an AuditLogger instance.
    """
    return AuditLogger(session)
