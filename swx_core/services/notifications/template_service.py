import os
import time
from typing import Any

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, Template
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import NOTIFICATION_TEMPLATE_CACHE_TTL, settings
from swx_core.models.notification_template import NotificationTemplate
from swx_core.repositories import notification_repository

_CACHE: dict[str, tuple[NotificationTemplate | None, float]] = {}


def invalidate_template_cache() -> None:
    _CACHE.clear()


def _get_env(base_template_path: str | None = None) -> Environment:
    template_dir = settings.NOTIFICATION_TEMPLATE_DIR or os.getenv("NOTIFICATION_TEMPLATE_DIR", "templates")
    loaders: list[FileSystemLoader | DictLoader] = []
    if os.path.isdir(template_dir):
        loaders.append(FileSystemLoader(template_dir))
    if base_template_path:
        loaders.append(DictLoader({}))
    if not loaders:
        loaders.append(DictLoader({}))
    loader = ChoiceLoader(loaders) if len(loaders) > 1 else loaders[0]
    return Environment(loader=loader, autoescape=True)


def _enrich_variables(context: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "brand_name": getattr(settings, "NOTIFICATION_DEFAULT_FROM_NAME", getattr(settings, "PROJECT_NAME", "App")),
        "brand_color": getattr(settings, "NOTIFICATION_BRAND_COLOR", "#3c42b6"),
        "support_email": getattr(settings, "NOTIFICATION_SUPPORT_EMAIL", "support@example.com"),
        "frontend_url": getattr(settings, "FRONTEND_HOST", "http://localhost:3000"),
    }
    defaults.update(context)
    return defaults


async def get_template(session: AsyncSession, key: str) -> NotificationTemplate | None:
    now = time.monotonic()
    cached_entry = _CACHE.get(key)
    if cached_entry is not None and now - cached_entry[1] < NOTIFICATION_TEMPLATE_CACHE_TTL:
        return cached_entry[0]
    template = await notification_repository.get_template_by_key(session, key)
    _CACHE[key] = (template, now)
    return template


async def render_template(session: AsyncSession, key: str, context: dict[str, Any], base_template_path: str | None = None) -> dict[str, str | None]:
    template = await get_template(session, key)
    if template is None or not template.is_active:
        raise ValueError(f"Notification template '{key}' not found")
    context = _enrich_variables(context)
    if base_template_path:
        env = _get_env(base_template_path)
        subject = env.from_string(template.subject_template or "").render(context) or None
        body = env.from_string(f'{{% extends "{base_template_path}" %}}{{% block content %}}{template.body_template}{{% endblock %}}').render(context)
        return {"channel": template.channel, "subject": subject, "body": body}
    subject = Template(template.subject_template or "").render(context) or None
    body = Template(template.body_template).render(context)
    return {"channel": template.channel, "subject": subject, "body": body}
