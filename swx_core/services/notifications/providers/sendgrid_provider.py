from typing import Any

import httpx


async def send_email(config: dict[str, Any], notification: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "personalizations": [{"to": [{"email": notification["to"]}]}],
        "from": {"email": config["from_email"], "name": config.get("from_name")},
        "subject": notification.get("subject") or "",
        "content": [{"type": "text/plain", "value": notification["body"]}],
    }
    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=float(config.get("timeout_seconds") or 30)) as client:
        response = await client.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers)
    response.raise_for_status()
    return {"provider": "sendgrid", "status_code": response.status_code}
