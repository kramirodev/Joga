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


class RefreshRetryRequired(SessionError):
    """Reuso do refresh imediatamente anterior dentro da janela de tolerância.

    Corrida legítima (duas chamadas concorrentes com o mesmo refresh): a
    família não é revogada e nenhum token é emitido. O cliente deve reler o
    par mais recente - entregue pela chamada concorrente que venceu - e repetir
    a operação. Emitir um par novo aqui invalidaria a resposta vencedora e
    permitiria que um token roubado obtivesse sessão nova dentro da janela.
    """

    def __init__(self, user_id: uuid.UUID, *, age_seconds: int) -> None:
        super().__init__("refresh token rotacionado recentemente; repetir com o mais novo")
        self.user_id = user_id
        self.age_seconds = age_seconds


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


_REUSE_REVOKE_REASON = "refresh_reuse"
_GRACE_MAX_SECONDS = 300


class SessionService:
    """Emite, valida e revoga sessões; tokens são persistidos só como HMAC."""

    def __init__(
        self,
        session: Session,
        secret: str,
        *,
        access_ttl_seconds: int = 600,
        refresh_absolute_ttl_days: int = 180,
        refresh_idle_ttl_days: int = 30,
        refresh_reuse_grace_seconds: int = 30,
    ) -> None:
        if not secret:
            raise ValueError("segredo de token não pode ser vazio")
        if access_ttl_seconds <= 0:
            raise ValueError("access_ttl_seconds deve ser positivo")
        if refresh_absolute_ttl_days <= 0 or refresh_idle_ttl_days <= 0:
            raise ValueError("TTLs de refresh devem ser positivos")
        if not 0 <= refresh_reuse_grace_seconds <= _GRACE_MAX_SECONDS:
            raise ValueError("refresh_reuse_grace_seconds deve estar entre 0 e 300")
        self._session = session
        self._secret = secret
        self._access_ttl = timedelta(seconds=access_ttl_seconds)
        self._refresh_absolute_ttl = timedelta(days=refresh_absolute_ttl_days)
        self._refresh_idle_ttl = timedelta(days=refresh_idle_ttl_days)
        self._refresh_reuse_grace = timedelta(seconds=refresh_reuse_grace_seconds)

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
        require_active: bool = True,
    ) -> AuthenticatedSession:
        """Valida o access token e devolve a sessão ativa.

        ``require_active=False`` permite que contas suspensas acessem apenas
        recursos de contestação da própria medida (ex.: recurso de moderação).
        """
        moment = ensure_utc(now or utcnow())
        token_hash = hash_token(access_token, self._secret, "access")
        conditions = [
            SessionRecord.access_token_hash == token_hash,
            SessionRecord.revoked_at.is_(None),
        ]
        if require_active:
            conditions.append(User.status == "active")
        row = self._session.scalar(
            select(SessionRecord).join(User, User.id == SessionRecord.user_id).where(*conditions)
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
        """Rotaciona o refresh e trata reutilização.

        Reutilizar o token imediatamente anterior dentro da janela de
        tolerância indica corrida no cliente e apenas exige nova tentativa
        (``RefreshRetryRequired``), sem revogar a família. Fora da janela, ou
        reutilizando token mais antigo, a família é revogada
        (``RefreshReuseDetected``).
        """
        token_hash = hash_token(refresh_token, self._secret, "refresh")
        row = self._session.scalar(
            select(SessionRecord)
            .where(SessionRecord.refresh_token_hash == token_hash)
            .with_for_update()
        )
        # Capturado depois do lock: na corrida, quem perde o lock precisa de um
        # instante igual ou posterior ao da rotação vencedora.
        moment = ensure_utc(now or utcnow())
        if row is None:
            raise InvalidRefreshToken("refresh token inválido")

        if row.replaced_by_session_id is not None:
            age_seconds = self._grace_reuse_age(row, moment)
            if age_seconds is not None:
                raise RefreshRetryRequired(row.user_id, age_seconds=age_seconds)
            self._revoke_family(row.family_id, moment, _REUSE_REVOKE_REASON)
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

    def revoke_others(
        self,
        user_id: uuid.UUID,
        *,
        keep_session_id: uuid.UUID,
        reason: str = "credential_change",
        now: datetime | None = None,
    ) -> int:
        """Revoga as demais sessões do usuário, preservando a atual."""
        moment = ensure_utc(now or utcnow())
        rows = self._session.scalars(
            select(SessionRecord).where(
                SessionRecord.user_id == user_id,
                SessionRecord.revoked_at.is_(None),
                SessionRecord.id != keep_session_id,
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

    def _grace_reuse_age(self, row: SessionRecord, moment: datetime) -> int | None:
        """Devolve a idade do token substituído se o reuso é tolerável.

        Só vale para o token imediatamente anterior ao topo da família, dentro
        da janela configurada, com a família ainda ativa e sem reuso suspeito
        registrado. Inconsistências falham fechado (``None``), levando ao
        comportamento de revogação da família. Desvio pequeno de relógio entre
        instâncias (rotação aparentemente no futuro) é tratado como idade zero.
        """
        if self._refresh_reuse_grace <= timedelta(0):
            return None
        if row.revoked_at is None or row.revoked_reason != "rotated":
            return None

        age = moment - ensure_utc(row.revoked_at)
        if age < timedelta(0):
            if -age >= self._refresh_reuse_grace:
                return None
            age = timedelta(0)
        if age >= self._refresh_reuse_grace:
            return None

        replacement_id = row.replaced_by_session_id
        if replacement_id is None:
            return None
        successor = self._session.get(SessionRecord, replacement_id, populate_existing=True)
        if successor is None or successor.revoked_at is not None:
            return None
        if successor.replaced_by_session_id is not None:
            # Já houve outra rotação: o token apresentado não é o penúltimo.
            return None

        suspicious = self._session.scalar(
            select(SessionRecord.id)
            .where(
                SessionRecord.family_id == row.family_id,
                SessionRecord.revoked_reason == _REUSE_REVOKE_REASON,
            )
            .limit(1)
        )
        if suspicious is not None:
            return None

        return int(age.total_seconds())
