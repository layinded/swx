from base64 import b64encode
from datetime import datetime, timezone
from collections.abc import Mapping
from typing import cast
from typing import Protocol

from typing_extensions import override

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

from swx_core.services.billing.providers import LocalPaymentProvider


class _ResponseLike(Protocol):
    def raise_for_status(self) -> None:
        ...

    def json(self) -> dict[str, object]:
        ...


class MpesaProvider(LocalPaymentProvider):
    def __init__(self, consumer_key: str, consumer_secret: str, passkey: str, shortcode: str, env: str = "sandbox"):
        self.consumer_key: str = consumer_key
        self.consumer_secret: str = consumer_secret
        self.passkey: str = passkey
        self.shortcode: str = shortcode
        self.base_url: str = "https://sandbox.safaricom.co.ke" if env == "sandbox" else "https://api.safaricom.co.ke"

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y%m%d%H%M%S")

    async def _token(self) -> str:
        if httpx is None:
            raise RuntimeError("httpx is required for M-Pesa provider")
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0, auth=(self.consumer_key, self.consumer_secret)) as client:
            response = cast(_ResponseLike, cast(object, await client.get("/oauth/v1/generate?grant_type=client_credentials")))
            response.raise_for_status()
            payload = response.json()
            return str(payload.get("access_token", ""))

    def _password(self, timestamp: str) -> str:
        raw = f"{self.shortcode}{self.passkey}{timestamp}".encode()
        return b64encode(raw).decode()

    async def _request(self, path: str, payload: Mapping[str, object]) -> dict[str, object]:
        if httpx is None:
            raise RuntimeError("httpx is required for M-Pesa provider")
        token = await self._token()
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            response = cast(_ResponseLike, cast(object, await client.post(path, json=payload, headers={"Authorization": f"Bearer {token}"})))
            response.raise_for_status()
            return response.json()

    @override
    async def initialize_payment(self, amount: int, currency: str, email: str, reference: str, callback_url: str, **kwargs: object) -> dict[str, object]:
        timestamp = self._timestamp()
        payload = {"BusinessShortCode": self.shortcode, "Password": self._password(timestamp), "Timestamp": timestamp, "TransactionType": "CustomerPayBillOnline", "Amount": amount, "PartyA": kwargs.get("phone_number"), "PartyB": self.shortcode, "PhoneNumber": kwargs.get("phone_number"), "CallBackURL": callback_url, "AccountReference": reference, "TransactionDesc": kwargs.get("description", email), "Currency": currency.upper()}
        data = await self._request("/mpesa/stkpush/v1/processrequest", payload)
        return {"provider": "mpesa", "reference": reference, "checkout_request_id": data.get("CheckoutRequestID"), "merchant_request_id": data.get("MerchantRequestID"), "raw": data}

    @override
    async def verify_payment(self, reference: str) -> dict[str, object]:
        timestamp = self._timestamp()
        payload = {"BusinessShortCode": self.shortcode, "Password": self._password(timestamp), "Timestamp": timestamp, "CheckoutRequestID": reference}
        data = await self._request("/mpesa/stkpushquery/v1/query", payload)
        return {"provider": "mpesa", "reference": reference, "status": data.get("ResultDesc"), "paid": str(data.get("ResultCode")) == "0", "raw": data}

    @override
    async def refund(self, reference: str, amount: int | None = None) -> dict[str, object]:
        raise NotImplementedError("M-Pesa refund is not supported in this implementation")
