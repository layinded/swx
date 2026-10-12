# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.conversation import Conversation
from swx_core.models.conversation_message import ConversationMessageCreate, ConversationMessagePublic, ConversationMessageUpdate
from swx_core.repositories import conversation_repository


async def _get_conversation_or_raise(session: AsyncSession, conversation_id: UUID, user_id: UUID | None = None) -> Conversation:
    conversation = await conversation_repository.get_conversation_by_id(session, conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found")
    if user_id is not None and conversation.user_id != user_id:
        raise PermissionError("Conversation access denied")
    return conversation


async def add_message(session: AsyncSession, conversation_id: UUID, body: ConversationMessageCreate, user_id: UUID | None = None) -> ConversationMessagePublic:
    await _get_conversation_or_raise(session, conversation_id, user_id)
    message_data = {**body.model_dump(exclude_unset=True), "conversation_id": conversation_id}
    message = await conversation_repository.create_message(session, message_data)
    await conversation_repository.update_conversation(session, conversation_id, {"status": "active"})
    await event_bus.dispatch("conversation.message_created", payload={"conversation_id": str(conversation_id), "message_id": str(message.id), "role": message.role})
    return ConversationMessagePublic.model_validate(message)


async def get_message(session: AsyncSession, message_id: UUID) -> ConversationMessagePublic:
    message = await conversation_repository.get_message_by_id(session, message_id)
    if message is None:
        raise ValueError("Message not found")
    return ConversationMessagePublic.model_validate(message)


async def list_messages(session: AsyncSession, conversation_id: UUID, user_id: UUID | None = None, skip: int = 0, limit: int = 50) -> list[ConversationMessagePublic]:
    await _get_conversation_or_raise(session, conversation_id, user_id)
    messages = await conversation_repository.list_messages(session, conversation_id=conversation_id, skip=skip, limit=limit)
    return [ConversationMessagePublic.model_validate(message) for message in messages]


async def update_message(session: AsyncSession, message_id: UUID, body: ConversationMessageUpdate) -> ConversationMessagePublic:
    message = await conversation_repository.get_message_by_id(session, message_id)
    if message is None:
        raise ValueError("Message not found")
    updated_message = await conversation_repository.update_message(session, message_id, body.model_dump(exclude_unset=True))
    await event_bus.dispatch("conversation.message_updated", payload={"conversation_id": str(message.conversation_id), "message_id": str(message_id)})
    return ConversationMessagePublic.model_validate(updated_message or message)
