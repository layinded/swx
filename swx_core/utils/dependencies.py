"""
Dependency Injection Utilities
------------------------------
FastAPI dependency shortcuts and helpers.
"""

import uuid
from typing import Type, TypeVar, Optional, Callable, Any
from functools import lru_cache

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from swx_core.container.container import get_container
from swx_core.guards.base import AuthenticatedUser
from swx_core.guards.jwt_guard import JWTGuard
from swx_core.guards.api_key_guard import APIKeyGuard
from swx_core.utils.errors import UnauthorizedError, ForbiddenError


T = TypeVar("T")

# Security schemes
security = HTTPBearer(auto_error=False)


# =========================================================================
# Container Dependencies
# =========================================================================

def inject(service_name: str) -> Any:
    """
    Dependency to inject a service from the container.
    
    Usage:
        @router.get("/users")
        async def list_users(
            user_service: UserService = Depends(inject("user_service"))
        ):
            return await user_service.list_users()
    """
    def dependency():
        container = get_container()
        return container.make(service_name)
    
    return Depends(dependency)


def inject_service(service_class: Type[T]) -> Callable[[], T]:
    """
    Dependency to inject a service by class.
    
    Usage:
        @router.get("/users")
        async def list_users(
            user_service: UserService = Depends(inject_service(UserService))
        ):
            return await user_service.list_users()
    """
    @lru_cache
    def dependency():
        container = get_container()
        # Try to resolve by class name first
        service_name = service_class.__name__
        if container.bound(service_name):
            return container.make(service_name)
        
        # Fall back to instantiating directly
        return service_class()
    
    return Depends(dependency)


# =========================================================================
# Authentication Dependencies
# =========================================================================

async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[AuthenticatedUser]:
    """
    Get current user if authenticated, otherwise return None.
    
    Usage:
        @router.get("/public")
        async def public_endpoint(user: Optional[AuthenticatedUser] = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello {user.email}"}
            return {"message": "Hello anonymous"}
    """
    if not credentials:
        return None
    
    container = get_container()
    
    # Try JWT guard
    jwt_guard: JWTGuard = container.make("guard.jwt")
    user = await jwt_guard.authenticate(Request)
    if user:
        return user
    
    # Try API key guard
    api_key_guard: APIKeyGuard = container.make("guard.api_key")
    user = await api_key_guard.authenticate(Request)
    if user:
        return user
    
    return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AuthenticatedUser:
    """
    Get current user, require authentication.
    
    Usage:
        @router.get("/profile")
        async def get_profile(user: AuthenticatedUser = Depends(get_current_user)):
            return {"email": user.email, "roles": user.roles}
    """
    if not credentials:
        raise UnauthorizedError("Authentication required")
    
    container = get_container()
    request = Request  # Will be injected by FastAPI
    
    # Try JWT guard
    jwt_guard: JWTGuard = container.make("guard.jwt")
    user = await jwt_guard.authenticate(Request)
    if user:
        return user
    
    # Try API key guard
    api_key_guard: APIKeyGuard = container.make("guard.api_key")
    user = await api_key_guard.authenticate(Request)
    if user:
        return user
    
    raise UnauthorizedError("Invalid authentication credentials")


# =========================================================================
# Authorization Dependencies
# =========================================================================

def require_roles(*roles: str) -> Callable:
    """
    Dependency to require specific roles.
    
    Usage:
        @router.get("/admin")
        async def admin_endpoint(user: AuthenticatedUser = Depends(require_roles("admin"))):
            return {"message": "Admin access granted"}
    """
    async def dependency(user: AuthenticatedUser = Depends(get_current_user)):
        if user.is_superuser:
            return user
        
        for role in roles:
            if user.has_role(role):
                return user
        
        raise ForbiddenError(
            message=f"One of the following roles required: {', '.join(roles)}",
            permission=f"role:{','.join(roles)}",
        )
    
    return Depends(dependency)


def require_permissions(*permissions: str) -> Callable:
    """
    Dependency to require specific permissions.
    
    Usage:
        @router.post("/products")
        async def create_product(
            data: ProductCreate,
            user: AuthenticatedUser = Depends(require_permissions("product:create"))
        ):
            return await product_service.create(data)
    """
    async def dependency(user: AuthenticatedUser = Depends(get_current_user)):
        if user.is_superuser:
            return user
        
        for permission in permissions:
            if user.has_permission(permission):
                return user
        
        raise ForbiddenError(
            message=f"One of the following permissions required: {', '.join(permissions)}",
            permission=f"permission:{','.join(permissions)}",
        )
    
    return Depends(dependency)


def require_superuser() -> Callable:
    """
    Dependency to require superuser.
    
    Usage:
        @router.delete("/system/cache")
        async def clear_cache(user: AuthenticatedUser = Depends(require_superuser())):
            await cache.clear()
            return {"message": "Cache cleared"}
    """
    async def dependency(user: AuthenticatedUser = Depends(get_current_user)):
        if user.is_superuser:
            return user
        
        raise ForbiddenError(
            message="Superuser access required",
            permission="superuser",
        )
    
    return Depends(dependency)


# =========================================================================
# Resource Ownership Dependencies
# =========================================================================

def require_ownership(resource_getter: Callable, resource_id_param: str = "id") -> Callable:
    """
    Dependency to require resource ownership.
    
    Usage:
        @router.put("/products/{product_id}")
        async def update_product(
            product_id: uuid.UUID,
            data: ProductUpdate,
            user: AuthenticatedUser = Depends(require_ownership(product_service.get, "product_id"))
        ):
            return await product_service.update(product_id, data)
    """
    async def dependency(
        user: AuthenticatedUser = Depends(get_current_user),
        **kwargs,
    ):
        resource_id = kwargs.get(resource_id_param)
        
        if not resource_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Resource ID '{resource_id_param}' not provided"
            )
        
        # Get the resource
        resource = await resource_getter(resource_id)
        
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found"
            )
        
        # Check ownership
        if user.is_superuser:
            return user
        
        resource_user_id = getattr(resource, "user_id", None) or getattr(resource, "owner_id", None)
        
        if resource_user_id and str(resource_user_id) == str(user.id):
            return user
        
        raise ForbiddenError(
            message="You don't have permission to access this resource",
            permission="ownership",
        )
    
    return Depends(dependency)


# =========================================================================
# Pagination Dependencies
# =========================================================================

def get_pagination_params(
    page: int = 1,
    per_page: int = 20,
    max_per_page: int = 1000,
) -> "PaginationParams":
    """
    Dependency for pagination parameters.
    
    Usage:
        @router.get("/products")
        async def list_products(pagination: PaginationParams = Depends(get_pagination_params)):
            return await product_service.paginate(page=pagination.page, per_page=pagination.per_page)
    """
    from swx_core.utils.pagination import PaginationParams
    
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20
    if per_page > max_per_page:
        per_page = max_per_page
    
    return PaginationParams(page=page, per_page=per_page)


# =========================================================================
# Request Context Dependencies
# =========================================================================

def get_request_id(request: Request) -> str:
    """
    Get or generate request ID.
    
    Usage:
        @router.get("/users")
        async def list_users(request_id: str = Depends(get_request_id)):
            logger.info(f"[{request_id}] Processing request")
    """
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


def get_client_ip(request: Request) -> str:
    """
    Get client IP address.
    
    Usage:
        @router.post("/login")
        async def login(client_ip: str = Depends(get_client_ip)):
            return await auth_service.login(credentials, client_ip=client_ip)
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


# =========================================================================
# Combined Dependencies
# =========================================================================

class AuthDependencies:
    """Collection of authentication dependencies."""
    
    current_user = staticmethod(get_current_user)
    current_user_optional = staticmethod(get_current_user_optional)
    require_roles = staticmethod(require_roles)
    require_permissions = staticmethod(require_permissions)
    require_superuser = staticmethod(require_superuser)
    require_ownership = staticmethod(require_ownership)


class CommonDependencies:
    """Collection of common dependencies."""
    
    pagination = staticmethod(get_pagination_params)
    request_id = staticmethod(get_request_id)
    client_ip = staticmethod(get_client_ip)