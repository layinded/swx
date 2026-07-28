# pyright: reportMissingTypeArgument=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.admin.dependencies import get_current_admin_user
from swx_core.controllers.conversation_controller import (
    archive_conversation_controller,
    delete_conversation_controller,
    get_conversation_controller,
    list_conversations_controller,
    update_conversation_controller,
)
from swx_core.database.db import get_session
from swx_core.models.conversation import ConversationPublic, ConversationUpdate

router = APIRouter(prefix="/conversations", tags=["Admin - Conversations"])


@router.get("", response_model=list[ConversationPublic])
async def list_conversations(
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await list_conversations_controller(session, status=status, skip=skip, limit=limit)


@router.get("/{conversation_id}", response_model=ConversationPublic)
async def get_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await get_conversation_controller(session, conversation_id)


@router.put("/{conversation_id}", response_model=ConversationPublic)
async def update_conversation(
    conversation_id: UUID,
    body: ConversationUpdate,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await update_conversation_controller(session, conversation_id, body)


@router.put("/{conversation_id}/archive", response_model=ConversationPublic)
async def archive_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await archive_conversation_controller(session, conversation_id)


@router.delete("/{conversation_id}", response_model=ConversationPublic)
async def delete_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await delete_conversation_controller(session, conversation_id)
