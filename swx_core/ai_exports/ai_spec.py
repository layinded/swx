"""
SwX AI-Aware Layer - Versioned AI Specification
=============================================

Exports versioned AI specification for compatibility.
"""

from datetime import datetime
from typing import Any, Dict


def get_ai_spec() -> Dict[str, Any]:
    """Get versioned AI specification."""
    
    return {
        "ai_metadata_schema_version": "1.0.0",
        "architecture_schema_version": "2.0.0",
        "change_safety_model_version": "1.0.0",
        "swx_version": "2.0.0",
        "generated_at": datetime.now().isoformat(),
        "compatibility": {
            "min_ai_spec_version": "1.0.0",
            "max_ai_spec_version": "1.0.0",
            "supported_export_formats": ["json", "yaml", "graph", "mermaid", "dot"],
            "supported_graph_formats": ["json", "dot", "mermaid", "plantuml"],
            "supported_context_formats": ["compact", "standard", "detailed"]
        },
        "deprecations": [],
        "breaking_changes": [],
        "export_commands": {
            "export_architecture": {
                "command": "swx ai export-architecture",
                "options": ["--format", "--include", "--output", "--pretty"]
            },
            "export_contracts": {
                "command": "swx ai export-contracts",
                "options": ["--format", "--interface", "--include-implementations"]
            },
            "export_graph": {
                "command": "swx ai export-graph",
                "options": ["--type", "--format", "--output"]
            },
            "ai_context": {
                "command": "swx ai ai-context",
                "options": ["--format", "--include", "--token-budget", "--output"]
            },
            "export_agent_rules": {
                "command": "swx ai export-agent-rules",
                "options": ["--format", "--output"]
            },
            "export_ai_spec": {
                "command": "swx ai export-ai-spec",
                "options": ["--format", "--output"]
            },
            "zone_check": {
                "command": "swx ai zone:check",
                "options": ["--operation"]
            },
            "plan_change": {
                "command": "swx ai plan-change",
                "options": ["--format"]
            }
        },
        "safe_zones": {
            "CORE": {
                "mutability": "read-only",
                "description": "Framework core - cannot be modified"
            },
            "APP": {
                "mutability": "safe",
                "description": "Application code - safe to modify within contracts"
            },
            "PROVIDER": {
                "mutability": "override-layer",
                "description": "Service providers - can be overridden via container"
            },
            "PLUGIN": {
                "mutability": "extension-layer",
                "description": "Plugins - extend functionality without modification"
            }
        },
        "metadata_schema": {
            "version": "1.0.0",
            "fields": {
                "SWX_ROLE": {
                    "type": "string",
                    "values": ["Service", "Repository", "Controller", "Guard", "Middleware", "Provider", "Event", "Listener", "Model", "Contract", "Plugin", "Utility", "Configuration"]
                },
                "SWX_SCOPE": {
                    "type": "string",
                    "values": ["Request", "Application", "Domain", "Infrastructure", "Framework"]
                },
                "SWX_DEPENDS_ON": {
                    "type": "array"
                },
                "SWX_MUTATION_ZONE": {
                    "type": "string",
                    "values": ["CORE", "APP", "PROVIDER", "PLUGIN", "READ_ONLY", "SAFE", "EXTENSION"]
                },
                "SWX_CONTRACTS": {
                    "type": "array"
                },
                "SWX_EXPORTS": {
                    "type": "array"
                }
            }
        }
    }
