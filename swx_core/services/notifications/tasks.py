from collections.abc import Callable
import importlib
from uuid import UUID

import anyio

from swx_core.database.db import AsyncSessionLocal
from swx_core.services.notifications.notification_service import deliver_notification_by_id


async def _deliver_notification(notification_id: str) -> None:
    async with AsyncSessionLocal() as session:
        _ = await deliver_notification_by_id(session, UUID(notification_id))


def _send_notification_task(notification_id: str) -> None:
    anyio.run(_deliver_notification, notification_id)


def _resolve_task() -> Callable[[str], None]:
    try:
        celery_module = importlib.import_module("celery")
    except ImportError:
        return _send_notification_task
    shared_task = getattr(celery_module, "shared_task")
    return shared_task(name="swx_core.services.notifications.tasks.send_notification_task")(_send_notification_task)


send_notification_task = _resolve_task()
