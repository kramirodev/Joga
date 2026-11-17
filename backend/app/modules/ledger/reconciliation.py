"""Reconciliação do crédito (ADR 0049 §13.7).

Dois saldos independentes:
- tickets: `ticket_balances` == soma de `ticket_lots.remaining`;
- caixa: `player_credit` == compras pagas + abertura − Σ k×310 das reservas
  quitadas por tickets.

Não corrige nada. Lista vagas de passe/grátis/admin como excluídas da Etapa 6b.
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
from app.modules.tickets.models import TicketBalance, TicketLot
from app.modules.tickets.service import expected_player_credit_cents

EXCLUDED_SOURCES = ("pass", "free_level", "admin")


@dataclass(frozen=True)
class CreditMismatch:
    user_id: uuid.UUID
    ledger_cents: int
    expected_cents: int

    @property
    def difference(self) -> int:
        return self.ledger_cents - self.expected_cents


@dataclass(frozen=True)
class BalanceMismatch:
    user_id: uuid.UUID
    cache_balance: int
    lots_balance: int

    @property
    def difference(self) -> int:
        return self.cache_balance - self.lots_balance


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
    balance_mismatches: list[BalanceMismatch] = field(default_factory=list)
    excluded_seats: list[ExcludedSeat] = field(default_factory=list)

    @property
    def divergence_count(self) -> int:
        return len(self.mismatches) + len(self.balance_mismatches)

    @property
    def clean(self) -> bool:
        return self.divergence_count == 0


def _known_users(session: Session) -> set[uuid.UUID]:
    users = set(
        session.scalars(
            select(LedgerAccount.owner_id).where(
                LedgerAccount.owner_kind == "user",
                LedgerAccount.code.like(f"{PLAYER_CREDIT_PREFIX}%"),
                LedgerAccount.owner_id.is_not(None),
            )
        ).all()
    )
    users.update(session.scalars(select(TicketLot.user_id).distinct()).all())
    users.update(session.scalars(select(TicketBalance.user_id).distinct()).all())
    return {user_id for user_id in users if user_id is not None}


def _ledger_credit_cents(session: Session, user_id: uuid.UUID) -> int:
    service = LedgerService(session)
    try:
        return service.balance_for_code(player_credit_code(user_id))
    except LedgerError:
        return 0


def _lots_balance(session: Session, user_id: uuid.UUID) -> int:
    value = session.scalar(
        select(func.coalesce(func.sum(TicketLot.remaining), 0)).where(
            TicketLot.user_id == user_id,
        )
    )
    return int(value or 0)


def reconcile_credit(session: Session) -> ReconciliationReport:
    report = ReconciliationReport()
    for user_id in sorted(_known_users(session), key=str):
        ledger_cents = _ledger_credit_cents(session, user_id)
        expected_cents = expected_player_credit_cents(session, user_id)
        report.checked_users += 1
        if ledger_cents != expected_cents:
            report.mismatches.append(
                CreditMismatch(
                    user_id=user_id,
                    ledger_cents=ledger_cents,
                    expected_cents=expected_cents,
                )
            )
        cache = session.get(TicketBalance, user_id)
        cache_balance = cache.balance if cache is not None else 0
        lots_balance = _lots_balance(session, user_id)
        if cache_balance != lots_balance:
            report.balance_mismatches.append(
                BalanceMismatch(
                    user_id=user_id,
                    cache_balance=cache_balance,
                    lots_balance=lots_balance,
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
        "credit_mismatches": len(report.mismatches),
        "balance_mismatches": len(report.balance_mismatches),
        "excluded_seats": len(report.excluded_seats),
    }


__all__ = [
    "BalanceMismatch",
    "CreditMismatch",
    "ExcludedSeat",
    "ReconciliationReport",
    "ledger_health",
    "reconcile_credit",
]
