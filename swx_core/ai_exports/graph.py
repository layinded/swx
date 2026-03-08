#MY|"""
#NS|SwX AI-Aware Layer - Dependency Graph Exporter
#XK|============================================
#RW|
#RK|Exports service, event, provider, and plugin dependency graphs.
#MX|"""
#HN|
#TZ|import json
#BT|from typing import Any, Dict, List
#SK|
#BT|# Safe import
#BT|from swx_core.ai_exports.architecture import get_architecture
#TX|
SwX AI-Aware Layer - Dependency Graph Exporter
============================================

Exports service, event, provider, and plugin dependency graphs.
"""

import json
from typing import Any, Dict, List

from swx_core.ai_exports.architecture import get_architecture


def generate_dependency_graph(
    graph_type: str = "all",
    output_format: str = "json"
) -> str:
    """Generate dependency graph."""
    
    architecture = get_architecture()
    
    if output_format == "mermaid":
        return _generate_mermaid(architecture, graph_type)
    elif output_format == "dot":
        return _generate_dot(architecture, graph_type)
    else:
        return _generate_json(architecture, graph_type)


def _generate_json(architecture: dict, graph_type: str) -> str:
    """Generate JSON graph."""
    
    graphs = {}
    
    if graph_type in ("all", "service"):
        graphs["service_dependencies"] = _build_service_graph(architecture)
    
    if graph_type in ("all", "event"):
        graphs["event_dependencies"] = _build_event_graph(architecture)
    
    if graph_type in ("all", "provider"):
        graphs["provider_dependencies"] = _build_provider_graph(architecture)
    
    return json.dumps(graphs, indent=2)


def _generate_mermaid(architecture: dict, graph_type: str) -> str:
    """Generate Mermaid diagram."""
    
    lines = ["```mermaid", "graph LR"]
    
    if graph_type in ("all", "service"):
        lines.append("\n  %% Service Dependencies")
        for edge in _get_service_edges(architecture):
            lines.append(f"  {edge['source']} --> {edge['target']}")
    
    if graph_type in ("all", "event"):
        lines.append("\n  %% Event Flow")
        for edge in _get_event_edges(architecture):
            lines.append(f"  {edge['source']} -.-> {edge['target']}")
    
    lines.append("```")
    return "\n".join(lines)


def _generate_dot(architecture: dict, graph_type: str) -> str:
    """Generate DOT (Graphviz) format."""
    
    lines = ["digraph swx_dependencies {"]
    lines.append('  rankdir=LR;')
    lines.append('  node [shape=box];')
    
    if graph_type in ("all", "service"):
        lines.append("\n  # Service Dependencies")
        for edge in _get_service_edges(architecture):
            lines.append(f'  {edge["source"]} -> {edge["target"]};')
    
    if graph_type in ("all", "event"):
        lines.append("\n  # Event Flow")
        for edge in _get_event_edges(architecture):
            lines.append(f'  {edge["source"]} -> {edge["target"]} [style=dashed];')
    
    lines.append("}")
    return "\n".join(lines)


def _build_service_graph(architecture: dict) -> Dict[str, Any]:
    """Build service dependency graph."""
    
    nodes = []
    edges = []
    seen = set()
    
    # Add providers as nodes
    for provider in architecture.get("providers", []):
        nodes.append({
            "id": provider["name"],
            "label": provider["name"],
            "zone": provider.get("zone", "CORE"),
            "type": "service"
        })
        
        # Add binding edges
        for binding in architecture.get("bindings", []):
            if provider["name"] in binding.get("concrete", "").lower():
                edges.append({
                    "source": binding["abstract"],
                    "target": provider["name"],
                    "type": "dependency"
                })
    
    return {
        "graph_type": "service_dependencies",
        "nodes": nodes,
        "edges": edges
    }


def _build_event_graph(architecture: dict) -> Dict[str, Any]:
    """Build event dependency graph."""
    
    nodes = []
    edges = []
    
    # Add dispatcher
    nodes.append({
        "id": "event_dispatcher",
        "label": "EventDispatcher",
        "type": "dispatcher"
    })
    
    # Add listeners
    events = architecture.get("events", {})
    for listener in events.get("listeners", []):
        event_name = listener.get("event", "unknown")
        handler = listener.get("handler", "unknown")
        
        if event_name not in [n["id"] for n in nodes]:
            nodes.append({
                "id": event_name,
                "label": event_name,
                "type": "event"
            })
        
        edges.append({
            "source": event_name,
            "target": handler,
            "type": "listener"
        })
    
    return {
        "graph_type": "event_dependencies",
        "nodes": nodes,
        "edges": edges
    }


def _build_provider_graph(architecture: dict) -> Dict[str, Any]:
    """Build provider dependency graph."""
    
    nodes = []
    edges = []
    
    for provider in architecture.get("providers", []):
        nodes.append({
            "id": provider["name"],
            "label": provider["name"],
            "priority": provider.get("priority", 100),
            "type": "provider"
        })
        
        # Add edges to dependencies (bindings)
        for binding in provider.get("bindings", []):
            edges.append({
                "source": provider["name"],
                "target": binding,
                "type": "registers"
            })
    
    return {
        "graph_type": "provider_dependencies",
        "nodes": nodes,
        "edges": edges
    }


def _get_service_edges(architecture: dict) -> List[Dict[str, str]]:
    """Get service dependency edges."""
    
    edges = []
    
    # Map services to their dependencies
    service_deps = {
        "database": ["config"],
        "event": ["database"],
        "auth": ["database", "event"],
        "rate_limit": ["database", "cache"],
        "billing": ["auth", "database"]
    }
    
    for service, deps in service_deps.items():
        for dep in deps:
            edges.append({
                "source": service,
                "target": dep
            })
    
    return edges


def _get_event_edges(architecture: dict) -> List[Dict[str, str]]:
    """Get event flow edges."""
    
    return [
        {"source": "user.created", "target": "UserListener"},
        {"source": "payment.completed", "target": "PaymentListener"},
        {"source": "subscription.created", "target": "SubscriptionListener"}
    ]
