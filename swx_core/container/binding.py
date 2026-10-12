from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Optional, Type, Union


class BindingType(Enum):
    TRANSIENT = "transient"
    SINGLETON = "singleton"
    SCOPED = "scoped"
    INSTANCE = "instance"


class ContainerError(Exception):
    pass


class BindingResolutionError(ContainerError):
    pass


class CircularDependencyError(ContainerError):
    pass


class Binding:
    __slots__ = ("concrete", "binding_type", "shared", "resolved")

    def __init__(
        self,
        concrete: Union[Callable, Type, Any],
        binding_type: BindingType,
        shared: bool = False,
    ):
        self.concrete = concrete
        self.binding_type = binding_type
        self.shared = shared
        self.resolved = False


class ContextualBinding:
    __slots__ = ("container", "when_abstract", "needs_abstract")

    def __init__(self, container: Container, when_abstract: str):
        self.container = container
        self.when_abstract = when_abstract
        self.needs_abstract: Optional[str] = None

    def needs(self, abstract: str) -> ContextualBinding:
        self.needs_abstract = abstract
        return self

    def give(self, concrete: Union[Callable, Type]) -> None:
        if self.needs_abstract:
            self.container._add_contextual(
                self.when_abstract, self.needs_abstract, concrete
            )