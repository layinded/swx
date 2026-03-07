"""
Model Mixins
------------
Reusable mixins for SQLAlchemy models.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field


class TimestampMixin:
    """
    Mixin to add created_at and updated_at timestamps.
    
    Usage:
        class Product(TimestampMixin, table=True):
            id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
            name: str
    """
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, server_default=func.now(), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    )


class SoftDeleteMixin:
    """
    Mixin to add soft delete capability.
    
    Usage:
        class Product(SoftDeleteMixin, table=True):
            id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
            name: str
        
        # To soft delete
        product.is_deleted = True
        
        # Query only active records
        query = select(Product).where(Product.is_deleted == False)
    """
    is_deleted: bool = Field(
        default=False,
        sa_column=Column(Boolean, server_default="false", nullable=False, index=True)
    )
    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime, nullable=True)
    )
    
    def soft_delete(self) -> None:
        """Mark the record as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
    
    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None


class UUIDPrimaryKeyMixin:
    """
    Mixin to add UUID primary key.
    
    Usage:
        class Product(UUIDPrimaryKeyMixin, table=True):
            name: str
    """
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        sa_column=Column(UUID(as_uuid=True), primary_key=True)
    )


class CreatedByMixin:
    """
    Mixin to track who created a record.
    
    Usage:
        class Product(CreatedByMixin, table=True):
            id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
            name: str
    """
    created_by_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), nullable=True, index=True)
    )


class UpdatedByMixin:
    """
    Mixin to track who last updated a record.
    
    Usage:
        class Product(UpdatedByMixin, table=True):
            id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
            name: str
    """
    updated_by_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), nullable=True, index=True)
    )


class AuditMixin(CreatedByMixin, UpdatedByMixin):
    """
    Full audit mixin combining created_by and updated_by.
    
    Usage:
        class Product(AuditMixin, table=True):
            id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
            name: str
    """
    pass


class ActiveMixin:
    """
    Mixin to add is_active flag.
    
    Usage:
        class Product(ActiveMixin, table=True):
            id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
            name: str
    """
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, server_default="true", nullable=False, index=True)
    )
    
    def activate(self) -> None:
        """Activate the record."""
        self.is_active = True
    
    def deactivate(self) -> None:
        """Deactivate the record."""
        self.is_active = False


class SlugMixin:
    """
    Mixin to add slug field for URL-friendly identifiers.
    
    Usage:
        class Product(SlugMixin, table=True):
            id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
            name: str
    """
    slug: str = Field(
        max_length=255,
        unique=True,
        index=True,
        sa_column=Column(String(255), unique=True, index=True)
    )


class TitleMixin:
    """
    Mixin to add title field with search optimization.
    
    Usage:
        class Product(TitleMixin, table=True):
            id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    """
    title: str = Field(
        max_length=255,
        index=True,
        sa_column=Column(String(255), index=True)
    )


class DescriptionMixin:
    """
    Mixin to add description field.
    
    Usage:
        class Product(DescriptionMixin, table=True):
            id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    """
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(String)
    )


class MetadataMixin:
    """
    Mixin to add JSON metadata field.
    
    Usage:
        class Product(MetadataMixin, table=True):
            id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
        
        # Store arbitrary metadata
        product.metadata = {"key": "value"}
    """
    metadata: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", sa_column_kwargs={"server_default": "{}"})
    )
    # Note: For PostgreSQL, you might want to use JSONB:
    # from sqlalchemy.dialects.postgresql import JSONB
    # metadata: dict = Field(default_factory=dict, sa_column=Column(JSONB, server_default="{}"))


class FullModelMixin(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    SoftDeleteMixin,
    ActiveMixin,
):
    """
    Complete mixin with all common fields.
    
    Usage:
        class Product(FullModelMixin, table=True):
            name: str
            price: Decimal
    """
    pass


class AuditedModelMixin(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    AuditMixin,
    SoftDeleteMixin,
):
    """
    Full audit mixin with timestamps and soft delete.
    
    Usage:
        class Product(AuditedModelMixin, table=True):
            name: str
            price: Decimal
    """
    pass