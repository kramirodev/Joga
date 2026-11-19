"""Dispatcher da Outbox para o provedor de e-mail (ADR 0050).

O worker é separado da API: a request apenas grava o desafio e o evento. Falha
de provedor não altera a resposta pública; ela fica no log de entrega e volta
para a fila com backoff.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.modules.email.deliveries import (
    EMAIL_EVENT_TYPE,
    EmailDeliveryService,
    mark_hard_bounce,
)
from app.modules.email.models import EmailDelivery
from app.modules.email.sender import EmailMessage, EmailSender, EmailSenderError
from app.modules.email.templates import InvalidTemplate, render
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.events import EMAIL_DELIVERY_FAILED, record_security_event
from app.modules.outbox.models import OutboxEvent
from app.modules.outbox.service import OutboxService

logger = logging.getLogger("joga.email")


@dataclass(frozen=True)
class DeliveryReport:
    sent: int = 0
    failed: int = 0
    bounced: int = 0
    skipped: int = 0


def dispatch_email_deliveries(
    session: Session,
    sender: EmailSender,
    *,
    max_attempts: int = 5,
    bounce_threshold: int = 3,
    limit: int = 100,
    now: datetime | None = None,
) -> DeliveryReport:
    """Entrega eventos de e-mail pendentes, com um retry imediato."""
    if max_attempts <= 0:
        raise ValueError("max_attempts deve ser positivo")
    outbox = OutboxService(session)
    moment = ensure_utc(now or utcnow())
    sent = failed = bounced = skipped = 0

    for event in outbox.pending(limit=limit, now=moment):
        if event.event_type != EMAIL_EVENT_TYPE:
            continue

        payload = event.payload if isinstance(event.payload, dict) else {}
        delivery_id = _uuid_or_none(payload.get("delivery_id"))
        to = payload.get("to")
        kind = payload.get("kind")
        if delivery_id is None or not isinstance(to, str) or not isinstance(kind, str):
            _discard(session, event, "invalid_payload", moment)
            failed += 1
            continue

        delivery = session.get(EmailDelivery, delivery_id, with_for_update=True)
        if delivery is None:
            _discard(session, event, "missing_delivery", moment)
            failed += 1
            continue
        if delivery.status in {"sent", "bounced"}:
            outbox.mark_dispatched(event, now=moment)
            skipped += 1
            continue
        if delivery.attempts >= max_attempts:
            delivery.status = "failed"
            delivery.last_error_code = "attempts_exhausted"
            session.flush()
            outbox.mark_dispatched(event, now=moment)
            _record_delivery_failure(session, delivery, "attempts_exhausted")
            failed += 1
            continue

        context = payload.get("context")
        if not isinstance(context, dict):
            context = {}
        code = payload.get("code")
        try:
            rendered = render(
                kind,
                code=code if isinstance(code, str) else None,
                ttl_minutes=int(context.get("ttl_minutes", 10)),
                display_name=context.get("display_name"),
                occurred_at=context.get("occurred_at"),
                device_label=context.get("device_label"),
                deletion_label=context.get("deletion_label"),
            )
        except (InvalidTemplate, TypeError, ValueError):
            _discard(session, event, "invalid_template", moment)
            delivery.status = "failed"
            delivery.last_error_code = "invalid_template"
            session.flush()
            failed += 1
            continue

        message = EmailMessage(
            to=to,
            subject=rendered.subject,
            text=rendered.text,
            html=rendered.html,
            kind=kind,
            code=code if isinstance(code, str) else None,
        )

        outcome = _deliver(
            session,
            outbox,
            event,
            delivery,
            sender,
            message,
            max_attempts=max_attempts,
            moment=moment,
        )
        if outcome == "sent":
            sent += 1
        elif outcome == "bounced":
            bounced += 1
            mark_hard_bounce(
                session,
                email_normalized=to,
                user_id=delivery.user_id,
                kind=kind,
                threshold=bounce_threshold,
                now=moment,
            )
        else:
            failed += 1
    session.flush()
    logger.info(
        "e-mail: enviados=%s falhos=%s bounced=%s ignorados=%s",
        sent,
        failed,
        bounced,
        skipped,
    )
    return DeliveryReport(sent=sent, failed=failed, bounced=bounced, skipped=skipped)


def _deliver(
    session: Session,
    outbox: OutboxService,
    event: OutboxEvent,
    delivery: EmailDelivery,
    sender: EmailSender,
    message: EmailMessage,
    *,
    max_attempts: int,
    moment: datetime,
) -> str:
    """Executa no máximo duas tentativas imediatas e devolve o desfecho."""
    immediate_attempts = 0
    while True:
        delivery.attempts += 1
        session.flush()
        try:
            message_id = sender.send(message)
        except EmailSenderError as error:
            delivery.last_error_code = error.code
            if error.permanent:
                is_bounce = error.code == "provider_rejected"
                delivery.status = "bounced" if is_bounce else "failed"
                session.flush()
                outbox.mark_dispatched(event, now=moment)
                _record_delivery_failure(session, delivery, error.code)
                return "bounced" if is_bounce else "failed"
            delivery.status = "failed"
            session.flush()
            if immediate_attempts == 0 and delivery.attempts < max_attempts:
                immediate_attempts += 1
                continue
            delay = EmailDeliveryService.next_retry_delay(delivery.attempts)
            outbox.mark_failed(
                event,
                error.code,
                now=moment,
                retry_in_seconds=int(delay.total_seconds()),
            )
            return "failed"

        delivery.status = "sent"
        delivery.sent_at = moment
        delivery.provider_message_id = message_id
        delivery.last_error_code = None
        session.flush()
        outbox.mark_dispatched(event, now=moment)
        _log_latency(event, delivery, moment)
        return "sent"


def _log_latency(event: OutboxEvent, delivery: EmailDelivery, moment: datetime) -> None:
    """Loga a latência do evento até o aceite do provedor, sem PII."""
    latency_ms = max(
        0.0, (ensure_utc(moment) - ensure_utc(event.created_at)).total_seconds() * 1000
    )
    logger.info(
        "e-mail: entregue kind=%s latencia_ms=%.0f",
        delivery.kind,
        latency_ms,
    )


def _record_delivery_failure(
    session: Session,
    delivery: EmailDelivery,
    code: str,
) -> None:
    record_security_event(
        session,
        EMAIL_DELIVERY_FAILED,
        user_id=delivery.user_id,
        details={"kind": delivery.kind, "code": code},
    )


def _discard(
    session: Session,
    event: OutboxEvent,
    reason: str,
    moment: datetime,
) -> None:
    """Evento veneno não deve ser reprocessado indefinidamente."""
    event.status = "FAILED"
    event.last_error = reason[:500]
    event.available_at = moment + timedelta(days=365)
    session.flush()


def _uuid_or_none(value: object) -> uuid.UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def purge_dispatched_email_events(
    session: Session,
    *,
    older_than_hours: int = 1,
    now: datetime | None = None,
) -> int:
    """Remove da Outbox o payload efêmero que continha destinatário e código."""
    if older_than_hours < 0:
        raise ValueError("older_than_hours não pode ser negativo")
    moment = ensure_utc(now or utcnow())
    cutoff = moment - timedelta(hours=older_than_hours)
    result = session.execute(
        delete(OutboxEvent).where(
            OutboxEvent.event_type == EMAIL_EVENT_TYPE,
            OutboxEvent.status == "DISPATCHED",
            OutboxEvent.dispatched_at.is_not(None),
            OutboxEvent.dispatched_at < cutoff,
        )
    )
    session.flush()
    return int(getattr(result, "rowcount", 0) or 0)


def purge_email_deliveries(
    session: Session,
    *,
    retention_days: int = 90,
    now: datetime | None = None,
) -> int:
    """Remove o log de entrega antigo (não contém PII em claro)."""
    if retention_days <= 0:
        raise ValueError("retention_days deve ser positivo")
    moment = ensure_utc(now or utcnow())
    cutoff = moment - timedelta(days=retention_days)
    result = session.execute(delete(EmailDelivery).where(EmailDelivery.created_at < cutoff))
    session.flush()
    return int(getattr(result, "rowcount", 0) or 0)


__all__ = [
    "DeliveryReport",
    "dispatch_email_deliveries",
    "purge_dispatched_email_events",
    "purge_email_deliveries",
]
