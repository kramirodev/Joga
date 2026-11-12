"""Confirmação de presença e fechamento de no-show (ADR 0039)."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.bookings.models import Booking, BookingParticipant
from app.modules.bookings.service import BookingService
from app.modules.bookings.substitutions import (
    BookingSubstitutionService,
    ParticipantNotFound,
)
from app.modules.identity.audit import record_audit
from app.modules.identity.clock import utcnow
from app.modules.organizations.models import OrganizationVenue
from app.modules.organizations.permissions import Capability
from app.modules.organizations.service import (
    Forbidden,
    OrganizationNotFound,
    OrganizationService,
)
from app.modules.profile.models import Venue

PRESENCE_METHODS = frozenset({"GPS", "VENUE"})


class PresenceError(Exception):
    """Erro base de presença."""


class PresenceWindowError(PresenceError):
    """Fora da janela de pré-check-in ou presença."""


class PresenceClosed(PresenceError):
    """Presença já foi fechada para a reserva."""


class PresenceForbidden(PresenceError):
    """Ator sem permissão para confirmar a presença."""


class PresenceInvalid(PresenceError):
    """Método ou coordenadas inválidas."""


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distância aproximada em metros entre dois pontos."""

    radius = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


class BookingPresenceService:
    """Pré-check-in, confirmação no local e fechamento automático."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.bookings = BookingService(session)

    def pre_check_in(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> BookingParticipant:
        bundle = self.bookings.get(actor_user_id, booking_id)
        booking = bundle.booking
        if booking.status != "CONFIRMED":
            raise PresenceInvalid("booking_not_confirmed")
        current = _aware(now or utcnow())
        self._ensure_window(booking, current)
        participant = self._active_participant(booking.id, actor_user_id)
        if participant is None:
            raise PresenceForbidden
        participant.pre_checked_in_at = current
        self.session.flush()
        return participant

    def confirm(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
        target_user_id: uuid.UUID,
        *,
        method: str,
        latitude: float | None = None,
        longitude: float | None = None,
        accuracy_m: int | None = None,
        now: datetime | None = None,
    ) -> BookingParticipant:
        if method not in PRESENCE_METHODS:
            raise PresenceInvalid("invalid_method")
        bundle = self.bookings.get(actor_user_id, booking_id)
        booking = bundle.booking
        if booking.status != "CONFIRMED":
            raise PresenceInvalid("booking_not_confirmed")
        if booking.presence_closed_at is not None:
            raise PresenceClosed
        current = _aware(now or utcnow())
        self._ensure_window(booking, current)
        participant = self._active_participant(booking.id, target_user_id)
        if participant is None:
            raise ParticipantNotFound

        distance: int | None = None
        accuracy: int | None = accuracy_m
        if method == "GPS":
            if target_user_id != actor_user_id:
                raise PresenceForbidden
            if latitude is None or longitude is None or accuracy_m is None:
                raise PresenceInvalid("coordinates_required")
            venue = self._venue_coordinates(booking)
            if venue is None:
                status = "UNVERIFIED"
            else:
                distance = int(
                    round(
                        haversine_m(
                            latitude,
                            longitude,
                            venue[0],
                            venue[1],
                        )
                    )
                )
                settings = get_settings()
                if accuracy_m > settings.presence_max_accuracy_m:
                    status = "UNVERIFIED"
                elif distance <= settings.presence_radius_m:
                    status = "PRESENT"
                else:
                    status = "UNVERIFIED"
        else:
            self._require_org_manager(actor_user_id, booking)
            status = "PRESENT"

        participant.presence_status = status
        participant.presence_method = method
        participant.presence_confirmed_at = current
        participant.presence_distance_m = distance
        participant.presence_accuracy_m = accuracy
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            action="booking.presence_confirmed",
            resource_type="booking",
            resource_id=booking.id,
            organization_id=booking.organization_id,
            details={
                "user_id": str(target_user_id),
                "method": method,
                "status": status,
                "distance_m": distance,
                "accuracy_m": accuracy,
            },
        )
        self.session.flush()
        return participant

    def list_presence(
        self, actor_user_id: uuid.UUID, booking_id: uuid.UUID
    ) -> list[BookingParticipant]:
        self.bookings.get(actor_user_id, booking_id)
        return list(
            self.session.scalars(
                select(BookingParticipant)
                .where(BookingParticipant.booking_id == booking_id)
                .order_by(BookingParticipant.seat)
            ).all()
        )

    def close_due(self, *, now: datetime | None = None) -> int:
        """Fecha a presença de reservas que chegaram ao cutoff de T-30m."""

        current = _aware(now or utcnow())
        settings = get_settings()
        limit = current + timedelta(minutes=settings.presence_close_lead_minutes)
        bookings = list(
            self.session.scalars(
                select(Booking)
                .where(
                    Booking.status == "CONFIRMED",
                    Booking.presence_closed_at.is_(None),
                    Booking.starts_at <= limit,
                )
                .order_by(Booking.starts_at)
                .with_for_update(skip_locked=True)
            ).all()
        )
        substitutions = BookingSubstitutionService(self.session)
        no_shows = 0
        for booking in bookings:
            booking.presence_closed_at = current
            participants = list(
                self.session.scalars(
                    select(BookingParticipant).where(
                        BookingParticipant.booking_id == booking.id,
                        BookingParticipant.active.is_(True),
                    )
                ).all()
            )
            for participant in participants:
                if participant.presence_status == "PRESENT":
                    continue
                participant.presence_status = "NO_SHOW"
                participant.presence_confirmed_at = current
                substitutions.mark_no_show(
                    None,
                    booking.id,
                    participant.user_id,
                    reason="auto_no_show",
                    auto_call=False,
                    now=current,
                )
                no_shows += 1
            substitutions.maybe_call_for_parity(booking, current)
            present = sum(1 for item in participants if item.presence_status == "PRESENT")
            if present >= 2:
                per_team = present // 2
                booking.players_per_team = per_team
                if present % 2 == 0:
                    booking.formation_note = f"{per_team}x{per_team}"
                else:
                    booking.formation_note = f"{per_team}x{per_team} + 1 rodízio (recomendado)"
            else:
                booking.players_per_team = None
                booking.formation_note = "Sem dois times"
        self.session.flush()
        return no_shows

    def _ensure_window(self, booking: Booking, current: datetime) -> None:
        settings = get_settings()
        starts_at = _aware(booking.starts_at)
        opens_at = starts_at - timedelta(minutes=settings.presence_open_lead_minutes)
        closes_at = starts_at - timedelta(minutes=settings.presence_close_lead_minutes)
        if current < opens_at or current > closes_at:
            raise PresenceWindowError

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

    def _venue_coordinates(self, booking: Booking) -> tuple[float, float] | None:
        venue = self.session.get(OrganizationVenue, booking.organization_venue_id)
        if venue is None:
            return None
        if venue.latitude is not None and venue.longitude is not None:
            return venue.latitude, venue.longitude
        if venue.venue_id is None:
            return None
        catalog = self.session.get(Venue, venue.venue_id)
        if catalog is None:
            return None
        return catalog.lat, catalog.lng

    def _require_org_manager(self, actor_user_id: uuid.UUID, booking: Booking) -> None:
        try:
            OrganizationService(self.session).require_capability(
                actor_user_id,
                booking.organization_id,
                Capability.BOOKINGS_MANAGE,
            )
        except (OrganizationNotFound, Forbidden) as exc:
            raise PresenceForbidden from exc


__all__ = [
    "BookingPresenceService",
    "PresenceClosed",
    "PresenceError",
    "PresenceForbidden",
    "PresenceInvalid",
    "PresenceWindowError",
    "haversine_m",
]
