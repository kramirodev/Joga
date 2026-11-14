"""Dispatcher de notificações da Outbox para o push (Fase 13E)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.outbox.service import OutboxService
from app.modules.push.service import PushError, PushSender, PushService


def dispatch_notifications(
    session: Session,
    sender: PushSender,
    *,
    limit: int = 100,
) -> int:
    """Envia eventos ``notification.created`` pendentes e marca a Outbox.

    Sem token ativo, o evento falha e permanece elegível para nova tentativa.
    Eventos de outros tipos são preservados para seus respectivos workers.
    """

    outbox = OutboxService(session)
    push = PushService(session, sender)
    delivered = 0
    for event in outbox.pending(limit=limit):
        if event.event_type != "notification.created":
            continue
        payload = event.payload or {}
        user_id = payload.get("user_id")
        if not isinstance(user_id, str):
            outbox.mark_failed(event, "invalid_payload")
            continue
        raw_data = payload.get("data")
        data: dict[str, str] = (
            {str(key): str(value) for key, value in raw_data.items()}
            if isinstance(raw_data, dict)
            else {}
        )
        try:
            count = push.send_to_user(
                uuid.UUID(user_id),
                title=str(payload.get("title") or "JOGA"),
                body=str(payload.get("body") or ""),
                data=data,
            )
        except PushError as exc:
            outbox.mark_failed(event, str(exc))
            continue
        if count == 0:
            outbox.mark_failed(event, "no_active_tokens")
            continue
        outbox.mark_dispatched(event)
        delivered += 1
    session.flush()
    return delivered


__all__ = ["dispatch_notifications"]
