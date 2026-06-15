"""
Supabase client — agent-core-infra
Singleton client shared across all products.
"""
import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")  # Service key, not anon

_client: Client | None = None

def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client

async def insert(table: str, data: dict, schema: str = "public") -> dict:
    client = get_client()
    res = client.schema(schema).table(table).insert(data).execute()
    return res.data[0] if res.data else {}

async def update(table: str, match: dict, data: dict, schema: str = "public") -> dict:
    client = get_client()
    q = client.schema(schema).table(table).update(data)
    for k, v in match.items():
        q = q.eq(k, v)
    res = q.execute()
    return res.data[0] if res.data else {}

async def select_one(table: str, match: dict, schema: str = "public") -> dict | None:
    client = get_client()
    q = client.schema(schema).table(table).select("*")
    for k, v in match.items():
        q = q.eq(k, v)
    res = q.limit(1).execute()
    return res.data[0] if res.data else None

async def upsert_lead(email: str, source_product: str) -> None:
    client = get_client()
    client.table("leads").upsert(
        {"email": email, "source_product": source_product},
        on_conflict="email"
    ).execute()
