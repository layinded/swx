# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for swx_core.middleware.csrf_middleware."""

import secrets
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.middleware.csrf_middleware import (
    CSRFConfig,
    CSRFMiddleware,
    _add_delete_cookie,
    _add_set_cookie,
    _get_cookie_value,
    _get_or_create_csrf_token,
    _has_auth_cookie_no_csrf,
    _is_exempt,
    _matches_path,
    _send_forbidden,
    apply_middleware,
    generate_csrf_token,
    get_csrf_token,
    set_csrf_cookie,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scope(
    path: str = "/api/test",
    method: str = "GET",
    scope_type: str = "http",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict:
    """Build a minimal ASGI scope dict."""
    return {
        "type": scope_type,
        "method": method,
        "path": path,
        "headers": headers or [],
    }


def _make_response_start(headers: list[tuple[bytes, bytes]] | None = None) -> dict:
    """Build a minimal http.response.start message."""
    return {
        "type": "http.response.start",
        "status": 200,
        "headers": headers or [],
    }


def _headers_to_dict(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    """Convert ASGI header tuples to a lowercase-keyed dict."""
    return {k.decode().lower(): v.decode() for k, v in headers}


# ---------------------------------------------------------------------------
# _matches_path
# ---------------------------------------------------------------------------

class TestMatchesPath:
    """Tests for the _matches_path helper."""

    def test_exact_match(self) -> None:
        """Exact path match returns True."""
        assert _matches_path("/api/auth/login", ["/api/auth/login"]) is True

    def test_prefix_match(self) -> None:
        """Path with trailing sub-path matches prefix."""
        assert _matches_path("/api/auth/login/callback", ["/api/auth/login"]) is True

    def test_no_match(self) -> None:
        """Unrelated path returns False."""
        assert _matches_path("/api/users", ["/api/auth/login"]) is False

    def test_multiple_patterns(self) -> None:
        """Any matching pattern returns True."""
        patterns = ["/api/auth/login", "/api/auth/social/login"]
        assert _matches_path("/api/auth/social/login", patterns) is True
        assert _matches_path("/api/other", patterns) is False


# ---------------------------------------------------------------------------
# _is_exempt
# ---------------------------------------------------------------------------

class TestIsExempt:
    """Tests for the _is_exempt helper."""

    def test_exact_exempt_path(self) -> None:
        """Exact exempt path returns True."""
        cfg = CSRFConfig()
        assert _is_exempt("/docs", cfg) is True
        assert _is_exempt("/openapi.json", cfg) is True

    def test_exempt_prefix(self) -> None:
        """Path starting with exempt prefix returns True."""
        cfg = CSRFConfig()
        assert _is_exempt("/api/utils/health", cfg) is True
        assert _is_exempt("/api/utils/health/check", cfg) is True

    def test_non_exempt_path(self) -> None:
        """Non-exempt path returns False."""
        cfg = CSRFConfig()
        assert _is_exempt("/api/users", cfg) is False


# ---------------------------------------------------------------------------
# _has_auth_cookie_no_csrf
# ---------------------------------------------------------------------------

class TestHasAuthCookieNoCSRF:
    """Tests for the _has_auth_cookie_no_csrf helper."""

    def test_auth_cookie_present_csrf_missing(self) -> None:
        """Returns True when auth cookie exists but CSRF cookie is missing."""
        with patch("swx_core.middleware.csrf_middleware.settings") as mock_settings:
            mock_settings.COOKIE_ACCESS_TOKEN_NAME = "access_token"
            cfg = CSRFConfig(cookie_name="csrf_token")
            cookie_str = "access_token=abc123"
            assert _has_auth_cookie_no_csrf(cookie_str, cfg) is True

    def test_both_cookies_present(self) -> None:
        """Returns False when both auth and CSRF cookies exist."""
        with patch("swx_core.middleware.csrf_middleware.settings") as mock_settings:
            mock_settings.COOKIE_ACCESS_TOKEN_NAME = "access_token"
            cfg = CSRFConfig(cookie_name="csrf_token")
            cookie_str = "access_token=abc123; csrf_token=xyz"
            assert _has_auth_cookie_no_csrf(cookie_str, cfg) is False

    def test_no_auth_cookie(self) -> None:
        """Returns False when no auth cookie is present."""
        with patch("swx_core.middleware.csrf_middleware.settings") as mock_settings:
            mock_settings.COOKIE_ACCESS_TOKEN_NAME = "access_token"
            cfg = CSRFConfig()
            cookie_str = ""
            assert _has_auth_cookie_no_csrf(cookie_str, cfg) is False


# ---------------------------------------------------------------------------
# _get_cookie_value
# ---------------------------------------------------------------------------

class TestGetCookieValue:
    """Tests for the _get_cookie_value helper."""

    def test_extracts_cookie_value(self) -> None:
        """Cookie value is extracted from the Cookie header."""
        cookie_str = "csrf_token=abc123; other=val"
        assert _get_cookie_value(cookie_str, "csrf_token") == "abc123"

    def test_returns_none_when_missing(self) -> None:
        """Returns None when the cookie is not present."""
        cookie_str = "other=val"
        assert _get_cookie_value(cookie_str, "csrf_token") is None

    def test_returns_none_when_no_cookie_header(self) -> None:
        """Returns None when there is no Cookie header."""
        cookie_str = ""
        assert _get_cookie_value(cookie_str, "csrf_token") is None


# ---------------------------------------------------------------------------
# _get_or_create_csrf_token
# ---------------------------------------------------------------------------

class TestGetOrCreateCSRFToken:
    """Tests for the _get_or_create_csrf_token helper."""

    def test_returns_existing_token(self) -> None:
        """Returns existing CSRF token from cookies."""
        cfg = CSRFConfig(cookie_name="csrf_token")
        cookie_str = "csrf_token=existing-token"
        token = _get_or_create_csrf_token(cookie_str, cfg)
        assert token == "existing-token"

    def test_creates_new_token_when_missing(self) -> None:
        """Creates a new token when no CSRF cookie exists."""
        cfg = CSRFConfig(cookie_name="csrf_token")
        cookie_str = ""
        token = _get_or_create_csrf_token(cookie_str, cfg)
        assert token is not None
        assert len(token) > 0


# ---------------------------------------------------------------------------
# _add_set_cookie / _add_delete_cookie
# ---------------------------------------------------------------------------

class TestCookieHelpers:
    """Tests for _add_set_cookie and _add_delete_cookie."""

    def test_add_set_cookie_includes_token(self) -> None:
        """Set-Cookie header includes the CSRF token."""
        with patch("swx_core.middleware.csrf_middleware.settings") as mock_settings:
            mock_settings.COOKIE_SECURE = False
            mock_settings.ENVIRONMENT = "local"
            mock_settings.COOKIE_SAMESITE = "lax"
            mock_settings.COOKIE_DOMAIN = None
            cfg = CSRFConfig(cookie_name="csrf_token", cookie_max_age=86400)
            result = _add_set_cookie([], "my-token", cfg)
            hdrs = _headers_to_dict(result)
            assert "set-cookie" in hdrs
            assert "csrf_token=my-token" in hdrs["set-cookie"]
            assert "Max-Age=86400" in hdrs["set-cookie"]

    def test_add_delete_cookie_clears_token(self) -> None:
        """Set-Cookie header clears the CSRF token."""
        with patch("swx_core.middleware.csrf_middleware.settings") as mock_settings:
            mock_settings.COOKIE_SAMESITE = "lax"
            cfg = CSRFConfig(cookie_name="csrf_token")
            result = _add_delete_cookie([], cfg)
            hdrs = _headers_to_dict(result)
            assert "set-cookie" in hdrs
            assert "csrf_token=;" in hdrs["set-cookie"]
            assert "Max-Age=0" in hdrs["set-cookie"]


# ---------------------------------------------------------------------------
# _send_forbidden
# ---------------------------------------------------------------------------

class TestSendForbidden:
    """Tests for the _send_forbidden helper."""

    @pytest.mark.asyncio
    async def test_sends_403_response(self) -> None:
        """_send_forbidden sends a 403 JSON response."""
        send = AsyncMock()
        scope: dict = {"type": "http"}
        receive = AsyncMock()

        await _send_forbidden(scope, receive, send, "CSRF token validation failed")

        assert send.await_count == 2
        start_call = send.await_args_list[0].args[0]
        assert start_call["type"] == "http.response.start"
        assert start_call["status"] == 403

        body_call = send.await_args_list[1].args[0]
        assert body_call["type"] == "http.response.body"
        assert b"CSRF token validation failed" in body_call["body"]


# ---------------------------------------------------------------------------
# CSRFMiddleware
# ---------------------------------------------------------------------------

class TestCSRFMiddleware:
    """Tests for the CSRFMiddleware ASGI middleware."""

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self) -> None:
        """Non-HTTP scopes pass through without CSRF processing."""
        inner_app = AsyncMock()
        middleware = CSRFMiddleware(inner_app)

        scope: dict = {"type": "lifespan"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        inner_app.assert_awaited_once()
        call_scope, _call_receive, call_send = inner_app.await_args.args
        assert call_scope == scope
        assert call_send is send

    @pytest.mark.asyncio
    async def test_websocket_passes_through(self) -> None:
        """WebSocket scopes pass through without CSRF processing."""
        inner_app = AsyncMock()
        middleware = CSRFMiddleware(inner_app)

        scope: dict = {"type": "websocket", "path": "/ws"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        inner_app.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_login_path_sets_csrf_cookie(self) -> None:
        """CSRF cookie is set on login paths (GET avoids CSRF validation)."""
        async def simulate_app(_scope, _receive, send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = CSRFMiddleware(simulate_app)
        scope = _make_scope(path="/api/auth/login", method="GET")
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        first_call = send.await_args_list[0].args[0]
        hdrs = _headers_to_dict(first_call["headers"])
        assert "set-cookie" in hdrs
        assert "csrf_token=" in hdrs["set-cookie"]

    @pytest.mark.asyncio
    async def test_logout_path_deletes_csrf_cookie(self) -> None:
        """CSRF cookie is deleted on logout paths (GET avoids CSRF validation)."""
        async def simulate_app(_scope, _receive, send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = CSRFMiddleware(simulate_app)
        scope = _make_scope(path="/api/auth/logout", method="GET")
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        first_call = send.await_args_list[0].args[0]
        hdrs = _headers_to_dict(first_call["headers"])
        assert "set-cookie" in hdrs
        assert "Max-Age=0" in hdrs["set-cookie"]

    @pytest.mark.asyncio
    async def test_bearer_auth_skips_validation(self) -> None:
        """Bearer token auth skips CSRF validation."""
        async def simulate_app(_scope, _receive, send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = CSRFMiddleware(simulate_app)
        scope = _make_scope(
            path="/api/users",
            method="POST",
            headers=[(b"authorization", b"Bearer token123")],
        )
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        first_call = send.await_args_list[0].args[0]
        assert first_call["status"] == 200

    @pytest.mark.asyncio
    async def test_api_key_auth_skips_validation(self) -> None:
        """API key auth skips CSRF validation."""
        async def simulate_app(_scope, _receive, send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = CSRFMiddleware(simulate_app)
        scope = _make_scope(
            path="/api/users",
            method="POST",
            headers=[(b"x-api-key", b"key-abc123")],
        )
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        first_call = send.await_args_list[0].args[0]
        assert first_call["status"] == 200

    @pytest.mark.asyncio
    async def test_lazy_set_when_auth_cookie_exists_no_csrf(self) -> None:
        """CSRF cookie is lazy-set when auth cookie exists but CSRF is missing."""
        with patch("swx_core.middleware.csrf_middleware.settings") as mock_settings:
            mock_settings.COOKIE_ACCESS_TOKEN_NAME = "access_token"
            mock_settings.COOKIE_SECURE = False
            mock_settings.ENVIRONMENT = "local"
            mock_settings.COOKIE_SAMESITE = "lax"
            mock_settings.COOKIE_DOMAIN = None

            async def simulate_app(_scope, _receive, send) -> None:
                await send({"type": "http.response.start", "status": 200, "headers": []})
                await send({"type": "http.response.body", "body": b"ok"})

            middleware = CSRFMiddleware(simulate_app)
            scope = _make_scope(
                path="/api/some-page",
                method="GET",
                headers=[(b"cookie", b"access_token=abc123")],
            )
            receive = AsyncMock()
            send = AsyncMock()

            await middleware(scope, receive, send)

            first_call = send.await_args_list[0].args[0]
            hdrs = _headers_to_dict(first_call["headers"])
            assert "set-cookie" in hdrs
            assert "csrf_token=" in hdrs["set-cookie"]

    @pytest.mark.asyncio
    async def test_missing_csrf_tokens_on_protected_method_returns_403(self) -> None:
        """Protected method without CSRF tokens returns 403."""
        inner_app = AsyncMock()
        middleware = CSRFMiddleware(inner_app)
        scope = _make_scope(path="/api/users", method="POST")
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        first_call = send.await_args_list[0].args[0]
        assert first_call["status"] == 403

    @pytest.mark.asyncio
    async def test_csrf_token_mismatch_returns_403(self) -> None:
        """Mismatched CSRF tokens return 403."""
        inner_app = AsyncMock()
        middleware = CSRFMiddleware(inner_app)
        scope = _make_scope(
            path="/api/users",
            method="POST",
            headers=[
                (b"cookie", b"csrf_token=token-a"),
                (b"x-csrf-token", b"token-b"),
            ],
        )
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        first_call = send.await_args_list[0].args[0]
        assert first_call["status"] == 403

    @pytest.mark.asyncio
    async def test_valid_csrf_tokens_allow_request(self) -> None:
        """Matching CSRF tokens allow the request through."""
        async def simulate_app(_scope, _receive, send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = CSRFMiddleware(simulate_app)
        token = "valid-csrf-token"
        scope = _make_scope(
            path="/api/users",
            method="POST",
            headers=[
                (b"cookie", f"csrf_token={token}".encode()),
                (b"x-csrf-token", token.encode()),
            ],
        )
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        first_call = send.await_args_list[0].args[0]
        assert first_call["status"] == 200

    @pytest.mark.asyncio
    async def test_get_request_skips_validation(self) -> None:
        """GET requests skip CSRF validation."""
        async def simulate_app(_scope, _receive, send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = CSRFMiddleware(simulate_app)
        scope = _make_scope(path="/api/users", method="GET")
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        first_call = send.await_args_list[0].args[0]
        assert first_call["status"] == 200

    @pytest.mark.asyncio
    async def test_exempt_path_skips_validation(self) -> None:
        """Exempt paths skip CSRF validation even for protected methods."""
        async def simulate_app(_scope, _receive, send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = CSRFMiddleware(simulate_app)
        scope = _make_scope(path="/docs", method="POST")
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        first_call = send.await_args_list[0].args[0]
        assert first_call["status"] == 200


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    """Tests for generate_csrf_token, get_csrf_token, set_csrf_cookie, apply_middleware."""

    def test_generate_csrf_token_returns_string(self) -> None:
        """generate_csrf_token returns a non-empty string."""
        with patch("swx_core.middleware.csrf_middleware.settings") as mock_settings:
            mock_settings.CSRF_TOKEN_LENGTH = 32
            token = generate_csrf_token()
            assert isinstance(token, str)
            assert len(token) > 0

    @pytest.mark.asyncio
    async def test_get_csrf_token_returns_existing(self) -> None:
        """get_csrf_token returns existing cookie value."""
        request = MagicMock()
        request.cookies = {"csrf_token": "existing-token"}
        with patch("swx_core.middleware.csrf_middleware.settings") as mock_settings:
            mock_settings.CSRF_COOKIE_NAME = "csrf_token"
            token = await get_csrf_token(request)
            assert token == "existing-token"

    @pytest.mark.asyncio
    async def test_get_csrf_token_creates_new(self) -> None:
        """get_csrf_token creates a new token when cookie is missing."""
        request = MagicMock()
        request.cookies = {}
        with patch("swx_core.middleware.csrf_middleware.settings") as mock_settings:
            mock_settings.CSRF_COOKIE_NAME = "csrf_token"
            mock_settings.CSRF_TOKEN_LENGTH = 32
            token = await get_csrf_token(request)
            assert isinstance(token, str)
            assert len(token) > 0

    @pytest.mark.asyncio
    async def test_set_csrf_cookie_calls_response_set_cookie(self) -> None:
        """set_csrf_cookie calls response.set_cookie with correct params."""
        response = MagicMock()
        with patch("swx_core.middleware.csrf_middleware.settings") as mock_settings:
            mock_settings.CSRF_COOKIE_NAME = "csrf_token"
            mock_settings.COOKIE_SECURE = False
            mock_settings.ENVIRONMENT = "local"
            mock_settings.COOKIE_SAMESITE = "lax"
            mock_settings.CSRF_COOKIE_MAX_AGE = 86400
            mock_settings.COOKIE_DOMAIN = None

            await set_csrf_cookie(response, "my-token")

        response.set_cookie.assert_called_once()
        kwargs = response.set_cookie.call_args.kwargs
        assert kwargs["key"] == "csrf_token"
        assert kwargs["value"] == "my-token"
        assert kwargs["httponly"] is False

    def test_apply_middleware_disabled(self) -> None:
        """apply_middleware does nothing when CSRF_ENABLED is False."""
        mock_app = MagicMock()
        with patch("swx_core.middleware.csrf_middleware.settings") as mock_settings:
            mock_settings.CSRF_ENABLED = False
            mock_settings.ENVIRONMENT = "local"
            apply_middleware(mock_app)

        mock_app.add_middleware.assert_not_called()
