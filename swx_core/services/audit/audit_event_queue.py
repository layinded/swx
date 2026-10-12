"""Audit Event Queue
-------------------
Async queue that buffers audit events and drains them to the database
in a background task.  Overflow is dropped with a warning to avoid
unbounded memory growth under load.

Wires into FastAPI lifespan: start the drain worker on startup, drain
remaining events on shutdown.

Usage::

    from swx_core.services.audit.audit_event_queue import audit_queue

    # In lifespan startup:
    await audit_queue.start()
    # In lifespan shutdown:
    await audit_queue.stop()

    # Enqueue from anywhere:
    await audit_queue.put(action="user.login", actor_type="user", ...)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.database.db import async_session

logger = logging.getLogger(__name__)

_MAX_QUEUE_SIZE = 10_000
_DRAIN_BATCH_SIZE = 100
_MAX_RETRY_CYCLES = 3


@dataclass
class AuditEvent:
    """Lightweight event envelope enqueued for batched DB write."""

    action: str
    actor_type: str
    actor_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    outcome: str = "success"
    severity: str = "info"
    context: dict[str, Any] = field(default_factory=dict)


class AuditEventQueue:
    """Buffered audit event queue with background drain worker.

    Overflow policy: ``put_nowait()`` drops the event and logs a warning
    when the queue is full, keeping latency predictable.

    Use ``queue_depth`` to monitor backlog size for alerting.
    """

    def __init__(self, maxsize: int = _MAX_QUEUE_SIZE) -> None:
        self._queue: asyncio.Queue[AuditEvent] = asyncio.Queue(maxsize=maxsize)
        self._worker_task: asyncio.Task[None] | None = None
        self._running = False
        self._retry_cycles: int = 0

    @property
    def queue_depth(self) -> int:
        """Current number of events waiting to be drained."""
        return self._queue.qsize()

    async def start(self) -> None:
        """Start the background drain worker. Call during app startup."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._drain_worker(), name="audit-event-drain")
        logger.info("Audit event queue started (maxsize=%d)", self._queue.maxsize)

    async def stop(self, timeout: float = 5.0) -> None:
        """Stop the drain worker, flushing remaining events. Call during app shutdown."""
        self._running = False
        if self._worker_task is not None:
            try:
                await asyncio.wait_for(self._worker_task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Audit drain worker did not stop within %.1fs — cancelling", timeout)
                self._worker_task.cancel()
            self._worker_task = None
        logger.info("Audit event queue stopped (remaining=%d)", self.queue_depth)

    def put(self, event: AuditEvent) -> None:
        """Enqueue an event. Drops on overflow with a warning."""
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "Audit event queue full (%d events) — dropping action=%s",
                self.queue_depth,
                event.action,
            )

    async def _drain_worker(self) -> None:
        """Background loop that batches events and writes them to the DB."""
        from swx_core.services.audit_logger import AuditLogger

        while self._running or not self._queue.empty():
            batch: list[AuditEvent] = []
            for _ in range(_DRAIN_BATCH_SIZE):
                try:
                    event = self._queue.get_nowait()
                    batch.append(event)
                except asyncio.QueueEmpty:
                    break

            if not batch:
                await asyncio.sleep(0.1)
                continue

            try:
                async with async_session() as session:
                    audit = AuditLogger(session)
                    for event in batch:
                        await audit.log_event(
                            action=event.action,
                            actor_type=event.actor_type,
                            actor_id=event.actor_id,
                            resource_type=event.resource_type,
                            resource_id=event.resource_id,
                            outcome=event.outcome,
                            severity=event.severity,
                            context=event.context,
                        )
                    await session.commit()
                self._retry_cycles = 0
            except Exception:
                logger.error(
                    "Failed to drain %d audit events — will retry on next cycle",
                    len(batch),
                    exc_info=True,
                )
                self._retry_cycles += 1
                if self._retry_cycles <= _MAX_RETRY_CYCLES:
                    for event in batch:
                        self.put(event)
                else:
                    logger.critical(
                        "Audit drain failed %d consecutive cycles — dropping %d events to prevent unbounded retry",
                        self._retry_cycles,
                        len(batch),
                    )
                await asyncio.sleep(1.0)


audit_queue = AuditEventQueue()
"""Module-level singleton. Import and use from anywhere."""