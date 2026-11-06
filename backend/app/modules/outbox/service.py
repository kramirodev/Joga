"""Serviço da Outbox transacional."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.outbox.models import OutboxEvent


class OutboxService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: uuid.UUID | None,
        payload: dict[str, Any],
        now: datetime | None = None,
    ) -> OutboxEvent:
        moment = ensure_utc(now or utcnow())
        event = OutboxEvent(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            status="PENDING",
            available_at=moment,
            created_at=moment,
        )
        self._session.add(event)
        self._session.flush()
        return event

    def pending(self, *, limit: int = 100, now: datetime | None = None) -> list[OutboxEvent]:
        moment = ensure_utc(now or utcnow())
        return list(
            self._session.scalars(
                select(OutboxEvent)
                .where(
                    OutboxEvent.status.in_(("PENDING", "FAILED")),
                    OutboxEvent.available_at <= moment,
                )
                .order_by(OutboxEvent.available_at, OutboxEvent.created_at)
                .limit(limit)
            )
        )

    def mark_dispatched(self, event: OutboxEvent, *, now: datetime | None = None) -> None:
        event.status = "DISPATCHED"
        event.dispatched_at = ensure_utc(now or utcnow())
        event.last_error = None
        self._session.flush()

    def mark_failed(
        self,
        event: OutboxEvent,
        error: str,
        *,
        now: datetime | None = None,
    ) -> None:
        event.status = "FAILED"
        event.attempts += 1
        event.last_error = error[:500]
        event.available_at = ensure_utc(now or utcnow())
        self._session.flush()
