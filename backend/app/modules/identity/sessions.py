"""Sessões com access/refresh opacos, rotação e revogação por família."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import Session as SessionRecord
from app.modules.identity.models import User
from app.modules.identity.tokens import generate_token, hash_token


class SessionError(Exception):
    """Erro base de sessão."""


class InvalidAccessToken(SessionError):
    """Access token ausente, expirado, revogado ou desconhecido."""


class InvalidRefreshToken(SessionError):
    """Refresh token expirado, revogado ou desconhecido."""


class RefreshReuseDetected(SessionError):
    """Refresh já rotacionado reutilizado; a família foi revogada."""

    def __init__(self, user_id: uuid.UUID) -> None:
        super().__init__("refresh token reutilizado")
        self.user_id = user_id


@dataclass(frozen=True)
class AuthenticatedSession:
    session_id: uuid.UUID
    user_id: uuid.UUID
    family_id: uuid.UUID
    expires_at: datetime


@dataclass(frozen=True)
class IssuedTokens:
    session_id: uuid.UUID
    user_id: uuid.UUID
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class SessionService:
    """Emite, valida e revoga sessões; tokens são persistidos só como HMAC."""

    def __init__(
        self,
        session: Session,
        secret: str,
        *,
        access_ttl_seconds: int = 600,
        refresh_absolute_ttl_days: int = 30,
        refresh_idle_ttl_days: int = 7,
    ) -> None:
        if not secret:
            raise ValueError("segredo de token não pode ser vazio")
        if access_ttl_seconds <= 0:
            raise ValueError("access_ttl_seconds deve ser positivo")
        if refresh_absolute_ttl_days <= 0 or refresh_idle_ttl_days <= 0:
            raise ValueError("TTLs de refresh devem ser positivos")
        self._session = session
        self._secret = secret
        self._access_ttl = timedelta(seconds=access_ttl_seconds)
        self._refresh_absolute_ttl = timedelta(days=refresh_absolute_ttl_days)
        self._refresh_idle_ttl = timedelta(days=refresh_idle_ttl_days)

    def issue(
        self,
        user_id: uuid.UUID,
        *,
        device_id: uuid.UUID | None = None,
        now: datetime | None = None,
        family_id: uuid.UUID | None = None,
        absolute_expires_at: datetime | None = None,
    ) -> IssuedTokens:
        """Cria uma sessão e devolve tokens em claro (única vez)."""
        moment = ensure_utc(now or utcnow())
        access_token = generate_token()
        refresh_token = generate_token()
        session_id = uuid.uuid4()
        resolved_family = family_id or uuid.uuid4()
        resolved_absolute = (
            ensure_utc(absolute_expires_at)
            if absolute_expires_at is not None
            else moment + self._refresh_absolute_ttl
        )
        access_expires_at = moment + self._access_ttl
        idle_expires_at = moment + self._refresh_idle_ttl

        self._session.add(
            SessionRecord(
                id=session_id,
                user_id=user_id,
                device_id=device_id,
                family_id=resolved_family,
                access_token_hash=hash_token(access_token, self._secret, "access"),
                access_expires_at=access_expires_at,
                refresh_token_hash=hash_token(refresh_token, self._secret, "refresh"),
                created_at=moment,
                expires_at=resolved_absolute,
                idle_expires_at=idle_expires_at,
            )
        )
        self._session.flush()

        return IssuedTokens(
            session_id=session_id,
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_expires_at,
            refresh_expires_at=resolved_absolute,
        )

    def authenticate(
        self,
        access_token: str,
        *,
        now: datetime | None = None,
    ) -> AuthenticatedSession:
        """Valida o access token e devolve a sessão ativa."""
        moment = ensure_utc(now or utcnow())
        token_hash = hash_token(access_token, self._secret, "access")
        row = self._session.scalar(
            select(SessionRecord)
            .join(User, User.id == SessionRecord.user_id)
            .where(
                SessionRecord.access_token_hash == token_hash,
                SessionRecord.revoked_at.is_(None),
                User.status == "active",
            )
        )
        if row is None or ensure_utc(row.access_expires_at) <= moment:
            raise InvalidAccessToken("access token inválido")

        return AuthenticatedSession(
            session_id=row.id,
            user_id=row.user_id,
            family_id=row.family_id,
            expires_at=ensure_utc(row.expires_at),
        )

    def rotate(
        self,
        refresh_token: str,
        *,
        now: datetime | None = None,
    ) -> IssuedTokens:
        """Rotaciona o refresh; reutilização revoga a família inteira."""
        moment = ensure_utc(now or utcnow())
        token_hash = hash_token(refresh_token, self._secret, "refresh")
        row = self._session.scalar(
            select(SessionRecord)
            .where(SessionRecord.refresh_token_hash == token_hash)
            .with_for_update()
        )
        if row is None:
            raise InvalidRefreshToken("refresh token inválido")

        if row.replaced_by_session_id is not None:
            self._revoke_family(row.family_id, moment, "refresh_reuse")
            raise RefreshReuseDetected(row.user_id)

        if row.revoked_at is not None:
            raise InvalidRefreshToken("refresh token revogado")

        if ensure_utc(row.expires_at) <= moment or ensure_utc(row.idle_expires_at) <= moment:
            row.revoked_at = moment
            row.revoked_reason = "expired"
            self._session.flush()
            raise InvalidRefreshToken("refresh token expirado")

        issued = self.issue(
            row.user_id,
            device_id=row.device_id,
            now=moment,
            family_id=row.family_id,
            absolute_expires_at=row.expires_at,
        )
        row.revoked_at = moment
        row.revoked_reason = "rotated"
        row.replaced_by_session_id = issued.session_id
        self._session.flush()
        return issued

    def revoke_session(
        self,
        session_id: uuid.UUID,
        *,
        reason: str = "logout",
        now: datetime | None = None,
    ) -> None:
        """Revoga uma sessão específica (logout)."""
        row = self._session.get(SessionRecord, session_id)
        if row is None or row.revoked_at is not None:
            return
        row.revoked_at = ensure_utc(now or utcnow())
        row.revoked_reason = reason
        self._session.flush()

    def revoke_by_refresh(
        self,
        refresh_token: str,
        *,
        reason: str = "web_logout",
        now: datetime | None = None,
    ) -> uuid.UUID | None:
        """Revoga a sessão associada ao refresh sem rotacionar o token.

        Usado pelo logout do painel web, em que o refresh fica apenas em cookie
        HttpOnly. Devolve o usuário da sessão, quando encontrado.
        """

        token_hash = hash_token(refresh_token, self._secret, "refresh")
        row = self._session.scalar(
            select(SessionRecord)
            .where(SessionRecord.refresh_token_hash == token_hash)
            .with_for_update()
        )
        if row is None:
            return None
        if row.revoked_at is None:
            row.revoked_at = ensure_utc(now or utcnow())
            row.revoked_reason = reason
            self._session.flush()
        return row.user_id

    def revoke_all(
        self,
        user_id: uuid.UUID,
        *,
        reason: str = "logout_all",
        now: datetime | None = None,
    ) -> int:
        """Revoga todas as sessões ativas do usuário."""
        moment = ensure_utc(now or utcnow())
        rows = self._session.scalars(
            select(SessionRecord).where(
                SessionRecord.user_id == user_id,
                SessionRecord.revoked_at.is_(None),
            )
        )
        count = 0
        for row in rows:
            row.revoked_at = moment
            row.revoked_reason = reason
            count += 1
        self._session.flush()
        return count

    def _revoke_family(self, family_id: uuid.UUID, moment: datetime, reason: str) -> None:
        rows = self._session.scalars(
            select(SessionRecord).where(
                SessionRecord.family_id == family_id,
                SessionRecord.revoked_at.is_(None),
            )
        )
        for row in rows:
            row.revoked_at = moment
            row.revoked_reason = reason
        self._session.flush()
