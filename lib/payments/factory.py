"""
Payment provider factory — agent-core-infra
Lazy imports: only loads the configured provider to avoid crashing on
modules that are not yet implemented.
"""
import os
from .base import PaymentProvider

# Map of provider name → (module path, class name)
_REGISTRY: dict[str, tuple[str, str]] = {
    "polar":   (".polar",   "PolarProvider"),
    "payhip":  (".payhip",  "PayhipProvider"),
    "gumroad": (".gumroad", "GumroadProvider"),
}


def get_provider() -> PaymentProvider:
    name = os.getenv("PAYMENT_PROVIDER", "")
    if not name:
        raise ValueError("PAYMENT_PROVIDER env var is not set")
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown PAYMENT_PROVIDER='{name}'. "
            f"Valid options: {list(_REGISTRY)}"
        )
    module_path, class_name = _REGISTRY[name]
    import importlib
    module = importlib.import_module(module_path, package=__package__)
    cls = getattr(module, class_name)
    return cls()
