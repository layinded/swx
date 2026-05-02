"""
Validation Decorators
---------------------

Validation decorators and utilities.
"""

import functools
import re
from typing import TypeVar, Callable, Optional, List, Any, Dict, Type
from functools import wraps
from pydantic import BaseModel, ValidationError as PydanticValidationError
from fastapi import HTTPException, status

from swx_core.utils.response import ValidationErrorResponse, ValidationError as ValidationErrorDetail


T = TypeVar("T")


def validate_model(model: Type[BaseModel]):
    """
    Decorator to validate request data against a Pydantic model.
    
    Usage:
        @validate_model(UserCreate)
        async def create_user(data: dict):
            return await service.create(data)
    
    Args:
        model: Pydantic model to validate against
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(data: Dict[str, Any], *args, **kwargs):
            try:
                validated = model(**data)
                return await func(validated.model_dump(), *args, **kwargs)
            except PydanticValidationError as e:
                errors = [
                    ValidationErrorDetail(
                        field=".".join(str(loc) for loc in err["loc"]),
                        message=err["msg"],
                        value=err.get("input"),
                    )
                    for err in e.errors()
                ]
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=ValidationErrorResponse(errors=errors).model_dump(),
                )
        return wrapper
    return decorator


def validate_email(field: str = "email"):
    """
    Decorator to validate email format.
    
    Usage:
        @validate_email("email")
        async def create_user(data: dict):
            return await service.create(data)
    
    Args:
        field: Field name to validate
    """
    email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(data: Dict[str, Any], *args, **kwargs):
            email = data.get(field)
            if email and not email_regex.match(email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid email format for field '{field}'",
                )
            return await func(data, *args, **kwargs)
        return wrapper
    return decorator


def validate_phone(field: str = "phone"):
    """
    Decorator to validate phone number format.
    
    Args:
        field: Field name to validate
    """
    phone_regex = re.compile(r'^\+?[1-9]\d{1,14}$')
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(data: Dict[str, Any], *args, **kwargs):
            phone = data.get(field)
            if phone and not phone_regex.match(phone.replace(" ", "")):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid phone number format for field '{field}'",
                )
            return await func(data, *args, **kwargs)
        return wrapper
    return decorator


def validate_password(
    field: str = "password",
    min_length: int = 8,
    require_uppercase: bool = True,
    require_lowercase: bool = True,
    require_digit: bool = True,
    require_special: bool = True,
):
    """
    Decorator to validate password strength.
    
    Usage:
        @validate_password(min_length=12, require_special=True)
        async def create_user(data: dict):
            return await service.create(data)
    
    Args:
        field: Field name to validate
        min_length: Minimum password length
        require_uppercase: Require at least one uppercase letter
        require_lowercase: Require at least one lowercase letter
        require_digit: Require at least one digit
        require_special: Require at least one special character
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(data: Dict[str, Any], *args, **kwargs):
            password = data.get(field)
            if not password:
                return await func(data, *args, **kwargs)
            
            errors = []
            
            if len(password) < min_length:
                errors.append(f"Password must be at least {min_length} characters")
            
            if require_uppercase and not any(c.isupper() for c in password):
                errors.append("Password must contain at least one uppercase letter")
            
            if require_lowercase and not any(c.islower() for c in password):
                errors.append("Password must contain at least one lowercase letter")
            
            if require_digit and not any(c.isdigit() for c in password):
                errors.append("Password must contain at least one digit")
            
            if require_special and not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password):
                errors.append("Password must contain at least one special character")
            
            if errors:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"errors": errors},
                )
            
            return await func(data, *args, **kwargs)
        return wrapper
    return decorator


def validate_unique(*fields: str):
    """
    Decorator to validate field uniqueness.
    
    Usage:
        @validate_unique("email", "username")
        async def create_user(data: dict):
            # Check uniqueness before creating
            return await service.create(data)
    
    Args:
        *fields: Field names to validate for uniqueness
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(data: Dict[str, Any], *args, **kwargs):
            # This decorator is a placeholder - actual uniqueness check
            # should be done in the service layer with repository access
            return await func(data, *args, **kwargs)
        return wrapper
    return decorator


def validate_required(*fields: str):
    """
    Decorator to validate required fields.
    
    Usage:
        @validate_required("email", "password", "name")
        async def create_user(data: dict):
            return await service.create(data)
    
    Args:
        *fields: Required field names
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(data: Dict[str, Any], *args, **kwargs):
            missing = [field for field in fields if field not in data or data[field] is None]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required fields: {', '.join(missing)}",
                )
            return await func(data, *args, **kwargs)
        return wrapper
    return decorator


def validate_min_value(field: str, min_value: float):
    """
    Decorator to validate minimum value.
    
    Args:
        field: Field name to validate
        min_value: Minimum allowed value
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(data: Dict[str, Any], *args, **kwargs):
            value = data.get(field)
            if value is not None and value < min_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Field '{field}' must be at least {min_value}",
                )
            return await func(data, *args, **kwargs)
        return wrapper
    return decorator


def validate_max_value(field: str, max_value: float):
    """
    Decorator to validate maximum value.
    
    Args:
        field: Field name to validate
        max_value: Maximum allowed value
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(data: Dict[str, Any], *args, **kwargs):
            value = data.get(field)
            if value is not None and value > max_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Field '{field}' must be at most {max_value}",
                )
            return await func(data, *args, **kwargs)
        return wrapper
    return decorator


def validate_length(field: str, min_length: int = None, max_length: int = None):
    """
    Decorator to validate string length.
    
    Args:
        field: Field name to validate
        min_length: Minimum length (optional)
        max_length: Maximum length (optional)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(data: Dict[str, Any], *args, **kwargs):
            value = data.get(field)
            if value is not None:
                if min_length is not None and len(str(value)) < min_length:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Field '{field}' must be at least {min_length} characters",
                    )
                if max_length is not None and len(str(value)) > max_length:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Field '{field}' must be at most {max_length} characters",
                    )
            return await func(data, *args, **kwargs)
        return wrapper
    return decorator


def validate_regex(field: str, pattern: str, message: str = None):
    """
    Decorator to validate field against regex pattern.
    
    Args:
        field: Field name to validate
        pattern: Regex pattern
        message: Custom error message
    """
    def decorator(func: Callable) -> Callable:
        regex = re.compile(pattern)
        
        @wraps(func)
        async def wrapper(data: Dict[str, Any], *args, **kwargs):
            value = data.get(field)
            if value is not None and not regex.match(str(value)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message or f"Field '{field}' has invalid format",
                )
            return await func(data, *args, **kwargs)
        return wrapper
    return decorator


def validate_in(field: str, allowed_values: List[Any]):
    """
    Decorator to validate field is in allowed values.
    
    Args:
        field: Field name to validate
        allowed_values: List of allowed values
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(data: Dict[str, Any], *args, **kwargs):
            value = data.get(field)
            if value is not None and value not in allowed_values:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Field '{field}' must be one of: {', '.join(str(v) for v in allowed_values)}",
                )
            return await func(data, *args, **kwargs)
        return wrapper
    return decorator