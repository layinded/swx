# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for the Auth Rate Limit Middleware."""

import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.middleware.auth_rate_limit import (
    RateLimitRule,
    _InMemoryCounter,
    AuthRateLimitMiddleware,
    _load_rules_from_env,
    apply_middleware,
)


class TestRateLimitRule:
    """Tests for the RateLimitRule dataclass and matches() method."""

    def test_matches_exact_path(self):
        """Rule with exact_path matches only that exact path."""
        rule = RateLimitRule(
            namespace="auth:login",
            exact_path="/api/auth/login",
            methods=("POST",),
            max_requests=5,
            window_seconds=60,
        )
        assert rule.matches("POST", "/api/auth/login") is True
        assert rule.matches("GET", "/api/auth/login") is False  # Wrong method
        assert rule.matches("POST", "/api/auth/other") is False  # Wrong path

    def test_matches_path_prefix(self):
        """Rule with path_prefix matches any path starting with the prefix."""
        rule = RateLimitRule(
            namespace="auth:api",
            path_prefix="/api/auth/",
            methods=(),
            max_requests=10,
            window_seconds=60,
        )
        assert rule.matches("POST", "/api/auth/login") is True
        assert rule.matches("GET", "/api/auth/verify") is True
        assert rule.matches("POST", "/api/auth/reset/confirm") is True
        assert rule.matches("POST", "/api/other") is False

    def test_matches_all_methods_when_empty(self):
        """When methods is empty, all HTTP methods match."""
        rule = RateLimitRule(
            namespace="all",
            exact_path="/api/public",
            methods=(),
            max_requests=5,
            window_seconds=60,
        )
        assert rule.matches("GET", "/api/public") is True
        assert rule.matches("POST", "/api/public") is True
        assert rule.matches("DELETE", "/api/public") is True

    def test_matches_specific_methods(self):
        """Rule only matches specified HTTP methods."""
        rule = RateLimitRule(
            namespace="login",
            exact_path="/api/auth/login",
            methods=("POST", "PUT"),
            max_requests=5,
            window_seconds=60,
        )
        assert rule.matches("POST", "/api/auth/login") is True
        assert rule.matches("PUT", "/api/auth/login") is True
        assert rule.matches("GET", "/api/auth/login") is False
        assert rule.matches("DELETE", "/api/auth/login") is False

    def test_method_matching_is_case_insensitive(self):
        """Method matching is case-insensitive."""
        rule = RateLimitRule(
            namespace="login",
            exact_path="/api/auth/login",
            methods=("POST",),
            max_requests=5,
            window_seconds=60,
        )
        assert rule.matches("post", "/api/auth/login") is True
        assert rule.matches("Post", "/api/auth/login") is True

    def test_no_path_match_returns_false(self):
        """When neither exact_path nor path_prefix is set, matches returns False."""
        rule = RateLimitRule(
            namespace="no-path",
            methods=(),
            max_requests=5,
            window_seconds=60,
        )
        assert rule.matches("GET", "/anything") is False

    def test_exact_path_takes_priority(self):
        """When both exact_path and path_prefix are set, exact_path is used."""
        rule = RateLimitRule(
            namespace="exact",
            exact_path="/api/exact",
            path_prefix="/api/",
            methods=(),
            max_requests=5,
            window_seconds=60,
        )
        assert rule.matches("GET", "/api/exact") is True
        assert rule.matches("GET", "/api/other") is False  # path_prefix ignored


class TestInMemoryCounter:
    """Tests for the _InMemoryCounter sliding window implementation."""

    def test_first_request_allowed(self):
        """First request is always allowed."""
        counter = _InMemoryCounter()
        allowed, retry_after = counter.check_and_increment("key1", max_requests=5, window_seconds=60)
        assert allowed is True
        assert retry_after == 0

    def test_within_limit_allowed(self):
        """Requests within the limit are allowed."""
        counter = _InMemoryCounter()
        for _ in range(3):
            allowed, _ = counter.check_and_increment("key1", max_requests=5, window_seconds=60)
            assert allowed is True

    def test_exceeds_limit_blocked(self):
        """Requests exceeding the limit are blocked."""
        counter = _InMemoryCounter()
        for _ in range(5):
            allowed, _ = counter.check_and_increment("key1", max_requests=5, window_seconds=60)
            assert allowed is True

        # 6th request should be blocked
        allowed, retry_after = counter.check_and_increment("key1", max_requests=5, window_seconds=60)
        assert allowed is False
        assert retry_after > 0

    def test_different_keys_independent(self):
        """Different keys have independent counters."""
        counter = _InMemoryCounter()
        # Fill up key1
        for _ in range(5):
            counter.check_and_increment("key1", max_requests=5, window_seconds=60)

        # key2 should still be allowed
        allowed, _ = counter.check_and_increment("key2", max_requests=5, window_seconds=60)
        assert allowed is True

    def test_retry_after_is_positive(self):
        """When blocked, retry_after is a positive integer."""
        counter = _InMemoryCounter()
        for _ in range(5):
            counter.check_and_increment("key1", max_requests=5, window_seconds=60)

        allowed, retry_after = counter.check_and_increment("key1", max_requests=5, window_seconds=60)
        assert allowed is False
        assert retry_after >= 1

    def test_eviction_of_expired_entries(self):
        """Expired timestamps are evicted, allowing new requests."""
        counter = _InMemoryCounter()
        # Simulate old timestamps
        old_time = time.monotonic() - 120  # 2 minutes ago
        counter._counts["key1"] = [old_time] * 5

        # With window_seconds=60, all should be expired
        allowed, _ = counter.check_and_increment("key1", max_requests=5, window_seconds=60)
        assert allowed is True


class TestAuthRateLimitMiddleware:
    """Tests for the AuthRateLimitMiddleware ASGI middleware."""

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self):
        """Non-HTTP scopes pass through without rate limiting."""
        app = AsyncMock()
        middleware = AuthRateLimitMiddleware(app, rules=[])

        scope: dict = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_no_rules_passes_through(self):
        """When no rules are configured, all requests pass through."""
        app = AsyncMock()
        middleware = AuthRateLimitMiddleware(app, rules=[])

        scope: dict = {"type": "http", "method": "POST", "path": "/api/auth/login"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_no_matching_rule_passes_through(self):
        """When no rule matches the request, it passes through."""
        app = AsyncMock()
        rule = RateLimitRule(
            namespace="login",
            exact_path="/api/auth/login",
            methods=("POST",),
            max_requests=5,
            window_seconds=60,
        )
        middleware = AuthRateLimitMiddleware(app, rules=[rule])

        scope: dict = {"type": "http", "method": "GET", "path": "/api/other"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_returns_429(self):
        """When rate limit is exceeded, returns 429 with Retry-After."""
        app = AsyncMock()
        rule = RateLimitRule(
            namespace="auth:login",
            exact_path="/api/auth/login",
            methods=("POST",),
            max_requests=1,
            window_seconds=60,
        )
        middleware = AuthRateLimitMiddleware(app, rules=[rule])

        scope: dict = {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "client": ("127.0.0.1", 12345),
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        await middleware(scope, receive, send)

        response_sent = False
        for call in send.call_args_list:
            msg = call[0][0]
            if msg.get("type") == "http.response.start":
                if msg.get("status") == 429:
                    response_sent = True
                    headers = {k.decode().lower(): v.decode() for k, v in msg.get("headers", [])}
                    assert "retry-after" in headers
                    assert "x-ratelimit-limit" in headers
                    break
        assert response_sent is True

    @pytest.mark.asyncio
    async def test_client_ip_from_x_forwarded_for(self):
        """Client IP is extracted from X-Forwarded-For header."""
        app = AsyncMock()
        rule = RateLimitRule(
            namespace="test",
            path_prefix="/api/",
            methods=(),
            max_requests=1,
            window_seconds=60,
        )
        middleware = AuthRateLimitMiddleware(app, rules=[rule])

        scope: dict = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "headers": [(b"x-forwarded-for", b"10.0.0.1, 10.0.0.2")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        # First request from 10.0.0.1
        await middleware(scope, receive, send)
        # Second request from same IP should be blocked
        await middleware(scope, receive, send)

        response_sent = False
        for call in send.call_args_list:
            msg = call[0][0]
            if msg.get("type") == "http.response.start" and msg.get("status") == 429:
                response_sent = True
                break
        assert response_sent is True

    @pytest.mark.asyncio
    async def test_client_ip_from_scope_client(self):
        """Client IP falls back to scope.client when no X-Forwarded-For."""
        app = AsyncMock()
        rule = RateLimitRule(
            namespace="test",
            path_prefix="/api/",
            methods=(),
            max_requests=1,
            window_seconds=60,
        )
        middleware = AuthRateLimitMiddleware(app, rules=[rule])

        scope: dict = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "client": ("192.168.1.1", 54321),
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        await middleware(scope, receive, send)

        response_sent = False
        for call in send.call_args_list:
            msg = call[0][0]
            if msg.get("type") == "http.response.start" and msg.get("status") == 429:
                response_sent = True
                break
        assert response_sent is True

    @pytest.mark.asyncio
    async def test_unknown_client_ip(self):
        """When no client info is available, uses 'unknown'."""
        app = AsyncMock()
        rule = RateLimitRule(
            namespace="test",
            path_prefix="/api/",
            methods=(),
            max_requests=1,
            window_seconds=60,
        )
        middleware = AuthRateLimitMiddleware(app, rules=[rule])

        scope: dict = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
        }
        receive = AsyncMock()
        send = AsyncMock()

        # Should not crash
        await middleware(scope, receive, send)

    @pytest.mark.asyncio
    async def test_multiple_rules_first_match_wins(self):
        """When multiple rules match, the first matching rule is enforced."""
        app = AsyncMock()
        rule1 = RateLimitRule(
            namespace="strict",
            path_prefix="/api/",
            methods=(),
            max_requests=1,
            window_seconds=60,
        )
        rule2 = RateLimitRule(
            namespace="lenient",
            path_prefix="/api/",
            methods=(),
            max_requests=100,
            window_seconds=60,
        )
        middleware = AuthRateLimitMiddleware(app, rules=[rule1, rule2])

        scope: dict = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "client": ("127.0.0.1", 12345),
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        await middleware(scope, receive, send)

        # Should be blocked by rule1 (max_requests=1)
        response_sent = False
        for call in send.call_args_list:
            msg = call[0][0]
            if msg.get("type") == "http.response.start" and msg.get("status") == 429:
                response_sent = True
                break
        assert response_sent is True


class TestLoadRulesFromEnv:
    """Tests for the _load_rules_from_env function."""

    def test_loads_valid_json_rules(self):
        """Valid JSON array of rules is parsed correctly."""
        rules_json = json.dumps([
            {
                "namespace": "auth:login",
                "exact_path": "/api/auth/login",
                "methods": ["POST"],
                "max_requests": 5,
                "window_seconds": 60,
            },
            {
                "namespace": "auth:verify",
                "path_prefix": "/api/auth/verify",
                "methods": ["GET", "POST"],
                "max_requests": 10,
                "window_seconds": 120,
            },
        ])
        with patch.dict(os.environ, {"SWX_AUTH_RATE_LIMIT_RULES": rules_json}):
            rules = _load_rules_from_env()

        assert len(rules) == 2
        assert rules[0].namespace == "auth:login"
        assert rules[0].exact_path == "/api/auth/login"
        assert rules[0].methods == ("POST",)
        assert rules[0].max_requests == 5
        assert rules[0].window_seconds == 60

        assert rules[1].namespace == "auth:verify"
        assert rules[1].path_prefix == "/api/auth/verify"
        assert rules[1].methods == ("GET", "POST")

    def test_empty_env_returns_empty_list(self):
        """Empty or missing env var returns empty list."""
        with patch.dict(os.environ, {}, clear=True):
            rules = _load_rules_from_env()
        assert rules == []

    def test_invalid_json_returns_empty_list(self):
        """Invalid JSON returns empty list."""
        with patch.dict(os.environ, {"SWX_AUTH_RATE_LIMIT_RULES": "not json"}):
            rules = _load_rules_from_env()
        assert rules == []

    def test_non_list_json_returns_empty_list(self):
        """JSON that is not a list returns empty list."""
        with patch.dict(os.environ, {"SWX_AUTH_RATE_LIMIT_RULES": '{"key": "value"}'}):
            rules = _load_rules_from_env()
        assert rules == []

    def test_skips_entries_without_namespace(self):
        """Entries without a namespace are skipped."""
        rules_json = json.dumps([
            {"exact_path": "/api/test", "max_requests": 5},
            {"namespace": "valid", "exact_path": "/api/valid", "max_requests": 10},
        ])
        with patch.dict(os.environ, {"SWX_AUTH_RATE_LIMIT_RULES": rules_json}):
            rules = _load_rules_from_env()

        assert len(rules) == 1
        assert rules[0].namespace == "valid"

    def test_skips_non_dict_entries(self):
        """Non-dict entries in the array are skipped."""
        rules_json = json.dumps([
            "not a dict",
            {"namespace": "valid", "exact_path": "/api/valid", "max_requests": 10},
        ])
        with patch.dict(os.environ, {"SWX_AUTH_RATE_LIMIT_RULES": rules_json}):
            rules = _load_rules_from_env()

        assert len(rules) == 1
        assert rules[0].namespace == "valid"

    def test_default_values_for_missing_fields(self):
        """Missing fields get default values."""
        rules_json = json.dumps([
            {"namespace": "minimal"},
        ])
        with patch.dict(os.environ, {"SWX_AUTH_RATE_LIMIT_RULES": rules_json}):
            rules = _load_rules_from_env()

        assert len(rules) == 1
        assert rules[0].path_prefix == ""
        assert rules[0].exact_path == ""
        assert rules[0].methods == ()
        assert rules[0].max_requests == 5
        assert rules[0].window_seconds == 60

    def test_methods_are_uppercased(self):
        """HTTP methods are uppercased."""
        rules_json = json.dumps([
            {"namespace": "test", "exact_path": "/api/test", "methods": ["post", "get"]},
        ])
        with patch.dict(os.environ, {"SWX_AUTH_RATE_LIMIT_RULES": rules_json}):
            rules = _load_rules_from_env()

        assert rules[0].methods == ("POST", "GET")


class TestApplyMiddleware:
    """Tests for apply_middleware registration on FastAPI app."""

    def test_apply_middleware_with_rules(self):
        """apply_middleware registers middleware when rules are configured."""
        from fastapi import FastAPI

        mock_app = MagicMock(spec=FastAPI)

        rules_json = json.dumps([
            {"namespace": "auth:login", "exact_path": "/api/auth/login", "methods": ["POST"]},
        ])
        with patch.dict(os.environ, {"SWX_AUTH_RATE_LIMIT_RULES": rules_json}):
            apply_middleware(mock_app)

        mock_app.add_middleware.assert_called_once()

    def test_apply_middleware_without_rules_skips(self):
        """apply_middleware does not register when no rules are configured."""
        from fastapi import FastAPI

        mock_app = MagicMock(spec=FastAPI)

        with patch.dict(os.environ, {}, clear=True):
            apply_middleware(mock_app)

        mock_app.add_middleware.assert_not_called()

    def test_apply_middleware_raises_for_non_fastapi(self):
        """apply_middleware raises TypeError for non-FastAPI apps."""
        mock_app = MagicMock()
        mock_app.__class__.__name__ = "Starlette"

        with pytest.raises(TypeError, match="Expected FastAPI app"):
            apply_middleware(mock_app)
