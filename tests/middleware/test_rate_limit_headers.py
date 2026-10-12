# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for the RateLimitHeadersMiddleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.middleware.rate_limit_headers import (
    RateLimitHeadersMiddleware,
    apply_middleware,
)


class TestRateLimitHeadersMiddleware:
    """Tests for RateLimitHeadersMiddleware ASGI middleware."""

    @pytest.mark.asyncio
    async def test_adds_rate_limit_headers_from_request_state(self):
        """Middleware adds X-RateLimit-* headers when state attributes are present."""
        captured_send = None

        async def app(scope, receive, send):
            nonlocal captured_send
            captured_send = send

        middleware = RateLimitHeadersMiddleware(app)

        state = MagicMock()
        state.rate_limit_limit = 100
        state.rate_limit_remaining = 45
        state.rate_limit_reset = 1690000000

        scope: dict = {"type": "http", "state": state}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        assert captured_send is not None
        await captured_send({"type": "http.response.start", "status": 200, "headers": []})

        send.assert_called()
        start_call = send.call_args[0][0]
        headers = start_call.get("headers", [])
        header_dict = {k.decode().lower(): v.decode() for k, v in headers}
        assert header_dict.get("x-ratelimit-limit") == "100"
        assert header_dict.get("x-ratelimit-remaining") == "45"
        assert header_dict.get("x-ratelimit-reset") == "1690000000"

    @pytest.mark.asyncio
    async def test_missing_state_attributes_are_skipped(self):
        """Headers are only added for state attributes that exist."""
        captured_send = None

        async def app(scope, receive, send):
            nonlocal captured_send
            captured_send = send

        middleware = RateLimitHeadersMiddleware(app)

        state = MagicMock()
        state.rate_limit_limit = 100
        del state.rate_limit_remaining
        del state.rate_limit_reset

        scope: dict = {"type": "http", "state": state}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        await captured_send({"type": "http.response.start", "status": 200, "headers": []})

        start_call = send.call_args[0][0]
        headers = start_call.get("headers", [])
        header_dict = {k.decode().lower(): v.decode() for k, v in headers}
        assert "x-ratelimit-limit" in header_dict
        assert "x-ratelimit-remaining" not in header_dict
        assert "x-ratelimit-reset" not in header_dict

    @pytest.mark.asyncio
    async def test_no_state_object_adds_no_headers(self):
        """When scope has no state, no rate limit headers are added."""
        captured_send = None

        async def app(scope, receive, send):
            nonlocal captured_send
            captured_send = send

        middleware = RateLimitHeadersMiddleware(app)

        scope: dict = {"type": "http"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        await captured_send({"type": "http.response.start", "status": 200, "headers": []})

        start_call = send.call_args[0][0]
        headers = start_call.get("headers", [])
        header_dict = {k.decode(): v.decode() for k, v in headers}
        assert "x-ratelimit-limit" not in header_dict
        assert "x-ratelimit-remaining" not in header_dict
        assert "x-ratelimit-reset" not in header_dict

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self):
        """Non-HTTP scopes (e.g. websocket) pass through without modification."""
        app = AsyncMock()
        middleware = RateLimitHeadersMiddleware(app)

        scope: dict = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # App should be called directly, no header injection
        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_headers_injected_only_once(self):
        """Headers are injected only on the first http.response.start message."""
        captured_send = None

        async def app(scope, receive, send):
            nonlocal captured_send
            captured_send = send

        middleware = RateLimitHeadersMiddleware(app)

        state = MagicMock()
        state.rate_limit_limit = 50
        state.rate_limit_remaining = 10
        state.rate_limit_reset = 1690000000

        scope: dict = {"type": "http", "state": state}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        await captured_send({"type": "http.response.start", "status": 200, "headers": []})
        await captured_send({"type": "http.response.start", "status": 200, "headers": []})

        header_injection_count = 0
        for call in send.call_args_list:
            msg = call[0][0]
            if msg.get("type") == "http.response.start":
                headers = msg.get("headers", [])
                header_dict = {k.decode().lower(): v.decode() for k, v in headers}
                if "x-ratelimit-limit" in header_dict:
                    header_injection_count += 1
        assert header_injection_count == 1


class TestApplyMiddleware:
    """Tests for apply_middleware registration on FastAPI app."""

    def test_apply_middleware_registers_on_fastapi_app(self):
        """apply_middleware calls app.add_middleware with RateLimitHeadersMiddleware."""
        from fastapi import FastAPI

        mock_app = MagicMock(spec=FastAPI)
        apply_middleware(mock_app)
        mock_app.add_middleware.assert_called_once_with(RateLimitHeadersMiddleware)

    def test_apply_middleware_raises_for_non_fastapi(self):
        """apply_middleware raises TypeError for non-FastAPI apps."""
        mock_app = MagicMock()
        mock_app.__class__.__name__ = "Starlette"

        with pytest.raises(TypeError, match="Expected FastAPI app"):
            apply_middleware(mock_app)
