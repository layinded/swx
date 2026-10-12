# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from swx_core.models.conversation import ConversationCreate, ConversationUpdate
from swx_core.models.conversation_message import ConversationMessageCreate, ConversationMessageUpdate
from swx_core.services.conversation import conversation_service, conversation_message_service


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def conversation_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "title": "Test Conversation",
        "status": "active",
        "metadata_": None,
        "user_id": uuid.uuid4(),
        "created_at": now(),
        "updated_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data, model_dump=lambda: data)


def message_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "conversation_id": uuid.uuid4(),
        "role": "user",
        "content": "Hello",
        "token_count": None,
        "model": None,
        "metadata_": None,
        "parent_message_id": None,
        "created_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data)


class TestConversationService:
    async def test_create_conversation_emits_event(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        body = ConversationCreate(title="Test")
        stored = conversation_object(user_id=user_id)
        with patch.object(conversation_service.conversation_repository, "create_conversation", new_callable=AsyncMock, return_value=stored):
            with patch.object(conversation_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                result = await conversation_service.create_conversation(session, user_id, body)
        assert result.title == "Test Conversation"
        assert mock_dispatch.await_args is not None
        assert mock_dispatch.await_args.args[0] == "conversation.created"

    async def test_get_conversation_raises_for_missing(self):
        session = AsyncMock()
        conversation_id = uuid.uuid4()
        with patch.object(conversation_service.conversation_repository, "get_conversation_by_id", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await conversation_service.get_conversation(session, conversation_id)

    async def test_get_conversation_raises_permission_error_for_wrong_user(self):
        session = AsyncMock()
        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        stored = conversation_object(user_id=owner_id)
        with patch.object(conversation_service.conversation_repository, "get_conversation_by_id", new_callable=AsyncMock, return_value=stored):
            with pytest.raises(PermissionError, match="access denied"):
                await conversation_service.get_conversation(session, stored.id, user_id=other_id)

    async def test_update_conversation_emits_event(self):
        session = AsyncMock()
        conversation_id = uuid.uuid4()
        user_id = uuid.uuid4()
        stored = conversation_object(id=conversation_id, user_id=user_id)
        updated = conversation_object(id=conversation_id, user_id=user_id, title="Updated")
        body = ConversationUpdate(title="Updated")
        with patch.object(conversation_service.conversation_repository, "get_conversation_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(conversation_service.conversation_repository, "update_conversation", new_callable=AsyncMock, return_value=updated):
                with patch.object(conversation_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await conversation_service.update_conversation(session, conversation_id, body, user_id)
        assert result.title == "Updated"
        assert mock_dispatch.await_args.args[0] == "conversation.updated"

    async def test_archive_conversation_emits_event(self):
        session = AsyncMock()
        conversation_id = uuid.uuid4()
        user_id = uuid.uuid4()
        stored = conversation_object(id=conversation_id, user_id=user_id, status="active")
        archived = conversation_object(id=conversation_id, user_id=user_id, status="archived")
        with patch.object(conversation_service.conversation_repository, "get_conversation_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(conversation_service.conversation_repository, "update_conversation", new_callable=AsyncMock, return_value=archived):
                with patch.object(conversation_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await conversation_service.archive_conversation(session, conversation_id, user_id)
        assert result.status == "archived"
        assert mock_dispatch.await_args.args[0] == "conversation.archived"

    async def test_delete_conversation_soft_deletes_and_emits_event(self):
        session = AsyncMock()
        conversation_id = uuid.uuid4()
        user_id = uuid.uuid4()
        stored = conversation_object(id=conversation_id, user_id=user_id, status="active")
        deleted = conversation_object(id=conversation_id, user_id=user_id, status="deleted")
        with patch.object(conversation_service.conversation_repository, "get_conversation_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(conversation_service.conversation_repository, "update_conversation", new_callable=AsyncMock, return_value=deleted):
                with patch.object(conversation_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await conversation_service.delete_conversation(session, conversation_id, user_id)
        assert result.status == "deleted"
        assert mock_dispatch.await_args.args[0] == "conversation.deleted"


class TestConversationMessageService:
    async def test_add_message_emits_event(self):
        session = AsyncMock()
        conversation_id = uuid.uuid4()
        user_id = uuid.uuid4()
        conv = conversation_object(id=conversation_id, user_id=user_id)
        msg = message_object(conversation_id=conversation_id, role="user")
        body = ConversationMessageCreate(role="user", content="Hello")
        with patch.object(conversation_message_service.conversation_repository, "get_conversation_by_id", new_callable=AsyncMock, return_value=conv):
            with patch.object(conversation_message_service.conversation_repository, "create_message", new_callable=AsyncMock, return_value=msg):
                with patch.object(conversation_message_service.conversation_repository, "update_conversation", new_callable=AsyncMock):
                    with patch.object(conversation_message_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                        result = await conversation_message_service.add_message(session, conversation_id, body, user_id)
        assert result.role == "user"
        assert mock_dispatch.await_args.args[0] == "conversation.message_created"

    async def test_add_message_validates_conversation_access(self):
        session = AsyncMock()
        conversation_id = uuid.uuid4()
        other_user = uuid.uuid4()
        body = ConversationMessageCreate(role="user", content="Hello")
        conv = conversation_object(id=conversation_id, user_id=uuid.uuid4())
        with patch.object(conversation_message_service.conversation_repository, "get_conversation_by_id", new_callable=AsyncMock, return_value=conv):
            with pytest.raises(PermissionError, match="access denied"):
                await conversation_message_service.add_message(session, conversation_id, body, other_user)

    async def test_update_message_emits_event(self):
        session = AsyncMock()
        message_id = uuid.uuid4()
        conversation_id = uuid.uuid4()
        msg = message_object(id=message_id, conversation_id=conversation_id)
        updated_msg = message_object(id=message_id, conversation_id=conversation_id, content="Updated")
        body = ConversationMessageUpdate(content="Updated")
        with patch.object(conversation_message_service.conversation_repository, "get_message_by_id", new_callable=AsyncMock, return_value=msg):
            with patch.object(conversation_message_service.conversation_repository, "update_message", new_callable=AsyncMock, return_value=updated_msg):
                with patch.object(conversation_message_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await conversation_message_service.update_message(session, message_id, body)
        assert result.content == "Updated"
        assert mock_dispatch.await_args.args[0] == "conversation.message_updated"