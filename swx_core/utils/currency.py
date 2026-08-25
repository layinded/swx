"""Currency-aware conversion between major units, provider minor units, and nano.

SwX stores all wallet balances in **nano** — the smallest integer subunit of a
currency.  Different payment providers report amounts in different units:

    Paystack    → kobo   (1 NGN = 100 kobo)
    Flutterwave → major  (1 NGN = 1 NGN)
    Stripe      → cents  (1 USD = 100 cents)

This module provides the single source of truth for those conversions so
that no caller hand-rolls the arithmetic.

Conversions are pure functions with no I/O and no side effects.
"""

from __future__ import annotations

# 1 major unit of currency = NANO_DIVISORS[currency] nano.
# NGN uses 10,000,000 because the platform's nano granularity is finer than
# the kobo (100) — the extra factor of 100,000 lets us represent fractional
# kobo for metered billing.
NANO_DIVISORS: dict[str, int] = {
    "NGN": 10_000_000,
    "KES": 100,
    "ZAR": 100,
    "USD": 100,
    "GHS": 100,
}

# Providers that report amounts in the currency's minor unit (e.g. kobo for
# NGN, cents for USD).  Providers not listed here report in major units.
_PROVIDER_MINOR_UNIT: dict[str, set[str]] = {
    "paystack": {"NGN"},  # Paystack sends NGN amounts in kobo
    "stripe": {"USD", "EUR", "GBP"},  # Stripe sends amounts in cents
}


def _normalise_currency(currency: str) -> str:
    """Return the uppercase ISO-4217 currency code."""
    return currency.strip().upper()


def major_to_nano(amount: float, currency: str) -> int:
    """Convert major currency units to nano (integer).

    Args:
        amount: Amount in major units (e.g. 1.0 for one NGN).
        currency: ISO-4217 currency code (case-insensitive).

    Returns:
        The equivalent amount in nano.

    Raises:
        ValueError: If the currency is not in :data:`NANO_DIVISORS`.
    """
    code = _normalise_currency(currency)
    divisor = NANO_DIVISORS.get(code)
    if divisor is None:
        raise ValueError(f"Unsupported currency: {code!r}. Known: {sorted(NANO_DIVISORS)}")
    return round(amount * divisor)


def nano_to_major(amount_nano: int, currency: str) -> float:
    """Convert nano back to major currency units.

    Args:
        amount_nano: Amount in nano.
        currency: ISO-4217 currency code (case-insensitive).

    Returns:
        The equivalent amount in major units.

    Raises:
        ValueError: If the currency is not in :data:`NANO_DIVISORS`.
    """
    code = _normalise_currency(currency)
    divisor = NANO_DIVISORS.get(code)
    if divisor is None:
        raise ValueError(f"Unsupported currency: {code!r}. Known: {sorted(NANO_DIVISORS)}")
    return amount_nano / divisor


def kobo_to_nano(kobo: int) -> int:
    """Convert Paystack kobo (NGN minor unit) to nano.

    1 NGN = 100 kobo = 10,000,000 nano, so 1 kobo = 100,000 nano.

    Args:
        kobo: Amount in kobo as reported by Paystack.

    Returns:
        The equivalent amount in nano.
    """
    return kobo * (NANO_DIVISORS["NGN"] // 100)


def provider_amount_to_nano(amount: int, currency: str, provider: str) -> int:
    """Convert a provider-reported amount to nano.

    Some providers report in the currency's minor unit (kobo, cents) while
    others report in major units.  This function dispatches based on the
    provider + currency pair.

    Args:
        amount: The amount as reported by the provider.
        currency: ISO-4217 currency code (case-insensitive).
        provider: Provider name (``"paystack"``, ``"flutterwave"``,
            ``"stripe"``).  Case-insensitive.

    Returns:
        The equivalent amount in nano.

    Raises:
        ValueError: If the currency is unsupported.
    """
    code = _normalise_currency(currency)
    provider_key = provider.strip().lower()

    minor_currencies = _PROVIDER_MINOR_UNIT.get(provider_key, set())
    if code in minor_currencies:
        divisor = NANO_DIVISORS[code]
        minor_per_major = 100  # all supported minor-unit currencies are 1/100
        nano_per_minor = divisor // minor_per_major
        return amount * nano_per_minor

    return major_to_nano(amount, code)


def major_to_provider_amount(amount: float, currency: str, provider: str) -> int:
    """Convert major currency units to the amount unit a provider expects.

    Paystack expects kobo (NGN minor), Stripe expects cents (USD minor),
    Flutterwave expects major units.  This function dispatches based on the
    provider + currency pair so callers never hand-roll the factor.

    Args:
        amount: Amount in major units (e.g. 1000.0 for one thousand NGN).
        currency: ISO-4217 currency code (case-insensitive).
        provider: Provider name (``"paystack"``, ``"flutterwave"``,
            ``"stripe"``).  Case-insensitive.

    Returns:
        The amount in the provider's expected unit (kobo, cents, or major).

    Raises:
        ValueError: If the currency is unsupported.
    """
    code = _normalise_currency(currency)
    if code not in NANO_DIVISORS:
        raise ValueError(f"Unsupported currency: {code!r}. Known: {sorted(NANO_DIVISORS)}")

    provider_key = provider.strip().lower()
    minor_currencies = _PROVIDER_MINOR_UNIT.get(provider_key, set())
    if code in minor_currencies:
        return round(amount * 100)
    return round(amount)


__all__ = [
    "NANO_DIVISORS",
    "kobo_to_nano",
    "major_to_nano",
    "major_to_provider_amount",
    "nano_to_major",
    "provider_amount_to_nano",
]
