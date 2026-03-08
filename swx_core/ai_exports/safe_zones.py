"""
SwX AI-Aware Layer - Safe Zones
==============================

Defines and enforces mutation zones for AI modifications.
"""

import re
from typing import Any, Dict, List, Optional
from pathlib import Path


# Zone definitions
ZONES = {
    "CORE": {
        "mutability": "read-only",
        "description": "Framework core - immutable by design",
        "paths": [
            "swx_core/container/**",
            "swx_core/bootstrap.py",
            "swx_core/router.py",
            "swx_core/main.py",
            "swx_core/__init__.py"
        ],
        "forbidden_operations": ["edit", "delete", "override", "replace"]
    },
    "APP": {
        "mutability": "safe",
        "description": "Application layer - safe modifications within contracts",
        "paths": [
            "swx_app/controllers/**",
            "swx_app/services/**",
            "swx_app/repositories/**",
            "swx_app/models/**",
            "swx_app/routes/**",
            "swx_app/listeners/**",
            "swx_app/middleware/**",
            "swx_app/providers/**"
        ],
        "allowed_operations": ["create", "edit", "delete", "extend", "implement"]
    },
    "PROVIDER": {
        "mutability": "override-layer",
        "description": "Service providers - can be overridden via container",
        "paths": [
            "swx_core/providers/*.py",
            "swx_app/providers/**"
        ],
        "allowed_operations": ["override_binding", "extend_provider", "create_new_provider"],
        "mechanism": "Container binding override"
    },
    "PLUGIN": {
        "mutability": "extension-layer",
        "description": "Plugins - extend functionality without modification",
        "paths": [
            "swx_plugins/**",
            "swx_core/plugins/**"
        ],
        "allowed_operations": ["install", "uninstall", "configure", "hook"],
        "constraints": ["Cannot override other plugins without explicit rule"]
    }
}


def get_zone_for_path(file_path: str) -> Dict[str, Any]:
    """Get zone classification for a file path."""
    
    # Normalize path
    file_path = str(file_path).replace("\\", "/")
    
    # Check each zone
    for zone_name, zone_def in ZONES.items():
        for pattern in zone_def.get("paths", []):
            # Convert glob pattern to regex
            regex_pattern = pattern.replace("**", ".*").replace("*", "[^/]+")
            
            if re.match(regex_pattern, file_path):
                return {
                    "zone": zone_name,
                    "mutability": zone_def.get("mutability"),
                    "description": zone_def.get("description"),
                    "allowed_operations": zone_def.get("allowed_operations", []),
                    "forbidden_operations": zone_def.get("forbidden_operations", [])
                }
    
    # Default to APP if not matched (for swx_app files)
    if "swx_app/" in file_path:
        return {
            "zone": "APP",
            "mutability": "safe",
            "description": "Application code - safe to modify",
            "allowed_operations": ["create", "edit", "delete", "extend", "implement"],
            "forbidden_operations": []
        }
    
    # Unknown zone
    return {
        "zone": "UNKNOWN",
        "mutability": "unknown",
        "description": "Unknown zone",
        "allowed_operations": [],
        "forbidden_operations": []
    }


def validate_zone(file_path: str, operation: str) -> Dict[str, Any]:
    """Validate if operation is allowed in zone."""
    
    zone_info = get_zone_for_path(file_path)
    zone_name = zone_info.get("zone", "UNKNOWN")
    
    # Check if operation is allowed
    if operation in zone_info.get("forbidden_operations", []):
        return {
            "allowed": False,
            "zone": zone_name,
            "mutability": zone_info.get("mutability"),
            "reason": f"Operation '{operation}' is forbidden in {zone_name} zone"
        }
    
    # Check mutability
    if zone_info.get("mutability") == "read-only":
        return {
            "allowed": False,
            "zone": zone_name,
            "mutability": zone_info.get("mutability"),
            "reason": f"Zone {zone_name} is read-only"
        }
    
    return {
        "allowed": True,
        "zone": zone_name,
        "mutability": zone_info.get("mutability"),
        "reason": None
    }


def check_modification_allowed(file_path: str, operation: str = "edit") -> bool:
    """Check if modification is allowed (simple boolean check)."""
    result = validate_zone(file_path, operation)
    return result.get("allowed", False)


def get_zone_metadata(zone_name: str) -> Optional[Dict[str, Any]]:
    """Get full metadata for a zone."""
    return ZONES.get(zone_name)


def list_zones() -> List[str]:
    """List all available zones."""
    return list(ZONES.keys())


def is_core_path(file_path: str) -> bool:
    """Check if path is in CORE zone."""
    return get_zone_for_path(file_path).get("zone") == "CORE"


def is_app_path(file_path: str) -> bool:
    """Check if path is in APP zone."""
    return get_zone_for_path(file_path).get("zone") == "APP"


# Export zone constants for easy access
CORE = "CORE"
APP = "APP"
PROVIDER = "PROVIDER"
PLUGIN = "PLUGIN"
