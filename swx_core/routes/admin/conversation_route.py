# pyright: reportMissingTypeArgument=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.admin.dependencies import AdminUserDep
from swx_core.controllers.conversation_controller import (
    archive_conversation_controller,
    delete_conversation_controller,
    get_conversation_controller,
    list_conversations_controller,
    update_conversation_controller,
)
from swx_core.database.db import get_session
from swx_core.models.conversation import ConversationPublic, ConversationUpdate

router = APIRouter(prefix="/admin/conversations", tags=["Admin - Conversations"])


@router.get("", response_model=list[ConversationPublic])
async def list_conversations(
    _admin: AdminUserDep,
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await list_conversations_controller(session, status=status, skip=skip, limit=limit)


@router.get("/{conversation_id}", response_model=ConversationPublic)
async def get_conversation(
    _admin: AdminUserDep,
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_conversation_controller(session, conversation_id)


@router.put("/{conversation_id}", response_model=ConversationPublic)
async def update_conversation(
    _admin: AdminUserDep,
    conversation_id: UUID,
    body: ConversationUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await update_conversation_controller(session, conversation_id, body)


@router.put("/{conversation_id}/archive", response_model=ConversationPublic)
async def archive_conversation(
    _admin: AdminUserDep,
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await archive_conversation_controller(session, conversation_id)


@router.delete("/{conversation_id}", response_model=ConversationPublic)
async def delete_conversation(
    _admin: AdminUserDep,
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await delete_conversation_controller(session, conversation_id)