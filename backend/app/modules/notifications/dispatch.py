"""Dispatcher de notificações da Outbox para push e WebSocket (Fase 13E/1.8)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.modules.outbox.service import OutboxService
from app.modules.push.service import PushError, PushMessage, PushSender, PushService
from app.modules.realtime.notifications import notification_event_payload

logger = logging.getLogger("joga.notifications")

# Notificações internas do painel não usam o push do app do jogador.
MODERATION_KINDS = frozenset({"moderation_report", "moderation_appeal"})

# Uma falha temporária (rede/5xx/429) volta para a Outbox com atraso. Sem isso,
# o ciclo seguinte selecionaria o mesmo evento imediatamente (loop apertado).
DEFAULT_RETRY_SECONDS = 60

NotificationPublisher = Callable[[uuid.UUID, dict[str, Any]], int]


@dataclass
class DispatchReport:
    """Contadores de um ciclo; nunca contém PII nem token."""

    processed: int = 0
    delivered: int = 0
    skipped: int = 0
    no_tokens: int = 0
    failed: int = 0
    revoked: int = 0
    published: int = 0


def _user_id(value: object) -> uuid.UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _string_data(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def dispatch_notifications(
    session: Session,
    sender: PushSender | None,
    *,
    publisher: NotificationPublisher | None = None,
    limit: int = 100,
    retry_in_seconds: int = DEFAULT_RETRY_SECONDS,
    now: datetime | None = None,
) -> DispatchReport:
    """Envia ``notification.created`` pendentes e marca a Outbox.

    - Sem sender configurado, nada é alterado: o worker não finge entrega.
    - Sem token ativo, o evento fica ``FAILED`` com ``no_active_tokens`` e só
      volta a ser elegível depois de ``retry_in_seconds``.
    - ``moderation`` é interna ao painel: não gera push nem WebSocket do app.
    - Publicar no WebSocket é best-effort e nunca impede a marcação da Outbox.
    """

    report = DispatchReport()
    if sender is None:
        return report

    outbox = OutboxService(session)
    push = PushService(session, sender)
    for event in outbox.pending(limit=limit, now=now):
        if event.event_type != "notification.created":
            continue
        report.processed += 1
        payload = event.payload or {}
        user_id = _user_id(payload.get("user_id"))
        if user_id is None:
            outbox.mark_failed(event, "invalid_payload", now=now)
            report.failed += 1
            continue

        kind = str(payload.get("kind") or "")
        if payload.get("channel") == "moderation" or kind in MODERATION_KINDS:
            outbox.mark_dispatched(event, now=now)
            report.skipped += 1
            continue

        title = str(payload.get("title") or "JOGA")
        body = str(payload.get("body") or "")
        data = _string_data(payload.get("data"))

        # Tempo real não depende de push: o app conectado recebe mesmo quando
        # não há token registrado. O histórico é a fonte de verdade. O evento
        # só é publicado na primeira tentativa: retries da Outbox não podem
        # duplicar a notificação no app.
        if publisher is not None and event.attempts == 0:
            notification_id = payload.get("notification_id")
            if notification_id is None:
                notification_id = event.aggregate_id
            ws_payload = notification_event_payload(
                notification_id=notification_id,
                kind=kind,
                title=title,
                body=body,
                data=data,
            )
            try:
                report.published += publisher(user_id, ws_payload)
            except Exception:
                logger.warning(
                    "notificações: falha ao publicar evento em tempo real",
                    exc_info=True,
                )

        tokens = push.active_tokens(user_id)
        if not tokens:
            outbox.mark_failed(
                event,
                "no_active_tokens",
                now=now,
                retry_in_seconds=retry_in_seconds,
            )
            report.no_tokens += 1
            continue

        messages = [
            PushMessage(
                token=token.token,
                title=title,
                body=body,
                data=data,
            )
            for token in tokens
        ]
        try:
            tickets = sender.send_batch(messages)
        except PushError as exc:
            outbox.mark_failed(
                event,
                str(exc),
                now=now,
                retry_in_seconds=retry_in_seconds,
            )
            report.failed += 1
            continue

        report.revoked += push.revoke_unregistered(tickets, now=now)
        if any(ticket.ok for ticket in tickets):
            outbox.mark_dispatched(event, now=now)
            report.delivered += 1
            continue
        error = next((ticket.error for ticket in tickets if ticket.error), "push_error")
        outbox.mark_failed(event, error, now=now, retry_in_seconds=retry_in_seconds)
        report.failed += 1

    session.flush()
    return report


__all__ = [
    "DEFAULT_RETRY_SECONDS",
    "MODERATION_KINDS",
    "DispatchReport",
    "NotificationPublisher",
    "dispatch_notifications",
]
