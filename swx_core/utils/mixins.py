"""
Model Mixins
------------
Reusable mixins for SQLAlchemy / SQLModel models.

BUG FIX (v2.23.4): Previous version used ``sa_column=Column(...)`` in
mixin class bodies.  That creates a **single shared Column instance**
at class-definition time.  When two ``table=True`` models inherit the
same mixin, SQLAlchemy raises::

    Column object 'X' already assigned to Table 'Y'

Root cause: Python evaluates default values at class-definition time,
not per-subclass.  So ``Field(sa_column=Column(...))`` in a mixin
shares one Column object across all inheriting models.

Solution: Mixins now use **pure ``Field()``** — no ``sa_column``.
Each ``Field()`` call creates a new ``FieldInfo``, so they're safe
to share across multiple ``table=True`` models.

For columns that need ``server_default``, ``onupdate``, ``index=True``,
or other SQLAlchemy Column kwargs, use the **factory functions** exported
below (``make_id()``, ``make_created_at()``, etc.) directly in each
model's class body.  Because each factory call creates a fresh Column,
this is safe per-model.

Usage::

    # Simple: use mixins for defaults (no server_default)
    class Product(FullModelMixin, SQLModel, table=True):
        name: str

    # Full: use factory functions for server_default, onupdate, etc.
    class Product(FullModelMixin, SQLModel, table=True):
        __tablename__ = 'products'
        name: str
        # Override mixin fields with full Column kwargs:
        id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=make_id())
        created_at: datetime = Field(sa_column=make_created_at())
        updated_at: datetime = Field(sa_column=make_updated_at())
        is_active: bool = Field(default=True, sa_column=make_is_active())

NOTE: ``metadata_`` (not ``metadata``) is used for the JSON column
because ``metadata`` is a reserved SQLAlchemy attribute name.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field

from swx_core.utils.time import utc_now


# ---------------------------------------------------------------------------
# Column factory functions — each call creates a fresh Column instance.
#
# Use these in model class bodies when you need server_default, onupdate,
# index, or other SQLAlchemy Column kwargs.  DO NOT use them in mixin
# class bodies — only in the model itself.
# ---------------------------------------------------------------------------


def make_id():
    """Create a fresh UUID primary key Column (call per model, not shared)."""
    return Column(PG_UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)


def make_created_at():
    """Create a fresh created_at Column with server_default."""
    return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def make_updated_at():
    """Create a fresh updated_at Column with server_default and onupdate."""
    return Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


def make_is_deleted():
    """Create a fresh is_deleted Column with server_default."""
    return Column(Boolean, server_default="false", nullable=False, index=True)


def make_deleted_at():
    """Create a fresh deleted_at Column."""
    return Column(DateTime(timezone=True), nullable=True)


def make_created_by_id():
    """Create a fresh created_by_id Column with index."""
    return Column(PG_UUID(as_uuid=True), nullable=True, index=True)


def make_updated_by_id():
    """Create a fresh updated_by_id Column with index."""
    return Column(PG_UUID(as_uuid=True), nullable=True, index=True)


def make_is_active():
    """Create a fresh is_active Column with server_default and index."""
    return Column(Boolean, server_default="true", nullable=False, index=True)


def make_slug():
    """Create a fresh slug Column with unique index."""
    return Column(String(255), unique=True, index=True)


def make_metadata():
    """Create a fresh metadata JSON Column (mapped to 'metadata' column name)."""
    return Column("metadata", JSON, nullable=True)


# ---------------------------------------------------------------------------
# Pure Field() mixins — safe for multiple table=True subclasses.
#
# These provide Python-side defaults but NO server_default, onupdate,
# or index.  Override with factory functions in the model body when
# you need those Column features.
# ---------------------------------------------------------------------------


class UUIDPrimaryKeyMixin:
    """UUID primary key mixin (pure Field — no server_default).

    For server_default, override in model body::

        id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=make_id())
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class TimestampMixin:
    """created_at / updated_at timestamps (pure Field — no server_default).

    For server_default/onupdate, override in model body::

        created_at: datetime = Field(sa_column=make_created_at())
        updated_at: datetime = Field(sa_column=make_updated_at())
    """

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SoftDeleteMixin:
    """Soft-delete support (is_deleted + deleted_at).

    For server_default, override in model body::

        is_deleted: bool = Field(default=False, sa_column=make_is_deleted())
        deleted_at: Optional[datetime] = Field(default=None, sa_column=make_deleted_at())
    """

    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = utc_now()

    def restore(self) -> None:
        self.is_deleted = False
        self.deleted_at = None


class CreatedByMixin:
    """Track which user created the record."""

    created_by_id: Optional[uuid.UUID] = Field(default=None)


class UpdatedByMixin:
    """Track which user last updated the record."""

    updated_by_id: Optional[uuid.UUID] = Field(default=None)


class AuditMixin(CreatedByMixin, UpdatedByMixin, TimestampMixin):
    """Combined mixin for full audit trail (created_at, updated_at, created_by_id, updated_by_id)."""

    pass


class ActiveMixin:
    """is_active flag (pure Field — no server_default).

    For server_default and index, override in model body::

        is_active: bool = Field(default=True, sa_column=make_is_active())
    """

    is_active: bool = Field(default=True)

    def activate(self) -> None:
        """Activate the record."""
        self.is_active = True

    def deactivate(self) -> None:
        """Deactivate the record."""
        self.is_active = False


class SlugMixin:
    """URL-friendly slug field (pure Field — no unique index).

    For unique index, override in model body::

        slug: str = Field(sa_column=make_slug())
    """

    slug: str = Field(max_length=255)


class TitleMixin:
    """Title field."""

    title: str = Field(max_length=255)


class DescriptionMixin:
    """Optional description field."""

    description: Optional[str] = Field(default=None)


class MetadataMixin:
    """JSON metadata field.

    Uses ``metadata_`` attribute name (mapped to ``metadata`` column)
    because ``metadata`` is a reserved SQLAlchemy attribute name.
    """

    metadata_: Optional[dict] = Field(default=None)


# ---------------------------------------------------------------------------
# Composite mixins
# ---------------------------------------------------------------------------


class FullModelMixin(TimestampMixin, UUIDPrimaryKeyMixin, ActiveMixin):
    """Complete mixin combining id, created_at, updated_at, is_active.

    Uses pure Field() — safe with multiple ``table=True`` subclasses.

    For server_default/onupdate/index, override in model body::

        id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=make_id())
        created_at: datetime = Field(sa_column=make_created_at())
        updated_at: datetime = Field(sa_column=make_updated_at())
        is_active: bool = Field(default=True, sa_column=make_is_active())

    Usage::

        class Product(FullModelMixin, SQLModel, table=True):
            __tablename__ = 'products'
            name: str
    """

    pass


class AuditedModelMixin(FullModelMixin, CreatedByMixin, UpdatedByMixin):
    """Full audit mixin with user tracking.

    Includes id, created_at, updated_at, is_active, created_by_id, updated_by_id.
    """

    pass


__all__ = [
    "TimestampMixin",
    "SoftDeleteMixin",
    "UUIDPrimaryKeyMixin",
    "CreatedByMixin",
    "UpdatedByMixin",
    "AuditMixin",
    "ActiveMixin",
    "SlugMixin",
    "TitleMixin",
    "DescriptionMixin",
    "MetadataMixin",
    "FullModelMixin",
    "AuditedModelMixin",
    # Factory functions — exported for direct use in model class bodies
    # when server_default, onupdate, or index is needed.
    "make_id",
    "make_created_at",
    "make_updated_at",
    "make_is_deleted",
    "make_deleted_at",
    "make_created_by_id",
    "make_updated_by_id",
    "make_is_active",
    "make_slug",
    "make_metadata",
]
