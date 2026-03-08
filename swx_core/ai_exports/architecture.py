"""
SwX AI-Aware Layer - Architecture Introspection Engine
====================================================

Exports complete architecture in machine-readable formats.
This module works without requiring full SwX initialization.
"""

import json
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

# Try imports, fall back to defaults if unavailable
try:
    from swx_core.bootstrap import CORE_PROVIDERS
except ImportError:
    CORE_PROVIDERS = [
        "swx_core.providers.database_provider.DatabaseServiceProvider",
        "swx_core.providers.event_provider.EventServiceProvider",
        "swx_core.providers.auth_provider.AuthServiceProvider",
        "swx_core.providers.rate_limit_provider.RateLimitServiceProvider",
        "swx_core.providers.billing_provider.BillingServiceProvider",
    ]

try:
    from swx_core.container.container import Container, get_container
except ImportError:
    Container = None
    get_container = None

try:
    from swx_core.providers.base import ServiceProvider
except ImportError:
    ServiceProvider = None

try:
    from swx_core.version import __version__
except ImportError:
    __version__ = "2.0.0"


class ArchitectureIntrospector:
    """Introspects SwX architecture for AI consumption."""
    
    def __init__(self, container=None):
        self.container = container
        self.swx_root = Path(__file__).parent.parent.parent
    
    def get_providers(self) -> List[Dict[str, Any]]:
        """Get all registered providers."""
        providers = []
        
        for provider_path in CORE_PROVIDERS:
            try:
                module_path, class_name = provider_path.rsplit(".", 1)
                module = __import__(module_path, fromlist=[class_name])
                provider_class = getattr(module, class_name)
                
                bindings = self._infer_provider_bindings(provider_class)
                
                providers.append({
                    "name": provider_class.__name__.replace("ServiceProvider", "").lower(),
                    "class_path": provider_path,
                    "priority": getattr(provider_class, 'priority', 100),
                    "bindings": bindings,
                    "tags": self._infer_provider_tags(provider_class),
                    "zone": "CORE"
                })
            except Exception:
                continue
        
        return providers
    
    def _infer_provider_bindings(self, provider_class: type) -> List[str]:
        """Infer bindings from provider class."""
        bindings = []
        name = provider_class.__name__.lower()
        
        if "database" in name:
            bindings = ["database", "db_connection", "query_builder"]
        elif "event" in name:
            bindings = ["event_bus", "event_dispatcher"]
        elif "auth" in name:
            bindings = ["auth_service", "token_service", "user_provider"]
        elif "rate_limit" in name:
            bindings = ["rate_limiter", "abuse_detector"]
        elif "billing" in name:
            bindings = ["billing_service", "subscription_manager", "entitlement_resolver"]
        
        return bindings
    
    def _infer_provider_tags(self, provider_class: type) -> List[str]:
        """Infer tags from provider class."""
        tags = ["core"]
        name = provider_class.__name__.lower()
        
        if "database" in name:
            tags.append("database")
        elif "event" in name:
            tags.append("events")
        elif "auth" in name:
            tags.append("security")
        elif "rate_limit" in name:
            tags.append("performance")
        elif "billing" in name:
            tags.append("billing")
        
        return tags
    
    def get_bindings(self) -> List[Dict[str, Any]]:
        """Get all container bindings."""
        bindings = []
        
        if self.container is None:
            return bindings
            
        for name, binding in self.container.get_bindings().items():
            bindings.append({
                "abstract": name,
                "concrete": self._get_binding_concrete(binding),
                "binding_type": binding.binding_type.value,
                "dependencies": self._extract_dependencies(binding),
                "shared": binding.shared
            })
        
        return bindings
    
    def _get_binding_concrete(self, binding) -> str:
        """Get concrete class path."""
        concrete = binding.concrete
        if callable(concrete) and hasattr(concrete, "__module__"):
            return f"{concrete.__module__}.{concrete.__name__}"
        return str(concrete)
    
    def _extract_dependencies(self, binding) -> List[str]:
        """Extract dependencies from binding."""
        deps = []
        concrete = binding.concrete
        
        if callable(concrete) and hasattr(concrete, "__init__"):
            try:
                sig = inspect.signature(concrete.__init__)
                for name, param in sig.parameters.items():
                    if name != "self" and param.annotation != inspect.Parameter.empty:
                        deps.append(self._type_to_string(param.annotation))
            except Exception:
                pass
        
        return deps
    
    def _type_to_string(self, typ: type) -> str:
        """Convert type to string."""
        if hasattr(typ, "__name__"):
            return typ.__name__
        return str(typ)
    
    def get_guards(self) -> Dict[str, Dict[str, Any]]:
        """Get guard configuration."""
        guards = {}
        
        # Check for JWT guard
        try:
            from swx_core.guards.jwt_guard import JWTGuard
            guards["jwt"] = {
                "class_path": "swx_core.guards.jwt_guard.JWTGuard",
                "enabled": True,
                "config": {"algorithm": "HS256", "expiration_minutes": 60}
            }
        except ImportError:
            pass
        
        # Check for API Key guard
        try:
            from swx_core.guards.api_key_guard import APIKeyGuard
            guards["api_key"] = {
                "class_path": "swx_core.guards.api_key_guard.APIKeyGuard",
                "enabled": True,
                "config": {}
            }
        except ImportError:
            pass
        
        return guards
    
    def get_events(self) -> Dict[str, Any]:
        """Get event registry."""
        events = {
            "dispatcher_class": "swx_core.events.dispatcher.EventDispatcher",
            "listeners": []
        }
        
        try:
            from swx_core.events.dispatcher import event_bus
            if hasattr(event_bus, "_listeners"):
                for event_name, listeners in event_bus._listeners.items():
                    for listener in listeners:
                        events["listeners"].append({
                            "event": event_name,
                            "handler": getattr(listener, "__name__", str(listener)),
                            "priority": getattr(listener, "priority", 50),
                            "queueable": getattr(listener, "queueable", False),
                            "zone": "APP"
                        })
        except Exception:
            pass
        
        return events
    
    def get_routes(self) -> List[Dict[str, Any]]:
        """Get route tree."""
        routes = []
        
        try:
            from swx_core.router import router
            for route in router.routes:
                routes.append({
                    "path": getattr(route, "path", "/"),
                    "methods": list(getattr(route, "methods", ["GET"])),
                    "handler": self._get_handler_path(route),
                    "domain": "public"
                })
        except Exception:
            pass
        
        return routes
    
    def _get_handler_path(self, route) -> str:
        """Get handler path."""
        if hasattr(route, "endpoint"):
            ep = route.endpoint
            if hasattr(ep, "__module__"):
                return f"{ep.__module__}.{ep.__name__}"
        return "unknown"
    
    def get_contracts(self) -> List[Dict[str, Any]]:
        """Get contract definitions."""
        contracts = []
        
        contracts.append({
            "name": "RepositoryProtocol",
            "interface_path": "swx_core.repositories.base.BaseRepository",
            "methods": [
                {"name": "find_by_id", "parameters": [{"name": "id", "type": "int"}], "return_type": "Optional[Model]", "is_async": True},
                {"name": "find_all", "parameters": [{"name": "filters", "type": "Optional[dict]"}], "return_type": "List[Model]", "is_async": True},
                {"name": "create", "parameters": [{"name": "data", "type": "dict"}], "return_type": "Model", "is_async": True},
                {"name": "update", "parameters": [{"name": "id", "type": "int"}, {"name": "data", "type": "dict"}], "return_type": "Optional[Model]", "is_async": True},
                {"name": "delete", "parameters": [{"name": "id", "type": "int"}], "return_type": "bool", "is_async": True}
            ],
            "implementations": ["swx_core.repositories.UserRepository"]
        })
        
        contracts.append({
            "name": "ServiceProtocol",
            "interface_path": "swx_core.services.base.BaseService",
            "methods": [
                {"name": "get", "parameters": [{"name": "id", "type": "int"}], "return_type": "Optional[Model]", "is_async": True},
                {"name": "create", "parameters": [{"name": "data", "type": "dict"}], "return_type": "Model", "is_async": True}
            ],
            "implementations": []
        })
        
        return contracts
    
    def get_safe_zones(self) -> Dict[str, Dict[str, Any]]:
        """Get safe zone definitions."""
        return {
            "core": {
                "mutability": "read-only",
                "description": "Framework core - cannot be modified",
                "paths": ["swx_core/container/**", "swx_core/bootstrap.py", "swx_core/router.py", "swx_core/main.py"],
                "forbidden_operations": ["edit", "delete", "override", "replace"]
            },
            "app": {
                "mutability": "safe",
                "description": "Application code - safe to modify within contracts",
                "paths": ["swx_app/controllers/**", "swx_app/services/**", "swx_app/repositories/**", "swx_app/models/**", "swx_app/routes/**"],
                "allowed_operations": ["create", "edit", "delete", "extend", "implement"]
            },
            "providers": {
                "mutability": "override-layer",
                "description": "Service providers - can be overridden via container",
                "paths": ["swx_core/providers/*.py", "swx_app/providers/**"],
                "allowed_operations": ["override_binding", "extend_provider", "create_new_provider"],
                "mechanism": "Container binding override"
            },
            "plugins": {
                "mutability": "extension-layer",
                "description": "Plugins - extend functionality without modification",
                "paths": ["swx_plugins/**", "swx_core/plugins/**"],
                "allowed_operations": ["install", "uninstall", "configure", "hook"],
                "constraints": ["Cannot override other plugins without explicit rule"]
            }
        }
    
    def get_middleware_stack(self) -> Dict[str, Any]:
        """Get middleware stack."""
        return {
            "global": [
                {"class_path": "swx_core.middleware.cors_middleware", "position": 0},
                {"class_path": "swx_core.middleware.logging_middleware", "position": 1},
                {"class_path": "swx_core.middleware.rate_limit_middleware", "position": 2}
            ],
            "route_specific": []
        }
    
    def export_full(self) -> Dict[str, Any]:
        """Export complete architecture."""
        return {
            "version": "2.0.0",
            "exported_at": datetime.now().isoformat(),
            "swx_version": __version__,
            "providers": self.get_providers(),
            "bindings": self.get_bindings(),
            "guards": self.get_guards(),
            "events": self.get_events(),
            "routes": self.get_routes(),
            "contracts": self.get_contracts(),
            "safe_zones": self.get_safe_zones(),
            "middleware": self.get_middleware_stack()
        }


def get_architecture() -> Dict[str, Any]:
    """Get full architecture export."""
    introspector = ArchitectureIntrospector()
    return introspector.export_full()
