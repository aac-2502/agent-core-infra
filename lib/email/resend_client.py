"""
Resend email client — agent-core-infra
Send transactional and nurture emails for all products.
"""
import os
import httpx
from pathlib import Path
from string import Template

RESEND_API_KEY  = os.getenv("RESEND_API_KEY", "")
FROM_DOMAIN     = os.getenv("EMAIL_FROM_DOMAIN", "noreply@yourdomain.com")
TEMPLATES_DIR   = Path(__file__).parent / "templates"

_HEADERS = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}


def _load_template(name: str, context: dict) -> str:
    path = TEMPLATES_DIR / f"{name}.html"
    raw = path.read_text()
    return Template(raw).safe_substitute(context)


async def send_email(to: str, subject: str, html: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.resend.com/emails",
            headers=_HEADERS,
            json={"from": FROM_DOMAIN, "to": [to], "subject": subject, "html": html},
        )
        r.raise_for_status()
        return r.json()


async def send_template(to: str, subject: str, template: str, context: dict) -> dict:
    html = _load_template(template, context)
    return await send_email(to, subject, html)


async def send_delivery(to: str, product: str, downloads: list[dict], extra: dict = {}) -> dict:
    ctx = {"product": product, "downloads_html": "".join(
        f'<a href="{d["url"]}" style="display:block;margin:8px 0;color:#C8963E">'
        f'⬇ {d["name"]}</a>' for d in downloads
    ), **extra}
    return await send_template(to, f"Tu {product} está listo ↓", "delivery", ctx)
