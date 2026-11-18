"""Casos de uso da interface financeira: liberações, contestações e extrato (Fase 15).

Implementação técnica de referência. Prazo de liberação, janela de contestação,
regra de repasse e tratamento de divergência NÃO são decisões aprovadas; ver
harness/build/phase-15-interface-financeira.md e docs/PENDENCIAS.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, aliased

from app.core.config import get_settings
from app.modules.bookings.models import Booking
from app.modules.bookings.service import BookingNotFound
from app.modules.identity.audit import record_audit
from app.modules.identity.clock import utcnow
from app.modules.payments.models import FinancialDispute, VenueRelease
from app.modules.payments.statement import (
    StatementRow,
)
from app.modules.payments.statement import (
    count_statement as project_count_statement,
)
from app.modules.payments.statement import statement as project_statement

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


class DisputeDeadlineExpired(FinancialError):
    """A janela técnica de contestação da reserva já passou."""


class ReleaseNotContestable(FinancialError):
    """A liberação não está pendente; não há valor a contestar."""


class OperatorNotAuthorized(FinancialError):
    """Operador não autorizado a decidir contestações."""


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def dispute_deadline(release: VenueRelease) -> datetime:
    """Prazo de contestação persistido no snapshot da liberação.

    A janela é definida em ``JOGA_DISPUTE_WINDOW_HOURS`` no momento da criação
    da liberação e não é recalculada depois.
    """

    return _as_utc(release.dispute_deadline)


@dataclass(frozen=True)
class CommissionRow:
    """Linha do relatório de comissão: valor do fornecedor e taxa separados."""

    booking_id: uuid.UUID
    starts_at: datetime
    confirmed_at: datetime
    venue_price_cents: int
    fee_cents: int
    total_cents: int
    release_status: str | None


class FinancialService:
    """Registra liberações e contestações sem movimentar dinheiro real."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_release(self, booking_id: uuid.UUID) -> VenueRelease | None:
        """Cria a obrigação de repasse de uma reserva confirmada/concluída."""

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

        # O valor devido é o preço da quadra congelado na reserva. Não usar a
        # soma de ``booking_payments``: no fluxo de ingresso as cobranças Pix
        # são canceladas e a quitação acontece na carteira.
        total = booking.venue_price_cents or booking.price_cents
        if total <= 0:
            return None

        starts_at = _as_utc(booking.starts_at)
        eligible_at = starts_at + timedelta(hours=get_settings().release_delay_hours)
        release = VenueRelease(
            organization_id=booking.organization_id,
            booking_id=booking.id,
            amount_cents=total,
            status="PENDING",
            eligible_at=eligible_at,
            dispute_deadline=eligible_at + timedelta(hours=get_settings().dispute_window_hours),
        )
        self.session.add(release)
        self.session.flush()
        return release

    def ensure_missing_releases(self) -> int:
        """Cria obrigações para reservas confirmadas/concluídas sem registro."""

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

    def reverse_for_refund(
        self,
        booking_id: uuid.UUID,
        *,
        reason: str,
        now: datetime | None = None,
    ) -> VenueRelease | None:
        """Reverte a obrigação de repasse quando a reserva é reembolsada.

        Se o valor já foi liberado, o status vira REVERSED como registro
        contábil; a recuperação efetiva continua manual e auditada.
        """

        release = self.session.scalar(
            select(VenueRelease).where(VenueRelease.booking_id == booking_id).with_for_update()
        )
        if release is None or release.status in {"REVERSED", "FAILED"}:
            return release
        previous = release.status
        moment = _as_utc(now or utcnow())
        release.status = "REVERSED"
        release.reversed_at = moment
        release.reason = reason[:200]
        record_audit(
            self.session,
            actor_user_id=None,
            organization_id=release.organization_id,
            action="financial.release_reversed",
            resource_type="venue_release",
            resource_id=release.id,
            details={"reason": reason, "previous_status": previous},
        )
        self.session.flush()
        return release

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
            if (booking.venue_price_cents or booking.price_cents) != release.amount_cents:
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

    def count_receivables(
        self,
        organization_id: uuid.UUID,
        *,
        status: str | None = None,
    ) -> int:
        conditions = [VenueRelease.organization_id == organization_id]
        if status is not None:
            conditions.append(VenueRelease.status == status)
        return int(
            self.session.scalar(select(func.count()).select_from(VenueRelease).where(*conditions))
            or 0
        )

    def statement(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[StatementRow]:
        return project_statement(
            self.session, organization_id=organization_id, limit=limit, offset=offset
        )

    def count_statement(self, organization_id: uuid.UUID) -> int:
        return project_count_statement(self.session, organization_id=organization_id)

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
            "reversed_cents": totals.get("REVERSED", 0),
            "failed_cents": totals.get("FAILED", 0),
            "disputed_cents": int(disputed or 0),
        }

    def commission_rows(
        self,
        organization_id: uuid.UUID,
        *,
        from_: datetime | None = None,
        to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CommissionRow]:
        """Relatório por reserva, com valor do fornecedor e taxa do JOGA separados.

        Só entram reservas confirmadas com preço congelado. O filtro de período
        usa ``confirmed_at`` (competência do fato financeiro).
        """

        release = aliased(VenueRelease)
        query = (
            select(Booking, release.status)
            .outerjoin(release, release.booking_id == Booking.id)
            .where(
                Booking.organization_id == organization_id,
                Booking.confirmed_at.is_not(None),
                Booking.total_cents > 0,
            )
            .order_by(Booking.starts_at.desc(), Booking.id)
            .offset(offset)
            .limit(limit)
        )
        if from_ is not None:
            query = query.where(Booking.confirmed_at >= _as_utc(from_))
        if to is not None:
            query = query.where(Booking.confirmed_at <= _as_utc(to))
        rows: list[CommissionRow] = []
        for booking, release_status in self.session.execute(query).all():
            assert booking.confirmed_at is not None  # garantido pelo filtro SQL
            rows.append(
                CommissionRow(
                    booking_id=booking.id,
                    starts_at=_as_utc(booking.starts_at),
                    confirmed_at=_as_utc(booking.confirmed_at),
                    venue_price_cents=booking.venue_price_cents,
                    fee_cents=booking.fee_cents,
                    total_cents=booking.total_cents,
                    release_status=release_status,
                )
            )
        return rows

    def commission_totals(
        self,
        organization_id: uuid.UUID,
        *,
        from_: datetime | None = None,
        to: datetime | None = None,
    ) -> dict[str, int]:
        """Totais do relatório; a taxa do JOGA nunca inclui o valor do fornecedor."""

        conditions = [
            Booking.organization_id == organization_id,
            Booking.confirmed_at.is_not(None),
            Booking.total_cents > 0,
        ]
        if from_ is not None:
            conditions.append(Booking.confirmed_at >= _as_utc(from_))
        if to is not None:
            conditions.append(Booking.confirmed_at <= _as_utc(to))
        venue, fee, total, count = self.session.execute(
            select(
                func.coalesce(func.sum(Booking.venue_price_cents), 0),
                func.coalesce(func.sum(Booking.fee_cents), 0),
                func.coalesce(func.sum(Booking.total_cents), 0),
                func.count(),
            ).where(*conditions)
        ).one()
        return {
            "bookings": int(count or 0),
            "venue_price_cents": int(venue or 0),
            "joga_fee_cents": int(fee or 0),
            "total_cents": int(total or 0),
        }

    def block_for_chargeback(
        self,
        booking_id: uuid.UUID,
        *,
        reason: str,
        now: datetime | None = None,
    ) -> VenueRelease | None:
        """Bloqueia o repasse por MED/chargeback, sem transferência real.

        O hook é chamado pelo fluxo de 14B quando o MED existir. Enquanto isso,
        é uma salvaguarda testável: ``PENDING`` vira ``FAILED`` e ``RELEASED``
        vira ``REVERSED`` com auditoria. Nenhum saldo é editado.
        """

        release = self.session.scalar(
            select(VenueRelease).where(VenueRelease.booking_id == booking_id).with_for_update()
        )
        if release is None or release.status in {"REVERSED", "FAILED"}:
            return release
        moment = _as_utc(now or utcnow())
        previous = release.status
        if release.status == "RELEASED":
            release.status = "REVERSED"
            release.reversed_at = moment
        else:
            release.status = "FAILED"
            release.failed_at = moment
        release.reason = reason[:200]
        record_audit(
            self.session,
            actor_user_id=None,
            action="financial.release_blocked",
            resource_type="venue_release",
            resource_id=release.id,
            organization_id=release.organization_id,
            reason=reason,
            details={
                "booking_id": str(release.booking_id),
                "previous_status": previous,
                "reason": "chargeback",
            },
        )
        self.session.flush()
        return release

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
            select(VenueRelease).where(VenueRelease.booking_id == booking.id).with_for_update()
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
        if release.status != "PENDING":
            raise ReleaseNotContestable
        if _as_utc(utcnow()) > dispute_deadline(release):
            raise DisputeDeadlineExpired

        dispute = FinancialDispute(
            organization_id=organization_id,
            booking_id=booking.id,
            release_id=release.id,
            amount_cents=release.amount_cents,
            status="OPEN",
            deadline_at=dispute_deadline(release),
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

    def count_disputes(
        self,
        organization_id: uuid.UUID,
        *,
        status: str | None = None,
    ) -> int:
        conditions = [FinancialDispute.organization_id == organization_id]
        if status is not None:
            conditions.append(FinancialDispute.status == status)
        return int(
            self.session.scalar(
                select(func.count()).select_from(FinancialDispute).where(*conditions)
            )
            or 0
        )

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
        organization_id: uuid.UUID | None = None,
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
        if organization_id is not None and dispute.organization_id != organization_id:
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
        release.status = "RELEASED"
        release.released_at = now
        release.reason = reason
        release.provider_reference = f"simulated:{release.id}"
        from app.modules.ledger.flow import post_release

        post_release(self.session, release, now=now)
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


__all__ = [
    "CommissionRow",
    "DisputeConflict",
    "DisputeDeadlineExpired",
    "DisputeNotFound",
    "DisputeStateError",
    "FinancialError",
    "FinancialService",
    "OperatorNotAuthorized",
    "ReleaseNotContestable",
    "ReleaseNotFound",
    "dispute_deadline",
]
