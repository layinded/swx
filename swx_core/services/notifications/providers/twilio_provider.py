import logging
from typing import Any

import httpx


logger = logging.getLogger(__name__)


async def send_sms(config: dict[str, Any], notification: dict[str, Any]) -> dict[str, Any]:
    account_sid = str(config["account_sid"])
    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    payload = {"To": notification["to"], "From": config.get("from_number"), "Body": notification["body"]}
    try:
        timeout_seconds = float(config.get("timeout_seconds") or 30)
        async with httpx.AsyncClient(timeout=timeout_seconds, auth=(account_sid, str(config["auth_token"]))) as client:
            response = await client.post(endpoint, data=payload)
        response.raise_for_status()
        return response.json()
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.exception("Twilio SMS send failed for recipient %s", notification.get("to"))
        return {"provider": "twilio", "accepted": False, "error": str(exc)}
