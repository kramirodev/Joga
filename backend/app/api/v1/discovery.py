"""Contratos HTTP da vitrine de quadras reserváveis (Fase 13C)."""

from __future__ import annotations

from datetime import datetime, time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.venues.discovery import (
    DiscoveryInvalid,
    DiscoveryNotFound,
    VenueDiscoveryService,
)
from app.modules.venues.storage import PhotoStorage, get_photo_storage

router = APIRouter(prefix="/discovery/bookable-venues", tags=["discovery"])


class BandView(BaseModel):
    id: UUID
    code: str
    label: str
    max_price_cents: int


class FormatView(BaseModel):
    id: UUID
    slug: str
    name: str
    team_size: int
    total_participants: int
    tickets_by_band: dict[str, int]


class SportView(BaseModel):
    id: UUID
    slug: str
    name: str
    formats: list[FormatView]


class AvailabilityView(BaseModel):
    weekday: int
    start_time: time
    end_time: time
    price_cents: int
    slot_minutes: int
    band: BandView | None


class SlotView(BaseModel):
    starts_at: datetime
    ends_at: datetime
    price_cents: int
    band_code: str | None


class SpaceView(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_covered: bool
    sports: list[SportView]
    availability: list[AvailabilityView]
    next_slots: list[SlotView]


class PhotoView(BaseModel):
    id: UUID
    caption: str | None
    content_type: str
    content_url: str


class VenueCardView(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    city: str | None
    state: str | None
    address_line: str | None
    latitude: float | None
    longitude: float | None
    timezone: str
    is_public: bool
    covered: bool
    spaces_count: int
    min_price_cents: int
    distance_km: float | None
    photo_url: str | None


class VenueCardListResponse(BaseModel):
    venues: list[VenueCardView]
    total: int
    page: int
    page_size: int


class VenueDetailView(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    city: str | None
    state: str | None
    address_line: str | None
    latitude: float | None
    longitude: float | None
    timezone: str
    is_public: bool
    photos: list[PhotoView]
    spaces: list[SpaceView]


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, DiscoveryNotFound):
        return _error("venue_not_found", status.HTTP_404_NOT_FOUND)
    if isinstance(exc, DiscoveryInvalid):
        return _error(str(exc), status.HTTP_422_UNPROCESSABLE_CONTENT)
    raise exc


def _photo_url(venue_id: UUID, photo_id: UUID) -> str:
    return f"/api/v1/discovery/bookable-venues/{venue_id}/photos/{photo_id}/content"


def _service(session: Session, storage: PhotoStorage) -> VenueDiscoveryService:
    return VenueDiscoveryService(session, storage)


@router.get("", response_model=VenueCardListResponse)
def list_bookable_venues(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    city: Annotated[str | None, Query(max_length=120)] = None,
) -> VenueCardListResponse:
    """Estabelecimentos ativos com ao menos uma quadra e uma janela de agenda."""
    service = _service(session, storage)
    try:
        result = service.list_venues(
            current.user_id,
            page=page,
            page_size=page_size,
            city=city,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return VenueCardListResponse(
        venues=[
            VenueCardView(
                id=item.id,
                organization_id=item.organization_id,
                name=item.name,
                city=item.city,
                state=item.state,
                address_line=item.address_line,
                latitude=item.latitude,
                longitude=item.longitude,
                timezone=item.timezone,
                is_public=item.is_public,
                covered=item.covered,
                spaces_count=item.spaces_count,
                min_price_cents=item.min_price_cents,
                distance_km=item.distance_km,
                photo_url=_photo_url(item.id, item.photo_id) if item.photo_id else None,
            )
            for item in result.venues
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{venue_id}", response_model=VenueDetailView)
def get_bookable_venue(
    venue_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> VenueDetailView:
    """Detalhe reservável: quadras, modalidades, faixas, agenda e próximos horários."""
    service = _service(session, storage)
    try:
        venue = service.get_venue(venue_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return VenueDetailView(
        id=venue.id,
        organization_id=venue.organization_id,
        name=venue.name,
        city=venue.city,
        state=venue.state,
        address_line=venue.address_line,
        latitude=venue.latitude,
        longitude=venue.longitude,
        timezone=venue.timezone,
        is_public=venue.is_public,
        photos=[
            PhotoView(
                id=photo.id,
                caption=photo.caption,
                content_type=photo.content_type,
                content_url=_photo_url(venue.id, photo.id),
            )
            for photo in venue.photos
        ],
        spaces=[
            SpaceView(
                id=space.id,
                name=space.name,
                description=space.description,
                is_covered=space.is_covered,
                sports=[
                    SportView(
                        id=sport.id,
                        slug=sport.slug,
                        name=sport.name,
                        formats=[
                            FormatView(
                                id=format_.id,
                                slug=format_.slug,
                                name=format_.name,
                                team_size=format_.team_size,
                                total_participants=format_.total_participants,
                                tickets_by_band=format_.tickets_by_band,
                            )
                            for format_ in sport.formats
                        ],
                    )
                    for sport in space.sports
                ],
                availability=[
                    AvailabilityView(
                        weekday=row.weekday,
                        start_time=row.start_time,
                        end_time=row.end_time,
                        price_cents=row.price_cents,
                        slot_minutes=row.slot_minutes,
                        band=(
                            BandView(
                                id=row.band.id,
                                code=row.band.code,
                                label=row.band.label,
                                max_price_cents=row.band.max_price_cents,
                            )
                            if row.band is not None
                            else None
                        ),
                    )
                    for row in space.availability
                ],
                next_slots=[
                    SlotView(
                        starts_at=slot.starts_at,
                        ends_at=slot.ends_at,
                        price_cents=slot.price_cents,
                        band_code=slot.band_code,
                    )
                    for slot in space.next_slots
                ],
            )
            for space in venue.spaces
        ],
    )


@router.get("/{venue_id}/photos/{photo_id}/content")
def get_bookable_venue_photo(
    venue_id: UUID,
    photo_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> Response:
    """Serve apenas foto aprovada de estabelecimento ativo."""
    service = _service(session, storage)
    try:
        data, content_type = service.photo_content(venue_id, photo_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": 'inline; filename="venue-photo.jpg"',
            # Cache-Control efetivo é definido pelo middleware de
            # observabilidade (no-store); não duplicar aqui.
        },
    )


__all__ = ["router"]
