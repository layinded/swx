"""
API Response Utilities
----------------------
Standardized API response utilities.
"""

from typing import Generic, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper.
    
    Usage:
        @router.get("/items/{id}")
        async def get_item(id: uuid.UUID) -> APIResponse[ItemPublic]:
            item = await service.get(id)
            return APIResponse.ok(data=item, message="Item retrieved successfully")
        
        @router.post("/items")
        async def create_item(data: ItemCreate) -> APIResponse[ItemPublic]:
            item = await service.create(data.model_dump())
            return APIResponse.ok(data=item, message="Item created successfully", status_code=201)
    """
    success: bool = Field(default=True, description="Whether the request was successful")
    data: Optional[T] = Field(default=None, description="Response data")
    message: Optional[str] = Field(default=None, description="Human-readable message")
    errors: Optional[List[str]] = Field(default=None, description="List of error messages")
    meta: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    
    class Config:
        arbitrary_types_allowed = True
    
    @classmethod
    def ok(
        cls,
        data: T = None,
        message: str = None,
        meta: Dict[str, Any] = None,
    ) -> "APIResponse[T]":
        """
        Create a successful response.
        
        Args:
            data: Response data
            message: Human-readable message
            meta: Additional metadata
            
        Returns:
            APIResponse instance
        """
        return cls(
            success=True,
            data=data,
            message=message,
            meta=meta,
        )
    
    @classmethod
    def error(
        cls,
        message: str,
        errors: List[str] = None,
        data: T = None,
        meta: Dict[str, Any] = None,
    ) -> "APIResponse[T]":
        """
        Create an error response.
        
        Args:
            message: Error message
            errors: List of error messages
            data: Optional response data
            meta: Additional metadata
            
        Returns:
            APIResponse instance
        """
        return cls(
            success=False,
            data=data,
            message=message,
            errors=errors,
            meta=meta,
        )
    
    @classmethod
    def created(
        cls,
        data: T,
        message: str = "Resource created successfully",
        meta: Dict[str, Any] = None,
    ) -> "APIResponse[T]":
        """
        Create a 'created' response (201).
        
        Args:
            data: Response data
            message: Human-readable message
            meta: Additional metadata
            
        Returns:
            APIResponse instance
        """
        return cls(
            success=True,
            data=data,
            message=message,
            meta=meta,
        )
    
    @classmethod
    def no_content(cls) -> "APIResponse[T]":
        """
        Create a 'no content' response (204).
        
        Returns:
            APIResponse instance with no data
        """
        return cls(
            success=True,
            data=None,
            message=None,
        )


class DataResponse(BaseModel, Generic[T]):
    """
    Simple data-only response without metadata.
    
    Usage:
        @router.get("/items")
        async def list_items() -> DataResponse[List[ItemPublic]]:
            items = await service.list()
            return DataResponse(data=items)
    """
    data: T
    
    class Config:
        arbitrary_types_allowed = True


class ErrorResponse(BaseModel):
    """
    Error response schema.
    
    Usage:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                code="VALIDATION_ERROR",
                message="Invalid input data",
                errors=["Email is required", "Password must be at least 8 characters"]
            ).model_dump()
        )
    """
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    errors: Optional[List[str]] = Field(default=None, description="Detailed error messages")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class ValidationError(BaseModel):
    """Validation error detail."""
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    value: Optional[Any] = Field(default=None, description="Invalid value")


class ValidationErrorResponse(BaseModel):
    """
    Validation error response.
    
    Usage:
        @app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request, exc):
            errors = [
                ValidationError(field=".".join(str(loc) for loc in err["loc"]), message=err["msg"])
                for err in exc.errors()
            ]
            return JSONResponse(
                status_code=422,
                content=ValidationErrorResponse(
                    code="VALIDATION_ERROR",
                    message="Validation failed",
                    errors=errors
                ).model_dump()
            )
    """
    code: str = Field(default="VALIDATION_ERROR", description="Error code")
    message: str = Field(default="Validation failed", description="Error message")
    errors: List[ValidationError] = Field(..., description="Validation errors")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class SuccessResponse(BaseModel):
    """Simple success response without data."""
    success: bool = Field(default=True)
    message: str = Field(default="Success")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DeleteResponse(BaseModel):
    """Response for delete operations."""
    success: bool = Field(default=True)
    message: str = Field(default="Resource deleted successfully")
    id: str = Field(..., description="ID of deleted resource")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BatchResponse(BaseModel, Generic[T]):
    """
    Response for batch operations.
    
    Usage:
        @router.post("/items/batch")
        async def create_batch(items: List[ItemCreate]) -> BatchResponse[ItemPublic]:
            created = await service.bulk_create([item.model_dump() for item in items])
            return BatchResponse(
                data=created,
                total=len(created),
                successful=len(created),
                failed=0,
            )
    """
    data: List[T] = Field(..., description="List of created items")
    total: int = Field(..., description="Total items processed")
    successful: int = Field(..., description="Successfully processed items")
    failed: int = Field(default=0, description="Failed items")
    errors: Optional[List[Dict[str, Any]]] = Field(default=None, description="Errors for failed items")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="healthy", description="Health status")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = Field(
        default_factory=dict,
        description="Status of dependent services"
    )


class PagedResponse(BaseModel, Generic[T]):
    """
    Paginated response with metadata.
    
    Usage:
        @router.get("/items")
        async def list_items(
            page: int = Query(1, ge=1),
            per_page: int = Query(20, ge=1, le=100),
        ) -> PagedResponse[ItemPublic]:
            result = await service.paginate(page=page, per_page=per_page)
            return PagedResponse(
                data=result["data"],
                total=result["total"],
                page=result["page"],
                per_page=result["per_page"],
                total_pages=result["total_pages"],
            )
    """
    data: List[T] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of records")
    page: int = Field(..., description="Current page number (1-indexed)")
    per_page: int = Field(..., description="Records per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")
    
    class Config:
        arbitrary_types_allowed = True


# Convenience functions
def success(message: str = "Success") -> SuccessResponse:
    """Create a simple success response."""
    return SuccessResponse(message=message)


def error(message: str, errors: List[str] = None) -> ErrorResponse:
    """Create an error response."""
    return ErrorResponse(
        code="ERROR",
        message=message,
        errors=errors,
    )


def validation_error(errors: List[Dict[str, Any]]) -> ValidationErrorResponse:
    """Create a validation error response."""
    validation_errors = [
        ValidationError(field=err.get("field", ""), message=err.get("message", ""))
        for err in errors
    ]
    return ValidationErrorResponse(errors=validation_errors)