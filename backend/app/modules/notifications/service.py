"""Serviço da central de notificações."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.notifications.models import Notification
from app.modules.outbox.service import OutboxService


class NotificationError(Exception):
    """Erro base da central de notificações."""


class NotificationNotFound(NotificationError):
    """Notificação inexistente ou de outro usuário."""


class NotificationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        user_id: uuid.UUID,
        kind: str,
        title: str,
        body: str,
        idempotency_key: str,
        data: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> tuple[Notification, bool]:
        """Cria a notificação e o evento de outbox, uma única vez por chave."""

        existing = self.session.scalar(
            select(Notification).where(Notification.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing, False
        moment = ensure_utc(now or utcnow())
        notification = Notification(
            user_id=user_id,
            kind=kind,
            title=title,
            body=body,
            data=data,
            idempotency_key=idempotency_key,
            created_at=moment,
        )
        self.session.add(notification)
        self.session.flush()
        OutboxService(self.session).enqueue(
            event_type="notification.created",
            aggregate_type="notification",
            aggregate_id=notification.id,
            payload={
                "notification_id": str(notification.id),
                "user_id": str(user_id),
                "kind": kind,
                "title": title,
                "body": body,
                "data": data or {},
            },
            now=moment,
        )
        return notification, True

    def create_many(
        self,
        user_ids: list[uuid.UUID] | tuple[uuid.UUID, ...],
        *,
        kind: str,
        title: str,
        body: str,
        idempotency_key_prefix: str,
        data: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> int:
        created = 0
        for user_id in dict.fromkeys(user_ids):
            _notification, is_new = self.create(
                user_id=user_id,
                kind=kind,
                title=title,
                body=body,
                idempotency_key=f"{idempotency_key_prefix}:{user_id}",
                data=data,
                now=now,
            )
            created += int(is_new)
        return created

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        unread_only: bool = False,
        limit: int = 30,
        offset: int = 0,
    ) -> list[Notification]:
        statement = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(offset)
            .limit(limit)
        )
        if unread_only:
            statement = statement.where(Notification.read_at.is_(None))
        return list(self.session.scalars(statement).all())

    def unread_count(self, user_id: uuid.UUID) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None),
                )
            )
            or 0
        )

    def mark_read(
        self,
        user_id: uuid.UUID,
        notification_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> Notification:
        notification = self.session.get(Notification, notification_id)
        if notification is None or notification.user_id != user_id:
            raise NotificationNotFound
        if notification.read_at is None:
            notification.read_at = ensure_utc(now or utcnow())
            self.session.flush()
        return notification

    def mark_all_read(self, user_id: uuid.UUID, *, now: datetime | None = None) -> int:
        moment = ensure_utc(now or utcnow())
        rows = list(
            self.session.scalars(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None),
                )
            ).all()
        )
        for row in rows:
            row.read_at = moment
        self.session.flush()
        return len(rows)


__all__ = [
    "NotificationError",
    "NotificationNotFound",
    "NotificationService",
]
