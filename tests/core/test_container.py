import pytest

from swx_core.container.binding import (
    Binding,
    BindingResolutionError,
    BindingType,
    CircularDependencyError,
    ContainerError,
    ContextualBinding,
)
from swx_core.container.container import Container


class TestBindingTypes:
    def test_binding_type_values(self):
        assert BindingType.TRANSIENT.value == "transient"
        assert BindingType.SINGLETON.value == "singleton"
        assert BindingType.SCOPED.value == "scoped"
        assert BindingType.INSTANCE.value == "instance"

    def test_binding_defaults(self):
        b = Binding(concrete=lambda c: 1, binding_type=BindingType.TRANSIENT)
        assert b.shared is False
        assert b.resolved is False

    def test_binding_singleton_shared(self):
        b = Binding(concrete=lambda c: 1, binding_type=BindingType.SINGLETON, shared=True)
        assert b.shared is True

    def test_exception_hierarchy(self):
        assert issubclass(BindingResolutionError, ContainerError)
        assert issubclass(CircularDependencyError, ContainerError)


class TestContainerBind:
    def test_bind_transient(self):
        c = Container()
        c.bind("svc", lambda c: 42)
        assert c.make("svc") == 42

    def test_bind_defaults_concrete_to_abstract(self):
        c = Container()
        c.bind("key", None)
        # When concrete is None, abstract is used as concrete string
        b = c.get_bindings()["key"]
        assert b.concrete == "key"

    def test_singleton_returns_same_instance(self):
        c = Container()
        c.singleton("cache", lambda c: {"v": 1})
        a = c.make("cache")
        b = c.make("cache")
        assert a is b

    def test_scoped_same_within_scope(self):
        c = Container()
        c.scoped("session", lambda c: object())
        with c.scope():
            a = c.make("session")
            b = c.make("session")
            assert a is b

    def test_scoped_different_between_scopes(self):
        c = Container()
        c.scoped("session", lambda c: object())
        with c.scope():
            a = c.make("session")
        with c.scope():
            b = c.make("session")
        assert a is not b

    def test_instance_binds_preexisting(self):
        c = Container()
        obj = {"data": True}
        c.instance("config", obj)
        assert c.make("config") is obj


class TestContainerContextualBinding:
    def test_contextual_binding(self):
        c = Container()
        c.bind("cache", lambda c: "default_cache")
        c.when("billing").needs("cache").give(lambda c: "redis_cache")
        assert c.make("cache") == "default_cache"

    def test_contextual_binding_builder(self):
        c = Container()
        c.bind("cache", lambda c: "default")
        cb = c.when("svc")
        result = cb.needs("cache")
        assert result is cb


class TestContainerTagging:
    def test_tag_and_tagged(self):
        c = Container()
        c.bind("a", lambda c: 1)
        c.bind("b", lambda c: 2)
        c.tag("nums", ["a", "b"])
        result = c.tagged("nums")
        assert result == [1, 2]

    def test_tagged_empty(self):
        c = Container()
        assert c.tagged("nonexistent") == []


class TestContainerAlias:
    def test_alias(self):
        c = Container()
        c.bind("real_name", lambda c: "value")
        c.alias("real_name", "short")
        assert c.make("short") == "value"


class TestContainerOverride:
    def test_override_replaces_binding(self):
        c = Container()
        c.bind("svc", lambda c: "old")
        assert c.make("svc") == "old"
        c.override("svc", lambda c: "new")
        assert c.make("svc") == "new"

    def test_override_clears_singleton_instance(self):
        c = Container()
        c.singleton("svc", lambda c: object())
        first = c.make("svc")
        c.override("svc", lambda c: "replaced")
        assert c.make("svc") == "replaced"
        assert c.make("svc") != first


class TestContainerHas:
    def test_has_alias(self):
        c = Container()
        c.bind("svc", lambda c: 1)
        assert c.has("svc") is True
        assert c.has("missing") is False

    def test_has_matches_bound(self):
        c = Container()
        c.bind("x", lambda c: 1)
        assert c.has("x") == c.bound("x")


class TestContainerCallbacks:
    def test_resolving_callback(self):
        c = Container()
        called = []
        c.resolving("svc", lambda container: called.append("resolving"))
        c.bind("svc", lambda c: "val")
        c.make("svc")
        assert "resolving" in called

    def test_after_resolving_callback(self):
        c = Container()
        called = []
        c.after_resolving("svc", lambda container: called.append("resolved"))
        c.bind("svc", lambda c: "val")
        c.make("svc")
        assert "resolved" in called

    def test_extend_callback(self):
        c = Container()
        c.bind("svc", lambda c: {"count": 1})
        c.extend("svc", lambda instance, container: {"count": instance["count"] + 10})
        result = c.make("svc")
        assert result["count"] == 11


class TestContainerForget:
    def test_forget_removes_binding(self):
        c = Container()
        c.bind("svc", lambda c: "val")
        assert c.has("svc")
        c.forget("svc")
        assert not c.has("svc")

    def test_forget_nonexistent_is_noop(self):
        c = Container()
        c.forget("nothing")  # no error


class TestContainerFlush:
    def test_flush_clears_all(self):
        c = Container()
        c.bind("a", lambda c: 1)
        c.singleton("b", lambda c: 2)
        c.instance("c", 3)
        c.flush()
        assert c.get_bindings() == {}
        assert c.get_instances() == {}


class TestContainerCircularDetection:
    def test_circular_dependency_raises(self):
        c = Container()
        c.bind("a", "b")
        c.bind("b", "a")
        with pytest.raises(CircularDependencyError):
            c.make("a")


class TestContainerBuildClass:
    def test_build_class_auto_injects(self):
        class Svc:
            def __init__(self, name: str = "default"):
                self.name = name

        c = Container()
        c.bind("name", lambda c: "injected")
        c.bind("svc", Svc)
        result = c.make("svc")
        # name is a str type, not in bindings by class name "str"
        # so it should fall through to the default
        assert result.name == "default"


class TestContainerModuleGlobals:
    def test_get_container_returns_singleton(self):
        from swx_core.container.container import get_container, set_container, reset_container
        reset_container()
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2
        reset_container()
        c3 = get_container()
        assert c3 is not c1  # new instance after reset

    def test_set_container(self):
        from swx_core.container.container import get_container, set_container, reset_container
        reset_container()
        custom = Container()
        set_container(custom)
        assert get_container() is custom
        reset_container()