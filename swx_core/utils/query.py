"""
Query Builder Utilities
-----------------------
Advanced query building utilities.
"""

from typing import TypeVar, Generic, Type, Optional, List, Dict, Any, Callable, Union
from enum import Enum
from datetime import datetime

from sqlalchemy import select, func, or_, and_, not_
from sqlalchemy.sql.expression import Select, BinaryExpression
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.database.db import get_session
from swx_core.models.base import Base


ModelType = TypeVar("ModelType", bound=Base)


class SortOrder(str, Enum):
    """Sort order enum."""
    ASC = "asc"
    DESC = "desc"


class QueryBuilder(Generic[ModelType]):
    """
    Fluent query builder for SQLAlchemy.
    
    Usage:
        query = QueryBuilder(Product)
            .where(Product.is_active == True)
            .where(Product.price > 100)
            .order_by(Product.created_at, descending=True)
            .limit(10)
            .offset(20)
        
        results = await query.execute()
        total = await query.count()
    """
    
    def __init__(self, model: Type[ModelType]):
        """
        Initialize query builder.
        
        Args:
            model: SQLAlchemy/SQLModel class
        """
        self.model = model
        self._statement: Select = select(model)
        self._conditions: List[BinaryExpression] = []
        self._order_by_columns: List[tuple] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._joins: List[tuple] = []
        self._eager_loads: List[str] = []
        self._distinct: bool = False
        self._group_by_columns: List = []
        self._having_conditions: List[BinaryExpression] = []
    
    def where(self, condition: BinaryExpression) -> "QueryBuilder[ModelType]":
        """
        Add WHERE condition.
        
        Args:
            condition: SQLAlchemy condition
            
        Returns:
            Self for chaining
        """
        self._conditions.append(condition)
        return self
    
    def where_in(self, field, values: List[Any]) -> "QueryBuilder[ModelType]":
        """
        Add WHERE IN condition.
        
        Args:
            field: Model field
            values: List of values
            
        Returns:
            Self for chaining
        """
        if values:
            self._conditions.append(field.in_(values))
        return self
    
    def where_not_in(self, field, values: List[Any]) -> "QueryBuilder[ModelType]":
        """
        Add WHERE NOT IN condition.
        
        Args:
            field: Model field
            values: List of values
            
        Returns:
            Self for chaining
        """
        if values:
            self._conditions.append(not_(field.in_(values)))
        return self
    
    def where_like(self, field, pattern: str) -> "QueryBuilder[ModelType]":
        """
        Add WHERE LIKE condition.
        
        Args:
            field: Model field
            pattern: LIKE pattern
            
        Returns:
            Self for chaining
        """
        self._conditions.append(field.like(pattern))
        return self
    
    def where_ilike(self, field, pattern: str) -> "QueryBuilder[ModelType]":
        """
        Add WHERE ILIKE condition (case-insensitive).
        
        Args:
            field: Model field
            pattern: LIKE pattern
            
        Returns:
            Self for chaining
        """
        self._conditions.append(field.ilike(pattern))
        return self
    
    def where_between(self, field, start: Any, end: Any) -> "QueryBuilder[ModelType]":
        """
        Add WHERE BETWEEN condition.
        
        Args:
            field: Model field
            start: Start value
            end: End value
            
        Returns:
            Self for chaining
        """
        self._conditions.append(field.between(start, end))
        return self
    
    def where_is_null(self, field) -> "QueryBuilder[ModelType]":
        """
        Add WHERE IS NULL condition.
        
        Args:
            field: Model field
            
        Returns:
            Self for chaining
        """
        self._conditions.append(field.is_(None))
        return self
    
    def where_is_not_null(self, field) -> "QueryBuilder[ModelType]":
        """
        Add WHERE IS NOT NULL condition.
        
        Args:
            field: Model field
            
        Returns:
            Self for chaining
        """
        self._conditions.append(field.is_not(None))
        return self
    
    def where_date_range(
        self,
        field,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> "QueryBuilder[ModelType]":
        """
        Add WHERE date range condition.
        
        Args:
            field: Model field
            start_date: Start date (optional)
            end_date: End date (optional)
            
        Returns:
            Self for chaining
        """
        if start_date:
            self._conditions.append(field >= start_date)
        if end_date:
            self._conditions.append(field <= end_date)
        return self
    
    def search(self, fields: List, query: str) -> "QueryBuilder[ModelType]":
        """
        Add search condition across multiple fields.
        
        Args:
            fields: List of model fields to search
            query: Search query
            
        Returns:
            Self for chaining
        """
        if query and fields:
            conditions = [field.ilike(f"%{query}%") for field in fields]
            self._conditions.append(or_(*conditions))
        return self
    
    def order_by(
        self,
        field,
        descending: bool = False,
        nulls_last: bool = True,
    ) -> "QueryBuilder[ModelType]":
        """
        Add ORDER BY clause.
        
        Args:
            field: Model field
            descending: Sort descending
            nulls_last: Place nulls last
            
        Returns:
            Self for chaining
        """
        if descending:
            order_col = field.desc()
        else:
            order_col = field.asc()
        
        if nulls_last:
            from sqlalchemy import nulls_last as sql_nulls_last
            order_col = sql_nulls_last(order_col)
        
        self._order_by_columns.append((order_col, descending))
        return self
    
    def limit(self, limit: int) -> "QueryBuilder[ModelType]":
        """
        Add LIMIT clause.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            Self for chaining
        """
        self._limit = limit
        return self
    
    def offset(self, offset: int) -> "QueryBuilder[ModelType]":
        """
        Add OFFSET clause.
        
        Args:
            offset: Number of results to skip
            
        Returns:
            Self for chaining
        """
        self._offset = offset
        return self
    
    def page(self, page: int, per_page: int = 20) -> "QueryBuilder[ModelType]":
        """
        Add pagination (LIMIT and OFFSET).
        
        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            
        Returns:
            Self for chaining
        """
        self._offset = (page - 1) * per_page
        self._limit = per_page
        return self
    
    def join(self, target, onclause: Optional[Any] = None) -> "QueryBuilder[ModelType]":
        """
        Add JOIN clause.
        
        Args:
            target: Joined model
            onclause: Join condition
            
        Returns:
            Self for chaining
        """
        self._joins.append((target, onclause))
        return self
    
    def distinct(self) -> "QueryBuilder[ModelType]":
        """
        Add DISTINCT clause.
        
        Returns:
            Self for chaining
        """
        self._distinct = True
        return self
    
    def group_by(self, *fields) -> "QueryBuilder[ModelType]":
        """
        Add GROUP BY clause.
        
        Args:
            *fields: Group by fields
            
        Returns:
            Self for chaining
        """
        self._group_by_columns.extend(fields)
        return self
    
    def having(self, condition: BinaryExpression) -> "QueryBuilder[ModelType]":
        """
        Add HAVING condition.
        
        Args:
            condition: Having condition
            
        Returns:
            Self for chaining
        """
        self._having_conditions.append(condition)
        return self
    
    def _build(self) -> Select:
        """Build the final SQLAlchemy statement."""
        statement = select(self.model)
        
        # Add WHERE conditions
        if self._conditions:
            statement = statement.where(and_(*self._conditions))
        
        # Add JOINs
        for target, onclause in self._joins:
            statement = statement.join(target, onclause)
        
        # Add GROUP BY
        if self._group_by_columns:
            statement = statement.group_by(*self._group_by_columns)
        
        # Add HAVING
        if self._having_conditions:
            statement = statement.having(and_(*self._having_conditions))
        
        # Add ORDER BY
        for order_col, _ in self._order_by_columns:
            statement = statement.order_by(order_col)
        
        # Add DISTINCT
        if self._distinct:
            statement = statement.distinct()
        
        # Add LIMIT and OFFSET
        if self._limit:
            statement = statement.limit(self._limit)
        if self._offset:
            statement = statement.offset(self._offset)
        
        return statement
    
    async def execute(self) -> List[ModelType]:
        """
        Execute the query and return results.
        
        Returns:
            List of model instances
        """
        statement = self._build()
        
        async with get_session() as session:
            result = await session.execute(statement)
            return list(result.scalars().all())
    
    async def first(self) -> Optional[ModelType]:
        """
        Execute the query and return first result.
        
        Returns:
            First model instance or None
        """
        statement = self._build().limit(1)
        
        async with get_session() as session:
            result = await session.execute(statement)
            return result.scalar_one_or_none()
    
    async def one(self) -> ModelType:
        """
        Execute the query and return exactly one result.
        
        Returns:
            Model instance
            
        Raises:
            ValueError: If no result or multiple results
        """
        statement = self._build()
        
        async with get_session() as session:
            result = await session.execute(statement)
            return result.scalar_one()
    
    async def count(self) -> int:
        """
        Execute COUNT query.
        
        Returns:
            Number of matching records
        """
        statement = select(func.count(self.model.id))
        
        # Add WHERE conditions
        if self._conditions:
            statement = statement.where(and_(*self._conditions))
        
        # Add JOINs
        for target, onclause in self._joins:
            statement = statement.join(target, onclause)
        
        # Add DISTINCT
        if self._distinct:
            statement = statement.distinct()
        
        async with get_session() as session:
            result = await session.execute(statement)
            return result.scalar() or 0
    
    async def exists(self) -> bool:
        """
        Check if any matching record exists.
        
        Returns:
            True if exists, False otherwise
        """
        return await self.count() > 0
    
    async def paginate(
        self,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """
        Execute query with pagination metadata.
        
        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            
        Returns:
            Dictionary with 'data', 'total', 'page', 'per_page', 'total_pages'
        """
        # Get total count
        total = await self.count()
        
        # Get items
        items = await self.clone().page(page, per_page).execute()
        
        # Calculate total pages
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        
        return {
            "data": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        }
    
    def clone(self) -> "QueryBuilder[ModelType]":
        """
        Create a copy of this query builder.
        
        Returns:
            New QueryBuilder instance
        """
        new_query = QueryBuilder(self.model)
        new_query._conditions = self._conditions.copy()
        new_query._order_by_columns = self._order_by_columns.copy()
        new_query._limit = self._limit
        new_query._offset = self._offset
        new_query._joins = self._joins.copy()
        new_query._eager_loads = self._eager_loads.copy()
        new_query._distinct = self._distinct
        new_query._group_by_columns = self._group_by_columns.copy()
        new_query._having_conditions = self._having_conditions.copy()
        return new_query