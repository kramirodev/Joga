"""Serviço de desafio de telefone e OTP de uso único."""

from __future__ import annotations

import hmac
import math
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import NoReturn

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import PhoneChallenge
from app.modules.identity.phone import hash_ip, hash_otp, hash_phone, normalize_phone
from app.modules.identity.sms import SmsSender

CODE_PATTERN = re.compile(r"^\d{6}$")
CODE_WHITESPACE = re.compile(r"\s+")


class ChallengePurpose(StrEnum):
    """Finalidades permitidas para um desafio de telefone."""

    registration = "registration"
    login = "login"
    phone_change = "phone_change"
    recovery = "recovery"


@dataclass(frozen=True)
class OtpPolicy:
    """Limites configuráveis do desafio."""

    ttl_seconds: int = 300
    max_attempts: int = 5
    resend_cooldown_seconds: int = 60
    max_per_hour: int = 5
    max_per_ip_per_hour: int = 20
    receipt_ttl_seconds: int = 600
    fixed_code: str | None = None

    def __post_init__(self) -> None:
        if self.ttl_seconds <= 0:
            raise ValueError("ttl_seconds deve ser positivo")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts deve ser positivo")
        if self.resend_cooldown_seconds < 0:
            raise ValueError("resend_cooldown_seconds não pode ser negativo")
        if self.max_per_hour <= 0:
            raise ValueError("max_per_hour deve ser positivo")
        if self.max_per_ip_per_hour <= 0:
            raise ValueError("max_per_ip_per_hour deve ser positivo")
        if self.receipt_ttl_seconds <= 0:
            raise ValueError("receipt_ttl_seconds deve ser positivo")
        if self.fixed_code is not None and not CODE_PATTERN.fullmatch(self.fixed_code):
            raise ValueError("fixed_code deve ter seis dígitos")


@dataclass(frozen=True)
class IssuedChallenge:
    challenge_id: uuid.UUID
    expires_at: datetime
    resend_after_seconds: int


@dataclass(frozen=True)
class VerifiedChallenge:
    challenge_id: uuid.UUID
    phone_hash: str
    user_id: uuid.UUID | None
    purpose: ChallengePurpose
    verified_at: datetime
    receipt_expires_at: datetime


class PhoneChallengeError(Exception):
    """Erro base do fluxo de desafio de telefone."""


class InvalidChallenge(PhoneChallengeError):
    """Desafio inexistente, já consumido ou inválido."""


class ExpiredChallenge(PhoneChallengeError):
    """Desafio expirado."""


class AttemptsExceeded(PhoneChallengeError):
    """Limite de tentativas atingido."""


class InvalidCode(PhoneChallengeError):
    """Código não corresponde ao desafio."""


class ResendTooSoon(PhoneChallengeError):
    """Reenvio solicitado antes do intervalo mínimo."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"aguarde {retry_after_seconds}s antes de solicitar outro código")
        self.retry_after_seconds = retry_after_seconds


class HourlyLimitReached(PhoneChallengeError):
    """Limite de desafios por telefone em uma hora atingido."""


class IpLimitReached(PhoneChallengeError):
    """Limite de desafios por IP em uma hora atingido."""


def generate_otp() -> str:
    """Gera um OTP numérico de seis dígitos com fonte criptográfica."""
    return f"{secrets.randbelow(1_000_000):06d}"


class PhoneChallengeService:
    """Cria e valida desafios OTP sem persistir telefone ou código em claro."""

    def __init__(
        self,
        session: Session,
        sender: SmsSender,
        secret: str,
        policy: OtpPolicy | None = None,
    ) -> None:
        if not secret:
            raise ValueError("segredo de hash não pode ser vazio")
        self._session = session
        self._sender = sender
        self._secret = secret
        self._policy = policy or OtpPolicy()

    def request(
        self,
        phone: str,
        purpose: ChallengePurpose,
        *,
        now: datetime | None = None,
        request_ip: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> IssuedChallenge:
        """Cria o desafio, persiste o HMAC e entrega o código ao adaptador."""
        normalized = normalize_phone(phone)
        phone_hash = hash_phone(normalized, self._secret)
        ip_hash = hash_ip(request_ip, self._secret) if request_ip else None
        moment = ensure_utc(now or utcnow())

        # Serializa a criação por telefone e por IP no PostgreSQL, evitando que
        # duas requisições simultâneas burlem o cooldown e os limites por hora.
        self._acquire_advisory_lock(phone_hash)
        if ip_hash is not None:
            self._acquire_advisory_lock(ip_hash)

        self._enforce_resend_cooldown(phone_hash, moment)
        self._enforce_hourly_limit(phone_hash, moment)
        if ip_hash is not None:
            self._enforce_ip_hourly_limit(ip_hash, moment)

        challenge_id = uuid.uuid4()
        code = self._policy.fixed_code or generate_otp()
        challenge = PhoneChallenge(
            id=challenge_id,
            phone_hash=phone_hash,
            user_id=user_id,
            purpose=purpose.value,
            code_hash=hash_otp(challenge_id, code, self._secret),
            attempts=0,
            max_attempts=self._policy.max_attempts,
            request_ip_hash=ip_hash,
            expires_at=moment + timedelta(seconds=self._policy.ttl_seconds),
            created_at=moment,
        )
        self._session.add(challenge)
        self._session.flush()

        # O envio ocorre depois do flush para que o desafio tenha ID e HMAC.
        # Se o adaptador falhar, o chamador deve reverter a transação.
        self._sender.send_otp(phone=normalized, code=code, purpose=purpose.value)

        return IssuedChallenge(
            challenge_id=challenge_id,
            expires_at=ensure_utc(challenge.expires_at),
            resend_after_seconds=self._policy.resend_cooldown_seconds,
        )

    def verify(
        self,
        challenge_id: uuid.UUID,
        code: str,
        *,
        now: datetime | None = None,
    ) -> VerifiedChallenge:
        """Valida o código e marca o desafio como consumido."""
        challenge = self._session.get(PhoneChallenge, challenge_id, with_for_update=True)
        if challenge is None or challenge.consumed_at is not None:
            raise InvalidChallenge("desafio inválido")

        moment = ensure_utc(now or utcnow())
        if ensure_utc(challenge.expires_at) <= moment:
            raise ExpiredChallenge("desafio expirado")

        if challenge.attempts >= challenge.max_attempts:
            raise AttemptsExceeded("limite de tentativas atingido")

        cleaned = CODE_WHITESPACE.sub("", code)
        if not CODE_PATTERN.fullmatch(cleaned):
            self._reject_code(challenge)

        expected = hash_otp(challenge_id, cleaned, self._secret)
        if not hmac.compare_digest(expected, challenge.code_hash):
            self._reject_code(challenge)

        challenge.attempts += 1
        challenge.consumed_at = moment
        self._session.flush()

        return VerifiedChallenge(
            challenge_id=challenge_id,
            phone_hash=challenge.phone_hash,
            user_id=challenge.user_id,
            purpose=ChallengePurpose(challenge.purpose),
            verified_at=moment,
            receipt_expires_at=moment + timedelta(seconds=self._policy.receipt_ttl_seconds),
        )

    def _reject_code(self, challenge: PhoneChallenge) -> NoReturn:
        challenge.attempts += 1
        self._session.flush()
        if challenge.attempts >= challenge.max_attempts:
            raise AttemptsExceeded("limite de tentativas atingido")
        raise InvalidCode("código inválido")

    def _enforce_resend_cooldown(self, phone_hash: str, moment: datetime) -> None:
        latest_created: datetime | None = self._session.scalar(
            select(PhoneChallenge.created_at)
            .where(PhoneChallenge.phone_hash == phone_hash)
            .order_by(PhoneChallenge.created_at.desc())
            .limit(1)
        )
        if latest_created is None:
            return

        elapsed = (moment - ensure_utc(latest_created)).total_seconds()
        if elapsed < self._policy.resend_cooldown_seconds:
            retry_after = max(1, math.ceil(self._policy.resend_cooldown_seconds - elapsed))
            raise ResendTooSoon(retry_after)

    def _enforce_hourly_limit(self, phone_hash: str, moment: datetime) -> None:
        since = moment - timedelta(hours=1)
        count = self._session.scalar(
            select(func.count())
            .select_from(PhoneChallenge)
            .where(
                PhoneChallenge.phone_hash == phone_hash,
                PhoneChallenge.created_at >= since,
            )
        )
        if (count or 0) >= self._policy.max_per_hour:
            raise HourlyLimitReached("limite de códigos por hora atingido")

    def _enforce_ip_hourly_limit(self, ip_hash: str, moment: datetime) -> None:
        since = moment - timedelta(hours=1)
        count = self._session.scalar(
            select(func.count())
            .select_from(PhoneChallenge)
            .where(
                PhoneChallenge.request_ip_hash == ip_hash,
                PhoneChallenge.created_at >= since,
            )
        )
        if (count or 0) >= self._policy.max_per_ip_per_hour:
            raise IpLimitReached("limite de códigos por IP por hora atingido")

    def _acquire_advisory_lock(self, value: str) -> None:
        """Serializa operações por chave no PostgreSQL; no SQLite é no-op."""
        bind = self._session.get_bind()
        if bind.dialect.name != "postgresql":
            return
        key = int.from_bytes(bytes.fromhex(value[:16]), "big", signed=True)
        self._session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
