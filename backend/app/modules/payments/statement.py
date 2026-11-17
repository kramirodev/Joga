"""Extrato financeiro do estabelecimento projetado do ledger de dupla entrada.

Substitui o antigo ``booking_ledger_entries`` (single-entry). Cada linha do
extrato é uma transação contábil que afeta a conta da quadra
(``venue_payable``/``venue_receivable``), com o valor da parte da quadra.

O identificador da linha é o ``ledger_transactions.id``. ``booking_payment_id``
fica nulo: o fato contábil é a reserva, não a cobrança individual do PSP.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import Subquery

from app.modules.bookings.models import Booking, BookingPayment
from app.modules.ledger.models import LedgerAccount, LedgerEntry, LedgerTransaction
from app.modules.payments.models import VenueRelease

# Tipo exibido no extrato -> (entry_type do contrato, direction).
STATEMENT_KINDS: dict[str, tuple[str, str]] = {
    "booking_confirmed": ("PAYMENT_CONFIRMED", "CREDIT"),
    "booking_refund": ("PAYMENT_REFUNDED", "DEBIT"),
    "payment_refund": ("PAYMENT_REFUNDED", "DEBIT"),
    "venue_release": ("VENUE_RELEASE", "CREDIT"),
}


@dataclass(frozen=True)
class StatementRow:
    """Linha do extrato; mantém os campos do contrato anterior."""

    id: uuid.UUID
    booking_id: uuid.UUID
    booking_payment_id: uuid.UUID | None
    entry_type: str
    direction: str
    amount_cents: int
    status: str
    details: dict[str, Any] | None
    created_at: datetime


def _base_statement() -> Subquery:
    """Transações do ledger que compõem o extrato, com a reserva resolvida."""

    booking_id = func.coalesce(
        Booking.id, BookingPayment.booking_id, VenueRelease.booking_id
    ).label("booking_id")
    venue_amount = (
        select(
            LedgerEntry.transaction_id.label("transaction_id"),
            func.coalesce(func.sum(LedgerEntry.amount_cents), 0).label("amount_cents"),
        )
        .join(LedgerAccount, LedgerAccount.id == LedgerEntry.account_id)
        .where(LedgerAccount.owner_kind == "venue")
        .group_by(LedgerEntry.transaction_id)
        .subquery()
    )
    statement = (
        select(
            LedgerTransaction.id.label("id"),
            booking_id,
            LedgerTransaction.kind.label("kind"),
            LedgerTransaction.idempotency_key.label("idempotency_key"),
            LedgerTransaction.occurred_at.label("occurred_at"),
            venue_amount.c.amount_cents.label("amount_cents"),
        )
        .outerjoin(
            Booking,
            and_(
                LedgerTransaction.ref_type == "booking",
                Booking.id == LedgerTransaction.ref_id,
            ),
        )
        .outerjoin(
            BookingPayment,
            and_(
                LedgerTransaction.ref_type == "booking_payment",
                BookingPayment.id == LedgerTransaction.ref_id,
            ),
        )
        .outerjoin(
            VenueRelease,
            and_(
                LedgerTransaction.ref_type == "venue_release",
                VenueRelease.id == LedgerTransaction.ref_id,
            ),
        )
        .outerjoin(venue_amount, venue_amount.c.transaction_id == LedgerTransaction.id)
        .where(LedgerTransaction.kind.in_(tuple(STATEMENT_KINDS)))
    )
    return statement.subquery()


def _row(raw: Any) -> StatementRow:
    entry_type, direction = STATEMENT_KINDS[str(raw.kind)]
    return StatementRow(
        id=raw.id,
        booking_id=raw.booking_id,
        booking_payment_id=None,
        entry_type=entry_type,
        direction=direction,
        amount_cents=int(raw.amount_cents),
        status="POSTED",
        details={"kind": str(raw.kind), "idempotency_key": str(raw.idempotency_key)},
        created_at=raw.occurred_at,
    )


def statement(
    session: Session,
    *,
    organization_id: uuid.UUID | None = None,
    booking_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[StatementRow]:
    """Extrato paginado por organização ou por reserva, em ordem decrescente."""

    sub = _base_statement()
    statement_query = select(sub).where(sub.c.amount_cents > 0)
    if organization_id is not None:
        statement_query = statement_query.where(
            sub.c.booking_id.in_(
                select(Booking.id).where(Booking.organization_id == organization_id)
            )
        )
    if booking_id is not None:
        statement_query = statement_query.where(sub.c.booking_id == booking_id)
    statement_query = (
        statement_query.order_by(
            sub.c.occurred_at.desc(),
            sub.c.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return [_row(raw) for raw in session.execute(statement_query).all()]


def count_statement(
    session: Session,
    *,
    organization_id: uuid.UUID | None = None,
    booking_id: uuid.UUID | None = None,
) -> int:
    sub = _base_statement()
    query = select(func.count()).select_from(sub).where(sub.c.amount_cents > 0)
    if organization_id is not None:
        query = query.where(
            sub.c.booking_id.in_(
                select(Booking.id).where(Booking.organization_id == organization_id)
            )
        )
    if booking_id is not None:
        query = query.where(sub.c.booking_id == booking_id)
    return int(session.scalar(query) or 0)


__all__ = ["STATEMENT_KINDS", "StatementRow", "count_statement", "statement"]
