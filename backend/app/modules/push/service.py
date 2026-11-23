"""Tokens de push e contrato dos adaptadores de envio.

O push é transporte best-effort: a central de notificações continua sendo a
fonte de verdade. O adaptador devolve um ``PushTicket`` por token para que o
dispatcher possa revogar dispositivos que o provedor declarou inválidos sem
confundir isso com uma falha temporária de rede.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.social.models import DevicePushToken

PLATFORMS = ("android", "ios", "web")

# Erros de ticket que significam "este token não deve mais receber push".
# ``DeviceNotRegistered`` é o caso normal (app desinstalado/token rotacionado);
# ``InvalidPushToken`` cobre token malformado que nunca vai funcionar.
REVOKE_TICKET_ERRORS = frozenset({"DeviceNotRegistered", "InvalidPushToken"})


class PushError(Exception):
    """Falha de token ou de envio.

    A mensagem é sempre um código interno seguro (nunca corpo do provedor nem
    token do dispositivo) e pode ir para ``outbox_events.last_error``.
    """


@dataclass(frozen=True)
class PushMessage:
    """Mensagem já renderizada para um único dispositivo."""

    token: str
    title: str
    body: str
    data: dict[str, str]
    channel_id: str | None = None


@dataclass(frozen=True)
class PushTicket:
    """Resultado do provedor para um token."""

    token: str
    ok: bool
    error: str | None = None
    ticket_id: str | None = None

    @property
    def should_revoke(self) -> bool:
        return self.error in REVOKE_TICKET_ERRORS


class PushSender(Protocol):
    """Contrato mínimo de um provedor de push."""

    def send_batch(self, messages: Sequence[PushMessage]) -> list[PushTicket]: ...

    def close(self) -> None: ...


class RecordingPushSender:
    """Adaptador de teste que apenas registra os envios.

    ``errors`` permite simular tickets de erro por token sem abrir socket.
    """

    def __init__(self, *, errors: Mapping[str, str] | None = None) -> None:
        self.sent: list[dict[str, object]] = []
        self._errors = dict(errors or {})

    def send_batch(self, messages: Sequence[PushMessage]) -> list[PushTicket]:
        tickets: list[PushTicket] = []
        for index, message in enumerate(messages):
            self.sent.append(
                {
                    "token": message.token,
                    "title": message.title,
                    "body": message.body,
                    "data": message.data,
                }
            )
            error = self._errors.get(message.token)
            tickets.append(
                PushTicket(
                    token=message.token,
                    ok=error is None,
                    error=error,
                    ticket_id=None if error is not None else f"ticket-{index}",
                )
            )
        return tickets

    def close(self) -> None:
        return None


class WebhookPushSender:
    """Envia o push para um worker/webhook externo.

    Não é um provedor APNs/FCM: é uma ponte operacional substituível. O worker
    externo decide como entregar e nunca é fonte de verdade do estado.
    """

    def __init__(self, url: str, *, timeout_seconds: int = 5) -> None:
        self.url = url
        self.client = httpx.Client(timeout=timeout_seconds, trust_env=False)

    def close(self) -> None:
        self.client.close()

    def send_batch(self, messages: Sequence[PushMessage]) -> list[PushTicket]:
        tickets: list[PushTicket] = []
        for message in messages:
            try:
                response = self.client.post(
                    self.url,
                    json={
                        "token": message.token,
                        "title": message.title,
                        "body": message.body,
                        "data": message.data,
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise PushError("push_webhook_failed") from exc
            tickets.append(PushTicket(token=message.token, ok=True))
        return tickets


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

    def active_tokens(self, user_id: uuid.UUID) -> list[DevicePushToken]:
        return list(
            self._session.scalars(
                select(DevicePushToken)
                .where(
                    DevicePushToken.user_id == user_id,
                    DevicePushToken.revoked_at.is_(None),
                )
                .order_by(DevicePushToken.created_at, DevicePushToken.id)
            )
        )

    def message_for(
        self,
        token: DevicePushToken,
        *,
        title: str,
        body: str,
        data: dict[str, str],
        channel_id: str | None = None,
    ) -> PushMessage:
        return PushMessage(
            token=token.token,
            title=title,
            body=body,
            data=data,
            channel_id=channel_id,
        )

    def send_to_user(
        self,
        user_id: uuid.UUID,
        *,
        title: str,
        body: str,
        data: dict[str, str],
        channel_id: str | None = None,
        now: datetime | None = None,
    ) -> list[PushTicket]:
        """Envia para todos os tokens ativos e revoga os que o provedor recusou."""
        if self._sender is None:
            return []
        messages = [
            self.message_for(token, title=title, body=body, data=data, channel_id=channel_id)
            for token in self.active_tokens(user_id)
        ]
        if not messages:
            return []
        tickets = self._sender.send_batch(messages)
        self.revoke_unregistered(tickets, now=now)
        return tickets

    def revoke_unregistered(
        self,
        tickets: Sequence[PushTicket],
        *,
        now: datetime | None = None,
    ) -> int:
        """Revoga tokens cujo ticket é definitivo (não é falha temporária)."""
        doomed = {ticket.token for ticket in tickets if ticket.should_revoke}
        if not doomed:
            return 0
        moment = ensure_utc(now or utcnow())
        rows = list(
            self._session.scalars(
                select(DevicePushToken).where(
                    DevicePushToken.token.in_(doomed),
                    DevicePushToken.revoked_at.is_(None),
                )
            )
        )
        for row in rows:
            row.revoked_at = moment
        if rows:
            self._session.flush()
        return len(rows)


__all__ = [
    "PLATFORMS",
    "REVOKE_TICKET_ERRORS",
    "PushError",
    "PushMessage",
    "PushSender",
    "PushService",
    "PushTicket",
    "RecordingPushSender",
    "WebhookPushSender",
    "build_webhook_push_sender",
]
