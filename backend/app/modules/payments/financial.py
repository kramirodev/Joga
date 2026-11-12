"""Casos de uso da interface financeira: liberações, contestações e extrato (Fase 15).

Implementação técnica de referência. Prazo de liberação, janela de contestação,
regra de repasse e tratamento de divergência NÃO são decisões aprovadas; ver
harness/build/phase-15-interface-financeira.md e docs/PENDENCIAS.md.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, aliased

from app.core.config import get_settings
from app.modules.bookings.models import Booking, BookingPayment
from app.modules.bookings.service import BookingNotFound
from app.modules.identity.audit import record_audit
from app.modules.identity.clock import utcnow
from app.modules.payments.models import FinancialDispute, LedgerEntry, VenueRelease

DISPUTE_DECISIONS = frozenset({"ACCEPTED", "REJECTED"})


class FinancialError(Exception):
    """Erro base da interface financeira."""


class ReleaseNotFound(FinancialError):
    """Não há valor liberável para a reserva informada."""


class DisputeNotFound(FinancialError):
    """Contestação inexistente na organização."""


class DisputeConflict(FinancialError):
    """Já existe contestação aberta para a reserva."""


class DisputeStateError(FinancialError):
    """Contestação não está aberta para decisão."""


class OperatorNotAuthorized(FinancialError):
    """Operador não autorizado a decidir contestações."""


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class FinancialService:
    """Registra liberações e contestações sem movimentar dinheiro real."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_release(self, booking_id: uuid.UUID) -> VenueRelease | None:
        """Cria o registro de liberação pendente de uma reserva concluída."""

        booking = self.session.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if booking is None:
            raise BookingNotFound
        existing = self.session.scalar(
            select(VenueRelease).where(VenueRelease.booking_id == booking.id)
        )
        if existing is not None:
            return existing
        if booking.status not in {"CONFIRMED", "COMPLETED"}:
            return None

        total = self._paid_total(booking.id)
        if total <= 0:
            return None

        starts_at = _as_utc(booking.starts_at)
        release = VenueRelease(
            organization_id=booking.organization_id,
            booking_id=booking.id,
            amount_cents=total,
            status="PENDING",
            eligible_at=starts_at + timedelta(hours=get_settings().release_delay_hours),
        )
        self.session.add(release)
        self.session.flush()
        return release

    def ensure_missing_releases(self) -> int:
        """Cria liberações para reservas concluídas que ainda não têm registro."""

        existing = select(VenueRelease.booking_id)
        booking_ids = list(
            self.session.scalars(
                select(Booking.id).where(
                    Booking.status.in_({"CONFIRMED", "COMPLETED"}),
                    Booking.id.not_in(existing),
                )
            ).all()
        )
        created = 0
        for booking_id in booking_ids:
            if self.ensure_release(booking_id) is not None:
                created += 1
        return created

    def release_due(self, now: datetime | None = None) -> int:
        """Libera valores vencidos que não estejam em contestação aberta."""

        current = _as_utc(now or utcnow())
        open_disputes = select(FinancialDispute.booking_id).where(FinancialDispute.status == "OPEN")
        releases = list(
            self.session.scalars(
                select(VenueRelease)
                .where(
                    VenueRelease.status == "PENDING",
                    VenueRelease.eligible_at <= current,
                    VenueRelease.booking_id.not_in(open_disputes),
                )
                .order_by(VenueRelease.eligible_at, VenueRelease.id)
                .with_for_update(skip_locked=True)
            ).all()
        )
        released = 0
        for release in releases:
            booking = self.session.get(Booking, release.booking_id)
            if booking is None or booking.status not in {"CONFIRMED", "COMPLETED"}:
                self._fail(release, "booking_not_fulfilled", current)
                continue
            if self._paid_total(booking.id) != release.amount_cents:
                self._fail(release, "amount_mismatch", current)
                continue
            if self._release(release, current, reason="auto_release"):
                released += 1
        return released

    def list_receivables(
        self,
        organization_id: uuid.UUID,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[tuple[VenueRelease, Booking, uuid.UUID | None]]:
        dispute = aliased(FinancialDispute)
        statement = (
            select(VenueRelease, Booking, dispute.id)
            .join(Booking, Booking.id == VenueRelease.booking_id)
            .outerjoin(
                dispute,
                and_(
                    dispute.booking_id == VenueRelease.booking_id,
                    dispute.status == "OPEN",
                ),
            )
            .where(VenueRelease.organization_id == organization_id)
            .order_by(
                VenueRelease.eligible_at.desc(),
                VenueRelease.created_at.desc(),
                VenueRelease.id,
            )
            .offset(offset)
            .limit(limit)
        )
        if status is not None:
            statement = statement.where(VenueRelease.status == status)
        return [
            (release, booking, dispute_id)
            for release, booking, dispute_id in self.session.execute(statement).all()
        ]

    def statement(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[LedgerEntry]:
        return list(
            self.session.scalars(
                select(LedgerEntry)
                .join(Booking, Booking.id == LedgerEntry.booking_id)
                .where(Booking.organization_id == organization_id)
                .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )

    def release_totals(self, organization_id: uuid.UUID) -> dict[str, int]:
        rows = self.session.execute(
            select(
                VenueRelease.status,
                func.coalesce(func.sum(VenueRelease.amount_cents), 0),
            )
            .where(VenueRelease.organization_id == organization_id)
            .group_by(VenueRelease.status)
        ).all()
        totals = {str(status): int(amount) for status, amount in rows}
        disputed = self.session.scalar(
            select(func.coalesce(func.sum(FinancialDispute.amount_cents), 0)).where(
                FinancialDispute.organization_id == organization_id,
                FinancialDispute.status == "OPEN",
            )
        )
        return {
            "pending_release_cents": totals.get("PENDING", 0),
            "released_cents": totals.get("RELEASED", 0),
            "disputed_cents": int(disputed or 0),
        }

    def open_dispute(
        self,
        *,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        booking_id: uuid.UUID,
        reason: str,
        evidence: str | None = None,
    ) -> FinancialDispute:
        booking = self.session.get(Booking, booking_id)
        if booking is None or booking.organization_id != organization_id:
            raise BookingNotFound
        release = self.session.scalar(
            select(VenueRelease).where(VenueRelease.booking_id == booking.id)
        )
        if release is None:
            release = self.ensure_release(booking.id)
        if release is None:
            raise ReleaseNotFound
        existing = self.session.scalar(
            select(FinancialDispute).where(
                FinancialDispute.booking_id == booking.id,
                FinancialDispute.status == "OPEN",
            )
        )
        if existing is not None:
            raise DisputeConflict

        dispute = FinancialDispute(
            organization_id=organization_id,
            booking_id=booking.id,
            release_id=release.id,
            amount_cents=release.amount_cents,
            status="OPEN",
            reason=reason,
            evidence=evidence,
            created_by=actor_user_id,
        )
        self.session.add(dispute)
        self.session.flush()
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            action="financial.dispute_opened",
            resource_type="financial_dispute",
            resource_id=dispute.id,
            organization_id=organization_id,
            reason=reason,
            details={
                "booking_id": str(booking.id),
                "amount_cents": dispute.amount_cents,
            },
        )
        self.session.flush()
        return dispute

    def list_disputes(
        self,
        organization_id: uuid.UUID,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FinancialDispute]:
        statement = (
            select(FinancialDispute)
            .where(FinancialDispute.organization_id == organization_id)
            .order_by(FinancialDispute.created_at.desc(), FinancialDispute.id.desc())
            .offset(offset)
            .limit(limit)
        )
        if status is not None:
            statement = statement.where(FinancialDispute.status == status)
        return list(self.session.scalars(statement).all())

    def get_dispute(self, organization_id: uuid.UUID, dispute_id: uuid.UUID) -> FinancialDispute:
        dispute = self.session.get(FinancialDispute, dispute_id)
        if dispute is None or dispute.organization_id != organization_id:
            raise DisputeNotFound
        return dispute

    def decide_dispute(
        self,
        dispute_id: uuid.UUID,
        *,
        operator: str,
        decision: str,
        reason: str,
        authorized_operators: frozenset[str] | None = None,
    ) -> FinancialDispute:
        allowed = (
            authorized_operators
            if authorized_operators is not None
            else get_settings().review_operator_ids
        )
        if operator not in allowed:
            raise OperatorNotAuthorized
        if decision not in DISPUTE_DECISIONS:
            raise DisputeStateError

        dispute = self.session.scalar(
            select(FinancialDispute).where(FinancialDispute.id == dispute_id).with_for_update()
        )
        if dispute is None:
            raise DisputeNotFound
        if dispute.status != "OPEN":
            raise DisputeStateError

        current = utcnow()
        dispute.status = decision
        dispute.decision_reason = reason
        dispute.decided_by = operator
        dispute.decided_at = current
        record_audit(
            self.session,
            actor_user_id=None,
            action="financial.dispute_decided",
            resource_type="financial_dispute",
            resource_id=dispute.id,
            organization_id=dispute.organization_id,
            reason=reason,
            details={"operator": operator, "decision": decision},
        )
        if decision == "ACCEPTED" and dispute.release_id is not None:
            release = self.session.get(VenueRelease, dispute.release_id)
            if release is not None:
                self._release(release, current, reason="dispute_accepted")
        self.session.flush()
        return dispute

    def _release(self, release: VenueRelease, now: datetime, *, reason: str) -> bool:
        if release.status != "PENDING":
            return False
        existing = self.session.scalar(
            select(LedgerEntry).where(
                LedgerEntry.booking_id == release.booking_id,
                LedgerEntry.entry_type == "VENUE_RELEASE",
            )
        )
        details: dict[str, Any] = {
            "release_id": str(release.id),
            "simulated": True,
            "provider": get_settings().psp_provider,
            "reason": reason,
        }
        if existing is None:
            self.session.add(
                LedgerEntry(
                    booking_id=release.booking_id,
                    booking_payment_id=None,
                    entry_type="VENUE_RELEASE",
                    direction="CREDIT",
                    amount_cents=release.amount_cents,
                    details=details,
                )
            )
        release.status = "RELEASED"
        release.released_at = now
        release.reason = reason
        release.provider_reference = f"simulated:{release.id}"
        record_audit(
            self.session,
            actor_user_id=None,
            action="financial.release",
            resource_type="venue_release",
            resource_id=release.id,
            organization_id=release.organization_id,
            details={
                "booking_id": str(release.booking_id),
                "amount_cents": release.amount_cents,
                "reason": reason,
            },
        )
        self.session.flush()
        return True

    def _fail(self, release: VenueRelease, reason: str, now: datetime) -> None:
        if release.status != "PENDING":
            return
        release.status = "FAILED"
        release.reason = reason
        release.failed_at = now
        record_audit(
            self.session,
            actor_user_id=None,
            action="financial.release_failed",
            resource_type="venue_release",
            resource_id=release.id,
            organization_id=release.organization_id,
            reason=reason,
            details={"booking_id": str(release.booking_id)},
        )
        self.session.flush()

    def _paid_total(self, booking_id: uuid.UUID) -> int:
        total = self.session.scalar(
            select(func.coalesce(func.sum(BookingPayment.amount_cents), 0)).where(
                BookingPayment.booking_id == booking_id,
                BookingPayment.status == "PAID",
            )
        )
        return int(total or 0)


__all__ = [
    "DisputeConflict",
    "DisputeNotFound",
    "DisputeStateError",
    "FinancialError",
    "FinancialService",
    "OperatorNotAuthorized",
    "ReleaseNotFound",
]
