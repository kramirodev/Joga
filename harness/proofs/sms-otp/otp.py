"""Prova isolada de OTP por SMS com adapter simulado (Fase 1).

Não é código de produto: não há persistência, HTTP, Redis ou provedor real.
Contrato de referência: docs/JOGA_DOCUMENTACAO_TECNICA.md §5.3.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from dataclasses import dataclass
from typing import Callable, Protocol

OTP_LENGTH = 6
OTP_TTL_SECONDS = 300
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60
MIN_SECRET_BYTES = 32

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


class OtpError(Exception):
    """Erro base da prova de OTP."""


class InvalidPhone(OtpError):
    pass


class ResendTooSoon(OtpError):
    pass


class ChallengeNotFound(OtpError):
    pass


class ChallengeExpired(OtpError):
    pass


class TooManyAttempts(OtpError):
    pass


class InvalidCode(OtpError):
    pass


class AlreadyUsed(OtpError):
    pass


def normalize_phone(raw: str) -> str:
    """Normaliza para E.164. Aceita separadores comuns e prefixo internacional 00."""
    if not isinstance(raw, str):
        raise InvalidPhone("telefone deve ser texto")
    compact = re.sub(r"[\s().-]", "", raw)
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    if not _E164.fullmatch(compact):
        raise InvalidPhone("telefone inválido; use E.164, por exemplo +5511999999999")
    return compact


def _code_hash(secret: bytes, challenge_id: str, code: str) -> str:
    message = f"{challenge_id}:{code}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _generate_code() -> str:
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


class SmsAdapter(Protocol):
    def send(self, phone: str, code: str) -> None: ...


class SimulatedSmsAdapter:
    """Adapter de teste: registra em memória, sem rede e sem custo."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def send(self, phone: str, code: str) -> None:
        self.sent.append({"phone": phone, "code": code})


@dataclass
class Challenge:
    id: str
    phone: str
    code_hash: str
    expires_at: float
    created_at: float
    attempts_left: int = MAX_ATTEMPTS
    used: bool = False

    def __repr__(self) -> str:
        return (
            f"Challenge(id={self.id!r}, phone='***', used={self.used}, "
            f"attempts_left={self.attempts_left})"
        )


class OtpService:
    """Serviço em memória para provar o contrato. Não usar como backend real."""

    def __init__(
        self,
        *,
        secret: bytes,
        adapter: SmsAdapter,
        clock: Callable[[], float] = time.monotonic,
        code_generator: Callable[[], str] = _generate_code,
    ) -> None:
        if len(secret) < MIN_SECRET_BYTES:
            raise ValueError(f"segredo deve ter ao menos {MIN_SECRET_BYTES} bytes")
        self._secret = secret
        self._adapter = adapter
        self._clock = clock
        self._generate_code = code_generator
        self._challenges: dict[str, Challenge] = {}
        self._active_by_phone: dict[str, str] = {}
        self._last_sent_at: dict[str, float] = {}

    def request_code(self, raw_phone: str) -> str:
        phone = normalize_phone(raw_phone)
        now = self._clock()

        last_sent = self._last_sent_at.get(phone)
        if last_sent is not None and now - last_sent < RESEND_COOLDOWN_SECONDS:
            raise ResendTooSoon("aguarde antes de solicitar outro código")

        previous_id = self._active_by_phone.get(phone)
        if previous_id is not None:
            previous = self._challenges.get(previous_id)
            if previous is not None:
                previous.used = True

        challenge_id = secrets.token_urlsafe(16)
        code = self._generate_code()
        challenge = Challenge(
            id=challenge_id,
            phone=phone,
            code_hash=_code_hash(self._secret, challenge_id, code),
            created_at=now,
            expires_at=now + OTP_TTL_SECONDS,
        )
        self._challenges[challenge_id] = challenge
        self._active_by_phone[phone] = challenge_id
        self._last_sent_at[phone] = now
        self._adapter.send(phone, code)
        return challenge_id

    def verify_code(self, challenge_id: str, code: str) -> str:
        challenge = self._challenges.get(challenge_id)
        if challenge is None:
            raise ChallengeNotFound("desafio inexistente")
        if challenge.used:
            raise AlreadyUsed("desafio já utilizado ou invalidado")
        if self._clock() > challenge.expires_at:
            challenge.used = True
            raise ChallengeExpired("código expirado")
        if challenge.attempts_left <= 0:
            challenge.used = True
            raise TooManyAttempts("tentativas esgotadas")

        expected = _code_hash(self._secret, challenge.id, code)
        if not hmac.compare_digest(challenge.code_hash, expected):
            challenge.attempts_left -= 1
            if challenge.attempts_left <= 0:
                challenge.used = True
                raise TooManyAttempts("tentativas esgotadas")
            raise InvalidCode(
                f"código inválido; tentativas restantes: {challenge.attempts_left}"
            )

        challenge.used = True
        return challenge.phone
