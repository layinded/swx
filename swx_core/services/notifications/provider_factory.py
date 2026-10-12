from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import NOTIFICATION_DEFAULT_RETRY_COUNT, NOTIFICATION_DEFAULT_TIMEOUT
from swx_core.models.email_provider_config import EmailProviderConfig
from swx_core.models.sms_provider_config import SMSProviderConfig
from swx_core.security.encryption import decrypt_value, is_encrypted
from swx_core.services.llm.config_resolver import resolve_config
from swx_core.services.llm.resilience import CircuitBreakerRegistry, call_with_timeout, retry_with_backoff
from swx_core.services.notifications import provider_cache
from swx_core.services.notifications.providers import africas_talking_provider, sendgrid_provider, smtp_provider, twilio_provider

_EMAIL_SENDERS = {"smtp": smtp_provider.send_email, "api": sendgrid_provider.send_email, "sendgrid": sendgrid_provider.send_email, "resend": sendgrid_provider.send_email}
_SMS_SENDERS = {"twilio": twilio_provider.send_sms, "africas_talking": africas_talking_provider.send_sms}

_SECRET_FIELDS_EMAIL = {"password", "api_key"}
_SECRET_FIELDS_SMS = {"auth_token", "api_key"}


def _decrypt_field(value: str | None) -> str | None:
    if not value or not is_encrypted(value):
        return value
    try:
        return decrypt_value(value)
    except Exception:
        return value


def _decrypt_secrets(config: EmailProviderConfig | SMSProviderConfig) -> dict[str, Any]:
    data = config.model_dump()
    secret_fields = _SECRET_FIELDS_EMAIL if isinstance(config, EmailProviderConfig) else _SECRET_FIELDS_SMS
    for field in secret_fields:
        if field in data and data[field] is not None:
            data[field] = _decrypt_field(data[field])
    return {key: value for key, value in data.items() if value is not None}


def _resolved_config(config: EmailProviderConfig | SMSProviderConfig) -> dict[str, Any]:
    decrypted = _decrypt_secrets(config)
    return resolve_config(decrypted)


def _breaker(name: str):
    return CircuitBreakerRegistry.get(name, failure_threshold=5, success_threshold=1, recovery_timeout_seconds=30)


def _retry_values(config: EmailProviderConfig | SMSProviderConfig) -> tuple[int, int]:
    return config.timeout_seconds or NOTIFICATION_DEFAULT_TIMEOUT, config.max_retries or NOTIFICATION_DEFAULT_RETRY_COUNT


async def _send_with_provider(
    sender: Any,
    config: EmailProviderConfig | SMSProviderConfig,
    notification: dict[str, Any],
    breaker,
) -> dict[str, Any]:
    timeout, retries = _retry_values(config)

    async def send_once() -> dict[str, Any]:
        return await call_with_timeout(lambda: sender(_resolved_config(config), notification), timeout, config.name)

    return await retry_with_backoff(send_once, retries, 0.5, 4.0, breaker)


async def get_email_provider(session: AsyncSession) -> tuple[EmailProviderConfig, dict[str, Any]] | None:
    return await get_email_provider_for_country(session)


async def get_email_provider_for_country(session: AsyncSession, country: str | None = None) -> tuple[EmailProviderConfig, dict[str, Any]] | None:
    providers = await provider_cache.get_cached_email_providers(session)
    if not providers:
        return None
    if country:
        country_providers = [provider for provider in providers if not provider.supported_countries or country in provider.supported_countries]
        if country_providers:
            return country_providers[0], _resolved_config(country_providers[0])
    return providers[0], _resolved_config(providers[0])


async def get_sms_provider(session: AsyncSession) -> tuple[SMSProviderConfig, dict[str, Any]] | None:
    providers = await provider_cache.get_cached_sms_providers(session)
    if not providers:
        return None
    return providers[0], _resolved_config(providers[0])


async def send_via_email(session: AsyncSession, notification: dict[str, Any], preferred_provider: str | None = None) -> tuple[EmailProviderConfig, dict[str, Any]]:
    errors: list[str] = []
    providers = await provider_cache.get_cached_email_providers(session)
    if preferred_provider:
        preferred_name = preferred_provider.casefold()
        matched_providers = [provider for provider in providers if provider.name.casefold() == preferred_name or provider.provider_type.casefold() == preferred_name]
        if matched_providers:
            providers = matched_providers
    country = notification.get("country")
    if isinstance(country, str) and country:
        country_providers = [provider for provider in providers if not provider.supported_countries or country in provider.supported_countries]
        if country_providers:
            providers = country_providers
    for provider_config in providers:
        sender = _EMAIL_SENDERS.get(provider_config.provider_type)
        if sender is None:
            errors.append(f"{provider_config.name}: unsupported provider")
            continue
        breaker = _breaker(f"notification:email:{provider_config.name}")
        try:
            result = await _send_with_provider(sender, provider_config, notification, breaker)
            await breaker.record_success()
            return provider_config, result
        except Exception as exc:  # noqa: BLE001
            await breaker.record_failure()
            errors.append(f"{provider_config.name}: {exc}")
    raise RuntimeError("; ".join(errors) or "No email providers configured")


async def send_via_sms(session: AsyncSession, notification: dict[str, Any]) -> tuple[SMSProviderConfig, dict[str, Any]]:
    errors: list[str] = []
    for provider_config in await provider_cache.get_cached_sms_providers(session):
        sender = _SMS_SENDERS.get(provider_config.provider_type)
        if sender is None:
            errors.append(f"{provider_config.name}: unsupported provider")
            continue
        breaker = _breaker(f"notification:sms:{provider_config.name}")
        try:
            result = await _send_with_provider(sender, provider_config, notification, breaker)
            await breaker.record_success()
            return provider_config, result
        except Exception as exc:  # noqa: BLE001
            await breaker.record_failure()
            errors.append(f"{provider_config.name}: {exc}")
    raise RuntimeError("; ".join(errors) or "No sms providers configured")
