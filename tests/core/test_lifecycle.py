import asyncio
import pytest

from swx_core.lifecycle import LifecycleError, LifecycleManager, LifecycleService


class _OkService(LifecycleService):
    name = "ok"
    started = False
    stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


class _FailStartService(LifecycleService):
    name = "fail_start"

    async def start(self):
        raise RuntimeError("boom")

    async def stop(self):
        pass


class _FailStopService(LifecycleService):
    name = "fail_stop"
    started = False

    async def start(self):
        self.started = True

    async def stop(self):
        raise RuntimeError("stop boom")


class _NoNameService(LifecycleService):
    name = ""

    async def start(self):
        pass

    async def stop(self):
        pass


class TestLifecycleManager:
    def test_register_requires_name(self):
        mgr = LifecycleManager()
        with pytest.raises(ValueError, match="non-empty 'name'"):
            mgr.register(_NoNameService())

    def test_register_returns_self_for_chaining(self):
        mgr = LifecycleManager()
        result = mgr.register(_OkService())
        assert result is mgr

    def test_services_property_returns_immutable_snapshot(self):
        mgr = LifecycleManager()
        svc = _OkService()
        mgr.register(svc)
        services = mgr.services
        assert len(services) == 1
        assert services[0] is svc
        assert isinstance(services, tuple)

    @pytest.mark.asyncio
    async def test_start_all_starts_in_order(self):
        mgr = LifecycleManager()
        svc = _OkService()
        mgr.register(svc)
        await mgr.start_all()
        assert svc.started

    @pytest.mark.asyncio
    async def test_stop_all_stops_in_reverse_order(self):
        mgr = LifecycleManager()
        svc = _OkService()
        mgr.register(svc)
        await mgr.start_all()
        await mgr.stop_all()
        assert svc.stopped

    @pytest.mark.asyncio
    async def test_start_failure_propagates_and_stops_already_started(self):
        mgr = LifecycleManager()
        ok = _OkService()
        fail = _FailStartService()
        mgr.register(ok)
        mgr.register(fail)

        with pytest.raises(LifecycleError) as exc_info:
            await mgr.start_all()

        assert exc_info.value.service_name == "fail_start"
        assert exc_info.value.action == "start"
        assert ok.stopped  # already-started service was stopped

    @pytest.mark.asyncio
    async def test_stop_failure_is_logged_not_raised(self):
        mgr = LifecycleManager()
        fail_stop = _FailStopService()
        mgr.register(fail_stop)
        await mgr.start_all()
        # Should NOT raise even though stop() raises
        await mgr.stop_all()

    @pytest.mark.asyncio
    async def test_stop_all_noop_if_not_started(self):
        mgr = LifecycleManager()
        mgr.register(_OkService())
        await mgr.stop_all()  # no error

    @pytest.mark.asyncio
    async def test_reverse_stop_order(self):
        order = []

        class Svc(LifecycleService):
            def __init__(self, n):
                self.name = n

            async def start(self):
                order.append(f"start_{self.name}")

            async def stop(self):
                order.append(f"stop_{self.name}")

        mgr = LifecycleManager()
        mgr.register(Svc("a"))
        mgr.register(Svc("b"))
        mgr.register(Svc("c"))

        await mgr.start_all()
        await mgr.stop_all()

        assert order == ["start_a", "start_b", "start_c", "stop_c", "stop_b", "stop_a"]


class TestLifecycleError:
    def test_error_fields(self):
        err = LifecycleError(service_name="cache", action="start", detail="timeout")
        assert err.service_name == "cache"
        assert err.action == "start"
        assert err.detail == "timeout"
        assert "cache" in str(err)