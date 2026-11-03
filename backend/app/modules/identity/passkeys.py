"""Serviço de passkeys WebAuthn (registro, autenticação e revogação)."""

from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.encoding import b64url_decode, b64url_encode
from app.modules.identity.models import PasskeyChallenge, PasskeyCredential, User

REGISTRATION = "registration"
AUTHENTICATION = "authentication"


class PasskeyError(Exception):
    """Erro base de passkeys."""


class PasskeyUserNotFound(PasskeyError):
    """Usuário inexistente ou inativo."""


class InvalidPasskeyChallenge(PasskeyError):
    """Desafio inexistente, consumido, expirado ou de outro usuário."""


class PasskeyVerificationFailed(PasskeyError):
    """Resposta WebAuthn inválida."""


class PasskeyAlreadyRegistered(PasskeyError):
    """Credential ID já registrado."""


class PasskeyNotFound(PasskeyError):
    """Credencial inexistente, revogada ou de outro usuário."""


class PasskeyRateLimited(PasskeyError):
    """Limite de desafios de passkey por IP por hora atingido."""


@dataclass(frozen=True)
class PasskeyOptions:
    challenge_id: uuid.UUID
    public_key: dict[str, Any]
    expires_at: datetime


@dataclass(frozen=True)
class PasskeyRegistration:
    credential_id: str
    name: str | None


@dataclass(frozen=True)
class PasskeyAuthentication:
    credential_id: str
    user_id: uuid.UUID


class PasskeyService:
    """Implementa o cerimonial WebAuthn com desafio de uso único."""

    def __init__(
        self,
        session: Session,
        *,
        rp_id: str,
        rp_name: str,
        origins: list[str],
        challenge_ttl_seconds: int = 300,
        max_per_ip_per_hour: int = 30,
    ) -> None:
        if not rp_id or not rp_name or not origins:
            raise ValueError("configuração WebAuthn incompleta")
        if challenge_ttl_seconds <= 0:
            raise ValueError("challenge_ttl_seconds deve ser positivo")
        if max_per_ip_per_hour <= 0:
            raise ValueError("max_per_ip_per_hour deve ser positivo")
        self._session = session
        self._rp_id = rp_id
        self._rp_name = rp_name
        self._origins = origins
        self._challenge_ttl = timedelta(seconds=challenge_ttl_seconds)
        self._max_per_ip_per_hour = max_per_ip_per_hour

    def begin_registration(
        self,
        user_id: uuid.UUID,
        *,
        name: str | None = None,
        now: datetime | None = None,
        request_ip_hash: str | None = None,
    ) -> PasskeyOptions:
        """Gera opções de registro e persiste o desafio."""
        user = self._session.get(User, user_id)
        if user is None or user.status != "active":
            raise PasskeyUserNotFound("usuário inválido")

        credentials = self._active_credentials(user_id)
        exclude = [
            PublicKeyCredentialDescriptor(id=b64url_decode(item.credential_id))
            for item in credentials
        ]
        options = generate_registration_options(
            rp_id=self._rp_id,
            rp_name=self._rp_name,
            user_id=user.id.bytes,
            user_name=f"user-{user.id}",
            user_display_name="JOGA",
            challenge=secrets.token_bytes(32),
            attestation=AttestationConveyancePreference.NONE,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            exclude_credentials=exclude,
        )
        moment = ensure_utc(now or utcnow())
        challenge = self._store_challenge(
            user_id=user_id,
            challenge=options.challenge,
            purpose=REGISTRATION,
            moment=moment,
            request_ip_hash=request_ip_hash,
        )
        return PasskeyOptions(
            challenge_id=challenge.id,
            public_key=json.loads(options_to_json(options)),
            expires_at=ensure_utc(challenge.expires_at),
        )

    def finish_registration(
        self,
        user_id: uuid.UUID,
        challenge_id: uuid.UUID,
        credential: dict[str, Any] | str,
        *,
        name: str | None = None,
        now: datetime | None = None,
    ) -> PasskeyRegistration:
        """Verifica a atestação e persiste a credencial pública."""
        moment = ensure_utc(now or utcnow())
        challenge = self._load_challenge(challenge_id, REGISTRATION, moment)
        if challenge.user_id != user_id:
            raise InvalidPasskeyChallenge("desafio de outro usuário")

        try:
            verified = verify_registration_response(
                credential=credential,
                expected_challenge=b64url_decode(challenge.challenge),
                expected_rp_id=self._rp_id,
                expected_origin=self._origins,
                require_user_verification=True,
            )
        except Exception as error:  # noqa: BLE001 - a biblioteca expõe erros variados
            raise PasskeyVerificationFailed("registro inválido") from error

        credential_id = b64url_encode(verified.credential_id)
        existing = self._session.scalar(
            select(PasskeyCredential).where(PasskeyCredential.credential_id == credential_id)
        )
        if existing is not None:
            raise PasskeyAlreadyRegistered("credencial já registrada")

        self._session.add(
            PasskeyCredential(
                user_id=user_id,
                credential_id=credential_id,
                public_key=verified.credential_public_key,
                sign_count=verified.sign_count,
                transports=_credential_transports(credential),
                name=name,
                created_at=moment,
            )
        )
        challenge.consumed_at = moment
        self._session.flush()

        return PasskeyRegistration(credential_id=credential_id, name=name)

    def begin_authentication(
        self,
        *,
        user_id: uuid.UUID | None = None,
        now: datetime | None = None,
        request_ip_hash: str | None = None,
    ) -> PasskeyOptions:
        """Gera opções de autenticação; sem usuário, usa credencial descobrível."""
        allow: list[PublicKeyCredentialDescriptor] = []
        if user_id is not None:
            user = self._session.get(User, user_id)
            if user is None or user.status != "active":
                raise PasskeyUserNotFound("usuário inválido")
            allow = [
                PublicKeyCredentialDescriptor(id=b64url_decode(item.credential_id))
                for item in self._active_credentials(user_id)
            ]

        options = generate_authentication_options(
            rp_id=self._rp_id,
            challenge=secrets.token_bytes(32),
            allow_credentials=allow,
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        moment = ensure_utc(now or utcnow())
        challenge = self._store_challenge(
            user_id=user_id,
            challenge=options.challenge,
            purpose=AUTHENTICATION,
            moment=moment,
            request_ip_hash=request_ip_hash,
        )
        return PasskeyOptions(
            challenge_id=challenge.id,
            public_key=json.loads(options_to_json(options)),
            expires_at=ensure_utc(challenge.expires_at),
        )

    def finish_authentication(
        self,
        challenge_id: uuid.UUID,
        credential: dict[str, Any] | str,
        *,
        now: datetime | None = None,
    ) -> PasskeyAuthentication:
        """Verifica a asserção e devolve o usuário da credencial."""
        moment = ensure_utc(now or utcnow())
        challenge = self._load_challenge(challenge_id, AUTHENTICATION, moment)
        payload = _credential_payload(credential)
        credential_id = payload.get("id") or payload.get("rawId")
        if not isinstance(credential_id, str) or not credential_id:
            raise PasskeyVerificationFailed("credencial sem id")

        stored = self._session.scalar(
            select(PasskeyCredential).where(
                PasskeyCredential.credential_id == credential_id,
                PasskeyCredential.revoked_at.is_(None),
            )
        )
        if stored is None:
            raise PasskeyNotFound("credencial não encontrada")
        if challenge.user_id is not None and challenge.user_id != stored.user_id:
            raise InvalidPasskeyChallenge("credencial de outro usuário")

        user = self._session.get(User, stored.user_id)
        if user is None or user.status != "active":
            raise PasskeyUserNotFound("usuário inválido")

        try:
            verified = verify_authentication_response(
                credential=credential,
                expected_challenge=b64url_decode(challenge.challenge),
                expected_rp_id=self._rp_id,
                expected_origin=self._origins,
                credential_public_key=stored.public_key,
                credential_current_sign_count=stored.sign_count,
                require_user_verification=True,
            )
        except Exception as error:  # noqa: BLE001 - a biblioteca expõe erros variados
            raise PasskeyVerificationFailed("autenticação inválida") from error

        if stored.sign_count > 0 and verified.new_sign_count <= stored.sign_count:
            raise PasskeyVerificationFailed("contador de assinatura inválido")

        stored.sign_count = verified.new_sign_count
        stored.last_used_at = moment
        challenge.consumed_at = moment
        self._session.flush()

        return PasskeyAuthentication(credential_id=credential_id, user_id=stored.user_id)

    def list_credentials(self, user_id: uuid.UUID) -> list[PasskeyCredential]:
        return self._active_credentials(user_id)

    def revoke_credential(self, user_id: uuid.UUID, credential_id: str) -> None:
        stored = self._session.scalar(
            select(PasskeyCredential).where(
                PasskeyCredential.credential_id == credential_id,
                PasskeyCredential.user_id == user_id,
            )
        )
        if stored is None:
            raise PasskeyNotFound("credencial não encontrada")
        if stored.revoked_at is None:
            stored.revoked_at = utcnow()
            self._session.flush()

    def _active_credentials(self, user_id: uuid.UUID) -> list[PasskeyCredential]:
        return list(
            self._session.scalars(
                select(PasskeyCredential)
                .where(
                    PasskeyCredential.user_id == user_id,
                    PasskeyCredential.revoked_at.is_(None),
                )
                .order_by(PasskeyCredential.created_at)
            )
        )

    def _store_challenge(
        self,
        *,
        user_id: uuid.UUID | None,
        challenge: bytes,
        purpose: str,
        moment: datetime,
        request_ip_hash: str | None,
    ) -> PasskeyChallenge:
        if request_ip_hash is not None:
            since = moment - timedelta(hours=1)
            recent = self._session.scalar(
                select(func.count())
                .select_from(PasskeyChallenge)
                .where(
                    PasskeyChallenge.request_ip_hash == request_ip_hash,
                    PasskeyChallenge.created_at >= since,
                )
            )
            if (recent or 0) >= self._max_per_ip_per_hour:
                raise PasskeyRateLimited("limite de desafios de passkey por IP")

        row = PasskeyChallenge(
            user_id=user_id,
            challenge=b64url_encode(challenge),
            purpose=purpose,
            expires_at=moment + self._challenge_ttl,
            request_ip_hash=request_ip_hash,
            created_at=moment,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def _load_challenge(
        self,
        challenge_id: uuid.UUID,
        purpose: str,
        moment: datetime,
    ) -> PasskeyChallenge:
        challenge = self._session.get(
            PasskeyChallenge,
            challenge_id,
            with_for_update=True,
        )
        if challenge is None or challenge.purpose != purpose:
            raise InvalidPasskeyChallenge("desafio inválido")
        if challenge.consumed_at is not None:
            raise InvalidPasskeyChallenge("desafio já utilizado")
        if ensure_utc(challenge.expires_at) <= moment:
            raise InvalidPasskeyChallenge("desafio expirado")
        return challenge


def _credential_payload(credential: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(credential, str):
        try:
            payload = json.loads(credential)
        except json.JSONDecodeError as error:
            raise PasskeyVerificationFailed("credencial não é JSON") from error
    else:
        payload = credential
    if not isinstance(payload, dict):
        raise PasskeyVerificationFailed("credencial inválida")
    return payload


def _credential_transports(credential: dict[str, Any] | str) -> list[str] | None:
    payload = _credential_payload(credential)
    response = payload.get("response")
    if not isinstance(response, dict):
        return None
    transports = response.get("transports")
    if isinstance(transports, list) and all(isinstance(item, str) for item in transports):
        return transports
    return None
