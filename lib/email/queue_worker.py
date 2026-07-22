"""
Email queue worker — agent-core-infra
Sends due, unsent rows from `email_queue` (populated by sequences.trigger_sequence)
and marks them sent. Call process_due_emails() from a cron-triggered endpoint —
each product's backend exposes one and an external scheduler (GitHub Actions,
cron-job.org, etc.) hits it periodically.
"""
from datetime import datetime, timezone

from .resend_client import send_template
from ..db.supabase_client import get_client


async def process_due_emails(limit: int = 50) -> int:
    """Send every queued email whose send_after has passed. Returns count sent."""
    client = get_client()
    now = datetime.now(timezone.utc).isoformat()
    res = (
        client.table("email_queue")
        .select("*")
        .eq("sent", False)
        .lte("send_after", now)
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    sent = 0
    for row in rows:
        try:
            await send_template(row["email"], row["subject"], row["template"], row["context"])
            client.table("email_queue").update({"sent": True}).eq("id", row["id"]).execute()
            sent += 1
        except Exception as exc:
            print(f"[email_queue] failed to send row {row.get('id')}: {exc}", flush=True)
    return sent
