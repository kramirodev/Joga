"""Conciliação interna entre pagamentos, reembolsos, liberações e ledger (Fase 15)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking, BookingPayment
from app.modules.payments.models import FinancialDispute, LedgerEntry, VenueRelease


def reconcile(
    session: Session,
    *,
    organization_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Compara os registros internos e devolve divergências para investigação.

    A função não corrige nada: divergência financeira exige análise e evento
    compensatório auditável, nunca edição silenciosa de saldo.
    """

    issues: list[dict[str, Any]] = []

    confirmed = and_(
        LedgerEntry.booking_payment_id == BookingPayment.id,
        LedgerEntry.entry_type == "PAYMENT_CONFIRMED",
    )
    refunded = and_(
        LedgerEntry.booking_payment_id == BookingPayment.id,
        LedgerEntry.entry_type == "PAYMENT_REFUNDED",
    )

    def payment_query(entry_condition: Any) -> Any:
        statement = (
            select(BookingPayment, LedgerEntry.id)
            .join(Booking, Booking.id == BookingPayment.booking_id)
            .outerjoin(LedgerEntry, entry_condition)
            .where(
                BookingPayment.status == ("PAID" if entry_condition is confirmed else "REFUNDED"),
                LedgerEntry.id.is_(None),
            )
        )
        if organization_id is not None:
            statement = statement.where(Booking.organization_id == organization_id)
        return statement

    for payment, _ in session.execute(payment_query(confirmed)).all():
        issues.append(
            {
                "code": "paid_without_confirmation_entry",
                "booking_id": str(payment.booking_id),
                "payment_id": str(payment.id),
                "amount_cents": payment.amount_cents,
            }
        )
    for payment, _ in session.execute(payment_query(refunded)).all():
        issues.append(
            {
                "code": "refunded_without_ledger_entry",
                "booking_id": str(payment.booking_id),
                "payment_id": str(payment.id),
                "amount_cents": payment.amount_cents,
            }
        )

    orphan_entries = (
        select(LedgerEntry)
        .join(Booking, Booking.id == LedgerEntry.booking_id)
        .outerjoin(BookingPayment, BookingPayment.id == LedgerEntry.booking_payment_id)
        .where(
            LedgerEntry.entry_type.in_({"PAYMENT_CONFIRMED", "PAYMENT_REFUNDED"}),
            BookingPayment.id.is_(None),
        )
    )
    if organization_id is not None:
        orphan_entries = orphan_entries.where(Booking.organization_id == organization_id)
    for entry in session.scalars(orphan_entries).all():
        issues.append(
            {
                "code": "ledger_entry_without_payment",
                "booking_id": str(entry.booking_id),
                "ledger_entry_id": str(entry.id),
                "amount_cents": entry.amount_cents,
            }
        )

    release_ledger = and_(
        LedgerEntry.booking_id == VenueRelease.booking_id,
        LedgerEntry.entry_type == "VENUE_RELEASE",
    )
    released = (
        select(VenueRelease, LedgerEntry.id)
        .join(Booking, Booking.id == VenueRelease.booking_id)
        .outerjoin(LedgerEntry, release_ledger)
        .where(VenueRelease.status == "RELEASED", LedgerEntry.id.is_(None))
    )
    if organization_id is not None:
        released = released.where(Booking.organization_id == organization_id)
    for release, _ in session.execute(released).all():
        issues.append(
            {
                "code": "release_without_ledger_entry",
                "booking_id": str(release.booking_id),
                "release_id": str(release.id),
                "amount_cents": release.amount_cents,
            }
        )

    orphan_release_entries = (
        select(LedgerEntry)
        .join(Booking, Booking.id == LedgerEntry.booking_id)
        .outerjoin(VenueRelease, VenueRelease.booking_id == LedgerEntry.booking_id)
        .where(
            LedgerEntry.entry_type == "VENUE_RELEASE",
            VenueRelease.id.is_(None),
        )
    )
    if organization_id is not None:
        orphan_release_entries = orphan_release_entries.where(
            Booking.organization_id == organization_id
        )
    for entry in session.scalars(orphan_release_entries).all():
        issues.append(
            {
                "code": "release_entry_without_record",
                "booking_id": str(entry.booking_id),
                "ledger_entry_id": str(entry.id),
                "amount_cents": entry.amount_cents,
            }
        )

    paid_totals = (
        select(
            BookingPayment.booking_id,
            func.coalesce(func.sum(BookingPayment.amount_cents), 0),
        )
        .where(BookingPayment.status == "PAID")
        .group_by(BookingPayment.booking_id)
        .subquery()
    )
    mismatched = (
        select(VenueRelease, paid_totals.c[1])
        .join(Booking, Booking.id == VenueRelease.booking_id)
        .join(paid_totals, paid_totals.c[0] == VenueRelease.booking_id)
        .where(
            VenueRelease.status.in_({"PENDING", "RELEASED"}),
            VenueRelease.amount_cents != paid_totals.c[1],
        )
    )
    if organization_id is not None:
        mismatched = mismatched.where(Booking.organization_id == organization_id)
    for release, paid_total in session.execute(mismatched).all():
        issues.append(
            {
                "code": "release_amount_mismatch",
                "booking_id": str(release.booking_id),
                "release_id": str(release.id),
                "amount_cents": release.amount_cents,
                "paid_cents": int(paid_total),
            }
        )

    completed_without_release = (
        select(Booking, paid_totals.c[1])
        .join(paid_totals, paid_totals.c[0] == Booking.id)
        .outerjoin(VenueRelease, VenueRelease.booking_id == Booking.id)
        .where(
            Booking.status == "COMPLETED",
            paid_totals.c[1] > 0,
            VenueRelease.id.is_(None),
        )
    )
    if organization_id is not None:
        completed_without_release = completed_without_release.where(
            Booking.organization_id == organization_id
        )
    for booking, paid_total in session.execute(completed_without_release).all():
        issues.append(
            {
                "code": "completed_booking_without_release",
                "booking_id": str(booking.id),
                "amount_cents": int(paid_total),
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
