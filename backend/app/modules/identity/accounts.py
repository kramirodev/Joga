"""Consumo do recibo de verificação para cadastro e login."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import PhoneChallenge, User, UserPhone
from app.modules.identity.otp import ChallengePurpose


class AccountError(Exception):
    """Erro base do fluxo de conta."""


class InvalidReceipt(AccountError):
    """Recibo inexistente, expirado, já usado ou de finalidade errada."""


class PhoneAlreadyRegistered(AccountError):
    """Telefone já vinculado a uma conta ativa."""


class AccountNotFound(AccountError):
    """Telefone verificado, mas sem conta ativa."""


@dataclass(frozen=True)
class AccountUser:
    id: uuid.UUID
    status: str


class AccountService:
    """Cria conta ou autentica usuário a partir de um recibo de telefone."""

    def __init__(self, session: Session, receipt_ttl_seconds: int = 600) -> None:
        if receipt_ttl_seconds <= 0:
            raise ValueError("receipt_ttl_seconds deve ser positivo")
        self._session = session
        self._receipt_ttl = timedelta(seconds=receipt_ttl_seconds)

    def register(
        self,
        challenge_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> AccountUser:
        """Consome um recibo de registro e cria usuário + telefone verificado."""
        moment = ensure_utc(now or utcnow())
        challenge = self._load_receipt(challenge_id, ChallengePurpose.registration, moment)

        existing = self._session.scalar(
            select(UserPhone).where(
                UserPhone.phone_hash == challenge.phone_hash,
                UserPhone.released_at.is_(None),
            )
        )
        if existing is not None:
            raise PhoneAlreadyRegistered("telefone já cadastrado")

        user = User(status="active")
        self._session.add(user)
        self._session.flush()

        self._session.add(
            UserPhone(
                user_id=user.id,
                phone_hash=challenge.phone_hash,
                is_primary=True,
                verified_at=ensure_utc(challenge.consumed_at)
                if challenge.consumed_at is not None
                else moment,
            )
        )
        challenge.receipt_used_at = moment
        self._session.flush()

        return AccountUser(id=user.id, status=user.status)

    def login(
        self,
        challenge_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> AccountUser:
        """Consome um recibo de login e devolve a conta ativa do telefone."""
        moment = ensure_utc(now or utcnow())
        challenge = self._load_receipt(challenge_id, ChallengePurpose.login, moment)

        user = self._session.scalar(
            select(User)
            .join(UserPhone, UserPhone.user_id == User.id)
            .where(
                UserPhone.phone_hash == challenge.phone_hash,
                UserPhone.released_at.is_(None),
                User.status == "active",
            )
        )
        if user is None:
            raise AccountNotFound("conta não encontrada")

        challenge.receipt_used_at = moment
        self._session.flush()

        return AccountUser(id=user.id, status=user.status)

    def _load_receipt(
        self,
        challenge_id: uuid.UUID,
        purpose: ChallengePurpose,
        moment: datetime,
    ) -> PhoneChallenge:
        challenge = self._session.get(PhoneChallenge, challenge_id, with_for_update=True)
        if challenge is None or challenge.consumed_at is None:
            raise InvalidReceipt("recibo inválido")
        if challenge.receipt_used_at is not None:
            raise InvalidReceipt("recibo já utilizado")
        if ChallengePurpose(challenge.purpose) is not purpose:
            raise InvalidReceipt("finalidade do recibo não confere")

        consumed_at = ensure_utc(challenge.consumed_at)
        if consumed_at + self._receipt_ttl <= moment:
            raise InvalidReceipt("recibo expirado")

        return challenge
