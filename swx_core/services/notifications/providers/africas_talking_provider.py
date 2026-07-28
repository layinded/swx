from typing import Any

import httpx


async def send_sms(config: dict[str, Any], notification: dict[str, Any]) -> dict[str, Any]:
    payload = {"username": config.get("username") or "sandbox", "to": notification["to"], "message": notification["body"]}
    sender_number = config.get("from_number")
    if sender_number:
        payload["from"] = sender_number
    headers = {"apiKey": str(config["api_key"]), "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=float(config.get("timeout_seconds") or 30)) as client:
        response = await client.post("https://api.africastalking.com/version1/messaging", data=payload, headers=headers)
    response.raise_for_status()
    return response.json()
