import asyncio
import pytest

from swx_core.background import BackgroundScheduler, ScheduledJob


class _Counter:
    def __init__(self):
        self.count = 0

    async def increment(self):
        self.count += 1


class TestBackgroundScheduler:
    def test_register_returns_self_for_chaining(self):
        sched = BackgroundScheduler()
        result = sched.register(name="t", handler=lambda: None, interval=60)
        assert result is sched

    def test_register_duplicate_name_raises(self):
        sched = BackgroundScheduler()
        async def noop(): pass
        sched.register(name="dup", handler=noop, interval=60)
        with pytest.raises(ValueError, match="already registered"):
            sched.register(name="dup", handler=noop, interval=60)

    def test_register_invalid_interval_raises(self):
        sched = BackgroundScheduler()
        async def noop(): pass
        with pytest.raises(ValueError, match=">= 1 second"):
            sched.register(name="t", handler=noop, interval=0)

    def test_unregister_removes_job(self):
        sched = BackgroundScheduler()
        async def noop(): pass
        sched.register(name="t", handler=noop, interval=60)
        sched.unregister("t")
        assert "t" not in sched._jobs

    @pytest.mark.asyncio
    async def test_start_runs_jobs(self):
        sched = BackgroundScheduler()
        counter = _Counter()
        sched.register(name="cnt", handler=counter.increment, interval=3600)
        await sched.start()

        # Give the task a moment to run once (startup=True by default)
        await asyncio.sleep(0.1)
        assert counter.count >= 1

        await sched.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        sched = BackgroundScheduler()
        async def noop(): pass
        sched.register(name="t", handler=noop, interval=60)
        await sched.start()
        await sched.start()  # should not duplicate tasks
        job = sched._jobs["t"]
        assert job._task is not None
        await sched.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self):
        sched = BackgroundScheduler()
        async def long_sleep():
            await asyncio.sleep(9999)
        sched.register(name="long", handler=long_sleep, interval=9999)
        await sched.start()
        await sched.stop()
        job = sched._jobs["long"]
        assert job._task is None

    @pytest.mark.asyncio
    async def test_error_policy_log_and_continue(self):
        sched = BackgroundScheduler()
        call_count = 0

        async def failing():
            nonlocal call_count
            call_count += 1
            raise ValueError("transient")

        sched.register(name="flaky", handler=failing, interval=1, error_policy="log_and_continue")
        await sched.start()
        await asyncio.sleep(2.5)
        await sched.stop()
        # Should have retried after the first failure (1s interval)
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_startup_false_delays_first_run(self):
        sched = BackgroundScheduler()
        counter = _Counter()

        sched.register(name="delayed", handler=counter.increment, interval=3600, startup=False)
        await sched.start()
        await asyncio.sleep(0.05)
        # With startup=False and interval=3600, the first run should NOT happen yet
        assert counter.count == 0
        await sched.stop()


class TestScheduledJob:
    def test_job_fields(self):
        async def h(): pass
        job = ScheduledJob(name="x", handler=h, interval=30)
        assert job.name == "x"
        assert job.interval == 30
        assert job.startup is True
        assert job.error_policy == "log_and_continue"