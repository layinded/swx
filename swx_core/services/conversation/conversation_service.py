# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.conversation import Conversation, ConversationCreate, ConversationPublic, ConversationUpdate
from swx_core.repositories import conversation_repository


async def _get_conversation_or_raise(session: AsyncSession, conversation_id: UUID, user_id: UUID | None = None) -> Conversation:
    conversation = await conversation_repository.get_conversation_by_id(session, conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found")
    if user_id is not None and conversation.user_id != user_id:
        raise PermissionError("Conversation access denied")
    return conversation


async def create_conversation(session: AsyncSession, user_id: UUID, body: ConversationCreate) -> ConversationPublic:
    conversation_data: dict[str, Any] = {**body.model_dump(exclude_unset=True), "user_id": user_id, "status": "active"}
    conversation = await conversation_repository.create_conversation(session, conversation_data)
    await event_bus.dispatch("conversation.created", payload={"conversation_id": str(conversation.id), "user_id": str(user_id)})
    return ConversationPublic.model_validate(conversation)


async def get_conversation(session: AsyncSession, conversation_id: UUID, user_id: UUID | None = None) -> ConversationPublic:
    conversation = await _get_conversation_or_raise(session, conversation_id, user_id)
    return ConversationPublic.model_validate(conversation)


async def list_conversations(session: AsyncSession, user_id: UUID | None = None, status: str | None = None, skip: int = 0, limit: int = 50) -> list[ConversationPublic]:
    conversations = await conversation_repository.list_conversations(session, user_id=user_id, status=status, skip=skip, limit=limit)
    return [ConversationPublic.model_validate(conversation) for conversation in conversations]


async def update_conversation(session: AsyncSession, conversation_id: UUID, body: ConversationUpdate, user_id: UUID | None = None) -> ConversationPublic:
    conversation = await _get_conversation_or_raise(session, conversation_id, user_id)
    updated_conversation = await conversation_repository.update_conversation(session, conversation_id, body.model_dump(exclude_unset=True))
    await event_bus.dispatch("conversation.updated", payload={"conversation_id": str(conversation_id), "user_id": str(conversation.user_id)})
    return ConversationPublic.model_validate(updated_conversation or conversation)


async def archive_conversation(session: AsyncSession, conversation_id: UUID, user_id: UUID | None = None) -> ConversationPublic:
    conversation = await _get_conversation_or_raise(session, conversation_id, user_id)
    updated_conversation = await conversation_repository.update_conversation(session, conversation_id, {"status": "archived"})
    await event_bus.dispatch("conversation.archived", payload={"conversation_id": str(conversation_id), "user_id": str(conversation.user_id)})
    return ConversationPublic.model_validate(updated_conversation or conversation)


async def delete_conversation(session: AsyncSession, conversation_id: UUID, user_id: UUID | None = None) -> ConversationPublic:
    conversation = await _get_conversation_or_raise(session, conversation_id, user_id)
    updated_conversation = await conversation_repository.update_conversation(session, conversation_id, {"status": "deleted"})
    await event_bus.dispatch("conversation.deleted", payload={"conversation_id": str(conversation_id), "user_id": str(conversation.user_id)})
    return ConversationPublic.model_validate(updated_conversation or conversation)
