"""
SwX Service Container.

Laravel-style IoC container for FastAPI with support for:
- bind() - Transient binding (new instance each time)
- singleton() - Singleton binding (same instance always)
- scoped() - Scoped binding (one instance per request)
- when() - Contextual binding
- tag() - Tagged bindings
- Circular dependency detection
"""

from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, Set
from enum import Enum
from contextlib import contextmanager, asynccontextmanager
from functools import wraps
import inspect
import asyncio
import threading

from swx_core.middleware.logging_middleware import logger

from swx_core.middleware.logging_middleware import logger

T = TypeVar('T')


class BindingType(Enum):
    """Type of binding."""
    TRANSIENT = "transient"    # New instance every time
    SINGLETON = "singleton"    # Same instance always
    SCOPED = "scoped"          # One instance per scope (request)
    INSTANCE = "instance"      # Pre-existing instance


class ContainerError(Exception):
    """Base exception for container errors."""
    pass


class BindingResolutionError(ContainerError):
    """Raised when a binding cannot be resolved."""
    pass


class CircularDependencyError(ContainerError):
    """Raised when circular dependency is detected."""
    pass


class Binding:
    """Represents a container binding."""
    
    def __init__(
        self,
        concrete: Union[Callable, Type, Any],
        binding_type: BindingType,
        shared: bool = False
    ):
        self.concrete = concrete
        self.binding_type = binding_type
        self.shared = shared
        self.resolved = False


class ContextualBinding:
    """Binding that applies only in specific context."""
    
    def __init__(self, container: "Container", when_abstract: str):
        self.container = container
        self.when_abstract = when_abstract
        self.needs_abstract: Optional[str] = None
    
    def needs(self, abstract: str) -> "ContextualBinding":
        """
        Specify the dependency that needs contextual binding.
        
        Usage:
            container.when("BillingService").needs("CacheInterface").give(RedisCache)
        """
        self.needs_abstract = abstract
        return self
    
    def give(self, concrete: Union[Callable, Type]) -> None:
        """Define the concrete implementation for this context."""
        if self.needs_abstract:
            self.container._add_contextual(
                self.when_abstract,
                self.needs_abstract,
                concrete
            )


class Container:
    """
    Inversion of Control container with FastAPI integration.
    
    Usage:
        container = Container()
        
        # Binding
        container.bind("rate_limiter", RateLimiter)
        container.singleton("cache", RedisCache)
        container.scoped("session", lambda c: c.make("session_factory"))
        
        # Resolution
        limiter = container.make("rate_limiter")
        
        # Contextual binding
        container.when("billing_service").needs("cache").give(RedisCache)
        
        # Tagging
        container.tag("webhooks", ["stripe_webhook", "paypal_webhook"])
        webhooks = container.tagged("webhooks")
        
        # FastAPI integration
        @app.get("/users")
        async def get_users(
            user_service: UserService = Depends(inject("user_service"))
        ):
            return await user_service.list_users()
    """
    
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
        self._scoped_contexts: List[Dict[str, Any]] = []
        
        # P0 Thread Safety: Locks for concurrent access
        self._singleton_lock = threading.Lock()
        self._scoped_lock = threading.RLock()  # Reentrant for nested resolution

    # =====================
    # BINDING METHODS
    # =====================
    
    def bind(
        self,
        abstract: str,
        concrete: Union[Callable, Type, None] = None,
    ) -> None:
        """
        Register a transient binding.
        
        A new instance is created each time the binding is resolved.
        
        Args:
            abstract: The abstract name or type
            concrete: The concrete implementation (defaults to abstract)
        """
        if concrete is None:
            concrete = abstract
        
        self._bindings[abstract] = Binding(
            concrete=concrete,
            binding_type=BindingType.TRANSIENT
        )
    
    def singleton(
        self,
        abstract: str,
        concrete: Union[Callable, Type, None] = None,
    ) -> None:
        """
        Register a singleton binding.
        
        The same instance is returned for all resolutions.
        
        Args:
            abstract: The abstract name or type
            concrete: The concrete implementation (defaults to abstract)
        """
        if concrete is None:
            concrete = abstract
        
        self._bindings[abstract] = Binding(
            concrete=concrete,
            binding_type=BindingType.SINGLETON,
            shared=True
        )
    
    def scoped(
        self,
        abstract: str,
        concrete: Union[Callable, Type, None] = None,
    ) -> None:
        """
        Register a scoped binding.
        
        One instance per scope (typically request). Must be within
        a scope context created by `async with container.scope():`.
        
        Args:
            abstract: The abstract name or type
            concrete: The concrete implementation (defaults to abstract)
        """
        if concrete is None:
            concrete = abstract
        
        self._bindings[abstract] = Binding(
            concrete=concrete,
            binding_type=BindingType.SCOPED
        )
    
    def instance(self, abstract: str, instance: Any) -> None:
        """
        Bind an existing instance.
        
        Args:
            abstract: The abstract name
            instance: The instance to bind
        """
        self._bindings[abstract] = Binding(
            concrete=instance,
            binding_type=BindingType.INSTANCE,
            shared=True
        )
        self._instances[abstract] = instance
    
    # =====================
    # CONTEXTUAL BINDING
    # =====================
    
    def when(self, abstract: str) -> ContextualBinding:
        """
        Start contextual binding.
        
        Usage:
            container.when("BillingService").needs("CacheInterface").give(RedisCache)
        
        Args:
            abstract: The service that needs the contextual binding
            
        Returns:
            ContextualBinding: The binding builder
        """
        return ContextualBinding(self, abstract)
    
    def _add_contextual(
        self,
        when_abstract: str,
        needs_abstract: str,
        concrete: Callable
    ) -> None:
        """Add contextual binding."""
        if when_abstract not in self._contextual:
            self._contextual[when_abstract] = {}
        self._contextual[when_abstract][needs_abstract] = concrete
    
    # =====================
    # TAGGING
    # =====================
    
    def tag(self, name: str, abstracts: List[str]) -> None:
        """
        Tag multiple bindings.
        
        Args:
            name: Tag name
            abstracts: List of abstract names
        """
        self._tags[name] = abstracts
    
    def tagged(self, name: str) -> List[Any]:
        """
        Resolve all bindings with given tag.
        
        Args:
            name: Tag name
            
        Returns:
            List: Resolved instances
        """
        abstracts = self._tags.get(name, [])
        return [self.make(abstract) for abstract in abstracts]
    
    # =====================
    # ALIASES
    # =====================
    
    def alias(self, abstract: str, alias: str) -> None:
        """
        Create an alias for a binding.
        
        Args:
            abstract: The original abstract name
            alias: The alias name
        """
        self._aliases[alias] = abstract
    
    # =====================
    # RESOLUTION
    # =====================
    
    def make(self, abstract: Union[str, Type[T]], **parameters) -> T:
        """
        Resolve a binding from the container.
        
        Args:
            abstract: The abstract name or type
            **parameters: Constructor parameters
            
        Returns:
            The resolved instance
            
        Raises:
            BindingResolutionError: If binding cannot be resolved
            CircularDependencyError: If circular dependency detected
        """
        # Resolve alias
        abstract_key = self._aliases.get(abstract, abstract)
        if isinstance(abstract_key, type):
            abstract_key = abstract_key.__name__
        
        # Check for circular dependency
        if abstract_key in self._build_stack:
            cycle = " -> ".join(self._build_stack + [abstract_key])
            raise CircularDependencyError(
                f"Circular dependency detected: {cycle}"
            )
        
        # Check for contextual binding
        if self._build_stack:
            contextual = self._get_contextual_concrete(abstract_key)
            if contextual:
                return self._build_contextual(contextual, parameters)
        
        return self._resolve(abstract_key, **parameters)
    
    def _resolve(self, abstract: str, **parameters) -> Any:
        """Internal resolution logic with thread-safe singleton/scoped resolution."""
        # Fire resolving callbacks
        self._fire_callbacks(abstract, self._resolving_callbacks)
        
        # Check for existing singleton instance (thread-safe read first)
        if abstract in self._instances:
            return self._instances[abstract]
        
        # Check for scoped instance in current scope (thread-safe)
        with self._scoped_lock:
            if self._scoped_instances and abstract in self._scoped_instances:
                return self._scoped_instances[abstract]
        
        # Check for binding
        binding = self._bindings.get(abstract)
        
        if binding is None:
            # Try to build unbound concrete class
            return self._build(abstract, **parameters)
        
        # Thread-safe resolution based on binding type
        if binding.binding_type == BindingType.SINGLETON:
            # Double-checked locking for singletons
            if abstract in self._instances:
                return self._instances[abstract]
            
            with self._singleton_lock:
                # Double-check after acquiring lock
                if abstract in self._instances:
                    return self._instances[abstract]
                
                # Build instance
                instance = self._build_binding(binding, abstract, **parameters)
                instance = self._apply_extenders(abstract, instance)
                self._instances[abstract] = instance
                binding.resolved = True
                self._fire_callbacks(abstract, self._resolved_callbacks)
                return instance
        
        elif binding.binding_type == BindingType.SCOPED:
            # Thread-safe scoped resolution
            with self._scoped_lock:
                if self._scoped_instances and abstract in self._scoped_instances:
                    return self._scoped_instances[abstract]
                
                # Build instance
                instance = self._build_binding(binding, abstract, **parameters)
                instance = self._apply_extenders(abstract, instance)
                
                if self._scoped_instances is not None:
                    self._scoped_instances[abstract] = instance
                
                self._fire_callbacks(abstract, self._resolved_callbacks)
                return instance
        
        else:
            # Transient binding - no locking needed
            instance = self._build_binding(binding, abstract, **parameters)
            instance = self._apply_extenders(abstract, instance)
            self._fire_callbacks(abstract, self._resolved_callbacks)
            return instance

    def _build_binding(
        self,
        binding: Binding,
        abstract: str,
        **parameters
    ) -> Any:
        """Build an instance from a binding."""
        concrete = binding.concrete
        
        if binding.binding_type == BindingType.INSTANCE:
            return concrete
        
        return self._build(concrete, **parameters)
    
    def _build(self, concrete: Union[Callable, Type, str], **parameters) -> Any:
        """Build an instance from concrete."""
        if isinstance(concrete, str):
            return self.make(concrete, **parameters)
        
        if callable(concrete) and not inspect.isclass(concrete):
            # Factory function - inject container
            return concrete(self, **parameters)
        
        if inspect.isclass(concrete):
            return self._build_class(concrete, **parameters)
        
        # Already an instance
        return concrete
    
    def _build_class(self, cls: Type, **parameters) -> Any:
        """Build a class instance with dependency injection."""
        # Get constructor signature
        try:
            sig = inspect.signature(cls.__init__)
        except (ValueError, TypeError):
            return cls()
        
        # Build parameters
        resolved_params = {}
        
        for name, param in sig.parameters.items():
            if name == 'self':
                continue
            
            # Check if parameter has type annotation
            if param.annotation != inspect.Parameter.empty:
                param_type = param.annotation
                type_name = self._get_type_name(param_type)
                
                # Try to resolve from container
                if type_name in self._bindings or type_name in self._aliases:
                    self._build_stack.append(type_name)
                    try:
                        resolved_params[name] = self.make(type_name)
                    finally:
                        self._build_stack.pop()
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
        """Get string name of a type."""
        if hasattr(type_obj, '__name__'):
            return type_obj.__name__
        return str(type_obj)
    
    def _get_contextual_concrete(self, abstract: str) -> Optional[Callable]:
        """Get contextual concrete if available."""
        for when_abstract in reversed(self._build_stack):
            if when_abstract in self._contextual:
                if abstract in self._contextual[when_abstract]:
                    return self._contextual[when_abstract][abstract]
        return None
    
    def _build_contextual(self, concrete: Callable, parameters: dict) -> Any:
        """Build from contextual binding."""
        if callable(concrete) and not inspect.isclass(concrete):
            return concrete(self, **parameters)
        return self._build(concrete, **parameters)
    
    # =====================
    # SCOPED RESOLUTION
    # =====================
    
    @contextmanager
    def scope(self) -> "Container":
        """
        Create a new scope for scoped bindings.
        
        Thread-safe: Uses lock to prevent race conditions.
        
        Usage:
            with container.scope():
                # Scoped bindings return same instance within this block
                session1 = container.make("session")
                session2 = container.make("session")
                assert session1 is session2
        """
        with self._scoped_lock:
            previous_scoped = self._scoped_instances
            self._scoped_instances = {}
        try:
            yield self
        finally:
            with self._scoped_lock:
                self._scoped_instances = previous_scoped

    @asynccontextmanager
    async def async_scope(self) -> "Container":
        """
        Create an async scope for scoped bindings.
        
        Thread-safe: Uses lock to prevent race conditions.
        
        Usage:
            async with container.async_scope():
                session1 = container.make("session")
                session2 = container.make("session")
                assert session1 is session2
        """
        # Note: thread-safe for async, uses threading lock for scoped_instances
        with self._scoped_lock:
            previous_scoped = self._scoped_instances
            self._scoped_instances = {}
        try:
            yield self
        finally:
            with self._scoped_lock:
                self._scoped_instances = previous_scoped

    # =====================
    # CALLBACKS & EXTENDERS
    # =====================
    
    def resolving(self, abstract: str, callback: Callable) -> None:
        """
        Register a callback before resolution.
        
        Args:
            abstract: The binding name
            callback: Callback function
        """
        if abstract not in self._resolving_callbacks:
            self._resolving_callbacks[abstract] = []
        self._resolving_callbacks[abstract].append(callback)
    
    def after_resolving(self, abstract: str, callback: Callable) -> None:
        """
        Register a callback after resolution.
        
        Args:
            abstract: The binding name
            callback: Callback function
        """
        if abstract not in self._resolved_callbacks:
            self._resolved_callbacks[abstract] = []
        self._resolved_callbacks[abstract].append(callback)
    
    def extend(self, abstract: str, callback: Callable) -> None:
        """
        Extend a resolved service.
        
        Args:
            abstract: The binding name
            callback: Callback that receives instance and returns modified instance
        """
        if abstract not in self._extenders:
            self._extenders[abstract] = []
        self._extenders[abstract].append(callback)
    
    def _apply_extenders(self, abstract: str, instance: Any) -> Any:
        """Apply extenders to resolved instance."""
        extenders = self._extenders.get(abstract, [])
        for extender in extenders:
            instance = extender(instance, self)
        return instance
    
    def _fire_callbacks(
        self,
        abstract: str,
        callbacks: Dict[str, List[Callable]]
    ) -> None:
        """Fire callbacks for abstract."""
        if abstract in callbacks:
            for callback in callbacks[abstract]:
                callback(self)
    
    # =====================
    # REBINDING
    # =====================
    
    def rebinding(self, abstract: str, callback: Callable) -> None:
        """
        Register a callback for when a binding is rebound.
        
        Args:
            abstract: The binding name
            callback: Callback function
        """
        if abstract not in self._rebindings:
            self._rebindings[abstract] = []
        self._rebindings[abstract].append(callback)
    
    def fresh(self, abstract: str) -> None:
        """
        Re-bind a service and call rebinding callbacks.
        
        Args:
            abstract: The binding name
        """
        # Remove existing instance
        if abstract in self._instances:
            del self._instances[abstract]
        
        # Fire rebinding callbacks
        if abstract in self._rebindings:
            instance = self.make(abstract)
            for callback in self._rebindings[abstract]:
                callback(self, instance)
    
    # =====================
    # UTILITIES
    # =====================
    
    def bound(self, abstract: str) -> bool:
        """
        Check if abstract is bound.
        
        Args:
            abstract: The binding name
            
        Returns:
            bool: True if bound
        """
        return abstract in self._bindings or abstract in self._aliases
    
    def forget(self, abstract: str) -> None:
        """
        Remove a binding from the container.
        
        Args:
            abstract: The binding name
        """
        self._bindings.pop(abstract, None)
        self._instances.pop(abstract, None)
        self._aliases = {k: v for k, v in self._aliases.items() if v != abstract}
    
    def flush(self) -> None:
        """Clear all bindings and instances."""
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
        """Get all bindings."""
        return self._bindings.copy()
    
    def get_instances(self) -> Dict[str, Any]:
        """Get all instances."""
        return self._instances.copy()


# Global container instance
_container: Optional[Container] = None


def get_container() -> Container:
    """Get the global container instance."""
    global _container
    if _container is None:
        _container = Container()
    return _container


def set_container(container: Container) -> None:
    """Set the global container instance."""
    global _container
    _container = container


def reset_container() -> None:
    """Reset the global container."""
    global _container
    _container = None