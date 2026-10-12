"""
SwX Lifecycle Manager
---------------------
Deterministic startup/shutdown for long-running services.

Applications register ``LifecycleService`` instances instead of scattering
``asyncio.create_task()`` calls throughout ``main.py``.  The manager starts
services in registration order and stops them in **reverse** order, so
dependencies that start later are torn down first.

Usage::

    from swx_core.lifecycle import LifecycleManager, LifecycleService

    manager = LifecycleManager()

    manager.register(JobRunnerService())
    manager.register(AuditQueueService())
    manager.register(CacheRefreshService())

    # During app startup:
    await manager.start_all()

    # During app shutdown:
    await manager.stop_all()
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

from swx_core.middleware.logging_middleware import logger


class LifecycleError(Exception):
    """Raised when a lifecycle service fails to start or stop."""

    def __init__(self, service_name: str, action: str, detail: str = ""):
        self.service_name = service_name
        self.action = action
        self.detail = detail
        super().__init__(f"Failed to {action} {service_name}: {detail}")


class LifecycleService(ABC):
    """Base class for services that participate in the app lifecycle.

    Subclass and implement ``start()`` and ``stop()``.  Register instances
    with ``LifecycleManager`` — do **not** call ``start()``/``stop()`` directly.
    """

    name: str = ""

    @abstractmethod
    async def start(self) -> None:
        """Start the service.  Raise on unrecoverable failure."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the service.  Best-effort — log errors, do not raise."""


class LifecycleManager:
    """Ordered registry of ``LifecycleService`` instances.

    * ``register()`` appends a service.
    * ``start_all()`` starts in registration order (dependencies first).
    * ``stop_all()`` stops in **reverse** registration order (dependents first).

    Start failures are fatal — they propagate with the service name.
    Stop failures are logged but never raise — shutdown must be resilient.
    """

    def __init__(self) -> None:
        self._services: list[LifecycleService] = []
        self._started: list[LifecycleService] = []

    def register(self, service: LifecycleService) -> "LifecycleManager":
        """Append a service.  Returns ``self`` for chaining."""
        if not service.name:
            raise ValueError(
                f"LifecycleService {type(service).__name__} must have a non-empty 'name'"
            )
        self._services.append(service)
        return self

    @property
    def services(self) -> tuple[LifecycleService, ...]:
        """Immutable snapshot of registered services in order."""
        return tuple(self._services)

    async def start_all(self) -> None:
        """Start every registered service in order.

        Raises ``LifecycleError`` on the first failure, identifying the
        exact service and stage that failed.
        """
        self._started.clear()
        for service in self._services:
            start_time = time.monotonic()
            try:
                await service.start()
                elapsed = time.monotonic() - start_time
                logger.info(
                    "lifecycle.started service=%s elapsed=%.2fs",
                    service.name,
                    elapsed,
                )
                self._started.append(service)
            except Exception as exc:
                # Attempt to stop whatever already started before re-raising.
                await self.stop_all()
                raise LifecycleError(
                    service_name=service.name,
                    action="start",
                    detail=str(exc),
                ) from exc

    async def stop_all(self) -> None:
        """Stop all started services in reverse order.

        Best-effort: errors are logged but never propagated.  ``timeout``
        is a soft limit per service — individual services should implement
        their own timeout handling in ``stop()``.
        """
        for service in reversed(self._started):
            start_time = time.monotonic()
            try:
                await service.stop()
                elapsed = time.monotonic() - start_time
                logger.info(
                    "lifecycle.stopped service=%s elapsed=%.2fs",
                    service.name,
                    elapsed,
                )
            except Exception:
                logger.exception("lifecycle.stop_failed service=%s", service.name)
        self._started.clear()