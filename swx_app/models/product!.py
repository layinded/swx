# This model was generated using swx CLI.

from typing import Optional
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base

class Product!Base(Base):
    # Define base fields here


class Product!(Product!Base, table=True):
    __tablename__ = "product!"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    # Define table-specific fields here


class Product!Create(SQLModel):
    # Define required fields for creation


class Product!Update(SQLModel):
    # Define fields that can be updated


class Product!Public(Product!):
    pass
