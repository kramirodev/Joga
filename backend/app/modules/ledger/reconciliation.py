"""Reconciliação do crédito (ADR 0049 §13.7).

Dois saldos independentes:
- tickets: `ticket_balances` é view; a verdade é a soma de
  `ticket_lots.remaining`, conferida contra `Σ original_amount` menos a soma
  algébrica de `ticket_ledger.amount` negativo por jogador;
- caixa: `player_credit` == compras pagas + abertura − Σ k×310 das reservas
  quitadas por tickets.

Não corrige nada. Também confere que toda vaga de passe/grátis/admin tem o
lançamento de confirmação da Etapa 6b.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking, BookingParticipant
from app.modules.ledger.accounts import PLAYER_CREDIT_PREFIX, player_credit_code
from app.modules.ledger.models import LedgerAccount, LedgerTransaction
from app.modules.ledger.service import LedgerError, LedgerService
from app.modules.pricing.service import TICKET_CALIBRATION_CENTS
from app.modules.tickets.models import TicketLedgerEntry, TicketLot
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
    lots_balance: int
    derived_balance: int

    @property
    def difference(self) -> int:
        return self.lots_balance - self.derived_balance


@dataclass(frozen=True)
class ExcludedSeat:
    booking_id: uuid.UUID
    participant_id: uuid.UUID
    user_id: uuid.UUID
    source: str
    contribution_cents: int


@dataclass(frozen=True)
class BookingRateioMismatch:
    booking_id: uuid.UUID
    field: str
    expected: int
    actual: int


@dataclass(frozen=True)
class NegativeBalance:
    kind: str
    user_id: uuid.UUID
    balance: int


@dataclass
class ReconciliationReport:
    checked_users: int = 0
    mismatches: list[CreditMismatch] = field(default_factory=list)
    balance_mismatches: list[BalanceMismatch] = field(default_factory=list)
    rateio_mismatches: list[BookingRateioMismatch] = field(default_factory=list)
    negative_balances: list[NegativeBalance] = field(default_factory=list)
    non_credit_seats: list[ExcludedSeat] = field(default_factory=list)
    missing_non_credit_postings: list[uuid.UUID] = field(default_factory=list)

    @property
    def divergence_count(self) -> int:
        return (
            len(self.mismatches)
            + len(self.balance_mismatches)
            + len(self.rateio_mismatches)
            + len(self.negative_balances)
            + len(self.missing_non_credit_postings)
        )

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
    users.update(session.scalars(select(TicketLedgerEntry.user_id).distinct()).all())
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


def _derived_balance(session: Session, user_id: uuid.UUID) -> int:
    """Saldo reconstruído dos lotes e do ledger de tickets.

    ``Σ original_amount`` + débitos (consumo, expiração, revogação) + devoluções
    que apenas reabriram um lote existente. Uma devolução que cria lote novo já
    entra em ``original_amount`` e é identificada por estar referenciada em
    ``ticket_lots.ledger_entry_id``.
    """

    original = session.scalar(
        select(func.coalesce(func.sum(TicketLot.original_amount), 0)).where(
            TicketLot.user_id == user_id,
        )
    )
    negative = session.scalar(
        select(func.coalesce(func.sum(TicketLedgerEntry.amount), 0)).where(
            TicketLedgerEntry.user_id == user_id,
            TicketLedgerEntry.amount < 0,
        )
    )
    restored = session.scalar(
        select(func.coalesce(func.sum(TicketLedgerEntry.amount), 0)).where(
            TicketLedgerEntry.user_id == user_id,
            TicketLedgerEntry.source == "refund",
            TicketLedgerEntry.amount > 0,
            TicketLedgerEntry.id.notin_(
                select(TicketLot.ledger_entry_id).where(TicketLot.ledger_entry_id.is_not(None))
            ),
        )
    )
    return int(original or 0) + int(negative or 0) + int(restored or 0)


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
        lots_balance = _lots_balance(session, user_id)
        derived_balance = _derived_balance(session, user_id)
        if lots_balance != derived_balance:
            report.balance_mismatches.append(
                BalanceMismatch(
                    user_id=user_id,
                    lots_balance=lots_balance,
                    derived_balance=derived_balance,
                )
            )
        if ledger_cents < 0:
            report.negative_balances.append(NegativeBalance("credit", user_id, ledger_cents))
        if lots_balance < 0:
            report.negative_balances.append(NegativeBalance("tickets", user_id, lots_balance))

    confirmed = session.scalars(
        select(Booking).where(
            Booking.status.in_(("CONFIRMED", "COMPLETED")),
            Booking.pricing_version != "legacy_v0",
        )
    ).all()
    for booking in confirmed:
        participants = session.scalars(
            select(BookingParticipant).where(
                BookingParticipant.booking_id == booking.id,
                BookingParticipant.active.is_(True),
            )
        ).all()
        if not participants:
            continue
        space_sum = sum(item.space_charge_cents for item in participants)
        if space_sum != booking.venue_price_cents:
            report.rateio_mismatches.append(
                BookingRateioMismatch(
                    booking_id=booking.id,
                    field="space_total",
                    expected=booking.venue_price_cents,
                    actual=space_sum,
                )
            )
        if all(item.funding_source == "credit" for item in participants):
            ticket_total = sum(
                item.tickets_consumed * TICKET_CALIBRATION_CENTS for item in participants
            )
            fee_sum = sum(item.fee_charge_cents for item in participants)
            expected_fee = ticket_total - booking.venue_price_cents
            if fee_sum != expected_fee:
                report.rateio_mismatches.append(
                    BookingRateioMismatch(
                        booking_id=booking.id,
                        field="fee_total",
                        expected=expected_fee,
                        actual=fee_sum,
                    )
                )
        for participant in participants:
            if participant.funding_source != "credit":
                continue
            ticket_value = participant.tickets_consumed * TICKET_CALIBRATION_CENTS
            if participant.contribution_cents != ticket_value:
                report.rateio_mismatches.append(
                    BookingRateioMismatch(
                        booking_id=booking.id,
                        field=f"participant:{participant.id}:contribution",
                        expected=ticket_value,
                        actual=participant.contribution_cents,
                    )
                )
            expected_fee = ticket_value - participant.space_charge_cents
            if participant.fee_charge_cents != expected_fee:
                report.rateio_mismatches.append(
                    BookingRateioMismatch(
                        booking_id=booking.id,
                        field=f"participant:{participant.id}:fee",
                        expected=expected_fee,
                        actual=participant.fee_charge_cents,
                    )
                )

    non_credit = list(
        session.scalars(
            select(BookingParticipant).where(
                BookingParticipant.funding_source.in_(EXCLUDED_SOURCES),
                BookingParticipant.tickets_consumed > 0,
            )
        ).all()
    )
    report.non_credit_seats = [
        ExcludedSeat(
            booking_id=participant.booking_id,
            participant_id=participant.id,
            user_id=participant.user_id,
            source=participant.funding_source or "unknown",
            contribution_cents=participant.contribution_cents,
        )
        for participant in non_credit
    ]
    booking_ids = {participant.booking_id for participant in non_credit}
    for booking_id in booking_ids:
        non_credit_booking = session.get(Booking, booking_id)
        if non_credit_booking is None or non_credit_booking.pricing_version == "legacy_v0":
            continue
        posted = session.scalar(
            select(LedgerTransaction.id).where(
                LedgerTransaction.idempotency_key == f"booking:{booking_id}:confirm"
            )
        )
        if posted is None:
            report.missing_non_credit_postings.append(booking_id)
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
        "rateio_mismatches": len(report.rateio_mismatches),
        "negative_balances": len(report.negative_balances),
        "non_credit_seats": len(report.non_credit_seats),
        "missing_non_credit_postings": len(report.missing_non_credit_postings),
    }


__all__ = [
    "BalanceMismatch",
    "BookingRateioMismatch",
    "CreditMismatch",
    "ExcludedSeat",
    "NegativeBalance",
    "ReconciliationReport",
    "ledger_health",
    "reconcile_credit",
]
