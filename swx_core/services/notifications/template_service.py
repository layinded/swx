import time
from typing import Any

from jinja2 import Template
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import NOTIFICATION_TEMPLATE_CACHE_TTL
from swx_core.models.notification_template import NotificationTemplate
from swx_core.repositories import notification_repository

_CACHE: dict[str, tuple[NotificationTemplate | None, float]] = {}


def invalidate_template_cache() -> None:
    _CACHE.clear()


async def get_template(session: AsyncSession, key: str) -> NotificationTemplate | None:
    now = time.monotonic()
    cached_entry = _CACHE.get(key)
    if cached_entry is not None and now - cached_entry[1] < NOTIFICATION_TEMPLATE_CACHE_TTL:
        return cached_entry[0]
    template = await notification_repository.get_template_by_key(session, key)
    _CACHE[key] = (template, now)
    return template


async def render_template(session: AsyncSession, key: str, context: dict[str, Any]) -> dict[str, str | None]:
    template = await get_template(session, key)
    if template is None or not template.is_active:
        raise ValueError(f"Notification template '{key}' not found")
    subject = Template(template.subject_template or "").render(context) or None
    body = Template(template.body_template).render(context)
    return {"channel": template.channel, "subject": subject, "body": body}
