"""Geração e hash de tokens opacos."""

import hashlib
import hmac
import secrets

TOKEN_BYTES = 32


def generate_token() -> str:
    """Gera um token opaco imprevisível em base64url."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str, secret: str, label: str) -> str:
    """HMAC-SHA256 com separação de domínio por tipo de token."""
    if label not in {"access", "refresh"}:
        raise ValueError("label de token inválido")
    message = f"{label}:{token}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
