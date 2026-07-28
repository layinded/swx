"""
Unit tests for compliance service logic: field redaction, IP masking, config cache.
"""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


class TestFieldRedaction:
    async def test_redact_known_sensitive_fields(self):
        from swx_core.services.compliance.field_redaction_service import redact_fields

        session = AsyncMock()
        with patch("swx_core.services.compliance.field_redaction_service.get_cached_configs", new_callable=AsyncMock, return_value=[]):
            data = {"ssn": "123-45-6789", "password": "secret123", "name": "John"}
            result = await redact_fields(session, data)

        assert result["ssn"] == "***-**-****"
        assert result["password"] == "[REDACTED]"
        assert result["name"] == "John"

    async def test_redact_email_phone_credit_card_dob(self):
        from swx_core.services.compliance.field_redaction_service import redact_fields

        session = AsyncMock()
        with patch("swx_core.services.compliance.field_redaction_service.get_cached_configs", new_callable=AsyncMock, return_value=[]):
            data = {"email": "user@example.com", "phone": "555-123-4567", "credit_card": "4111222233334444", "dob": "01/15/1990"}
            result = await redact_fields(session, data)

        assert result["email"] == "u***@example.com"
        assert result["phone"] == "***-***-4567"
        assert result["credit_card"] == "****-****-****-4444"
        assert result["dob"] == "XX/XX/1990"

    async def test_redact_nested_dicts(self):
        from swx_core.services.compliance.field_redaction_service import redact_fields

        session = AsyncMock()
        with patch("swx_core.services.compliance.field_redaction_service.get_cached_configs", new_callable=AsyncMock, return_value=[]):
            data = {"user": {"password": "secret", "name": "Jane"}}
            result = await redact_fields(session, data)

        assert result["user"]["password"] == "[REDACTED]"
        assert result["user"]["name"] == "Jane"

    async def test_non_sensitive_fields_untouched(self):
        from swx_core.services.compliance.field_redaction_service import redact_fields

        session = AsyncMock()
        with patch("swx_core.services.compliance.field_redaction_service.get_cached_configs", new_callable=AsyncMock, return_value=[]):
            data = {"username": "jdoe", "age": 30, "active": True}
            result = await redact_fields(session, data)

        assert result == {"username": "jdoe", "age": 30, "active": True}


class TestIPMasking:
    async def test_full_masking_returns_zeros(self):
        from swx_core.services.compliance.ip_masking_service import mask_ip

        session = AsyncMock()
        with patch("swx_core.services.compliance.ip_masking_service.get_masking_config", new_callable=AsyncMock, return_value="full"):
            result = await mask_ip(session, "192.168.1.100")

        assert result == "0.0.0.0"

    async def test_partial_masking_masks_last_two_octets(self):
        from swx_core.services.compliance.ip_masking_service import mask_ip

        session = AsyncMock()
        with patch("swx_core.services.compliance.ip_masking_service.get_masking_config", new_callable=AsyncMock, return_value="partial"):
            result = await mask_ip(session, "192.168.1.100")

        assert result == "192.168.*.*"

    async def test_none_masking_returns_original(self):
        from swx_core.services.compliance.ip_masking_service import mask_ip

        session = AsyncMock()
        with patch("swx_core.services.compliance.ip_masking_service.get_masking_config", new_callable=AsyncMock, return_value="none"):
            result = await mask_ip(session, "192.168.1.100")

        assert result == "192.168.1.100"

    async def test_none_ip_returns_none(self):
        from swx_core.services.compliance.ip_masking_service import mask_ip

        session = AsyncMock()
        result = await mask_ip(session, None)
        assert result is None

    async def test_ipv6_partial_masking(self):
        from swx_core.services.compliance.ip_masking_service import mask_ip

        session = AsyncMock()
        with patch("swx_core.services.compliance.ip_masking_service.get_masking_config", new_callable=AsyncMock, return_value="partial"):
            result = await mask_ip(session, "2001:0db8:85a3:0000:0000:8a2e:0370:7334")

        assert result.startswith("2001:0db8")
        assert "*" in result


class TestConfigCache:
    def test_invalidate_clears_cache(self):
        from swx_core.services.compliance.config_cache import invalidate_compliance_config_cache, _CACHE

        _CACHE["test"] = ([], 0.0)
        invalidate_compliance_config_cache()
        assert len(_CACHE) == 0

    def test_resolve_config_value_with_env_var(self):
        from swx_core.services.compliance.config_cache import resolve_config_value

        os.environ["TEST_COMPLIANCE_VAR"] = "resolved_value"
        result = resolve_config_value("${TEST_COMPLIANCE_VAR}")
        assert result == "resolved_value"
        del os.environ["TEST_COMPLIANCE_VAR"]

    def test_resolve_config_value_with_default(self):
        from swx_core.services.compliance.config_cache import resolve_config_value

        result = resolve_config_value("${NONEXISTENT_VAR:fallback}")
        assert result == "fallback"

    def test_resolve_config_value_plain_string(self):
        from swx_core.services.compliance.config_cache import resolve_config_value

        result = resolve_config_value("plain_string")
        assert result == "plain_string"

    def test_resolve_config_value_json(self):
        from swx_core.services.compliance.config_cache import resolve_config_value

        result = resolve_config_value('{"key": "value"}')
        assert result == {"key": "value"}

    def test_serialize_config_value_masks_secrets(self):
        from swx_core.services.compliance.config_cache import serialize_config_value

        result = serialize_config_value("api_secret_key", "sk-1234567890abcdef")
        assert "1234" in result and "cdef" in result
        assert result != "sk-1234567890abcdef"

    def test_serialize_config_value_preserves_non_secrets(self):
        from swx_core.services.compliance.config_cache import serialize_config_value

        result = serialize_config_value("retention_days", "365")
        assert result == 365


class TestDataAccessCheck:
    async def test_check_data_access_allows_by_default(self):
        from swx_core.services.compliance.compliance_audit_service import check_data_access

        session = AsyncMock()
        with patch("swx_core.services.compliance.compliance_audit_service.get_cached_configs", new_callable=AsyncMock, return_value=[]):
            result = await check_data_access(session, "user", "PUBLIC")

        assert result == "ALLOWED"

    async def test_check_data_access_denied_consent_required(self):
        from swx_core.services.compliance.compliance_audit_service import check_data_access

        session = AsyncMock()
        with patch("swx_core.services.compliance.compliance_audit_service.get_cached_configs", new_callable=AsyncMock, return_value=[]):
            result = await check_data_access(session, "user", "PHI", {"consent_required": True, "consent_granted": False})

        assert result == "DENIED_CONSENT_REQUIRED"