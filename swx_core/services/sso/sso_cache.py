# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ...models.sso_provider import SSOProvider
from ...repositories import sso_repository

_TTL_SECONDS = 300
_provider_cache: dict[str, tuple[SSOProvider | list[SSOProvider] | None, float]] = {}


def _is_fresh(cached_at: float) -> bool:
    return time.monotonic() - cached_at < _TTL_SECONDS


def invalidate_provider_cache() -> None:
    _provider_cache.clear()


async def get_cached_provider(session: AsyncSession, provider_id: UUID) -> SSOProvider | None:
    cache_key = f"provider:{provider_id}"
    cached = _provider_cache.get(cache_key)
    if cached is not None and _is_fresh(cached[1]):
        return cached[0] if isinstance(cached[0], SSOProvider) or cached[0] is None else None
    provider = await sso_repository.get_provider_by_id(session, provider_id)
    _provider_cache[cache_key] = (provider, time.monotonic())
    return provider


async def get_cached_provider_by_domain(session: AsyncSession, domain: str) -> SSOProvider | None:
    cache_key = f"domain:{domain.lower()}"
    cached = _provider_cache.get(cache_key)
    if cached is not None and _is_fresh(cached[1]):
        return cached[0] if isinstance(cached[0], SSOProvider) or cached[0] is None else None
    provider = await sso_repository.get_provider_by_domain(session, domain)
    _provider_cache[cache_key] = (provider, time.monotonic())
    return provider


async def get_cached_enabled_providers(session: AsyncSession) -> list[SSOProvider]:
    cache_key = "providers:enabled"
    cached = _provider_cache.get(cache_key)
    if cached is not None and _is_fresh(cached[1]) and isinstance(cached[0], list):
        return cached[0]
    providers = await sso_repository.list_providers(session, enabled=True)
    _provider_cache[cache_key] = (providers, time.monotonic())
    return providers
