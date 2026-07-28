"""
Tests for Compliance Audit event emissions.

Validates that all compliance-related events are dispatched correctly
when services perform state changes.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from swx_core.events import event_bus


class TestComplianceAuditEvents:
    """Test event emissions from compliance_audit_service."""

    async def test_record_compliance_audit_emits_data_accessed(self):
        from swx_core.services.compliance import compliance_audit_service

        session = AsyncMock()
        log = SimpleNamespace(
            action="user.viewed",
            data_classification="PII",
            access_result="ALLOWED",
            actor_id=str(uuid.uuid4()),
            resource_id=str(uuid.uuid4()),
        )
        event_bus.clear_fired()

        with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
            await compliance_audit_service.record_compliance_audit(session, log)

        call = mock_dispatch.call_args_list[0]
        assert call.args[0] == "compliance.data_accessed"
        assert call.kwargs["payload"]["action"] == "user.viewed"
        assert call.kwargs["payload"]["classification"] == "PII"

    async def test_record_compliance_audit_emits_consent_violation(self):
        from swx_core.services.compliance import compliance_audit_service

        session = AsyncMock()
        log = SimpleNamespace(
            action="data.read",
            data_classification="PHI",
            access_result="DENIED_CONSENT_REQUIRED",
            actor_id=str(uuid.uuid4()),
            resource_id=str(uuid.uuid4()),
        )
        event_bus.clear_fired()

        with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
            await compliance_audit_service.record_compliance_audit(session, log)

        calls = mock_dispatch.call_args_list
        event_names = [c.args[0] for c in calls]
        assert "compliance.data_accessed" in event_names
        assert "compliance.consent_violation" in event_names

    async def test_generate_compliance_report_emits_data_exported(self):
        from swx_core.services.compliance import compliance_audit_service

        session = AsyncMock()
        event_bus.clear_fired()

        with patch("swx_core.services.compliance.compliance_audit_service.compliance_audit_repository") as mock_repo:
            mock_repo.get_compliance_logs = AsyncMock(return_value=[])
            mock_repo.get_compliance_log_count = AsyncMock(return_value=0)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                await compliance_audit_service.generate_compliance_report(session)

        call = mock_dispatch.call_args
        assert call.args[0] == "compliance.data_exported"
        assert call.kwargs["payload"]["report"] is True

    async def test_upsert_compliance_config_emits_config_updated(self):
        from swx_core.services.compliance import compliance_audit_service

        session = AsyncMock()
        config_data = SimpleNamespace(
            key="ip_masking_mode",
            value="partial",
            category="masking",
            model_dump=lambda: {"key": "ip_masking_mode", "value": "partial", "category": "masking"},
        )
        event_bus.clear_fired()

        with patch("swx_core.services.compliance.compliance_audit_service.compliance_audit_repository") as mock_repo:
            mock_repo.upsert_compliance_config = AsyncMock(return_value=config_data)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                from swx_core.services.compliance.config_cache import invalidate_compliance_config_cache
                invalidate_compliance_config_cache()
                from swx_core.models.compliance_audit import ComplianceConfigCreate
                body = ComplianceConfigCreate(key="ip_masking_mode", value="partial", category="masking")
                await compliance_audit_service.upsert_compliance_config(session, body)

        call = mock_dispatch.call_args
        assert call.args[0] == "compliance.config_updated"
        assert call.kwargs["payload"]["key"] == "ip_masking_mode"


class TestDataSubjectRequestEvents:
    """Test event emissions from data_subject_service."""

    async def test_create_data_subject_request_emits_created(self):
        from swx_core.services.compliance import data_subject_service

        session = AsyncMock()
        user_id = uuid.uuid4()
        request = SimpleNamespace(
            id=uuid.uuid4(), user_id=user_id, request_type="access", verification_token="tok"
        )
        event_bus.clear_fired()

        with patch("swx_core.services.compliance.data_subject_service.compliance_audit_repository") as mock_repo:
            mock_repo.create_data_subject_request = AsyncMock(return_value=request)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                from swx_core.models.compliance_audit import DataSubjectRequestCreate
                body = DataSubjectRequestCreate(request_type="access")
                await data_subject_service.create_data_subject_request(session, user_id, body)

        call = mock_dispatch.call_args
        assert call.args[0] == "compliance.request_created"
        assert call.kwargs["payload"]["request_type"] == "access"

    async def test_verify_request_emits_verified(self):
        from swx_core.services.compliance import data_subject_service

        session = AsyncMock()
        request_id = uuid.uuid4()
        verified = SimpleNamespace(id=request_id, user_id=uuid.uuid4())

        with patch("swx_core.services.compliance.data_subject_service.compliance_audit_repository") as mock_repo:
            mock_repo.get_data_subject_request = AsyncMock(return_value=SimpleNamespace(verification_token="tok", user_id=verified.user_id))
            mock_repo.update_data_subject_request = AsyncMock(return_value=verified)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                await data_subject_service.verify_request(session, request_id, "tok", verified.user_id)

        call = mock_dispatch.call_args
        assert call.args[0] == "compliance.request_verified"

    async def test_cancel_data_subject_request_emits_cancelled(self):
        from swx_core.services.compliance import data_subject_service

        session = AsyncMock()
        request_id = uuid.uuid4()
        user_id = uuid.uuid4()
        cancelled = SimpleNamespace(id=request_id, user_id=user_id)

        with patch("swx_core.services.compliance.data_subject_service.compliance_audit_repository") as mock_repo:
            mock_repo.get_data_subject_request = AsyncMock(return_value=SimpleNamespace(id=request_id, user_id=user_id, status="pending"))
            mock_repo.update_data_subject_request = AsyncMock(return_value=cancelled)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                await data_subject_service.cancel_data_subject_request(session, request_id, user_id)

        call = mock_dispatch.call_args
        assert call.args[0] == "compliance.request_cancelled"


class TestRetentionServiceEvents:
    """Test event emissions from retention_service."""

    async def test_upsert_retention_policy_emits_updated(self):
        from swx_core.services.compliance import retention_service

        session = AsyncMock()
        policy = SimpleNamespace(resource_type="audit_log", retention_days=365, action_on_expiry="anonymize")

        with patch("swx_core.services.compliance.retention_service.compliance_audit_repository") as mock_repo:
            mock_repo.upsert_retention_policy = AsyncMock(return_value=policy)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                from swx_core.models.compliance_audit import RetentionPolicyCreate
                body = RetentionPolicyCreate(resource_type="audit_log", retention_days=365, action_on_expiry="anonymize")
                await retention_service.upsert_retention_policy(session, body)

        call = mock_dispatch.call_args
        assert call.args[0] == "compliance.retention_policy_updated"

    async def test_apply_retention_emits_policy_applied(self):
        from swx_core.services.compliance import retention_service

        session = AsyncMock()
        policy = SimpleNamespace(resource_type="audit_log", retention_days=365, action_on_expiry="anonymize", is_active=True)

        with patch("swx_core.services.compliance.retention_service.compliance_audit_repository") as mock_repo:
            mock_repo.list_retention_policies = AsyncMock(return_value=[policy])
            mock_repo.anonymize_audit_logs_before = AsyncMock(return_value=5)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                await retention_service.apply_retention(session)

        call = mock_dispatch.call_args
        assert call.args[0] == "compliance.retention_policy_applied"
        assert call.kwargs["payload"]["affected"] == 5


class TestFieldRedactionEvents:
    """Test event emissions from field_redaction_service."""

    async def test_add_redaction_rule_emits_updated(self):
        from swx_core.services.compliance import field_redaction_service

        session = AsyncMock()
        config = SimpleNamespace(key="custom_field", value="[REDACTED]", category="redaction")

        with patch("swx_core.services.compliance.field_redaction_service.compliance_audit_repository") as mock_repo:
            mock_repo.upsert_compliance_config = AsyncMock(return_value=config)
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                with patch("swx_core.services.compliance.field_redaction_service.invalidate_compliance_config_cache"):
                    await field_redaction_service.add_redaction_rule(session, "custom_field", "[REDACTED]")

        call = mock_dispatch.call_args
        assert call.args[0] == "compliance.redaction_rule_updated"
        assert call.kwargs["payload"]["key"] == "custom_field"