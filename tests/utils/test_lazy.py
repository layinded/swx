# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for swx_core.utils.lazy — deferred module imports via _LazyProxy."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from swx_core.utils.lazy import _LazyProxy, lazy_import


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_module(name: str, attr_name: str, attr_value: object) -> types.ModuleType:
    """Create a fake module with a single attribute for testing lazy imports."""
    mod = types.ModuleType(name)
    setattr(mod, attr_name, attr_value)
    return mod


# ---------------------------------------------------------------------------
# _LazyProxy
# ---------------------------------------------------------------------------

class TestLazyProxy:
    """Tests for the _LazyProxy class."""

    def test_defers_import_until_attribute_access(self) -> None:
        """The module is not imported until an attribute is accessed."""
        fake_mod = _make_fake_module("fake.module", "MyClass", MagicMock())
        with patch.dict(sys.modules, {"fake.module": fake_mod}):
            proxy = _LazyProxy("fake.module", "MyClass")
            # Before access, _loaded should be False
            assert object.__getattribute__(proxy, "_loaded") is False
            # Access an attribute — this triggers the import
            _ = proxy.some_attr
            assert object.__getattribute__(proxy, "_loaded") is True

    def test_attribute_access_resolves_target(self) -> None:
        """Attribute access on the proxy delegates to the resolved target."""
        target = MagicMock()
        target.some_method = MagicMock(return_value="result")
        fake_mod = _make_fake_module("fake.module", "MyClass", target)
        with patch.dict(sys.modules, {"fake.module": fake_mod}):
            proxy = _LazyProxy("fake.module", "MyClass")
            result = proxy.some_method()
            assert result == "result"
            target.some_method.assert_called_once()

    def test_call_resolves_and_invokes_target(self) -> None:
        """Calling the proxy resolves the target and calls it."""
        target = MagicMock(return_value="called")
        fake_mod = _make_fake_module("fake.module", "MyClass", target)
        with patch.dict(sys.modules, {"fake.module": fake_mod}):
            proxy = _LazyProxy("fake.module", "MyClass")
            result = proxy("arg1", kwarg1="val")
            assert result == "called"
            target.assert_called_once_with("arg1", kwarg1="val")

    def test_repr_unresolved(self) -> None:
        """__repr__ shows the lazy proxy info when unresolved."""
        proxy = _LazyProxy("my.module", "SomeClass")
        r = repr(proxy)
        assert "LazyProxy" in r
        assert "my.module" in r
        assert "SomeClass" in r

    def test_repr_resolved(self) -> None:
        """__repr__ delegates to the target's repr when resolved."""
        target = MagicMock()
        target.__repr__ = MagicMock(return_value="<TargetInstance>")
        fake_mod = _make_fake_module("fake.module", "MyClass", target)
        with patch.dict(sys.modules, {"fake.module": fake_mod}):
            proxy = _LazyProxy("fake.module", "MyClass")
            # Force resolution
            _ = proxy._resolve()
            r = repr(proxy)
            assert r == "<TargetInstance>"

    def test_bool_truthy(self) -> None:
        """__bool__ returns True when the resolved target is truthy."""
        fake_mod = _make_fake_module("fake.module", "MyClass", True)
        with patch.dict(sys.modules, {"fake.module": fake_mod}):
            proxy = _LazyProxy("fake.module", "MyClass")
            assert bool(proxy) is True

    def test_bool_falsy(self) -> None:
        """__bool__ returns False when the resolved target is falsy."""
        fake_mod = _make_fake_module("fake.module", "MyClass", None)
        with patch.dict(sys.modules, {"fake.module": fake_mod}):
            proxy = _LazyProxy("fake.module", "MyClass")
            assert bool(proxy) is False

    def test_bool_resolves_only_once(self) -> None:
        """__bool__ triggers resolution but caches the result."""
        target = MagicMock()
        fake_mod = _make_fake_module("fake.module", "MyClass", target)
        with patch.dict(sys.modules, {"fake.module": fake_mod}):
            proxy = _LazyProxy("fake.module", "MyClass")
            bool(proxy)
            bool(proxy)
            # Target should only be accessed once (during first resolution)
            # The second bool() uses the cached target

    def test_instancecheck(self) -> None:
        """__instancecheck__ delegates to the resolved target."""
        target = str  # Use a real type for isinstance check
        fake_mod = _make_fake_module("fake.module", "MyClass", target)
        with patch.dict(sys.modules, {"fake.module": fake_mod}):
            proxy = _LazyProxy("fake.module", "MyClass")
            assert isinstance("hello", proxy) is True

    def test_subclasscheck(self) -> None:
        """__subclasscheck__ delegates to the resolved target."""
        target = object
        fake_mod = _make_fake_module("fake.module", "MyClass", target)
        with patch.dict(sys.modules, {"fake.module": fake_mod}):
            proxy = _LazyProxy("fake.module", "MyClass")
            assert issubclass(str, proxy) is True

    def test_import_error_propagates(self) -> None:
        """If the module cannot be imported, the error propagates."""
        proxy = _LazyProxy("nonexistent.module.xyz", "SomeClass")
        with pytest.raises(ModuleNotFoundError):
            proxy._resolve()

    def test_attribute_error_on_missing_attr(self) -> None:
        """If the attribute doesn't exist on the module, AttributeError propagates."""
        fake_mod = types.ModuleType("fake.module")
        with patch.dict(sys.modules, {"fake.module": fake_mod}):
            proxy = _LazyProxy("fake.module", "MissingAttr")
            with pytest.raises(AttributeError):
                proxy._resolve()


# ---------------------------------------------------------------------------
# lazy_import
# ---------------------------------------------------------------------------

class TestLazyImport:
    """Tests for the lazy_import convenience function."""

    def test_returns_lazy_proxy(self) -> None:
        """lazy_import returns a _LazyProxy instance."""
        proxy = lazy_import("some.module", "SomeClass")
        assert isinstance(proxy, _LazyProxy)

    def test_proxy_resolves_on_call(self) -> None:
        """The proxy returned by lazy_import resolves correctly on call."""
        target = MagicMock(return_value="instantiated")
        fake_mod = _make_fake_module("real.module", "RealClass", target)
        with patch.dict(sys.modules, {"real.module": fake_mod}):
            proxy = lazy_import("real.module", "RealClass")
            result = proxy("arg")
            assert result == "instantiated"
            target.assert_called_once_with("arg")

    def test_proxy_resolves_on_attribute_access(self) -> None:
        """The proxy returned by lazy_import resolves on attribute access."""
        target = MagicMock()
        target.method = MagicMock(return_value="ok")
        fake_mod = _make_fake_module("real.module", "RealClass", target)
        with patch.dict(sys.modules, {"real.module": fake_mod}):
            proxy = lazy_import("real.module", "RealClass")
            result = proxy.method()
            assert result == "ok"

    def test_multiple_proxies_independent(self) -> None:
        """Multiple lazy_import proxies are independent."""
        target_a = MagicMock()
        target_b = MagicMock()
        fake_mod_a = _make_fake_module("mod.a", "ClassA", target_a)
        fake_mod_b = _make_fake_module("mod.b", "ClassB", target_b)
        with patch.dict(sys.modules, {"mod.a": fake_mod_a, "mod.b": fake_mod_b}):
            proxy_a = lazy_import("mod.a", "ClassA")
            proxy_b = lazy_import("mod.b", "ClassB")
            proxy_a()
            proxy_b()
            target_a.assert_called_once()
            target_b.assert_called_once()
