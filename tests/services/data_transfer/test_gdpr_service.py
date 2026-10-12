# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false, reportArgumentType=false

"""Tests for the GDPR data export service — DataExportService ZIP generation."""

import json
import uuid
import zipfile
from datetime import datetime
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.services.data_transfer.gdpr_service import (
    _model_to_dict,
    _models_to_dicts,
    cancel_deletion,
    export_user_data_zip,
    request_deletion,
)


def _make_user(user_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    user.full_name = "Test User"
    user.is_active = True
    user.auth_provider = "local"
    user.provider_id = None
    user.avatar_url = None
    user.anonymous = False
    user.model_dump = lambda: {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
    }
    return user


def _make_social_account(provider: str = "google") -> MagicMock:
    sa = MagicMock()
    sa.provider = provider
    sa.provider_user_id = "12345"
    sa.model_dump = lambda: {"provider": provider, "provider_user_id": "12345"}
    return sa


class TestModelToDict:
    """Tests for _model_to_dict helper."""

    def test_converts_model_with_model_dump(self):
        obj = MagicMock()
        obj.model_dump = lambda: {"key": "value", "id": "abc"}
        result = _model_to_dict(obj)
        assert result == {"key": "value", "id": "abc"}

    def test_converts_object_without_model_dump(self):
        obj = MagicMock(spec=[])
        obj.name = "Test"
        obj.value = 42
        result = _model_to_dict(obj)
        assert result["name"] == "Test"
        assert result["value"] == 42

    def test_converts_uuid_to_string(self):
        obj = MagicMock(spec=[])
        obj.some_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = _model_to_dict(obj)
        assert isinstance(result["some_id"], str)

    def test_skips_private_attributes(self):
        obj = MagicMock(spec=[])
        obj.public_field = "visible"
        obj._private_field = "hidden"
        result = _model_to_dict(obj)
        assert "public_field" in result
        assert "_private_field" not in result

    def test_converts_datetime_to_isoformat(self):
        from datetime import datetime
        dt = datetime(2026, 1, 15, 12, 30, 0)
        obj = MagicMock(spec=[])
        obj.created_at = dt
        result = _model_to_dict(obj)
        assert result["created_at"] == dt.isoformat()


class TestModelsToDicts:
    """Tests for _models_to_dicts helper."""

    def test_converts_list_of_models(self):
        items = [_make_social_account("google"), _make_social_account("github")]
        result = _models_to_dicts(items)
        assert len(result) == 2
        assert result[0]["provider"] == "google"
        assert result[1]["provider"] == "github"

    def test_returns_empty_list_for_empty_input(self):
        result = _models_to_dicts([])
        assert result == []


class TestExportUserDataZip:
    """Tests for export_user_data_zip()."""

    @pytest.mark.asyncio
    async def test_returns_empty_bytes_when_user_not_found(self):
        session = AsyncMock()

        with patch("swx_core.services.data_transfer.gdpr_service.gdpr_export_repository") as mock_repo:
            mock_repo.get_user_profile = AsyncMock(return_value=None)

            result = await export_user_data_zip(session, uuid.uuid4())

            assert result == b""

    @pytest.mark.asyncio
    async def test_generates_valid_zip_with_profile(self):
        user_id = uuid.uuid4()
        user = _make_user(user_id=user_id)
        session = AsyncMock()

        with patch("swx_core.services.data_transfer.gdpr_service.gdpr_export_repository") as mock_repo, \
             patch("swx_core.services.data_transfer.gdpr_service.event_bus") as mock_bus:
            mock_repo.get_user_profile = AsyncMock(return_value=user)
            mock_repo.get_user_social_accounts = AsyncMock(return_value=[])
            mock_repo.get_user_consents = AsyncMock(return_value=[])
            mock_repo.get_user_notifications = AsyncMock(return_value=[])
            mock_repo.get_user_notification_preferences = AsyncMock(return_value=[])
            mock_repo.get_user_api_keys = AsyncMock(return_value=[])
            mock_repo.get_user_webhook_endpoints = AsyncMock(return_value=[])
            mock_repo.get_user_devices = AsyncMock(return_value=[])
            mock_repo.get_user_exports = AsyncMock(return_value=[])
            mock_repo.get_user_imports = AsyncMock(return_value=[])
            mock_repo.get_user_roles = AsyncMock(return_value=[])
            mock_repo.get_user_team_memberships = AsyncMock(return_value=[])
            mock_repo.get_user_org_memberships = AsyncMock(return_value=[])
            mock_repo.get_user_referral_codes = AsyncMock(return_value=[])
            mock_repo.get_user_referral_events = AsyncMock(return_value=[])
            mock_repo.get_user_onboarding_steps = AsyncMock(return_value=[])
            mock_repo.get_user_flag_evaluations = AsyncMock(return_value=[])
            mock_repo.get_user_audit_logs = AsyncMock(return_value=[])
            mock_repo.get_user_conversations = AsyncMock(return_value=[])
            mock_bus.dispatch = AsyncMock()

            result = await export_user_data_zip(session, user_id)

            assert len(result) > 0
            with zipfile.ZipFile(BytesIO(result)) as zf:
                names = zf.namelist()
                assert "profile.json" in names
                assert "social_accounts.json" in names
                assert "conversations.json" in names
                assert "conversation_messages.json" in names

    @pytest.mark.asyncio
    async def test_zip_contains_all_expected_sections(self):
        user_id = uuid.uuid4()
        user = _make_user(user_id=user_id)
        session = AsyncMock()

        with patch("swx_core.services.data_transfer.gdpr_service.gdpr_export_repository") as mock_repo, \
             patch("swx_core.services.data_transfer.gdpr_service.event_bus") as mock_bus:
            mock_repo.get_user_profile = AsyncMock(return_value=user)
            mock_repo.get_user_social_accounts = AsyncMock(return_value=[_make_social_account()])
            mock_repo.get_user_consents = AsyncMock(return_value=[])
            mock_repo.get_user_notifications = AsyncMock(return_value=[])
            mock_repo.get_user_notification_preferences = AsyncMock(return_value=[])
            mock_repo.get_user_api_keys = AsyncMock(return_value=[])
            mock_repo.get_user_webhook_endpoints = AsyncMock(return_value=[])
            mock_repo.get_user_devices = AsyncMock(return_value=[])
            mock_repo.get_user_exports = AsyncMock(return_value=[])
            mock_repo.get_user_imports = AsyncMock(return_value=[])
            mock_repo.get_user_roles = AsyncMock(return_value=[])
            mock_repo.get_user_team_memberships = AsyncMock(return_value=[])
            mock_repo.get_user_org_memberships = AsyncMock(return_value=[])
            mock_repo.get_user_referral_codes = AsyncMock(return_value=[])
            mock_repo.get_user_referral_events = AsyncMock(return_value=[])
            mock_repo.get_user_onboarding_steps = AsyncMock(return_value=[])
            mock_repo.get_user_flag_evaluations = AsyncMock(return_value=[])
            mock_repo.get_user_audit_logs = AsyncMock(return_value=[])
            mock_repo.get_user_conversations = AsyncMock(return_value=[])
            mock_bus.dispatch = AsyncMock()

            result = await export_user_data_zip(session, user_id)

            with zipfile.ZipFile(BytesIO(result)) as zf:
                names = zf.namelist()
                expected_sections = [
                    "profile.json",
                    "social_accounts.json",
                    "consents.json",
                    "notifications.json",
                    "notification_preferences.json",
                    "api_keys.json",
                    "webhook_endpoints.json",
                    "devices.json",
                    "exports.json",
                    "imports.json",
                    "roles.json",
                    "team_memberships.json",
                    "org_memberships.json",
                    "referral_codes.json",
                    "referral_events.json",
                    "onboarding_steps.json",
                    "flag_evaluations.json",
                    "audit_logs.json",
                    "conversations.json",
                    "conversation_messages.json",
                ]
                for section in expected_sections:
                    assert section in names, f"Missing {section} in ZIP"

    @pytest.mark.asyncio
    async def test_social_accounts_section_contains_data(self):
        user_id = uuid.uuid4()
        user = _make_user(user_id=user_id)
        session = AsyncMock()
        sa = _make_social_account("google")

        with patch("swx_core.services.data_transfer.gdpr_service.gdpr_export_repository") as mock_repo, \
             patch("swx_core.services.data_transfer.gdpr_service.event_bus") as mock_bus:
            mock_repo.get_user_profile = AsyncMock(return_value=user)
            mock_repo.get_user_social_accounts = AsyncMock(return_value=[sa])
            mock_repo.get_user_consents = AsyncMock(return_value=[])
            mock_repo.get_user_notifications = AsyncMock(return_value=[])
            mock_repo.get_user_notification_preferences = AsyncMock(return_value=[])
            mock_repo.get_user_api_keys = AsyncMock(return_value=[])
            mock_repo.get_user_webhook_endpoints = AsyncMock(return_value=[])
            mock_repo.get_user_devices = AsyncMock(return_value=[])
            mock_repo.get_user_exports = AsyncMock(return_value=[])
            mock_repo.get_user_imports = AsyncMock(return_value=[])
            mock_repo.get_user_roles = AsyncMock(return_value=[])
            mock_repo.get_user_team_memberships = AsyncMock(return_value=[])
            mock_repo.get_user_org_memberships = AsyncMock(return_value=[])
            mock_repo.get_user_referral_codes = AsyncMock(return_value=[])
            mock_repo.get_user_referral_events = AsyncMock(return_value=[])
            mock_repo.get_user_onboarding_steps = AsyncMock(return_value=[])
            mock_repo.get_user_flag_evaluations = AsyncMock(return_value=[])
            mock_repo.get_user_audit_logs = AsyncMock(return_value=[])
            mock_repo.get_user_conversations = AsyncMock(return_value=[])
            mock_bus.dispatch = AsyncMock()

            result = await export_user_data_zip(session, user_id)

            with zipfile.ZipFile(BytesIO(result)) as zf:
                sa_data = json.loads(zf.read("social_accounts.json"))
                assert len(sa_data) == 1
                assert sa_data[0]["provider"] == "google"

    @pytest.mark.asyncio
    async def test_dispatches_export_completed_event(self):
        user_id = uuid.uuid4()
        user = _make_user(user_id=user_id)
        session = AsyncMock()

        with patch("swx_core.services.data_transfer.gdpr_service.gdpr_export_repository") as mock_repo, \
             patch("swx_core.services.data_transfer.gdpr_service.event_bus") as mock_bus:
            mock_repo.get_user_profile = AsyncMock(return_value=user)
            mock_repo.get_user_social_accounts = AsyncMock(return_value=[])
            mock_repo.get_user_consents = AsyncMock(return_value=[])
            mock_repo.get_user_notifications = AsyncMock(return_value=[])
            mock_repo.get_user_notification_preferences = AsyncMock(return_value=[])
            mock_repo.get_user_api_keys = AsyncMock(return_value=[])
            mock_repo.get_user_webhook_endpoints = AsyncMock(return_value=[])
            mock_repo.get_user_devices = AsyncMock(return_value=[])
            mock_repo.get_user_exports = AsyncMock(return_value=[])
            mock_repo.get_user_imports = AsyncMock(return_value=[])
            mock_repo.get_user_roles = AsyncMock(return_value=[])
            mock_repo.get_user_team_memberships = AsyncMock(return_value=[])
            mock_repo.get_user_org_memberships = AsyncMock(return_value=[])
            mock_repo.get_user_referral_codes = AsyncMock(return_value=[])
            mock_repo.get_user_referral_events = AsyncMock(return_value=[])
            mock_repo.get_user_onboarding_steps = AsyncMock(return_value=[])
            mock_repo.get_user_flag_evaluations = AsyncMock(return_value=[])
            mock_repo.get_user_audit_logs = AsyncMock(return_value=[])
            mock_repo.get_user_conversations = AsyncMock(return_value=[])
            mock_bus.dispatch = AsyncMock()

            await export_user_data_zip(session, user_id)

            mock_bus.dispatch.assert_called_once_with("gdpr.export_completed", payload={"user_id": str(user_id)})

    @pytest.mark.asyncio
    async def test_fetch_failure_continues_with_empty_section(self):
        user_id = uuid.uuid4()
        user = _make_user(user_id=user_id)
        session = AsyncMock()

        with patch("swx_core.services.data_transfer.gdpr_service.gdpr_export_repository") as mock_repo, \
             patch("swx_core.services.data_transfer.gdpr_service.event_bus") as mock_bus:
            mock_repo.get_user_profile = AsyncMock(return_value=user)
            mock_repo.get_user_social_accounts = AsyncMock(side_effect=Exception("DB error"))
            mock_repo.get_user_consents = AsyncMock(return_value=[])
            mock_repo.get_user_notifications = AsyncMock(return_value=[])
            mock_repo.get_user_notification_preferences = AsyncMock(return_value=[])
            mock_repo.get_user_api_keys = AsyncMock(return_value=[])
            mock_repo.get_user_webhook_endpoints = AsyncMock(return_value=[])
            mock_repo.get_user_devices = AsyncMock(return_value=[])
            mock_repo.get_user_exports = AsyncMock(return_value=[])
            mock_repo.get_user_imports = AsyncMock(return_value=[])
            mock_repo.get_user_roles = AsyncMock(return_value=[])
            mock_repo.get_user_team_memberships = AsyncMock(return_value=[])
            mock_repo.get_user_org_memberships = AsyncMock(return_value=[])
            mock_repo.get_user_referral_codes = AsyncMock(return_value=[])
            mock_repo.get_user_referral_events = AsyncMock(return_value=[])
            mock_repo.get_user_onboarding_steps = AsyncMock(return_value=[])
            mock_repo.get_user_flag_evaluations = AsyncMock(return_value=[])
            mock_repo.get_user_audit_logs = AsyncMock(return_value=[])
            mock_repo.get_user_conversations = AsyncMock(return_value=[])
            mock_bus.dispatch = AsyncMock()

            result = await export_user_data_zip(session, user_id)

            assert len(result) > 0
            with zipfile.ZipFile(BytesIO(result)) as zf:
                sa_data = json.loads(zf.read("social_accounts.json"))
                assert sa_data == []


class TestRequestDeletion:
    """Tests for request_deletion()."""

    @pytest.mark.asyncio
    async def test_delegates_to_erasure_service(self):
        user_id = uuid.uuid4()
        session = AsyncMock()
        mock_cert = MagicMock()
        mock_cert.id = uuid.uuid4()
        mock_cert.erasure_type = "delete"
        mock_cert.created_at = datetime.utcnow()

        with patch("swx_core.services.compliance.erasure_service.request_erasure", new_callable=AsyncMock) as mock_erasure:
            mock_erasure.return_value = mock_cert

            result = await request_deletion(session, user_id)

            mock_erasure.assert_called_once_with(session, user_id)
            assert result["status"] == "deactivated"
            assert "certificate_id" in result


class TestCancelDeletion:
    """Tests for cancel_deletion()."""

    @pytest.mark.asyncio
    async def test_delegates_to_erasure_service(self):
        user_id = uuid.uuid4()
        session = AsyncMock()

        with patch("swx_core.services.compliance.erasure_service.cancel_erasure", new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = {"status": "restored", "user_id": str(user_id)}

            result = await cancel_deletion(session, user_id)

            mock_cancel.assert_called_once_with(session, user_id)
            assert result["status"] == "restored"