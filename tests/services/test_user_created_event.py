"""
Tests for user.created event emission during registration.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Skip entire module if passlib is not installed (required by auth_service)
pytest.importorskip("passlib")

from swx_core.events.dispatcher import EventBus, Event
from swx_core.models.user import User, UserCreate


class TestUserCreatedEvent:
    async def test_register_user_emits_event(self):
        from swx_core.services.auth_service import register_user_service
        
        mock_session = AsyncMock()
        mock_request = MagicMock()
        user_create = UserCreate(
            email="test@example.com",
            password="testpassword123",
            full_name="Test User",
        )
        
        mock_user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            full_name="Test User",
            auth_provider="local",
        )
        
        with patch("swx_core.services.auth_service.get_user_by_email", return_value=None):
            with patch("swx_core.services.auth_service.create_user", return_value=mock_user):
                with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                    await register_user_service(
                        session=mock_session,
                        user_in=user_create,
                        request=mock_request,
                    )
                    
                    assert mock_emit.called
                    call_args = mock_emit.call_args
                    event = call_args[0][0]
                    
                    assert event.name == "user.created"
                    assert "id" in event.payload
                    assert event.payload["data"]["email"] == "test@example.com"

    async def test_register_user_with_event_context(self):
        from swx_core.services.auth_service import register_user_service
        
        mock_session = AsyncMock()
        mock_request = MagicMock()
        user_create = UserCreate(
            email="patient@example.com",
            password="testpassword123",
            full_name="Patient User",
        )
        
        mock_user = User(
            id=uuid.uuid4(),
            email="patient@example.com",
            full_name="Patient User",
            auth_provider="local",
        )
        
        event_context = {
            "user_type": "patient",
            "hospital_id": "hospital-uuid-123",
            "registration_source": "mobile_app",
        }
        
        with patch("swx_core.services.auth_service.get_user_by_email", return_value=None):
            with patch("swx_core.services.auth_service.create_user", return_value=mock_user):
                with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                    await register_user_service(
                        session=mock_session,
                        user_in=user_create,
                        request=mock_request,
                        event_context=event_context,
                    )
                    
                    assert mock_emit.called
                    call_args = mock_emit.call_args
                    event = call_args[0][0]
                    
                    assert event.name == "user.created"
                    assert event.payload["context"] == event_context
                    assert event.payload["context"]["user_type"] == "patient"

    async def test_register_user_without_event_context(self):
        from swx_core.services.auth_service import register_user_service
        
        mock_session = AsyncMock()
        mock_request = MagicMock()
        user_create = UserCreate(
            email="standard@example.com",
            password="testpassword123",
            full_name="Standard User",
        )
        
        mock_user = User(
            id=uuid.uuid4(),
            email="standard@example.com",
            full_name="Standard User",
            auth_provider="local",
        )
        
        with patch("swx_core.services.auth_service.get_user_by_email", return_value=None):
            with patch("swx_core.services.auth_service.create_user", return_value=mock_user):
                with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                    await register_user_service(
                        session=mock_session,
                        user_in=user_create,
                        request=mock_request,
                    )
                    
                    assert mock_emit.called
                    call_args = mock_emit.call_args
                    event = call_args[0][0]
                    
                    assert event.name == "user.created"
                    assert "id" in event.payload
                    assert "data" in event.payload

    async def test_user_created_event_payload_structure(self):
        from swx_core.services.auth_service import register_user_service
        
        mock_session = AsyncMock()
        mock_request = MagicMock()
        user_create = UserCreate(
            email="structure@example.com",
            password="testpassword123",
            full_name="Structure Test",
        )
        
        user_id = uuid.uuid4()
        mock_user = User(
            id=user_id,
            email="structure@example.com",
            full_name="Structure Test",
            auth_provider="local",
        )
        
        with patch("swx_core.services.auth_service.get_user_by_email", return_value=None):
            with patch("swx_core.services.auth_service.create_user", return_value=mock_user):
                with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                    await register_user_service(
                        session=mock_session,
                        user_in=user_create,
                        request=mock_request,
                        event_context={"source": "test"},
                    )
                    
                    call_args = mock_emit.call_args
                    event = call_args[0][0]
                    
                    # Verify payload structure matches BaseService convention
                    assert event.payload["id"] == str(user_id)
                    assert "data" in event.payload
                    assert "email" in event.payload["data"]
                    assert "full_name" in event.payload["data"]
                    assert "auth_provider" in event.payload["data"]
                    assert "context" in event.payload