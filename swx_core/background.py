"""
SwX Background Scheduler
-------------------------
Declarative recurring task registration with graceful shutdown.

Applications register named recurring jobs instead of hand-rolling
``while True: … await asyncio.sleep(N)`` loops in ``main.py``.

Usage::

    from swx_core.background import background

    background.register(
        name="cache_refresh",
        handler=refresh_translation_cache,
        interval=3600,
    )

    # During app startup:
    await background.start()

    # During app shutdown:
    await background.stop()

For single-execution, database-backed jobs with distributed locking,
continue using ``swx_core.services.job.JobRunner`` — that system
provides ``SELECT … FOR UPDATE SKIP LOCKED`` to prevent duplicate
execution across workers.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from swx_core.middleware.logging_middleware import logger


@dataclass
class ScheduledJob:
    """Internal representation of a registered recurring job."""

    name: str
    handler: Callable[[], Awaitable[None]]
    interval: int  # seconds
    startup: bool = True
    error_policy: str = "log_and_continue"  # "log_and_continue" | "raise"
    _task: asyncio.Task[None] | None = field(default=None, repr=False, init=False)


class BackgroundScheduler:
    """Registry and runner for named recurring async tasks.

    Each registered job runs as an ``asyncio.Task`` that calls the handler
    and then sleeps for ``interval`` seconds.  Errors are logged by default;
    set ``error_policy="raise"`` to crash the task on failure.

    The scheduler itself is designed to be registered with
    ``LifecycleManager`` so it starts and stops with the app lifecycle.
    """

    name = "background_scheduler"

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}
        self._running = False

    # -- registration --------------------------------------------------

    def register(
        self,
        name: str,
        handler: Callable[[], Awaitable[None]],
        interval: int,
        *,
        startup: bool = True,
        error_policy: str = "log_and_continue",
    ) -> "BackgroundScheduler":
        """Register a recurring job.

        Args:
            name: Unique identifier for the job.
            handler: Async callable invoked each interval.
            interval: Seconds between invocations.
            startup: If ``True`` (default), the first run happens
                immediately on start.  Set ``False`` to wait one
                interval before the first run.
            error_policy: ``"log_and_continue"`` (default) keeps the
                loop alive after errors.  ``"raise"`` propagates the
                exception and cancels the task.

        Returns:
            ``self``, for chaining.
        """
        if name in self._jobs:
            raise ValueError(f"Job '{name}' is already registered")
        if interval < 1:
            raise ValueError(f"Interval for '{name}' must be >= 1 second, got {interval}")

        self._jobs[name] = ScheduledJob(
            name=name,
            handler=handler,
            interval=interval,
            startup=startup,
            error_policy=error_policy,
        )
        logger.info("background.registered job=%s interval=%ds", name, interval)
        return self

    def unregister(self, name: str) -> None:
        """Cancel and remove a registered job by name."""
        job = self._jobs.pop(name, None)
        if job and job._task and not job._task.done():
            job._task.cancel()
        logger.info("background.unregistered job=%s", name)

    # -- lifecycle -----------------------------------------------------

    async def start(self) -> None:
        """Start all registered jobs as asyncio tasks."""
        if self._running:
            logger.warning("background.already_running")
            return
        self._running = True

        for job in self._jobs.values():
            job._task = asyncio.create_task(
                self._run_loop(job),
                name=f"swx:bg:{job.name}",
            )
            logger.info("background.started job=%s", job.name)

    async def stop(self) -> None:
        """Cancel all running tasks and wait for them to finish.

        Errors during cancellation are logged but never raised.
        """
        if not self._running:
            return
        self._running = False

        tasks = [j._task for j in self._jobs.values() if j._task and not j._task.done()]
        if not tasks:
            return

        for task in tasks:
            task.cancel()

        done = await asyncio.gather(*tasks, return_exceptions=True)
        cancelled_count = sum(1 for result in done if isinstance(result, asyncio.CancelledError))
        error_count = sum(1 for result in done if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError))
        if error_count:
            logger.warning("background.stopped cancelled=%d errors=%d", cancelled_count, error_count)
        else:
            logger.info("background.stopped cancelled=%d", cancelled_count)

        for job in self._jobs.values():
            job._task = None

    # -- internal ------------------------------------------------------

    async def _run_loop(self, job: ScheduledJob) -> None:
        """Run a single job's handler in a loop with interval sleep."""
        # If startup=False, sleep one interval before the first run.
        if not job.startup:
            await asyncio.sleep(job.interval)

        while self._running:
            start = time.monotonic()
            try:
                await job.handler()
                elapsed = time.monotonic() - start
                logger.info("background.completed job=%s elapsed=%.2fs", job.name, elapsed)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if job.error_policy == "raise":
                    logger.error("background.fatal job=%s error=%s", job.name, exc)
                    raise
                logger.exception("background.error job=%s", job.name)

            # Sleep for the remainder of the interval, or the full interval
            # if the handler took longer than expected.
            remaining = job.interval - (time.monotonic() - start)
            if remaining > 0:
                await asyncio.sleep(remaining)


# Module-level singleton for convenience.
background = BackgroundScheduler()