"""Fila de substitutos e cancelamento individual com T4/T5 (ADR 0039)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.bookings.models import (
    Booking,
    BookingEvent,
    BookingParticipant,
    BookingPayment,
    BookingRefundExclusion,
    BookingSubstitution,
)
from app.modules.bookings.service import BookingNotFound, BookingService
from app.modules.identity.audit import record_audit
from app.modules.identity.clock import utcnow
from app.modules.identity.models import User
from app.modules.matchmaking.models import Lobby, LobbyParticipant, LobbySubstitute
from app.modules.organizations.permissions import Capability
from app.modules.organizations.service import (
    Forbidden,
    OrganizationNotFound,
    OrganizationService,
)
from app.modules.ratings.trust import TrustService

MIN_WINDOW_BEFORE_CUTOFF = timedelta(minutes=15)


class SubstitutionError(Exception):
    """Erro base de substituição/cancelamento individual."""


class LobbyNotFound(SubstitutionError):
    """Lobby inexistente ou não está agendado."""


class QueueConflict(SubstitutionError):
    """Usuário já está na fila, é titular ou não pode sair agora."""


class QueueForbidden(SubstitutionError):
    """Usuário sem acesso à fila do lobby."""


class ParticipantNotFound(SubstitutionError):
    """Participante ativo não encontrado na reserva."""


class CancellationClosed(SubstitutionError):
    """Cutoff de cancelamento já passou."""


class SubstitutionConflict(SubstitutionError):
    """Reserva não está no estado que permite cancelamento individual."""


class SubstitutionForbidden(SubstitutionError):
    """Ator sem permissão para atribuir substituto."""


class SubstitutionNotFound(SubstitutionError):
    """Vaga de substituição inexistente."""


class SubstituteIneligible(SubstitutionError):
    """Substituto inválido, inativo ou já participante."""


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class LobbySubstituteService:
    """Mantém a fila de substitutos em standby de um lobby."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def join(self, user_id: uuid.UUID, lobby_id: uuid.UUID) -> LobbySubstitute:
        lobby = self.session.get(Lobby, lobby_id)
        if lobby is None or lobby.status != "scheduled":
            raise LobbyNotFound
        participant = self.session.scalar(
            select(LobbyParticipant).where(
                LobbyParticipant.lobby_id == lobby_id,
                LobbyParticipant.user_id == user_id,
            )
        )
        if participant is not None:
            raise QueueConflict("already_participant")
        existing = self.session.scalar(
            select(LobbySubstitute).where(
                LobbySubstitute.lobby_id == lobby_id,
                LobbySubstitute.user_id == user_id,
            )
        )
        if existing is not None:
            if existing.status in {"PLAYED", "NO_SHOW", "DECLINED"}:
                existing.status = "STANDBY"
                existing.position = self._next_position(lobby_id)
                existing.called_at = None
                existing.confirmed_at = None
                existing.played_at = None
                self.session.flush()
            return existing

        substitute = LobbySubstitute(
            lobby_id=lobby_id,
            user_id=user_id,
            status="STANDBY",
            position=self._next_position(lobby_id),
        )
        self.session.add(substitute)
        self.session.flush()
        return substitute

    def leave(self, user_id: uuid.UUID, lobby_id: uuid.UUID) -> None:
        substitute = self.session.scalar(
            select(LobbySubstitute).where(
                LobbySubstitute.lobby_id == lobby_id,
                LobbySubstitute.user_id == user_id,
            )
        )
        if substitute is None:
            return
        if substitute.status not in {"STANDBY", "CALLED", "CONFIRMED"}:
            raise QueueConflict("queue_entry_not_removable")
        self.session.delete(substitute)
        self.session.flush()

    def list_for_lobby(
        self, actor_user_id: uuid.UUID, lobby_id: uuid.UUID
    ) -> list[LobbySubstitute]:
        self._require_view(actor_user_id, lobby_id)
        return list(
            self.session.scalars(
                select(LobbySubstitute)
                .where(LobbySubstitute.lobby_id == lobby_id)
                .order_by(LobbySubstitute.position, LobbySubstitute.created_at)
            ).all()
        )

    def _require_view(self, actor_user_id: uuid.UUID, lobby_id: uuid.UUID) -> None:
        participant = self.session.scalar(
            select(LobbyParticipant.id).where(
                LobbyParticipant.lobby_id == lobby_id,
                LobbyParticipant.user_id == actor_user_id,
            )
        )
        substitute = self.session.scalar(
            select(LobbySubstitute.id).where(
                LobbySubstitute.lobby_id == lobby_id,
                LobbySubstitute.user_id == actor_user_id,
            )
        )
        if participant is None and substitute is None:
            raise QueueForbidden

    def _next_position(self, lobby_id: uuid.UUID) -> int:
        current = self.session.scalar(
            select(func.max(LobbySubstitute.position)).where(LobbySubstitute.lobby_id == lobby_id)
        )
        return int(current or 0) + 1


class BookingSubstitutionService:
    """Abre e resolve a janela T4 de uma vaga desistente."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.bookings = BookingService(session)

    def cancel_participant(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> BookingSubstitution:
        booking = self.session.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if booking is None:
            raise BookingNotFound
        if booking.status != "CONFIRMED":
            raise SubstitutionConflict("booking_not_confirmed")
        existing = self.session.scalar(
            select(BookingSubstitution).where(
                BookingSubstitution.booking_id == booking.id,
                BookingSubstitution.outgoing_user_id == actor_user_id,
                BookingSubstitution.status == "OPEN",
            )
        )
        if existing is not None:
            return existing
        participant = self.session.scalar(
            select(BookingParticipant).where(
                BookingParticipant.booking_id == booking.id,
                BookingParticipant.user_id == actor_user_id,
                BookingParticipant.active.is_(True),
            )
        )
        if participant is None:
            raise ParticipantNotFound

        current = _aware(now or utcnow())
        starts_at = _aware(booking.starts_at)
        settings = get_settings()
        cutoff = starts_at - timedelta(hours=settings.cancellation_cutoff_hours)
        if current >= cutoff:
            raise CancellationClosed

        existing = self.session.scalar(
            select(BookingSubstitution).where(
                BookingSubstitution.booking_id == booking.id,
                BookingSubstitution.seat == participant.seat,
                BookingSubstitution.status == "OPEN",
            )
        )
        if existing is not None:
            return existing

        remaining = starts_at - current
        window = remaining * (settings.substitution_window_percent / 100)
        window = max(window, timedelta(minutes=settings.substitution_window_min_minutes))
        window = min(window, timedelta(hours=settings.substitution_window_max_hours))
        deadline = min(current + window, cutoff)
        if deadline - current < MIN_WINDOW_BEFORE_CUTOFF:
            raise CancellationClosed

        participant.active = False
        participant.left_at = current
        substitution = BookingSubstitution(
            booking_id=booking.id,
            seat=participant.seat,
            outgoing_user_id=actor_user_id,
            status="OPEN",
            deadline_at=deadline,
            reason="participant_cancelled",
        )
        self.session.add(substitution)
        TrustService(self.session).apply_event(
            actor_user_id,
            "cancel_after_confirmation",
            details={"booking_id": str(booking.id), "seat": participant.seat},
            now=current,
        )
        self.session.add(
            BookingRefundExclusion(
                booking_id=booking.id,
                user_id=actor_user_id,
                reason="participant_cancelled",
            )
        )
        self.session.add(
            BookingEvent(
                booking_id=booking.id,
                actor_user_id=actor_user_id,
                event_type="participant.left",
                from_status=booking.status,
                to_status=booking.status,
                reason="participant_cancelled",
                details={
                    "seat": participant.seat,
                    "substitution_deadline_at": deadline.isoformat(),
                },
            )
        )
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            action="booking.participant_left",
            resource_type="booking",
            resource_id=booking.id,
            organization_id=booking.organization_id,
            details={"seat": participant.seat, "deadline_at": deadline.isoformat()},
        )
        self.session.flush()
        self.maybe_call_for_parity(booking, current)
        self.session.flush()
        return substitution

    def mark_no_show(
        self,
        actor_user_id: uuid.UUID | None,
        booking_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        reason: str | None = None,
        auto_call: bool = True,
        now: datetime | None = None,
    ) -> BookingSubstitution:
        """Marca ausência após o cutoff e abre vaga em seat já pago."""

        booking = self.session.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if booking is None:
            raise BookingNotFound
        if actor_user_id is not None:
            self._require_manager(actor_user_id, booking)
        if booking.status != "CONFIRMED":
            raise SubstitutionConflict("booking_not_confirmed")

        current = _aware(now or utcnow())
        starts_at = _aware(booking.starts_at)
        cutoff = starts_at - timedelta(hours=get_settings().cancellation_cutoff_hours)
        if current < cutoff:
            raise SubstitutionConflict("cutoff_not_reached")

        participant = self.session.scalar(
            select(BookingParticipant).where(
                BookingParticipant.booking_id == booking.id,
                BookingParticipant.user_id == user_id,
                BookingParticipant.active.is_(True),
            )
        )
        if participant is None:
            raise ParticipantNotFound
        existing = self.session.scalar(
            select(BookingSubstitution).where(
                BookingSubstitution.booking_id == booking.id,
                BookingSubstitution.seat == participant.seat,
                BookingSubstitution.status == "OPEN",
                BookingSubstitution.paid_seat.is_(True),
            )
        )
        if existing is not None:
            return existing

        participant.active = False
        participant.left_at = current
        substitution = BookingSubstitution(
            booking_id=booking.id,
            seat=participant.seat,
            outgoing_user_id=user_id,
            status="OPEN",
            paid_seat=True,
            deadline_at=current
            + timedelta(minutes=get_settings().late_substitution_window_minutes),
            reason="no_show",
        )
        self.session.add(substitution)
        TrustService(self.session).apply_event(
            user_id,
            "no_show",
            details={"booking_id": str(booking.id), "seat": participant.seat},
            now=current,
        )
        self.session.add(
            BookingEvent(
                booking_id=booking.id,
                actor_user_id=actor_user_id,
                event_type="participant.no_show",
                from_status=booking.status,
                to_status=booking.status,
                reason=reason or "no_show",
                details={
                    "seat": participant.seat,
                    "user_id": str(user_id),
                    "substitution_deadline_at": substitution.deadline_at.isoformat(),
                },
            )
        )
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            action="booking.participant_no_show",
            resource_type="booking",
            resource_id=booking.id,
            organization_id=booking.organization_id,
            reason=reason,
            details={"seat": participant.seat, "user_id": str(user_id)},
        )
        self.session.flush()
        if auto_call:
            self.maybe_call_for_parity(booking, current)
        self.session.flush()
        return substitution

    def assign(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
        substitution_id: uuid.UUID,
        substitute_user_id: uuid.UUID,
        *,
        allow_called_user: bool = False,
        now: datetime | None = None,
    ) -> BookingSubstitution:
        """Atribui um substituto e abre a cobrança da vaga."""

        booking = self.session.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if booking is None:
            raise BookingNotFound
        substitution = self.session.scalar(
            select(BookingSubstitution)
            .where(
                BookingSubstitution.id == substitution_id,
                BookingSubstitution.booking_id == booking.id,
            )
            .with_for_update()
        )
        if substitution is None:
            raise SubstitutionNotFound
        called_user = (
            substitution.status == "CALLED"
            and substitution.called_user_id == actor_user_id
            and substitute_user_id == actor_user_id
        )
        if not (allow_called_user and called_user):
            self._require_manager(actor_user_id, booking)
        if substitution.status == "FILLED":
            return substitution
        if substitution.status == "AWAITING_PAYMENT":
            if substitution.filled_by_user_id == substitute_user_id:
                return substitution
            raise SubstitutionConflict("substitution_already_assigned")
        if substitution.status not in {"OPEN", "CALLED"}:
            raise SubstitutionConflict("substitution_not_open")

        current = _aware(now or utcnow())
        if current >= _aware(substitution.deadline_at):
            raise SubstitutionConflict("substitution_deadline_expired")
        if substitute_user_id == substitution.outgoing_user_id:
            raise SubstituteIneligible("same_user")
        user = self.session.get(User, substitute_user_id)
        if user is None or user.status != "active":
            raise SubstituteIneligible("user_not_active")
        duplicate = self.session.scalar(
            select(BookingParticipant).where(
                BookingParticipant.booking_id == booking.id,
                BookingParticipant.user_id == substitute_user_id,
                BookingParticipant.active.is_(True),
            )
        )
        if duplicate is not None:
            raise SubstituteIneligible("already_participant")
        outgoing = self.session.scalar(
            select(BookingParticipant).where(
                BookingParticipant.booking_id == booking.id,
                BookingParticipant.user_id == substitution.outgoing_user_id,
            )
        )
        if outgoing is None:
            raise SubstitutionConflict("outgoing_participant_not_found")

        payment: BookingPayment | None = None
        if substitution.paid_seat:
            outgoing_payment = self.session.scalar(
                select(BookingPayment)
                .where(
                    BookingPayment.booking_id == booking.id,
                    BookingPayment.participant_id == outgoing.id,
                    BookingPayment.status == "PAID",
                )
                .order_by(BookingPayment.version.desc())
                .limit(1)
            )
            if outgoing_payment is None:
                raise SubstitutionConflict("outgoing_payment_not_found")
            participant = BookingParticipant(
                booking_id=booking.id,
                user_id=substitute_user_id,
                seat=substitution.seat,
                active=True,
                contribution_cents=outgoing.contribution_cents,
                payment_status="WAIVED",
            )
            self.session.add(participant)
            self.session.flush()
            substitution.status = "FILLED"
            substitution.resolved_at = current
            substitution.covered_by_payment_id = outgoing_payment.id
        else:
            participant = BookingParticipant(
                booking_id=booking.id,
                user_id=substitute_user_id,
                seat=substitution.seat,
                active=True,
                contribution_cents=outgoing.contribution_cents,
                payment_status="PENDING",
            )
            self.session.add(participant)
            self.session.flush()
            booking.payment_version += 1
            payment = BookingPayment(
                booking_id=booking.id,
                participant_id=participant.id,
                version=booking.payment_version,
                amount_cents=outgoing.contribution_cents,
                status="PENDING",
            )
            self.session.add(payment)
            self.session.flush()
            substitution.status = "AWAITING_PAYMENT"

        substitution.filled_by_user_id = substitute_user_id
        substitution.substitute_payment_id = payment.id if payment is not None else None
        substitution.called_user_id = None
        substitution.call_deadline_at = None
        if not substitution.paid_seat:
            booking.status = "PAYMENT_PENDING"
        queue_entry = self.session.scalar(
            select(LobbySubstitute).where(
                LobbySubstitute.lobby_id == booking.lobby_id,
                LobbySubstitute.user_id == substitute_user_id,
            )
        )
        if queue_entry is not None:
            queue_entry.status = "PLAYED" if substitution.paid_seat else "CONFIRMED"
            queue_entry.called_at = current
            queue_entry.confirmed_at = current
            if substitution.paid_seat:
                queue_entry.played_at = current

        self.session.add(
            BookingEvent(
                booking_id=booking.id,
                actor_user_id=actor_user_id,
                event_type="substitution.assigned",
                from_status="CONFIRMED",
                to_status=booking.status,
                details={
                    "substitution_id": str(substitution.id),
                    "seat": substitution.seat,
                    "substitute_user_id": str(substitute_user_id),
                    "payment_id": str(payment.id) if payment is not None else None,
                    "paid_seat": substitution.paid_seat,
                },
            )
        )
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            action="booking.substitute_assigned",
            resource_type="booking_substitution",
            resource_id=substitution.id,
            organization_id=booking.organization_id,
            details={
                "booking_id": str(booking.id),
                "seat": substitution.seat,
                "substitute_user_id": str(substitute_user_id),
                "paid_seat": substitution.paid_seat,
            },
        )
        self.session.flush()
        return substitution

    def list_for_booking(
        self, actor_user_id: uuid.UUID, booking_id: uuid.UUID
    ) -> list[BookingSubstitution]:
        self.bookings.get(actor_user_id, booking_id)
        return list(
            self.session.scalars(
                select(BookingSubstitution)
                .where(BookingSubstitution.booking_id == booking_id)
                .order_by(BookingSubstitution.created_at.desc())
            ).all()
        )

    def accept_call(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
        substitution_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> BookingSubstitution:
        substitution = self.session.scalar(
            select(BookingSubstitution).where(
                BookingSubstitution.id == substitution_id,
                BookingSubstitution.booking_id == booking_id,
            )
        )
        if substitution is None:
            raise SubstitutionNotFound
        if substitution.status != "CALLED" or substitution.called_user_id != actor_user_id:
            raise SubstitutionForbidden
        return self.assign(
            actor_user_id,
            booking_id,
            substitution_id,
            actor_user_id,
            allow_called_user=True,
            now=now,
        )

    def decline_call(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
        substitution_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> BookingSubstitution:
        booking = self.session.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if booking is None:
            raise BookingNotFound
        substitution = self.session.scalar(
            select(BookingSubstitution)
            .where(
                BookingSubstitution.id == substitution_id,
                BookingSubstitution.booking_id == booking.id,
            )
            .with_for_update()
        )
        if substitution is None:
            raise SubstitutionNotFound
        if substitution.status != "CALLED" or substitution.called_user_id != actor_user_id:
            raise SubstitutionForbidden
        current = _aware(now or utcnow())
        queue_entry = self.session.scalar(
            select(LobbySubstitute).where(
                LobbySubstitute.lobby_id == booking.lobby_id,
                LobbySubstitute.user_id == actor_user_id,
            )
        )
        if queue_entry is not None:
            queue_entry.status = "DECLINED"
        substitution.called_user_id = None
        substitution.call_deadline_at = None
        substitution.status = "OPEN"
        self.maybe_call_for_parity(booking, current)
        self.session.flush()
        return substitution

    def maybe_call_for_parity(self, booking: Booking, now: datetime) -> bool:
        """Chama no máximo um substituto por vez e só se o número estiver ímpar."""

        active = int(
            self.session.scalar(
                select(func.count())
                .select_from(BookingParticipant)
                .where(
                    BookingParticipant.booking_id == booking.id,
                    BookingParticipant.active.is_(True),
                )
            )
            or 0
        )
        called = self.session.scalar(
            select(BookingSubstitution)
            .where(
                BookingSubstitution.booking_id == booking.id,
                BookingSubstitution.status == "CALLED",
            )
            .order_by(BookingSubstitution.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if active % 2 == 0:
            if called is not None:
                queue_entry = self.session.scalar(
                    select(LobbySubstitute).where(
                        LobbySubstitute.lobby_id == booking.lobby_id,
                        LobbySubstitute.user_id == called.called_user_id,
                    )
                )
                if queue_entry is not None:
                    queue_entry.status = "STANDBY"
                    queue_entry.called_at = None
                called.called_user_id = None
                called.call_deadline_at = None
                called.status = "OPEN"
            return False
        if called is not None:
            return True
        open_substitution = self.session.scalar(
            select(BookingSubstitution)
            .where(
                BookingSubstitution.booking_id == booking.id,
                BookingSubstitution.status == "OPEN",
            )
            .order_by(BookingSubstitution.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if open_substitution is None:
            return False
        return self._call_next(booking, open_substitution, now)

    def _call_next(
        self,
        booking: Booking,
        substitution: BookingSubstitution,
        now: datetime,
    ) -> bool:
        if substitution.status not in {"OPEN", "CALLED"}:
            return False
        queue_entry = self.session.scalar(
            select(LobbySubstitute)
            .where(
                LobbySubstitute.lobby_id == booking.lobby_id,
                LobbySubstitute.status == "STANDBY",
            )
            .order_by(LobbySubstitute.position)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if queue_entry is None:
            substitution.called_user_id = None
            substitution.call_deadline_at = None
            if substitution.status == "CALLED":
                substitution.status = "OPEN"
            return False
        queue_entry.status = "CALLED"
        queue_entry.called_at = now
        substitution.called_user_id = queue_entry.user_id
        substitution.call_deadline_at = now + timedelta(
            minutes=get_settings().substitution_call_timeout_minutes
        )
        substitution.call_attempts += 1
        substitution.status = "CALLED"
        return True

    def _require_manager(self, actor_user_id: uuid.UUID, booking: Booking) -> None:
        if booking.created_by == actor_user_id:
            return
        try:
            OrganizationService(self.session).require_capability(
                actor_user_id,
                booking.organization_id,
                Capability.BOOKINGS_MANAGE,
            )
        except (OrganizationNotFound, Forbidden) as exc:
            raise SubstitutionForbidden from exc

    def expire_due(self, *, now: datetime | None = None) -> int:
        current = _aware(now or utcnow())
        substitutions = list(
            self.session.scalars(
                select(BookingSubstitution)
                .where(
                    or_(
                        and_(
                            BookingSubstitution.status == "CALLED",
                            BookingSubstitution.call_deadline_at <= current,
                        ),
                        and_(
                            BookingSubstitution.status.in_({"OPEN", "AWAITING_PAYMENT"}),
                            BookingSubstitution.deadline_at <= current,
                        ),
                    )
                )
                .order_by(BookingSubstitution.deadline_at)
                .with_for_update(skip_locked=True)
            ).all()
        )
        expired = 0
        for substitution in substitutions:
            if substitution.status == "CALLED":
                call_booking = self.session.get(Booking, substitution.booking_id)
                if call_booking is not None:
                    called_queue = self.session.scalar(
                        select(LobbySubstitute).where(
                            LobbySubstitute.lobby_id == call_booking.lobby_id,
                            LobbySubstitute.user_id == substitution.called_user_id,
                        )
                    )
                    if called_queue is not None:
                        called_queue.status = "DECLINED"
                substitution.called_user_id = None
                substitution.call_deadline_at = None
                substitution.status = "OPEN"
                if call_booking is not None:
                    self.maybe_call_for_parity(call_booking, current)
                if substitution.status == "CALLED":
                    continue
                if _aware(substitution.deadline_at) > current:
                    continue
            if substitution.status == "AWAITING_PAYMENT":
                payment = self.session.get(BookingPayment, substitution.substitute_payment_id)
                if payment is not None and payment.status == "PAID":
                    substitution.status = "FILLED"
                    substitution.resolved_at = current
                    self.session.flush()
                    continue
                substitution.status = "EXPIRED"
                substitution.resolved_at = current
                substitution.reason = "substitute_payment_expired"
                if substitution.filled_by_user_id is not None:
                    substitute = self.session.scalar(
                        select(BookingParticipant).where(
                            BookingParticipant.booking_id == substitution.booking_id,
                            BookingParticipant.user_id == substitution.filled_by_user_id,
                            BookingParticipant.active.is_(True),
                        )
                    )
                    if substitute is not None:
                        substitute.active = False
                        substitute.left_at = current
                        substitute.payment_status = "FAILED"
                if payment is not None and payment.status == "PENDING":
                    payment.status = "FAILED"
                queue_booking = self.session.get(Booking, substitution.booking_id)
                if queue_booking is not None and substitution.filled_by_user_id is not None:
                    queue_entry = self.session.scalar(
                        select(LobbySubstitute).where(
                            LobbySubstitute.lobby_id == queue_booking.lobby_id,
                            LobbySubstitute.user_id == substitution.filled_by_user_id,
                        )
                    )
                    if queue_entry is not None:
                        queue_entry.status = "DECLINED"
            booking = self.session.get(Booking, substitution.booking_id)
            if booking is None or booking.status not in {"CONFIRMED", "PAYMENT_PENDING"}:
                substitution.status = "CANCELLED"
                substitution.resolved_at = current
                substitution.reason = "booking_not_confirmed"
                self.session.flush()
                continue
            if substitution.paid_seat:
                # A reserva já foi entregue e paga; sem substituto, apenas a
                # vaga é encerrada, sem cancelar a quadra nem reembolsar.
                substitution.status = "EXPIRED"
                substitution.resolved_at = current
                substitution.reason = "no_substitute_paid_seat"
                expired += 1
                continue
            substitution.status = "EXPIRED"
            substitution.resolved_at = current
            substitution.reason = "no_substitute"
            self.bookings.cancel_by_system(
                booking.id,
                reason="no_substitute",
                now=current,
            )
            lobby = self.session.get(Lobby, booking.lobby_id)
            if lobby is not None and lobby.status == "scheduled":
                lobby.status = "cancelled"
            expired += 1
        self.session.flush()
        return expired
