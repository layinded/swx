# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class SocialAccountBase(Base):
    provider: str = Field(max_length=50, description="OAuth provider name (google, facebook, github, etc.)")
    provider_id: str = Field(max_length=255, description="Provider-specific user ID")
    provider_email: str | None = Field(default=None, max_length=255, description="Email from the provider at link time")
    display_name: str | None = Field(default=None, max_length=255, description="Name from the provider")
    avatar_url: str | None = Field(default=None, max_length=1000, description="Profile picture URL from provider")


class SocialAccount(SocialAccountBase, table=True):
    __tablename__ = "swx_social_accounts"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="swx_users.id", index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


class SocialAccountPublic(SocialAccountBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class SocialAccountLinkRequest(SQLModel):
    provider: str = Field(min_length=1, max_length=50)
    redirect_url: str | None = Field(default=None, max_length=1000)


class SocialAccountUnlinkRequest(SQLModel):
    provider: str = Field(min_length=1, max_length=50)