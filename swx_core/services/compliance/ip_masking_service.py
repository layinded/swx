from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import COMPLIANCE_DEFAULT_IP_MASKING
from swx_core.services.compliance.config_cache import get_cached_configs, resolve_config_value


async def get_masking_config(session: AsyncSession) -> str:
    for config in await get_cached_configs(session, category="masking"):
        if config.key == "ip_masking_mode":
            value = resolve_config_value(config.value)
            if isinstance(value, str):
                return value
    return COMPLIANCE_DEFAULT_IP_MASKING


def _mask_ipv6_address(ip_address: str) -> str:
    parts = ip_address.split(":")
    return ":".join(parts[:2] + ["*", "*", "*", "*"][: max(0, len(parts) - 2)])


async def mask_ip(session: AsyncSession, ip_address: str | None) -> str | None:
    if ip_address is None:
        return None
    masking_mode = (await get_masking_config(session)).lower()
    if masking_mode == "none":
        return ip_address
    if masking_mode == "full":
        return "0.0.0.0"
    if ":" in ip_address:
        return _mask_ipv6_address(ip_address)
    octets = ip_address.split(".")
    return ".".join(octets[:2] + ["*", "*"]) if len(octets) == 4 else ip_address
