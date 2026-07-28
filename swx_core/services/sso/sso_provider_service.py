# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ...events.dispatcher import event_bus
from ...models.sso_provider import SSOProvider, SSOProviderCreate, SSOProviderPublic, SSOProviderUpdate
from ...repositories import sso_repository
from .sso_cache import get_cached_enabled_providers, get_cached_provider, invalidate_provider_cache


def _mask_secret(value: str | None) -> str | None:
    return None if not value else "***"


def _to_public(provider: SSOProvider) -> SSOProviderPublic:
    data = provider.model_dump()
    data["client_secret"] = _mask_secret(provider.client_secret)
    data["certificate"] = _mask_secret(provider.certificate)
    return SSOProviderPublic.model_validate(data)


async def create_provider(session: AsyncSession, body: SSOProviderCreate) -> SSOProviderPublic:
    provider = await sso_repository.create_provider(session, body.model_dump(exclude_unset=True))
    invalidate_provider_cache()
    _ = await event_bus.dispatch("sso.provider_created", payload={"provider_id": str(provider.id), "provider_type": provider.provider_type})
    return _to_public(provider)


async def get_provider(session: AsyncSession, provider_id: UUID, *, enabled_only: bool = False) -> SSOProviderPublic:
    provider = await get_cached_provider(session, provider_id)
    if provider is None or (enabled_only and not provider.enabled):
        raise ValueError("SSO provider not found")
    return _to_public(provider)


async def list_providers(session: AsyncSession, *, enabled_only: bool = False, skip: int = 0, limit: int = 100) -> list[SSOProviderPublic]:
    providers = await get_cached_enabled_providers(session) if enabled_only and skip == 0 else await sso_repository.list_providers(session, enabled=True if enabled_only else None, skip=skip, limit=limit)
    return [_to_public(provider) for provider in providers]


async def update_provider(session: AsyncSession, provider_id: UUID, body: SSOProviderUpdate) -> SSOProviderPublic:
    provider = await sso_repository.update_provider(session, provider_id, body.model_dump(exclude_unset=True))
    if provider is None:
        raise ValueError("SSO provider not found")
    invalidate_provider_cache()
    _ = await event_bus.dispatch("sso.provider_updated", payload={"provider_id": str(provider.id), "provider_type": provider.provider_type})
    return _to_public(provider)


async def delete_provider(session: AsyncSession, provider_id: UUID) -> dict[str, bool]:
    provider = await sso_repository.get_provider_by_id(session, provider_id)
    if provider is None:
        raise ValueError("SSO provider not found")
    deleted = await sso_repository.delete_provider(session, provider_id)
    invalidate_provider_cache()
    _ = await event_bus.dispatch("sso.provider_deleted", payload={"provider_id": str(provider_id), "provider_type": provider.provider_type})
    return {"success": deleted}
