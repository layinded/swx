# pyright: reportUninitializedInstanceVariable=false, reportUnannotatedClassAttribute=false, reportAny=false, reportExplicitAny=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

"""Lazy proxy for deferred module imports.

Defers the actual import until first attribute access, avoiding circular imports
and reducing startup time for heavy optional dependencies.

Usage:
    Redis = lazy_import("redis.asyncio", "Redis")
    # redis package is NOT imported until Redis is accessed
    client = Redis()  # NOW the import happens
"""

import importlib
from typing import Any


class _LazyProxy:
    """Proxy object that defers module import until first attribute access.

    Replaces the pattern of importing heavy modules at the top level,
    which can cause circular imports or slow startup when the module
    is only needed conditionally.
    """

    __slots__ = ("_module_path", "_attr_name", "_target", "_loaded")

    def __init__(self, module_path: str, attr_name: str) -> None:
        object.__setattr__(self, "_module_path", module_path)
        object.__setattr__(self, "_attr_name", attr_name)
        object.__setattr__(self, "_target", None)
        object.__setattr__(self, "_loaded", False)

    def _resolve(self) -> Any:
        if not object.__getattribute__(self, "_loaded"):
            module = importlib.import_module(
                object.__getattribute__(self, "_module_path")
            )
            target = getattr(module, object.__getattribute__(self, "_attr_name"))
            object.__setattr__(self, "_target", target)
            object.__setattr__(self, "_loaded", True)
        return object.__getattribute__(self, "_target")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._resolve()(*args, **kwargs)

    def __repr__(self) -> str:
        if object.__getattribute__(self, "_loaded"):
            return repr(object.__getattribute__(self, "_target"))
        module = object.__getattribute__(self, "_module_path")
        attr = object.__getattribute__(self, "_attr_name")
        return f"<LazyProxy {module}.{attr}>"

    def __bool__(self) -> bool:
        return bool(self._resolve())

    def __instancecheck__(self, instance: Any) -> bool:
        return isinstance(instance, self._resolve())

    def __subclasscheck__(self, subclass: Any) -> bool:
        return issubclass(subclass, self._resolve())


def lazy_import(module_path: str, attr_name: str) -> _LazyProxy:
    """Create a lazy proxy that defers the import until first use.

    Args:
        module_path: Dotted module path, e.g. "redis.asyncio"
        attr_name: Name of the attribute to import from the module, e.g. "Redis"

    Returns:
        A proxy object that behaves like the imported attribute,
        but only performs the import when first accessed.
    """
    return _LazyProxy(module_path, attr_name)