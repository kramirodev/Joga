"""Normalização de telefone (E.164) e hashes HMAC de dados sensíveis."""

import hashlib
import hmac
import re
from uuid import UUID

E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")
FORMATTING_PATTERN = re.compile(r"[\s().-]")


class InvalidPhoneNumber(ValueError):
    """Número fora do formato E.164 aceito pelo contrato da API."""


def normalize_phone(value: str) -> str:
    """Remove formatação e exige E.164 já com código de país.

    A conversão de formato nacional para E.164 exige uma biblioteca de
    numeração; nesta iteração o cliente deve enviar o número internacional.
    """
    if not isinstance(value, str):
        raise InvalidPhoneNumber("telefone deve ser texto em E.164")
    cleaned = FORMATTING_PATTERN.sub("", value.strip())
    if not E164_PATTERN.fullmatch(cleaned):
        raise InvalidPhoneNumber("telefone deve estar em E.164, por exemplo +5511987654321")
    return cleaned


def _digest(secret: str, label: str, value: str) -> str:
    message = f"{label}:{value}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def hash_phone(phone: str, secret: str) -> str:
    """Hash de busca do telefone; o número não é persistido em claro."""
    return _digest(secret, "phone", normalize_phone(phone))


def hash_ip(ip: str, secret: str) -> str:
    """Hash do IP de origem para rate limiting e auditoria sem PII."""
    return _digest(secret, "ip", ip.strip().lower())


def hash_otp(challenge_id: UUID, code: str, secret: str) -> str:
    """HMAC do OTP vinculado ao desafio; nunca armazena o código em claro."""
    return _digest(secret, "otp", f"{challenge_id}:{code}")
