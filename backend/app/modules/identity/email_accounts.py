"""Cadastro, login por senha, reset e troca de e-mail (ADR 0050).

O código de e-mail é usado apenas para verificar o endereço no cadastro, trocar
o e-mail e redefinir a senha. Login usa e-mail + senha; não há login por código.
"""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.text import CONTROL_PATTERN
from app.modules.email.addresses import hash_email, normalize_email
from app.modules.email.deliveries import EmailBudgetExhausted, EmailDeliveryService
from app.modules.email.models import UserEmail
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.email_challenges import (
    DisposableEmailDomain,
    EmailChallengeService,
    VerifiedEmailChallenge,
)
from app.modules.identity.models import PhoneChallenge, User, UserPassword
from app.modules.identity.otp import ChallengePurpose
from app.modules.identity.passwords import PasswordService
from app.modules.profile.models import UserProfile


class EmailAccountError(Exception):
    """Erro base do fluxo de conta por e-mail."""


class InvalidEmailReceipt(EmailAccountError):
    """Recibo inexistente, expirado, já usado, de outra finalidade ou endereço."""


class InvalidCredentials(EmailAccountError):
    """E-mail/senha/conta inválidos; a resposta pública é sempre genérica."""


class InvalidPasswordReset(EmailAccountError):
    """Recibo, endereço ou conta inválidos no reset de senha."""


class EmailAlreadyRegistered(EmailAccountError):
    """Endereço já vinculado a outra conta ativa."""


class EmailUnchanged(EmailAccountError):
    """Novo endereço é igual ao atual."""


class EmailChangeCooldown(EmailAccountError):
    """Troca recente; aguardar a janela de 24 h."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("troca de e-mail em cooldown")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class EmailAccountUser:
    id: uuid.UUID
    status: str


@dataclass(frozen=True)
class EmailChangeResult:
    old_email: str
    new_email: str


class EmailAccountService:
    """Consome recibos, autentica por senha e mantém a credencial primária."""

    def __init__(
        self,
        session: Session,
        challenges: EmailChallengeService,
        deliveries: EmailDeliveryService,
        passwords: PasswordService,
        secret: str,
        *,
        receipt_ttl_seconds: int = 600,
        change_cooldown_hours: int = 24,
    ) -> None:
        if receipt_ttl_seconds <= 0:
            raise ValueError("receipt_ttl_seconds deve ser positivo")
        if change_cooldown_hours <= 0:
            raise ValueError("change_cooldown_hours deve ser positivo")
        if not secret:
            raise ValueError("segredo de hash não pode ser vazio")
        self._session = session
        self._challenges = challenges
        self._deliveries = deliveries
        self._passwords = passwords
        self._secret = secret
        self._receipt_ttl = timedelta(seconds=receipt_ttl_seconds)
        self._change_cooldown = timedelta(hours=change_cooldown_hours)

    def register(
        self,
        challenge_id: uuid.UUID,
        email: str,
        password: str,
        *,
        display_name: str | None = None,
        now: datetime | None = None,
    ) -> EmailAccountUser:
        """Consome o recibo de verificação e cria conta + perfil + senha."""
        moment = ensure_utc(now or utcnow())
        normalized = normalize_email(email)
        self._passwords.validate(password, normalized)

        challenge = self._load_receipt(challenge_id, ChallengePurpose.email_verification, moment)
        self._bind(challenge, normalized)

        existing = self._active_credential(normalized)
        if existing is not None:
            raise EmailAlreadyRegistered("e-mail já cadastrado")

        user = User(status="active")
        self._session.add(user)
        self._session.flush()

        self._session.add(
            UserEmail(
                user_id=user.id,
                email_normalized=normalized,
                verified_at=ensure_utc(challenge.consumed_at)
                if challenge.consumed_at is not None
                else moment,
                is_primary=True,
                created_at=moment,
            )
        )
        self._session.add(
            UserProfile(
                user_id=user.id,
                display_name=_clean_display_name(display_name),
                created_at=moment,
            )
        )
        self._session.add(
            UserPassword(
                user_id=user.id,
                password_hash=self._passwords.hash(password),
                password_changed_at=moment,
            )
        )
        challenge.receipt_used_at = moment
        self._session.flush()
        return EmailAccountUser(id=user.id, status=user.status)

    def authenticate(
        self,
        email: str,
        password: str,
        *,
        now: datetime | None = None,
    ) -> EmailAccountUser:
        """Autentica e-mail + senha com resposta e custo uniformes.

        E-mail inexistente executa um verify descartável para não revelar a
        existência da conta pelo tempo de resposta.
        """
        normalized = normalize_email(email)
        credential = self._session.scalar(
            select(UserEmail).where(
                UserEmail.email_normalized == normalized,
                UserEmail.released_at.is_(None),
            )
        )
        if credential is None:
            self._passwords.verify_dummy(password)
            raise InvalidCredentials("credenciais inválidas")

        stored = self._session.get(UserPassword, credential.user_id)
        if stored is None:
            self._passwords.verify_dummy(password)
            raise InvalidCredentials("credenciais inválidas")

        valid = self._passwords.verify(stored.password_hash, password)
        user = self._session.get(User, credential.user_id)
        if (
            not valid
            or user is None
            or user.status != "active"
            or credential.verified_at is None
            or credential.undeliverable_at is not None
            or stored.compromised_at is not None
        ):
            raise InvalidCredentials("credenciais inválidas")

        if self._passwords.needs_rehash(stored.password_hash):
            stored.password_hash = self._passwords.hash(password)
            self._session.flush()

        return EmailAccountUser(id=user.id, status=user.status)

    def request_password_reset(
        self,
        email: str,
        *,
        request_ip: str | None = None,
        now: datetime | None = None,
    ) -> tuple[uuid.UUID, datetime, int]:
        """Envia código de reset sem revelar se o endereço tem conta."""
        moment = ensure_utc(now or utcnow())
        normalized = normalize_email(email)
        credential = self._active_credential(normalized)
        suppress = credential is None or credential.undeliverable_at is not None
        issued = self._challenges.request(
            normalized,
            ChallengePurpose.password_reset,
            now=moment,
            request_ip=request_ip,
            user_id=credential.user_id if credential is not None else None,
            suppress_delivery=suppress,
        )
        return issued.challenge_id, issued.expires_at, issued.resend_after_seconds

    def reset_password(
        self,
        challenge_id: uuid.UUID,
        email: str,
        new_password: str,
        *,
        now: datetime | None = None,
    ) -> EmailAccountUser:
        """Consome o código de reset e grava a nova senha."""
        moment = ensure_utc(now or utcnow())
        normalized = normalize_email(email)
        self._passwords.validate(new_password, normalized)

        challenge = self._load_receipt(challenge_id, ChallengePurpose.password_reset, moment)
        self._bind(challenge, normalized)

        credential = self._active_credential(normalized)
        user = self._session.get(User, credential.user_id) if credential is not None else None
        if (
            credential is None
            or credential.verified_at is None
            or credential.undeliverable_at is not None
            or user is None
            or user.status != "active"
        ):
            raise InvalidPasswordReset("reset inválido")

        stored = self._session.get(UserPassword, user.id)
        if stored is None:
            stored = UserPassword(
                user_id=user.id,
                password_hash=self._passwords.hash(new_password),
                password_changed_at=moment,
            )
            self._session.add(stored)
        else:
            stored.password_hash = self._passwords.hash(new_password)
            stored.password_changed_at = moment
            stored.compromised_at = None
        challenge.receipt_used_at = moment
        self._session.flush()

        self._queue_password_changed(user.id, normalized, f"reset:{challenge_id}", moment)
        return EmailAccountUser(id=user.id, status=user.status)

    def change_password(
        self,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str,
        *,
        now: datetime | None = None,
    ) -> EmailAccountUser:
        """Troca a senha de uma sessão autenticada, verificando a atual."""
        moment = ensure_utc(now or utcnow())
        user = self._session.get(User, user_id)
        stored = self._session.get(UserPassword, user_id)
        if (
            user is None
            or user.status != "active"
            or stored is None
            or not self._passwords.verify(stored.password_hash, current_password)
        ):
            raise InvalidCredentials("credenciais inválidas")

        credential = self._primary(user_id)
        if credential is None:
            raise InvalidCredentials("credenciais inválidas")
        self._passwords.validate(new_password, credential.email_normalized)

        stored.password_hash = self._passwords.hash(new_password)
        stored.password_changed_at = moment
        stored.compromised_at = None
        self._session.flush()
        self._queue_password_changed(
            user_id,
            credential.email_normalized,
            f"change:{uuid.uuid4()}",
            moment,
        )
        return EmailAccountUser(id=user.id, status=user.status)

    def request_change(
        self,
        user_id: uuid.UUID,
        new_email: str,
        *,
        request_ip: str | None = None,
        now: datetime | None = None,
    ) -> tuple[uuid.UUID, datetime, int]:
        """Envia código ao novo endereço após validar cooldown e igualdade."""
        moment = ensure_utc(now or utcnow())
        normalized = normalize_email(new_email)

        current = self._primary(user_id)
        if current is not None and hmac.compare_digest(current.email_normalized, normalized):
            raise EmailUnchanged("novo e-mail é igual ao atual")

        self._enforce_change_cooldown(user_id, moment)

        existing = self._active_credential(normalized)
        suppress = existing is not None and existing.undeliverable_at is not None
        issued = self._challenges.request(
            normalized,
            ChallengePurpose.email_change,
            now=moment,
            request_ip=request_ip,
            user_id=user_id,
            suppress_delivery=suppress,
        )
        return issued.challenge_id, issued.expires_at, issued.resend_after_seconds

    def confirm_change(
        self,
        user_id: uuid.UUID,
        new_email: str,
        challenge_id: uuid.UUID,
        code: str,
        *,
        now: datetime | None = None,
    ) -> EmailChangeResult:
        """Valida o código no novo endereço, troca a credencial e avisa o antigo."""
        moment = ensure_utc(now or utcnow())
        verified = self._challenges.verify(challenge_id, code, now=moment)
        if verified.purpose is not ChallengePurpose.email_change:
            raise InvalidEmailReceipt("recibo de outra finalidade")
        if verified.user_id != user_id:
            raise InvalidEmailReceipt("recibo de outro usuário")

        challenge = self._session.get(PhoneChallenge, verified.challenge_id)
        if challenge is None or challenge.receipt_used_at is not None:
            raise InvalidEmailReceipt("recibo já utilizado")

        normalized = self._bind_hash(verified, new_email)
        current_rows = self._active_credentials(user_id)
        old_email = self._old_primary(current_rows)
        if old_email is not None and hmac.compare_digest(old_email, normalized):
            raise EmailUnchanged("novo e-mail é igual ao atual")

        existing = self._active_credential(normalized)
        if existing is not None and existing.user_id != user_id:
            raise EmailAlreadyRegistered("e-mail já cadastrado")

        self._enforce_change_cooldown(user_id, moment)

        for row in current_rows:
            row.released_at = moment
            row.is_primary = False
        # Libera a primária antiga antes de inserir a nova, para não colidir
        # com o índice único parcial de primária ativa.
        self._session.flush()

        self._session.add(
            UserEmail(
                user_id=user_id,
                email_normalized=normalized,
                verified_at=moment,
                is_primary=True,
                created_at=moment,
            )
        )
        challenge.receipt_used_at = moment
        self._session.flush()

        if old_email is not None:
            try:
                self._deliveries.enqueue(
                    "email_change_notice",
                    to=old_email,
                    user_id=user_id,
                    reference=f"change:{challenge_id}",
                    context={"occurred_at": _format_moment(moment)},
                    now=moment,
                )
            except EmailBudgetExhausted:
                pass

        return EmailChangeResult(old_email=old_email or normalized, new_email=normalized)

    def list_credentials(self, user_id: uuid.UUID) -> list[UserEmail]:
        return list(
            self._session.scalars(
                select(UserEmail)
                .where(UserEmail.user_id == user_id, UserEmail.released_at.is_(None))
                .order_by(UserEmail.is_primary.desc(), UserEmail.created_at)
            )
        )

    def primary_email(self, user_id: uuid.UUID) -> UserEmail | None:
        return self._primary(user_id)

    def _queue_password_changed(
        self,
        user_id: uuid.UUID,
        email: str,
        reference: str,
        moment: datetime,
    ) -> None:
        try:
            self._deliveries.enqueue(
                "password_changed",
                to=email,
                user_id=user_id,
                reference=reference,
                context={"occurred_at": _format_moment(moment)},
                now=moment,
            )
        except EmailBudgetExhausted:
            pass

    def _load_receipt(
        self,
        challenge_id: uuid.UUID,
        purpose: ChallengePurpose,
        moment: datetime,
    ) -> PhoneChallenge:
        challenge = self._session.get(PhoneChallenge, challenge_id, with_for_update=True)
        if challenge is None or challenge.subject_type != "email":
            raise InvalidEmailReceipt("recibo inválido")
        if challenge.consumed_at is None or challenge.receipt_used_at is not None:
            raise InvalidEmailReceipt("recibo inválido")
        if ChallengePurpose(challenge.purpose) is not purpose:
            raise InvalidEmailReceipt("finalidade do recibo não confere")
        consumed_at = ensure_utc(challenge.consumed_at)
        if consumed_at + self._receipt_ttl <= moment:
            raise InvalidEmailReceipt("recibo expirado")
        return challenge

    def _bind(self, challenge: PhoneChallenge, normalized: str) -> None:
        expected = hash_email(normalized, self._secret)
        if not hmac.compare_digest(expected, challenge.phone_hash):
            raise InvalidEmailReceipt("recibo de outro endereço")

    def _bind_hash(self, verified: VerifiedEmailChallenge, email: str) -> str:
        normalized = normalize_email(email)
        expected = hash_email(normalized, self._secret)
        if not hmac.compare_digest(expected, verified.email_hash):
            raise InvalidEmailReceipt("recibo de outro endereço")
        return normalized

    def _active_credential(self, normalized: str) -> UserEmail | None:
        return self._session.scalar(
            select(UserEmail).where(
                UserEmail.email_normalized == normalized,
                UserEmail.released_at.is_(None),
            )
        )

    def _active_credentials(self, user_id: uuid.UUID) -> list[UserEmail]:
        return list(
            self._session.scalars(
                select(UserEmail).where(
                    UserEmail.user_id == user_id,
                    UserEmail.released_at.is_(None),
                )
            )
        )

    def _primary(self, user_id: uuid.UUID) -> UserEmail | None:
        return self._session.scalar(
            select(UserEmail).where(
                UserEmail.user_id == user_id,
                UserEmail.released_at.is_(None),
                UserEmail.is_primary.is_(True),
            )
        )

    def _old_primary(self, rows: list[UserEmail]) -> str | None:
        for row in rows:
            if row.is_primary:
                return row.email_normalized
        return rows[0].email_normalized if rows else None

    def _enforce_change_cooldown(self, user_id: uuid.UUID, moment: datetime) -> None:
        latest = self._session.scalar(
            select(func.max(UserEmail.released_at)).where(UserEmail.user_id == user_id)
        )
        if latest is None:
            return
        elapsed = (moment - ensure_utc(latest)).total_seconds()
        cooldown = self._change_cooldown.total_seconds()
        if elapsed < cooldown:
            raise EmailChangeCooldown(max(1, int(cooldown - elapsed)))


def _clean_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = CONTROL_PATTERN.sub(" ", value).strip()
    return cleaned[:60] or None


def _format_moment(moment: datetime) -> str:
    return moment.strftime("%d/%m/%Y %H:%M UTC")


__all__ = [
    "DisposableEmailDomain",
    "EmailAccountError",
    "EmailAccountService",
    "EmailAccountUser",
    "EmailAlreadyRegistered",
    "EmailChangeCooldown",
    "EmailChangeResult",
    "EmailUnchanged",
    "InvalidCredentials",
    "InvalidEmailReceipt",
    "InvalidPasswordReset",
]
