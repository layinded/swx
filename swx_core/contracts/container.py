"""
Container Contracts.

Defines interfaces for the service container and service providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, List, Type, TypeVar, Union, Optional

T = TypeVar('T')


class ContainerInterface(ABC):
    """
    Abstract interface for the service container.
    
    The container manages service bindings and resolution.
    """
    
    @abstractmethod
    def bind(self, abstract: str, concrete: Union[Callable, Type, None] = None) -> None:
        """
        Register a transient binding.
        
        A new instance is created each time the binding is resolved.
        
        Args:
            abstract: The abstract name or type
            concrete: The concrete implementation
        """
        pass
    
    @abstractmethod
    def singleton(self, abstract: str, concrete: Union[Callable, Type, None] = None) -> None:
        """
        Register a singleton binding.
        
        The same instance is returned for all resolutions.
        
        Args:
            abstract: The abstract name or type
            concrete: The concrete implementation
        """
        pass
    
    @abstractmethod
    def scoped(self, abstract: str, concrete: Union[Callable, Type, None] = None) -> None:
        """
        Register a scoped binding.
        
        One instance per scope (typically request).
        
        Args:
            abstract: The abstract name or type
            concrete: The concrete implementation
        """
        pass
    
    @abstractmethod
    def instance(self, abstract: str, instance: Any) -> None:
        """
        Bind an existing instance.
        
        Args:
            abstract: The abstract name
            instance: The instance to bind
        """
        pass
    
    @abstractmethod
    def make(self, abstract: Union[str, Type[T]], **parameters) -> T:
        """
        Resolve a binding from the container.
        
        Args:
            abstract: The abstract name or type
            **parameters: Constructor parameters
            
        Returns:
            The resolved instance
        """
        pass
    
    @abstractmethod
    def bound(self, abstract: str) -> bool:
        """
        Check if abstract is bound.
        
        Args:
            abstract: The abstract name
            
        Returns:
            bool: True if bound
        """
        pass
    
    @abstractmethod
    def forget(self, abstract: str) -> None:
        """
        Remove a binding.
        
        Args:
            abstract: The abstract name
        """
        pass
    
    @abstractmethod
    def when(self, abstract: str) -> "ContextualBinding":
        """
        Start a contextual binding.
        
        Args:
            abstract: The abstract name
            
        Returns:
            ContextualBinding: The contextual binding builder
        """
        pass
    
    @abstractmethod
    def tag(self, name: str, abstracts: List[str]) -> None:
        """
        Tag multiple bindings.
        
        Args:
            name: Tag name
            abstracts: List of abstract names
        """
        pass
    
    @abstractmethod
    def tagged(self, name: str) -> List[Any]:
        """
        Resolve all bindings with given tag.
        
        Args:
            name: Tag name
            
        Returns:
            List: Resolved instances
        """
        pass


class ContextualBinding(ABC):
    """
    Abstract interface for contextual bindings.
    """
    
    @abstractmethod
    def needs(self, abstract: str) -> "ContextualBinding":
        """
        Specify the dependency that needs contextual binding.
        
        Args:
            abstract: The dependency name
            
        Returns:
            self for chaining
        """
        pass
    
    @abstractmethod
    def give(self, concrete: Union[Callable, Type]) -> None:
        """
        Specify the concrete implementation for the context.
        
        Args:
            concrete: The concrete implementation
        """
        pass


class ServiceProviderInterface(ABC):
    """
    Abstract interface for service providers.
    
    Providers register and boot services in the container.
    """
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """
        Provider registration priority.
        
        Lower numbers are registered first.
        
        Returns:
            int: Priority value
        """
        pass
    
    @property
    def defer(self) -> bool:
        """
        Whether to defer loading until a provided service is needed.
        
        Returns:
            bool: True for deferred loading
        """
        return False
    
    @property
    def depends(self) -> List[str]:
        """
        List of provider names this provider depends on.
        
        Returns:
            List[str]: Provider dependencies
        """
        return []
    
    @abstractmethod
    def register(self) -> None:
        """
        Register services in the container.
        
        Do NOT resolve services here - only bind.
        """
        pass
    
    def boot(self) -> None:
        """
        Boot the provider after all providers have registered.
        
        Safe to resolve services here.
        """
        pass
    
    def provides(self) -> List[str]:
        """
        List services this provider provides.
        
        Used for deferred loading.
        
        Returns:
            List[str]: Service names
        """
        return []