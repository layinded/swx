# This model was generated using swx CLI.

from typing import Optional
from sqlmodel import SQLModel, Field
from swx_core.models.base import Base

class UserAccountBase(Base):
    # Define base fields here


class UserAccount(UserAccountBase, table=True):
    __tablename__ = "user_account"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    # Define table-specific fields here


class UserAccountCreate(SQLModel):
    # Define required fields for creation


class UserAccountUpdate(SQLModel):
    # Define fields that can be updated


class UserAccountPublic(UserAccount):
    pass
