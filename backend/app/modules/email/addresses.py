"""Normalização e hash de endereços de e-mail.

O endereço normalizado é a chave da credencial (``user_emails``). O hash HMAC
é usado apenas em logs de entrega e eventos de segurança; o endereço completo
nunca deve ir para log.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from ipaddress import ip_address

MAX_EMAIL_LENGTH = 254
MAX_LOCAL_LENGTH = 64

# Subconjunto ASCII de atext do RFC 5322. Endereços com parte local
# internacionalizada ficam fora do beta; evita homógrafos e ambiguidade.
LOCAL_PATTERN = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+$")
DOMAIN_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

# Lista embutida, sem dependência paga. Pode ser ampliada por
# JOGA_EMAIL_DISPOSABLE_DOMAINS (separada por vírgula).
BUILTIN_DISPOSABLE_DOMAINS = frozenset(
    {
        "10minutemail.com",
        "guerrillamail.com",
        "guerrillamail.net",
        "mailinator.com",
        "sharklasers.com",
        "tempmail.com",
        "tempmail.net",
        "throwawaymail.com",
        "trashmail.com",
        "yopmail.com",
    }
)


class InvalidEmail(ValueError):
    """Endereço fora do formato aceito pelo contrato da API."""


def normalize_email(value: str) -> str:
    """Normaliza trim/minúsculas e converte o domínio para punycode.

    A parte local é mantida sem remoção de pontos ou sufixos ``+``: remover
    esses elementos juntaria endereços distintos em uma única credencial.
    """
    if not isinstance(value, str):
        raise InvalidEmail("e-mail deve ser texto")

    cleaned = value.strip()
    if not cleaned or len(cleaned) > MAX_EMAIL_LENGTH:
        raise InvalidEmail("e-mail inválido")
    if any(char.isspace() or ord(char) < 32 for char in cleaned):
        raise InvalidEmail("e-mail inválido")
    if cleaned.count("@") != 1:
        raise InvalidEmail("e-mail inválido")

    local, domain = cleaned.rsplit("@", 1)
    if not local or len(local) > MAX_LOCAL_LENGTH:
        raise InvalidEmail("e-mail inválido")
    if not LOCAL_PATTERN.fullmatch(local):
        raise InvalidEmail("e-mail inválido")
    if local.startswith(".") or local.endswith(".") or ".." in local:
        raise InvalidEmail("e-mail inválido")

    domain = domain.strip().rstrip(".").lower()
    if not domain:
        raise InvalidEmail("e-mail inválido")
    try:
        # ``idna`` rejeita espaços, sublinhados e rótulos inválidos.
        ascii_domain = domain.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise InvalidEmail("domínio de e-mail inválido") from error

    if len(ascii_domain) > 253:
        raise InvalidEmail("domínio de e-mail inválido")
    try:
        ip_address(ascii_domain)
    except ValueError:
        labels = ascii_domain.split(".")
        if len(labels) < 2 or any(not DOMAIN_LABEL_PATTERN.fullmatch(label) for label in labels):
            raise InvalidEmail("domínio de e-mail inválido") from None
    else:
        raise InvalidEmail("domínio de e-mail inválido")

    normalized = f"{local.lower()}@{ascii_domain}"
    if len(normalized) > MAX_EMAIL_LENGTH:
        raise InvalidEmail("e-mail inválido")
    return normalized


def email_domain(normalized: str) -> str:
    """Domínio de um endereço já normalizado."""
    return normalized.rsplit("@", 1)[1]


def is_disposable_domain(normalized: str, extra_domains: frozenset[str]) -> bool:
    """Indica se o domínio está na lista embutida ou na configuração."""
    domain = email_domain(normalized)
    while domain:
        if domain in BUILTIN_DISPOSABLE_DOMAINS or domain in extra_domains:
            return True
        if "." not in domain:
            return False
        domain = domain.split(".", 1)[1]
    return False


def hash_email(normalized: str, secret: str) -> str:
    """HMAC de busca do e-mail; nunca persiste o endereço em claro no log."""
    message = f"email:{normalized}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


__all__ = [
    "BUILTIN_DISPOSABLE_DOMAINS",
    "InvalidEmail",
    "email_domain",
    "hash_email",
    "is_disposable_domain",
    "normalize_email",
]
