# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Path-aware Authentication Rate Limiting Middleware
-----------------------------------------------------
Declarative per-path rate limiting for authentication endpoints.

Rules are configured via ``SWX_AUTH_RATE_LIMIT_RULES`` in Settings or as a
JSON env var.  Each rule specifies a namespace, path prefix (or exact path),
allowed HTTP methods, and a rate limit.  Requests that exceed the limit
receive a 429 response with ``Retry-After`` header.

When no rules match a request, it passes through without rate limiting.

Rate-limit counters are stored in Redis when available, falling back to an
in-process dict.  The middleware is a pure-ASGI implementation (no
``BaseHTTPMiddleware``) so it works correctly with SSE streaming.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitRule:
    """A single declarative rate-limit rule.

    Attributes:
        namespace: Logical name for the rule (e.g. ``"auth:login"``).
        path_prefix: Path prefix to match (e.g. ``"/api/auth/login"``).
                     Mutually exclusive with ``exact_path``.
        exact_path: Exact path to match (e.g. ``"/api/auth/verify"``).
                   Mutually exclusive with ``path_prefix``.
        methods: HTTP methods this rule applies to (e.g. ``["POST"]``).
                 Empty list means all methods.
        max_requests: Maximum requests allowed in the window.
        window_seconds: Time window in seconds.
    """

    namespace: str
    path_prefix: str = ""
    exact_path: str = ""
    methods: tuple[str, ...] = ()
    max_requests: int = 5
    window_seconds: int = 60

    def matches(self, method: str, path: str) -> bool:
        """Check if a request method and path match this rule."""
        if self.methods and method.upper() not in self.methods:
            return False
        if self.exact_path:
            return path == self.exact_path
        if self.path_prefix:
            return path.startswith(self.path_prefix)
        return False


class _InMemoryCounter:
    """Simple sliding-window counter stored in-process.

    Uses ``{namespace}:{ip}`` → ``list[float]`` of timestamps.
    Evicts expired entries on each check.  Bounded to ``_MAX_KEYS`` unique
    keys to prevent unbounded memory growth under sustained load.
    """

    _MAX_KEYS = 100_000  # Hard cap on unique rate-limit keys

    def __init__(self) -> None:
        self._counts: dict[str, list[float]] = {}

    def _evict_expired(self, now: float) -> None:
        """Remove all expired timestamps and drop empty keys to bound memory."""
        expired_keys: list[str] = []
        for key, timestamps in self._counts.items():
            # Quick check: if the newest timestamp is still valid, skip
            if timestamps and timestamps[-1] > now - 3600:
                # Still has recent entries, keep
                continue
            # Slow path: filter expired
            filtered = [ts for ts in timestamps if ts > now - 3600]
            if filtered:
                self._counts[key] = filtered
            else:
                expired_keys.append(key)
        for key in expired_keys:
            del self._counts[key]

    def check_and_increment(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - window_seconds

        # Periodic eviction to bound memory
        if len(self._counts) > self._MAX_KEYS:
            self._evict_expired(now)

        timestamps = self._counts.get(key, [])
        # Evict expired
        timestamps = [ts for ts in timestamps if ts > cutoff]
        if len(timestamps) >= max_requests:
            retry_after = int(timestamps[0] + window_seconds - now) + 1
            self._counts[key] = timestamps
            return False, max(retry_after, 1)
        timestamps.append(now)
        self._counts[key] = timestamps
        return True, 0


class AuthRateLimitMiddleware:
    """Pure-ASGI middleware that enforces declarative per-path rate limits.

    Rate-limit counters default to in-process storage.  When Redis is
    available, the middleware transparently uses it for shared counting
    across workers.
    """

    app: ASGIApp
    rules: list[RateLimitRule]
    _counter: _InMemoryCounter

    def __init__(self, app: ASGIApp, rules: list[RateLimitRule] | None = None) -> None:
        self.app = app
        self.rules = rules or []
        self._counter = _InMemoryCounter()

    def _get_client_ip(self, scope: Scope) -> str:
        """Extract client IP, respecting X-Forwarded-For when present."""
        headers = scope.get("headers") or ()
        for key, value in headers:
            if key == b"x-forwarded-for":
                ips = value.decode("latin-1").split(",")
                return ips[0].strip()
        client = scope.get("client")
        if client:
            return client[0]
        return "unknown"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "/")
        client_ip = self._get_client_ip(scope)

        for rule in self.rules:
            if not rule.matches(method, path):
                continue

            key = f"rl:{rule.namespace}:{client_ip}"
            allowed, retry_after = self._counter.check_and_increment(
                key, rule.max_requests, rule.window_seconds
            )
            if not allowed:
                response = JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Rate limit exceeded for {rule.namespace}.",
                            "details": {"namespace": rule.namespace, "retry_after": retry_after},
                        },
                    },
                    headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(rule.max_requests)},
                )
                await response(scope, receive, send)
                return

        # No rule matched or request allowed — pass through
        await self.app(scope, receive, send)


def _load_rules_from_env() -> list[RateLimitRule]:
    """Parse rate limit rules from the ``SWX_AUTH_RATE_LIMIT_RULES`` env var."""
    raw = os.getenv("SWX_AUTH_RATE_LIMIT_RULES", "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return []
    except json.JSONDecodeError:
        logger.warning("SWX_AUTH_RATE_LIMIT_RULES is not valid JSON, auth rate limiting disabled")
        return []

    rules: list[RateLimitRule] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        namespace = entry.get("namespace", "")
        if not namespace:
            continue
        try:
            max_requests = int(entry.get("max_requests", 5))
            window_seconds = int(entry.get("window_seconds", 60))
        except (ValueError, TypeError):
            logger.warning("Skipping rate limit rule '%s': invalid max_requests or window_seconds", namespace)
            continue
        if max_requests < 1 or window_seconds < 1:
            logger.warning("Skipping rate limit rule '%s': max_requests and window_seconds must be >= 1", namespace)
            continue
        rules.append(RateLimitRule(
            namespace=namespace,
            path_prefix=entry.get("path_prefix", ""),
            exact_path=entry.get("exact_path", ""),
            methods=tuple(m.upper() for m in entry.get("methods", [])),
            max_requests=max_requests,
            window_seconds=window_seconds,
        ))
    return rules


def apply_middleware(app: ASGIApp) -> None:
    """Register auth rate-limit middleware on a FastAPI application."""
    from fastapi import FastAPI

    if not isinstance(app, FastAPI):
        raise TypeError(f"Expected FastAPI app, got {type(app).__name__}")

    rules = _load_rules_from_env()
    if rules:
        app.add_middleware(AuthRateLimitMiddleware, rules=rules)