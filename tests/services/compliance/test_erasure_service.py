# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false, reportAttributeAccessIssue=false, reportOperatorIssue=false

"""Tests for the ErasureService — GDPR right-to-erasure lifecycle."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.services.compliance.erasure_service import (
    cancel_erasure,
    execute_erasure,
    get_erasure_certificate,
    list_erasure_certificates,
    request_erasure,
    _check_sole_owner,
)


def _make_user(user_id: uuid.UUID | None = None, is_active: bool = True) -> MagicMock:
    user = MagicMock(spec=["id", "email", "is_active", "gdpr_deleted_at", "deactivated_at"])
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    user.is_active = is_active
    user.gdpr_deleted_at = datetime.utcnow() + timedelta(days=30)
    user.deactivated_at = None
    return user


def _make_cert(cert_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None, erasure_type: str = "anonymize", status: str = "pending") -> MagicMock:
    cert = MagicMock(spec=["id", "user_id", "erasure_type", "status", "created_at", "updated_at", "tables_affected", "certificate_data", "error_message", "completed_at", "request_id"])
    cert.id = cert_id or uuid.uuid4()
    cert.user_id = user_id or uuid.uuid4()
    cert.erasure_type = erasure_type
    cert.status = status
    cert.created_at = datetime.utcnow()
    cert.updated_at = datetime.utcnow()
    cert.tables_affected = None
    cert.certificate_data = None
    cert.error_message = None
    cert.completed_at = None
    cert.request_id = None
    return cert


class TestRequestErasure:
    """Tests for request_erasure()."""

    @pytest.mark.asyncio
    async def test_request_erasure_blocks_when_sole_org_owner(self):
        user_id = uuid.uuid4()
        org = MagicMock(spec=["__class__", "name"])
        org.__class__.__name__ = "Organization"
        org.name = "Acme Corp"

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo, \
             patch("swx_core.services.compliance.erasure_service._check_sole_owner", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = [org]

            with pytest.raises(Exception) as exc_info:
                await request_erasure(AsyncMock(), user_id)

            assert exc_info.value.status_code == 409
            assert "sole owner" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_request_erasure_blocks_when_sole_team_owner(self):
        user_id = uuid.uuid4()
        team = MagicMock(spec=["__class__", "name"])
        team.__class__.__name__ = "Team"
        team.name = "Engineering"

        with patch("swx_core.services.compliance.erasure_service._check_sole_owner", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = [team]

            with pytest.raises(Exception) as exc_info:
                await request_erasure(AsyncMock(), user_id)

            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_request_erasure_creates_certificate_and_deactivates_user(self):
        user_id = uuid.uuid4()
        user = _make_user(user_id=user_id, is_active=True)
        cert = _make_cert(user_id=user_id)

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo, \
             patch("swx_core.services.compliance.erasure_service._check_sole_owner", new_callable=AsyncMock) as mock_check, \
             patch("swx_core.services.compliance.erasure_service._revoke_auth_session", new_callable=AsyncMock) as mock_revoke, \
             patch("swx_core.services.compliance.erasure_service.event_bus") as mock_bus, \
             patch("swx_core.services.compliance.erasure_service.settings") as mock_settings:
            mock_check.return_value = []
            mock_settings.GDPR_ANONYMIZE_ON_DELETE = False
            mock_settings.GDPR_DELETION_GRACE_DAYS = 30
            mock_repo.create_certificate = AsyncMock(return_value=cert)
            mock_repo.mark_user_for_deletion = AsyncMock(return_value=user)
            mock_bus.dispatch = AsyncMock()

            result = await request_erasure(AsyncMock(), user_id)

            mock_repo.create_certificate.assert_called_once()
            mock_repo.mark_user_for_deletion.assert_called_once()
            mock_revoke.assert_called_once()
            mock_bus.dispatch.assert_called_once()
            assert result.erasure_type == "anonymize"

    @pytest.mark.asyncio
    async def test_request_erasure_raises_404_when_user_not_found(self):
        user_id = uuid.uuid4()
        cert = _make_cert(user_id=user_id)

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo, \
             patch("swx_core.services.compliance.erasure_service._check_sole_owner", new_callable=AsyncMock) as mock_check, \
             patch("swx_core.services.compliance.erasure_service.settings") as mock_settings:
            mock_check.return_value = []
            mock_settings.GDPR_ANONYMIZE_ON_DELETE = False
            mock_settings.GDPR_DELETION_GRACE_DAYS = 30
            mock_repo.create_certificate = AsyncMock(return_value=cert)
            mock_repo.mark_user_for_deletion = AsyncMock(return_value=None)
            mock_repo.update_certificate = AsyncMock()

            with pytest.raises(Exception) as exc_info:
                await request_erasure(AsyncMock(), user_id)
            assert exc_info.value.status_code == 404


class TestExecuteErasure:
    """Tests for execute_erasure()."""

    @pytest.mark.asyncio
    async def test_execute_erasure_blocks_when_sole_owner(self):
        user_id = uuid.uuid4()
        org = MagicMock(spec=["__class__", "name"])
        org.__class__.__name__ = "Organization"
        org.name = "Acme Corp"

        with patch("swx_core.services.compliance.erasure_service._check_sole_owner", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = [org]

            result = await execute_erasure(AsyncMock(), user_id)

            assert result["status"] == "blocked"
            assert "sole owner" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_execute_erasure_anonymize_mode(self):
        user_id = uuid.uuid4()
        user = _make_user(user_id=user_id)
        cert = _make_cert(user_id=user_id)

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo, \
             patch("swx_core.services.compliance.erasure_service._check_sole_owner", new_callable=AsyncMock) as mock_check, \
             patch("swx_core.services.compliance.erasure_service._revoke_auth_session", new_callable=AsyncMock) as mock_revoke, \
             patch("swx_core.services.compliance.erasure_service.event_bus") as mock_bus, \
             patch("swx_core.services.compliance.erasure_service.settings") as mock_settings, \
             patch("swx_core.services.compliance.erasure_service.utc_now") as mock_now:
            mock_check.return_value = []
            mock_settings.GDPR_ANONYMIZE_ON_DELETE = True
            mock_now.return_value = datetime.utcnow()
            mock_repo.create_certificate = AsyncMock(return_value=cert)
            mock_repo.get_user_email = AsyncMock(return_value="test@example.com")
            mock_repo.anonymize_user = AsyncMock(return_value=user)
            mock_repo.delete_user_related_data = AsyncMock(return_value={
                "swx_social_accounts": "deleted:3",
                "swx_audit_logs": "anonymized:5",
            })
            mock_repo.update_certificate = AsyncMock(return_value=cert)
            mock_bus.dispatch = AsyncMock()

            result = await execute_erasure(AsyncMock(), user_id)

            mock_repo.anonymize_user.assert_called_once()
            assert result["status"] == "completed"
            assert "swx_social_accounts" in result["tables_erased"]

    @pytest.mark.asyncio
    async def test_execute_erasure_hard_delete_mode(self):
        user_id = uuid.uuid4()
        user = _make_user(user_id=user_id)
        cert = _make_cert(user_id=user_id)

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo, \
             patch("swx_core.services.compliance.erasure_service._check_sole_owner", new_callable=AsyncMock) as mock_check, \
             patch("swx_core.services.compliance.erasure_service._revoke_auth_session", new_callable=AsyncMock) as mock_revoke, \
             patch("swx_core.services.compliance.erasure_service.event_bus") as mock_bus, \
             patch("swx_core.services.compliance.erasure_service.settings") as mock_settings, \
             patch("swx_core.services.compliance.erasure_service.utc_now") as mock_now:
            mock_check.return_value = []
            mock_settings.GDPR_ANONYMIZE_ON_DELETE = False
            mock_now.return_value = datetime.utcnow()
            mock_repo.create_certificate = AsyncMock(return_value=cert)
            mock_repo.get_user_email = AsyncMock(return_value="test@example.com")
            mock_repo.hard_delete_user = AsyncMock(return_value=user)
            mock_repo.delete_user_related_data = AsyncMock(return_value={
                "swx_social_accounts": "deleted:3",
            })
            mock_repo.update_certificate = AsyncMock(return_value=cert)
            mock_bus.dispatch = AsyncMock()

            result = await execute_erasure(AsyncMock(), user_id)

            mock_repo.hard_delete_user.assert_called_once()
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_execute_erasure_handles_related_data_errors(self):
        user_id = uuid.uuid4()
        user = _make_user(user_id=user_id)
        cert = _make_cert(user_id=user_id)

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo, \
             patch("swx_core.services.compliance.erasure_service._check_sole_owner", new_callable=AsyncMock) as mock_check, \
             patch("swx_core.services.compliance.erasure_service._revoke_auth_session", new_callable=AsyncMock) as mock_revoke, \
             patch("swx_core.services.compliance.erasure_service.event_bus") as mock_bus, \
             patch("swx_core.services.compliance.erasure_service.settings") as mock_settings, \
             patch("swx_core.services.compliance.erasure_service.utc_now") as mock_now:
            mock_check.return_value = []
            mock_settings.GDPR_ANONYMIZE_ON_DELETE = True
            mock_now.return_value = datetime.utcnow()
            mock_repo.create_certificate = AsyncMock(return_value=cert)
            mock_repo.get_user_email = AsyncMock(return_value="test@example.com")
            mock_repo.anonymize_user = AsyncMock(return_value=user)
            mock_repo.delete_user_related_data = AsyncMock(return_value={
                "swx_social_accounts": "deleted:3",
                "swx_sso_sessions": "error:connection failed",
            })
            mock_repo.update_certificate = AsyncMock(return_value=cert)
            mock_bus.dispatch = AsyncMock()

            result = await execute_erasure(AsyncMock(), user_id)

            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_execute_erasure_dispatches_completed_event(self):
        user_id = uuid.uuid4()
        user = _make_user(user_id=user_id)
        cert = _make_cert(user_id=user_id)

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo, \
             patch("swx_core.services.compliance.erasure_service._check_sole_owner", new_callable=AsyncMock) as mock_check, \
             patch("swx_core.services.compliance.erasure_service._revoke_auth_session", new_callable=AsyncMock) as mock_revoke, \
             patch("swx_core.services.compliance.erasure_service.event_bus") as mock_bus, \
             patch("swx_core.services.compliance.erasure_service.settings") as mock_settings, \
             patch("swx_core.services.compliance.erasure_service.utc_now") as mock_now:
            mock_check.return_value = []
            mock_settings.GDPR_ANONYMIZE_ON_DELETE = True
            mock_now.return_value = datetime.utcnow()
            mock_repo.create_certificate = AsyncMock(return_value=cert)
            mock_repo.get_user_email = AsyncMock(return_value="test@example.com")
            mock_repo.anonymize_user = AsyncMock(return_value=user)
            mock_repo.delete_user_related_data = AsyncMock(return_value={})
            mock_repo.update_certificate = AsyncMock(return_value=cert)
            mock_bus.dispatch = AsyncMock()

            await execute_erasure(AsyncMock(), user_id)

            event_calls = [c for c in mock_bus.dispatch.call_args_list if c.args[0] == "gdpr.erasure_completed"]
            assert len(event_calls) == 1


class TestCancelErasure:
    """Tests for cancel_erasure()."""

    @pytest.mark.asyncio
    async def test_cancel_erasure_restores_user(self):
        user_id = uuid.uuid4()
        user = _make_user(user_id=user_id, is_active=False)

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo, \
             patch("swx_core.services.compliance.erasure_service.event_bus") as mock_bus:
            mock_repo.cancel_deletion = AsyncMock(return_value=user)
            mock_bus.dispatch = AsyncMock()

            result = await cancel_erasure(AsyncMock(), user_id)

            assert result["status"] == "restored"
            assert result["user_id"] == str(user_id)
            mock_repo.cancel_deletion.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_erasure_raises_404_when_user_not_found(self):
        user_id = uuid.uuid4()

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo:
            mock_repo.cancel_deletion = AsyncMock(return_value=None)

            with pytest.raises(Exception) as exc_info:
                await cancel_erasure(AsyncMock(), user_id)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_erasure_dispatches_cancelled_event(self):
        user_id = uuid.uuid4()
        user = _make_user(user_id=user_id)

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo, \
             patch("swx_core.services.compliance.erasure_service.event_bus") as mock_bus:
            mock_repo.cancel_deletion = AsyncMock(return_value=user)
            mock_bus.dispatch = AsyncMock()

            await cancel_erasure(AsyncMock(), user_id)

            mock_bus.dispatch.assert_called_once_with("gdpr.erasure_cancelled", payload={"user_id": str(user_id)})


class TestGetErasureCertificate:
    """Tests for get_erasure_certificate()."""

    @pytest.mark.asyncio
    async def test_get_certificate_returns_none_when_not_found(self):
        cert_id = uuid.uuid4()

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo:
            mock_repo.get_certificate = AsyncMock(return_value=None)

            result = await get_erasure_certificate(AsyncMock(), cert_id)

            assert result is None


class TestListErasureCertificates:
    """Tests for list_erasure_certificates()."""

    @pytest.mark.asyncio
    async def test_list_certificates_calls_repository(self):
        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo:
            mock_repo.list_certificates = AsyncMock(return_value=[])

            result = await list_erasure_certificates(AsyncMock())

            mock_repo.list_certificates.assert_called_once()
            assert result == []


class TestCheckSoleOwner:
    """Tests for _check_sole_owner()."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_sole_owned(self):
        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo:
            mock_repo.find_sole_owned_organizations = AsyncMock(return_value=[])
            mock_repo.find_sole_owned_teams = AsyncMock(return_value=[])

            result = await _check_sole_owner(AsyncMock(), uuid.uuid4())

            assert result == []

    @pytest.mark.asyncio
    async def test_returns_orgs_when_sole_owner(self):
        user_id = uuid.uuid4()
        org = MagicMock()
        org.__class__.__name__ = "Organization"
        org.name = "Acme Corp"

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo:
            mock_repo.find_sole_owned_organizations = AsyncMock(return_value=[org])
            mock_repo.find_sole_owned_teams = AsyncMock(return_value=[])

            result = await _check_sole_owner(AsyncMock(), user_id)

            assert len(result) == 1
            assert result[0].name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_returns_teams_when_sole_owner(self):
        user_id = uuid.uuid4()
        team = MagicMock()
        team.__class__.__name__ = "Team"
        team.name = "Engineering"

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo:
            mock_repo.find_sole_owned_organizations = AsyncMock(return_value=[])
            mock_repo.find_sole_owned_teams = AsyncMock(return_value=[team])

            result = await _check_sole_owner(AsyncMock(), user_id)

            assert len(result) == 1
            assert result[0].name == "Engineering"

    @pytest.mark.asyncio
    async def test_returns_both_orgs_and_teams(self):
        user_id = uuid.uuid4()
        org = MagicMock()
        org.__class__.__name__ = "Organization"
        org.name = "Acme Corp"
        team = MagicMock()
        team.__class__.__name__ = "Team"
        team.name = "Engineering"

        with patch("swx_core.services.compliance.erasure_service.erasure_repository") as mock_repo:
            mock_repo.find_sole_owned_organizations = AsyncMock(return_value=[org])
            mock_repo.find_sole_owned_teams = AsyncMock(return_value=[team])

            result = await _check_sole_owner(AsyncMock(), user_id)

            assert len(result) == 2