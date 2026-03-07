"""
SwX Route Versioning helpers.

Provides utilities for API versioning:
- Version negotiation
- Deprecation warnings
- Version routing helpers
- Route versioning decorators
"""
import re
import warnings
from functools import wraps
from typing import Optional, Callable, Any, List, Dict, TypeVar, Union
from enum import Enum

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from swx_core.config.settings import settings


# Type variables for generic decorators
F = TypeVar('F', bound=Callable[..., Any])


class VersionStatus(str, Enum):
    """Status of an API version."""
    STABLE = "stable"          # Current stable version
    DEPRECATED = "deprecated"  # Will be removed in future
    SUNSET = "sunset"          # Scheduled for removal
    BETA = "beta"              # Preview/beta version
    INTERNAL = "internal"      # Internal use only


class VersionInfo(BaseModel):
    """Information about an API version."""
    version: str
    status: VersionStatus
    release_date: Optional[str] = None
    deprecation_date: Optional[str] = None
    sunset_date: Optional[str] = None
    description: Optional[str] = None
    migration_guide_url: Optional[str] = None


# Default version statuses
DEFAULT_VERSION_STATUS: Dict[str, VersionStatus] = {
    "v1": VersionStatus.STABLE,
    "v2": VersionStatus.STABLE,
}


def parse_version(version_str: str) -> tuple[int, int]:
    """
    Parse a version string into major and minor components.
    
    Args:
        version_str: Version string like 'v1', 'v2.1', '1.0'
    
    Returns:
        Tuple of (major, minor) version numbers
    
    Examples:
        >>> parse_version("v1")
        (1, 0)
        >>> parse_version("v2.1")
        (2, 1)
        >>> parse_version("1.5")
        (1, 5)
    """
    # Remove 'v' prefix if present
    clean_version = version_str.lower().lstrip('v')
    
    # Split by dot
    parts = clean_version.split('.')
    
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        return (major, minor)
    except (ValueError, IndexError):
        return (0, 0)


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two version strings.
    
    Returns:
        -1 if v1 < v2
         0 if v1 == v2
         1 if v1 > v2
    
    Examples:
        >>> compare_versions("v1", "v2")
        -1
        >>> compare_versions("v2.1", "v2.0")
        1
    """
    maj1, min1 = parse_version(v1)
    maj2, min2 = parse_version(v2)
    
    if maj1 < maj2:
        return -1
    elif maj1 > maj2:
        return 1
    elif min1 < min2:
        return -1
    elif min1 > min2:
        return 1
    else:
        return 0


def get_latest_version(versions: List[str]) -> str:
    """
    Get the latest version from a list of version strings.
    
    Args:
        versions: List of version strings
    
    Returns:
        The latest version string
    
    Examples:
        >>> get_latest_version(["v1", "v2", "v1.5"])
        'v2'
    """
    if not versions:
        raise ValueError("No versions provided")
    
    return max(versions, key=lambda v: parse_version(v))


def is_valid_version(version: str, allowed_versions: Optional[List[str]] = None) -> bool:
    """
    Check if a version string is valid.
    
    Args:
        version: Version string to validate
        allowed_versions: List of allowed versions (uses settings.API_VERSIONS if None)
    
    Returns:
        True if version is valid, False otherwise
    """
    if allowed_versions is None:
        allowed_versions = getattr(settings, 'API_VERSIONS', ['v1'])
    
    return version in allowed_versions


def get_version_status(version: str) -> VersionStatus:
    """
    Get the status of a specific API version.
    
    Args:
        version: Version string
    
    Returns:
        VersionStatus enum value
    """
    return DEFAULT_VERSION_STATUS.get(version, VersionStatus.STABLE)


def set_version_status(version: str, status: VersionStatus) -> None:
    """
    Set the status of a specific API version.
    
    Args:
        version: Version string
        status: VersionStatus to set
    """
    DEFAULT_VERSION_STATUS[version] = status


# ------------------------------------------------------------------------------
# Deprecation Warnings
# ------------------------------------------------------------------------------

class DeprecationWarningMiddleware:
    """Middleware for adding deprecation headers to responses."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Process request and add deprecation headers
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                # Add deprecation headers if version is deprecated
                path = scope.get("path", "")
                version_match = re.search(r'/api/(v\d+)', path)
                
                if version_match:
                    version = version_match.group(1)
                    status = get_version_status(version)
                    
                    if status == VersionStatus.DEPRECATED:
                        headers = dict(message.get("headers", []))
                        headers[b"x-api-deprecated"] = b"true"
                        headers[b"x-api-sunset"] = b"See documentation for sunset date"
                        message["headers"] = list(headers.items())
            
            await send(message)
        
        await self.app(scope, receive, send_with_headers)


def deprecated_version(
    version: str,
    replacement_version: Optional[str] = None,
    sunset_date: Optional[str] = None,
    migration_guide_url: Optional[str] = None
) -> Callable[[F], F]:
    """
    Decorator to mark an endpoint as deprecated.
    
    Adds deprecation headers to responses and logs warnings.
    
    Args:
        version: The version being deprecated
        replacement_version: The version to use instead
        sunset_date: When the deprecated version will be removed
        migration_guide_url: URL to migration documentation
    
    Usage:
        @deprecated_version("v1", replacement_version="v2", sunset_date="2025-12-31")
        async def get_users_v1():
            return {"users": []}
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Log deprecation warning
            warnings.warn(
                f"API version {version} is deprecated. "
                f"Use {replacement_version} instead. "
                f"Sunset date: {sunset_date}",
                DeprecationWarning,
                stacklevel=2
            )
            
            # Add deprecation headers to response
            response = await func(*args, **kwargs)
            
            if isinstance(response, Response):
                response.headers["X-API-Deprecated"] = "true"
                if replacement_version:
                    response.headers["X-API-Replacement"] = replacement_version
                if sunset_date:
                    response.headers["X-API-Sunset"] = sunset_date
                if migration_guide_url:
                    response.headers["X-API-Migration-Guide"] = migration_guide_url
            
            return response
        
        return wrapper  # type: ignore
    
    return decorator


# ------------------------------------------------------------------------------
# Version Routing Helpers
# ------------------------------------------------------------------------------

def create_versioned_router(
    prefix: str,
    versions: List[str],
    default_version: Optional[str] = None
) -> Dict[str, APIRouter]:
    """
    Create multiple versioned routers for the same resource.
    
    Args:
        prefix: Base path prefix (e.g., "/users")
        versions: List of versions to create routers for
        default_version: Default version to use (uses latest if None)
    
    Returns:
        Dictionary mapping version strings to APIRouter instances
    
    Usage:
        versioned_routers = create_versioned_router("/users", ["v1", "v2"])
        v1_router = versioned_routers["v1"]
        v2_router = versioned_routers["v2"]
        
        @v1_router.get("/")
        async def list_users_v1():
            return {"version": "v1"}
        
        @v2_router.get("/")
        async def list_users_v2():
            return {"version": "v2", "users": []}
    """
    routers = {}
    
    for version in versions:
        version_prefix = f"/{version}{prefix}"
        routers[version] = APIRouter(prefix=version_prefix, tags=[f"{prefix.strip('/')} - {version}"])
    
    if default_version is None:
        default_version = get_latest_version(versions)
    
    routers["default"] = routers[default_version]
    
    return routers


def version_route(
    versions: Dict[str, Callable],
    default: Optional[str] = None
) -> Callable:
    """
    Route requests to different handlers based on API version.
    
    Args:
        versions: Dictionary mapping version strings to handler functions
        default: Default version to use if no version specified
    
    Returns:
        Handler function that routes to appropriate version
    
    Usage:
        @router.get("/users")
        @version_route({
            "v1": list_users_v1,
            "v2": list_users_v2
        }, default="v1")
        async def list_users(request: Request):
            ...
    """
    # Determine default version
    if default is None:
        default = get_latest_version(list(versions.keys()))
    
    async def handler(request: Request, *args, **kwargs):
        # Extract version from request
        version = request.path_params.get("version", default)
        
        # Check if version is valid
        if version not in versions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid API version: {version}. Valid versions: {list(versions.keys())}"
            )
        
        # Route to appropriate handler
        return await versions[version](request, *args, **kwargs)
    
    return handler


def negotiate_version(
    request: Request,
    supported_versions: List[str],
    default_version: Optional[str] = None
) -> str:
    """
    Negotiate the API version based on request headers.
    
    Checks for version in:
    1. X-API-Version header
    2. Accept header (application/vnd.api+json; version=1)
    3. Query parameter (?version=v1)
    4. Default version
    
    Args:
        request: FastAPI Request object
        supported_versions: List of supported versions
        default_version: Default version if none specified
    
    Returns:
        Negotiated version string
    
    Usage:
        @router.get("/users")
        async def list_users(request: Request):
            version = negotiate_version(request, ["v1", "v2"])
            # Use version to route to appropriate handler
    """
    # Check X-API-Version header
    version_header = request.headers.get("X-API-Version")
    if version_header and is_valid_version(version_header, supported_versions):
        return version_header
    
    # Check Accept header
    accept_header = request.headers.get("Accept", "")
    version_match = re.search(r'version=(\d+(?:\.\d+)?)', accept_header)
    if version_match:
        version = f"v{version_match.group(1)}"
        # Normalize version (v1 -> v1.0)
        version = f"v{parse_version(version)[0]}"
        if is_valid_version(version, supported_versions):
            return version
    
    # Check query parameter
    version_param = request.query_params.get("version")
    if version_param and is_valid_version(version_param, supported_versions):
        return version_param
    
    # Return default
    if default_version:
        return default_version
    
    # Return latest supported version
    return get_latest_version(supported_versions)


# ------------------------------------------------------------------------------
# Version Router Class
# ------------------------------------------------------------------------------

class VersionedRouter:
    """
    A router that manages multiple API versions.
    
    Usage:
        router = VersionedRouter("/users", ["v1", "v2"])
        
        @router.route("v1", "/")
        async def list_users_v1():
            return {"version": "v1"}
        
        @router.route("v2", "/")
        async def list_users_v2():
            return {"version": "v2"}
        
        # Get all version routers
        for version, api_router in router.get_routers():
            app.include_router(api_router)
    """
    
    def __init__(
        self,
        prefix: str,
        versions: List[str],
        default_version: Optional[str] = None,
        version_statuses: Optional[Dict[str, VersionStatus]] = None
    ):
        """
        Initialize a versioned router.
        
        Args:
            prefix: Base path prefix
            versions: List of supported versions
            default_version: Default version (uses latest if None)
            version_statuses: Dictionary of version statuses
        """
        self.prefix = prefix.rstrip("/")
        self.versions = versions
        self.default_version = default_version or get_latest_version(versions)
        self.version_statuses = version_statuses or DEFAULT_VERSION_STATUS.copy()
        
        # Create routers for each version
        self._routers: Dict[str, APIRouter] = {}
        for version in versions:
            version_prefix = f"/{version}{self.prefix}"
            self._routers[version] = APIRouter(
                prefix=version_prefix,
                tags=[f"{prefix.strip('/')} - {version}"]
            )
    
    def route(self, version: str, path: str, **kwargs):
        """
        Register a route for a specific version.
        
        Args:
            version: API version
            path: Route path
            **kwargs: Additional route arguments
        
        Returns:
            Decorator function
        """
        if version not in self._routers:
            raise ValueError(f"Version {version} not in supported versions: {self.versions}")
        
        return self._routers[version].api_route(path, **kwargs)
    
    def get_router(self, version: str) -> APIRouter:
        """Get the router for a specific version."""
        if version not in self._routers:
            raise ValueError(f"Version {version} not supported")
        return self._routers[version]
    
    def get_routers(self) -> List[tuple[str, APIRouter]]:
        """Get all version routers."""
        return [(v, r) for v, r in self._routers.items()]
    
    def add_version(self, version: str, status: VersionStatus = VersionStatus.STABLE) -> None:
        """Add a new version to the router."""
        if version in self._routers:
            raise ValueError(f"Version {version} already exists")
        
        version_prefix = f"/{version}{self.prefix}"
        self._routers[version] = APIRouter(
            prefix=version_prefix,
            tags=[f"{self.prefix.strip('/')} - {version}"]
        )
        self.versions.append(version)
        self.version_statuses[version] = status
    
    def deprecate_version(
        self,
        version: str,
        sunset_date: Optional[str] = None,
        migration_guide: Optional[str] = None
    ) -> None:
        """
        Mark a version as deprecated.
        
        Args:
            version: Version to deprecate
            sunset_date: When the version will be removed
            migration_guide: URL to migration documentation
        """
        if version not in self._routers:
            raise ValueError(f"Version {version} not supported")
        
        self.version_statuses[version] = VersionStatus.DEPRECATED
        
        # Add deprecation header middleware
        original_router = self._routers[version]
        
        # Store metadata
        original_router.deprecated = True  # type: ignore
        original_router.sunset_date = sunset_date  # type: ignore
        original_router.migration_guide = migration_guide  # type: ignore
    
    def get_version_info(self, version: str) -> VersionInfo:
        """Get detailed information about a version."""
        status = self.version_statuses.get(version, VersionStatus.STABLE)
        
        if version not in self._routers:
            raise ValueError(f"Version {version} not supported")
        
        router = self._routers[version]
        
        return VersionInfo(
            version=version,
            status=status,
            sunset_date=getattr(router, 'sunset_date', None),
            description=f"API version {version} for {self.prefix}",
            migration_guide_url=getattr(router, 'migration_guide', None)
        )


# ------------------------------------------------------------------------------
# Convenience Functions
# ------------------------------------------------------------------------------

def list_versions() -> List[VersionInfo]:
    """
    List all available API versions with their status.
    
    Returns:
        List of VersionInfo objects
    """
    versions = getattr(settings, 'API_VERSIONS', ['v1'])
    return [
        VersionInfo(
            version=v,
            status=get_version_status(v),
            description=f"API version {v}"
        )
        for v in versions
    ]


def check_version_compatibility(requested_version: str, minimum_version: str) -> bool:
    """
    Check if a requested version meets minimum version requirements.
    
    Args:
        requested_version: Version being requested
        minimum_version: Minimum required version
    
    Returns:
        True if compatible, False otherwise
    
    Usage:
        @router.get("/users")
        async def list_users(request: Request):
            if not check_version_compatibility(request.headers.get("X-API-Version", "v1"), "v2"):
                raise HTTPException(400, "This endpoint requires API version v2 or higher")
    """
    return compare_versions(requested_version, minimum_version) >= 0


__all__ = [
    # Enums
    "VersionStatus",
    
    # Models
    "VersionInfo",
    
    # Version parsing/comparison
    "parse_version",
    "compare_versions",
    "get_latest_version",
    "is_valid_version",
    "get_version_status",
    "set_version_status",
    
    # Deprecation
    "DeprecationWarningMiddleware",
    "deprecated_version",
    
    # Routing
    "create_versioned_router",
    "version_route",
    "negotiate_version",
    "VersionedRouter",
    
    # Convenience
    "list_versions",
    "check_version_compatibility",
]