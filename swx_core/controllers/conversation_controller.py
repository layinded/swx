from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.conversation import ConversationCreate, ConversationPublic, ConversationUpdate
from swx_core.models.conversation_message import ConversationMessageCreate, ConversationMessagePublic, ConversationMessageUpdate
from swx_core.services.conversation import conversation_message_service, conversation_service


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


async def create_conversation_controller(session: AsyncSession, user_id: UUID, body: ConversationCreate) -> ConversationPublic:
    return await conversation_service.create_conversation(session, user_id, body)


async def get_conversation_controller(session: AsyncSession, conversation_id: UUID, user_id: UUID | None = None) -> ConversationPublic:
    try:
        return await conversation_service.get_conversation(session, conversation_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_conversations_controller(session: AsyncSession, user_id: UUID | None = None, status: str | None = None, skip: int = 0, limit: int = 50) -> list[ConversationPublic]:
    return await conversation_service.list_conversations(session, user_id=user_id, status=status, skip=skip, limit=limit)


async def update_conversation_controller(session: AsyncSession, conversation_id: UUID, body: ConversationUpdate, user_id: UUID | None = None) -> ConversationPublic:
    try:
        return await conversation_service.update_conversation(session, conversation_id, body, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def archive_conversation_controller(session: AsyncSession, conversation_id: UUID, user_id: UUID | None = None) -> ConversationPublic:
    try:
        return await conversation_service.archive_conversation(session, conversation_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def delete_conversation_controller(session: AsyncSession, conversation_id: UUID, user_id: UUID | None = None) -> ConversationPublic:
    try:
        return await conversation_service.delete_conversation(session, conversation_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def add_message_controller(session: AsyncSession, conversation_id: UUID, body: ConversationMessageCreate, user_id: UUID | None = None) -> ConversationMessagePublic:
    try:
        return await conversation_message_service.add_message(session, conversation_id, body, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_messages_controller(session: AsyncSession, conversation_id: UUID, user_id: UUID | None = None, skip: int = 0, limit: int = 50) -> list[ConversationMessagePublic]:
    try:
        return await conversation_message_service.list_messages(session, conversation_id, user_id, skip=skip, limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def update_message_controller(session: AsyncSession, message_id: UUID, body: ConversationMessageUpdate) -> ConversationMessagePublic:
    try:
        return await conversation_message_service.update_message(session, message_id, body)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
