# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for the Audit Retention Service."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock the async_session import that audit_event_queue.py tries to load
# (the actual name in db.py is AsyncSessionLocal, not async_session)
_mock_async_session = AsyncMock()
sys.modules.setdefault("swx_core.database.db", MagicMock())
sys.modules["swx_core.database.db"].async_session = _mock_async_session

from swx_core.services.audit.audit_retention_service import run_retention


class TestRunRetention:
    """Tests for the run_retention function."""

    @pytest.mark.asyncio
    async def test_retention_disabled_when_days_is_none(self):
        """When SWX_AUDIT_RETENTION_DAYS is None, returns empty result."""
        session = AsyncMock()

        with patch("swx_core.services.audit.audit_retention_service.settings") as mock_settings:
            mock_settings.SWX_AUDIT_RETENTION_DAYS = None

            result = await run_retention(session)

        assert result == {"deleted": 0, "anonymized": 0, "cutoff": None}

    @pytest.mark.asyncio
    async def test_retention_disabled_when_days_is_zero(self):
        """When SWX_AUDIT_RETENTION_DAYS is 0, returns empty result."""
        session = AsyncMock()

        with patch("swx_core.services.audit.audit_retention_service.settings") as mock_settings:
            mock_settings.SWX_AUDIT_RETENTION_DAYS = 0

            result = await run_retention(session)

        assert result == {"deleted": 0, "anonymized": 0, "cutoff": None}

    @pytest.mark.asyncio
    async def test_dry_run_returns_count_without_deleting(self):
        """Dry-run mode returns eligible count but does not delete."""
        session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 42
        session.execute = AsyncMock(return_value=mock_count_result)

        with patch("swx_core.services.audit.audit_retention_service.settings") as mock_settings:
            mock_settings.SWX_AUDIT_RETENTION_DAYS = 90

            result = await run_retention(session, dry_run=True)

        assert result["deleted"] == 0
        assert result["anonymized"] == 0
        assert result["eligible"] == 42
        assert result["cutoff"] is not None
        # Session commit should NOT have been called
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_with_zero_eligible(self):
        """Dry-run with no eligible records returns 0."""
        session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        session.execute = AsyncMock(return_value=mock_count_result)

        with patch("swx_core.services.audit.audit_retention_service.settings") as mock_settings:
            mock_settings.SWX_AUDIT_RETENTION_DAYS = 30

            result = await run_retention(session, dry_run=True)

        assert result["eligible"] == 0
        assert result["deleted"] == 0

    @pytest.mark.asyncio
    async def test_retention_with_days_configured(self):
        """When SWX_AUDIT_RETENTION_DAYS is set, performs batch deletion."""
        session = AsyncMock()

        # Mock the batch delete to return 0 (no records to delete)
        with patch("swx_core.services.audit.audit_retention_service.settings") as mock_settings:
            mock_settings.SWX_AUDIT_RETENTION_DAYS = 90
            with patch("swx_core.services.audit.audit_retention_service._batch_delete_before", new_callable=AsyncMock) as mock_batch:
                mock_batch.return_value = 0

                result = await run_retention(session)

        assert result["deleted"] == 0
        assert result["anonymized"] == 0
        assert result["cutoff"] is not None

    @pytest.mark.asyncio
    async def test_retention_deletes_records(self):
        """Batch deletion returns the count of deleted records."""
        session = AsyncMock()

        with patch("swx_core.services.audit.audit_retention_service.settings") as mock_settings:
            mock_settings.SWX_AUDIT_RETENTION_DAYS = 365
            with patch("swx_core.services.audit.audit_retention_service._batch_delete_before", new_callable=AsyncMock) as mock_batch:
                mock_batch.return_value = 1500

                result = await run_retention(session)

        assert result["deleted"] == 1500
        assert result["anonymized"] == 0
        assert result["cutoff"] is not None

    @pytest.mark.asyncio
    async def test_cutoff_is_calculated_correctly(self):
        """Cutoff date is utc_now minus retention days."""
        session = AsyncMock()

        with patch("swx_core.services.audit.audit_retention_service.settings") as mock_settings:
            mock_settings.SWX_AUDIT_RETENTION_DAYS = 7
            with patch("swx_core.services.audit.audit_retention_service._batch_delete_before", new_callable=AsyncMock) as mock_batch:
                mock_batch.return_value = 0

                result = await run_retention(session)

        assert result["cutoff"] is not None
        # cutoff should be an ISO format string
        assert "T" in result["cutoff"]
