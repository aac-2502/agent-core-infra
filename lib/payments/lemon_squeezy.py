"""
LemonSqueezy client — agent-core-infra
Checkout link generation, webhook verification, subscription management.
"""
import hashlib
import hmac
import json
import os
import httpx

LEMON_API_KEY  = os.getenv("LEMON_SQUEEZY_API_KEY", "")
LEMON_STORE_ID = os.getenv("LEMON_STORE_ID", "")
WEBHOOK_SECRET = os.getenv("LEMON_WEBHOOK_SECRET", "")
BASE_URL       = "https://api.lemonsqueezy.com/v1"

HEADERS = {
    "Authorization": f"Bearer {LEMON_API_KEY}",
    "Accept": "application/vnd.api+json",
    "Content-Type": "application/vnd.api+json",
}

async def create_checkout(variant_id: str, email: str, custom_data: dict, redirect_url: str) -> str:
    """Generate a LemonSqueezy checkout URL for a product variant."""
    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_data": {"email": email, "custom": custom_data},
                "product_options": {"redirect_url": redirect_url},
            },
            "relationships": {
                "store":   {"data": {"type": "stores",   "id": LEMON_STORE_ID}},
                "variant": {"data": {"type": "variants", "id": variant_id}},
            },
        }
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/checkouts", headers=HEADERS, json=payload)
        r.raise_for_status()
        return r.json()["data"]["attributes"]["url"]

def verify_webhook(payload_bytes: bytes, signature: str) -> bool:
    """Verify LemonSqueezy webhook HMAC-SHA256 signature."""
    expected = hmac.new(WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def parse_webhook_event(payload_bytes: bytes) -> dict:
    return json.loads(payload_bytes)


class LemonSqueezyProvider:
    """Class wrapper — satisfies the PaymentProvider factory contract."""

    async def create_checkout(self, variant_id: str, email: str, custom_data: dict,
                              redirect_url: str = "") -> str:
        return await create_checkout(variant_id, email, custom_data, redirect_url)

    def verify_webhook(self, payload_bytes: bytes, signature: str) -> bool:
        return verify_webhook(payload_bytes, signature)

    async def get_order(self, order_id: str) -> dict:
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{BASE_URL}/orders/{order_id}", headers=HEADERS)
            r.raise_for_status()
            return r.json()
