"""
Query Parameter Filters for FastAPI.

Provides reusable filter builders for common query parameter patterns.

Usage:
    from swx_core.utils.filters import FilterBuilder, DateFilter, RangeFilter
    
    @router.get("/products")
    async def list_products(
        name: str | None = Query(None),
        category: str | None = Query(None),
        min_price: float | None = Query(None),
        max_price: float | None = Query(None),
        created_after: datetime | None = Query(None),
    ):
        filters = FilterBuilder()
        if name:
            filters.add(Product.name.ilike(f"%{name}%"))
        if category:
            filters.add(Product.category == category)
        if min_price is not None:
            filters.add(Product.price >= min_price)
        if max_price is not None:
            filters.add(Product.price <= max_price)
        
        query = filters.apply(select(Product))
        result = await session.execute(query)
        return result.scalars().all()
"""

from typing import Any, Optional, List, Dict, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
import re

from sqlalchemy import and_, or_, not_, func
from sqlalchemy.sql.expression import BinaryExpression, BooleanClauseList
from sqlalchemy.orm import InstrumentedAttribute

T = TypeVar("T")


class FilterOperator(Enum):
    """Filter operators."""
    EQ = "eq"  # equals
    NE = "ne"  # not equals
    GT = "gt"  # greater than
    GTE = "gte"  # greater than or equals
    LT = "lt"  # less than
    LTE = "lte"  # less than or equals
    LIKE = "like"  # LIKE
    ILIKE = "ilike"  # case-insensitive LIKE
    IN = "in"  # in list
    NOT_IN = "not_in"  # not in list
    BETWEEN = "between"  # between two values
    IS_NULL = "is_null"  # is null
    IS_NOT_NULL = "is_not_null"  # is not null
    CONTAINS = "contains"  # contains substring
    STARTSWITH = "startswith"  # starts with
    ENDSWITH = "endswith"  # ends with


@dataclass
class FilterCondition:
    """A single filter condition."""
    field: InstrumentedAttribute
    operator: FilterOperator
    value: Any
    negate: bool = False


class FilterBuilder:
    """
    Builds SQLAlchemy filter expressions from conditions.
    
    Features:
    - Chained filter building
    - AND/OR group support
    - Negation support
    - Common patterns (search, range, date filters)
    
    Example:
        filters = FilterBuilder()
            .where(User.is_active == True)
            .where(User.role == "admin")
            .search(User.name, "john")
            .apply(query)
    """
    
    def __init__(self):
        """Initialize filter builder."""
        self._conditions: List[FilterCondition] = []
        self._groups: List['FilterBuilder'] = []
    
    def where(self, condition: BinaryExpression) -> 'FilterBuilder':
        """
        Add a raw filter condition.
        
        Args:
            condition: SQLAlchemy binary expression
            
        Returns:
            Self for chaining
        """
        # Wrap in a simple condition for tracking
        self._conditions.append(FilterCondition(
            field=None,  # We don't track field for raw conditions
            operator=FilterOperator.EQ,
            value=condition
        ))
        return self
    
    def filter(
        self, 
        field: InstrumentedAttribute,
        operator: FilterOperator,
        value: Any,
        negate: bool = False
    ) -> 'FilterBuilder':
        """
        Add a filter condition.
        
        Args:
            field: SQLAlchemy column
            operator: Filter operator
            value: Filter value
            negate: Whether to negate the condition
            
        Returns:
            Self for chaining
        """
        self._conditions.append(FilterCondition(
            field=field,
            operator=operator,
            value=value,
            negate=negate
        ))
        return self
    
    def eq(self, field: InstrumentedAttribute, value: Any) -> 'FilterBuilder':
        """Add equality filter."""
        return self.filter(field, FilterOperator.EQ, value)
    
    def ne(self, field: InstrumentedAttribute, value: Any) -> 'FilterBuilder':
        """Add not-equals filter."""
        return self.filter(field, FilterOperator.NE, value)
    
    def gt(self, field: InstrumentedAttribute, value: Any) -> 'FilterBuilder':
        """Add greater-than filter."""
        return self.filter(field, FilterOperator.GT, value)
    
    def gte(self, field: InstrumentedAttribute, value: Any) -> 'FilterBuilder':
        """Add greater-than-or-equals filter."""
        return self.filter(field, FilterOperator.GTE, value)
    
    def lt(self, field: InstrumentedAttribute, value: Any) -> 'FilterBuilder':
        """Add less-than filter."""
        return self.filter(field, FilterOperator.LT, value)
    
    def lte(self, field: InstrumentedAttribute, value: Any) -> 'FilterBuilder':
        """Add less-than-or-equals filter."""
        return self.filter(field, FilterOperator.LTE, value)
    
    def like(self, field: InstrumentedAttribute, pattern: str) -> 'FilterBuilder':
        """Add LIKE filter."""
        return self.filter(field, FilterOperator.LIKE, pattern)
    
    def ilike(self, field: InstrumentedAttribute, pattern: str) -> 'FilterBuilder':
        """Add case-insensitive LIKE filter."""
        return self.filter(field, FilterOperator.ILIKE, pattern)
    
    def contains(self, field: InstrumentedAttribute, value: str) -> 'FilterBuilder':
        """Add contains filter (substring match)."""
        return self.filter(field, FilterOperator.ILIKE, f"%{value}%")
    
    def startswith(self, field: InstrumentedAttribute, value: str) -> 'FilterBuilder':
        """Add starts-with filter."""
        return self.filter(field, FilterOperator.ILIKE, f"{value}%")
    
    def endswith(self, field: InstrumentedAttribute, value: str) -> 'FilterBuilder':
        """Add ends-with filter."""
        return self.filter(field, FilterOperator.ILIKE, f"%{value}")
    
    def in_(self, field: InstrumentedAttribute, values: List[Any]) -> 'FilterBuilder':
        """Add IN filter."""
        return self.filter(field, FilterOperator.IN, values)
    
    def not_in(self, field: InstrumentedAttribute, values: List[Any]) -> 'FilterBuilder':
        """Add NOT IN filter."""
        return self.filter(field, FilterOperator.NOT_IN, values)
    
    def is_null(self, field: InstrumentedAttribute) -> 'FilterBuilder':
        """Add IS NULL filter."""
        return self.filter(field, FilterOperator.IS_NULL, None)
    
    def is_not_null(self, field: InstrumentedAttribute) -> 'FilterBuilder':
        """Add IS NOT NULL filter."""
        return self.filter(field, FilterOperator.IS_NOT_NULL, None)
    
    def between(
        self, 
        field: InstrumentedAttribute, 
        start: Any, 
        end: Any
    ) -> 'FilterBuilder':
        """Add BETWEEN filter."""
        return self.filter(field, FilterOperator.BETWEEN, (start, end))
    
    def search(
        self, 
        fields: List[InstrumentedAttribute], 
        query: str
    ) -> 'FilterBuilder':
        """
        Add full-text search across multiple fields.
        
        Args:
            fields: List of columns to search
            query: Search string
            
        Returns:
            Self for chaining
        """
        if not query:
            return self
        
        # Use OR to search across fields
        or_conditions = []
        for field in fields:
            or_conditions.append(field.ilike(f"%{query}%"))
        
        if or_conditions:
            # Create an OR group
            or_filter = or_(*or_conditions)
            self._conditions.append(FilterCondition(
                field=None,
                operator=FilterOperator.EQ,
                value=or_filter
            ))
        
        return self
    
    def date_range(
        self, 
        field: InstrumentedAttribute,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> 'FilterBuilder':
        """
        Add date range filter.
        
        Args:
            field: Date/datetime column
            start: Start date (inclusive)
            end: End date (inclusive)
            
        Returns:
            Self for chaining
        """
        if start is not None:
            self.gte(field, start)
        if end is not None:
            self.lte(field, end)
        return self
    
    def or_group(self, group: 'FilterBuilder') -> 'FilterBuilder':
        """
        Add an OR group.
        
        Args:
            group: Another FilterBuilder to include as OR
            
        Returns:
            Self for chaining
        """
        self._groups.append(group)
        return self
    
    def build(self) -> Optional[BooleanClauseList]:
        """
        Build the SQLAlchemy filter expression.
        
        Returns:
            SQLAlchemy boolean expression or None if no conditions
        """
        conditions = []
        
        for cond in self._conditions:
            if cond.field is None:
                # Raw condition
                conditions.append(cond.value)
            else:
                expr = self._build_condition(cond)
                if expr is not None:
                    if cond.negate:
                        expr = not_(expr)
                    conditions.append(expr)
        
        # Add OR groups
        for group in self._groups:
            group_expr = group.build()
            if group_expr is not None:
                conditions.append(group_expr)
        
        if not conditions:
            return None
        
        if len(conditions) == 1:
            return conditions[0]
        
        return and_(*conditions)
    
    def _build_condition(self, cond: FilterCondition) -> Optional[BinaryExpression]:
        """Build a single condition expression."""
        field = cond.field
        op = cond.operator
        value = cond.value
        
        if op == FilterOperator.EQ:
            return field == value
        elif op == FilterOperator.NE:
            return field != value
        elif op == FilterOperator.GT:
            return field > value
        elif op == FilterOperator.GTE:
            return field >= value
        elif op == FilterOperator.LT:
            return field < value
        elif op == FilterOperator.LTE:
            return field <= value
        elif op == FilterOperator.LIKE:
            return field.like(value)
        elif op == FilterOperator.ILIKE:
            return field.ilike(value)
        elif op == FilterOperator.IN:
            return field.in_(value)
        elif op == FilterOperator.NOT_IN:
            return ~field.in_(value)
        elif op == FilterOperator.BETWEEN:
            if isinstance(value, (list, tuple)) and len(value) == 2:
                return field.between(value[0], value[1])
            return None
        elif op == FilterOperator.IS_NULL:
            return field.is_(None)
        elif op == FilterOperator.IS_NOT_NULL:
            return field.isnot(None)
        
        return None
    
    def apply(self, query):
        """
        Apply filters to a query.
        
        Args:
            query: SQLAlchemy query object
            
        Returns:
            Modified query with filters applied
        """
        expr = self.build()
        if expr is not None:
            return query.where(expr)
        return query


class SortBuilder:
    """
    Build sort expressions for queries.
    
    Example:
        sort = SortBuilder()
            .asc(User.name)
            .desc(User.created_at)
            .apply(query)
    """
    
    def __init__(self):
        """Initialize sort builder."""
        self._sorts: List[tuple] = []
    
    def asc(self, field: InstrumentedAttribute) -> 'SortBuilder':
        """Add ascending sort."""
        self._sorts.append((field, 'asc'))
        return self
    
    def desc(self, field: InstrumentedAttribute) -> 'SortBuilder':
        """Add descending sort."""
        self._sorts.append((field, 'desc'))
        return self
    
    def build(self):
        """Build sort expressions."""
        from sqlalchemy import asc as sql_asc, desc as sql_desc
        
        expressions = []
        for field, direction in self._sorts:
            if direction == 'asc':
                expressions.append(sql_asc(field))
            else:
                expressions.append(sql_desc(field))
        
        return expressions
    
    def apply(self, query):
        """Apply sorts to a query."""
        expressions = self.build()
        for expr in expressions:
            query = query.order_by(expr)
        return query


class FilterParams:
    """
    Common filter parameters for FastAPI endpoints.
    
    Usage:
        @router.get("/products")
        async def list_products(
            filters: FilterParams = Depends(),
            name: str | None = Query(None),
            min_price: float | None = Query(None),
        ):
            builder = FilterBuilder()
            if name:
                builder.contains(Product.name, name)
            if min_price is not None:
                builder.gte(Product.price, min_price)
            
            query = builder.apply(select(Product))
            query = SortBuilder().desc(Product.created_at).apply(query)
            query = query.offset(filters.offset).limit(filters.limit)
            ...
    """
    
    def __init__(
        self,
        page: int = 1,
        per_page: int = 20,
        sort_by: str | None = None,
        sort_order: str = "desc",
        search: str | None = None,
    ):
        self.page = page
        self.per_page = per_page
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.search = search
    
    @property
    def offset(self) -> int:
        """Calculate offset from page."""
        return (self.page - 1) * self.per_page
    
    @property
    def limit(self) -> int:
        """Get limit from per_page."""
        return self.per_page


__all__ = [
    "FilterOperator",
    "FilterCondition",
    "FilterBuilder",
    "SortBuilder",
    "FilterParams",
]