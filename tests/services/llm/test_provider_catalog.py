# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for the LLM Provider Catalog."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.services.llm.provider_catalog import (
    get_provider_catalog,
    invalidate_catalog_cache,
    _read_catalog_from_db,
)


class TestGetProviderCatalog:
    """Tests for the get_provider_catalog function."""

    @pytest.mark.asyncio
    async def test_returns_static_defaults_when_no_redis_no_db(self):
        """When Redis and DB are unavailable, returns static defaults."""
        with patch("swx_core.services.llm.provider_catalog.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)  # Cache miss
            mock_cache.set = AsyncMock()
            mock_get_cache.return_value = mock_cache

            result = await get_provider_catalog(session=None)

        assert isinstance(result, list)
        assert len(result) > 0
        # Each provider should have expected keys
        for provider in result:
            assert "name" in provider or "provider" in provider

    @pytest.mark.asyncio
    async def test_redis_cache_hit_returns_cached(self):
        """When Redis has cached data, it is returned without DB query."""
        cached_data = [{"name": "openai", "models": ["gpt-4o"]}]

        with patch("swx_core.services.llm.provider_catalog.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=cached_data)
            mock_get_cache.return_value = mock_cache

            result = await get_provider_catalog(session=AsyncMock())

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_redis_cache_miss_falls_back_to_db(self):
        """When Redis misses, DB is queried and result is cached."""
        db_catalog = [{"name": "anthropic", "models": ["claude-3"]}]

        with patch("swx_core.services.llm.provider_catalog.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)  # Cache miss
            mock_cache.set = AsyncMock()
            mock_get_cache.return_value = mock_cache

            with patch("swx_core.services.llm.provider_catalog._read_catalog_from_db", new_callable=AsyncMock) as mock_read:
                mock_read.return_value = db_catalog

                result = await get_provider_catalog(session=AsyncMock())

        assert result == db_catalog
        # Result should be cached
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_error_falls_back_to_static_defaults(self):
        """When DB query fails, static defaults are returned."""
        with patch("swx_core.services.llm.provider_catalog.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)  # Cache miss
            mock_cache.set = AsyncMock()
            mock_get_cache.return_value = mock_cache

            with patch("swx_core.services.llm.provider_catalog._read_catalog_from_db", new_callable=AsyncMock) as mock_read:
                mock_read.side_effect = Exception("DB connection error")

                result = await get_provider_catalog(session=AsyncMock())

        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_cache_set_error_is_handled_gracefully(self):
        """When caching fails, the result is still returned."""
        db_catalog = [{"name": "openai", "models": ["gpt-4o"]}]

        with patch("swx_core.services.llm.provider_catalog.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(side_effect=Exception("Redis write error"))
            mock_get_cache.return_value = mock_cache

            with patch("swx_core.services.llm.provider_catalog._read_catalog_from_db", new_callable=AsyncMock) as mock_read:
                mock_read.return_value = db_catalog

                result = await get_provider_catalog(session=AsyncMock())

        # Should still return the DB result even though caching failed
        assert result == db_catalog

    @pytest.mark.asyncio
    async def test_no_session_skips_db(self):
        """When session is None, DB is skipped entirely."""
        with patch("swx_core.services.llm.provider_catalog.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_get_cache.return_value = mock_cache

            result = await get_provider_catalog(session=None)

        assert isinstance(result, list)


class TestReadCatalogFromDb:
    """Tests for the _read_catalog_from_db helper."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_config(self):
        """Returns None when no SystemConfig entry exists."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await _read_catalog_from_db(session)

        assert result is None

    @pytest.mark.asyncio
    async def test_parses_json_string_value(self):
        """Parses JSON string value from SystemConfig."""
        session = AsyncMock()
        mock_config = MagicMock()
        mock_config.value = '[{"name": "openai", "models": ["gpt-4o"]}]'
        mock_config.is_active = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        session.execute = AsyncMock(return_value=mock_result)

        result = await _read_catalog_from_db(session)

        assert result == [{"name": "openai", "models": ["gpt-4o"]}]

    @pytest.mark.asyncio
    async def test_handles_invalid_json_gracefully(self):
        """Returns None for invalid JSON in SystemConfig value."""
        session = AsyncMock()
        mock_config = MagicMock()
        mock_config.value = "not valid json {{{"
        mock_config.is_active = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        session.execute = AsyncMock(return_value=mock_result)

        result = await _read_catalog_from_db(session)

        assert result is None

    @pytest.mark.asyncio
    async def test_handles_dict_with_providers_key(self):
        """Extracts providers list from dict with 'providers' key."""
        session = AsyncMock()
        mock_config = MagicMock()
        mock_config.value = {"providers": [{"name": "openai"}]}
        mock_config.is_active = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        session.execute = AsyncMock(return_value=mock_result)

        result = await _read_catalog_from_db(session)

        assert result == [{"name": "openai"}]

    @pytest.mark.asyncio
    async def test_returns_none_for_unexpected_value_type(self):
        """Returns None when value is not a list, string, or dict with providers."""
        session = AsyncMock()
        mock_config = MagicMock()
        mock_config.value = 42  # Unexpected type
        mock_config.is_active = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        session.execute = AsyncMock(return_value=mock_result)

        result = await _read_catalog_from_db(session)

        assert result is None


class TestInvalidateCatalogCache:
    """Tests for the invalidate_catalog_cache function."""

    @pytest.mark.asyncio
    async def test_invalidate_deletes_cache_key(self):
        """invalidate_catalog_cache deletes the catalog cache key."""
        with patch("swx_core.services.llm.provider_catalog.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.delete = AsyncMock()
            mock_get_cache.return_value = mock_cache

            await invalidate_catalog_cache()

        mock_cache.delete.assert_called_once_with("llm:provider_catalog")

    @pytest.mark.asyncio
    async def test_invalidate_handles_redis_error(self):
        """invalidate_catalog_cache handles Redis errors gracefully."""
        with patch("swx_core.services.llm.provider_catalog.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.delete = AsyncMock(side_effect=Exception("Redis down"))
            mock_get_cache.return_value = mock_cache

            # Should not raise
            await invalidate_catalog_cache()
