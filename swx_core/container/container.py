"""
SwX Service Container.

Laravel-style IoC container with transient, singleton, scoped, contextual,
and tagged bindings.  Thread-safe singleton/scoped resolution via RLock.
"""

from __future__ import annotations

import inspect
import threading
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from swx_core.container.binding import (
    Binding,
    BindingType,
    CircularDependencyError,
    ContextualBinding,
)
from swx_core.middleware.logging_middleware import logger

T = TypeVar("T")


class Container:

    def __init__(self):
        self._bindings: Dict[str, Binding] = {}
        self._instances: Dict[str, Any] = {}
        self._scoped_instances: Dict[str, Any] = {}
        self._aliases: Dict[str, str] = {}
        self._contextual: Dict[str, Dict[str, Callable]] = {}
        self._tags: Dict[str, List[str]] = {}
        self._resolving_callbacks: Dict[str, List[Callable]] = {}
        self._resolved_callbacks: Dict[str, List[Callable]] = {}
        self._extenders: Dict[str, List[Callable]] = {}
        self._rebindings: Dict[str, List[Callable]] = {}
        self._build_stack: List[str] = []
        # RLock required: factory functions may call make() again for
        # nested deps, which would deadlock a non-reentrant Lock.
        self._singleton_lock = threading.RLock()
        self._scoped_lock = threading.RLock()

    # -- Binding methods --------------------------------------------------

    def bind(
        self,
        abstract: str,
        concrete: Union[Callable, Type, None] = None,
    ) -> None:
        if concrete is None:
            concrete = abstract
        self._bindings[abstract] = Binding(
            concrete=concrete, binding_type=BindingType.TRANSIENT
        )

    def singleton(
        self,
        abstract: str,
        concrete: Union[Callable, Type, None] = None,
    ) -> None:
        if concrete is None:
            concrete = abstract
        self._bindings[abstract] = Binding(
            concrete=concrete, binding_type=BindingType.SINGLETON, shared=True
        )

    def scoped(
        self,
        abstract: str,
        concrete: Union[Callable, Type, None] = None,
    ) -> None:
        if concrete is None:
            concrete = abstract
        self._bindings[abstract] = Binding(
            concrete=concrete, binding_type=BindingType.SCOPED
        )

    def instance(self, abstract: str, instance: Any) -> None:
        self._bindings[abstract] = Binding(
            concrete=instance, binding_type=BindingType.INSTANCE, shared=True
        )
        self._instances[abstract] = instance

    # -- Contextual binding -----------------------------------------------

    def when(self, abstract: str) -> ContextualBinding:
        return ContextualBinding(self, abstract)

    def _add_contextual(
        self,
        when_abstract: str,
        needs_abstract: str,
        concrete: Callable,
    ) -> None:
        if when_abstract not in self._contextual:
            self._contextual[when_abstract] = {}
        self._contextual[when_abstract][needs_abstract] = concrete

    # -- Tagging ----------------------------------------------------------

    def tag(self, name: str, abstracts: List[str]) -> None:
        self._tags[name] = abstracts

    def tagged(self, name: str) -> List[Any]:
        return [self.make(a) for a in self._tags.get(name, [])]

    # -- Aliases ----------------------------------------------------------

    def alias(self, abstract: str, alias_name: str) -> None:
        self._aliases[alias_name] = abstract

    # -- Resolution -------------------------------------------------------

    def make(self, abstract: Union[str, Type[T]], **parameters) -> T:
        abstract_key = self._aliases.get(abstract, abstract)
        if isinstance(abstract_key, type):
            abstract_key = abstract_key.__name__

        if abstract_key in self._build_stack:
            cycle = " -> ".join(self._build_stack + [abstract_key])
            raise CircularDependencyError(f"Circular dependency detected: {cycle}")

        if self._build_stack:
            contextual = self._get_contextual_concrete(abstract_key)
            if contextual:
                return self._build_contextual(contextual, parameters)

        self._build_stack.append(abstract_key)
        try:
            return self._resolve(abstract_key, **parameters)
        finally:
            self._build_stack.pop()

    def _resolve(self, abstract: str, **parameters) -> Any:
        self._fire_callbacks(abstract, self._resolving_callbacks)

        if abstract in self._instances:
            return self._instances[abstract]

        with self._scoped_lock:
            if self._scoped_instances and abstract in self._scoped_instances:
                return self._scoped_instances[abstract]

        binding = self._bindings.get(abstract)
        if binding is None:
            return self._build(abstract, **parameters)

        if binding.binding_type == BindingType.SINGLETON:
            if abstract in self._instances:
                return self._instances[abstract]
            with self._singleton_lock:
                if abstract in self._instances:
                    return self._instances[abstract]
                instance = self._build_binding(binding, abstract, **parameters)
                instance = self._apply_extenders(abstract, instance)
                self._instances[abstract] = instance
                binding.resolved = True
                self._fire_callbacks(abstract, self._resolved_callbacks)
                return instance

        if binding.binding_type == BindingType.SCOPED:
            with self._scoped_lock:
                if self._scoped_instances and abstract in self._scoped_instances:
                    return self._scoped_instances[abstract]
                instance = self._build_binding(binding, abstract, **parameters)
                instance = self._apply_extenders(abstract, instance)
                if self._scoped_instances is not None:
                    self._scoped_instances[abstract] = instance
                self._fire_callbacks(abstract, self._resolved_callbacks)
                return instance

        # Transient
        instance = self._build_binding(binding, abstract, **parameters)
        instance = self._apply_extenders(abstract, instance)
        self._fire_callbacks(abstract, self._resolved_callbacks)
        return instance

    def _build_binding(self, binding: Binding, abstract: str, **parameters) -> Any:
        concrete = binding.concrete
        if binding.binding_type == BindingType.INSTANCE:
            return concrete
        return self._build(concrete, **parameters)

    def _build(self, concrete: Union[Callable, Type, str], **parameters) -> Any:
        if isinstance(concrete, str):
            return self.make(concrete, **parameters)
        if callable(concrete) and not inspect.isclass(concrete):
            return concrete(self, **parameters)
        if inspect.isclass(concrete):
            return self._build_class(concrete, **parameters)
        return concrete

    def _build_class(self, cls: Type, **parameters) -> Any:
        try:
            sig = inspect.signature(cls.__init__)
        except (ValueError, TypeError):
            return cls()

        resolved_params: Dict[str, Any] = {}
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.annotation != inspect.Parameter.empty:
                type_name = self._get_type_name(param.annotation)
                if type_name in self._bindings or type_name in self._aliases:
                    resolved_params[name] = self.make(type_name)
                elif param.default != inspect.Parameter.empty:
                    resolved_params[name] = param.default
                elif name in parameters:
                    resolved_params[name] = parameters[name]
            elif param.default != inspect.Parameter.empty:
                resolved_params[name] = param.default
            elif name in parameters:
                resolved_params[name] = parameters[name]

        return cls(**resolved_params)

    def _get_type_name(self, type_obj: Type) -> str:
        if hasattr(type_obj, "__name__"):
            return type_obj.__name__
        return str(type_obj)

    def _get_contextual_concrete(self, abstract: str) -> Optional[Callable]:
        for when_abstract in reversed(self._build_stack):
            if when_abstract in self._contextual:
                if abstract in self._contextual[when_abstract]:
                    return self._contextual[when_abstract][abstract]
        return None

    def _build_contextual(self, concrete: Callable, parameters: dict) -> Any:
        if callable(concrete) and not inspect.isclass(concrete):
            return concrete(self, **parameters)
        return self._build(concrete, **parameters)

    # -- Scoped resolution ------------------------------------------------

    @contextmanager
    def scope(self):
        with self._scoped_lock:
            previous_scoped = self._scoped_instances
            self._scoped_instances = {}
        try:
            yield self
        finally:
            with self._scoped_lock:
                self._scoped_instances = previous_scoped

    @asynccontextmanager
    async def async_scope(self):
        with self._scoped_lock:
            previous_scoped = self._scoped_instances
            self._scoped_instances = {}
        try:
            yield self
        finally:
            with self._scoped_lock:
                self._scoped_instances = previous_scoped

    # -- Callbacks & extenders --------------------------------------------

    def resolving(self, abstract: str, callback: Callable) -> None:
        self._resolving_callbacks.setdefault(abstract, []).append(callback)

    def after_resolving(self, abstract: str, callback: Callable) -> None:
        self._resolved_callbacks.setdefault(abstract, []).append(callback)

    def extend(self, abstract: str, callback: Callable) -> None:
        self._extenders.setdefault(abstract, []).append(callback)

    def _apply_extenders(self, abstract: str, instance: Any) -> Any:
        for extender in self._extenders.get(abstract, []):
            instance = extender(instance, self)
        return instance

    def _fire_callbacks(
        self, abstract: str, callbacks: Dict[str, List[Callable]]
    ) -> None:
        for callback in callbacks.get(abstract, []):
            callback(self)

    # -- Rebinding --------------------------------------------------------

    def rebinding(self, abstract: str, callback: Callable) -> None:
        self._rebindings.setdefault(abstract, []).append(callback)

    def fresh(self, abstract: str) -> None:
        if abstract in self._instances:
            del self._instances[abstract]
        if abstract in self._rebindings:
            instance = self.make(abstract)
            for callback in self._rebindings[abstract]:
                callback(self, instance)

    # -- Utilities --------------------------------------------------------

    def bound(self, abstract: str) -> bool:
        return abstract in self._bindings or abstract in self._aliases

    def has(self, abstract: str) -> bool:
        """Alias for ``bound()`` — more readable for positive checks."""
        return self.bound(abstract)

    def override(self, abstract: str, concrete: Any) -> None:
        """Replace an existing binding and clear any cached singleton instance."""
        if abstract in self._instances:
            del self._instances[abstract]
        self._bindings[abstract] = Binding(
            concrete=concrete, binding_type=BindingType.TRANSIENT
        )
        logger.info("container.overridden abstract=%s", abstract)

    def forget(self, abstract: str) -> None:
        self._bindings.pop(abstract, None)
        self._instances.pop(abstract, None)
        self._aliases = {k: v for k, v in self._aliases.items() if v != abstract}

    def flush(self) -> None:
        self._bindings = {}
        self._instances = {}
        self._scoped_instances = {}
        self._aliases = {}
        self._contextual = {}
        self._tags = {}
        self._extenders = {}
        self._resolving_callbacks = {}
        self._resolved_callbacks = {}

    def get_bindings(self) -> Dict[str, Binding]:
        return self._bindings.copy()

    def get_instances(self) -> Dict[str, Any]:
        return self._instances.copy()


_container: Optional[Container] = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container()
    return _container


def set_container(container: Container) -> None:
    global _container
    _container = container


def reset_container() -> None:
    global _container
    _container = None