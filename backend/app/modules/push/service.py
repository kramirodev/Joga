"""Tokens de push e adaptador de envio."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.social.models import DevicePushToken

PLATFORMS = ("android", "ios", "web")


class PushError(Exception):
    """Falha de token ou de envio."""


class PushSender(Protocol):
    def send(self, *, token: str, title: str, body: str, data: dict[str, str]) -> None: ...


class RecordingPushSender:
    """Adaptador de teste que apenas registra os envios."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    def send(self, *, token: str, title: str, body: str, data: dict[str, str]) -> None:
        self.sent.append({"token": token, "title": title, "body": body, "data": data})


class PushService:
    def __init__(self, session: Session, sender: PushSender | None = None) -> None:
        self._session = session
        self._sender = sender

    def register_token(
        self,
        user_id: uuid.UUID,
        token: str,
        platform: str,
        *,
        now: datetime | None = None,
    ) -> DevicePushToken:
        if platform not in PLATFORMS:
            raise PushError("plataforma inválida")
        if not token.strip() or len(token) > 255:
            raise PushError("token inválido")
        moment = ensure_utc(now or utcnow())
        existing = self._session.scalar(
            select(DevicePushToken).where(DevicePushToken.token == token)
        )
        if existing is None:
            existing = DevicePushToken(
                user_id=user_id,
                token=token,
                platform=platform,
                created_at=moment,
                last_seen_at=moment,
            )
            self._session.add(existing)
        else:
            existing.user_id = user_id
            existing.platform = platform
            existing.last_seen_at = moment
            existing.revoked_at = None
        self._session.flush()
        return existing

    def revoke_token(self, user_id: uuid.UUID, token: str, *, now: datetime | None = None) -> None:
        row = self._session.scalar(
            select(DevicePushToken).where(
                DevicePushToken.user_id == user_id,
                DevicePushToken.token == token,
            )
        )
        if row is None:
            raise PushError("token não encontrado")
        row.revoked_at = ensure_utc(now or utcnow())
        self._session.flush()

    def send_to_user(
        self,
        user_id: uuid.UUID,
        *,
        title: str,
        body: str,
        data: dict[str, str],
    ) -> int:
        if self._sender is None:
            return 0
        tokens = list(
            self._session.scalars(
                select(DevicePushToken).where(
                    DevicePushToken.user_id == user_id,
                    DevicePushToken.revoked_at.is_(None),
                )
            )
        )
        for token in tokens:
            self._sender.send(token=token.token, title=title, body=body, data=data)
        return len(tokens)
