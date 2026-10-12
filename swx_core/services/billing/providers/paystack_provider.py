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


class PaystackProvider(LocalPaymentProvider):
    def __init__(self, secret_key: str, public_key: str, base_url: str = "https://api.paystack.co"):
        self.secret_key: str = secret_key
        self.public_key: str = public_key
        self.base_url: str = base_url.rstrip("/")

    async def _request(self, method: str, path: str, json: dict[str, object] | None = None) -> dict[str, object]:
        if httpx is None:
            raise RuntimeError("httpx is required for Paystack provider")
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
            logger.exception("Paystack request failed for %s %s", method, path)
            raise HTTPException(status_code=503, detail="Paystack service unavailable") from exc
        return cast(dict[str, object], response_data.get("data", response_data))

    @override
    async def initialize_payment(self, amount: int, currency: str, email: str, reference: str, callback_url: str, **kwargs: object) -> dict[str, object]:
        request_payload = {
            "amount": amount,
            "currency": currency.upper(),
            "email": email,
            "reference": reference,
            "callback_url": callback_url,
            "metadata": kwargs.get("metadata", {}),
        }
        data = await self._request("POST", "/transaction/initialize", request_payload)
        return {"provider": "paystack", "reference": reference, "authorization_url": data.get("authorization_url"), "access_code": data.get("access_code"), "raw": data}

    @override
    async def verify_payment(self, reference: str) -> dict[str, object]:
        data = await self._request("GET", f"/transaction/verify/{reference}")
        return {"provider": "paystack", "reference": reference, "status": data.get("status"), "paid": data.get("status") == "success", "raw": data}

    @override
    async def refund(self, reference: str, amount: int | None = None) -> dict[str, object]:
        request_payload: dict[str, object] = {"transaction": reference}
        if amount is not None:
            request_payload["amount"] = amount
        data = await self._request("POST", "/refund", request_payload)
        return {"provider": "paystack", "reference": reference, "status": data.get("status"), "raw": data}
