"""
Storage factory — picks provider from STORAGE_PROVIDER env var.
  supabase  (default) — uses Supabase Storage, no extra credentials needed
  r2                  — uses Cloudflare R2 (needs R2_* env vars)
"""
import os as _os
import importlib as _imp

_PROVIDERS = {
    "supabase": ".supabase_storage",
    "r2":       ".r2_client",
}

def _get_module():
    name = _os.getenv("STORAGE_PROVIDER", "supabase")
    path = _PROVIDERS.get(name)
    if not path:
        raise ValueError(f"Unknown STORAGE_PROVIDER={name!r}. Choose: {list(_PROVIDERS)}")
    return _imp.import_module(path, package=__package__)

def upload_artifact(key: str, data: bytes, content_type: str = "application/pdf") -> None:
    _get_module().upload_artifact(key, data, content_type)

def signed_url(key: str, expires_hours: int = 48) -> str:
    return _get_module().signed_url(key, expires_hours)

def upload_and_sign(key: str, data: bytes, expires_hours: int = 48,
                    content_type: str = "application/pdf") -> str:
    return _get_module().upload_and_sign(key, data, expires_hours, content_type)

def delete_artifact(key: str) -> None:
    _get_module().delete_artifact(key)

__all__ = ["upload_artifact", "signed_url", "upload_and_sign", "delete_artifact"]
