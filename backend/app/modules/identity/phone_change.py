"""Troca de telefone autenticada com verificação OTP no novo número."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import PhoneChallenge, UserPhone
from app.modules.identity.otp import (
    ChallengePurpose,
    IssuedChallenge,
    PhoneChallengeService,
)
from app.modules.identity.phone import hash_phone, normalize_phone


class PhoneChangeError(Exception):
    """Erro base da troca de telefone."""


class PhoneUnchanged(PhoneChangeError):
    """O novo telefone é igual ao atual."""


class PhoneAlreadyRegistered(PhoneChangeError):
    """O novo telefone já pertence a uma conta ativa."""


class InvalidPhoneChange(PhoneChangeError):
    """Desafio inválido, de outra conta ou de outra finalidade."""


@dataclass(frozen=True)
class PhoneChangeResult:
    user_id: uuid.UUID
    new_phone_hash: str


class PhoneChangeService:
    """Solicita e confirma a troca de telefone de um usuário autenticado."""

    def __init__(
        self,
        session: Session,
        challenges: PhoneChallengeService,
        phone_secret: str,
    ) -> None:
        if not phone_secret:
            raise ValueError("segredo de telefone não pode ser vazio")
        self._session = session
        self._challenges = challenges
        self._secret = phone_secret

    def request(
        self,
        user_id: uuid.UUID,
        new_phone: str,
        *,
        now: datetime | None = None,
        request_ip: str | None = None,
    ) -> IssuedChallenge:
        """Cria desafio para o novo número; não altera o telefone ainda."""
        normalized = normalize_phone(new_phone)
        new_hash = hash_phone(normalized, self._secret)

        current = self._session.scalar(
            select(UserPhone).where(
                UserPhone.user_id == user_id,
                UserPhone.released_at.is_(None),
            )
        )
        if current is not None and current.phone_hash == new_hash:
            raise PhoneUnchanged("telefone novo é igual ao atual")

        other = self._session.scalar(
            select(UserPhone).where(
                UserPhone.phone_hash == new_hash,
                UserPhone.released_at.is_(None),
            )
        )
        if other is not None:
            raise PhoneAlreadyRegistered("telefone já cadastrado")

        return self._challenges.request(
            normalized,
            ChallengePurpose.phone_change,
            now=now,
            request_ip=request_ip,
            user_id=user_id,
        )

    def confirm(
        self,
        user_id: uuid.UUID,
        challenge_id: uuid.UUID,
        code: str,
        *,
        now: datetime | None = None,
    ) -> PhoneChangeResult:
        """Verifica o OTP, troca o telefone e marca o recibo como usado."""
        challenge = self._session.get(PhoneChallenge, challenge_id, with_for_update=True)
        if (
            challenge is None
            or challenge.user_id != user_id
            or challenge.purpose != ChallengePurpose.phone_change.value
        ):
            raise InvalidPhoneChange("desafio de troca inválido")

        verified = self._challenges.verify(challenge_id, code, now=now)
        moment = ensure_utc(now or utcnow())

        active = self._session.scalar(
            select(UserPhone).where(
                UserPhone.phone_hash == verified.phone_hash,
                UserPhone.released_at.is_(None),
            )
        )
        if active is not None:
            if active.user_id == user_id:
                raise PhoneUnchanged("telefone novo é igual ao atual")
            raise PhoneAlreadyRegistered("telefone já cadastrado")

        self._session.execute(
            update(UserPhone)
            .where(
                UserPhone.user_id == user_id,
                UserPhone.released_at.is_(None),
            )
            .values(released_at=moment, is_primary=False)
        )
        self._session.add(
            UserPhone(
                user_id=user_id,
                phone_hash=verified.phone_hash,
                is_primary=True,
                verified_at=verified.verified_at,
            )
        )
        challenge.receipt_used_at = moment

        try:
            self._session.flush()
        except IntegrityError as error:
            self._session.rollback()
            raise PhoneAlreadyRegistered("telefone já cadastrado") from error

        return PhoneChangeResult(
            user_id=user_id,
            new_phone_hash=verified.phone_hash,
        )
