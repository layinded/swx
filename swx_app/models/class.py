# This model was generated using swx CLI.

from typing import Optional
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base

class ClassBase(Base):
    # Define base fields here


class Class(ClassBase, table=True):
    __tablename__ = "class"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    # Define table-specific fields here


class ClassCreate(SQLModel):
    # Define required fields for creation


class ClassUpdate(SQLModel):
    # Define fields that can be updated


class ClassPublic(Class):
    pass
