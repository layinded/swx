# This model was generated using swx CLI.

from typing import Optional
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base

class OrderItemBase(Base):
    # Define base fields here


class OrderItem(OrderItemBase, table=True):
    __tablename__ = "order_item"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    # Define table-specific fields here


class OrderItemCreate(SQLModel):
    # Define required fields for creation


class OrderItemUpdate(SQLModel):
    # Define fields that can be updated


class OrderItemPublic(OrderItem):
    pass
