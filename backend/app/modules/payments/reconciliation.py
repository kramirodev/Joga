"""Conciliação interna entre pagamentos, liberações e o ledger de dupla entrada.

O antigo ``booking_ledger_entries`` foi aposentado na Etapa 9; a conciliação
passa a conferir as transações contábeis ``booking_confirmed``,
``booking_refund``, ``payment_refund`` e ``venue_release``.

A função não corrige nada: divergência financeira exige análise e evento
compensatório auditável, nunca edição silenciosa de saldo.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking, BookingPayment
from app.modules.ledger.models import LedgerTransaction
from app.modules.payments.models import FinancialDispute, VenueRelease


def reconcile(
    session: Session,
    *,
    organization_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Compara os registros internos e devolve divergências para investigação."""

    issues: list[dict[str, Any]] = []

    confirmed = (
        select(Booking)
        .outerjoin(
            LedgerTransaction,
            and_(
                LedgerTransaction.ref_type == "booking",
                LedgerTransaction.ref_id == Booking.id,
                LedgerTransaction.kind == "booking_confirmed",
            ),
        )
        .where(
            Booking.status.in_({"CONFIRMED", "COMPLETED"}),
            Booking.pricing_version != "legacy_v0",
            LedgerTransaction.id.is_(None),
        )
    )
    if organization_id is not None:
        confirmed = confirmed.where(Booking.organization_id == organization_id)
    for booking in session.scalars(confirmed).all():
        issues.append(
            {
                "code": "confirmed_booking_without_ledger_entry",
                "booking_id": str(booking.id),
                "amount_cents": booking.venue_price_cents,
            }
        )

    if organization_id is None:
        orphan_booking_entries = (
            select(LedgerTransaction)
            .outerjoin(
                Booking,
                and_(
                    LedgerTransaction.ref_type == "booking",
                    Booking.id == LedgerTransaction.ref_id,
                ),
            )
            .where(
                LedgerTransaction.kind.in_({"booking_confirmed", "booking_refund"}),
                LedgerTransaction.ref_type == "booking",
                Booking.id.is_(None),
            )
        )
        for transaction in session.scalars(orphan_booking_entries).all():
            issues.append(
                {
                    "code": "ledger_transaction_without_booking",
                    "ledger_transaction_id": str(transaction.id),
                    "kind": transaction.kind,
                }
            )

    if organization_id is None:
        orphan_payment_refunds = (
            select(LedgerTransaction)
            .outerjoin(
                BookingPayment,
                and_(
                    LedgerTransaction.ref_type == "booking_payment",
                    BookingPayment.id == LedgerTransaction.ref_id,
                ),
            )
            .where(
                LedgerTransaction.kind == "payment_refund",
                LedgerTransaction.ref_type == "booking_payment",
                BookingPayment.id.is_(None),
            )
        )
        for transaction in session.scalars(orphan_payment_refunds).all():
            issues.append(
                {
                    "code": "payment_refund_without_payment",
                    "ledger_transaction_id": str(transaction.id),
                }
            )

    released = (
        select(VenueRelease, Booking.id)
        .join(Booking, Booking.id == VenueRelease.booking_id)
        .outerjoin(
            LedgerTransaction,
            and_(
                LedgerTransaction.ref_type == "venue_release",
                LedgerTransaction.ref_id == VenueRelease.id,
                LedgerTransaction.kind == "venue_release",
            ),
        )
        .where(VenueRelease.status == "RELEASED", LedgerTransaction.id.is_(None))
    )
    if organization_id is not None:
        released = released.where(Booking.organization_id == organization_id)
    for release, booking_id in session.execute(released).all():
        issues.append(
            {
                "code": "release_without_ledger_entry",
                "booking_id": str(booking_id),
                "release_id": str(release.id),
                "amount_cents": release.amount_cents,
            }
        )

    if organization_id is None:
        orphan_release_entries = (
            select(LedgerTransaction)
            .outerjoin(
                VenueRelease,
                and_(
                    LedgerTransaction.ref_type == "venue_release",
                    VenueRelease.id == LedgerTransaction.ref_id,
                ),
            )
            .where(
                LedgerTransaction.kind == "venue_release",
                LedgerTransaction.ref_type == "venue_release",
                VenueRelease.id.is_(None),
            )
        )
        for transaction in session.scalars(orphan_release_entries).all():
            issues.append(
                {
                    "code": "release_entry_without_record",
                    "ledger_transaction_id": str(transaction.id),
                }
            )

    mismatched = (
        select(VenueRelease, Booking.venue_price_cents)
        .join(Booking, Booking.id == VenueRelease.booking_id)
        .where(
            VenueRelease.status.in_({"PENDING", "RELEASED"}),
            VenueRelease.amount_cents != Booking.venue_price_cents,
        )
    )
    if organization_id is not None:
        mismatched = mismatched.where(Booking.organization_id == organization_id)
    for release, venue_price_cents in session.execute(mismatched).all():
        issues.append(
            {
                "code": "release_amount_mismatch",
                "booking_id": str(release.booking_id),
                "release_id": str(release.id),
                "amount_cents": release.amount_cents,
                "booking_venue_price_cents": int(venue_price_cents),
            }
        )

    completed_without_release = (
        select(Booking)
        .outerjoin(VenueRelease, VenueRelease.booking_id == Booking.id)
        .where(
            Booking.status == "COMPLETED",
            Booking.venue_price_cents > 0,
            VenueRelease.id.is_(None),
        )
    )
    if organization_id is not None:
        completed_without_release = completed_without_release.where(
            Booking.organization_id == organization_id
        )
    for booking in session.scalars(completed_without_release).all():
        issues.append(
            {
                "code": "completed_booking_without_release",
                "booking_id": str(booking.id),
                "amount_cents": booking.venue_price_cents,
            }
        )

    open_dispute_without_release = (
        select(FinancialDispute)
        .join(Booking, Booking.id == FinancialDispute.booking_id)
        .outerjoin(VenueRelease, VenueRelease.id == FinancialDispute.release_id)
        .where(
            FinancialDispute.status == "OPEN",
            VenueRelease.id.is_(None),
        )
    )
    if organization_id is not None:
        open_dispute_without_release = open_dispute_without_release.where(
            Booking.organization_id == organization_id
        )
    for dispute in session.scalars(open_dispute_without_release).all():
        issues.append(
            {
                "code": "open_dispute_without_release",
                "booking_id": str(dispute.booking_id),
                "dispute_id": str(dispute.id),
                "amount_cents": dispute.amount_cents,
            }
        )

    return issues


__all__ = ["reconcile"]
