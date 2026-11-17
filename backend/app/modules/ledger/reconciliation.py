"""Reconciliação do crédito em centavos (ADR 0049 §11.6).

Compara `player_credit:<user>` no ledger com a soma de
`ticket_lots.remaining_cents` dos lotes comprados/devolução. Não corrige nada.
Também lista as vagas de passe/grátis/admin como excluídas da Etapa 6 — a
Etapa 6b é quem lança a quadra e a taxa dessas fontes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import BookingParticipant
from app.modules.ledger.accounts import PLAYER_CREDIT_PREFIX, player_credit_code
from app.modules.ledger.models import LedgerAccount
from app.modules.ledger.service import LedgerError, LedgerService
from app.modules.tickets.models import TicketLot
from app.modules.tickets.service import PAID_SOURCES

EXCLUDED_SOURCES = ("pass", "free_level", "admin")


@dataclass(frozen=True)
class CreditMismatch:
    user_id: uuid.UUID
    ledger_cents: int
    lots_cents: int

    @property
    def difference(self) -> int:
        return self.ledger_cents - self.lots_cents


@dataclass(frozen=True)
class ExcludedSeat:
    booking_id: uuid.UUID
    participant_id: uuid.UUID
    user_id: uuid.UUID
    source: str
    contribution_cents: int


@dataclass
class ReconciliationReport:
    checked_users: int = 0
    mismatches: list[CreditMismatch] = field(default_factory=list)
    excluded_seats: list[ExcludedSeat] = field(default_factory=list)

    @property
    def divergence_count(self) -> int:
        return len(self.mismatches)

    @property
    def clean(self) -> bool:
        return not self.mismatches


def _credit_users(session: Session) -> set[uuid.UUID]:
    users = set(
        session.scalars(
            select(LedgerAccount.owner_id).where(
                LedgerAccount.owner_kind == "user",
                LedgerAccount.code.like(f"{PLAYER_CREDIT_PREFIX}%"),
                LedgerAccount.owner_id.is_not(None),
            )
        ).all()
    )
    users.update(
        session.scalars(
            select(TicketLot.user_id)
            .where(
                TicketLot.source.in_(PAID_SOURCES),
                TicketLot.remaining_cents.is_not(None),
            )
            .distinct()
        ).all()
    )
    return {user_id for user_id in users if user_id is not None}


def _lots_cents(session: Session, user_id: uuid.UUID) -> int:
    value = session.scalar(
        select(func.coalesce(func.sum(TicketLot.remaining_cents), 0)).where(
            TicketLot.user_id == user_id,
            TicketLot.source.in_(PAID_SOURCES),
            TicketLot.remaining_cents.is_not(None),
        )
    )
    return int(value or 0)


def reconcile_credit(session: Session) -> ReconciliationReport:
    report = ReconciliationReport()
    service = LedgerService(session)
    for user_id in sorted(_credit_users(session), key=str):
        try:
            ledger_cents = service.balance_for_code(player_credit_code(user_id))
        except LedgerError:
            ledger_cents = 0
        lots_cents = _lots_cents(session, user_id)
        report.checked_users += 1
        if ledger_cents != lots_cents:
            report.mismatches.append(
                CreditMismatch(
                    user_id=user_id,
                    ledger_cents=ledger_cents,
                    lots_cents=lots_cents,
                )
            )

    excluded = session.execute(
        select(BookingParticipant).where(
            BookingParticipant.funding_source.in_(EXCLUDED_SOURCES),
            BookingParticipant.tickets_consumed > 0,
        )
    ).scalars()
    report.excluded_seats = [
        ExcludedSeat(
            booking_id=participant.booking_id,
            participant_id=participant.id,
            user_id=participant.user_id,
            source=participant.funding_source or "unknown",
            contribution_cents=participant.contribution_cents,
        )
        for participant in excluded
    ]
    return report


def ledger_health(session: Session) -> dict[str, object]:
    """Health check executável, sem PII: contadores de divergência."""

    report = reconcile_credit(session)
    return {
        "clean": report.clean,
        "checked_users": report.checked_users,
        "divergence_count": report.divergence_count,
        "excluded_seats": len(report.excluded_seats),
    }


__all__ = [
    "CreditMismatch",
    "ExcludedSeat",
    "ReconciliationReport",
    "ledger_health",
    "reconcile_credit",
]
