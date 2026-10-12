# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from swx_core.models.email_provider_config import EmailProviderConfigCreate
from swx_core.models.notification_template import NotificationTemplateCreate
from swx_core.services.notifications import management_service, template_service


def config_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    data = {
        "id": uuid.uuid4(),
        "name": "sendgrid-primary",
        "provider_type": "sendgrid",
        "host": None,
        "port": None,
        "username": None,
        "password": "${SENDGRID_PASSWORD}",
        "api_key": "${SENDGRID_API_KEY}",
        "from_email": "noreply@example.com",
        "from_name": "SwX",
        "is_ssl": True,
        "is_active": True,
        "priority": 0,
        "max_retries": 3,
        "timeout_seconds": 30,
        "extra_config": {},
        "created_at": now,
        "updated_at": now,
    }
    data.update(cast(dict[str, Any], overrides))
    return SimpleNamespace(**data, model_dump=lambda: data)


class TestNotificationServices:
    async def test_upsert_email_provider_invalidates_cache_and_emits_event(self):
        session = AsyncMock()
        payload = EmailProviderConfigCreate(name="sendgrid-primary", provider_type="sendgrid", from_email="noreply@example.com", api_key="${SENDGRID_API_KEY}")
        stored = config_object()
        with patch.object(management_service.notification_repository, "upsert_email_provider_config", new_callable=AsyncMock, return_value=stored):
            with patch.object(management_service, "invalidate_provider_cache") as mock_invalidate:
                with patch.object(management_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await management_service.upsert_email_provider(session, payload)
        assert result.name == "sendgrid-primary"
        assert result.api_key is not None
        assert result.api_key.startswith("${SE")
        assert result.api_key.endswith("KEY}")
        mock_invalidate.assert_called_once()
        assert mock_dispatch.await_args is not None
        assert mock_dispatch.await_args.args[0] == "notification.email_provider.upserted"

    async def test_upsert_template_emits_event_and_clears_cache(self):
        session = AsyncMock()
        payload = NotificationTemplateCreate(key="email.verification", channel="email", subject_template="Hello {{ name }}", body_template="Code {{ code }}")
        stored = SimpleNamespace(id=uuid.uuid4(), key=payload.key, channel=payload.channel, subject_template=payload.subject_template, body_template=payload.body_template, is_active=True, created_at=datetime.now(timezone.utc).replace(tzinfo=None), updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        with patch.object(management_service.notification_repository, "upsert_notification_template", new_callable=AsyncMock, return_value=stored):
            with patch.object(management_service, "invalidate_template_cache") as mock_invalidate:
                with patch.object(management_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await management_service.upsert_template(session, payload)
        assert result.key == "email.verification"
        mock_invalidate.assert_called_once()
        assert mock_dispatch.await_args is not None
        assert mock_dispatch.await_args.args[0] == "notification.template.upserted"

    async def test_render_template_uses_repository_template(self):
        session = AsyncMock()
        stored = SimpleNamespace(key="email.verification", channel="email", subject_template="Hello {{ name }}", body_template="Code {{ code }}", is_active=True)
        template_service.invalidate_template_cache()
        with patch.object(template_service.notification_repository, "get_template_by_key", new_callable=AsyncMock, return_value=stored) as mock_get:
            rendered = await template_service.render_template(session, "email.verification", {"name": "Ada", "code": "123456"})
            rendered_cached = await template_service.render_template(session, "email.verification", {"name": "Ada", "code": "123456"})
        assert rendered["subject"] == "Hello Ada"
        assert rendered["body"] == "Code 123456"
        assert rendered_cached == rendered
        assert mock_get.await_count == 1
