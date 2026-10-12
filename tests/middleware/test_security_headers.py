# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for swx_core.middleware.security_headers_middleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.middleware.security_headers_middleware import (
    SecurityHeadersConfig,
    SecurityHeadersMiddleware,
    _inject_headers,
    _is_docs_path,
    setup_security_headers,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scope(
    path: str = "/api/test",
    method: str = "GET",
    scope_type: str = "http",
    content_type: bytes = b"application/json",
) -> dict:
    """Build a minimal ASGI scope dict."""
    return {
        "type": scope_type,
        "method": method,
        "path": path,
        "headers": [
            (b"content-type", content_type),
        ],
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
# SecurityHeadersConfig
# ---------------------------------------------------------------------------

class TestSecurityHeadersConfig:
    """Tests for SecurityHeadersConfig defaults."""

    def test_defaults(self) -> None:
        """Default config has expected values."""
        cfg = SecurityHeadersConfig()
        assert cfg.hsts_max_age == 63072000
        assert cfg.hsts_include_subdomains is True
        assert cfg.hsts_preload is True
        assert cfg.content_type_nosniff is True
        assert cfg.frame_options == "DENY"
        assert cfg.referrer_policy == "strict-origin-when-cross-origin"
        assert cfg.corp_for_sse == "cross-origin"
        assert cfg.corp_default == "same-origin"
        assert cfg.csp_api == "default-src 'none'; frame-ancestors 'none'"

    def test_custom_values(self) -> None:
        """Custom config values override defaults."""
        cfg = SecurityHeadersConfig(
            hsts_max_age=3600,
            frame_options="SAMEORIGIN",
            corp_default="cross-origin",
        )
        assert cfg.hsts_max_age == 3600
        assert cfg.frame_options == "SAMEORIGIN"
        assert cfg.corp_default == "cross-origin"


# ---------------------------------------------------------------------------
# _is_docs_path
# ---------------------------------------------------------------------------

class TestIsDocsPath:
    """Tests for the _is_docs_path helper."""

    def test_docs_paths_are_detected(self) -> None:
        """Known docs paths return True."""
        assert _is_docs_path("/docs") is True
        assert _is_docs_path("/redoc") is True
        assert _is_docs_path("/openapi.json") is True

    def test_docs_paths_with_trailing_slash(self) -> None:
        """Trailing slashes are stripped before matching."""
        assert _is_docs_path("/docs/") is True
        assert _is_docs_path("/redoc/") is True

    def test_api_paths_are_not_docs(self) -> None:
        """Regular API paths return False."""
        assert _is_docs_path("/api/users") is False
        assert _is_docs_path("/api/auth/login") is False


# ---------------------------------------------------------------------------
# _inject_headers
# ---------------------------------------------------------------------------

class TestInjectHeaders:
    """Tests for the _inject_headers function."""

    def test_all_security_headers_present(self) -> None:
        """All expected security headers are injected on a regular response."""
        cfg = SecurityHeadersConfig()
        scope = _make_scope(path="/api/test")
        msg = _make_response_start()
        result = _inject_headers(msg, cfg, scope)
        hdrs = _headers_to_dict(result["headers"])

        assert "x-content-type-options" in hdrs
        assert hdrs["x-content-type-options"] == "nosniff"
        assert "x-frame-options" in hdrs
        assert hdrs["x-frame-options"] == "DENY"
        assert "x-xss-protection" in hdrs
        assert hdrs["x-xss-protection"] == "0"
        assert "referrer-policy" in hdrs
        assert hdrs["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "permissions-policy" in hdrs
        assert "cross-origin-resource-policy" in hdrs
        assert "cross-origin-opener-policy" in hdrs
        assert "cross-origin-embedder-policy" in hdrs

    def test_sse_response_gets_cross_origin_corp(self) -> None:
        """SSE (text/event-stream) responses get cross-origin CORP."""
        cfg = SecurityHeadersConfig()
        scope = _make_scope(path="/api/stream", content_type=b"text/event-stream")
        msg = _make_response_start([(b"content-type", b"text/event-stream")])
        result = _inject_headers(msg, cfg, scope)
        hdrs = _headers_to_dict(result["headers"])

        assert hdrs["cross-origin-resource-policy"] == "cross-origin"

    def test_api_route_gets_restrictive_csp(self) -> None:
        """API routes get the restrictive CSP header."""
        cfg = SecurityHeadersConfig()
        scope = _make_scope(path="/api/users")
        msg = _make_response_start()
        result = _inject_headers(msg, cfg, scope)
        hdrs = _headers_to_dict(result["headers"])

        assert "content-security-policy" in hdrs
        assert hdrs["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"

    def test_docs_path_skips_csp(self) -> None:
        """Docs paths do not get the CSP header."""
        cfg = SecurityHeadersConfig()
        scope = _make_scope(path="/docs")
        msg = _make_response_start()
        result = _inject_headers(msg, cfg, scope)
        hdrs = _headers_to_dict(result["headers"])

        assert "content-security-policy" not in hdrs

    def test_existing_headers_are_preserved(self) -> None:
        """Headers already set by the application are not overwritten."""
        cfg = SecurityHeadersConfig()
        scope = _make_scope(path="/api/test")
        msg = _make_response_start([(b"x-custom", b"my-value")])
        result = _inject_headers(msg, cfg, scope)
        hdrs = _headers_to_dict(result["headers"])

        assert hdrs["x-custom"] == "my-value"

    def test_hsts_in_production(self) -> None:
        """HSTS header is injected in production environment."""
        cfg = SecurityHeadersConfig(environment="production")
        scope = _make_scope(path="/api/test")
        msg = _make_response_start()
        result = _inject_headers(msg, cfg, scope)
        hdrs = _headers_to_dict(result["headers"])

        assert "strict-transport-security" in hdrs
        assert "max-age=63072000" in hdrs["strict-transport-security"]
        assert "includeSubDomains" in hdrs["strict-transport-security"]
        assert "preload" in hdrs["strict-transport-security"]

    def test_hsts_not_in_local(self) -> None:
        """HSTS header is NOT injected in local environment."""
        cfg = SecurityHeadersConfig(environment="local")
        scope = _make_scope(path="/api/test")
        msg = _make_response_start()
        result = _inject_headers(msg, cfg, scope)
        hdrs = _headers_to_dict(result["headers"])

        assert "strict-transport-security" not in hdrs


# ---------------------------------------------------------------------------
# SecurityHeadersMiddleware
# ---------------------------------------------------------------------------

class TestSecurityHeadersMiddleware:
    """Tests for the SecurityHeadersMiddleware ASGI middleware."""

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self) -> None:
        """Non-HTTP scopes (e.g. lifespan) pass through without modification."""
        inner_app = AsyncMock()
        middleware = SecurityHeadersMiddleware(inner_app)

        scope: dict = {"type": "lifespan"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # Inner app should be called with the original send
        inner_app.assert_awaited_once()
        call_scope, call_receive, call_send = inner_app.await_args.args
        assert call_scope == scope
        # The send function should be the original (not wrapped)
        assert call_send is send

    @pytest.mark.asyncio
    async def test_http_scope_injects_headers(self) -> None:
        """HTTP scopes get security headers injected on response start."""
        async def simulate_app(_scope, _receive, send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = SecurityHeadersMiddleware(simulate_app, config=SecurityHeadersConfig())
        scope = _make_scope(path="/api/test")
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        assert send.await_count >= 1
        first_call = send.await_args_list[0].args[0]
        assert first_call["type"] == "http.response.start"
        hdrs = _headers_to_dict(first_call["headers"])
        assert "x-content-type-options" in hdrs

    @pytest.mark.asyncio
    async def test_headers_injected_only_once(self) -> None:
        """Headers are injected only on the first response.start message."""
        async def simulate_app(_scope, _receive, send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = SecurityHeadersMiddleware(simulate_app, config=SecurityHeadersConfig())
        scope = _make_scope(path="/api/test")
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        first = send.await_args_list[0].args[0]
        hdrs1 = _headers_to_dict(first["headers"])
        assert "x-content-type-options" in hdrs1

        second = send.await_args_list[1].args[0]
        hdrs2 = _headers_to_dict(second["headers"])
        assert "x-content-type-options" not in hdrs2


# ---------------------------------------------------------------------------
# setup_security_headers
# ---------------------------------------------------------------------------

class TestSetupSecurityHeaders:
    """Tests for the setup_security_headers convenience function."""

    def test_adds_middleware_to_fastapi_app(self) -> None:
        """setup_security_headers adds SecurityHeadersMiddleware to a FastAPI app."""
        from fastapi import FastAPI

        mock_app = MagicMock(spec=FastAPI)
        mock_app.add_middleware = MagicMock()

        setup_security_headers(mock_app)

        mock_app.add_middleware.assert_called_once()
        call_args = mock_app.add_middleware.call_args
        assert call_args.args[0] is SecurityHeadersMiddleware

    def test_raises_type_error_for_non_fastapi(self) -> None:
        """setup_security_headers raises TypeError for non-FastAPI apps."""
        with pytest.raises(TypeError, match="Expected FastAPI app"):
            setup_security_headers("not-an-app")  # type: ignore[arg-type]
