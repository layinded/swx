import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class MfaRecoveryCodeBase(Base):
    user_id: uuid.UUID = Field(foreign_key="swx_users.id", index=True)
    code_hash: str = Field(max_length=255)
    used_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class MfaRecoveryCode(MfaRecoveryCodeBase, table=True):
    __tablename__ = "swx_mfa_recovery_codes"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


class MfaEnrollRequest(SQLModel):
    pass


class MfaVerifyEnrollRequest(SQLModel):
    code: str = Field(min_length=6, max_length=6)


class MfaChallengeRequest(SQLModel):
    mfa_token: str = Field(min_length=1)
    code: str = Field(min_length=6, max_length=8)


class MfaRecoverRequest(SQLModel):
    mfa_token: str = Field(min_length=1)
    recovery_code: str = Field(min_length=1)


class MfaDisableRequest(SQLModel):
    code: str = Field(min_length=6, max_length=8)


class MfaStepUpRequest(SQLModel):
    code: str = Field(min_length=6, max_length=8)


class MfaStepUpResponse(SQLModel):
    step_up_token: str
    expires_in: int


class MfaEnrollResponse(SQLModel):
    secret: str
    qr_code_uri: str
    recovery_codes: list[str]


class MfaChallengeResponse(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MfaStatusResponse(SQLModel):
    mfa_enabled: bool
    mfa_verified_at: Optional[datetime] = None