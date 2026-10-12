"""
Abuse Detector
--------------
Detects abuse patterns and triggers alerts.

Abuse Signals:
- Credential stuffing (multiple failed auth attempts)
- Endpoint scanning (sequential 404s)
- Token abuse (same token from multiple IPs)
- Burst abuse (repeated rate limit violations)
"""

import time
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.middleware.logging_middleware import logger
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource


class AbuseDetector:
    """
    Detects abuse patterns and triggers alerts.
    
    Uses Redis to track abuse signals across time windows.
    """
    
    def __init__(self, redis_client=None):
        """
        Initialize abuse detector.
        
        Args:
            redis_client: Redis client for tracking abuse signals
        """
        self.redis = redis_client
        self._thresholds = {
            "credential_stuffing": {
                "failures": 5,  # Failed auth attempts
                "window": 60,   # Per minute
            },
            "endpoint_scanning": {
                "404s": 10,     # 404 responses
                "window": 60,   # Per minute
            },
            "token_abuse": {
                "requests": 100,  # Requests from same token
                "window": 60,     # Per minute
            },
            "burst_abuse": {
                "violations": 3,  # Rate limit violations
                "window": 300,    # Per 5 minutes
            },
        }
    
    async def check_credential_stuffing(
        self,
        ip_address: str,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Check for credential stuffing (multiple failed auth attempts from same IP).
        
        Args:
            ip_address: Client IP address
            session: Database session for audit logging
        
        Returns:
            True if abuse detected, False otherwise
        """
        if not self.redis:
            return False
        
        try:
            threshold = self._thresholds["credential_stuffing"]
            key = f"abuse:credential_stuffing:{ip_address}"
            
            # Increment failure count
            count = await self.redis.incr(key)
            await self.redis.expire(key, threshold["window"])
            
            if count == 1:
                # First failure - set expiration
                await self.redis.expire(key, threshold["window"])
            
            if count >= threshold["failures"]:
                # Abuse detected
                await self._trigger_abuse_alert(
                    "credential_stuffing",
                    ip_address=ip_address,
                    count=count,
                    session=session
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking credential stuffing: {e}", exc_info=True)
            return False
    
    async def check_endpoint_scanning(
        self,
        ip_address: str,
        path: str,
        status_code: int,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Check for endpoint scanning (sequential 404s from same IP).
        
        Args:
            ip_address: Client IP address
            path: Request path
            status_code: HTTP status code
            session: Database session for audit logging
        
        Returns:
            True if abuse detected, False otherwise
        """
        if not self.redis or status_code != 404:
            return False
        
        try:
            threshold = self._thresholds["endpoint_scanning"]
            key = f"abuse:endpoint_scanning:{ip_address}"
            
            # Increment 404 count
            count = await self.redis.incr(key)
            
            if count == 1:
                await self.redis.expire(key, threshold["window"])
            
            if count >= threshold["404s"]:
                # Abuse detected
                await self._trigger_abuse_alert(
                    "endpoint_scanning",
                    ip_address=ip_address,
                    path=path,
                    count=count,
                    session=session
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking endpoint scanning: {e}", exc_info=True)
            return False
    
    async def check_token_abuse(
        self,
        token_id: str,
        ip_address: str,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Check for token abuse (same token used from multiple IPs or at unusual rate).
        
        Args:
            token_id: Token identifier
            ip_address: Current IP address
            session: Database session for audit logging
        
        Returns:
            True if abuse detected, False otherwise
        """
        if not self.redis:
            return False
        
        try:
            threshold = self._thresholds["token_abuse"]
            
            # Track requests per token
            request_key = f"abuse:token_requests:{token_id}"
            request_count = await self.redis.incr(request_key)
            if request_count == 1:
                await self.redis.expire(request_key, threshold["window"])
            
            # Track IPs per token
            ip_key = f"abuse:token_ips:{token_id}"
            await self.redis.sadd(ip_key, ip_address)
            await self.redis.expire(ip_key, threshold["window"] * 2)
            ip_count = await self.redis.scard(ip_key)
            
            # Check for abuse
            if request_count >= threshold["requests"] or ip_count > 3:
                await self._trigger_abuse_alert(
                    "token_abuse",
                    token_id=token_id,
                    ip_address=ip_address,
                    request_count=request_count,
                    ip_count=ip_count,
                    session=session
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking token abuse: {e}", exc_info=True)
            return False
    
    async def check_burst_abuse(
        self,
        actor_type: str,
        actor_id: str,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Check for burst abuse (repeated rate limit violations).
        
        Args:
            actor_type: Actor type (user/admin/anonymous)
            actor_id: Actor identifier
            session: Database session for audit logging
        
        Returns:
            True if abuse detected, False otherwise
        """
        if not self.redis:
            return False
        
        try:
            threshold = self._thresholds["burst_abuse"]
            key = f"abuse:burst:{actor_type}:{actor_id}"
            
            # Increment violation count
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, threshold["window"])
            
            if count >= threshold["violations"]:
                await self._trigger_abuse_alert(
                    "burst_abuse",
                    actor_type=actor_type,
                    actor_id=actor_id,
                    count=count,
                    session=session
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking burst abuse: {e}", exc_info=True)
            return False
    
    async def _trigger_abuse_alert(
        self,
        abuse_type: str,
        session: Optional[AsyncSession] = None,
        **context: Any
    ) -> None:
        """
        Trigger alert for detected abuse.
        
        Args:
            abuse_type: Type of abuse detected
            session: Database session for audit logging
            **context: Additional context about the abuse
        """
        # Audit log
        if session:
            try:
                audit = get_audit_logger(session)
                await audit.log_event(
                    action="abuse.detected",
                    actor_type=ActorType.SYSTEM,
                    actor_id="system",
                    resource_type="abuse",
                    resource_id=abuse_type,
                    outcome=AuditOutcome.FAILURE,
                    context={"abuse_type": abuse_type, **context}
                )
            except Exception as e:
                logger.error(f"Error logging abuse event: {e}")
        
        # Send alert
        try:
            await alert_engine.send_alert(
                severity=AlertSeverity.HIGH,
                source=AlertSource.SECURITY,
                title=f"Abuse Detected: {abuse_type}",
                message=f"Abuse pattern detected: {abuse_type}",
                context={"abuse_type": abuse_type, **context}
            )
            logger.warning(f"Abuse alert sent: {abuse_type} - {context}")
        except Exception as e:
            logger.error(f"Error sending abuse alert: {e}", exc_info=True)


# Global abuse detector instance
_abuse_detector: Optional[AbuseDetector] = None


def get_abuse_detector() -> AbuseDetector:
    """Get or create the global abuse detector instance."""
    global _abuse_detector
    if _abuse_detector is None:
        _abuse_detector = AbuseDetector()
    return _abuse_detector


def set_abuse_detector(detector: AbuseDetector) -> None:
    """Set the global abuse detector instance."""
    global _abuse_detector
    _abuse_detector = detector
