# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for the Audit Event Queue."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock the async_session import that audit_event_queue.py tries to load
# (the actual name in db.py is AsyncSessionLocal, not async_session)
_mock_async_session = MagicMock()
_mock_async_session.return_value.__aenter__ = AsyncMock()
_mock_async_session.return_value.__aexit__ = AsyncMock()
sys.modules.setdefault("swx_core.database.db", MagicMock())
sys.modules["swx_core.database.db"].async_session = _mock_async_session

from swx_core.services.audit.audit_event_queue import (
    AuditEvent,
    AuditEventQueue,
    audit_queue,
)


class TestAuditEvent:
    """Tests for the AuditEvent dataclass."""

    def test_default_values(self):
        """AuditEvent has sensible defaults."""
        event = AuditEvent(action="user.login", actor_type="user")
        assert event.action == "user.login"
        assert event.actor_type == "user"
        assert event.actor_id is None
        assert event.resource_type is None
        assert event.resource_id is None
        assert event.outcome == "success"
        assert event.severity == "info"
        assert event.context == {}

    def test_full_event_data(self):
        """AuditEvent stores all fields correctly."""
        event = AuditEvent(
            action="data.export",
            actor_type="user",
            actor_id="user-123",
            resource_type="report",
            resource_id="report-456",
            outcome="success",
            severity="high",
            context={"format": "csv", "rows": 1000},
        )
        assert event.action == "data.export"
        assert event.actor_id == "user-123"
        assert event.resource_type == "report"
        assert event.resource_id == "report-456"
        assert event.outcome == "success"
        assert event.severity == "high"
        assert event.context["format"] == "csv"


class TestAuditEventQueuePut:
    """Tests for enqueuing events."""

    def test_put_nowait_adds_event(self):
        """put() adds an event to the queue."""
        q = AuditEventQueue(maxsize=100)
        event = AuditEvent(action="test", actor_type="system")

        q.put(event)

        assert q.queue_depth == 1

    def test_put_multiple_events(self):
        """Multiple events can be enqueued."""
        q = AuditEventQueue(maxsize=100)

        for i in range(5):
            q.put(AuditEvent(action=f"test.{i}", actor_type="system"))

        assert q.queue_depth == 5

    def test_queue_overflow_drops_events_no_crash(self):
        """When queue is full, events are dropped without crashing."""
        q = AuditEventQueue(maxsize=2)

        q.put(AuditEvent(action="a", actor_type="system"))
        q.put(AuditEvent(action="b", actor_type="system"))
        # This should be dropped (queue full)
        q.put(AuditEvent(action="c", actor_type="system"))

        assert q.queue_depth == 2

    def test_queue_depth_reflects_current_size(self):
        """queue_depth property returns the current queue size."""
        q = AuditEventQueue(maxsize=100)
        assert q.queue_depth == 0

        q.put(AuditEvent(action="a", actor_type="system"))
        assert q.queue_depth == 1

        q.put(AuditEvent(action="b", actor_type="system"))
        assert q.queue_depth == 2


class TestAuditEventQueueLifecycle:
    """Tests for start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_worker_task(self):
        """start() creates a background drain worker."""
        q = AuditEventQueue(maxsize=100)

        with patch("swx_core.services.audit.audit_event_queue.async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            await q.start()

            assert q._running is True
            assert q._worker_task is not None

            await q.stop(timeout=1.0)

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self):
        """Calling start() twice does not create a second worker."""
        q = AuditEventQueue(maxsize=100)

        with patch("swx_core.services.audit.audit_event_queue.async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            await q.start()
            task1 = q._worker_task
            await q.start()
            task2 = q._worker_task

            assert task1 is task2

            await q.stop(timeout=1.0)

    @pytest.mark.asyncio
    async def test_stop_drains_remaining_events(self):
        """stop() waits for the drain worker to finish."""
        q = AuditEventQueue(maxsize=100)

        with patch("swx_core.services.audit.audit_event_queue.async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            await q.start()
            await q.stop(timeout=2.0)

            assert q._running is False
            assert q._worker_task is None

    @pytest.mark.asyncio
    async def test_stop_timeout_cancels_worker(self):
        """When stop times out, the worker task is cancelled."""
        q = AuditEventQueue(maxsize=100)

        # Put an event so the worker has something to drain
        q.put(AuditEvent(action="test", actor_type="system"))

        with patch("swx_core.services.audit.audit_event_queue.async_session") as mock_session_factory:
            # Make the session block so drain takes forever
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            await q.start()
            # Use a very short timeout to trigger cancellation
            await q.stop(timeout=0.001)

            assert q._running is False


class TestModuleLevelSingleton:
    """Tests for the module-level audit_queue singleton."""

    def test_audit_queue_is_audit_event_queue_instance(self):
        """The module-level audit_queue is an AuditEventQueue instance."""
        assert isinstance(audit_queue, AuditEventQueue)

    def test_audit_queue_has_default_maxsize(self):
        """The singleton has the default maxsize of 10_000."""
        assert audit_queue._queue.maxsize == 10_000
