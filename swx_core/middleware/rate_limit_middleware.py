"""
Rate Limit Middleware
--------------------
FastAPI middleware for rate limiting requests.

Applies rate limits:
- After authentication
- Before business logic
- Before policy evaluation

Features:
- Identity-aware limits
- Billing-aware limits
- Clear error responses
- Retry headers
"""

from typing import Optional
from fastapi import Request, HTTPException, status, FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from swx_core.services.rate_limit import (
    get_rate_limiter,
    get_limit,
    resolve_plan,
    get_endpoint_class,
    get_feature_from_path,
    LimitWindow,
    set_rate_limiter,
)
from swx_core.middleware.logging_middleware import logger
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limits on all requests.
    
    Checks limits based on:
    - Actor type (system/admin/user/anonymous)
    - Billing plan (free/pro/team/enterprise)
    - Feature (api_requests/billing/search/export)
    - Endpoint class (read/write/delete)
    """
    
    def __init__(self, app: ASGIApp, skip_paths: Optional[list] = None):
        """
        Initialize rate limit middleware.
        
        Args:
            app: ASGI application
            skip_paths: Paths to skip rate limiting (e.g., health checks)
        """
        super().__init__(app)
        self.skip_paths = skip_paths or [
            "/api/utils/health-check", 
            "/api/utils/health",  # Health check should not be rate limited
            "/api/utils/language",  # Language endpoints should not be rate limited
            "/docs", 
            "/openapi.json", 
            "/redoc",
            "/api/admin/auth",  # Admin authentication should not be rate limited
            "/api/auth",  # User authentication should not be rate limited
            "/api/admin/",  # All admin endpoints should not be rate limited (admin users have high limits anyway)
            "/api/user/profile",  # User profile endpoints should not be rate limited (authenticated users)
            "/api/qa_article",  # QA article endpoints should not be rate limited for testing
            "/api/oauth",  # OAuth endpoints should not be rate limited
            "/",  # Root endpoint should not be rate limited
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for certain paths
        if any(request.url.path.startswith(path) for path in self.skip_paths):
            return await call_next(request)
        
        # Get actor information
        actor_type, actor_id, billing_plan = await self._get_actor_info(request)
        
        # Get feature and endpoint class
        feature = get_feature_from_path(request.url.path)
        endpoint_class = get_endpoint_class(request.method)
        
        # Resolve plan
        plan = resolve_plan(actor_type, billing_plan)
        
        # Get limits (check burst first, then sustained)
        burst_limit = get_limit(plan, feature, endpoint_class, "burst")
        sustained_limit = get_limit(plan, feature, endpoint_class, "sustained")
        
        # Build rate limit keys
        limiter = get_rate_limiter()
        
        # Check burst limit (1 minute window)
        burst_key = f"rate_limit:{actor_type}:{actor_id}:{feature}:{endpoint_class}:1m"
        burst_result = await limiter.check_limit(burst_key, burst_limit, LimitWindow.MINUTE)
        
        if not burst_result.allowed:
            # Check for burst abuse
            from swx_core.services.rate_limit import get_abuse_detector
            abuse_detector = get_abuse_detector()
            await abuse_detector.check_burst_abuse(actor_type, actor_id)
            
            return await self._rate_limit_exceeded_response(
                request, burst_result, actor_type, actor_id, feature, endpoint_class
            )
        
        # Check sustained limit (1 hour window)
        sustained_key = f"rate_limit:{actor_type}:{actor_id}:{feature}:{endpoint_class}:1h"
        sustained_result = await limiter.check_limit(sustained_key, sustained_limit, LimitWindow.HOUR)
        
        if not sustained_result.allowed:
            return await self._rate_limit_exceeded_response(
                request, sustained_result, actor_type, actor_id, feature, endpoint_class
            )
        
        # Check daily limit (24 hour window)
        daily_limit = get_limit(plan, feature, endpoint_class, "daily")
        daily_key = f"rate_limit:{actor_type}:{actor_id}:{feature}:{endpoint_class}:24h"
        daily_result = await limiter.check_limit(daily_key, daily_limit, LimitWindow.DAY)
        
        if not daily_result.allowed:
            return await self._rate_limit_exceeded_response(
                request, daily_result, actor_type, actor_id, feature, endpoint_class
            )
        
        # All limits passed - proceed
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(burst_limit)
        response.headers["X-RateLimit-Remaining"] = str(burst_result.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(burst_result.reset_at.timestamp()))
        
        return response
    
    def _actor_from_bearer(self, request: Request) -> Optional[tuple[str, str, Optional[str]]]:
        """
        Resolve actor from Authorization Bearer JWT (no DB).
        Used when route deps have not yet set request.state (middleware runs first).
        """
        auth = request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            return None
        token = auth[7:].strip()
        if not token:
            return None
        try:
            import jwt
            from swx_core.auth.core.jwt import decode_token, TokenAudience
            from swx_core.config.settings import settings
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.PASSWORD_SECURITY_ALGORITHM],
                options={"verify_aud": False},
            )
            aud = payload.get("aud")
            sub = str(payload.get("sub", ""))
            if not sub:
                return None
            if aud == TokenAudience.ADMIN.value:
                return ("admin", sub, None)
            if aud == TokenAudience.USER.value:
                return ("user", sub, "free")
            return None
        except Exception:
            return None

    async def _get_actor_info(self, request: Request) -> tuple[str, str, Optional[str]]:
        """
        Extract actor information from request.
        
        Returns:
            Tuple of (actor_type, actor_id, billing_plan)
        """
        # Try to get current user (request.state is a namespace, not a dict)
        current_user = getattr(request.state, "current_user", None)
        if current_user:
            # Get billing plan from user's subscription
            billing_plan = await self._get_user_billing_plan(request, current_user.id)
            return ("user", str(current_user.id), billing_plan)
        
        # Try to get current admin
        current_admin = getattr(request.state, "current_admin", None)
        if current_admin:
            return ("admin", str(current_admin.id), None)
        
        # Middleware runs before route deps; resolve from Bearer JWT if present
        from_bearer = self._actor_from_bearer(request)
        if from_bearer:
            return from_bearer
        
        # Anonymous request - use IP address as identifier
        client_ip = request.client.host if request.client else "unknown"
        return ("anonymous", client_ip, None)
    
    async def _get_user_billing_plan(self, request: Request, user_id: str) -> Optional[str]:
        """Get user's billing plan from subscription."""
        try:
            # Import here to avoid circular dependencies
            from swx_core.services.billing.entitlement_resolver import EntitlementResolver
            from swx_core.database.db import AsyncSessionLocal
            
            async with AsyncSessionLocal() as session:
                resolver = EntitlementResolver(session)
                # Get user's active plan
                # This is a simplified version - in production, fetch from subscription
                # For now, default to "free"
                return "free"
        except Exception as e:
            logger.warning(f"Error getting billing plan for user {user_id}: {e}")
            return None
    
    async def _rate_limit_exceeded_response(
        self,
        request: Request,
        result,
        actor_type: str,
        actor_id: str,
        feature: str,
        endpoint_class: str
    ) -> JSONResponse:
        """Create rate limit exceeded response."""
        # Audit log
        try:
            from swx_core.database.db import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                audit = get_audit_logger(session)
                await audit.log_event(
                    action="rate_limit.exceeded",
                    actor_type=ActorType.SYSTEM if actor_type == "system" else (
                        ActorType.ADMIN if actor_type == "admin" else ActorType.USER
                    ),
                    actor_id=actor_id,
                    resource_type="rate_limit",
                    resource_id=f"{feature}:{endpoint_class}",
                    outcome=AuditOutcome.FAILURE,
                    context={
                        "limit": result.limit,
                        "feature": feature,
                        "endpoint_class": endpoint_class,
                        "retry_after": result.retry_after,
                    },
                    request=request
                )
        except Exception as e:
            logger.error(f"Error logging rate limit event: {e}")
        
        # Create error response
        error_response = {
            "error": "rate_limit_exceeded",
            "message": f"Rate limit exceeded for {feature}:{endpoint_class}",
            "limit": result.limit,
            "remaining": result.remaining,
            "reset_at": result.reset_at.isoformat(),
            "retry_after": result.retry_after,
        }
        
        response = JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=error_response
        )
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(result.reset_at.timestamp()))
        if result.retry_after:
            response.headers["Retry-After"] = str(result.retry_after)
        
        logger.warning(
            f"Rate limit exceeded: actor={actor_type}:{actor_id}, "
            f"feature={feature}, endpoint={endpoint_class}, limit={result.limit}"
        )
        
        return response


def apply_middleware(app: FastAPI) -> None:
    """
    Apply rate limit middleware to FastAPI app.
    
    This function is called by the dynamic middleware loader.
    """
    # Initialize Redis connection if available
    redis_client = None
    try:
        import redis.asyncio as aioredis
        from swx_core.config.settings import settings
        
        if settings.REDIS_ENABLED:
            redis_host = "redis" if settings.DOCKERIZED else settings.REDIS_HOST
            redis_url = f"redis://{redis_host}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
            if settings.REDIS_PASSWORD:
                redis_url = f"redis://:{settings.REDIS_PASSWORD}@{redis_host}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
            
            redis_client = aioredis.from_url(
                redis_url,
                decode_responses=False
            )
            # Skip startup ping: we may already be inside an event loop (uvicorn).
            # Connection is verified on first use; failures are handled fail-closed.
            logger.info("Redis client configured for rate limiting (connection not verified at startup)")
        else:
            logger.info("Redis disabled in settings")
    except ImportError:
        logger.warning("Redis library not installed. Install with: pip install redis[hiredis]")
    except Exception as e:
        logger.warning(f"Redis not available for rate limiting: {e}. Rate limiting will fail-closed.")
    
    # Initialize rate limiter
    from swx_core.services.rate_limit import RateLimiter, AbuseDetector
    limiter = RateLimiter(redis_client)
    set_rate_limiter(limiter)
    
    # Initialize abuse detector
    detector = AbuseDetector(redis_client)
    from swx_core.services.rate_limit import set_abuse_detector
    set_abuse_detector(detector)
    
    app.add_middleware(RateLimitMiddleware)
    logger.info("Rate limit middleware applied")
