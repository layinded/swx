"""
Error Handling Utilities
------------------------
Standardized error handling and exception classes.
"""

from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status


class SwXError(Exception):
    """Base exception for SwX framework."""
    
    def __init__(
        self,
        message: str = "An error occurred",
        code: str = "ERROR",
        details: Dict[str, Any] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
        }


class ValidationError(SwXError):
    """Validation error."""
    
    def __init__(
        self,
        message: str = "Validation failed",
        errors: List[Dict[str, str]] = None,
    ):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={"errors": errors or []},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class NotFoundError(SwXError):
    """Resource not found error."""
    
    def __init__(self, resource: str = "Resource", resource_id: str = None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with id '{resource_id}' not found"
        
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedError(SwXError):
    """Authentication required error."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(SwXError):
    """Permission denied error."""
    
    def __init__(self, message: str = "Permission denied", permission: str = None):
        details = {}
        if permission:
            details["permission"] = permission
        
        super().__init__(
            message=message,
            code="FORBIDDEN",
            details=details,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ConflictError(SwXError):
    """Resource conflict error."""
    
    def __init__(self, message: str = "Resource conflict", resource: str = None):
        details = {}
        if resource:
            details["resource"] = resource
        
        super().__init__(
            message=message,
            code="CONFLICT",
            details=details,
            status_code=status.HTTP_409_CONFLICT,
        )


class RateLimitError(SwXError):
    """Rate limit exceeded error."""
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            message=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class ServiceUnavailableError(SwXError):
    """Service unavailable error."""
    
    def __init__(self, service: str = None, message: str = "Service temporarily unavailable"):
        details = {}
        if service:
            details["service"] = service
        
        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            details=details,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class DatabaseError(SwXError):
    """Database operation error."""
    
    def __init__(self, message: str = "Database operation failed", operation: str = None):
        details = {}
        if operation:
            details["operation"] = operation
        
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ExternalServiceError(SwXError):
    """External service error."""
    
    def __init__(self, service: str, message: str = "External service error"):
        super().__init__(
            message=message,
            code="EXTERNAL_SERVICE_ERROR",
            details={"service": service},
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class ConfigurationError(SwXError):
    """Configuration error."""
    
    def __init__(self, message: str = "Configuration error"):
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# HTTP Exception wrappers
def not_found(resource: str = "Resource", resource_id: str = None) -> HTTPException:
    """Raise HTTP 404 Not Found."""
    raise NotFoundError(resource, resource_id)


def unauthorized(message: str = "Authentication required") -> HTTPException:
    """Raise HTTP 401 Unauthorized."""
    raise UnauthorizedError(message)


def forbidden(message: str = "Permission denied", permission: str = None) -> HTTPException:
    """Raise HTTP 403 Forbidden."""
    raise ForbiddenError(message, permission)


def bad_request(message: str = "Bad request", details: Dict[str, Any] = None) -> HTTPException:
    """Raise HTTP 400 Bad Request."""
    raise SwXError(message=message, code="BAD_REQUEST", details=details or {})


def conflict(message: str = "Resource conflict", resource: str = None) -> HTTPException:
    """Raise HTTP 409 Conflict."""
    raise ConflictError(message, resource)


def rate_limited(retry_after: int = 60) -> HTTPException:
    """Raise HTTP 429 Too Many Requests."""
    raise RateLimitError(retry_after)


def service_unavailable(service: str = None, message: str = None) -> HTTPException:
    """Raise HTTP 503 Service Unavailable."""
    raise ServiceUnavailableError(service, message)