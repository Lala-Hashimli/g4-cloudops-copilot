from __future__ import annotations

from typing import Iterable


def mask_secret(secret: str | None, visible_chars: int = 4) -> str:
    if not secret:
        return ""
    if len(secret) <= visible_chars:
        return "*" * len(secret)
    return f"{secret[:visible_chars]}***"


def sanitize_text(text: str, secrets: Iterable[str | None]) -> str:
    sanitized = text
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, mask_secret(secret))
    return sanitized


def mask_chat_id(value: str | int | None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) <= 6:
        return "*" * len(text)
    return f"{text[:4]}****{text[-3:]}"
