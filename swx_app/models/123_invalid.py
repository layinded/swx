# This model was generated using swx CLI.

from typing import Optional
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base

class 123InvalidBase(Base):
    # Define base fields here


class 123Invalid(123InvalidBase, table=True):
    __tablename__ = "123_invalid"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(...)


class 123InvalidCreate(SQLModel):
    name: str


class 123InvalidUpdate(SQLModel):
    name: Optional[str] = None


class 123InvalidPublic(123Invalid):
    pass
