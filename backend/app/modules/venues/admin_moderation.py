"""Moderação de quadras comerciais pela plataforma (ADR 0063).

O administrador da plataforma enxerga todas as quadras, inclusive as de
organizações de terceiros, mas a moderação é limitada a estado operacional e
campos cadastrais seguros. Preços, agenda, reservas e histórico nunca são
alterados por este módulo, e nenhuma quadra é excluída.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.audit import record_audit
from app.modules.identity.clock import utcnow
from app.modules.organizations.models import Organization, OrganizationVenue
from app.modules.venues.models import VenueSpace, VenueSport


class AdminVenueError(Exception):
    """Erro base da moderação global de quadras."""


class AdminVenueNotFound(AdminVenueError):
    """Quadra inexistente, independentemente da organização."""


class AdminVenueInvalid(AdminVenueError):
    """Alteração fora dos campos seguros ou com valor inválido."""


@dataclass(frozen=True)
class AdminVenueRecord:
    """Quadra com a organização dona e contagem de espaços."""

    venue: OrganizationVenue
    organization: Organization
    spaces_count: int
    active_spaces_count: int


_SAFE_UPDATE_FIELDS = frozenset(
    {
        "name",
        "city",
        "state",
        "address_line",
        "postal_code",
        "latitude",
        "longitude",
        "is_public",
        "geocoding_source",
        "geocoding_precision",
    }
)
_GEOCODING_PRECISIONS = frozenset({"street", "venue", "approximate", "manual"})
_RESOLVED_GEOCODING_PRECISIONS = frozenset({"street", "venue", "approximate"})


def _optional_text(value: object, *, field: str, max_length: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AdminVenueInvalid(field)
    cleaned = value.strip()
    if len(cleaned) > max_length:
        raise AdminVenueInvalid(field)
    return cleaned or None


def _coordinate(value: object, *, field: str, minimum: float, maximum: float) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise AdminVenueInvalid(field)
    converted = float(value)
    if not minimum <= converted <= maximum:
        raise AdminVenueInvalid(field)
    return converted


def _diff(previous: object, current: object) -> dict[str, object]:
    return {"from": previous, "to": current}


class AdminVenueModerationService:
    """Leitura global e moderação sem exclusão."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- leitura ---------------------------------------------------------

    def list_venues(
        self,
        *,
        q: str | None = None,
        status: str | None = None,
        is_public: bool | None = None,
        organization_id: uuid.UUID | None = None,
        active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AdminVenueRecord], int]:
        conditions = []
        if status is not None:
            conditions.append(OrganizationVenue.status == status)
        if active is not None:
            conditions.append(OrganizationVenue.status == ("active" if active else "inactive"))
        if is_public is not None:
            conditions.append(OrganizationVenue.is_public.is_(is_public))
        if organization_id is not None:
            conditions.append(OrganizationVenue.organization_id == organization_id)
        term = (q or "").strip()
        if term:
            lowered = term.lower()
            conditions.append(
                or_(
                    func.lower(OrganizationVenue.name).contains(lowered, autoescape=True),
                    func.lower(OrganizationVenue.city).contains(lowered, autoescape=True),
                    func.lower(OrganizationVenue.address_line).contains(lowered, autoescape=True),
                )
            )

        total = int(
            self.session.scalar(
                select(func.count(OrganizationVenue.id))
                .select_from(OrganizationVenue)
                .join(Organization, Organization.id == OrganizationVenue.organization_id)
                .where(*conditions)
            )
            or 0
        )
        rows = self.session.execute(
            select(OrganizationVenue, Organization)
            .join(Organization, Organization.id == OrganizationVenue.organization_id)
            .where(*conditions)
            .order_by(func.lower(OrganizationVenue.name), OrganizationVenue.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        counts = self._space_counts([row[0].id for row in rows])
        return (
            [
                AdminVenueRecord(
                    venue=venue,
                    organization=organization,
                    spaces_count=counts.get(venue.id, (0, 0))[0],
                    active_spaces_count=counts.get(venue.id, (0, 0))[1],
                )
                for venue, organization in rows
            ],
            total,
        )

    def get_venue(self, venue_id: uuid.UUID) -> AdminVenueRecord:
        row = self.session.execute(
            select(OrganizationVenue, Organization)
            .join(Organization, Organization.id == OrganizationVenue.organization_id)
            .where(OrganizationVenue.id == venue_id)
        ).first()
        if row is None:
            raise AdminVenueNotFound
        venue, organization = row
        total, active = self._space_counts([venue.id]).get(venue.id, (0, 0))
        return AdminVenueRecord(
            venue=venue,
            organization=organization,
            spaces_count=total,
            active_spaces_count=active,
        )

    def list_spaces(self, venue_id: uuid.UUID) -> list[tuple[VenueSpace, uuid.UUID | None]]:
        """Espaços da quadra e a primeira modalidade associada, se houver."""

        spaces = list(
            self.session.scalars(
                select(VenueSpace)
                .where(VenueSpace.organization_venue_id == venue_id)
                .order_by(VenueSpace.name, VenueSpace.id)
            ).all()
        )
        sports: dict[uuid.UUID, uuid.UUID] = {}
        if spaces:
            for space_id, sport_id in self.session.execute(
                select(VenueSport.venue_space_id, VenueSport.sport_id)
                .where(VenueSport.venue_space_id.in_([space.id for space in spaces]))
                .order_by(VenueSport.created_at, VenueSport.id)
            ).all():
                sports.setdefault(space_id, sport_id)
        return [(space, sports.get(space.id)) for space in spaces]

    # -- moderação -------------------------------------------------------

    def suspend(
        self,
        actor_user_id: uuid.UUID,
        venue_id: uuid.UUID,
        *,
        reason: str,
        context: Mapping[str, Any] | None = None,
    ) -> AdminVenueRecord:
        venue = self._lock(venue_id)
        previous = venue.status
        venue.status = "inactive"
        self._audit(
            actor_user_id,
            venue,
            action="admin.venue.suspended",
            reason=reason,
            changes={"status": _diff(previous, venue.status)},
            context=context,
        )
        return self._persist(venue)

    def reactivate(
        self,
        actor_user_id: uuid.UUID,
        venue_id: uuid.UUID,
        *,
        reason: str,
        context: Mapping[str, Any] | None = None,
    ) -> AdminVenueRecord:
        venue = self._lock(venue_id)
        previous = venue.status
        venue.status = "active"
        self._audit(
            actor_user_id,
            venue,
            action="admin.venue.reactivated",
            reason=reason,
            changes={"status": _diff(previous, venue.status)},
            context=context,
        )
        return self._persist(venue)

    def update(
        self,
        actor_user_id: uuid.UUID,
        venue_id: uuid.UUID,
        *,
        changes: Mapping[str, Any],
        reason: str,
        context: Mapping[str, Any] | None = None,
    ) -> AdminVenueRecord:
        unknown = set(changes) - _SAFE_UPDATE_FIELDS
        if unknown:
            raise AdminVenueInvalid("unsafe_field")
        venue = self._lock(venue_id)
        applied: dict[str, dict[str, object]] = {}

        if "name" in changes:
            raw_name = changes["name"]
            if not isinstance(raw_name, str) or not raw_name.strip():
                raise AdminVenueInvalid("name")
            cleaned_name = raw_name.strip()
            if len(cleaned_name) > 120:
                raise AdminVenueInvalid("name")
            if venue.name != cleaned_name:
                applied["name"] = _diff(venue.name, cleaned_name)
                venue.name = cleaned_name

        for field, max_length in (("city", 120), ("address_line", 200)):
            if field in changes:
                cleaned = _optional_text(changes[field], field=field, max_length=max_length)
                previous = getattr(venue, field)
                if previous != cleaned:
                    applied[field] = _diff(previous, cleaned)
                    setattr(venue, field, cleaned)

        if "state" in changes:
            cleaned_state = _optional_text(changes["state"], field="state", max_length=2)
            if cleaned_state is not None:
                cleaned_state = cleaned_state.upper()
                if len(cleaned_state) != 2:
                    raise AdminVenueInvalid("state")
            if venue.state != cleaned_state:
                applied["state"] = _diff(venue.state, cleaned_state)
                venue.state = cleaned_state

        if "postal_code" in changes:
            cleaned_postal = _optional_text(
                changes["postal_code"], field="postal_code", max_length=9
            )
            if cleaned_postal is not None and not cleaned_postal.isdigit():
                raise AdminVenueInvalid("postal_code")
            if venue.postal_code != cleaned_postal:
                applied["postal_code"] = _diff(venue.postal_code, cleaned_postal)
                venue.postal_code = cleaned_postal

        for field, minimum, maximum in (
            ("latitude", -90.0, 90.0),
            ("longitude", -180.0, 180.0),
        ):
            if field in changes:
                cleaned_coordinate = _coordinate(
                    changes[field], field=field, minimum=minimum, maximum=maximum
                )
                previous = getattr(venue, field)
                if previous != cleaned_coordinate:
                    applied[field] = _diff(previous, cleaned_coordinate)
                    setattr(venue, field, cleaned_coordinate)

        if "is_public" in changes:
            raw_public = changes["is_public"]
            if not isinstance(raw_public, bool):
                raise AdminVenueInvalid("is_public")
            if venue.is_public != raw_public:
                applied["is_public"] = _diff(venue.is_public, raw_public)
                venue.is_public = raw_public

        provenance_supplied = "geocoding_source" in changes or "geocoding_precision" in changes
        if provenance_supplied:
            if "geocoding_precision" in changes:
                precision = changes["geocoding_precision"]
                if precision is not None and precision not in _GEOCODING_PRECISIONS:
                    raise AdminVenueInvalid("geocoding_precision")
            if "geocoding_source" in changes:
                source = changes["geocoding_source"]
                if source is not None and not isinstance(source, str):
                    raise AdminVenueInvalid("geocoding_source")
            resolved_precision = changes.get("geocoding_precision", venue.geocoding_precision)
            for field, value in (
                ("geocoding_source", changes.get("geocoding_source", venue.geocoding_source)),
                ("geocoding_precision", resolved_precision),
                (
                    "geocoded_at",
                    utcnow() if resolved_precision in _RESOLVED_GEOCODING_PRECISIONS else None,
                ),
            ):
                previous = getattr(venue, field)
                if previous != value:
                    applied[field] = _diff(previous, value)
                    setattr(venue, field, value)
        elif {"latitude", "longitude", "postal_code"} & changes.keys():
            # Coordenada editada sem proveniência declarada é manual.
            for field, value in (
                ("geocoding_source", None),
                ("geocoding_precision", "manual"),
                ("geocoded_at", None),
            ):
                previous = getattr(venue, field)
                if previous != value:
                    applied[field] = _diff(previous, value)
                    setattr(venue, field, value)

        self._audit(
            actor_user_id,
            venue,
            action="admin.venue.updated",
            reason=reason,
            changes=applied,
            context=context,
        )
        return self._persist(venue)

    # -- auxiliares ------------------------------------------------------

    def _lock(self, venue_id: uuid.UUID) -> OrganizationVenue:
        venue = self.session.scalar(
            select(OrganizationVenue).where(OrganizationVenue.id == venue_id).with_for_update()
        )
        if venue is None:
            raise AdminVenueNotFound
        return venue

    def _space_counts(self, venue_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
        if not venue_ids:
            return {}
        rows = self.session.execute(
            select(
                VenueSpace.organization_venue_id,
                func.count(VenueSpace.id),
                func.count(VenueSpace.id).filter(VenueSpace.status == "active"),
            )
            .where(VenueSpace.organization_venue_id.in_(venue_ids))
            .group_by(VenueSpace.organization_venue_id)
        ).all()
        return {row[0]: (int(row[1]), int(row[2])) for row in rows}

    def _audit(
        self,
        actor_user_id: uuid.UUID,
        venue: OrganizationVenue,
        *,
        action: str,
        reason: str,
        changes: Mapping[str, object],
        context: Mapping[str, Any] | None,
    ) -> None:
        details: dict[str, Any] = dict(context or {})
        details["changes"] = dict(changes)
        details["venue_name"] = venue.name
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            organization_id=venue.organization_id,
            action=action,
            resource_type="organization_venue",
            resource_id=venue.id,
            reason=reason,
            details=details,
        )

    def _persist(self, venue: OrganizationVenue) -> AdminVenueRecord:
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise AdminVenueInvalid("constraint") from exc
        return self.get_venue(venue.id)


__all__ = [
    "AdminVenueError",
    "AdminVenueInvalid",
    "AdminVenueModerationService",
    "AdminVenueNotFound",
    "AdminVenueRecord",
]
