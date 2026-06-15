from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class CheckoutResult:
    url: str
    order_id: str
    provider: str

class PaymentProvider(ABC):
    @abstractmethod
    async def create_checkout(self, product_id, variant_id, custom_data) -> CheckoutResult: ...
    @abstractmethod
    async def verify_webhook(self, payload, signature) -> dict: ...
    @abstractmethod
    async def get_order(self, order_id) -> dict: ...