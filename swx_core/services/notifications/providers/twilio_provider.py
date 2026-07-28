from typing import Any

import httpx


async def send_sms(config: dict[str, Any], notification: dict[str, Any]) -> dict[str, Any]:
    account_sid = str(config["account_sid"])
    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    payload = {"To": notification["to"], "From": config.get("from_number"), "Body": notification["body"]}
    async with httpx.AsyncClient(timeout=float(config.get("timeout_seconds") or 30), auth=(account_sid, str(config["auth_token"]))) as client:
        response = await client.post(endpoint, data=payload)
    response.raise_for_status()
    return response.json()
