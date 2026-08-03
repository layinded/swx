# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for the Service Token Guard."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette import status

from swx_core.guards.service_token_guard import (
    ServicePrincipal,
    _get_service_principal,
)


class TestServicePrincipal:
    """Tests for the ServicePrincipal dataclass."""

    def test_default_service_name(self):
        """ServicePrincipal defaults service_name when not provided."""
        principal = ServicePrincipal(service_name="my-service")
        assert principal.service_name == "my-service"
        assert principal.scopes == []

    def test_with_scopes(self):
        """ServicePrincipal stores scopes from SWX_SERVICE_TOKEN_SCOPES."""
        principal = ServicePrincipal(
            service_name="worker",
            scopes=["read", "write"],
        )
        assert principal.scopes == ["read", "write"]

    def test_to_authenticated_user_conversion(self):
        """to_authenticated_user() returns a valid AuthenticatedUser."""
        principal = ServicePrincipal(
            service_name="worker",
            scopes=["read", "write"],
        )
        user = principal.to_authenticated_user()

        assert user.id == "svc:worker"
        assert user.email == "worker@service.internal"
        assert user.type == "service"
        assert user.roles == ["service"]
        assert user.permissions == ["read", "write"]
        assert user.is_superuser is False
        assert user.is_active is True
        assert user.metadata == {"service_name": "worker"}

    def test_to_authenticated_user_without_scopes(self):
        """to_authenticated_user() works with empty scopes."""
        principal = ServicePrincipal(service_name="cron")
        user = principal.to_authenticated_user()

        assert user.id == "svc:cron"
        assert user.permissions == []


class TestGetServicePrincipal:
    """Tests for the _get_service_principal FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_service_principal(self):
        """Valid X-Service-Token header returns a ServicePrincipal."""
        request = MagicMock()
        request.headers = {
            "X-Service-Token": "secret-token",
            "X-Service-Name": "worker",
        }

        with patch("swx_core.guards.service_token_guard.settings") as mock_settings:
            mock_settings.SWX_SERVICE_TOKEN = "secret-token"
            mock_settings.SWX_SERVICE_TOKEN_SCOPES = "read,write"

            result = await _get_service_principal(request)

        assert isinstance(result, ServicePrincipal)
        assert result.service_name == "worker"
        assert result.scopes == ["read", "write"]

    @pytest.mark.asyncio
    async def test_missing_header_raises_401(self):
        """Missing X-Service-Token header raises 401."""
        request = MagicMock()
        request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            await _get_service_principal(request)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing X-Service-Token header" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        """Invalid X-Service-Token header raises 401."""
        request = MagicMock()
        request.headers = {"X-Service-Token": "wrong-token"}

        with patch("swx_core.guards.service_token_guard.settings") as mock_settings:
            mock_settings.SWX_SERVICE_TOKEN = "correct-token"

            with pytest.raises(HTTPException) as exc_info:
                await _get_service_principal(request)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid service token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_not_configured_raises_403(self):
        """When SWX_SERVICE_TOKEN is not configured, raises 403."""
        request = MagicMock()
        request.headers = {"X-Service-Token": "any-token"}

        with patch("swx_core.guards.service_token_guard.settings") as mock_settings:
            mock_settings.SWX_SERVICE_TOKEN = None

            with pytest.raises(HTTPException) as exc_info:
                await _get_service_principal(request)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_x_service_name_header_extraction(self):
        """X-Service-Name header is extracted for service_name."""
        request = MagicMock()
        request.headers = {
            "X-Service-Token": "secret",
            "X-Service-Name": "my-custom-service",
        }

        with patch("swx_core.guards.service_token_guard.settings") as mock_settings:
            mock_settings.SWX_SERVICE_TOKEN = "secret"
            mock_settings.SWX_SERVICE_TOKEN_SCOPES = None

            result = await _get_service_principal(request)

        assert result.service_name == "my-custom-service"

    @pytest.mark.asyncio
    async def test_missing_x_service_name_defaults_to_service(self):
        """When X-Service-Name is missing, defaults to 'service'."""
        request = MagicMock()
        request.headers = {"X-Service-Token": "secret"}

        with patch("swx_core.guards.service_token_guard.settings") as mock_settings:
            mock_settings.SWX_SERVICE_TOKEN = "secret"
            mock_settings.SWX_SERVICE_TOKEN_SCOPES = None

            result = await _get_service_principal(request)

        assert result.service_name == "service"

    @pytest.mark.asyncio
    async def test_scopes_from_setting(self):
        """Scopes are parsed from SWX_SERVICE_TOKEN_SCOPES comma-separated string."""
        request = MagicMock()
        request.headers = {"X-Service-Token": "secret"}

        with patch("swx_core.guards.service_token_guard.settings") as mock_settings:
            mock_settings.SWX_SERVICE_TOKEN = "secret"
            mock_settings.SWX_SERVICE_TOKEN_SCOPES = "admin, audit, billing"

            result = await _get_service_principal(request)

        assert result.scopes == ["admin", "audit", "billing"]

    @pytest.mark.asyncio
    async def test_empty_scopes_setting_returns_empty_list(self):
        """Empty SWX_SERVICE_TOKEN_SCOPES returns empty scopes list."""
        request = MagicMock()
        request.headers = {"X-Service-Token": "secret"}

        with patch("swx_core.guards.service_token_guard.settings") as mock_settings:
            mock_settings.SWX_SERVICE_TOKEN = "secret"
            mock_settings.SWX_SERVICE_TOKEN_SCOPES = ""

            result = await _get_service_principal(request)

        assert result.scopes == []

    @pytest.mark.asyncio
    async def test_scopes_with_whitespace_are_stripped(self):
        """Scopes with extra whitespace are properly stripped."""
        request = MagicMock()
        request.headers = {"X-Service-Token": "secret"}

        with patch("swx_core.guards.service_token_guard.settings") as mock_settings:
            mock_settings.SWX_SERVICE_TOKEN = "secret"
            mock_settings.SWX_SERVICE_TOKEN_SCOPES = " read , write , admin "

            result = await _get_service_principal(request)

        assert result.scopes == ["read", "write", "admin"]
