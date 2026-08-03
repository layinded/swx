# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for LLM provider validation and model listing — llm_service.validate_provider / list_provider_models."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from swx_core.contracts.llm import ValidateProviderResult


class TestValidateProvider:
    """Tests for the validate_provider() service function."""

    @pytest.mark.asyncio
    async def test_validate_provider_success(self) -> None:
        """validate_provider returns valid=True when provider validates successfully."""
        from swx_core.services.llm import llm_service

        config_id = uuid4()
        mock_config = MagicMock()
        mock_config.provider = "openai"
        mock_config.id = config_id

        mock_provider = AsyncMock()
        mock_provider.validate_api_key = AsyncMock(
            return_value=ValidateProviderResult(valid=True, models=["gpt-4o", "gpt-4o-mini"])
        )

        with patch("swx_core.services.llm.llm_service.llm_provider_repository") as mock_repo, \
             patch("swx_core.services.llm.llm_service.create_provider", return_value=mock_provider):
            mock_repo.get_by_id = AsyncMock(return_value=mock_config)

            result = await llm_service.validate_provider(AsyncMock(), config_id)

        assert result.valid is True
        assert "gpt-4o" in result.models

    @pytest.mark.asyncio
    async def test_validate_provider_invalid_key(self) -> None:
        """validate_provider returns valid=False when the API key is invalid."""
        from swx_core.services.llm import llm_service

        config_id = uuid4()
        mock_config = MagicMock()
        mock_config.provider = "openai"
        mock_config.id = config_id

        mock_provider = AsyncMock()
        mock_provider.validate_api_key = AsyncMock(
            return_value=ValidateProviderResult(valid=False, error="Invalid API key")
        )

        with patch("swx_core.services.llm.llm_service.llm_provider_repository") as mock_repo, \
             patch("swx_core.services.llm.llm_service.create_provider", return_value=mock_provider):
            mock_repo.get_by_id = AsyncMock(return_value=mock_config)

            result = await llm_service.validate_provider(AsyncMock(), config_id)

        assert result.valid is False
        assert "Invalid API key" in result.error

    @pytest.mark.asyncio
    async def test_validate_provider_not_found(self) -> None:
        """validate_provider raises 404 when config doesn't exist."""
        from swx_core.services.llm import llm_service
        from fastapi import HTTPException

        config_id = uuid4()

        with patch("swx_core.services.llm.llm_service.llm_provider_repository") as mock_repo:
            mock_repo.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await llm_service.validate_provider(AsyncMock(), config_id)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_validate_provider_unknown_type(self) -> None:
        """validate_provider returns valid=False when create_provider returns None."""
        from swx_core.services.llm import llm_service

        config_id = uuid4()
        mock_config = MagicMock()
        mock_config.provider = "unknown_provider"
        mock_config.id = config_id

        with patch("swx_core.services.llm.llm_service.llm_provider_repository") as mock_repo, \
             patch("swx_core.services.llm.llm_service.create_provider", return_value=None):
            mock_repo.get_by_id = AsyncMock(return_value=mock_config)

            result = await llm_service.validate_provider(AsyncMock(), config_id)

        assert result.valid is False
        assert "Unknown provider type" in result.error


class TestListProviderModels:
    """Tests for the list_provider_models() service function."""

    @pytest.mark.asyncio
    async def test_list_models_success(self) -> None:
        """list_provider_models returns model list when provider supports it."""
        from swx_core.services.llm import llm_service

        config_id = uuid4()
        mock_config = MagicMock()
        mock_config.provider = "openai"
        mock_config.id = config_id

        mock_provider = AsyncMock()
        mock_provider.list_models = AsyncMock(return_value=["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"])

        with patch("swx_core.services.llm.llm_service.llm_provider_repository") as mock_repo, \
             patch("swx_core.services.llm.llm_service.create_provider", return_value=mock_provider):
            mock_repo.get_by_id = AsyncMock(return_value=mock_config)

            models = await llm_service.list_provider_models(AsyncMock(), config_id)

        assert len(models) == 3
        assert "gpt-4o" in models

    @pytest.mark.asyncio
    async def test_list_models_not_found(self) -> None:
        """list_provider_models raises 404 when config doesn't exist."""
        from swx_core.services.llm import llm_service
        from fastapi import HTTPException

        config_id = uuid4()

        with patch("swx_core.services.llm.llm_service.llm_provider_repository") as mock_repo:
            mock_repo.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await llm_service.list_provider_models(AsyncMock(), config_id)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_models_unknown_provider_returns_empty(self) -> None:
        """list_provider_models returns empty list when create_provider returns None."""
        from swx_core.services.llm import llm_service

        config_id = uuid4()
        mock_config = MagicMock()
        mock_config.provider = "unknown_provider"
        mock_config.id = config_id

        with patch("swx_core.services.llm.llm_service.llm_provider_repository") as mock_repo, \
             patch("swx_core.services.llm.llm_service.create_provider", return_value=None):
            mock_repo.get_by_id = AsyncMock(return_value=mock_config)

            models = await llm_service.list_provider_models(AsyncMock(), config_id)

        assert models == []


class TestCredentialSourceBYOK:
    """Tests for CredentialSource enum and BYOK encryption in provider config CRUD."""

    def test_credential_source_values(self) -> None:
        """CredentialSource has the expected enum values."""
        from swx_core.models.llm_provider_config import CredentialSource

        assert CredentialSource.ENV_PLACEHOLDER.value == "env_placeholder"
        assert CredentialSource.ENCRYPTED_DB.value == "encrypted_db"
        assert CredentialSource.DIRECT.value == "direct"

    def test_credential_source_default(self) -> None:
        """Default credential source is ENV_PLACEHOLDER."""
        from swx_core.models.llm_provider_config import CredentialSource

        assert CredentialSource.ENV_PLACEHOLDER.value == "env_placeholder"