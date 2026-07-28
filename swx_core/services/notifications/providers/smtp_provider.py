from email.message import EmailMessage
from typing import Any


async def send_email(config: dict[str, Any], notification: dict[str, Any]) -> dict[str, Any]:
    try:
        import aiosmtplib  # pyright: ignore[reportMissingImports]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("aiosmtplib is required for SMTP notifications") from exc
    message = EmailMessage()
    from_name = config.get("from_name")
    message["From"] = f"{from_name} <{config['from_email']}>" if from_name else str(config["from_email"])
    message["To"] = str(notification["to"])
    if notification.get("subject"):
        message["Subject"] = str(notification["subject"])
    message.set_content(str(notification["body"]))
    await aiosmtplib.send(
        message,
        hostname=str(config["host"]),
        port=int(config.get("port") or 465),
        username=str(config.get("username") or "") or None,
        password=str(config.get("password") or "") or None,
        use_tls=bool(config.get("is_ssl", True)),
        timeout=float(config.get("timeout_seconds") or 30),
    )
    return {"provider": "smtp", "accepted": True}
