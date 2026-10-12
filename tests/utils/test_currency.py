"""Unit tests for the currency conversion utility (swx_core.utils.currency)."""

import pytest

from swx_core.utils.currency import (
    NANO_DIVISORS,
    kobo_to_nano,
    major_to_nano,
    major_to_provider_amount,
    nano_to_major,
    provider_amount_to_nano,
)


class TestMajorToNano:
    def test_ngn_conversion(self):
        assert major_to_nano(1.0, "NGN") == 10_000_000

    def test_usd_conversion(self):
        assert major_to_nano(1.0, "USD") == 100

    def test_kes_conversion(self):
        assert major_to_nano(1.0, "KES") == 100

    def test_case_insensitive(self):
        assert major_to_nano(1.0, "ngn") == 10_000_000
        assert major_to_nano(1.0, "Usd") == 100

    def test_large_amount(self):
        assert major_to_nano(1000.0, "NGN") == 10_000_000_000

    def test_zero_amount(self):
        assert major_to_nano(0.0, "NGN") == 0

    def test_unsupported_currency_raises(self):
        with pytest.raises(ValueError, match="Unsupported currency"):
            major_to_nano(1.0, "EUR")

    def test_rounding(self):
        assert major_to_nano(1.5, "USD") == 150


class TestNanoToMajor:
    def test_ngn_conversion(self):
        assert nano_to_major(10_000_000, "NGN") == 1.0

    def test_usd_conversion(self):
        assert nano_to_major(100, "USD") == 1.0

    def test_case_insensitive(self):
        assert nano_to_major(10_000_000, "ngn") == 1.0

    def test_unsupported_currency_raises(self):
        with pytest.raises(ValueError, match="Unsupported currency"):
            nano_to_major(100, "EUR")


class TestKoboToNano:
    def test_one_kobo(self):
        assert kobo_to_nano(1) == 100_000

    def test_one_ngn_in_kobo(self):
        assert kobo_to_nano(100) == 10_000_000

    def test_zero(self):
        assert kobo_to_nano(0) == 0

    def test_large_amount(self):
        assert kobo_to_nano(100_000) == 10_000_000_000


class TestProviderAmountToNano:
    def test_paystack_ngn_kobo(self):
        assert provider_amount_to_nano(100_000, "NGN", "paystack") == 10_000_000_000

    def test_flutterwave_ngn_major(self):
        assert provider_amount_to_nano(1000, "NGN", "flutterwave") == 10_000_000_000

    def test_stripe_usd_cents(self):
        assert provider_amount_to_nano(100, "USD", "stripe") == 100

    def test_case_insensitive_provider(self):
        assert provider_amount_to_nano(100_000, "NGN", "Paystack") == 10_000_000_000

    def test_unknown_provider_defaults_to_major(self):
        assert provider_amount_to_nano(1000, "NGN", "unknown") == 10_000_000_000


class TestMajorToProviderAmount:
    def test_paystack_ngn_to_kobo(self):
        assert major_to_provider_amount(1000, "NGN", "paystack") == 100_000

    def test_flutterwave_ngn_stays_major(self):
        assert major_to_provider_amount(1000, "NGN", "flutterwave") == 1000

    def test_stripe_usd_to_cents(self):
        assert major_to_provider_amount(10, "USD", "stripe") == 1000

    def test_case_insensitive(self):
        assert major_to_provider_amount(1000, "ngn", "Paystack") == 100_000

    def test_unsupported_currency_raises(self):
        with pytest.raises(ValueError, match="Unsupported currency"):
            major_to_provider_amount(1000, "EUR", "paystack")

    def test_rounding(self):
        assert major_to_provider_amount(1.5, "USD", "stripe") == 150


class TestNanoDivisors:
    def test_all_supported_currencies_present(self):
        expected = {"NGN", "KES", "ZAR", "USD", "GHS"}
        assert expected.issubset(set(NANO_DIVISORS.keys()))

    def test_ngn_has_highest_divisor(self):
        assert NANO_DIVISORS["NGN"] == 10_000_000

    def test_all_divisors_positive(self):
        for currency, divisor in NANO_DIVISORS.items():
            assert divisor > 0, f"{currency} has non-positive divisor"