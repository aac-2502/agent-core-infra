"""
Supabase Storage adapter — agent-core-infra
Drop-in replacement for r2_client when STORAGE_PROVIDER=supabase (default).
Uses the same public bucket pattern; signed URLs expire in 48 h.
"""
import os
from supabase import create_client, Client

BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "agent-artifacts")

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            os.getenv("SUPABASE_URL", ""),
            os.getenv("SUPABASE_SERVICE_KEY", ""),
        )
    return _client


def upload_artifact(key: str, data: bytes, content_type: str = "application/pdf") -> None:
    _get_client().storage.from_(BUCKET).upload(
        key, data, {"content-type": content_type, "upsert": "true"}
    )


def signed_url(key: str, expires_hours: int = 48) -> str:
    result = _get_client().storage.from_(BUCKET).create_signed_url(
        key, expires_in=expires_hours * 3600
    )
    return result["signedURL"]


def upload_and_sign(key: str, data: bytes, expires_hours: int = 48,
                    content_type: str = "application/pdf") -> str:
    upload_artifact(key, data, content_type)
    return signed_url(key, expires_hours)


def delete_artifact(key: str) -> None:
    _get_client().storage.from_(BUCKET).remove([key])
