# This model was generated using swx CLI.

from typing import Optional
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base

class MyModelBase(Base):
    # Define base fields here


class MyModel(MyModelBase, table=True):
    __tablename__ = "my_model"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    # Define table-specific fields here


class MyModelCreate(SQLModel):
    # Define required fields for creation


class MyModelUpdate(SQLModel):
    # Define fields that can be updated


class MyModelPublic(MyModel):
    pass
