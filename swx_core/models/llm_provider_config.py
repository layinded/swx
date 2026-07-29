# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

SECRET_KEY_TOKENS = ("key", "token", "secret", "password")

class LLMProviderType(str, Enum):
    OPENAI = "openai"
    AZURE = "azure"
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"

def mask_credentials_map(credentials: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in credentials.items():
        if isinstance(value, dict):
            masked[key] = mask_credentials_map(value)
            continue
        masked[key] = "***" if any(token in key.lower() for token in SECRET_KEY_TOKENS) else value
    return masked

class LLMProviderConfigBase(SQLModel):
    provider: str = Field(max_length=50)
    name: str = Field(max_length=100)
    model_name: str = Field(max_length=100)
    credentials: dict[str, Any] = Field(default_factory=dict)
    default_params: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    is_primary: bool = False
    is_active: bool = True
    supported_phases: list[str] = Field(default_factory=list)
    cost_per_1k_tokens: float | None = None
    supports_streaming: bool = True
    supports_json_mode: bool = True
    # Per-provider resilience config (None = fall back to global settings)
    timeout_seconds: int | None = None
    max_retries: int | None = None
    circuit_breaker_threshold: int | None = None
    circuit_breaker_reset_seconds: int | None = None
    rate_limit_per_minute: int | None = None
    daily_token_limit: int | None = None
    extra_data: dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")

class LLMProviderConfig(LLMProviderConfigBase, Base, table=True):
    __tablename__ = "swx_llm_provider_config"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        Index("idx_swx_llm_provider_phase_priority", "is_active", "priority"),
        {"extend_existing": True},
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    team_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_team.id", ondelete="CASCADE"), index=True, nullable=True),
    )
    provider: str = Field(sa_column=Column(String(50), nullable=False, index=True))
    credentials: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    default_params: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    supported_phases: list[str] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")))
    cost_per_1k_tokens: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    extra_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    timeout_seconds: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    max_retries: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    circuit_breaker_threshold: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    circuit_breaker_reset_seconds: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    rate_limit_per_minute: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    daily_token_limit: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))

class LLMProviderConfigCreate(LLMProviderConfigBase):
    team_id: uuid.UUID | None = None

class LLMProviderConfigUpdate(SQLModel):
    provider: str | None = Field(default=None, max_length=50)
    name: str | None = Field(default=None, max_length=100)
    model_name: str | None = Field(default=None, max_length=100)
    credentials: dict[str, Any] | None = None
    default_params: dict[str, Any] | None = None
    priority: int | None = None
    is_primary: bool | None = None
    is_active: bool | None = None
    supported_phases: list[str] | None = None
    cost_per_1k_tokens: float | None = None
    supports_streaming: bool | None = None
    supports_json_mode: bool | None = None
    timeout_seconds: int | None = None
    max_retries: int | None = None
    circuit_breaker_threshold: int | None = None
    circuit_breaker_reset_seconds: int | None = None
    rate_limit_per_minute: int | None = None
    daily_token_limit: int | None = None
    extra_data: dict[str, Any] | None = Field(default=None, serialization_alias="metadata")

class LLMProviderConfigPublic(LLMProviderConfigBase):
    id: uuid.UUID
    team_id: uuid.UUID | None = None
    credentials: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True

LLM_PROVIDER_DEFAULTS: list[dict[str, Any]] = [
    {
        "provider": LLMProviderType.OPENAI.value,
        "name": "OpenAI GPT-4o",
        "model_name": "gpt-4o",
        "credentials": {"api_key": "${OPENAI_API_KEY}", "organization": "${OPENAI_ORGANIZATION:-}"},
        "default_params": {"temperature": 0.2, "max_tokens": 2048, "top_p": 1.0},
        "priority": 10,
        "is_primary": True,
        "is_active": True,
        "supported_phases": ["chat", "triage", "analysis"],
        "cost_per_1k_tokens": 0.01,
        "timeout_seconds": 60,
        "max_retries": 3,
        "circuit_breaker_threshold": 5,
        "circuit_breaker_reset_seconds": 30,
        "rate_limit_per_minute": 500,
    },
    {
        "provider": LLMProviderType.AZURE.value,
        "name": "Azure OpenAI GPT-4o",
        "model_name": "gpt-4o",
        "credentials": {"api_key": "${AZURE_OPENAI_API_KEY}", "endpoint": "${AZURE_OPENAI_ENDPOINT}", "deployment": "${AZURE_OPENAI_DEPLOYMENT:-gpt-4o}"},
        "default_params": {"temperature": 0.2, "max_tokens": 2048, "top_p": 1.0},
        "priority": 20,
        "is_primary": False,
        "is_active": False,
        "supported_phases": ["chat", "triage", "analysis"],
        "cost_per_1k_tokens": 0.01,
        "timeout_seconds": 60,
        "max_retries": 3,
        "circuit_breaker_threshold": 5,
        "circuit_breaker_reset_seconds": 30,
        "rate_limit_per_minute": 60,
    },
    {
        "provider": LLMProviderType.ANTHROPIC.value,
        "name": "Anthropic Claude Sonnet",
        "model_name": "claude-3-5-sonnet-latest",
        "credentials": {"api_key": "${ANTHROPIC_API_KEY}"},
        "default_params": {"temperature": 0.2, "max_tokens": 2048, "top_p": 1.0},
        "priority": 30,
        "is_primary": False,
        "is_active": False,
        "supported_phases": ["chat", "analysis"],
        "cost_per_1k_tokens": 0.015,
        "timeout_seconds": 90,
        "max_retries": 2,
        "circuit_breaker_threshold": 5,
        "circuit_breaker_reset_seconds": 30,
        "rate_limit_per_minute": 50,
    },
    {
        "provider": LLMProviderType.OLLAMA.value,
        "name": "Ollama Local",
        "model_name": "llama3.2",
        "credentials": {"base_url": "${OLLAMA_HOST:-http://localhost:11434}"},
        "default_params": {"temperature": 0.4, "max_tokens": 1024, "top_p": 1.0},
        "priority": 100,
        "is_primary": False,
        "is_active": True,
        "supported_phases": ["chat", "triage", "analysis"],
        "cost_per_1k_tokens": 0.0,
        "timeout_seconds": 120,
        "max_retries": 1,
        "circuit_breaker_threshold": 3,
        "circuit_breaker_reset_seconds": 60,
    },
]
