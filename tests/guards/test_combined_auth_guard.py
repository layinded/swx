# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for the Combined Auth Guard (JWT + API key fallback)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette import status

from swx_core.guards.base import AuthenticatedUser
from swx_core.guards.combined_auth_guard import (
    _get_authenticated_user,
    _get_authenticated_user_optional,
)


def _make_user(**overrides) -> AuthenticatedUser:
    """Helper to create an AuthenticatedUser with defaults."""
    defaults = {
        "id": "user-1",
        "email": "user@example.com",
        "type": "user",
        "roles": ["user"],
        "permissions": ["read"],
        "is_superuser": False,
        "is_active": True,
        "metadata": {},
    }
    defaults.update(overrides)
    return AuthenticatedUser(**defaults)


class TestGetAuthenticatedUser:
    """Tests for the _get_authenticated_user FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_jwt_success_returns_user_with_auth_mode_jwt(self):
        """When JWT guard succeeds, returns user with auth_mode='jwt'."""
        request = MagicMock()
        manager = AsyncMock()
        jwt_user = _make_user(id="jwt-user", email="jwt@example.com")
        manager.authenticate = AsyncMock(return_value=jwt_user)

        result = await _get_authenticated_user(request, manager)

        assert result.id == "jwt-user"
        assert result.metadata["auth_mode"] == "jwt"
        manager.authenticate.assert_called_once_with(request, guard="jwt")

    @pytest.mark.asyncio
    async def test_jwt_failure_api_key_success_returns_user_with_auth_mode_api_key(self):
        """When JWT fails but API key succeeds, returns user with auth_mode='api_key'."""
        request = MagicMock()
        manager = AsyncMock()
        api_user = _make_user(id="api-user", email="api@example.com")
        manager.authenticate = AsyncMock(side_effect=[None, api_user])

        result = await _get_authenticated_user(request, manager)

        assert result.id == "api-user"
        assert result.metadata["auth_mode"] == "api_key"
        assert manager.authenticate.call_count == 2

    @pytest.mark.asyncio
    async def test_both_fail_raises_401(self):
        """When both JWT and API key fail, raises 401."""
        request = MagicMock()
        manager = AsyncMock()
        manager.authenticate = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await _get_authenticated_user(request, manager)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authentication required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_jwt_success_does_not_try_api_key(self):
        """When JWT succeeds, API key guard is not called."""
        request = MagicMock()
        manager = AsyncMock()
        jwt_user = _make_user(id="jwt-user")
        manager.authenticate = AsyncMock(return_value=jwt_user)

        await _get_authenticated_user(request, manager)

        # Should only be called once (for JWT)
        manager.authenticate.assert_called_once_with(request, guard="jwt")

    @pytest.mark.asyncio
    async def test_metadata_preserved_on_jwt_user(self):
        """Existing metadata on JWT user is preserved when auth_mode is added."""
        request = MagicMock()
        manager = AsyncMock()
        jwt_user = _make_user(
            id="jwt-user",
            metadata={"tenant_id": "t-1", "team_id": "team-1"},
        )
        manager.authenticate = AsyncMock(return_value=jwt_user)

        result = await _get_authenticated_user(request, manager)

        assert result.metadata["auth_mode"] == "jwt"
        assert result.metadata["tenant_id"] == "t-1"
        assert result.metadata["team_id"] == "team-1"

    @pytest.mark.asyncio
    async def test_metadata_preserved_on_api_key_user(self):
        """Existing metadata on API key user is preserved when auth_mode is added."""
        request = MagicMock()
        manager = AsyncMock()
        api_user = _make_user(
            id="api-user",
            metadata={"key_id": "key-123"},
        )
        manager.authenticate = AsyncMock(side_effect=[None, api_user])

        result = await _get_authenticated_user(request, manager)

        assert result.metadata["auth_mode"] == "api_key"
        assert result.metadata["key_id"] == "key-123"


class TestGetAuthenticatedUserOptional:
    """Tests for the _get_authenticated_user_optional FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_jwt_success_returns_user(self):
        """Optional variant returns user when JWT succeeds."""
        request = MagicMock()
        manager = AsyncMock()
        jwt_user = _make_user(id="jwt-user")
        manager.authenticate = AsyncMock(return_value=jwt_user)

        result = await _get_authenticated_user_optional(request, manager)

        assert result is not None
        assert result.id == "jwt-user"
        assert result.metadata["auth_mode"] == "jwt"

    @pytest.mark.asyncio
    async def test_api_key_success_returns_user(self):
        """Optional variant returns user when API key succeeds after JWT fails."""
        request = MagicMock()
        manager = AsyncMock()
        api_user = _make_user(id="api-user")
        manager.authenticate = AsyncMock(side_effect=[None, api_user])

        result = await _get_authenticated_user_optional(request, manager)

        assert result is not None
        assert result.id == "api-user"
        assert result.metadata["auth_mode"] == "api_key"

    @pytest.mark.asyncio
    async def test_both_fail_returns_none(self):
        """Optional variant returns None when both guards fail."""
        request = MagicMock()
        manager = AsyncMock()
        manager.authenticate = AsyncMock(return_value=None)

        result = await _get_authenticated_user_optional(request, manager)

        assert result is None

    @pytest.mark.asyncio
    async def test_optional_does_not_raise_on_failure(self):
        """Optional variant never raises HTTPException."""
        request = MagicMock()
        manager = AsyncMock()
        manager.authenticate = AsyncMock(return_value=None)

        # Should not raise
        result = await _get_authenticated_user_optional(request, manager)
        assert result is None
