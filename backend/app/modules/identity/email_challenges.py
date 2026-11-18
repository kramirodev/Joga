"""Desafios de e-mail reaproveitando a tabela, o HMAC e os limites do OTP.

Não existe um segundo mecanismo de rate limiting: os limites por endereço,
IP, cooldown e tentativas usam ``phone_challenges``, ``OtpPolicy`` e o mesmo
HMAC (ADR 0050).
"""

from __future__ import annotations

import hmac
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NoReturn

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.modules.email.addresses import (
    InvalidEmail,
    hash_email,
    is_disposable_domain,
    normalize_email,
)
from app.modules.email.deliveries import EmailBudgetExhausted, EmailDeliveryService
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import PhoneChallenge
from app.modules.identity.otp import (
    CODE_PATTERN,
    CODE_WHITESPACE,
    AttemptsExceeded,
    ChallengePurpose,
    ExpiredChallenge,
    HourlyLimitReached,
    InvalidChallenge,
    InvalidCode,
    IpLimitReached,
    IssuedChallenge,
    OtpPolicy,
    ResendTooSoon,
    generate_otp,
)
from app.modules.identity.phone import hash_ip, hash_otp

EMAIL_PURPOSES = {
    ChallengePurpose.email_verification,
    ChallengePurpose.email_change,
    ChallengePurpose.password_reset,
}

DELIVERY_KINDS = {
    ChallengePurpose.email_verification: "email_verification",
    ChallengePurpose.email_change: "email_change_confirm",
    ChallengePurpose.password_reset: "password_reset",
}


class DisposableEmailDomain(ValueError):
    """Domínio descartável bloqueado pela lista configurável."""


@dataclass(frozen=True)
class VerifiedEmailChallenge:
    challenge_id: uuid.UUID
    email_hash: str
    user_id: uuid.UUID | None
    purpose: ChallengePurpose
    verified_at: datetime
    receipt_expires_at: datetime


class EmailChallengeService:
    """Cria e valida desafios com sujeito de e-mail."""

    def __init__(
        self,
        session: Session,
        deliveries: EmailDeliveryService,
        secret: str,
        policy: OtpPolicy | None = None,
        *,
        disposable_domains: frozenset[str] | None = None,
    ) -> None:
        if not secret:
            raise ValueError("segredo de hash não pode ser vazio")
        self._session = session
        self._deliveries = deliveries
        self._secret = secret
        self._policy = policy or OtpPolicy()
        self._disposable = disposable_domains or frozenset()

    @property
    def policy(self) -> OtpPolicy:
        return self._policy

    def request(
        self,
        email: str,
        purpose: ChallengePurpose,
        *,
        now: datetime | None = None,
        request_ip: str | None = None,
        user_id: uuid.UUID | None = None,
        suppress_delivery: bool = False,
    ) -> IssuedChallenge:
        """Cria o desafio e agenda a entrega; falha de orçamento não vaza."""
        if purpose not in EMAIL_PURPOSES:
            raise ValueError("finalidade não pertence ao fluxo de e-mail")

        normalized = normalize_email(email)
        if is_disposable_domain(normalized, self._disposable):
            raise DisposableEmailDomain("domínio de e-mail descartável")

        subject_hash = hash_email(normalized, self._secret)
        ip_hash = hash_ip(request_ip, self._secret) if request_ip else None
        moment = ensure_utc(now or utcnow())

        # Serializa por endereço e por IP no PostgreSQL para que duas
        # requisições simultâneas não burlem cooldown/limites.
        self._acquire_advisory_lock(subject_hash)
        if ip_hash is not None:
            self._acquire_advisory_lock(ip_hash)

        self._enforce_resend_cooldown(subject_hash, moment)
        self._enforce_hourly_limit(subject_hash, moment)
        if ip_hash is not None:
            self._enforce_ip_hourly_limit(ip_hash, moment)

        challenge_id = uuid.uuid4()
        code = self._policy.fixed_code or generate_otp()
        challenge = PhoneChallenge(
            id=challenge_id,
            phone_hash=subject_hash,
            subject_type="email",
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

        if not suppress_delivery:
            try:
                self._deliveries.enqueue(
                    DELIVERY_KINDS[purpose],
                    to=normalized,
                    user_id=user_id,
                    reference=str(challenge_id),
                    code=code,
                    context={"ttl_minutes": max(1, self._policy.ttl_seconds // 60)},
                    now=moment,
                )
            except EmailBudgetExhausted:
                # Erro operacional: a resposta pública continua genérica e o
                # evento de orçamento já foi registrado pelo serviço de entrega.
                pass

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
    ) -> VerifiedEmailChallenge:
        """Valida o código, consome o desafio e devolve o recibo curto."""
        challenge = self._session.get(PhoneChallenge, challenge_id, with_for_update=True)
        if challenge is None or challenge.consumed_at is not None:
            raise InvalidChallenge("desafio inválido")
        if challenge.subject_type != "email" or challenge.purpose not in {
            purpose.value for purpose in EMAIL_PURPOSES
        }:
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

        return VerifiedEmailChallenge(
            challenge_id=challenge_id,
            email_hash=challenge.phone_hash,
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

    def _enforce_resend_cooldown(self, subject_hash: str, moment: datetime) -> None:
        latest_created: datetime | None = self._session.scalar(
            select(PhoneChallenge.created_at)
            .where(
                PhoneChallenge.phone_hash == subject_hash,
                PhoneChallenge.subject_type == "email",
            )
            .order_by(PhoneChallenge.created_at.desc())
            .limit(1)
        )
        if latest_created is None:
            return
        elapsed = (moment - ensure_utc(latest_created)).total_seconds()
        if elapsed < self._policy.resend_cooldown_seconds:
            retry_after = max(1, math.ceil(self._policy.resend_cooldown_seconds - elapsed))
            raise ResendTooSoon(retry_after)

    def _enforce_hourly_limit(self, subject_hash: str, moment: datetime) -> None:
        since = moment - timedelta(hours=1)
        count = self._session.scalar(
            select(func.count())
            .select_from(PhoneChallenge)
            .where(
                PhoneChallenge.phone_hash == subject_hash,
                PhoneChallenge.subject_type == "email",
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
                PhoneChallenge.subject_type == "email",
                PhoneChallenge.created_at >= since,
            )
        )
        if (count or 0) >= self._policy.max_per_ip_per_hour:
            raise IpLimitReached("limite de códigos por IP por hora atingido")

    def _acquire_advisory_lock(self, value: str) -> None:
        bind = self._session.get_bind()
        if bind.dialect.name != "postgresql":
            return
        key = int.from_bytes(bytes.fromhex(value[:16]), "big", signed=True)
        self._session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


__all__ = [
    "DELIVERY_KINDS",
    "EMAIL_PURPOSES",
    "DisposableEmailDomain",
    "EmailChallengeService",
    "InvalidEmail",
    "VerifiedEmailChallenge",
]
