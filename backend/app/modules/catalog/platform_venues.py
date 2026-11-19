"""Validação de publicação de quadras públicas da plataforma."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.organizations.models import OrganizationVenue
from app.modules.pricing.models import PricingBand
from app.modules.pricing.service import (
    BandTicketsNotConfigured,
    PriceAboveCeiling,
    PricingBandError,
    resolve_band,
    tickets_for,
)
from app.modules.pricing.suggest import pricing_configured
from app.modules.profile.models import Sport, SportFormat
from app.modules.venues.models import VenueAvailability, VenueSpace, VenueSport


class PlatformVenueError(Exception):
    """Erro base de quadra pública."""


class VenueNotPublishable(PlatformVenueError):
    """Faltam dados operacionais para publicar a quadra."""


class GeocodingRequired(PlatformVenueError):
    """A quadra não tem coordenada publicável."""


class PricingNotConfigured(PlatformVenueError):
    """Falta preço em faixa válida para o formato do espaço."""


class InvalidPlatformSpace(PlatformVenueError):
    """Modalidade/formato/preço inválidos para o espaço."""


def validate_space_pricing(
    session: Session,
    *,
    sport_id: uuid.UUID,
    format_id: uuid.UUID,
    price_cents: int,
) -> tuple[SportFormat, PricingBand]:
    """Valida modalidade, formato e preço antes de gravar o espaço."""

    sport = session.get(Sport, sport_id)
    if sport is None or not sport.active:
        raise InvalidPlatformSpace
    format_ = session.get(SportFormat, format_id)
    if format_ is None or not format_.active or format_.sport_id != sport.id or price_cents <= 0:
        raise InvalidPlatformSpace
    if not pricing_configured(session, format_.team_size):
        raise PricingNotConfigured
    try:
        band = resolve_band(session, price_cents)
        tickets_for(session, band.id, format_.team_size)
    except (PricingBandError, PriceAboveCeiling, BandTicketsNotConfigured) as exc:
        raise PricingNotConfigured from exc
    return format_, band


def validate_publication(session: Session, venue: OrganizationVenue) -> None:
    """Regras mínimas para aparecer na descoberta."""

    if venue.latitude is None or venue.longitude is None:
        raise GeocodingRequired
    if not (venue.name or "").strip() or not venue.city or not venue.state:
        raise VenueNotPublishable
    spaces = list(
        session.scalars(
            select(VenueSpace).where(
                VenueSpace.organization_venue_id == venue.id,
                VenueSpace.status == "active",
            )
        )
    )
    if not spaces:
        raise VenueNotPublishable

    missing_price = False
    price_mismatch = False
    publishable = False
    for space in spaces:
        if space.format_id is None or space.price_cents is None:
            missing_price = True
            continue
        sports = list(
            session.scalars(
                select(Sport)
                .join(VenueSport, VenueSport.sport_id == Sport.id)
                .where(
                    VenueSport.venue_space_id == space.id,
                    Sport.active.is_(True),
                )
            )
        )
        if not sports:
            continue
        try:
            validate_space_pricing(
                session,
                sport_id=sports[0].id,
                format_id=space.format_id,
                price_cents=space.price_cents,
            )
        except InvalidPlatformSpace:
            continue
        windows = list(
            session.scalars(
                select(VenueAvailability).where(VenueAvailability.venue_space_id == space.id)
            )
        )
        if not windows:
            continue
        if any(window.price_cents != space.price_cents for window in windows):
            price_mismatch = True
            continue
        publishable = True
        break

    if publishable:
        return
    if missing_price or price_mismatch:
        raise PricingNotConfigured
    raise VenueNotPublishable


__all__ = [
    "GeocodingRequired",
    "InvalidPlatformSpace",
    "PlatformVenueError",
    "PricingNotConfigured",
    "VenueNotPublishable",
    "validate_publication",
    "validate_space_pricing",
]
