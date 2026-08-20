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
from swx_core.models.user import User

router = APIRouter(prefix="/conversations", tags=["User - Conversations"])


def _current_user_id(user: User) -> UUID:
    return user.id


@router.get("", response_model=list[ConversationPublic])
async def list_my_conversations(
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(UserDep),
):
    user_id = _current_user_id(user)
    return await list_conversations_controller(session, user_id=user_id, status=status, skip=skip, limit=limit)


@router.post("", response_model=ConversationPublic, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(UserDep),
):
    user_id = _current_user_id(user)
    return await create_conversation_controller(session, user_id, body)


@router.get("/{conversation_id}", response_model=ConversationPublic)
async def get_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(UserDep),
):
    user_id = _current_user_id(user)
    return await get_conversation_controller(session, conversation_id, user_id)


@router.put("/{conversation_id}", response_model=ConversationPublic)
async def update_conversation(
    conversation_id: UUID,
    body: ConversationUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(UserDep),
):
    user_id = _current_user_id(user)
    return await update_conversation_controller(session, conversation_id, body, user_id)


@router.put("/{conversation_id}/archive", response_model=ConversationPublic)
async def archive_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(UserDep),
):
    user_id = _current_user_id(user)
    return await archive_conversation_controller(session, conversation_id, user_id)


@router.delete("/{conversation_id}", response_model=ConversationPublic)
async def delete_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(UserDep),
):
    user_id = _current_user_id(user)
    return await delete_conversation_controller(session, conversation_id, user_id)


@router.post("/{conversation_id}/messages", response_model=ConversationMessagePublic, status_code=201)
async def add_message(
    conversation_id: UUID,
    body: ConversationMessageCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(UserDep),
):
    user_id = _current_user_id(user)
    return await add_message_controller(session, conversation_id, body, user_id)


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessagePublic])
async def list_messages(
    conversation_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(UserDep),
):
    user_id = _current_user_id(user)
    return await list_messages_controller(session, conversation_id, user_id, skip=skip, limit=limit)


@router.put("/messages/{message_id}", response_model=ConversationMessagePublic)
async def update_message(
    message_id: UUID,
    body: ConversationMessageUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(UserDep),
):
    return await update_message_controller(session, message_id, body)
