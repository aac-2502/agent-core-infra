"""
Email sequence orchestration — agent-core-infra
Sends the immediate email and stores scheduled ones in Supabase
for a cron job to pick up (e.g. Supabase Edge Functions cron or Railway cron).
"""
from .resend_client import send_template
from ..db.supabase_client import insert

SEQUENCES: dict[str, list[dict]] = {
    "agentcv_free": [
        {"delay_hours": 0,   "template": "nurture_1",   "subject": "3 errores que detectamos en tu CV"},
        {"delay_hours": 72,  "template": "upsell",      "subject": "Tu CV optimizado completo →"},
        {"delay_hours": 168, "template": "confirmation", "subject": "¿Tenés un contrato freelance actualizado?"},
    ],
    "agentcv_paid": [
        {"delay_hours": 0,   "template": "delivery",    "subject": "Tu CV optimizado está listo ↓"},
        {"delay_hours": 72,  "template": "nurture_1",   "subject": "¿Ya lo enviaste? Tip para la entrevista"},
        {"delay_hours": 240, "template": "upsell",      "subject": "¿Tenés código que revisar antes de una entrevista técnica?"},
    ],
}


async def trigger_sequence(
    email: str,
    sequence_name: str,
    context: dict,
    product: str = "agentcv",
) -> None:
    steps = SEQUENCES.get(sequence_name, [])
    if not steps:
        return

    # Send immediate step (delay_hours == 0) right now
    for step in steps:
        if step["delay_hours"] == 0:
            await send_template(email, step["subject"], step["template"], context)
        else:
            # Store in Supabase — a cron job picks these up and sends at the right time
            delay_hours = step["delay_hours"]
            await insert("email_queue", {
                "email":        email,
                "template":     step["template"],
                "subject":      step["subject"],
                "context":      context,
                "product":      product,
                "send_after":   f"NOW() + INTERVAL '{delay_hours} hours'",
                "sent":         False,
            })
