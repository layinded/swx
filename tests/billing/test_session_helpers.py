"""Unit tests for session helpers (swx_core.database.session_helpers).

Tests that with_read_session yields an AsyncSession and closes it properly.
Uses a mock AsyncSessionLocal to avoid requiring a real database.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.database.session_helpers import with_read_session


class TestWithReadSession:
    @pytest.mark.asyncio
    async def test_yields_session(self):
        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("swx_core.database.session_helpers.AsyncSessionLocal") as mock_factory:
            mock_factory.return_value = mock_cm
            async with with_read_session() as session:
                assert session is mock_session

    @pytest.mark.asyncio
    async def test_closes_session_on_exit(self):
        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("swx_core.database.session_helpers.AsyncSessionLocal") as mock_factory:
            mock_factory.return_value = mock_cm
            async with with_read_session():
                pass
            mock_cm.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_propagates_errors(self):
        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("swx_core.database.session_helpers.AsyncSessionLocal") as mock_factory:
            mock_factory.return_value = mock_cm
            with pytest.raises(ValueError, match="test error"):
                async with with_read_session():
                    raise ValueError("test error")
            mock_cm.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_available_inside_context(self):
        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("swx_core.database.session_helpers.AsyncSessionLocal") as mock_factory:
            mock_factory.return_value = mock_cm
            async with with_read_session() as session:
                assert session is not None
                assert session is mock_session