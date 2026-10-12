# pyright: reportMissingTypeArgument=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers.conversation_controller import (
    add_message_controller,
    archive_conversation_controller,
    create_conversation_controller,
    delete_conversation_controller,
    get_conversation_controller,
    list_conversations_controller,
    list_messages_controller,
    update_conversation_controller,
    update_message_controller,
)
from swx_core.database.db import get_session
from swx_core.models.conversation import ConversationCreate, ConversationPublic, ConversationUpdate
from swx_core.models.conversation_message import ConversationMessageCreate, ConversationMessagePublic, ConversationMessageUpdate

router = APIRouter(prefix="/conversations", tags=["User - Conversations"])


@router.get("", response_model=list[ConversationPublic])
async def list_my_conversations(
    user: UserDep,
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await list_conversations_controller(session, user_id=user.id, status=status, skip=skip, limit=limit)


@router.post("", response_model=ConversationPublic, status_code=201)
async def create_conversation(
    user: UserDep,
    body: ConversationCreate,
    session: AsyncSession = Depends(get_session),
):
    return await create_conversation_controller(session, user.id, body)


@router.get("/{conversation_id}", response_model=ConversationPublic)
async def get_conversation(
    user: UserDep,
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_conversation_controller(session, conversation_id, user.id)


@router.put("/{conversation_id}", response_model=ConversationPublic)
async def update_conversation(
    user: UserDep,
    conversation_id: UUID,
    body: ConversationUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await update_conversation_controller(session, conversation_id, body, user.id)


@router.put("/{conversation_id}/archive", response_model=ConversationPublic)
async def archive_conversation(
    user: UserDep,
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await archive_conversation_controller(session, conversation_id, user.id)


@router.delete("/{conversation_id}", response_model=ConversationPublic)
async def delete_conversation(
    user: UserDep,
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await delete_conversation_controller(session, conversation_id, user.id)


@router.post("/{conversation_id}/messages", response_model=ConversationMessagePublic, status_code=201)
async def add_message(
    user: UserDep,
    conversation_id: UUID,
    body: ConversationMessageCreate,
    session: AsyncSession = Depends(get_session),
):
    return await add_message_controller(session, conversation_id, body, user.id)


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessagePublic])
async def list_messages(
    user: UserDep,
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await list_messages_controller(session, conversation_id, user.id, skip=skip, limit=limit)


@router.put("/messages/{message_id}", response_model=ConversationMessagePublic)
async def update_message(
    message_id: UUID,
    body: ConversationMessageUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await update_message_controller(session, message_id, body)