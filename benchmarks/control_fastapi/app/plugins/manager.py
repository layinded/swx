"""
Control FastAPI Project - Plugin System
Manual hook registration for benchmarking against SwX.
"""

from typing import Callable, Dict, Any, List, Optional, Type
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


@dataclass
class PluginHook:
    """Plugin hook definition."""
    name: str
    callback: Callable
    priority: int = 50  # Lower = runs first


class PluginInterface(ABC):
    """Base plugin interface."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""
        pass
    
    @abstractmethod
    def register(self) -> None:
        """Register plugin hooks."""
        pass
    
    @abstractmethod
    def unregister(self) -> None:
        """Unregister plugin hooks."""
        pass
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure plugin."""
        pass


class PluginManager:
    """Manual plugin manager."""
    
    def __init__(self):
        self._plugins: Dict[str, PluginInterface] = {}
        self._hooks: Dict[str, List[PluginHook]] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}
    
    def register_plugin(self, plugin: PluginInterface) -> None:
        """Register a plugin."""
        if plugin.name in self._plugins:
            logger.warning(f"Plugin {plugin.name} already registered")
            return
        
        # Apply configuration
        config = self._configs.get(plugin.name, {})
        plugin.configure(config)
        
        # Register hooks
        plugin.register()
        self._plugins[plugin.name] = plugin
        
        logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")
    
    def unregister_plugin(self, plugin_name: str) -> None:
        """Unregister a plugin."""
        plugin = self._plugins.pop(plugin_name, None)
        if plugin:
            plugin.unregister()
            logger.info(f"Unregistered plugin: {plugin_name}")
    
    def get_plugin(self, plugin_name: str) -> Optional[PluginInterface]:
        """Get a plugin by name."""
        return self._plugins.get(plugin_name)
    
    def list_plugins(self) -> List[str]:
        """List all registered plugins."""
        return list(self._plugins.keys())
    
    def register_hook(
        self,
        hook_name: str,
        callback: Callable,
        priority: int = 50
    ) -> None:
        """Register a hook callback."""
        hook = PluginHook(name=hook_name, callback=callback, priority=priority)
        
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        
        self._hooks[hook_name].append(hook)
        self._hooks[hook_name].sort(key=lambda h: h.priority)
        
        logger.debug(f"Registered hook: {hook_name}")
    
    def unregister_hook(self, hook_name: str, callback: Callable) -> None:
        """Unregister a hook callback."""
        if hook_name in self._hooks:
            self._hooks[hook_name] = [
                h for h in self._hooks[hook_name]
                if h.callback != callback
            ]
    
    def execute_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Execute all callbacks for a hook."""
        results = []
        
        hooks = self._hooks.get(hook_name, [])
        
        for hook in hooks:
            try:
                result = hook.callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Hook {hook_name} error: {e}")
        
        return results
    
    async def execute_hook_async(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Execute all async callbacks for a hook."""
        import asyncio
        
        results = []
        hooks = self._hooks.get(hook_name, [])
        
        for hook in hooks:
            try:
                if asyncio.iscoroutinefunction(hook.callback):
                    result = await hook.callback(*args, **kwargs)
                else:
                    result = hook.callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Hook {hook_name} error: {e}")
        
        return results
    
    def configure_plugin(self, plugin_name: str, config: Dict[str, Any]) -> None:
        """Configure a plugin."""
        if plugin_name not in self._configs:
            self._configs[plugin_name] = {}
        
        self._configs[plugin_name].update(config)
        
        # Apply to plugin if already registered
        plugin = self._plugins.get(plugin_name)
        if plugin:
            plugin.configure(config)


# Global plugin manager
plugin_manager = PluginManager()


# Decorator for hooks
def hook(hook_name: str, priority: int = 50):
    """Decorator to register a hook callback."""
    def decorator(func: Callable):
        plugin_manager.register_hook(hook_name, func, priority)
        return func
    return decorator
