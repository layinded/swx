"""Per-route rate limit enforcement API.

Allows route handlers to enforce rate limits with custom namespaces
that cannot be inferred from the URL path alone (e.g., business
context like ``detection:detect:public`` vs ``detection:detect:team``).

Usage::

    from swx_core.services.rate_limit.enforce import enforce_limit

    @router.post("/detect/public")
    async def detect_public(request: Request):
        await enforce_limit(request, namespace="detection:detect:public")
        ...

    @router.post("/detect/team")
    async def detect_team(request: Request, user=Depends(get_current_user)):
        await enforce_limit(request, namespace="detection:detect:team")
        ...
"""

from typing import Optional
from fastapi import HTTPException, Request, status

from swx_core.services.rate_limit.rate_limiter import get_rate_limiter, LimitWindow
from swx_core.services.rate_limit.limit_registry import get_limit, resolve_plan
from swx_core.middleware.logging_middleware import logger


_PERIOD_SECONDS: dict[str, int] = {
    "second": 1, "seconds": 1,
    "minute": 60, "minutes": 60,
    "hour": 3600, "hours": 3600,
    "day": 86400, "days": 86400,
}


def parse_rate_limit(limit: str) -> tuple[int, int]:
    """Parse a human-readable rate limit string into (max_requests, window_seconds).

    Examples:
        "5/minute"   -> (5, 60)
        "100/hour"   -> (100, 3600)
        "10/second"  -> (10, 1)
    """
    value, period = limit.strip().split("/")
    max_requests = int(value)
    period_key = period.lower()
    if period_key not in _PERIOD_SECONDS:
        raise ValueError(f"Unsupported rate period: {period}")
    return max_requests, _PERIOD_SECONDS[period_key]


def get_client_ip(request: Request) -> str:
    """Extract the real client IP from X-Forwarded-For / X-Real-IP headers.

    When behind trusted proxies, walks the X-Forwarded-For chain backwards
    to find the first IP not in the TRUSTED_PROXIES set.
    """
    from swx_core.config.settings import settings

    trusted_proxies = set(
        ip.strip() for ip in settings.TRUSTED_PROXIES.split(",") if ip.strip()
    )

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for and trusted_proxies:
        parts = [p.strip() for p in forwarded_for.split(",")]
        for i, part in enumerate(reversed(parts)):
            client_ip = part.split(":")[0] if ":" in part else part
            peer = parts[-(i + 2)] if i + 2 <= len(parts) else (
                request.client.host if request.client else None
            )
            if peer not in trusted_proxies:
                return client_ip

    if forwarded_for:
        return forwarded_for.split(",")[0].strip().split(":")[0]

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip().split(":")[0]

    return request.client.host if request.client else "unknown"


async def enforce_rate_limit(
    request: Request,
    limit: str,
    namespace: str,
) -> None:
    """Enforce a rate limit using a human-readable limit string.

    Args:
        request: FastAPI request object.
        limit: Rate limit string like "5/minute" or "100/hour".
        namespace: Application-specific rate limit namespace.

    Raises:
        HTTPException: 429 if rate limit exceeded.
    """
    max_requests, window_seconds = parse_rate_limit(limit)

    if not max_requests or not window_seconds:
        return

    actor_type, actor_id, _ = _resolve_actor(request)

    window = LimitWindow.MINUTE if window_seconds <= 60 else (
        LimitWindow.HOUR if window_seconds <= 3600 else LimitWindow.DAY
    )

    limiter = get_rate_limiter()
    redis_key = f"rate_limit:{actor_type}:{actor_id}:{namespace}:{window.value}"
    result = await limiter.check_limit(redis_key, max_requests, window)

    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {namespace}",
            headers={
                "Retry-After": str(result.retry_after or window_seconds),
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(result.reset_at.timestamp())),
            },
        )


async def enforce_limit(
    request: Request,
    namespace: str,
    feature: str = "api_requests",
    endpoint_class: str = "read",
    limit_type: str = "burst",
    window: LimitWindow = LimitWindow.MINUTE,
    actor_id: Optional[str] = None,
    actor_type: Optional[str] = None,
    billing_plan: Optional[str] = None,
    custom_limit: Optional[int] = None,
) -> int:
    """Enforce a per-route rate limit.

    Resolves the actor from the request (JWT claim or request.state),
    looks up the limit for the given plan/feature/endpoint, checks Redis,
    and raises ``HTTPException(429)`` if the limit is exceeded.

    Args:
        request: FastAPI request object.
        namespace: Application-specific rate limit namespace
            (e.g., ``"detection:detect:public"``). Used as part of the
            Redis key to isolate counters per route.
        feature: Feature bucket for limit lookup (default ``"api_requests"``).
        endpoint_class: Endpoint class for limit lookup (default ``"read"``).
        limit_type: Which limit to check (``"burst"``, ``"sustained"``, ``"daily"``).
        window: Time window for the counter.
        actor_id: Override actor ID (defaults to JWT sub or IP).
        actor_type: Override actor type (defaults to JWT-derived type).
        billing_plan: Override billing plan (defaults to JWT claim).
        custom_limit: Override the limit value entirely (bypasses registry lookup).

    Returns:
        Remaining requests in the window (int).

    Raises:
        HTTPException: 429 if rate limit exceeded.
    """
    if actor_type is None or actor_id is None or billing_plan is None:
        resolved_type, resolved_id, resolved_plan = _resolve_actor(request)
        actor_type = actor_type or resolved_type
        actor_id = actor_id or resolved_id
        billing_plan = billing_plan or resolved_plan

    if custom_limit is not None:
        limit = custom_limit
    else:
        plan = resolve_plan(actor_type, billing_plan)
        limit = get_limit(plan, feature, endpoint_class, limit_type)

    if limit <= 0:
        logger.warning(
            f"Rate limit is 0 for namespace={namespace}, "
            f"plan={resolve_plan(actor_type, billing_plan)}, "
            f"feature={feature}, endpoint={endpoint_class}"
        )
        return 0

    limiter = get_rate_limiter()
    redis_key = f"rate_limit:{actor_type}:{actor_id}:{namespace}:{window.value}"
    result = await limiter.check_limit(redis_key, limit, window)

    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {namespace}",
            headers={
                "Retry-After": str(result.retry_after or 60),
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(result.reset_at.timestamp())),
            },
        )

    return result.remaining


def _resolve_actor(request: Request) -> tuple[str, str, Optional[str]]:

    current_user = getattr(request.state, "current_user", None)
    if current_user:
        return ("user", str(current_user.id), None)

    current_admin = getattr(request.state, "current_admin", None)
    if current_admin:
        return ("admin", str(current_admin.id), None)

    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
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
                if sub:
                    if aud == TokenAudience.ADMIN.value:
                        return ("admin", sub, None)
                    if aud == TokenAudience.USER.value:
                        return ("user", sub, payload.get("billing_plan", settings.DEFAULT_PLAN_KEY))
            except Exception:
                pass

    client_ip = get_client_ip(request)
    return ("anonymous", client_ip, None)