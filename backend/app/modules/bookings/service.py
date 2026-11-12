"""Casos de uso de reservas, bloqueios e temporizadores (Fase 13A)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.bookings.models import (
    TERMINAL_BOOKING_STATUSES,
    Booking,
    BookingEvent,
    BookingHold,
    BookingParticipant,
    BookingPayment,
    BookingSubstitution,
    BookingTimer,
)
from app.modules.identity.audit import record_audit
from app.modules.identity.clock import utcnow
from app.modules.identity.models import User
from app.modules.matchmaking.models import Lobby, LobbyParticipant
from app.modules.organizations.models import Organization, OrganizationVenue
from app.modules.organizations.permissions import Capability
from app.modules.organizations.service import (
    Forbidden,
    OrganizationNotFound,
    OrganizationService,
)
from app.modules.pricing.service import PricingBandError as PricingError
from app.modules.pricing.service import tickets_for
from app.modules.profile.models import SportFormat
from app.modules.ratings.trust import TrustService
from app.modules.tickets.service import InsufficientTickets, consume, refund
from app.modules.venues.models import VenueAvailability, VenueBlackout, VenueSpace

LOCAL_ENVIRONMENTS = frozenset({"local", "test", "development", "ci"})
SPACE_BLOCKING_STATUSES = frozenset(
    {"HOLD_CONFIRMED", "PAYMENT_PENDING", "SUBSTITUTING", "CONFIRMED"}
)

LOCAL_ENVIRONMENTS = frozenset({"local", "test", "development", "ci"})


class BookingError(Exception):
    """Erro base do domínio de reservas."""


class BookingNotFound(BookingError):
    """Reserva inexistente ou fora do acesso do ator."""


class BookingForbidden(BookingError):
    """Ator sem autorização para a operação."""


class BookingInvalid(BookingError):
    """Dados ou janela inválidos."""


class BookingConflict(BookingError):
    """Conflito de estado, espaço ou concorrência."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BookingTransitionError(BookingError):
    """Transição não permitida pela máquina de estados."""


@dataclass(frozen=True)
class BookingBundle:
    """Reserva com participantes, timers, hold e pagamentos."""

    booking: Booking
    participants: list[BookingParticipant]
    timers: list[BookingTimer]
    hold: BookingHold | None
    payments: list[BookingPayment]


class BookingService:
    """Reservas multi-tenant com temporizadores controlados pelo backend."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.organizations = OrganizationService(session)

    # -- criação ---------------------------------------------------------

    def create(
        self,
        actor_user_id: uuid.UUID,
        *,
        lobby_id: uuid.UUID,
        organization_venue_id: uuid.UUID,
        venue_space_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> BookingBundle:
        existing = self.session.scalar(select(Booking).where(Booking.lobby_id == lobby_id))
        if existing is not None:
            self._require_access(actor_user_id, existing)
            return self._bundle(existing)

        lobby = self.session.get(Lobby, lobby_id)
        if lobby is None:
            raise BookingNotFound
        if lobby.status != "scheduled":
            raise BookingInvalid
        lobby_participants = list(
            self.session.scalars(
                select(LobbyParticipant)
                .where(LobbyParticipant.lobby_id == lobby.id)
                .order_by(LobbyParticipant.team, LobbyParticipant.created_at, LobbyParticipant.id)
            ).all()
        )
        if not any(item.user_id == actor_user_id for item in lobby_participants):
            raise BookingForbidden
        if not lobby_participants:
            raise BookingInvalid

        venue = self.session.get(OrganizationVenue, organization_venue_id)
        if venue is None or venue.status != "active":
            raise BookingInvalid
        organization = self.session.get(Organization, venue.organization_id)
        if organization is None or organization.status != "active":
            raise BookingInvalid
        space = self.session.scalar(
            select(VenueSpace).where(
                VenueSpace.id == venue_space_id,
                VenueSpace.organization_venue_id == venue.id,
                VenueSpace.status == "active",
            )
        )
        if space is None:
            raise BookingInvalid

        format_ = self.session.get(SportFormat, lobby.format_id)
        if format_ is None or format_.total_participants <= 0:
            raise BookingInvalid
        seats = format_.total_participants
        if len(lobby_participants) != seats:
            raise BookingInvalid

        self._validate_timezone_window(starts_at, ends_at)
        price_cents = self._validate_space_window(venue, space, starts_at, ends_at, check_hold=True)

        now = utcnow()
        settings = get_settings()
        t1 = timedelta(minutes=settings.booking_t1_minutes)
        t2 = timedelta(minutes=settings.booking_t2_minutes)
        t3 = timedelta(minutes=settings.booking_t3_minutes)
        buffer = timedelta(minutes=settings.booking_payment_buffer_minutes)
        if now + t1 + t2 + t3 + buffer >= starts_at:
            raise BookingConflict("insufficient_lead_time")

        booking = Booking(
            lobby_id=lobby.id,
            organization_id=venue.organization_id,
            organization_venue_id=venue.id,
            venue_space_id=space.id,
            created_by=actor_user_id,
            status="PARTICIPANT_CONFIRMATION",
            starts_at=starts_at,
            ends_at=ends_at,
            price_cents=price_cents,
            seats=seats,
            policy_version="v1",
            cancellation_policy="full_refund_until_confirmed",
        )
        try:
            with self.session.begin_nested():
                self.session.add(booking)
                self.session.flush()
        except IntegrityError as exc:
            existing = self.session.scalar(select(Booking).where(Booking.lobby_id == lobby_id))
            if existing is not None:
                return self._bundle(existing)
            raise BookingConflict("booking_conflict") from exc

        contributions = _split_price(price_cents, seats)
        for seat, lobby_participant in enumerate(lobby_participants, start=1):
            self.session.add(
                BookingParticipant(
                    booking_id=booking.id,
                    user_id=lobby_participant.user_id,
                    seat=seat,
                    contribution_cents=contributions[seat - 1],
                )
            )
        self.session.add(
            BookingTimer(
                booking_id=booking.id,
                timer_type="T1",
                status="RUNNING",
                started_at=now,
                deadline_at=min(now + t1, starts_at - t2 - t3 - buffer),
            )
        )
        self._event(
            booking,
            actor_user_id,
            "booking.created",
            None,
            booking.status,
            details={"seats": seats, "price_cents": price_cents},
        )
        self._audit(actor_user_id, booking, "booking.created", {"seats": seats})
        self.session.flush()
        return self._bundle(booking)

    # -- T1 -----------------------------------------------------------------

    def confirm_participation(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        decision: str,
    ) -> BookingBundle:
        booking = self._lock_booking(booking_id)
        participant = self._active_participant(booking.id, actor_user_id)
        if participant is None:
            raise BookingForbidden
        if decision not in {"CONFIRM", "DECLINE"}:
            raise BookingInvalid
        if participant.confirmed_at is not None and decision == "CONFIRM":
            return self._bundle(booking)
        if participant.declined_at is not None and decision == "DECLINE":
            return self._bundle(booking)
        self._ensure_timer_open(booking.id, "T1")
        if booking.status != "PARTICIPANT_CONFIRMATION":
            raise BookingTransitionError

        now = utcnow()
        if decision == "CONFIRM":
            participant.confirmed_at = now
            self._event(
                booking, actor_user_id, "participant.confirmed", booking.status, booking.status
            )
        else:
            participant.declined_at = now
            participant.active = False
            TrustService(self.session).apply_event(
                actor_user_id,
                "cancel_before_payment",
                details={"booking_id": str(booking.id), "seat": participant.seat},
                now=now,
            )
            self._event(
                booking, actor_user_id, "participant.declined", booking.status, booking.status
            )

        active = self._active_participants(booking.id)
        if len(active) == booking.seats and all(item.confirmed_at is not None for item in active):
            self._start_t2(booking, actor_user_id)
        self._audit(
            actor_user_id, booking, "booking.participant_confirmation", {"decision": decision}
        )
        self.session.flush()
        return self._bundle(booking)

    # -- substituição -------------------------------------------------------

    def substitute(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        replace_user_id: uuid.UUID,
        new_user_id: uuid.UUID,
    ) -> BookingBundle:
        booking = self._lock_booking(booking_id)
        self._require_creator_or_org(actor_user_id, booking)
        if booking.status not in {"PARTICIPANT_CONFIRMATION", "PAYMENT_PENDING", "SUBSTITUTING"}:
            raise BookingTransitionError
        if replace_user_id == new_user_id:
            raise BookingInvalid
        if booking.status == "PARTICIPANT_CONFIRMATION":
            self._ensure_timer_open(booking.id, "T1")
        else:
            self._ensure_timer_open(booking.id, "T3")

        duplicate = self.session.scalar(
            select(BookingParticipant).where(
                BookingParticipant.booking_id == booking.id,
                BookingParticipant.user_id == new_user_id,
                BookingParticipant.active.is_(True),
            )
        )
        if duplicate is not None:
            raise BookingConflict("participant_already_in_booking")
        new_user = self.session.get(User, new_user_id)
        if new_user is None or new_user.status != "active":
            raise BookingInvalid

        outgoing = self.session.scalar(
            select(BookingParticipant).where(
                BookingParticipant.booking_id == booking.id,
                BookingParticipant.user_id == replace_user_id,
                BookingParticipant.active.is_(True),
            )
        )
        if outgoing is None:
            outgoing = self.session.scalar(
                select(BookingParticipant).where(
                    BookingParticipant.booking_id == booking.id,
                    BookingParticipant.user_id == replace_user_id,
                )
            )
        if outgoing is None:
            raise BookingInvalid

        now = utcnow()
        seat = outgoing.seat
        contribution = outgoing.contribution_cents
        outgoing.active = False
        outgoing.replaced_by_user_id = new_user_id
        outgoing.replaced_at = now

        new_participant = BookingParticipant(
            booking_id=booking.id,
            user_id=new_user_id,
            seat=seat,
            contribution_cents=contribution,
        )
        self.session.add(new_participant)
        self.session.flush()

        if booking.status in {"PAYMENT_PENDING", "SUBSTITUTING"}:
            previous = booking.status
            booking.status = "SUBSTITUTING"
            self._event(booking, actor_user_id, "booking.substituting", previous, booking.status)
            booking.payment_version += 1
            self.session.add(
                BookingPayment(
                    booking_id=booking.id,
                    participant_id=new_participant.id,
                    version=booking.payment_version,
                    amount_cents=contribution,
                    status="PENDING",
                )
            )
            booking.status = "PAYMENT_PENDING"
            self._event(
                booking,
                actor_user_id,
                "booking.substitution_applied",
                "SUBSTITUTING",
                "PAYMENT_PENDING",
                details={"seat": seat},
            )
        else:
            self._event(
                booking,
                actor_user_id,
                "participant.replaced",
                booking.status,
                booking.status,
                details={"seat": seat},
            )
            active = self._active_participants(booking.id)
            if len(active) == booking.seats and all(
                item.confirmed_at is not None for item in active
            ):
                self._start_t2(booking, actor_user_id)

        self._audit(
            actor_user_id,
            booking,
            "booking.participant_substituted",
            {"seat": seat, "outgoing": str(replace_user_id), "incoming": str(new_user_id)},
        )
        self.session.flush()
        return self._bundle(booking)

    # -- T2 -----------------------------------------------------------------

    def accept(self, actor_user_id: uuid.UUID, booking_id: uuid.UUID) -> BookingBundle:
        booking = self._lock_booking(booking_id)
        self.organizations.require_capability(
            actor_user_id, booking.organization_id, Capability.BOOKINGS_MANAGE
        )
        if booking.status in {"HOLD_CONFIRMED", "PAYMENT_PENDING", "CONFIRMED"}:
            return self._bundle(booking)
        self._ensure_timer_open(booking.id, "T2")
        if booking.status != "REQUESTED":
            raise BookingTransitionError

        venue = self.session.get(OrganizationVenue, booking.organization_venue_id)
        space = self.session.scalar(
            select(VenueSpace).where(VenueSpace.id == booking.venue_space_id).with_for_update()
        )
        if venue is None or space is None:
            raise BookingInvalid
        self._validate_space_window(
            venue,
            space,
            booking.starts_at,
            booking.ends_at,
            check_hold=True,
            exclude_booking_id=booking.id,
        )

        now = utcnow()
        settings = get_settings()
        t3 = timedelta(minutes=settings.booking_t3_minutes)
        buffer = timedelta(minutes=settings.booking_payment_buffer_minutes)
        booking.status = "HOLD_CONFIRMED"
        booking.accepted_at = now
        booking.hold_confirmed_at = now
        booking.hold_expires_at = now + t3
        booking.payment_due_at = now + t3 - buffer
        self._finish_timer(booking.id, "T2", "COMPLETED", now)
        self.session.add(
            BookingHold(
                booking_id=booking.id,
                venue_space_id=booking.venue_space_id,
                starts_at=booking.starts_at,
                ends_at=booking.ends_at,
                status="ACTIVE",
                confirmed_by=actor_user_id,
            )
        )
        self.session.add(
            BookingTimer(
                booking_id=booking.id,
                timer_type="T3",
                status="RUNNING",
                started_at=now,
                deadline_at=booking.hold_expires_at,
            )
        )
        self._event(booking, actor_user_id, "booking.accepted", "REQUESTED", "HOLD_CONFIRMED")

        for participant in self._active_participants(booking.id):
            self.session.add(
                BookingPayment(
                    booking_id=booking.id,
                    participant_id=participant.id,
                    version=booking.payment_version,
                    amount_cents=participant.contribution_cents,
                    status="PENDING",
                )
            )
        booking.status = "PAYMENT_PENDING"
        booking.payment_opened_at = now
        self._event(
            booking,
            actor_user_id,
            "booking.payment_opened",
            "HOLD_CONFIRMED",
            "PAYMENT_PENDING",
        )
        self._audit(actor_user_id, booking, "booking.accepted", {})
        self.session.flush()
        return self._bundle(booking)

    def decline(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        reason: str,
    ) -> BookingBundle:
        booking = self._lock_booking(booking_id)
        self.organizations.require_capability(
            actor_user_id, booking.organization_id, Capability.BOOKINGS_MANAGE
        )
        if booking.status == "DECLINED":
            return self._bundle(booking)
        self._ensure_timer_open(booking.id, "T2")
        if booking.status != "REQUESTED":
            raise BookingTransitionError
        now = utcnow()
        booking.status = "DECLINED"
        booking.declined_at = now
        booking.cancellation_reason = _clean_reason(reason)
        self._finish_timer(booking.id, "T2", "COMPLETED", now)
        self._event(
            booking,
            actor_user_id,
            "booking.declined",
            "REQUESTED",
            "DECLINED",
            reason=booking.cancellation_reason,
        )
        self._audit(
            actor_user_id, booking, "booking.declined", {"reason": booking.cancellation_reason}
        )
        self.session.flush()
        return self._bundle(booking)

    # -- T3 -----------------------------------------------------------------

    def simulate_payment(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
    ) -> BookingBundle:
        if get_settings().environment.lower() not in LOCAL_ENVIRONMENTS:
            raise BookingForbidden
        booking = self._lock_booking(booking_id)
        if booking.status == "CONFIRMED":
            return self._bundle(booking)
        if booking.status not in {"PAYMENT_PENDING", "SUBSTITUTING"}:
            raise BookingTransitionError
        participant = self._active_participant(booking.id, actor_user_id)
        if participant is None:
            raise BookingForbidden
        if participant.payment_status == "PAID":
            return self._bundle(booking)

        payment = self.session.scalar(
            select(BookingPayment).where(
                BookingPayment.booking_id == booking.id,
                BookingPayment.participant_id == participant.id,
                BookingPayment.version == booking.payment_version,
            )
        )
        if payment is None:
            raise BookingInvalid
        awaiting_substitution = self.session.scalar(
            select(BookingSubstitution.id).where(
                BookingSubstitution.substitute_payment_id == payment.id,
                BookingSubstitution.status == "AWAITING_PAYMENT",
            )
        )
        if awaiting_substitution is None:
            self._ensure_timer_open(booking.id, "T3")
        now = utcnow()
        payment.status = "PAID"
        payment.paid_at = now
        participant.payment_status = "PAID"
        self._event(booking, actor_user_id, "payment.simulated", booking.status, booking.status)
        self._confirm_if_all_paid(booking, actor_user_id, now)
        self.session.flush()
        return self._bundle(booking)

    def register_payment_result(
        self,
        booking_id: uuid.UUID,
        payment_id: uuid.UUID,
        *,
        status: str,
        provider_reference: str | None = None,
        paid_at: datetime | None = None,
    ) -> BookingBundle:
        """Aplica o resultado de um PSP/simulador a uma cobrança.

        A confirmação da reserva só ocorre quando todas as vagas ativas estão
        pagas; replay e estados repetidos são idempotentes.
        """

        if status not in {"PAID", "REFUNDED", "FAILED", "EXPIRED", "PENDING"}:
            raise BookingInvalid
        booking = self._lock_booking(booking_id)
        payment = self.session.get(BookingPayment, payment_id)
        if payment is None or payment.booking_id != booking.id:
            raise BookingInvalid
        participant = self.session.get(BookingParticipant, payment.participant_id)
        if participant is None:
            raise BookingInvalid
        if payment.status == status:
            return self._bundle(booking)

        payment.status = status
        if provider_reference:
            payment.provider_reference = provider_reference
        now = paid_at or utcnow()
        if status == "PAID":
            payment.paid_at = now
            participant.payment_status = "PAID"
            self._event(booking, None, "payment.confirmed", booking.status, booking.status)
            self._confirm_if_all_paid(booking, None, now)
        elif status == "REFUNDED":
            participant.payment_status = "REFUNDED"
            self._event(booking, None, "payment.refunded", booking.status, booking.status)
        elif status in {"FAILED", "EXPIRED"}:
            participant.payment_status = status
            self._event(booking, None, "payment.failed", booking.status, booking.status)
        self.session.flush()
        return self._bundle(booking)

    def settle_with_tickets(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
    ) -> BookingBundle:
        """Cada participante quita a própria vaga com ingressos (ADR 0042 §2).

        O débito é do saldo do próprio jogador: o ingresso é pessoal e
        intransferível. A reserva confirma quando todas as vagas ativas estão
        quitadas, seja por Pix ou por ingresso.
        """

        booking = self._lock_booking(booking_id)
        participant = self._active_participant(booking.id, actor_user_id)
        if participant is None:
            raise BookingForbidden
        if participant.tickets_consumed > 0:
            return self._bundle(booking)
        if booking.status != "PAYMENT_PENDING":
            raise BookingTransitionError

        count = self._tickets_per_seat(booking)
        try:
            consume(
                self.session,
                actor_user_id,
                count,
                ref_type="booking",
                ref_id=booking.id,
            )
        except InsufficientTickets as exc:
            raise BookingConflict("insufficient_tickets") from exc

        now = utcnow()
        participant.tickets_consumed = count
        participant.settled_with = "tickets"
        participant.payment_status = "PAID"
        self._event(
            booking,
            actor_user_id,
            "participant.settled_with_tickets",
            booking.status,
            booking.status,
        )
        self._confirm_if_all_paid(booking, actor_user_id, now)
        self.session.flush()
        return self._bundle(booking)

    def _refund_tickets(
        self,
        booking: Booking,
        *,
        exclude_user_id: uuid.UUID | None = None,
    ) -> None:
        """Devolve ingressos consumidos, conforme a matriz da ADR 0039.

        A devolução é idempotente pela chave `booking_cancel:{booking_id}:{user}`.
        """

        for participant in self._active_participants(booking.id):
            if participant.tickets_consumed <= 0:
                continue
            if exclude_user_id is not None and participant.user_id == exclude_user_id:
                continue
            refund(
                self.session,
                participant.user_id,
                participant.tickets_consumed,
                ref_type="booking_cancel",
                ref_id=booking.id,
            )
            participant.payment_status = "REFUNDED"

    def _tickets_per_seat(self, booking: Booking) -> int:
        """Resolve a tabela 2D para a reserva: faixa da janela × formato do lobby."""

        venue = self.session.get(OrganizationVenue, booking.organization_venue_id)
        space = self.session.get(VenueSpace, booking.venue_space_id)
        lobby = self.session.get(Lobby, booking.lobby_id)
        if venue is None or space is None or lobby is None:
            raise BookingInvalid
        fmt = self.session.get(SportFormat, lobby.format_id)
        if fmt is None:
            raise BookingInvalid
        availability = self._availability_for(booking, venue, space)
        if availability.band_id is None:
            raise BookingConflict("band_missing")
        try:
            return tickets_for(self.session, availability.band_id, fmt.team_size)
        except PricingError as exc:
            raise BookingConflict("tickets_not_configured") from exc

    def _availability_for(
        self,
        booking: Booking,
        venue: OrganizationVenue,
        space: VenueSpace,
    ) -> VenueAvailability:
        try:
            tz = ZoneInfo(venue.timezone)
        except Exception as exc:  # noqa: BLE001
            raise BookingInvalid from exc
        local_start = booking.starts_at.astimezone(tz)
        local_end = booking.ends_at.astimezone(tz)
        availability = self.session.scalar(
            select(VenueAvailability)
            .where(
                VenueAvailability.venue_space_id == space.id,
                VenueAvailability.weekday == local_start.isoweekday(),
                VenueAvailability.start_time <= local_start.time(),
                VenueAvailability.end_time >= local_end.time(),
            )
            .order_by(VenueAvailability.start_time)
            .limit(1)
        )
        if availability is None:
            raise BookingConflict("space_unavailable")
        return availability

    def _confirm_if_all_paid(
        self,
        booking: Booking,
        actor_user_id: uuid.UUID | None,
        now: datetime,
    ) -> None:
        if booking.status not in {"PAYMENT_PENDING", "SUBSTITUTING"}:
            return
        active = self._active_participants(booking.id)
        if not active or not all(item.payment_status == "PAID" for item in active):
            return
        previous = booking.status
        booking.status = "CONFIRMED"
        booking.confirmed_at = now
        self._finish_timer(booking.id, "T3", "COMPLETED", now)
        self._release_hold(booking.id, "CONFIRMED", now)
        self._event(booking, actor_user_id, "booking.confirmed", previous, "CONFIRMED")
        self._audit(actor_user_id, booking, "booking.confirmed", {})

    # -- cancelamento/conclusão --------------------------------------------

    def cancel(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        reason: str,
        by_venue: bool = False,
    ) -> BookingBundle:
        booking = self._lock_booking(booking_id)
        if by_venue:
            self.organizations.require_capability(
                actor_user_id, booking.organization_id, Capability.BOOKINGS_MANAGE
            )
            target = "CANCELLED_BY_VENUE"
        else:
            self._require_creator_or_org(actor_user_id, booking)
            target = "CANCELLED_BY_PLAYER"
        if booking.status == target:
            return self._bundle(booking)
        if booking.status in TERMINAL_BOOKING_STATUSES:
            raise BookingTransitionError

        now = utcnow()
        previous = booking.status
        booking.status = target
        booking.cancelled_at = now
        booking.cancellation_reason = _clean_reason(reason)
        self._release_hold(booking.id, "CANCELLED", now)
        self._finish_running_timers(booking.id, "CANCELLED", now)
        self._event(
            booking,
            actor_user_id,
            "booking.cancelled",
            previous,
            target,
            reason=booking.cancellation_reason,
        )
        if by_venue:
            # Falha do estabelecimento: todos recebem os ingressos de volta.
            self._refund_tickets(booking)
        else:
            # ADR 0039: quem cancelou perde; os demais recebem.
            self._refund_tickets(booking, exclude_user_id=actor_user_id)
        self._audit(
            actor_user_id,
            booking,
            "booking.cancelled",
            {"status": target, "reason": booking.cancellation_reason},
        )
        self.session.flush()
        return self._bundle(booking)

    def cancel_by_system(
        self,
        booking_id: uuid.UUID,
        *,
        reason: str,
        now: datetime | None = None,
    ) -> BookingBundle:
        """Cancela a reserva por decisão do sistema (T4 sem substituto)."""

        booking = self._lock_booking(booking_id)
        if booking.status in TERMINAL_BOOKING_STATUSES:
            return self._bundle(booking)

        moment = now or utcnow()
        previous = booking.status
        booking.status = "CANCELLED"
        booking.cancelled_at = moment
        booking.cancellation_reason = _clean_reason(reason)
        self._release_hold(booking.id, "CANCELLED", moment)
        self._finish_running_timers(booking.id, "CANCELLED", moment)
        self._event(
            booking,
            None,
            "booking.cancelled",
            previous,
            "CANCELLED",
            reason=booking.cancellation_reason,
        )
        # Reserva que não se confirma: todos recebem os ingressos de volta.
        self._refund_tickets(booking)
        self._audit(
            None,
            booking,
            "booking.cancelled",
            {"status": "CANCELLED", "reason": booking.cancellation_reason},
        )
        self.session.flush()
        return self._bundle(booking)

    def complete(self, actor_user_id: uuid.UUID, booking_id: uuid.UUID) -> BookingBundle:
        booking = self._lock_booking(booking_id)
        self.organizations.require_capability(
            actor_user_id, booking.organization_id, Capability.BOOKINGS_MANAGE
        )
        if booking.status == "COMPLETED":
            return self._bundle(booking)
        if booking.status != "CONFIRMED":
            raise BookingTransitionError
        booking.status = "COMPLETED"
        booking.completed_at = utcnow()
        trust = TrustService(self.session)
        for participant in self._active_participants(booking.id):
            if participant.presence_status == "PRESENT":
                trust.apply_event(
                    participant.user_id,
                    "match_completed",
                    details={"booking_id": str(booking.id)},
                    now=booking.completed_at,
                )
        self._event(booking, actor_user_id, "booking.completed", "CONFIRMED", "COMPLETED")
        self._audit(actor_user_id, booking, "booking.completed", {})
        self.session.flush()
        return self._bundle(booking)

    # -- expiração ----------------------------------------------------------

    def expire_due(self, *, now: datetime | None = None) -> int:
        moment = now or utcnow()
        timers = list(
            self.session.scalars(
                select(BookingTimer).where(
                    BookingTimer.status == "RUNNING",
                    BookingTimer.deadline_at <= moment,
                )
            ).all()
        )
        expired = 0
        for timer in timers:
            booking = self._lock_booking(timer.booking_id)
            if timer.status != "RUNNING":
                continue
            if timer.timer_type == "T1" and booking.status == "PARTICIPANT_CONFIRMATION":
                booking.status = "EXPIRED"
                booking.expired_at = moment
                self._expire_timer(timer, moment)
            elif timer.timer_type == "T2" and booking.status == "REQUESTED":
                booking.status = "EXPIRED"
                booking.expired_at = moment
                self._expire_timer(timer, moment)
            elif timer.timer_type == "T3" and booking.status in {
                "PAYMENT_PENDING",
                "SUBSTITUTING",
            }:
                booking.status = "CANCELLED"
                booking.cancelled_at = moment
                booking.cancellation_reason = "t3_expired"
                self._expire_timer(timer, moment)
                self._release_hold(booking.id, "EXPIRED", moment)
            else:
                continue
            self._event(
                booking,
                None,
                f"{timer.timer_type.lower()}.expired",
                None,
                booking.status,
            )
            self._audit(None, booking, f"booking.{timer.timer_type.lower()}_expired", {})
            expired += 1
        self.session.flush()
        return expired

    # -- leitura ------------------------------------------------------------

    def get(self, actor_user_id: uuid.UUID, booking_id: uuid.UUID) -> BookingBundle:
        booking = self.session.get(Booking, booking_id)
        if booking is None:
            raise BookingNotFound
        self._require_access(actor_user_id, booking)
        return self._bundle(booking)

    def viewer_is_org(self, actor_user_id: uuid.UUID, booking: Booking) -> bool:
        """Indica se o ator vê a reserva como membro da organização."""

        try:
            self.organizations.require_capability(
                actor_user_id, booking.organization_id, Capability.BOOKINGS_READ
            )
        except (OrganizationNotFound, Forbidden):
            return False
        return True

    def list_for_user(self, actor_user_id: uuid.UUID) -> list[BookingBundle]:
        rows = (
            self.session.scalars(
                select(Booking)
                .join(BookingParticipant, BookingParticipant.booking_id == Booking.id)
                .where(BookingParticipant.user_id == actor_user_id)
                .order_by(Booking.created_at.desc(), Booking.id.desc())
            )
            .unique()
            .all()
        )
        return [self._bundle(row) for row in rows]

    def list_for_organization(
        self, actor_user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[BookingBundle]:
        self.organizations.require_capability(
            actor_user_id, organization_id, Capability.BOOKINGS_READ
        )
        rows = self.session.scalars(
            select(Booking)
            .where(Booking.organization_id == organization_id)
            .order_by(Booking.created_at.desc(), Booking.id.desc())
        ).all()
        return [self._bundle(row) for row in rows]

    # -- auxiliares ---------------------------------------------------------

    def _bundle(self, booking: Booking) -> BookingBundle:
        participants = list(
            self.session.scalars(
                select(BookingParticipant)
                .where(BookingParticipant.booking_id == booking.id)
                .order_by(BookingParticipant.seat, BookingParticipant.created_at)
            ).all()
        )
        timers = list(
            self.session.scalars(
                select(BookingTimer)
                .where(BookingTimer.booking_id == booking.id)
                .order_by(BookingTimer.started_at)
            ).all()
        )
        hold = self.session.scalar(
            select(BookingHold)
            .where(BookingHold.booking_id == booking.id)
            .order_by(BookingHold.created_at.desc())
            .limit(1)
        )
        payments = list(
            self.session.scalars(
                select(BookingPayment)
                .where(BookingPayment.booking_id == booking.id)
                .order_by(BookingPayment.created_at)
            ).all()
        )
        return BookingBundle(
            booking=booking,
            participants=participants,
            timers=timers,
            hold=hold,
            payments=payments,
        )

    def _lock_booking(self, booking_id: uuid.UUID) -> Booking:
        booking = self.session.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if booking is None:
            raise BookingNotFound
        return booking

    def _active_participants(self, booking_id: uuid.UUID) -> list[BookingParticipant]:
        return list(
            self.session.scalars(
                select(BookingParticipant).where(
                    BookingParticipant.booking_id == booking_id,
                    BookingParticipant.active.is_(True),
                )
            ).all()
        )

    def _active_participant(
        self, booking_id: uuid.UUID, user_id: uuid.UUID
    ) -> BookingParticipant | None:
        return self.session.scalar(
            select(BookingParticipant).where(
                BookingParticipant.booking_id == booking_id,
                BookingParticipant.user_id == user_id,
                BookingParticipant.active.is_(True),
            )
        )

    def _require_access(self, actor_user_id: uuid.UUID, booking: Booking) -> None:
        if self._active_participant(booking.id, actor_user_id) is not None:
            return
        try:
            self.organizations.require_capability(
                actor_user_id, booking.organization_id, Capability.BOOKINGS_READ
            )
        except (OrganizationNotFound, Forbidden) as exc:
            raise BookingNotFound from exc

    def _require_creator_or_org(self, actor_user_id: uuid.UUID, booking: Booking) -> None:
        if booking.created_by == actor_user_id:
            return
        try:
            self.organizations.require_capability(
                actor_user_id, booking.organization_id, Capability.BOOKINGS_MANAGE
            )
        except (OrganizationNotFound, Forbidden) as exc:
            raise BookingForbidden from exc

    def _start_t2(self, booking: Booking, actor_user_id: uuid.UUID) -> None:
        settings = get_settings()
        now = utcnow()
        previous = booking.status
        booking.status = "REQUESTED"
        booking.response_due_at = now + timedelta(minutes=settings.booking_t2_minutes)
        self._finish_timer(booking.id, "T1", "COMPLETED", now)
        self.session.add(
            BookingTimer(
                booking_id=booking.id,
                timer_type="T2",
                status="RUNNING",
                started_at=now,
                deadline_at=booking.response_due_at,
            )
        )
        self._event(booking, actor_user_id, "booking.requested", previous, "REQUESTED")
        self._audit(actor_user_id, booking, "booking.requested", {})

    def _finish_timer(
        self, booking_id: uuid.UUID, timer_type: str, status: str, now: datetime
    ) -> None:
        timer = self.session.scalar(
            select(BookingTimer).where(
                BookingTimer.booking_id == booking_id,
                BookingTimer.timer_type == timer_type,
            )
        )
        if timer is not None and timer.status == "RUNNING":
            timer.status = status
            timer.ended_at = now

    def _expire_timer(self, timer: BookingTimer, now: datetime) -> None:
        timer.status = "EXPIRED"
        timer.ended_at = now

    def _ensure_timer_open(self, booking_id: uuid.UUID, timer_type: str) -> None:
        timer = self.session.scalar(
            select(BookingTimer).where(
                BookingTimer.booking_id == booking_id,
                BookingTimer.timer_type == timer_type,
                BookingTimer.status == "RUNNING",
            )
        )
        if timer is None:
            raise BookingTransitionError
        deadline = timer.deadline_at
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        if deadline <= utcnow():
            raise BookingConflict(f"{timer_type.lower()}_expired")

    def _finish_running_timers(self, booking_id: uuid.UUID, status: str, now: datetime) -> None:
        for timer in self.session.scalars(
            select(BookingTimer).where(
                BookingTimer.booking_id == booking_id,
                BookingTimer.status == "RUNNING",
            )
        ).all():
            timer.status = status
            timer.ended_at = now

    def _release_hold(self, booking_id: uuid.UUID, reason: str, now: datetime) -> None:
        for hold in self.session.scalars(
            select(BookingHold).where(
                BookingHold.booking_id == booking_id,
                BookingHold.status == "ACTIVE",
            )
        ).all():
            hold.status = "EXPIRED" if reason == "EXPIRED" else "RELEASED"
            hold.released_at = now
            hold.release_reason = reason

    def _validate_timezone_window(self, starts_at: datetime, ends_at: datetime) -> None:
        if starts_at.tzinfo is None or ends_at.tzinfo is None:
            raise BookingInvalid
        if ends_at <= starts_at:
            raise BookingInvalid

    def _validate_space_window(
        self,
        venue: OrganizationVenue,
        space: VenueSpace,
        starts_at: datetime,
        ends_at: datetime,
        *,
        check_hold: bool,
        exclude_booking_id: uuid.UUID | None = None,
    ) -> int:
        try:
            tz = ZoneInfo(venue.timezone)
        except Exception as exc:  # noqa: BLE001
            raise BookingInvalid from exc
        local_start = starts_at.astimezone(tz)
        local_end = ends_at.astimezone(tz)
        if local_start.date() != local_end.date():
            raise BookingInvalid
        availability = self.session.scalar(
            select(VenueAvailability)
            .where(
                VenueAvailability.venue_space_id == space.id,
                VenueAvailability.weekday == local_start.isoweekday(),
                VenueAvailability.start_time <= local_start.time(),
                VenueAvailability.end_time >= local_end.time(),
            )
            .order_by(VenueAvailability.start_time)
            .limit(1)
        )
        if availability is None:
            raise BookingConflict("space_unavailable")

        blackout = self.session.scalar(
            select(VenueBlackout).where(
                VenueBlackout.venue_space_id == space.id,
                VenueBlackout.starts_at < ends_at,
                VenueBlackout.ends_at > starts_at,
            )
        )
        if blackout is not None:
            raise BookingConflict("space_unavailable")
        if check_hold:
            hold_query = select(BookingHold).where(
                BookingHold.venue_space_id == space.id,
                BookingHold.status == "ACTIVE",
                BookingHold.starts_at < ends_at,
                BookingHold.ends_at > starts_at,
            )
            if exclude_booking_id is not None:
                hold_query = hold_query.where(BookingHold.booking_id != exclude_booking_id)
            if self.session.scalar(hold_query) is not None:
                raise BookingConflict("space_unavailable")

            booking_query = select(Booking).where(
                Booking.venue_space_id == space.id,
                Booking.status.in_(SPACE_BLOCKING_STATUSES),
                Booking.starts_at < ends_at,
                Booking.ends_at > starts_at,
            )
            if exclude_booking_id is not None:
                booking_query = booking_query.where(Booking.id != exclude_booking_id)
            if self.session.scalar(booking_query) is not None:
                raise BookingConflict("space_unavailable")
        return availability.price_cents

    def _event(
        self,
        booking: Booking,
        actor_user_id: uuid.UUID | None,
        event_type: str,
        from_status: str | None,
        to_status: str | None,
        *,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            BookingEvent(
                booking_id=booking.id,
                actor_user_id=actor_user_id,
                event_type=event_type,
                from_status=from_status,
                to_status=to_status,
                reason=reason,
                details=details,
            )
        )

    def _audit(
        self,
        actor_user_id: uuid.UUID | None,
        booking: Booking,
        action: str,
        details: dict[str, Any],
    ) -> None:
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            organization_id=booking.organization_id,
            action=action,
            resource_type="booking",
            resource_id=booking.id,
            details=details,
        )


def _split_price(price_cents: int, seats: int) -> list[int]:
    base, remainder = divmod(price_cents, seats)
    return [base + (1 if index < remainder else 0) for index in range(seats)]


def _clean_reason(value: str) -> str:
    normalized = " ".join(value.split())
    if not 1 <= len(normalized) <= 200:
        raise BookingInvalid
    return normalized


__all__ = [
    "BookingBundle",
    "BookingConflict",
    "BookingError",
    "BookingForbidden",
    "BookingInvalid",
    "BookingNotFound",
    "BookingService",
    "BookingTransitionError",
]
