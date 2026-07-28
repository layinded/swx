from abc import ABC, abstractmethod
from typing import Any


class NotificationProvider(ABC):
    @abstractmethod
    async def send(self, config: dict[str, Any], notification: dict[str, Any]) -> bool:
        pass

    @abstractmethod
    async def health_check(self, config: dict[str, Any]) -> bool:
        pass
