import hashlib
import uuid
from unittest.mock import AsyncMock, patch

from swx_core.events import event_bus


class TestApiKeyEvents:
    async def test_create_api_key_emits_created(self):
        from swx_core.services.auth import api_key_service

        session = AsyncMock()
        user_id = uuid.uuid4()
        key_id = uuid.uuid4()
        created_key = SimpleNamespace(
            id=key_id, name="Test Key", key_prefix="sk_test_",
            hashed_key="abc123", user_id=user_id, is_active=True,
            expires_at=None, rate_limit_override=None,
            metadata_={}, created_at=None, updated_at=None,
        )

        with patch("swx_core.services.auth.api_key_service.repo") as mock_repo:
            mock_repo.create_api_key = AsyncMock(return_value=created_key)
            mock_repo.add_scopes = AsyncMock(return_value=[])
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                from swx_core.models.api_key_scope import ApiKeyCreate
                await api_key_service.create_api_key(session, user_id, ApiKeyCreate(name="Test Key"))

        call = mock_dispatch.call_args
        assert call.args[0] == "api_key.created"
        assert call.kwargs["payload"]["key_prefix"] == "sk_test_"

    async def test_revoke_api_key_emits_revoked(self):
        from swx_core.services.auth import api_key_service

        session = AsyncMock()
        key_id = uuid.uuid4()
        user_id = uuid.uuid4()
        deactivated = SimpleNamespace(id=key_id, user_id=user_id, is_active=False)

        with patch("swx_core.services.auth.api_key_service.repo") as mock_repo:
            mock_repo.get_api_key_by_id = AsyncMock(return_value=SimpleNamespace(id=key_id, user_id=user_id, is_active=True))
            mock_repo.deactivate_api_key = AsyncMock(return_value=deactivated)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                await api_key_service.revoke_api_key(session, key_id, user_id)

        call = mock_dispatch.call_args
        assert call.args[0] == "api_key.revoked"

    async def test_rotate_api_key_emits_rotated(self):
        from swx_core.services.auth import api_key_service

        session = AsyncMock()
        old_key_id = uuid.uuid4()
        user_id = uuid.uuid4()
        old_key = SimpleNamespace(
            id=old_key_id, name="Old Key", user_id=user_id, is_active=True,
            rate_limit_override=None, expires_at=None,
        )

        with patch("swx_core.services.auth.api_key_service.repo") as mock_repo:
            mock_repo.get_api_key_by_id = AsyncMock(return_value=old_key)
            mock_repo.get_scopes_for_key = AsyncMock(return_value=[])
            mock_repo.create_api_key = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
            mock_repo.add_scopes = AsyncMock(return_value=[])
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                await api_key_service.rotate_api_key(session, old_key_id, user_id)

        event_names = [c.args[0] for c in mock_dispatch.call_args_list]
        assert "api_key.rotated" in event_names

    async def test_update_scopes_emits_scope_changed(self):
        from swx_core.services.auth import api_key_service

        session = AsyncMock()
        key_id = uuid.uuid4()
        key = SimpleNamespace(id=key_id, is_active=True)

        with patch("swx_core.services.auth.api_key_service.repo") as mock_repo:
            mock_repo.get_api_key_by_id = AsyncMock(return_value=key)
            mock_repo.add_scopes = AsyncMock(return_value=[])
            mock_repo.get_scopes_for_key = AsyncMock(return_value=[])
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                await api_key_service.update_scopes(session, key_id, add=[{"resource": "billing", "action": "read"}], remove=[])

        call = mock_dispatch.call_args
        assert call.args[0] == "api_key.scope_changed"


class TestApiKeyScopeValidation:
    def test_validate_scope_format_valid(self):
        from swx_core.services.auth.api_key_scope_service import validate_scope_format

        assert validate_scope_format("billing", "read") is True
        assert validate_scope_format("users", "*") is True
        assert validate_scope_format("*", "*") is True

    def test_validate_scope_format_invalid(self):
        from swx_core.services.auth.api_key_scope_service import validate_scope_format

        assert validate_scope_format("", "read") is False
        assert validate_scope_format("billing", "") is False

    def test_check_permission_with_wildcard(self):
        from swx_core.services.auth.api_key_scope_service import check_permission
        from swx_core.models.api_key_scope import ApiKeyScopePublic

        scopes = [
            ApiKeyScopePublic(id=uuid.uuid4(), api_key_id=uuid.uuid4(), resource="billing", action="*", is_active=True),
        ]
        assert check_permission(scopes, "billing", "read") is True
        assert check_permission(scopes, "billing", "write") is True

    def test_check_permission_exact_match(self):
        from swx_core.services.auth.api_key_scope_service import check_permission
        from swx_core.models.api_key_scope import ApiKeyScopePublic

        scopes = [
            ApiKeyScopePublic(id=uuid.uuid4(), api_key_id=uuid.uuid4(), resource="billing", action="read", is_active=True),
        ]
        assert check_permission(scopes, "billing", "read") is True
        assert check_permission(scopes, "billing", "write") is False

    def test_expand_scopes(self):
        from swx_core.services.auth.api_key_scope_service import expand_scopes
        from swx_core.models.api_key_scope import ApiKeyScopePublic

        scopes = [
            ApiKeyScopePublic(id=uuid.uuid4(), api_key_id=uuid.uuid4(), resource="billing", action="read", is_active=True),
            ApiKeyScopePublic(id=uuid.uuid4(), api_key_id=uuid.uuid4(), resource="users", action="*", is_active=True),
        ]
        result = expand_scopes(scopes)
        assert "billing:read" in result
        assert "users:*" in result


class TestApiKeyHashing:
    def test_hash_key_produces_sha256(self):
        from swx_core.models.api_key_scope import _hash_key

        result = _hash_key("test_key_123")
        assert len(result) == 64
        assert result == hashlib.sha256("test_key_123".encode()).hexdigest()

    def test_prefix_extracts_first_8_chars(self):
        from swx_core.models.api_key_scope import _prefix

        result = _prefix("abcdefghijklmnopqrstuvwxyz")
        assert result == "abcdefgh"
        assert len(result) == 8