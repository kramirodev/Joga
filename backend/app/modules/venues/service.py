"""Casos de uso de quadras, modalidades, agenda, bloqueios e fotos (Fase 12A)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.bookings.models import Booking
from app.modules.identity.audit import record_audit
from app.modules.identity.clock import utcnow
from app.modules.organizations.models import OrganizationMembership, OrganizationVenue
from app.modules.organizations.permissions import Capability, Role
from app.modules.organizations.service import (
    Forbidden,
    OrganizationNotFound,
    OrganizationService,
    VenueNotFound,
)
from app.modules.pricing.service import PriceAboveCeiling, resolve_band
from app.modules.profile.models import Sport
from app.modules.venues.models import (
    VenueAvailability,
    VenueBlackout,
    VenuePhoto,
    VenueSpace,
    VenueSport,
)
from app.modules.venues.photos import InvalidPhoto, process_photo
from app.modules.venues.storage import PhotoNotFound as StoredPhotoNotFound
from app.modules.venues.storage import PhotoStorage, PhotoStorageError

REVIEWER_ROLES = frozenset({Role.OWNER, Role.ADMIN})

# Reservas que ainda podem acontecer: bloqueiam reajuste da janela afetada.
ACTIVE_BOOKING_STATUSES = (
    "PARTICIPANT_CONFIRMATION",
    "REQUESTED",
    "HOLD_CONFIRMED",
    "PAYMENT_PENDING",
    "CONFIRMED",
    "SUBSTITUTING",
)


class VenueError(Exception):
    """Erro base do domínio de quadras e mídia."""


class SpaceNotFound(VenueError):
    """Quadra/espaço inexistente no estabelecimento."""


class AvailabilityNotFound(VenueError):
    """Janela de disponibilidade inexistente."""


class BlackoutNotFound(VenueError):
    """Bloqueio inexistente."""


class PhotoNotFound(VenueError):
    """Foto inexistente no estabelecimento."""


class ReviewNotAllowed(VenueError):
    """Papel sem permissão para revisar fotos."""


class VenueInvalid(VenueError):
    """Dados inválidos para a operação."""


class VenueConflict(VenueError):
    """Conflito de unicidade, sobreposição ou estado."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PriceNotEligible(VenueInvalid):
    """O valor da quadra não cabe em nenhuma faixa de preço ativa."""

    code = "price_above_band"


@dataclass(frozen=True)
class SpaceRecord:
    """Quadra com as modalidades vinculadas."""

    space: VenueSpace
    sports: Sequence[Sport]


@dataclass(frozen=True)
class PhotoRecord:
    """Foto e a permissão de revisão do ator."""

    photo: VenuePhoto
    can_review: bool


@dataclass(frozen=True)
class PhotoListResult:
    """Lista de fotos e a permissão de revisão do ator."""

    photos: list[PhotoRecord]
    can_review: bool


class VenueService:
    """Operações multi-tenant de quadras, agenda e fotos."""

    def __init__(self, session: Session, storage: PhotoStorage) -> None:
        self.session = session
        self.storage = storage
        self.organizations = OrganizationService(session)

    # -- quadras ---------------------------------------------------------

    def create_space(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        *,
        name: str,
        description: str | None = None,
        is_covered: bool = False,
    ) -> VenueSpace:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_MANAGE
        )
        space = VenueSpace(
            organization_venue_id=venue.id,
            name=_clean_name(name),
            description=_clean_optional(description, 280),
            is_covered=bool(is_covered),
        )
        try:
            with self.session.begin_nested():
                self.session.add(space)
                self.session.flush()
        except IntegrityError as exc:
            raise VenueConflict("space_name_exists") from exc

        self._audit(
            actor_user_id,
            organization_id,
            "venue_space.created",
            "venue_space",
            space.id,
            {"venue_id": str(venue.id), "name": space.name},
        )
        self.session.flush()
        return space

    def list_spaces(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
    ) -> list[SpaceRecord]:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_READ
        )
        spaces = list(
            self.session.scalars(
                select(VenueSpace)
                .where(VenueSpace.organization_venue_id == venue.id)
                .order_by(VenueSpace.name, VenueSpace.id)
            ).all()
        )
        if not spaces:
            return []
        rows = self.session.execute(
            select(VenueSport.venue_space_id, Sport)
            .join(Sport, Sport.id == VenueSport.sport_id)
            .where(VenueSport.venue_space_id.in_([space.id for space in spaces]))
            .order_by(Sport.name)
        ).all()
        sports: dict[uuid.UUID, list[Sport]] = defaultdict(list)
        for space_id, sport in rows:
            sports[space_id].append(sport)
        return [SpaceRecord(space=space, sports=sports[space.id]) for space in spaces]

    def get_space(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        space_id: uuid.UUID,
    ) -> SpaceRecord:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_READ
        )
        space = self._space(venue.id, space_id)
        sports = list(
            self.session.scalars(
                select(Sport)
                .join(VenueSport, VenueSport.sport_id == Sport.id)
                .where(VenueSport.venue_space_id == space.id)
                .order_by(Sport.name)
            ).all()
        )
        return SpaceRecord(space=space, sports=sports)

    def update_space(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        space_id: uuid.UUID,
        *,
        changes: dict[str, Any],
    ) -> VenueSpace:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_MANAGE
        )
        space = self._lock_space(venue.id, space_id)
        applied: dict[str, Any] = {}
        for field, value in changes.items():
            if field == "name":
                if value is None:
                    raise VenueInvalid
                cleaned: Any = _clean_name(value)
            elif field == "description":
                cleaned = _clean_optional(value, 280)
            elif field == "status":
                if value not in {"active", "inactive"}:
                    raise VenueInvalid
                cleaned = value
            elif field == "is_covered":
                cleaned = bool(value)
            else:
                raise VenueInvalid
            previous = getattr(space, field)
            if previous != cleaned:
                setattr(space, field, cleaned)
                applied[field] = {"from": previous, "to": cleaned}

        if applied:
            try:
                self.session.flush()
            except IntegrityError as exc:
                raise VenueConflict("space_name_exists") from exc
            self._audit(
                actor_user_id,
                organization_id,
                "venue_space.updated",
                "venue_space",
                space.id,
                {"changes": applied},
            )
            self.session.flush()
        return space

    def delete_space(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        space_id: uuid.UUID,
    ) -> None:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_MANAGE
        )
        space = self._lock_space(venue.id, space_id)
        self.session.delete(space)
        self._audit(
            actor_user_id,
            organization_id,
            "venue_space.deleted",
            "venue_space",
            space_id,
            {"name": space.name},
        )
        self.session.flush()

    def replace_sports(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        space_id: uuid.UUID,
        sport_ids: list[uuid.UUID],
    ) -> list[Sport]:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_MANAGE
        )
        space = self._lock_space(venue.id, space_id)
        unique_ids = list(dict.fromkeys(sport_ids))
        sports = (
            list(
                self.session.scalars(
                    select(Sport).where(Sport.id.in_(unique_ids), Sport.active.is_(True))
                ).all()
            )
            if unique_ids
            else []
        )
        if len(sports) != len(unique_ids):
            raise VenueInvalid

        self.session.execute(delete(VenueSport).where(VenueSport.venue_space_id == space.id))
        for sport in sports:
            self.session.add(VenueSport(venue_space_id=space.id, sport_id=sport.id))
        self._audit(
            actor_user_id,
            organization_id,
            "venue_space.sports_replaced",
            "venue_space",
            space.id,
            {"sports": [str(sport.id) for sport in sports]},
        )
        self.session.flush()
        return sorted(sports, key=lambda sport: sport.name)

    # -- agenda ----------------------------------------------------------

    def create_availability(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        space_id: uuid.UUID,
        *,
        weekday: int,
        start_time: time,
        end_time: time,
        price_cents: int,
        slot_minutes: int,
    ) -> VenueAvailability:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_MANAGE
        )
        space = self._lock_space(venue.id, space_id)
        _validate_window(weekday, start_time, end_time, price_cents, slot_minutes)
        self._ensure_no_availability_overlap(space.id, weekday, start_time, end_time)
        availability = VenueAvailability(
            venue_space_id=space.id,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
            price_cents=price_cents,
            slot_minutes=slot_minutes,
            band_id=self._band_id_for(price_cents),
        )
        try:
            with self.session.begin_nested():
                self.session.add(availability)
                self.session.flush()
        except IntegrityError as exc:
            raise VenueConflict("availability_conflict") from exc
        self._audit(
            actor_user_id,
            organization_id,
            "venue_availability.created",
            "venue_availability",
            availability.id,
            {"space_id": str(space.id), "weekday": weekday},
        )
        self.session.flush()
        return availability

    def list_availability(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        space_id: uuid.UUID,
    ) -> Sequence[VenueAvailability]:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_READ
        )
        space = self._space(venue.id, space_id)
        return self.session.scalars(
            select(VenueAvailability)
            .where(VenueAvailability.venue_space_id == space.id)
            .order_by(VenueAvailability.weekday, VenueAvailability.start_time)
        ).all()

    def update_availability(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        space_id: uuid.UUID,
        availability_id: uuid.UUID,
        *,
        changes: dict[str, Any],
    ) -> VenueAvailability:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_MANAGE
        )
        space = self._lock_space(venue.id, space_id)
        availability = self._availability(space.id, availability_id)
        weekday = int(changes.get("weekday", availability.weekday))
        start_time = changes.get("start_time", availability.start_time)
        end_time = changes.get("end_time", availability.end_time)
        price_cents = int(changes.get("price_cents", availability.price_cents))
        slot_minutes = int(changes.get("slot_minutes", availability.slot_minutes))
        _validate_window(weekday, start_time, end_time, price_cents, slot_minutes)
        self._ensure_no_availability_overlap(
            space.id, weekday, start_time, end_time, exclude_id=availability.id
        )
        if price_cents != availability.price_cents and self._has_future_booking(
            space.id, weekday, start_time, end_time
        ):
            raise VenueConflict("availability_has_future_booking")
        availability.weekday = weekday
        availability.start_time = start_time
        availability.end_time = end_time
        availability.price_cents = price_cents
        availability.slot_minutes = slot_minutes
        availability.band_id = self._band_id_for(price_cents)
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise VenueConflict("availability_conflict") from exc
        self._audit(
            actor_user_id,
            organization_id,
            "venue_availability.updated",
            "venue_availability",
            availability.id,
            {"space_id": str(space.id)},
        )
        return availability

    def delete_availability(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        space_id: uuid.UUID,
        availability_id: uuid.UUID,
    ) -> None:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_MANAGE
        )
        space = self._lock_space(venue.id, space_id)
        availability = self._availability(space.id, availability_id)
        self.session.delete(availability)
        self._audit(
            actor_user_id,
            organization_id,
            "venue_availability.deleted",
            "venue_availability",
            availability_id,
            {"space_id": str(space.id)},
        )
        self.session.flush()

    def create_blackout(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        space_id: uuid.UUID,
        *,
        starts_at: datetime,
        ends_at: datetime,
        reason: str,
        external_reference: str | None = None,
    ) -> VenueBlackout:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_MANAGE
        )
        space = self._lock_space(venue.id, space_id)
        _validate_blackout(starts_at, ends_at)
        overlap = self.session.scalar(
            select(VenueBlackout).where(
                VenueBlackout.venue_space_id == space.id,
                VenueBlackout.starts_at < ends_at,
                VenueBlackout.ends_at > starts_at,
            )
        )
        if overlap is not None:
            raise VenueConflict("blackout_overlap")
        blackout = VenueBlackout(
            venue_space_id=space.id,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=_clean_name(reason, max_length=200),
            external_reference=_clean_optional(external_reference, 120),
            created_by=actor_user_id,
        )
        self.session.add(blackout)
        self.session.flush()
        self._audit(
            actor_user_id,
            organization_id,
            "venue_blackout.created",
            "venue_blackout",
            blackout.id,
            {"space_id": str(space.id)},
        )
        return blackout

    def list_blackouts(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        space_id: uuid.UUID,
    ) -> Sequence[VenueBlackout]:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_READ
        )
        space = self._space(venue.id, space_id)
        return self.session.scalars(
            select(VenueBlackout)
            .where(VenueBlackout.venue_space_id == space.id)
            .order_by(VenueBlackout.starts_at)
        ).all()

    def delete_blackout(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        space_id: uuid.UUID,
        blackout_id: uuid.UUID,
    ) -> None:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_MANAGE
        )
        space = self._space(venue.id, space_id)
        blackout = self.session.scalar(
            select(VenueBlackout).where(
                VenueBlackout.id == blackout_id,
                VenueBlackout.venue_space_id == space.id,
            )
        )
        if blackout is None:
            raise BlackoutNotFound
        self.session.delete(blackout)
        self._audit(
            actor_user_id,
            organization_id,
            "venue_blackout.deleted",
            "venue_blackout",
            blackout_id,
            {"space_id": str(space.id)},
        )
        self.session.flush()

    # -- fotos -----------------------------------------------------------

    def create_photo(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        *,
        raw: bytes,
        caption: str | None = None,
        space_id: uuid.UUID | None = None,
    ) -> PhotoRecord:
        venue, membership = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_MANAGE
        )
        if space_id is not None:
            self._space(venue.id, space_id)

        from app.core.config import get_settings

        settings = get_settings()
        processed = process_photo(
            raw,
            max_bytes=settings.venue_photo_max_bytes,
            max_pixels=settings.venue_photo_max_pixels,
            max_dimension=settings.venue_photo_max_dimension,
            min_dimension=settings.venue_photo_min_dimension,
            output_max_dimension=settings.venue_photo_output_max_dimension,
        )
        key = self.storage.save(processed.data)
        photo = VenuePhoto(
            organization_venue_id=venue.id,
            venue_space_id=space_id,
            status="PENDING",
            storage_key=key,
            content_type=processed.content_type,
            size_bytes=len(processed.data),
            width=processed.width,
            height=processed.height,
            caption=_clean_optional(caption, 160),
            created_by=actor_user_id,
        )
        try:
            with self.session.begin_nested():
                self.session.add(photo)
                self.session.flush()
        except Exception:
            self.storage.delete(key)
            raise
        self._audit(
            actor_user_id,
            organization_id,
            "venue_photo.uploaded",
            "venue_photo",
            photo.id,
            {"venue_id": str(venue.id), "space_id": str(space_id) if space_id else None},
        )
        self.session.flush()
        return PhotoRecord(
            photo=photo,
            can_review=Role(membership.role) in REVIEWER_ROLES,
        )

    def list_photos(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        *,
        include_removed: bool = False,
    ) -> PhotoListResult:
        venue, membership = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_READ
        )
        query = select(VenuePhoto).where(VenuePhoto.organization_venue_id == venue.id)
        if not include_removed:
            query = query.where(VenuePhoto.status != "REMOVED")
        photos = self.session.scalars(
            query.order_by(VenuePhoto.created_at.desc(), VenuePhoto.id.desc())
        ).all()
        can_review = Role(membership.role) in REVIEWER_ROLES
        return PhotoListResult(
            photos=[PhotoRecord(photo=photo, can_review=can_review) for photo in photos],
            can_review=can_review,
        )

    def review_photo(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        photo_id: uuid.UUID,
        *,
        decision: str,
        reason: str | None = None,
    ) -> VenuePhoto:
        venue, membership = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_MANAGE
        )
        if Role(membership.role) not in REVIEWER_ROLES:
            raise ReviewNotAllowed
        if decision not in {"APPROVED", "REJECTED"}:
            raise VenueInvalid
        if decision == "REJECTED" and not (reason and reason.strip()):
            raise VenueInvalid
        photo = self._photo(venue.id, photo_id)
        if photo.status == "REMOVED":
            raise PhotoNotFound
        photo.status = decision
        photo.rejection_reason = (
            _clean_name(reason, max_length=200) if decision == "REJECTED" and reason else None
        )
        photo.reviewed_by = actor_user_id
        photo.reviewed_at = utcnow()
        self._audit(
            actor_user_id,
            organization_id,
            "venue_photo.reviewed",
            "venue_photo",
            photo.id,
            {"decision": decision, "reason": photo.rejection_reason},
        )
        self.session.flush()
        return photo

    def remove_photo(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        photo_id: uuid.UUID,
    ) -> None:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_MANAGE
        )
        photo = self._photo(venue.id, photo_id)
        photo.status = "REMOVED"
        photo.removed_at = utcnow()
        deleted = True
        try:
            self.storage.delete(photo.storage_key)
        except PhotoStorageError:
            deleted = False
        self._audit(
            actor_user_id,
            organization_id,
            "venue_photo.removed",
            "venue_photo",
            photo.id,
            {"file_deleted": deleted},
        )
        self.session.flush()

    def photo_content(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        photo_id: uuid.UUID,
    ) -> tuple[bytes, str]:
        venue, _ = self._venue_access(
            actor_user_id, organization_id, venue_id, Capability.VENUES_READ
        )
        photo = self._photo(venue.id, photo_id)
        if photo.status == "REMOVED":
            raise PhotoNotFound
        try:
            return self.storage.read(photo.storage_key), photo.content_type
        except StoredPhotoNotFound as exc:
            raise PhotoNotFound from exc

    # -- auxiliares ------------------------------------------------------

    def _venue_access(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        capability: Capability,
    ) -> tuple[OrganizationVenue, OrganizationMembership]:
        membership = self.organizations.require_capability(
            actor_user_id, organization_id, capability
        )
        venue = self.session.scalar(
            select(OrganizationVenue).where(
                OrganizationVenue.id == venue_id,
                OrganizationVenue.organization_id == organization_id,
            )
        )
        if venue is None:
            raise VenueNotFound
        return venue, membership

    def _space(self, venue_id: uuid.UUID, space_id: uuid.UUID) -> VenueSpace:
        space = self.session.scalar(
            select(VenueSpace).where(
                VenueSpace.id == space_id,
                VenueSpace.organization_venue_id == venue_id,
            )
        )
        if space is None:
            raise SpaceNotFound
        return space

    def _lock_space(self, venue_id: uuid.UUID, space_id: uuid.UUID) -> VenueSpace:
        space = self.session.scalar(
            select(VenueSpace)
            .where(
                VenueSpace.id == space_id,
                VenueSpace.organization_venue_id == venue_id,
            )
            .with_for_update()
        )
        if space is None:
            raise SpaceNotFound
        return space

    def _availability(self, space_id: uuid.UUID, availability_id: uuid.UUID) -> VenueAvailability:
        availability = self.session.scalar(
            select(VenueAvailability).where(
                VenueAvailability.id == availability_id,
                VenueAvailability.venue_space_id == space_id,
            )
        )
        if availability is None:
            raise AvailabilityNotFound
        return availability

    def _photo(self, venue_id: uuid.UUID, photo_id: uuid.UUID) -> VenuePhoto:
        photo = self.session.scalar(
            select(VenuePhoto).where(
                VenuePhoto.id == photo_id,
                VenuePhoto.organization_venue_id == venue_id,
            )
        )
        if photo is None:
            raise PhotoNotFound
        return photo

    def _ensure_no_availability_overlap(
        self,
        space_id: uuid.UUID,
        weekday: int,
        start_time: time,
        end_time: time,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        query = select(VenueAvailability).where(
            VenueAvailability.venue_space_id == space_id,
            VenueAvailability.weekday == weekday,
            VenueAvailability.start_time < end_time,
            VenueAvailability.end_time > start_time,
        )
        if exclude_id is not None:
            query = query.where(VenueAvailability.id != exclude_id)
        if self.session.scalar(query) is not None:
            raise VenueConflict("availability_overlap")

    def _band_id_for(self, price_cents: int) -> uuid.UUID:
        """Faixa da tabela 2D que cobre o valor da quadra (ADR 0042 §3)."""
        try:
            return resolve_band(self.session, price_cents).id
        except PriceAboveCeiling as exc:
            raise PriceNotEligible from exc

    def _has_future_booking(
        self,
        space_id: uuid.UUID,
        weekday: int,
        start_time: time,
        end_time: time,
    ) -> bool:
        """Reserva futura na mesma janela impede reajuste (ADR 0042 §9)."""
        tz = ZoneInfo(get_settings().default_timezone)
        rows = self.session.execute(
            select(Booking.starts_at, Booking.ends_at).where(
                Booking.venue_space_id == space_id,
                Booking.starts_at >= utcnow(),
                Booking.status.in_(ACTIVE_BOOKING_STATUSES),
            )
        ).all()
        for starts_at, ends_at in rows:
            local_start = starts_at.astimezone(tz)
            local_end = ends_at.astimezone(tz)
            if local_start.isoweekday() != weekday:
                continue
            if local_start.time() < end_time and local_end.time() > start_time:
                return True
        return False

    def _audit(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID,
        details: dict[str, Any],
    ) -> None:
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )


def _clean_name(value: str, max_length: int = 120) -> str:
    normalized = " ".join(value.split())
    if not 1 <= len(normalized) <= max_length:
        raise VenueInvalid
    return normalized


def _clean_optional(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if len(normalized) > max_length:
        raise VenueInvalid
    return normalized or None


def _validate_window(
    weekday: int,
    start_time: time,
    end_time: time,
    price_cents: int,
    slot_minutes: int,
) -> None:
    if not 1 <= weekday <= 7:
        raise VenueInvalid
    if start_time >= end_time:
        raise VenueInvalid
    if price_cents < 0:
        raise VenueInvalid
    if not 15 <= slot_minutes <= 240:
        raise VenueInvalid


def _validate_blackout(starts_at: datetime, ends_at: datetime) -> None:
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise VenueInvalid
    if ends_at <= starts_at:
        raise VenueInvalid


__all__ = [
    "AvailabilityNotFound",
    "BlackoutNotFound",
    "Forbidden",
    "OrganizationNotFound",
    "PhotoNotFound",
    "PhotoRecord",
    "ReviewNotAllowed",
    "SpaceNotFound",
    "SpaceRecord",
    "VenueConflict",
    "VenueError",
    "VenueInvalid",
    "VenueNotFound",
    "VenueService",
    "InvalidPhoto",
]
