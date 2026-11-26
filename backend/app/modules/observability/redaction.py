"""Redação de segredos e PII antes de qualquer persistência de log.

Regras deliberadamente conservadoras: o log operacional nunca deve conter
senha, token, cookie, OTP, chave de API, CPF, e-mail ou telefone em claro.
Texto livre (``message``, ``reason``, stack) passa por mascaramento; valores de
``metadata``/``details`` passam por redação por chave e por texto.
"""

from __future__ import annotations

import json
import re
from typing import Any

REDACTED = "[redacted]"
MAX_METADATA_BYTES = 8_192
MAX_MESSAGE_CHARS = 2_048
MAX_USER_AGENT_CHARS = 512
MAX_STACK_CHARS = 16_000

SECRET_KEY_PATTERN = re.compile(
    r"(password|senha|token|access_token|refresh_token|authorization|cookie|"
    r"set-cookie|set_cookie|otp|code|cpf|card|cvv|pix|secret|api_key|apikey)",
    re.IGNORECASE,
)

_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=:\-]{6,}")
_JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}")
_KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b(password|senha|token|access_token|refresh_token|authorization|"
    r"cookie|set-cookie|otp|code|cpf|card|cvv|pix|secret|api_key)"
    r"\b\s*[:=]\s*(\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
)
_EMAIL_PATTERN = re.compile(
    r"\b([A-Za-z0-9._%+\-])([A-Za-z0-9._%+\-]*)@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b"
)
_CPF_PATTERN = re.compile(r"(?<![\w])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![\w])")
_PHONE_PATTERN = re.compile(
    r"(?<![\d\w])(?:\+\d{1,3}[\s\-.]?)?"
    r"(?:\(\d{2}\)\s?|\d{2}[\s.])"
    r"(?:9?\d{4})[\s\-.]?\d{4}(?!\d)"
)
_INTERNATIONAL_PHONE_PATTERN = re.compile(r"\+\d{1,3}[\s\-.]?\d{10,11}(?!\d)")


def _mask_phone(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) < 8:
        return REDACTED
    return f"{digits[:2]}{'*' * (len(digits) - 4)}{digits[-2:]}"


def redact_text(value: str) -> str:
    """Remove segredos e mascara PII de um texto livre."""
    if not value:
        return value
    text = _KEY_VALUE_PATTERN.sub(lambda m: f"{m.group(1)}={REDACTED}", value)
    text = _BEARER_PATTERN.sub("Bearer " + REDACTED, text)
    text = _JWT_PATTERN.sub(REDACTED, text)
    text = _EMAIL_PATTERN.sub(
        lambda m: f"{m.group(1)}***@{m.group(3)}",
        text,
    )
    text = _CPF_PATTERN.sub("***.***.***-**", text)
    text = _INTERNATIONAL_PHONE_PATTERN.sub(_mask_phone, text)
    text = _PHONE_PATTERN.sub(_mask_phone, text)
    return text


def redact_value(value: Any, *, depth: int = 0) -> Any:
    """Reduz um valor arbitrário a JSON seguro, redigindo por chave e por texto."""
    if depth > 8:
        return REDACTED
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 100:
                redacted["_truncated"] = True
                break
            key_text = str(key)
            lowered = key_text.lower()
            already_masked = lowered.endswith(("_masked", "_redacted"))
            if SECRET_KEY_PATTERN.search(key_text) and not already_masked:
                redacted[key_text] = REDACTED
            else:
                redacted[key_text] = redact_value(item, depth=depth + 1)
        return redacted
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        result = [redact_value(item, depth=depth + 1) for item in items[:100]]
        if len(items) > 100:
            result.append("[truncated]")
        return result
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return redact_text(str(value))


def sanitize_metadata(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Redige e limita ``metadata``/``details`` a 8 KB de JSON."""
    if not value:
        return None
    redacted = redact_value(value)
    if not isinstance(redacted, dict):
        redacted = {"value": redacted}
    encoded = json.dumps(redacted, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(encoded.encode("utf-8")) <= MAX_METADATA_BYTES:
        return redacted
    return {
        "_truncated": True,
        "preview": encoded[: MAX_METADATA_BYTES - 64],
    }


def sanitize_message(value: str | None, *, limit: int = MAX_MESSAGE_CHARS) -> str | None:
    if value is None:
        return None
    return redact_text(value)[:limit]


def sanitize_user_agent(value: str | None) -> str | None:
    if not value:
        return None
    return value[:MAX_USER_AGENT_CHARS]


def sanitize_stack(value: str | None) -> str | None:
    if not value:
        return None
    return redact_text(value)[:MAX_STACK_CHARS]


def sanitize_details(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Alias explícito para detalhes de auditoria/segurança."""
    return sanitize_metadata(value)


def mask_ip(value: str | None) -> str | None:
    """Mascara o IP para listagens administrativas (ex.: ``203.0.113.•``)."""
    if not value:
        return value
    if ":" in value:
        hextets = value.split(":")
        if len(hextets) >= 4:
            return ":".join(hextets[:3] + ["•"])
        return "•"
    octets = value.split(".")
    if len(octets) == 4:
        return ".".join(octets[:3] + ["•"])
    return "•"


__all__ = [
    "MAX_METADATA_BYTES",
    "MAX_MESSAGE_CHARS",
    "MAX_USER_AGENT_CHARS",
    "REDACTED",
    "mask_ip",
    "redact_text",
    "redact_value",
    "sanitize_details",
    "sanitize_message",
    "sanitize_metadata",
    "sanitize_stack",
    "sanitize_user_agent",
]
