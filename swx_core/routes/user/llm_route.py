from typing import Any

from fastapi import APIRouter
from sqlmodel import SQLModel

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers import llm_controller
from swx_core.database.db import SessionDep


class LLMGenerateRequest(SQLModel):
    prompt: str
    phase: str = "chat"
    system_prompt: str | None = None
    json_mode: bool = False
    temperature: float = 0.7
    max_tokens: int = 1024
    top_p: float = 1.0
    stop_sequences: list[str] | None = None


router = APIRouter(prefix="/user/llm", tags=["user-llm"])


@router.post("/generate", response_model=dict[str, Any])
async def generate(session: SessionDep, body: LLMGenerateRequest, current_user: UserDep) -> dict[str, Any]:
    payload = body.model_dump()
    return await llm_controller.generate_controller(session, account_id=current_user.id, **payload)


@router.get("/usage", response_model=dict[str, Any])
async def usage(session: SessionDep, current_user: UserDep, skip: int = 0, limit: int = 100) -> dict[str, Any]:
    return await llm_controller.usage_controller(session, current_user.id, skip, limit)
