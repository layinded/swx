from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import SQLModel

from swx_core.auth.admin.dependencies import get_current_admin_user
from swx_core.controllers import llm_controller
from swx_core.database.db import SessionDep
from swx_core.models.llm_provider_config import LLMProviderConfigCreate, LLMProviderConfigPublic, LLMProviderConfigUpdate


class LLMGenerateRequest(SQLModel):
    prompt: str
    phase: str = "chat"
    system_prompt: str | None = None
    json_mode: bool = False
    temperature: float = 0.7
    max_tokens: int = 1024
    top_p: float = 1.0
    stop_sequences: list[str] | None = None
    account_id: UUID | None = None


router = APIRouter(prefix="/admin/llm", tags=["admin-llm"], dependencies=[Depends(get_current_admin_user)])


@router.post("/providers", response_model=LLMProviderConfigPublic, status_code=201)
async def create_provider(session: SessionDep, body: LLMProviderConfigCreate) -> LLMProviderConfigPublic:
    return await llm_controller.create_provider_controller(session, body)


@router.get("/providers", response_model=list[LLMProviderConfigPublic])
async def list_providers(session: SessionDep, active_only: bool = False) -> list[LLMProviderConfigPublic]:
    return await llm_controller.list_providers_controller(session, active_only)


@router.get("/providers/{config_id}", response_model=LLMProviderConfigPublic)
async def get_provider(session: SessionDep, config_id: UUID) -> LLMProviderConfigPublic:
    return await llm_controller.get_provider_controller(session, config_id)


@router.put("/providers/{config_id}", response_model=LLMProviderConfigPublic)
async def update_provider(session: SessionDep, config_id: UUID, body: LLMProviderConfigUpdate) -> LLMProviderConfigPublic:
    return await llm_controller.update_provider_controller(session, config_id, body)


@router.delete("/providers/{config_id}", response_model=dict[str, bool])
async def delete_provider(session: SessionDep, config_id: UUID) -> dict[str, bool]:
    return await llm_controller.delete_provider_controller(session, config_id)


@router.post("/generate", response_model=dict[str, Any])
async def generate(session: SessionDep, body: LLMGenerateRequest) -> dict[str, Any]:
    payload = body.model_dump()
    return await llm_controller.generate_controller(session, **payload)


@router.get("/health", response_model=dict[str, bool])
async def health(session: SessionDep) -> dict[str, bool]:
    return await llm_controller.health_controller(session)


@router.get("/usage/{account_id}", response_model=dict[str, Any])
async def usage(session: SessionDep, account_id: UUID, skip: int = 0, limit: int = 100) -> dict[str, Any]:
    return await llm_controller.usage_controller(session, account_id, skip, limit)
