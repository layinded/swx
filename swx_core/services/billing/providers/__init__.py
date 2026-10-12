from abc import ABC, abstractmethod

from swx_core.services.billing.billing_provider_base import BillingProvider


class LocalPaymentProvider(ABC):
    """Abstract base for local/African payment providers."""

    @abstractmethod
    async def initialize_payment(self, amount: int, currency: str, email: str, reference: str, callback_url: str, **kwargs: object) -> dict[str, object]:
        ...

    @abstractmethod
    async def verify_payment(self, reference: str) -> dict[str, object]:
        ...

    @abstractmethod
    async def refund(self, reference: str, amount: int | None = None) -> dict[str, object]:
        ...


__all__ = ["BillingProvider", "LocalPaymentProvider"]
