import logging
from typing import Any

import httpx


logger = logging.getLogger(__name__)


async def send_sms(config: dict[str, Any], notification: dict[str, Any]) -> dict[str, Any]:
    payload = {"username": config.get("username") or "sandbox", "to": notification["to"], "message": notification["body"]}
    sender_number = config.get("from_number")
    if sender_number:
        payload["from"] = sender_number
    headers = {"apiKey": str(config["api_key"]), "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    try:
        timeout_seconds = float(config.get("timeout_seconds") or 30)
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post("https://api.africastalking.com/version1/messaging", data=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.exception("Africa's Talking SMS send failed for recipient %s", notification.get("to"))
        return {"provider": "africas_talking", "accepted": False, "error": str(exc)}
