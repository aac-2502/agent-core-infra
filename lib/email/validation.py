import re

_SYNTAX_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


def validate_syntax(email: str) -> bool:
    """Return True if email passes basic syntax check. Use before sending via Resend."""
    return bool(_SYNTAX_RE.match(email.strip().lower()))
