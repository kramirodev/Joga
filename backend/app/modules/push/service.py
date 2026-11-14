"""Tokens de push e adaptador de envio."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
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


class WebhookPushSender:
    """Envia o push para um worker/webhook externo.

    Não é um provedor APNs/FCM: é uma ponte operacional substituível. O worker
    externo decide como entregar e nunca é fonte de verdade do estado.
    """

    def __init__(self, url: str, *, timeout_seconds: int = 5) -> None:
        self.url = url
        self.client = httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        self.client.close()

    def send(self, *, token: str, title: str, body: str, data: dict[str, str]) -> None:
        try:
            response = self.client.post(
                self.url,
                json={"token": token, "title": title, "body": body, "data": data},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PushError("falha no webhook de push") from exc


def build_webhook_push_sender() -> WebhookPushSender | None:
    settings = get_settings()
    if not settings.push_webhook_url:
        return None
    return WebhookPushSender(
        settings.push_webhook_url,
        timeout_seconds=settings.push_timeout_seconds,
    )


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
