"""
SwX AI-Aware Layer - Change Planning Protocol
==========================================

Provides automated change impact analysis and planning.
"""

import re
from typing import Any, Dict, List

from swx_core.ai_exports.safe_zones import get_zone_for_path, validate_zone


def plan_modification(description: str) -> Dict[str, Any]:
    """Plan a modification with impact analysis."""
    
    # Analyze description to determine affected components
    affected = _analyze_description(description)
    
    # Determine files to modify
    files = _determine_files(affected)
    
    # Assess risk
    risk = _assess_risk(files, affected)
    
    # Check contracts
    contracts = _check_contracts(affected)
    
    return {
        "change_description": description,
        "timestamp": "2026-03-08T12:00:00Z",
        "impact_analysis": {
            "scope": affected.get("scope", "local"),
            "affected_components": affected.get("components", []),
            "breaking_change": risk.get("breaking", False),
            "migration_needed": risk.get("migration", False)
        },
        "files_to_modify": files,
        "contracts_to_respect": contracts,
        "risk_level": risk.get("level", "medium"),
        "breaking_change": risk.get("breaking", False),
        "recommendations": _get_recommendations(affected, risk)
    }


def _analyze_description(description: str) -> Dict[str, Any]:
    """Analyze description to determine affected components."""
    
    description = description.lower()
    components = []
    scope = "local"
    
    # Determine affected components
    if "rate limit" in description or "rate limit" in description:
        components.append("rate_limiter")
        if "multi-tenant" in description or "tenant" in description:
            components.append("tenant_context")
    
    if "audit" in description or "logging" in description:
        components.append("audit_logger")
    
    if "api key" in description or "api-key" in description:
        components.append("api_key_guard")
    
    if "billing" in description or "subscription" in description or "plan" in description:
        components.append("billing_service")
        components.append("entitlement_resolver")
    
    if "event" in description or "listener" in description:
        components.append("event_dispatcher")
    
    if "plugin" in description:
        components.append("plugin_manager")
    
    if "provider" in description or "service" in description:
        components.append("service_provider")
    
    # Determine scope
    if len(components) > 2:
        scope = "module"
    if len(components) > 4:
        scope = "system"
    
    return {
        "components": components,
        "scope": scope
    }


def _determine_files(affected: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Determine files to modify based on affected components."""
    
    files = []
    components = affected.get("components", [])
    
    component_to_files = {
        "rate_limiter": [
            {"path": "swx_app/providers/rate_limit_provider.py", "action": "extend", "zone": "PROVIDER"}
        ],
        "audit_logger": [
            {"path": "swx_app/services/audit_service.py", "action": "create", "zone": "APP"},
            {"path": "swx_app/middleware/audit_middleware.py", "action": "create", "zone": "APP"}
        ],
        "api_key_guard": [
            {"path": "swx_app/guards/api_key_guard.py", "action": "create", "zone": "APP"},
            {"path": "swx_app/routes/external.py", "action": "modify", "zone": "APP"}
        ],
        "billing_service": [
            {"path": "swx_app/services/entitlement_service.py", "action": "create", "zone": "APP"},
            {"path": "swx_app/middleware/plan_restriction.py", "action": "create", "zone": "APP"}
        ],
        "event_dispatcher": [
            {"path": "swx_app/listeners/custom_listener.py", "action": "create", "zone": "APP"}
        ],
        "plugin_manager": [
            {"path": "swx_plugins/custom/", "action": "create", "zone": "PLUGIN"}
        ],
        "service_provider": [
            {"path": "swx_app/providers/custom_provider.py", "action": "create", "zone": "PROVIDER"}
        ],
        "tenant_context": [
            {"path": "swx_app/services/tenant_service.py", "action": "create", "zone": "APP"}
        ]
    }
    
    for component in components:
        if component in component_to_files:
            files.extend(component_to_files[component])
    
    return files


def _assess_risk(files: List[Dict[str, Any]], affected: Dict[str, Any]) -> Dict[str, Any]:
    """Assess risk level of modification."""
    
    risk = {
        "level": "low",
        "breaking": False,
        "migration": False,
        "factors": []
    }
    
    # Check for CORE zone modifications
    for f in files:
        if f.get("zone") == "CORE":
            risk["level"] = "high"
            risk["breaking"] = True
            risk["factors"].append("CORE zone modification")
    
    # Check for breaking changes
    scope = affected.get("scope", "local")
    if scope == "system":
        risk["level"] = "high"
        risk["breaking"] = True
        risk["factors"].append("System-wide change")
    
    # Check for migrations
    if "billing" in affected.get("components", []):
        risk["migration"] = True
        risk["factors"].append("Billing changes may require data migration")
    
    # Escalate risk for multiple components
    if len(affected.get("components", [])) > 3:
        if risk["level"] == "low":
            risk["level"] = "medium"
        risk["factors"].append(f"Multiple components affected ({len(affected.get('components', []))})")
    
    return risk


def _check_contracts(affected: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check contracts that must be respected."""
    
    contracts = []
    components = affected.get("components", [])
    
    if "rate_limiter" in components:
        contracts.append({
            "contract_name": "RateLimiterProtocol",
            "constraint": "Must implement check_limit() and get_limit()",
            "methods_affected": ["check_limit"]
        })
    
    if "billing_service" in components or "entitlement_resolver" in components:
        contracts.append({
            "contract_name": "EntitlementProtocol",
            "constraint": "Must implement has_feature() and check_limit()",
            "methods_affected": ["has_feature", "check_limit"]
        })
    
    if "service_provider" in components:
        contracts.append({
            "contract_name": "ServiceProvider",
            "constraint": "Must implement register() and boot()",
            "methods_affected": ["register", "boot"]
        })
    
    return contracts


def _get_recommendations(affected: Dict[str, Any], risk: Dict[str, Any]) -> List[str]:
    """Get recommendations for the modification."""
    
    recommendations = []
    
    # Risk-based recommendations
    if risk["level"] == "high":
        recommendations.append("Consider breaking this into smaller changes")
        recommendations.append("Run full test suite before deploying")
    
    # Component-specific recommendations
    components = affected.get("components", [])
    
    if "billing" in components:
        recommendations.append("Test thoroughly with different subscription tiers")
        recommendations.append("Ensure backwards compatibility for API responses")
    
    if "rate_limiter" in components:
        recommendations.append("Test rate limiting with multiple concurrent requests")
        recommendations.append("Consider Redis for distributed rate limiting")
    
    if "event_dispatcher" in components:
        recommendations.append("Keep event handlers idempotent")
        recommendations.append("Consider async event handling for performance")
    
    if not recommendations:
        recommendations.append("Run existing test suite to verify no regressions")
    
    return recommendations
