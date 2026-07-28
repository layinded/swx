import logging
from typing import Any

import httpx


logger = logging.getLogger(__name__)


async def send_email(config: dict[str, Any], notification: dict[str, Any]) -> dict[str, Any]:
    sender_name = config.get("from_name")
    payload = {
        "personalizations": [{"to": [{"email": notification["to"]}]}],
        "from": {"email": config["from_email"], "name": sender_name},
        "subject": notification.get("subject") or "",
        "content": [{"type": "text/plain", "value": notification["body"]}],
    }
    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
    try:
        timeout_seconds = float(config.get("timeout_seconds") or 30)
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers)
        response.raise_for_status()
        return {"provider": "sendgrid", "status_code": response.status_code}
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.exception("SendGrid email send failed for recipient %s", notification.get("to"))
        return {"provider": "sendgrid", "status_code": None, "accepted": False, "error": str(exc)}
