"""
SwX AI-Aware Layer - Agent Context Bundle Generator
================================================

Generates compressed architecture context optimized for LLM token limits.
"""

import json
from typing import Any, Dict, List, Optional
from pathlib import Path

# Safe import - architecture module handles its own fallbacks
from swx_core.ai_exports.architecture import get_architecture


def generate_agent_context(
    format: str = "standard",
    include: Optional[List[str]] = None,
    token_budget: int = 4000
) -> Dict[str, Any]:
    """Generate AI agent context bundle."""
    
    architecture = get_architecture()
    
    if format == "compact":
        return _generate_compact(architecture, include)
    elif format == "detailed":
        return _generate_detailed(architecture, include)
    else:
        return _generate_standard(architecture, include)


def _generate_compact(architecture: dict, include: Optional[List[str]]) -> Dict[str, Any]:
    """Generate compact context."""
    
    return {
        "version": architecture.get("version"),
        "format": "compact",
        "summary": "SwX FastAPI Framework v2.0 - Production SaaS Platform",
        "folder_structure": {
            "swx_core": "Framework core (READ-ONLY)",
            "swx_app": "Application layer (SAFE modification)",
            "swx_plugins": "Plugin extensions",
            "swx_core/config": "Configuration",
            "swx_core/providers": "Service providers",
            "swx_core/guards": "Authentication guards",
            "swx_core/events": "Event system",
            "swx_core/routes": "API routes"
        },
        "extension_points": [
            {
                "type": "provider",
                "path": "swx_app/providers/",
                "purpose": "Register new services",
                "example": "class CustomProvider(ServiceProvider)"
            },
            {
                "type": "middleware",
                "path": "swx_app/middleware/",
                "purpose": "Request/response processing",
                "example": "class CustomMiddleware(BaseMiddleware)"
            },
            {
                "type": "event_listener",
                "path": "swx_app/listeners/",
                "purpose": "React to events",
                "example": "class UserListener(Listener)"
            },
            {
                "type": "controller",
                "path": "swx_app/controllers/",
                "purpose": "API endpoints",
                "example": "class ProductController(BaseController)"
            }
        ],
        "safe_zones": {
            "CORE": "Do not modify - framework",
            "APP": "Safe to modify",
            "PROVIDER": "Override via container binding",
            "PLUGIN": "Extension layer"
        }
    }


def _generate_standard(architecture: dict, include: Optional[List[str]]) -> Dict[str, Any]:
    """Generate standard context."""
    
    context = _generate_compact(architecture, include)
    context["format"] = "standard"
    
    # Add service map
    context["service_map"] = {}
    for provider in architecture.get("providers", []):
        name = provider["name"]
        context["service_map"][name] = {
            "purpose": _get_service_purpose(name),
            "zone": provider.get("zone", "CORE"),
            "bindings": provider.get("bindings", [])
        }
    
    # Add guard config
    context["guard_config"] = architecture.get("guards", {})
    
    # Add event topology
    events = architecture.get("events", {})
    context["event_topology"] = {
        "dispatcher": events.get("dispatcher_class", "swx_core.events.dispatcher.EventDispatcher"),
        "common_events": _extract_common_events(events)
    }
    
    # Add modification patterns
    context["modification_patterns"] = {
        "add_service": "Create provider in swx_app/providers/",
        "add_route": "Create controller in swx_app/controllers/",
        "add_middleware": "Create in swx_app/middleware/",
        "subscribe_to_event": "Create listener in swx_app/listeners/"
    }
    
    return context


def _generate_detailed(architecture: dict, include: Optional[List[str]]) -> Dict[str, Any]:
    """Generate detailed context."""
    
    context = _generate_standard(architecture, include)
    context["format"] = "detailed"
    
    # Add full route tree
    context["routes"] = architecture.get("routes", [])
    
    # Add all bindings
    context["bindings"] = architecture.get("bindings", [])
    
    # Add contracts
    context["contracts"] = architecture.get("contracts", [])
    
    # Add middleware
    context["middleware"] = architecture.get("middleware", {})
    
    return context


def _get_service_purpose(name: str) -> str:
    """Get service purpose description."""
    purposes = {
        "database": "Database connection and queries",
        "event": "Event dispatching and listeners",
        "auth": "JWT authentication and authorization",
        "rate_limit": "Rate limiting and abuse detection",
        "billing": "Stripe integration and subscriptions"
    }
    return purposes.get(name, "Custom service")


def _extract_common_events(events: dict) -> List[str]:
    """Extract common event names."""
    common = [
        "user.created",
        "user.updated",
        "user.deleted",
        "payment.completed",
        "subscription.created",
        "subscription.cancelled"
    ]
    return common
