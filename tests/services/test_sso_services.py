# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from swx_core.models.sso_provider import SSOProviderCreate, SSOProviderUpdate
from swx_core.models.sso_session import SSOSessionCreate, SSOSessionUpdate
from swx_core.services.sso import sso_provider_service, sso_session_service


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def provider_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "provider_type": "saml",
        "name": "Corporate SSO",
        "client_id": "spn-client-id",
        "client_secret": "${SSO_CLIENT_SECRET}",
        "authorization_url": "https://sso.example.com/auth",
        "issuer_url": "https://sso.example.com",
        "sso_url": "https://sso.example.com/sso",
        "certificate": "${SSO_CERTIFICATE}",
        "domain": "example.com",
        "scopes": ["openid", "email"],
        "enabled": True,
        "metadata_": {},
        "created_at": now(),
        "updated_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data, model_dump=lambda: data)


def session_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "provider_id": uuid.uuid4(),
        "status": "active",
        "saml_request_id": None,
        "saml_response": None,
        "expires_at": None,
        "metadata_": {},
        "created_at": now(),
        "updated_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data)


class TestSSOProviderService:
    async def test_create_provider_emits_event_and_invalidates_cache(self):
        session = AsyncMock()
        body = SSOProviderCreate(provider_type="saml", name="Corporate SSO", client_id="spn-client-id", client_secret="${SSO_CLIENT_SECRET}", authorization_url="https://sso.example.com/auth", issuer_url="https://sso.example.com", sso_url="https://sso.example.com/sso", domain="example.com")
        stored = provider_object()
        with patch.object(sso_provider_service.sso_repository, "create_provider", new_callable=AsyncMock, return_value=stored):
            with patch.object(sso_provider_service, "invalidate_provider_cache") as mock_invalidate:
                with patch.object(sso_provider_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await sso_provider_service.create_provider(session, body)
        assert result.client_secret == "***"
        assert result.certificate == "***"
        mock_invalidate.assert_called_once()
        assert mock_dispatch.await_args.args[0] == "sso.provider_created"

    async def test_get_provider_raises_for_missing(self):
        session = AsyncMock()
        provider_id = uuid.uuid4()
        with patch.object(sso_provider_service, "get_cached_provider", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await sso_provider_service.get_provider(session, provider_id)

    async def test_update_provider_emits_event_and_invalidates_cache(self):
        session = AsyncMock()
        provider_id = uuid.uuid4()
        updated = provider_object(id=provider_id, name="Updated SSO")
        body = SSOProviderUpdate(name="Updated SSO")
        with patch.object(sso_provider_service.sso_repository, "update_provider", new_callable=AsyncMock, return_value=updated):
            with patch.object(sso_provider_service, "invalidate_provider_cache") as mock_invalidate:
                with patch.object(sso_provider_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await sso_provider_service.update_provider(session, provider_id, body)
        assert result.name == "Updated SSO"
        mock_invalidate.assert_called_once()
        assert mock_dispatch.await_args.args[0] == "sso.provider_updated"

    async def test_delete_provider_emits_event_and_invalidates_cache(self):
        session = AsyncMock()
        provider_id = uuid.uuid4()
        stored = provider_object(id=provider_id)
        with patch.object(sso_provider_service.sso_repository, "get_provider_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(sso_provider_service.sso_repository, "delete_provider", new_callable=AsyncMock, return_value=True):
                with patch.object(sso_provider_service, "invalidate_provider_cache") as mock_invalidate:
                    with patch.object(sso_provider_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                        result = await sso_provider_service.delete_provider(session, provider_id)
        assert result["success"] is True
        mock_invalidate.assert_called_once()
        assert mock_dispatch.await_args.args[0] == "sso.provider_deleted"

    def test_mask_secret_masks_value(self):
        assert sso_provider_service._mask_secret("my-secret") == "***"
        assert sso_provider_service._mask_secret(None) is None


class TestSSOProviderEncryption:
    """Tests for SSO provider secret/certificate encryption helpers."""

    def test_encrypt_field_round_trip(self) -> None:
        """_encrypt_field then _decrypt_field returns the original plaintext."""
        import base64
        from swx_core.services.sso.sso_provider_service import _encrypt_field, _decrypt_field

        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        with patch.dict(os.environ, {"SWX_ENCRYPTION_KEY": key}):
            import swx_core.security.encryption as enc_mod
            enc_mod._encryption_service = None

            plaintext = "my-sso-client-secret"
            ciphertext = _encrypt_field(plaintext)
            assert ciphertext != plaintext
            assert _decrypt_field(ciphertext) == plaintext

    def test_encrypt_field_produces_versioned_ciphertext(self) -> None:
        """Encrypted SSO fields start with a version prefix."""
        import base64
        from swx_core.services.sso.sso_provider_service import _encrypt_field

        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        with patch.dict(os.environ, {"SWX_ENCRYPTION_KEY": key}):
            import swx_core.security.encryption as enc_mod
            enc_mod._encryption_service = None

            ciphertext = _encrypt_field("certificate-data")
            assert ciphertext.startswith("v")

    def test_decrypt_field_returns_plaintext_unchanged(self) -> None:
        """_decrypt_field returns non-encrypted values as-is."""
        from swx_core.services.sso.sso_provider_service import _decrypt_field

        assert _decrypt_field("plain-secret") == "plain-secret"
        assert _decrypt_field("${ENV_VAR}") == "${ENV_VAR}"

    def test_decrypt_field_handles_none(self) -> None:
        """_decrypt_field handles None gracefully."""
        from swx_core.services.sso.sso_provider_service import _decrypt_field

        assert _decrypt_field(None) is None

    def test_decrypt_field_handles_empty_string(self) -> None:
        """_decrypt_field handles empty string gracefully."""
        from swx_core.services.sso.sso_provider_service import _decrypt_field

        assert _decrypt_field("") == ""

    def test_encrypt_field_fallback_without_key(self) -> None:
        """_encrypt_field returns plaintext when encryption key is not configured."""
        from swx_core.services.sso.sso_provider_service import _encrypt_field

        with patch.dict(os.environ, {}, clear=True):
            import swx_core.security.encryption as enc_mod
            enc_mod._encryption_service = None

            result = _encrypt_field("fallback-secret")
            assert result == "fallback-secret"

    def test_encrypt_field_handles_none(self) -> None:
        """_encrypt_field handles None gracefully."""
        from swx_core.services.sso.sso_provider_service import _encrypt_field

        assert _encrypt_field(None) is None

    def test_to_public_masks_decrypted_fields(self) -> None:
        """_to_public decrypts stored fields and masks them."""
        import base64
        from swx_core.services.sso.sso_provider_service import _to_public
        from swx_core.security.encryption import encrypt_value

        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        with patch.dict(os.environ, {"SWX_ENCRYPTION_KEY": key}):
            import swx_core.security.encryption as enc_mod
            enc_mod._encryption_service = None

            encrypted_secret = encrypt_value("client-secret-123")
            encrypted_cert = encrypt_value("cert-data-456")

            provider = provider_object(client_secret=encrypted_secret, certificate=encrypted_cert)
            result = _to_public(provider)
            assert result.client_secret == "***"
            assert result.certificate == "***"


class TestSSOSessionService:
    async def test_initiate_sso_emits_event(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        provider_id = uuid.uuid4()
        provider = provider_object(id=provider_id, enabled=True)
        sso_session = session_object(user_id=user_id, provider_id=provider_id)
        with patch.object(sso_session_service, "get_cached_provider", new_callable=AsyncMock, return_value=provider):
            with patch.object(sso_session_service.sso_repository, "get_active_session_by_user", new_callable=AsyncMock, return_value=None):
                with patch.object(sso_session_service.sso_repository, "create_session", new_callable=AsyncMock, return_value=sso_session):
                    with patch.object(sso_session_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                        result = await sso_session_service.initiate_sso(session, user_id, provider_id)
        assert result["session_id"] is not None
        assert mock_dispatch.await_args.args[0] == "sso.session_initiated"

    async def test_initiate_sso_raises_for_missing_provider(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        provider_id = uuid.uuid4()
        with patch.object(sso_session_service, "get_cached_provider", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await sso_session_service.initiate_sso(session, user_id, provider_id)

    async def test_complete_sso_login_emits_event(self):
        session = AsyncMock()
        sso_session_id = uuid.uuid4()
        user_id = uuid.uuid4()
        stored = session_object(id=sso_session_id, user_id=user_id)
        updated = session_object(id=sso_session_id, user_id=user_id, status="completed")
        body = SSOSessionUpdate(status="completed", saml_response="response-data")
        with patch.object(sso_session_service.sso_repository, "get_session_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(sso_session_service.sso_repository, "update_session", new_callable=AsyncMock, return_value=updated):
                with patch.object(sso_session_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await sso_session_service.complete_sso_login(session, sso_session_id, body)
        assert mock_dispatch.await_args.args[0] == "sso.session_completed"

    async def test_terminate_session_emits_event(self):
        session = AsyncMock()
        sso_session_id = uuid.uuid4()
        user_id = uuid.uuid4()
        stored = session_object(id=sso_session_id, user_id=user_id, status="active")
        terminated = session_object(id=sso_session_id, user_id=user_id, status="terminated")
        with patch.object(sso_session_service.sso_repository, "get_session_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(sso_session_service.sso_repository, "terminate_session", new_callable=AsyncMock, return_value=terminated):
                with patch.object(sso_session_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await sso_session_service.terminate_session(session, sso_session_id)
        assert mock_dispatch.await_args.args[0] == "sso.session_terminated"

    async def test_get_session_raises_for_missing(self):
        session = AsyncMock()
        session_id = uuid.uuid4()
        with patch.object(sso_session_service.sso_repository, "get_session_by_id", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await sso_session_service._get_session_or_raise(session, session_id)