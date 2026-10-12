import logging
from typing import Protocol, cast

from fastapi import HTTPException
from typing_extensions import override

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

from swx_core.services.billing.providers import LocalPaymentProvider


logger = logging.getLogger(__name__)


class _ResponseLike(Protocol):
    def raise_for_status(self) -> None:
        ...

    def json(self) -> dict[str, object]:
        ...


class FlutterwaveProvider(LocalPaymentProvider):
    def __init__(self, secret_key: str, public_key: str, encryption_key: str, base_url: str = "https://api.flutterwave.com/v3"):
        self.secret_key: str = secret_key
        self.public_key: str = public_key
        self.encryption_key: str = encryption_key
        self.base_url: str = base_url.rstrip("/")

    async def _request(self, method: str, path: str, json: dict[str, object] | None = None) -> dict[str, object]:
        if httpx is None:
            raise RuntimeError("httpx is required for Flutterwave provider")
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
                response = cast(
                    _ResponseLike,
                    cast(
                        object,
                        await client.request(
                            method,
                            path,
                            json=json,
                            headers={
                                "Authorization": f"Bearer {self.secret_key}",
                                "Content-Type": "application/json",
                            },
                        ),
                    ),
                )
                response.raise_for_status()
                response_data = response.json()
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.exception("Flutterwave request failed for %s %s", method, path)
            raise HTTPException(status_code=503, detail="Flutterwave service unavailable") from exc
        return cast(dict[str, object], response_data.get("data", response_data))

    @override
    async def initialize_payment(self, amount: int, currency: str, email: str, reference: str, callback_url: str, **kwargs: object) -> dict[str, object]:
        request_payload = {
            "tx_ref": reference,
            "amount": amount,
            "currency": currency.upper(),
            "redirect_url": callback_url,
            "customer": {"email": email},
            "meta": kwargs.get("metadata", {}),
        }
        data = await self._request("POST", "/payments", request_payload)
        return {"provider": "flutterwave", "reference": reference, "link": data.get("link"), "id": data.get("id"), "raw": data}

    @override
    async def verify_payment(self, reference: str) -> dict[str, object]:
        data = await self._request("GET", f"/transactions/{reference}/verify")
        return {"provider": "flutterwave", "reference": reference, "status": data.get("status"), "paid": data.get("status") == "successful", "raw": data}

    @override
    async def refund(self, reference: str, amount: int | None = None) -> dict[str, object]:
        payload: dict[str, object] = {"id": reference}
        if amount is not None:
            payload["amount"] = amount
        data = await self._request("POST", "/refunds", payload)
        return {"provider": "flutterwave", "reference": reference, "status": data.get("status"), "raw": data}
