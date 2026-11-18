"""Enfileiramento idempotente e orçamento diário de e-mail transacional."""

from __future__ import annotations

import logging
import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.email.addresses import hash_email
from app.modules.email.models import EMAIL_KINDS, EmailDelivery, UserEmail
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.events import (
    EMAIL_BOUNCE,
    EMAIL_BUDGET_EXHAUSTED,
    EMAIL_BUDGET_WARNING,
    record_security_event,
)
from app.modules.identity.models import SecurityEvent
from app.modules.outbox.service import OutboxService

EMAIL_EVENT_TYPE = "email.delivery_requested"
WARNING_RATIO = 0.8
logger = logging.getLogger("joga.email")


def mark_hard_bounce(
    session: Session,
    *,
    email_normalized: str,
    user_id: uuid.UUID | None,
    kind: str,
    threshold: int,
    now: datetime | None = None,
) -> None:
    """Incrementa o bounce da credencial e a marca como não entregável."""
    moment = ensure_utc(now or utcnow())
    credential = session.scalar(
        select(UserEmail).where(
            UserEmail.email_normalized == email_normalized,
            UserEmail.released_at.is_(None),
        )
    )
    if credential is None:
        record_security_event(
            session,
            EMAIL_BOUNCE,
            user_id=user_id,
            details={"kind": kind, "credential": False},
        )
        return

    credential.hard_bounce_count += 1
    if credential.undeliverable_at is None and credential.hard_bounce_count >= threshold:
        credential.undeliverable_at = moment
    record_security_event(
        session,
        EMAIL_BOUNCE,
        user_id=credential.user_id,
        details={
            "kind": kind,
            "credential": True,
            "hard_bounces": credential.hard_bounce_count,
            "undeliverable": credential.undeliverable_at is not None,
        },
    )
    session.flush()


class EmailDeliveryError(Exception):
    """Erro base da camada de entrega."""


class InvalidEmailKind(EmailDeliveryError):
    """Tipo de e-mail fora da lista transacional permitida."""


class EmailBudgetExhausted(EmailDeliveryError):
    """Orçamento diário esgotado; é erro operacional, não de credencial."""

    def __init__(self, budget: int) -> None:
        super().__init__(f"orçamento diário de e-mail esgotado ({budget})")
        self.budget = budget


class EmailDeliveryService:
    """Cria registros de entrega e eventos de Outbox na mesma transação."""

    def __init__(
        self,
        session: Session,
        *,
        provider: str,
        daily_budget: int,
        secret: str,
        max_attempts: int = 5,
        bounce_threshold: int = 3,
    ) -> None:
        if daily_budget <= 0:
            raise ValueError("daily_budget deve ser positivo")
        if max_attempts <= 0:
            raise ValueError("max_attempts deve ser positivo")
        if bounce_threshold <= 0:
            raise ValueError("bounce_threshold deve ser positivo")
        if not secret:
            raise ValueError("segredo de hash não pode ser vazio")
        self._session = session
        self._provider = provider
        self._daily_budget = daily_budget
        self._secret = secret
        self._max_attempts = max_attempts
        self._bounce_threshold = bounce_threshold

    @property
    def daily_budget(self) -> int:
        return self._daily_budget

    @property
    def max_attempts(self) -> int:
        return self._max_attempts

    @property
    def bounce_threshold(self) -> int:
        return self._bounce_threshold

    def enqueue(
        self,
        kind: str,
        *,
        to: str,
        user_id: uuid.UUID | None,
        reference: str,
        code: str | None = None,
        context: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> EmailDelivery:
        """Persiste o log e o evento de Outbox sem duplicar por idempotência."""
        if kind not in EMAIL_KINDS:
            raise InvalidEmailKind("tipo de e-mail desconhecido")
        if not reference or len(reference) > 80:
            raise EmailDeliveryError("referência de entrega inválida")

        moment = ensure_utc(now or utcnow())
        key = self.idempotency_key(user_id=user_id, kind=kind, reference=reference)
        existing = self._session.scalar(
            select(EmailDelivery).where(EmailDelivery.idempotency_key == key)
        )
        if existing is not None:
            return existing

        used_today = self.count_today(now=moment)
        if used_today >= self._daily_budget:
            record_security_event(
                self._session,
                EMAIL_BUDGET_EXHAUSTED,
                details={"budget": self._daily_budget},
            )
            logger.warning(
                "orcamento diario de e-mail esgotado: budget=%s",
                self._daily_budget,
            )
            raise EmailBudgetExhausted(self._daily_budget)

        delivery_id = uuid.uuid4()
        delivery = EmailDelivery(
            id=delivery_id,
            user_id=user_id,
            kind=kind,
            status="queued",
            attempts=0,
            provider=self._provider,
            email_hash=hash_email(to, self._secret),
            reference=reference,
            idempotency_key=key,
            created_at=moment,
        )
        try:
            with self._session.begin_nested():
                self._session.add(delivery)
                self._session.flush()
        except IntegrityError:
            existing = self._session.scalar(
                select(EmailDelivery).where(EmailDelivery.idempotency_key == key)
            )
            if existing is not None:
                return existing
            raise

        OutboxService(self._session).enqueue(
            event_type=EMAIL_EVENT_TYPE,
            aggregate_type="email_delivery",
            aggregate_id=delivery_id,
            payload={
                "delivery_id": str(delivery_id),
                "kind": kind,
                "to": to,
                "user_id": str(user_id) if user_id is not None else None,
                "code": code,
                "context": context or {},
            },
            now=moment,
        )

        self._warn_if_needed(now=moment)
        return delivery

    def count_today(self, *, now: datetime | None = None) -> int:
        moment = ensure_utc(now or utcnow())
        start = datetime(moment.year, moment.month, moment.day, tzinfo=UTC)
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(EmailDelivery)
                .where(EmailDelivery.created_at >= start)
            )
            or 0
        )

    def mark_bounce(
        self,
        *,
        email_normalized: str,
        user_id: uuid.UUID | None,
        kind: str,
        now: datetime | None = None,
    ) -> None:
        """Contabiliza bounce permanente na credencial, após o limite."""
        mark_hard_bounce(
            self._session,
            email_normalized=email_normalized,
            user_id=user_id,
            kind=kind,
            threshold=self._bounce_threshold,
            now=now,
        )

    @staticmethod
    def idempotency_key(*, user_id: uuid.UUID | None, kind: str, reference: str) -> str:
        owner = str(user_id) if user_id is not None else "anonymous"
        return f"{owner}:{kind}:{reference}"[:160]

    def _warn_if_needed(self, *, now: datetime) -> None:
        start = datetime(now.year, now.month, now.day, tzinfo=UTC)
        threshold = max(1, math.ceil(self._daily_budget * WARNING_RATIO))
        used = self.count_today(now=now)
        if used < threshold:
            return
        already = self._session.scalar(
            select(SecurityEvent.id)
            .where(
                SecurityEvent.event_type == EMAIL_BUDGET_WARNING,
                SecurityEvent.created_at >= start,
            )
            .limit(1)
        )
        if already is not None:
            return
        record_security_event(
            self._session,
            EMAIL_BUDGET_WARNING,
            details={"budget": self._daily_budget, "used": used, "threshold": threshold},
        )
        logger.warning(
            "orcamento diario de e-mail em %s%%: used=%s budget=%s",
            round(used * 100 / self._daily_budget),
            used,
            self._daily_budget,
        )

    @staticmethod
    def next_retry_delay(attempts: int) -> timedelta:
        """Backoff exponencial simples, limitado a uma hora."""
        return timedelta(seconds=min(3_600, 60 * (2 ** max(0, attempts - 1))))


__all__ = [
    "EMAIL_EVENT_TYPE",
    "EmailBudgetExhausted",
    "EmailDeliveryError",
    "EmailDeliveryService",
    "InvalidEmailKind",
    "mark_hard_bounce",
]
