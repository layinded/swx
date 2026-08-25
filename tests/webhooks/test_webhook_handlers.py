"""Unit tests for Paystack and Flutterwave webhook handlers."""

import hashlib
import hmac
import json

import pytest

from swx_core.config.settings import settings
from swx_core.utils.currency import kobo_to_nano, provider_amount_to_nano
from swx_core.webhooks.paystack_webhook import (
    PaystackWebhookResult,
    _extract_payload_fields as paystack_extract,
    _parse_reference_prefix as paystack_parse_ref,
    _resolve_webhook_secret as paystack_resolve_secret,
    _verify_signature as paystack_verify,
)
from swx_core.webhooks.flutterwave_webhook import (
    FlutterwaveWebhookResult,
    _extract_payload_fields as flutterwave_extract,
    _parse_reference_prefix as flutterwave_parse_ref,
    _resolve_webhook_secret as flutterwave_resolve_secret,
    _verify_signature as flutterwave_verify,
)


class TestPaystackSignature:
    def _sign(self, payload: bytes, secret: str) -> str:
        return hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()

    def test_valid_signature(self):
        payload = b'{"event":"charge.success"}'
        secret = "sk_test_abc123"
        signature = self._sign(payload, secret)
        assert paystack_verify(payload, signature, secret) is True

    def test_invalid_signature(self):
        payload = b'{"event":"charge.success"}'
        assert paystack_verify(payload, "wrong_signature", "sk_test_abc123") is False

    def test_tampered_payload(self):
        payload = b'{"event":"charge.success"}'
        secret = "sk_test_abc123"
        signature = self._sign(payload, secret)
        assert paystack_verify(b'{"event":"charge.failed"}', signature, secret) is False

    def test_empty_signature(self):
        assert paystack_verify(b'{"event":"charge.success"}', "", "secret") is False

    def test_wrong_secret(self):
        payload = b'{"event":"charge.success"}'
        signature = self._sign(payload, "correct_secret")
        assert paystack_verify(payload, signature, "wrong_secret") is False


class TestPaystackPayloadExtraction:
    def test_valid_fields(self):
        data = {
            "reference": "ref_abc123",
            "amount": 100_000,
            "customer": {"email": "user@example.com"},
            "currency": "NGN",
            "status": "success",
        }
        result = paystack_extract(data)
        assert result is not None
        assert result[0] == "ref_abc123"
        assert result[1] == 100_000
        assert result[2] == "user@example.com"
        assert result[3] == "NGN"
        assert result[4] == "success"

    def test_missing_reference(self):
        data = {"amount": 100_000, "customer": {"email": "user@example.com"}}
        assert paystack_extract(data) is None

    def test_missing_amount(self):
        data = {"reference": "ref_abc", "customer": {"email": "user@example.com"}}
        assert paystack_extract(data) is None

    def test_missing_email(self):
        data = {"reference": "ref_abc", "amount": 100_000, "customer": {}}
        assert paystack_extract(data) is None

    def test_no_customer_object(self):
        data = {"reference": "ref_abc", "amount": 100_000}
        assert paystack_extract(data) is None

    def test_amount_as_string_fails(self):
        data = {"reference": "ref_abc", "amount": "100000", "customer": {"email": "u@e.com"}}
        assert paystack_extract(data) is None

    def test_default_currency(self):
        from swx_core.config.settings import settings
        data = {
            "reference": "ref_abc",
            "amount": 100_000,
            "customer": {"email": "user@example.com"},
            "status": "success",
        }
        result = paystack_extract(data)
        assert result is not None
        assert result[3] == settings.DEFAULT_BASE_CURRENCY


class TestFlutterwaveSignature:
    def _sign(self, payload: bytes, secret: str) -> str:
        return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    def test_valid_signature(self):
        payload = b'{"event":"charge.completed"}'
        secret = "flw_secret_123"
        signature = self._sign(payload, secret)
        assert flutterwave_verify(payload, signature, secret) is True

    def test_invalid_signature(self):
        assert flutterwave_verify(b'{"event":"charge.completed"}', "wrong", "secret") is False

    def test_empty_signature(self):
        assert flutterwave_verify(b'{"event":"charge.completed"}', "", "secret") is False

    def test_different_algorithm_from_paystack(self):
        payload = b'{"event":"charge.completed"}'
        secret = "shared_secret"
        sha512_sig = hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()
        assert flutterwave_verify(payload, sha512_sig, secret) is False


class TestFlutterwavePayloadExtraction:
    def test_valid_fields(self):
        data = {
            "tx_ref": "flw_ref_123",
            "amount": 1000,
            "customer": {"email": "user@example.com"},
            "currency": "NGN",
            "status": "successful",
        }
        result = flutterwave_extract(data)
        assert result is not None
        assert result[0] == "flw_ref_123"
        assert result[1] == 1000
        assert result[2] == "user@example.com"
        assert result[4] == "successful"

    def test_uses_tx_ref_not_reference(self):
        data = {
            "reference": "should_be_ignored",
            "tx_ref": "flw_ref_123",
            "amount": 1000,
            "customer": {"email": "user@example.com"},
            "status": "successful",
        }
        result = flutterwave_extract(data)
        assert result is not None
        assert result[0] == "flw_ref_123"

    def test_missing_tx_ref(self):
        data = {"amount": 1000, "customer": {"email": "user@example.com"}}
        assert flutterwave_extract(data) is None

    def test_float_amount_converted_to_int(self):
        data = {
            "tx_ref": "flw_ref",
            "amount": 1000.0,
            "customer": {"email": "user@example.com"},
            "status": "successful",
        }
        result = flutterwave_extract(data)
        assert result is not None
        assert isinstance(result[1], int)
        assert result[1] == 1000

    def test_status_is_successful_not_success(self):
        data = {
            "tx_ref": "flw_ref",
            "amount": 1000,
            "customer": {"email": "user@example.com"},
            "status": "success",
        }
        result = flutterwave_extract(data)
        assert result is not None
        assert result[4] == "success"


class TestWebhookResultDataclasses:
    def test_paystack_result_defaults(self):
        result = PaystackWebhookResult(status="success")
        assert result.status == "success"
        assert result.reference is None
        assert result.event_type is None
        assert result.message is None

    def test_flutterwave_result_defaults(self):
        result = FlutterwaveWebhookResult(status="ignored", message="Not supported")
        assert result.status == "ignored"
        assert result.message == "Not supported"
        assert result.reference is None


class TestCurrencyConversionInWebhookContext:
    def test_paystack_kobo_to_nano_for_wallet_credit(self):
        kobo_amount = 100_000
        nano_amount = kobo_to_nano(kobo_amount)
        assert nano_amount == 10_000_000_000

    def test_flutterwave_major_to_nano_for_wallet_credit(self):
        major_amount = 1000
        nano_amount = provider_amount_to_nano(major_amount, "NGN", "flutterwave")
        assert nano_amount == 10_000_000_000

    def test_both_providers_same_nano_result(self):
        paystack_kobo = 100_000
        flutterwave_major = 1000
        assert kobo_to_nano(paystack_kobo) == provider_amount_to_nano(flutterwave_major, "NGN", "flutterwave")


class TestReferencePrefixParsing:
    """SWX-011: webhook must parse reference prefix to route plan vs pack payments."""

    def test_plan_prefix(self):
        prefix, key = paystack_parse_ref("plan-pro_v1-a1b2c3d4e5f6")
        assert prefix == "plan"
        assert key == "pro_v1"

    def test_pack_prefix(self):
        prefix, key = paystack_parse_ref("pack-starter_50k-a1b2c3d4e5f6")
        assert prefix == "pack"
        assert key == "starter_50k"

    def test_plan_key_with_hyphens(self):
        prefix, key = paystack_parse_ref("plan-pro-v1-a1b2c3d4e5f6")
        assert prefix == "plan"
        assert key == "pro-v1"

    def test_pack_key_with_hyphens(self):
        prefix, key = paystack_parse_ref("pack-mega-2m-tokens-a1b2c3d4")
        assert prefix == "pack"
        assert key == "mega-2m-tokens"

    def test_unrecognized_prefix(self):
        prefix, key = paystack_parse_ref("unknown-foo-bar")
        assert prefix == ""
        assert key is None

    def test_no_prefix(self):
        prefix, key = paystack_parse_ref("a1b2c3d4e5f6")
        assert prefix == ""
        assert key is None

    def test_too_short(self):
        prefix, key = paystack_parse_ref("plan")
        assert prefix == ""
        assert key is None

    def test_two_parts_only(self):
        prefix, key = paystack_parse_ref("plan-pro")
        assert prefix == ""
        assert key is None

    def test_flutterwave_plan_prefix(self):
        prefix, key = flutterwave_parse_ref("plan-pro_v1-a1b2c3d4e5f6")
        assert prefix == "plan"
        assert key == "pro_v1"

    def test_flutterwave_pack_prefix(self):
        prefix, key = flutterwave_parse_ref("pack-starter_50k-a1b2c3d4e5f6")
        assert prefix == "pack"
        assert key == "starter_50k"

    def test_flutterwave_key_with_hyphens(self):
        prefix, key = flutterwave_parse_ref("plan-pro-v1-a1b2c3d4e5f6")
        assert prefix == "plan"
        assert key == "pro-v1"

    def test_flutterwave_unrecognized(self):
        prefix, key = flutterwave_parse_ref("unknown-foo-bar")
        assert prefix == ""
        assert key is None


class TestWebhookSecretResolution:
    """SWX-012: webhook secret must fall back to API key when placeholder is unset."""

    def test_paystack_resolves_real_webhook_secret(self, monkeypatch):
        monkeypatch.setattr(settings, "PAYSTACK_WEBHOOK_SECRET", "sk_real_webhook_secret")
        monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_real_api_key")
        assert paystack_resolve_secret() == "sk_real_webhook_secret"

    def test_paystack_falls_back_to_api_key_when_placeholder(self, monkeypatch):
        monkeypatch.setattr(settings, "PAYSTACK_WEBHOOK_SECRET", "${PAYSTACK_WEBHOOK_SECRET}")
        monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_real_api_key")
        assert paystack_resolve_secret() == "sk_real_api_key"

    def test_paystack_returns_none_when_both_placeholders(self, monkeypatch):
        monkeypatch.setattr(settings, "PAYSTACK_WEBHOOK_SECRET", "${PAYSTACK_WEBHOOK_SECRET}")
        monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "${PAYSTACK_SECRET_KEY}")
        assert paystack_resolve_secret() is None

    def test_paystack_returns_none_when_both_empty(self, monkeypatch):
        monkeypatch.setattr(settings, "PAYSTACK_WEBHOOK_SECRET", "")
        monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "")
        assert paystack_resolve_secret() is None

    def test_flutterwave_resolves_real_webhook_secret(self, monkeypatch):
        monkeypatch.setattr(settings, "FLUTTERWAVE_WEBHOOK_SECRET", "flw_real_webhook_secret")
        monkeypatch.setattr(settings, "FLUTTERWAVE_SECRET_KEY", "flw_real_api_key")
        assert flutterwave_resolve_secret() == "flw_real_webhook_secret"

    def test_flutterwave_falls_back_to_api_key_when_placeholder(self, monkeypatch):
        monkeypatch.setattr(settings, "FLUTTERWAVE_WEBHOOK_SECRET", "${FLUTTERWAVE_WEBHOOK_SECRET}")
        monkeypatch.setattr(settings, "FLUTTERWAVE_SECRET_KEY", "flw_real_api_key")
        assert flutterwave_resolve_secret() == "flw_real_api_key"

    def test_flutterwave_returns_none_when_both_placeholders(self, monkeypatch):
        monkeypatch.setattr(settings, "FLUTTERWAVE_WEBHOOK_SECRET", "${FLUTTERWAVE_WEBHOOK_SECRET}")
        monkeypatch.setattr(settings, "FLUTTERWAVE_SECRET_KEY", "${FLUTTERWAVE_SECRET_KEY}")
        assert flutterwave_resolve_secret() is None