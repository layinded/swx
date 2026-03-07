"""
Pagination Utilities
--------------------
Standard pagination support for API responses.
"""

from typing import Generic, TypeVar, List, Optional, Dict, Any
from pydantic import BaseModel, Field
from math import ceil


T = TypeVar("T")


class PaginationParams(BaseModel):
    """
    Standard pagination parameters.
    
    Usage:
        @router.get("/items")
        async def list_items(
            pagination: PaginationParams = Depends(),
        ):
            return await repository.paginate(
                page=pagination.page,
                per_page=pagination.per_page,
            )
    """
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    per_page: int = Field(default=20, ge=1, le=1000, description="Items per page")
    
    @property
    def skip(self) -> int:
        """Calculate skip value for database queries."""
        return (self.page - 1) * self.per_page
    
    @property
    def offset(self) -> int:
        """Alias for skip."""
        return self.skip
    
    @property
    def limit(self) -> int:
        """Alias for per_page."""
        return self.per_page


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard paginated response schema.
    
    Usage:
        items = await repository.find_all(skip=skip, limit=limit)
        total = await repository.count()
        return PaginatedResponse.create(
            data=items,
            total=total,
            page=1,
            per_page=20,
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
    
    @classmethod
    def create(
        cls,
        data: List[T],
        total: int,
        page: int,
        per_page: int,
    ) -> "PaginatedResponse[T]":
        """
        Create a paginated response.
        
        Args:
            data: List of items
            total: Total number of records
            page: Current page number
            per_page: Records per page
            
        Returns:
            PaginatedResponse instance
        """
        total_pages = ceil(total / per_page) if per_page > 0 else 0
        return cls(
            data=data,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )
    
    @classmethod
    def empty(cls, page: int = 1, per_page: int = 20) -> "PaginatedResponse[T]":
        """
        Create an empty paginated response.
        
        Args:
            page: Current page number
            per_page: Records per page
            
        Returns:
            Empty PaginatedResponse instance
        """
        return cls(
            data=[],
            total=0,
            page=page,
            per_page=per_page,
            total_pages=0,
            has_next=False,
            has_prev=False,
        )


class CursorPaginationParams(BaseModel):
    """
    Cursor-based pagination parameters for infinite scroll.
    
    More efficient than offset-based pagination for large datasets.
    """
    cursor: Optional[str] = Field(default=None, description="Next cursor")
    limit: int = Field(default=20, ge=1, le=100, description="Number of items")
    direction: str = Field(default="next", description="next or previous")


class CursorPaginatedResponse(BaseModel, Generic[T]):
    """
    Cursor-based paginated response for infinite scroll.
    """
    data: List[T] = Field(..., description="List of items")
    next_cursor: Optional[str] = Field(default=None, description="Cursor for next page")
    prev_cursor: Optional[str] = Field(default=None, description="Cursor for previous page")
    has_next: bool = Field(default=False, description="Whether there is a next page")
    has_prev: bool = Field(default=False, description="Whether there is a previous page")
    
    @classmethod
    def create(
        cls,
        data: List[T],
        next_cursor: Optional[str] = None,
        prev_cursor: Optional[str] = None,
    ) -> "CursorPaginatedResponse[T]":
        """
        Create a cursor paginated response.
        """
        return cls(
            data=data,
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
            has_next=next_cursor is not None,
            has_prev=prev_cursor is not None,
        )


class OffsetPaginationParams(BaseModel):
    """
    Offset/limit based pagination parameters.
    
    Alternative to page/per_page based pagination.
    """
    offset: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(default=20, ge=1, le=1000, description="Maximum records to return")
    
    @property
    def page(self) -> int:
        """Calculate page number from offset and limit."""
        return (self.offset // self.limit) + 1 if self.limit > 0 else 1


class PagedResult(BaseModel, Generic[T]):
    """
    Comprehensive pagination result with metadata.
    
    Includes additional metadata beyond basic pagination.
    """
    data: List[T]
    meta: "PaginationMeta"


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool
    start_index: int
    end_index: int
    
    @classmethod
    def create(cls, total: int, page: int, per_page: int) -> "PaginationMeta":
        """
        Create pagination metadata.
        
        Args:
            total: Total number of records
            page: Current page number
            per_page: Records per page
            
        Returns:
            PaginationMeta instance
        """
        total_pages = ceil(total / per_page) if per_page > 0 else 0
        start_index = (page - 1) * per_page + 1 if total > 0 else 0
        end_index = min(page * per_page, total)
        
        return cls(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
            start_index=start_index,
            end_index=end_index,
        )


def paginate(
    items: List[T],
    total: int,
    page: int,
    per_page: int,
) -> PaginatedResponse[T]:
    """
    Helper function to create a paginated response.
    
    Args:
        items: List of items
        total: Total number of records
        page: Current page number
        per_page: Records per page
        
    Returns:
        PaginatedResponse instance
    """
    return PaginatedResponse.create(
        data=items,
        total=total,
        page=page,
        per_page=per_page,
    )


def calculate_pagination(
    total: int,
    page: int,
    per_page: int,
) -> Dict[str, Any]:
    """
    Calculate pagination values.
    
    Args:
        total: Total number of records
        page: Current page number
        per_page: Records per page
        
    Returns:
        Dictionary with skip, limit, total_pages, has_next, has_prev
    """
    total_pages = ceil(total / per_page) if per_page > 0 else 0
    return {
        "skip": (page - 1) * per_page,
        "limit": per_page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }