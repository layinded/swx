"""
Rate Limit Registry
-------------------
Central registry for rate limit configurations.

No hardcoded limits in code - all limits defined here.
"""

from typing import Dict, Any, Optional
from swx_core.middleware.logging_middleware import logger


# Default rate limits by plan and feature
RATE_LIMITS: Dict[str, Dict[str, Dict[str, Dict[str, int]]]] = {
    "free": {
        "api_requests": {
            "read": {"burst": 10000, "sustained": 100000, "daily": 1000000},
            "write": {"burst": 5000, "sustained": 50000, "daily": 500000},
            "delete": {"burst": 2000, "sustained": 10000, "daily": 100000},
        },
        "billing": {
            "read": {"burst": 1000, "sustained": 10000, "daily": 100000},
            "write": {"burst": 500, "sustained": 5000, "daily": 50000},
        },
        "search": {
            "read": {"burst": 1000, "sustained": 10000, "daily": 100000},
        },
        "export": {
            "write": {"burst": 500, "sustained": 2000, "daily": 10000},
        },
    },
    "pro": {
        "api_requests": {
            "read": {"burst": 200, "sustained": 10000, "daily": 100000},
            "write": {"burst": 100, "sustained": 5000, "daily": 50000},
            "delete": {"burst": 50, "sustained": 1000, "daily": 10000},
        },
        "billing": {
            "read": {"burst": 50, "sustained": 1000, "daily": 10000},
            "write": {"burst": 20, "sustained": 500, "daily": 5000},
        },
        "search": {
            "read": {"burst": 100, "sustained": 5000, "daily": 50000},
        },
        "export": {
            "write": {"burst": 20, "sustained": 100, "daily": 1000},
        },
    },
    "team": {
        "api_requests": {
            "read": {"burst": 500, "sustained": 50000, "daily": 500000},
            "write": {"burst": 200, "sustained": 20000, "daily": 200000},
            "delete": {"burst": 100, "sustained": 5000, "daily": 50000},
        },
        "billing": {
            "read": {"burst": 100, "sustained": 5000, "daily": 50000},
            "write": {"burst": 50, "sustained": 2000, "daily": 20000},
        },
        "search": {
            "read": {"burst": 200, "sustained": 20000, "daily": 200000},
        },
        "export": {
            "write": {"burst": 50, "sustained": 500, "daily": 5000},
        },
    },
    "enterprise": {
        "api_requests": {
            "read": {"burst": 1000, "sustained": 100000, "daily": 1000000},
            "write": {"burst": 500, "sustained": 50000, "daily": 500000},
            "delete": {"burst": 200, "sustained": 10000, "daily": 100000},
        },
        "billing": {
            "read": {"burst": 200, "sustained": 10000, "daily": 100000},
            "write": {"burst": 100, "sustained": 5000, "daily": 50000},
        },
        "search": {
            "read": {"burst": 500, "sustained": 50000, "daily": 500000},
        },
        "export": {
            "write": {"burst": 100, "sustained": 2000, "daily": 20000},
        },
    },
    "admin": {
        "api_requests": {
            "read": {"burst": 1000, "sustained": 100000, "daily": 1000000},
            "write": {"burst": 500, "sustained": 50000, "daily": 500000},
            "delete": {"burst": 200, "sustained": 10000, "daily": 100000},
        },
        "billing": {
            "read": {"burst": 500, "sustained": 50000, "daily": 500000},
            "write": {"burst": 200, "sustained": 20000, "daily": 200000},
        },
        "search": {
            "read": {"burst": 1000, "sustained": 100000, "daily": 1000000},
        },
        "export": {
            "write": {"burst": 200, "sustained": 5000, "daily": 50000},
        },
    },
    "system": {
        "api_requests": {
            "read": {"burst": 10000, "sustained": 1000000, "daily": 10000000},
            "write": {"burst": 5000, "sustained": 500000, "daily": 5000000},
            "delete": {"burst": 1000, "sustained": 100000, "daily": 1000000},
        },
    },
    "anonymous": {
        "api_requests": {
            "read": {"burst": 10000, "sustained": 100000, "daily": 1000000},
            "write": {"burst": 5000, "sustained": 50000, "daily": 500000},
        },
    },
}


def get_limit(
    plan: str,
    feature: str,
    endpoint_class: str,
    limit_type: str = "burst"
) -> int:
    """
    Get rate limit for a plan/feature/endpoint combination.
    
    Args:
        plan: Billing plan (free, pro, team, enterprise, admin, system, anonymous)
        feature: Feature name (api_requests, billing, search, export)
        endpoint_class: Endpoint class (read, write, delete)
        limit_type: Limit type (burst, sustained, daily)
    
    Returns:
        Rate limit value, or 0 if not found (fail-closed)
    """
    plan_limits = RATE_LIMITS.get(plan, {})
    feature_limits = plan_limits.get(feature, {})
    endpoint_limits = feature_limits.get(endpoint_class, {})
    limit = endpoint_limits.get(limit_type, 0)
    
    if limit == 0:
        # Fail-closed: if limit not found, default to very restrictive
        logger.warning(
            f"Rate limit not found for plan={plan}, feature={feature}, "
            f"endpoint={endpoint_class}, type={limit_type}. Using fail-closed default."
        )
        return 1  # Very restrictive default
    
    return limit


def resolve_plan(actor_type: str, billing_plan: Optional[str] = None) -> str:
    """
    Resolve billing plan from actor type and billing info.
    
    Args:
        actor_type: Actor type (system, admin, user, anonymous)
        billing_plan: Billing plan from subscription (optional)
    
    Returns:
        Plan identifier for rate limit lookup
    """
    # System and admin actors use their own plans
    if actor_type in ("system", "admin"):
        return actor_type
    
    # Anonymous users
    if actor_type == "anonymous":
        return "anonymous"
    
    # Regular users: use billing plan or default to free
    if actor_type == "user":
        return billing_plan or "free"
    
    # Default to anonymous (most restrictive)
    return "anonymous"


def get_endpoint_class(method: str) -> str:
    """
    Map HTTP method to endpoint class.
    
    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
    
    Returns:
        Endpoint class (read, write, delete)
    """
    method_upper = method.upper()
    if method_upper == "GET":
        return "read"
    elif method_upper in ("POST", "PUT", "PATCH"):
        return "write"
    elif method_upper == "DELETE":
        return "delete"
    else:
        return "read"  # Default to read


def get_feature_from_path(path: str) -> str:
    """
    Determine feature from request path.
    
    Args:
        path: Request path (e.g., "/api/billing/accounts")
    
    Returns:
        Feature name (api_requests, billing, search, export)
    """
    path_lower = path.lower()
    
    if "/billing" in path_lower:
        return "billing"
    elif "/search" in path_lower or "/query" in path_lower:
        return "search"
    elif "/export" in path_lower or "/download" in path_lower:
        return "export"
    else:
        return "api_requests"  # Default
