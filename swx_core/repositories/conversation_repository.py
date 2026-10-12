# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false, reportAttributeAccessIssue=false

from typing import Any
from uuid import UUID
from swx_core.utils.time import utc_now

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.conversation import Conversation
from swx_core.models.conversation_message import ConversationMessage

def _apply_updates(instance: Any, updates: dict[str, Any]) -> Any:
    for field_name, value in updates.items():
        setattr(instance, field_name, value)
    return instance

async def create_conversation(session: AsyncSession, data: dict[str, Any]) -> Conversation:
    conversation = Conversation(**data)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation

async def get_conversation_by_id(session: AsyncSession, conversation_id: UUID) -> Conversation | None:
    return await session.get(Conversation, conversation_id)

async def list_conversations(session: AsyncSession, *, user_id: UUID | None = None, status: str | None = None, skip: int = 0, limit: int = 50) -> list[Conversation]:
    stmt = select(Conversation)
    if user_id is not None:
        stmt = stmt.where(Conversation.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Conversation.status == status)
    stmt = stmt.order_by(Conversation.updated_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())

async def update_conversation(session: AsyncSession, conversation_id: UUID, data: dict[str, Any]) -> Conversation | None:
    conversation = await get_conversation_by_id(session, conversation_id)
    if conversation is None:
        return None
    _apply_updates(conversation, {**data, "updated_at": utc_now()})
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation

async def get_conversation_count(session: AsyncSession, *, user_id: UUID | None = None, status: str | None = None) -> int:
    stmt = select(func.count()).select_from(Conversation)
    if user_id is not None:
        stmt = stmt.where(Conversation.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Conversation.status == status)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)

async def create_message(session: AsyncSession, data: dict[str, Any]) -> ConversationMessage:
    message = ConversationMessage(**data)
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message

async def get_message_by_id(session: AsyncSession, message_id: UUID) -> ConversationMessage | None:
    return await session.get(ConversationMessage, message_id)

async def list_messages(session: AsyncSession, *, conversation_id: UUID, skip: int = 0, limit: int = 50) -> list[ConversationMessage]:
    stmt = (
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())

async def update_message(session: AsyncSession, message_id: UUID, data: dict[str, Any]) -> ConversationMessage | None:
    message = await get_message_by_id(session, message_id)
    if message is None:
        return None
    _apply_updates(message, data)
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message

async def get_message_count(session: AsyncSession, conversation_id: UUID) -> int:
    stmt = select(func.count()).select_from(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)
