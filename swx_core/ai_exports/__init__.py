"""
SwX AI-Aware Layer
==================

Exports for AI-aware layer functionality.
"""

from swx_core.ai_exports.architecture import get_architecture, ArchitectureIntrospector
from swx_core.ai_exports.context_bundle import generate_agent_context
from swx_core.ai_exports.graph import generate_dependency_graph
from swx_core.ai_exports.contracts import get_contracts_export
from swx_core.ai_exports.agent_manifest import get_agent_manifest
from swx_core.ai_exports.ai_spec import get_ai_spec
from swx_core.ai_exports.safe_zones import (
    get_zone_for_path,
    validate_zone,
    check_modification_allowed,
    get_zone_metadata,
    list_zones,
    is_core_path,
    is_app_path,
    ZONES
)
from swx_core.ai_exports.change_planner import plan_modification

__all__ = [
    "get_architecture",
    "ArchitectureIntrospector",
    "generate_agent_context",
    "generate_dependency_graph",
    "get_contracts_export",
    "get_agent_manifest",
    "get_ai_spec",
    "get_zone_for_path",
    "validate_zone",
    "check_modification_allowed",
    "get_zone_metadata",
    "list_zones",
    "is_core_path",
    "is_app_path",
    "ZONES",
    "plan_modification",
]
