# This model was generated using swx CLI.

from typing import Optional
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base

class ProductBase(Base):
    # Define base fields here


class Product(ProductBase, table=True):
    __tablename__ = "product"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    class: str = Field(...)


class ProductCreate(SQLModel):
    class: str


class ProductUpdate(SQLModel):
    class: Optional[str] = None


class ProductPublic(Product):
    pass
