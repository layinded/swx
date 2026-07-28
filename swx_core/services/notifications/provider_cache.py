import time

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import NOTIFICATION_PROVIDER_CACHE_TTL
from swx_core.models.email_provider_config import EmailProviderConfig
from swx_core.models.sms_provider_config import SMSProviderConfig
from swx_core.repositories import notification_repository

_email_cache: tuple[list[EmailProviderConfig], float] | None = None
_sms_cache: tuple[list[SMSProviderConfig], float] | None = None


def invalidate_provider_cache() -> None:
    global _email_cache, _sms_cache
    _email_cache = None
    _sms_cache = None


async def get_cached_email_providers(session: AsyncSession) -> list[EmailProviderConfig]:
    global _email_cache
    cache = _email_cache
    if cache is not None and time.monotonic() - cache[1] < NOTIFICATION_PROVIDER_CACHE_TTL:
        return cache[0]
    providers = await notification_repository.get_active_email_providers(session)
    _email_cache = (providers, time.monotonic())
    return providers


async def get_cached_sms_providers(session: AsyncSession) -> list[SMSProviderConfig]:
    global _sms_cache
    cache = _sms_cache
    if cache is not None and time.monotonic() - cache[1] < NOTIFICATION_PROVIDER_CACHE_TTL:
        return cache[0]
    providers = await notification_repository.get_active_sms_providers(session)
    _sms_cache = (providers, time.monotonic())
    return providers
