# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for the Region Routing Middleware."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.middleware.region_routing import (
    RegionRoutingConfig,
    RegionRoutingMiddleware,
    _resolve_country,
    _load_regions_from_env,
    apply_middleware,
    resolve_region,
)


class TestResolveRegion:
    """Tests for the resolve_region function."""

    def test_maps_country_to_region(self):
        """Country code is mapped to the correct region."""
        regions = {"eu": ["DE", "FR", "NL"], "us": ["US", "CA", "MX"]}
        assert resolve_region("DE", regions) == "eu"
        assert resolve_region("FR", regions) == "eu"
        assert resolve_region("US", regions) == "us"
        assert resolve_region("CA", regions) == "us"

    def test_unknown_country_returns_none(self):
        """Country not in any region returns None."""
        regions = {"eu": ["DE", "FR"], "us": ["US", "CA"]}
        assert resolve_region("JP", regions) is None
        assert resolve_region("AU", regions) is None

    def test_none_country_returns_none(self):
        """None country returns None."""
        regions = {"eu": ["DE", "FR"]}
        assert resolve_region(None, regions) is None

    def test_empty_country_returns_none(self):
        """Empty string country returns None."""
        regions = {"eu": ["DE", "FR"]}
        assert resolve_region("", regions) is None

    def test_empty_regions_returns_none(self):
        """Empty regions dict returns None for any country."""
        assert resolve_region("DE", {}) is None

    def test_case_sensitive_matching(self):
        """Country matching is case-sensitive (upper case expected)."""
        regions = {"eu": ["DE", "FR"]}
        assert resolve_region("de", regions) is None  # Lowercase not matched
        assert resolve_region("DE", regions) == "eu"


class TestResolveCountry:
    """Tests for the _resolve_country helper."""

    def test_extracts_from_cf_ipcountry_header(self):
        """Country code is extracted from CF-IPCountry header."""
        scope = {
            "type": "http",
            "headers": [
                (b"cf-ipcountry", b"DE"),
                (b"host", b"example.com"),
            ],
        }
        result = _resolve_country(scope, "CF-IPCountry")
        assert result == "DE"

    def test_extracts_from_x_forwarded_for(self):
        """Country code can be extracted from custom headers."""
        scope = {
            "type": "http",
            "headers": [
                (b"x-custom-country", b"US"),
            ],
        }
        result = _resolve_country(scope, "X-Custom-Country")
        assert result == "US"

    def test_no_matching_header_returns_none(self):
        """When the header is not present, returns None."""
        scope = {
            "type": "http",
            "headers": [
                (b"host", b"example.com"),
            ],
        }
        result = _resolve_country(scope, "CF-IPCountry")
        assert result is None

    def test_no_headers_returns_none(self):
        """When scope has no headers, returns None."""
        scope = {"type": "http"}
        result = _resolve_country(scope, "CF-IPCountry")
        assert result is None

    def test_empty_header_value_returns_none(self):
        """Empty header value returns None."""
        scope = {
            "type": "http",
            "headers": [
                (b"cf-ipcountry", b""),
            ],
        }
        result = _resolve_country(scope, "CF-IPCountry")
        assert result is None

    def test_strips_and_uppercases_value(self):
        """Header value is stripped and uppercased."""
        scope = {
            "type": "http",
            "headers": [
                (b"cf-ipcountry", b"  de  "),
            ],
        }
        result = _resolve_country(scope, "CF-IPCountry")
        assert result == "DE"


class TestRegionRoutingConfig:
    """Tests for the RegionRoutingConfig dataclass."""

    def test_defaults(self):
        """Default config has empty regions and CF-IPCountry header."""
        config = RegionRoutingConfig()
        assert config.regions == {}
        assert config.header_name == "CF-IPCountry"

    def test_custom_config(self):
        """Custom config stores regions and header name."""
        config = RegionRoutingConfig(
            regions={"eu": ["DE", "FR"]},
            header_name="X-Custom-Country",
        )
        assert config.regions == {"eu": ["DE", "FR"]}
        assert config.header_name == "X-Custom-Country"


class TestRegionRoutingMiddleware:
    """Tests for the RegionRoutingMiddleware ASGI middleware."""

    @pytest.mark.asyncio
    async def test_no_regions_configured_passes_through(self):
        """When no regions are configured, middleware is a no-op."""
        app = AsyncMock()
        config = RegionRoutingConfig(regions={})
        middleware = RegionRoutingMiddleware(app, config)

        scope: dict = {"type": "http", "headers": [(b"cf-ipcountry", b"DE")]}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self):
        """Non-HTTP scopes pass through without modification."""
        app = AsyncMock()
        config = RegionRoutingConfig(regions={"eu": ["DE"]})
        middleware = RegionRoutingMiddleware(app, config)

        scope: dict = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_resolves_region_and_stores_on_state(self):
        """Region is resolved and stored on request.state.region."""
        app = AsyncMock()
        config = RegionRoutingConfig(regions={"eu": ["DE", "FR"]})
        middleware = RegionRoutingMiddleware(app, config)

        scope: dict = {
            "type": "http",
            "headers": [(b"cf-ipcountry", b"DE")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # Check that state.region was set
        state = scope.get("state")
        assert state is not None
        assert state.region == "eu"

    @pytest.mark.asyncio
    async def test_unknown_country_stores_none_region(self):
        """When country is not in any region, state.region is None."""
        app = AsyncMock()
        config = RegionRoutingConfig(regions={"eu": ["DE", "FR"]})
        middleware = RegionRoutingMiddleware(app, config)

        scope: dict = {
            "type": "http",
            "headers": [(b"cf-ipcountry", b"JP")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        state = scope.get("state")
        assert state is not None
        assert state.region is None

    @pytest.mark.asyncio
    async def test_no_country_header_stores_none_region(self):
        """When country header is missing, state.region is None."""
        app = AsyncMock()
        config = RegionRoutingConfig(regions={"eu": ["DE"]})
        middleware = RegionRoutingMiddleware(app, config)

        scope: dict = {"type": "http", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        state = scope.get("state")
        assert state is not None
        assert state.region is None

    @pytest.mark.asyncio
    async def test_custom_header_name(self):
        """Custom header name is used for country resolution."""
        app = AsyncMock()
        config = RegionRoutingConfig(
            regions={"us": ["US", "CA"]},
            header_name="X-Custom-Country",
        )
        middleware = RegionRoutingMiddleware(app, config)

        scope: dict = {
            "type": "http",
            "headers": [(b"x-custom-country", b"US")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        state = scope.get("state")
        assert state.region == "us"


class TestLoadRegionsFromEnv:
    """Tests for the _load_regions_from_env function."""

    def test_loads_valid_json(self):
        """Valid JSON is parsed into regions dict."""
        with patch.dict(os.environ, {"SWX_REGIONS": '{"eu": ["DE", "FR"], "us": ["US"]}'}):
            result = _load_regions_from_env()
        assert result == {"eu": ["DE", "FR"], "us": ["US"]}

    def test_empty_env_returns_empty_dict(self):
        """Empty or missing env var returns empty dict."""
        with patch.dict(os.environ, {}, clear=True):
            result = _load_regions_from_env()
        assert result == {}

    def test_invalid_json_returns_empty_dict(self):
        """Invalid JSON returns empty dict."""
        with patch.dict(os.environ, {"SWX_REGIONS": "not valid json"}):
            result = _load_regions_from_env()
        assert result == {}

    def test_non_dict_json_returns_empty_dict(self):
        """JSON that is not a dict returns empty dict."""
        with patch.dict(os.environ, {"SWX_REGIONS": '["eu", "us"]'}):
            result = _load_regions_from_env()
        assert result == {}

    def test_filters_non_list_values(self):
        """Region values that are not lists are filtered out."""
        with patch.dict(os.environ, {"SWX_REGIONS": '{"eu": ["DE"], "bad": "not-a-list"}'}):
            result = _load_regions_from_env()
        assert "eu" in result
        assert "bad" not in result


class TestApplyMiddleware:
    """Tests for apply_middleware registration on FastAPI app."""

    def test_apply_middleware_registers_on_fastapi_app(self):
        """apply_middleware calls app.add_middleware with RegionRoutingMiddleware."""
        from fastapi import FastAPI

        mock_app = MagicMock(spec=FastAPI)
        with patch.dict(os.environ, {"SWX_REGIONS": '{"eu": ["DE"]}'}):
            apply_middleware(mock_app)

        mock_app.add_middleware.assert_called_once()
        args, kwargs = mock_app.add_middleware.call_args
        assert args[0] == RegionRoutingMiddleware

    def test_apply_middleware_raises_for_non_fastapi(self):
        """apply_middleware raises TypeError for non-FastAPI apps."""
        mock_app = MagicMock()
        mock_app.__class__.__name__ = "Starlette"

        with pytest.raises(TypeError, match="Expected FastAPI app"):
            apply_middleware(mock_app)
