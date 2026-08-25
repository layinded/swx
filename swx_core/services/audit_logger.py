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
from swx_core.services.compliance.audit_integrity_service import persist_log_hash


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


class AuditAction(str, Enum):
    """Canonical audit event action categories for SOC 2 CC7.2 compliance."""

    # Auth events
    AUTH_LOGIN_SUCCESS = "auth.login_success"
    AUTH_LOGIN_FAILURE = "auth.login_failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_REFRESH = "auth.token_refresh"
    AUTH_MFA_ENABLED = "auth.mfa_enabled"
    AUTH_MFA_DISABLED = "auth.mfa_disabled"
    AUTH_MFA_CHALLENGE_SUCCESS = "auth.mfa_challenge_success"
    AUTH_MFA_CHALLENGE_FAILURE = "auth.mfa_challenge_failure"
    AUTH_PASSWORD_RESET_REQUESTED = "auth.password_reset_requested"
    AUTH_PASSWORD_RESET_COMPLETED = "auth.password_reset_completed"
    AUTH_SOCIAL_LOGIN_SUCCESS = "auth.social_login_success"
    AUTH_SOCIAL_LOGIN_FAILURE = "auth.social_login_failure"
    AUTH_ACCOUNT_LOCKED = "auth.account_locked"
    AUTH_ACCOUNT_UNLOCKED = "auth.account_unlocked"
    AUTH_PASSWORD_RESET_RATE_LIMITED = "auth.password_reset_rate_limited"

    # RBAC events
    RBAC_ROLE_ASSIGNED = "rbac.role_assigned"
    RBAC_ROLE_REMOVED = "rbac.role_removed"
    RBAC_PERMISSION_DENIED = "rbac.permission_denied"

    # Organization events
    ORG_CREATED = "org.created"
    ORG_UPDATED = "org.updated"
    ORG_DELETED = "org.deleted"
    ORG_MEMBER_ADDED = "org.member_added"
    ORG_MEMBER_REMOVED = "org.member_removed"
    ORG_OWNERSHIP_TRANSFERRED = "org.ownership_transferred"

    # Team events
    TEAM_CREATED = "team.created"
    TEAM_UPDATED = "team.updated"
    TEAM_DELETED = "team.deleted"
    TEAM_MEMBER_ADDED = "team.member_added"
    TEAM_MEMBER_REMOVED = "team.member_removed"
    TEAM_OWNERSHIP_TRANSFERRED = "team.ownership_transferred"

    # GDPR events
    GDPR_EXPORT_REQUESTED = "gdpr.export_requested"
    GDPR_ERASURE_REQUESTED = "gdpr.erasure_requested"
    GDPR_ERASURE_COMPLETED = "gdpr.erasure_completed"
    GDPR_ERASURE_CANCELLED = "gdpr.erasure_cancelled"

    # Admin events
    ADMIN_USER_CREATED = "admin.user_created"
    ADMIN_USER_DEACTIVATED = "admin.user_deactivated"
    ADMIN_USER_REACTIVATED = "admin.user_reactivated"
    ADMIN_ROLE_CHANGED = "admin.role_changed"

    # API key events
    API_KEY_CREATED = "api_key.created"
    API_KEY_ROTATED = "api_key.rotated"
    API_KEY_REVOKED = "api_key.revoked"
    API_KEY_EXPIRED = "api_key.expired"
    API_KEY_INACTIVE_REVOKED = "api_key.inactive_revoked"

    # Data export events
    DATA_EXPORT_REQUESTED = "data_export.requested"
    DATA_EXPORT_COMPLETED = "data_export.completed"

    # PII encryption events
    PII_ENCRYPTION_ENABLED = "pii.encryption_enabled"
    PII_ENCRYPTION_KEY_ROTATED = "pii.encryption_key_rotated"

    # Session management events (SOC 2 CC6.1)
    AUTH_SESSION_REVOKED = "auth.session_revoked"
    AUTH_SESSION_LIMIT_ENFORCED = "auth.session_limit_enforced"
    AUTH_SESSION_EXPIRED_IDLE = "auth.session_expired_idle"

    # Security events
    SECURITY_CSP_VIOLATION = "security.csp_violation"


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
            try:
                await persist_log_hash(self.session, audit_entry)
            except Exception as hash_err:
                logger.critical("Failed to persist hash chain for audit entry %s: %s. Removing entry to preserve chain integrity.", audit_entry.id, hash_err)
                try:
                    await self.session.delete(audit_entry)
                    await self.session.commit()
                except Exception:
                    logger.critical("Failed to remove unhashed audit entry %s — chain integrity at risk.", audit_entry.id)
            logger.debug(f"Audit log recorded: {action} by {actor_type}:{actor_id}")

            from swx_core.services.compliance.siem_service import enqueue_siem_event
            await enqueue_siem_event(action, safe_context)

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
