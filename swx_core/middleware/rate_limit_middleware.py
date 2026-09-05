# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Rate Limit Middleware — pure ASGI, SSE-safe.

Enforces per-identity rate limits (burst, sustained, daily) with Redis-backed
or in-process counters.  Returns 429 with retry headers when limits are exceeded.

Replaces the previous BaseHTTPMiddleware implementation which buffered
response bodies and broke Server-Sent Events streaming.
"""

from typing import Optional
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from swx_core.services.rate_limit import (
    get_rate_limiter,
    get_limit,
    resolve_plan,
    get_endpoint_class,
    get_feature_from_path,
    LimitWindow,
    set_rate_limiter,
)
from swx_core.services.rate_limit.rate_limit_override import (
    get_override,
    is_loaded as overrides_loaded,
    load_overrides,
)
from swx_core.middleware.logging_middleware import logger
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome


def _extract_header(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    """Extract a header value by lowercase name match."""
    for k, v in headers:
        if k.lower() == name:
            return v.decode("latin-1")
    return None


def _path_matches(path: str, prefixes: list[str]) -> bool:
    """Check whether *path* starts with any of the given *prefixes*."""
    return any(path.startswith(prefix) for prefix in prefixes)


def _fnmatch_any(path: str, patterns: list[str]) -> bool:
    """Shell-style glob match (imported locally to avoid hard dep)."""
    import fnmatch
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


class RateLimitMiddleware:
    """Pure-ASGI rate-limit middleware — SSE-safe.

    Checks limits based on actor type, billing plan, feature, and endpoint
    class.  For rejected requests a 429 JSONResponse is sent directly
    without reaching the app.  For allowed requests, X-RateLimit-* headers
    are injected via the ``send`` wrapper on ``http.response.start``.
    """

    _DEFAULT_SKIP_PATHS = [
        "/api/utils/health-check",
        "/api/utils/health",
        "/api/utils/language",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/",
    ]

    def __init__(
        self,
        app: ASGIApp,
        skip_paths: Optional[list[str]] = None,
        exempt_namespaces: Optional[list[str]] = None,
    ):
        self.app = app
        if skip_paths is not None:
            self.skip_paths = skip_paths
        else:
            from swx_core.config.settings import settings
            extra = list(getattr(settings, "RATE_LIMIT_SKIP_PATHS", []) or [])
            self.skip_paths = list(self._DEFAULT_SKIP_PATHS) + extra

        self.exempt_namespaces = exempt_namespaces or []

    # ------------------------------------------------------------------
    # Pure-ASGI entry point
    # ------------------------------------------------------------------

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from swx_core.config.settings import settings

        if not settings.RATE_LIMIT_ENABLED:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        method = scope.get("method", "GET")

        if _path_matches(path, self.skip_paths):
            await self.app(scope, receive, send)
            return

        if self.exempt_namespaces and _fnmatch_any(path, self.exempt_namespaces):
            await self.app(scope, receive, send)
            return

        actor_type, actor_id, billing_plan = await self._get_actor_info(scope)

        feature = get_feature_from_path(path)
        endpoint_class = get_endpoint_class(method)
        plan = resolve_plan(actor_type, billing_plan)

        # Lazy-load DB overrides from SystemConfig on first request
        if getattr(settings, "RATE_LIMIT_OVERRIDE_ENABLED", True) and not overrides_loaded():
            try:
                from swx_core.database.db import AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    await load_overrides(session)
            except Exception as e:
                logger.warning(f"Could not load rate limit overrides: {e}")

        def _resolve_limit(ftype: str, eclass: str, ltype: str) -> int:
            override = get_override(plan, ftype, eclass, ltype)
            if override is not None:
                return override
            return get_limit(plan, ftype, eclass, ltype)

        burst_limit = _resolve_limit(feature, endpoint_class, "burst")
        sustained_limit = _resolve_limit(feature, endpoint_class, "sustained")
        daily_limit = _resolve_limit(feature, endpoint_class, "daily")

        limiter = get_rate_limiter()

        # --- Burst check (1 min) ---
        burst_key = f"rate_limit:{actor_type}:{actor_id}:{feature}:{endpoint_class}:1m"
        burst_result = await limiter.check_limit(burst_key, burst_limit, LimitWindow.MINUTE)

        if not burst_result.allowed:
            await self._send_rate_limited(
                scope, receive, send,
                burst_result, actor_type, actor_id, feature, endpoint_class, burst_limit,
            )
            return

        # --- Sustained check (1 hr) ---
        sustained_key = f"rate_limit:{actor_type}:{actor_id}:{feature}:{endpoint_class}:1h"
        sustained_result = await limiter.check_limit(sustained_key, sustained_limit, LimitWindow.HOUR)

        if not sustained_result.allowed:
            await self._send_rate_limited(
                scope, receive, send,
                sustained_result, actor_type, actor_id, feature, endpoint_class, burst_limit,
            )
            return

        # --- Daily check (24 hr) ---
        daily_key = f"rate_limit:{actor_type}:{actor_id}:{feature}:{endpoint_class}:24h"
        daily_result = await limiter.check_limit(daily_key, daily_limit, LimitWindow.DAY)

        if not daily_result.allowed:
            await self._send_rate_limited(
                scope, receive, send,
                daily_result, actor_type, actor_id, feature, endpoint_class, burst_limit,
            )
            return

        # --- All limits passed — forward to app with rate-limit headers ---
        rate_headers: list[tuple[bytes, bytes]] = [
            (b"X-RateLimit-Limit", str(burst_limit).encode()),
            (b"X-RateLimit-Remaining", str(burst_result.remaining).encode()),
            (b"X-RateLimit-Reset", str(int(burst_result.reset_at.timestamp())).encode()),
        ]

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(rate_headers)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)

    # ------------------------------------------------------------------
    # Actor resolution (scope-based, no Request object)
    # ------------------------------------------------------------------

    def _actor_from_bearer(self, headers: list[tuple[bytes, bytes]]) -> Optional[tuple[str, str, Optional[str]]]:
        """Resolve actor from Authorization Bearer JWT using scope headers."""
        auth = _extract_header(headers, b"authorization")
        if not auth or not auth.lower().startswith("bearer "):
            return None
        token = auth[7:].strip()
        if not token:
            return None
        try:
            import jwt
            from swx_core.auth.core.jwt import TokenAudience
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
                billing_plan = payload.get("billing_plan", settings.DEFAULT_PLAN_KEY)
                return ("user", sub, billing_plan)
            return None
        except Exception:
            return None

    async def _get_actor_info(self, scope: Scope) -> tuple[str, str, Optional[str]]:
        """Extract actor information from scope state and headers."""
        state = scope.get("state")
        if state is not None:
            current_user = getattr(state, "current_user", None) if not isinstance(state, dict) else state.get("current_user")
            if current_user:
                billing_plan = await self._get_user_billing_plan(scope)
                return ("user", str(current_user.id), billing_plan)

            current_admin = getattr(state, "current_admin", None) if not isinstance(state, dict) else state.get("current_admin")
            if current_admin:
                return ("admin", str(current_admin.id), None)

        headers = scope.get("headers", [])
        from_bearer = self._actor_from_bearer(headers)
        if from_bearer is not None:
            return from_bearer

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        return ("anonymous", client_ip, None)

    async def _get_user_billing_plan(self, scope: Scope) -> Optional[str]:
        """Get user billing plan from JWT claim in scope headers."""
        headers = scope.get("headers", [])
        auth = _extract_header(headers, b"authorization")
        if not auth or not auth.lower().startswith("bearer "):
            return None
        token = auth[7:].strip()
        if not token:
            return None
        try:
            import jwt
            from swx_core.config.settings import settings
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.PASSWORD_SECURITY_ALGORITHM],
                options={"verify_aud": False},
            )
            return payload.get("billing_plan", settings.DEFAULT_PLAN_KEY)
        except Exception as e:
            logger.warning(f"Error decoding billing plan: {e}")
            return None

    # ------------------------------------------------------------------
    # 429 response (direct ASGI, no buffering)
    # ------------------------------------------------------------------

    async def _send_rate_limited(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        result,
        actor_type: str,
        actor_id: str,
        feature: str,
        endpoint_class: str,
        burst_limit: int,
    ) -> None:
        """Send a 429 Too Many Requests response directly via ASGI."""
        # Audit log (best-effort, don't block on failure)
        try:
            from swx_core.database.db import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                audit = get_audit_logger(session)
                await audit.log_event(
                    action="rate_limit.exceeded",
                    actor_type=ActorType.SYSTEM if actor_type == "system" else (ActorType.ADMIN if actor_type == "admin" else ActorType.USER),
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
                )
        except Exception as e:
            logger.error(f"Error logging rate limit event: {e}")

        logger.warning(
            f"Rate limit exceeded: actor={actor_type}:{actor_id}, "
            f"feature={feature}, endpoint={endpoint_class}, limit={result.limit}"
        )

        body = {
            "error": "rate_limit_exceeded",
            "message": f"Rate limit exceeded for {feature}:{endpoint_class}",
            "limit": result.limit,
            "remaining": result.remaining,
            "reset_at": result.reset_at.isoformat(),
            "retry_after": result.retry_after,
        }

        response = JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content=body)
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(result.reset_at.timestamp()))
        if result.retry_after:
            response.headers["Retry-After"] = str(result.retry_after)

        await response(scope, receive, send)


def apply_middleware(app: FastAPI) -> None:
    """Apply rate limit middleware to FastAPI app (called by dynamic loader)."""
    redis_client = None
    try:
        import redis.asyncio as aioredis
        from swx_core.config.settings import settings

        if settings.REDIS_ENABLED:
            redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
            logger.info(
                "Redis client configured for rate limiting (connection not verified at startup)"
            )
        else:
            logger.info("Redis disabled in settings")
    except ImportError:
        logger.warning(
            "Redis library not installed. Install with: pip install redis[hiredis]"
        )
    except Exception as e:
        logger.warning(
            f"Redis not available for rate limiting: {e}. Rate limiting will fail-closed."
        )

    from swx_core.services.rate_limit import RateLimiter, AbuseDetector

    limiter = RateLimiter(redis_client)
    set_rate_limiter(limiter)

    detector = AbuseDetector(redis_client)
    from swx_core.services.rate_limit import set_abuse_detector
    set_abuse_detector(detector)

    app.add_middleware(RateLimitMiddleware)
    logger.info("Rate limit middleware applied")