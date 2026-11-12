"""Endpoints de quadras, agenda, bloqueios e fotos (Fase 12A)."""

from __future__ import annotations

from datetime import datetime, time
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.organizations.service import (
    Forbidden,
    OrganizationError,
    OrganizationNotFound,
    VenueNotFound,
)
from app.modules.profile.models import Sport
from app.modules.venues.models import (
    VenueAvailability,
    VenueBlackout,
    VenuePhoto,
)
from app.modules.venues.photos import InvalidPhoto
from app.modules.venues.service import (
    AvailabilityNotFound,
    BlackoutNotFound,
    PhotoNotFound,
    PriceNotEligible,
    ReviewNotAllowed,
    SpaceNotFound,
    SpaceRecord,
    VenueConflict,
    VenueError,
    VenueInvalid,
    VenueService,
)
from app.modules.venues.storage import PhotoStorage, PhotoStorageError, get_photo_storage

router = APIRouter(
    prefix="/organizations/{organization_id}/venues/{venue_id}",
    tags=["venues"],
)


class SpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=280)
    is_covered: bool = False


class SpaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=280)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")
    is_covered: bool | None = None


class SportView(BaseModel):
    id: UUID
    slug: str
    name: str


class SportsReplace(BaseModel):
    sport_ids: list[UUID] = Field(max_length=20)


class SpaceView(BaseModel):
    id: UUID
    venue_id: UUID
    name: str
    description: str | None
    is_covered: bool
    status: str
    sports: list[SportView]
    created_at: datetime
    updated_at: datetime


class SpaceListResponse(BaseModel):
    spaces: list[SpaceView]


class AvailabilityCreate(BaseModel):
    weekday: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    price_cents: int = Field(ge=0, le=100_000_000)
    slot_minutes: int = Field(default=60, ge=15, le=240)


class AvailabilityUpdate(BaseModel):
    weekday: int | None = Field(default=None, ge=1, le=7)
    start_time: time | None = None
    end_time: time | None = None
    price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    slot_minutes: int | None = Field(default=None, ge=15, le=240)


class AvailabilityView(BaseModel):
    id: UUID
    space_id: UUID
    weekday: int
    start_time: time
    end_time: time
    price_cents: int
    slot_minutes: int
    band_id: UUID | None


class AvailabilityListResponse(BaseModel):
    availability: list[AvailabilityView]


class BlackoutCreate(BaseModel):
    starts_at: datetime
    ends_at: datetime
    reason: str = Field(min_length=1, max_length=200)
    external_reference: str | None = Field(default=None, max_length=120)


class BlackoutView(BaseModel):
    id: UUID
    space_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: str
    external_reference: str | None
    created_at: datetime


class BlackoutListResponse(BaseModel):
    blackouts: list[BlackoutView]


class PhotoView(BaseModel):
    id: UUID
    venue_id: UUID
    space_id: UUID | None
    status: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    caption: str | None
    rejection_reason: str | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    content_url: str
    can_review: bool


class PhotoListResponse(BaseModel):
    photos: list[PhotoView]
    can_review: bool


class PhotoReview(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    reason: str | None = Field(default=None, max_length=200)


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _handle(exc: Exception) -> HTTPException:
    mapping = {
        OrganizationNotFound: ("organization_not_found", status.HTTP_404_NOT_FOUND),
        VenueNotFound: ("venue_not_found", status.HTTP_404_NOT_FOUND),
        SpaceNotFound: ("space_not_found", status.HTTP_404_NOT_FOUND),
        AvailabilityNotFound: ("availability_not_found", status.HTTP_404_NOT_FOUND),
        BlackoutNotFound: ("blackout_not_found", status.HTTP_404_NOT_FOUND),
        PhotoNotFound: ("photo_not_found", status.HTTP_404_NOT_FOUND),
        ReviewNotAllowed: ("review_not_allowed", status.HTTP_403_FORBIDDEN),
        Forbidden: ("forbidden", status.HTTP_403_FORBIDDEN),
        InvalidPhoto: ("invalid_photo", status.HTTP_422_UNPROCESSABLE_CONTENT),
        PriceNotEligible: ("price_above_band", status.HTTP_422_UNPROCESSABLE_CONTENT),
        VenueInvalid: ("invalid_input", status.HTTP_422_UNPROCESSABLE_CONTENT),
        VenueConflict: (getattr(exc, "code", "conflict"), status.HTTP_409_CONFLICT),
        PhotoStorageError: ("photo_storage_unavailable", status.HTTP_503_SERVICE_UNAVAILABLE),
        VenueError: ("venue_error", status.HTTP_409_CONFLICT),
        OrganizationError: ("organization_error", status.HTTP_409_CONFLICT),
    }
    for error_type, (code, status_code) in mapping.items():
        if isinstance(exc, error_type):
            return _error(code, status_code)
    raise exc


def _sport_view(sport: Sport) -> SportView:
    return SportView(id=sport.id, slug=sport.slug, name=sport.name)


def _space_view(record: SpaceRecord) -> SpaceView:
    space = record.space
    return SpaceView(
        id=space.id,
        venue_id=space.organization_venue_id,
        name=space.name,
        description=space.description,
        is_covered=space.is_covered,
        status=space.status,
        sports=[_sport_view(sport) for sport in record.sports],
        created_at=space.created_at,
        updated_at=space.updated_at,
    )


def _availability_view(item: VenueAvailability) -> AvailabilityView:
    return AvailabilityView(
        id=item.id,
        space_id=item.venue_space_id,
        weekday=item.weekday,
        start_time=item.start_time,
        end_time=item.end_time,
        price_cents=item.price_cents,
        slot_minutes=item.slot_minutes,
        band_id=item.band_id,
    )


def _blackout_view(item: VenueBlackout) -> BlackoutView:
    return BlackoutView(
        id=item.id,
        space_id=item.venue_space_id,
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        reason=item.reason,
        external_reference=item.external_reference,
        created_at=item.created_at,
    )


def _photo_view(
    item: VenuePhoto,
    *,
    organization_id: UUID,
    venue_id: UUID,
    can_review: bool,
) -> PhotoView:
    return PhotoView(
        id=item.id,
        venue_id=item.organization_venue_id,
        space_id=item.venue_space_id,
        status=item.status,
        content_type=item.content_type,
        size_bytes=item.size_bytes,
        width=item.width,
        height=item.height,
        caption=item.caption,
        rejection_reason=item.rejection_reason,
        reviewed_by=item.reviewed_by,
        reviewed_at=item.reviewed_at,
        created_at=item.created_at,
        content_url=(
            f"/api/v1/organizations/{organization_id}/venues/{venue_id}/photos/{item.id}/content"
        ),
        can_review=can_review,
    )


def _service(session: Session, storage: PhotoStorage) -> VenueService:
    return VenueService(session, storage)


# -- quadras -----------------------------------------------------------------


@router.post("/spaces", response_model=SpaceView, status_code=status.HTTP_201_CREATED)
def create_space(
    organization_id: UUID,
    venue_id: UUID,
    payload: SpaceCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> SpaceView:
    service = _service(session, storage)
    try:
        space = service.create_space(
            current.user_id,
            organization_id,
            venue_id,
            name=payload.name,
            description=payload.description,
            is_covered=payload.is_covered,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _space_view(service.get_space(current.user_id, organization_id, venue_id, space.id))


@router.get("/spaces", response_model=SpaceListResponse)
def list_spaces(
    organization_id: UUID,
    venue_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> SpaceListResponse:
    service = _service(session, storage)
    try:
        spaces = service.list_spaces(current.user_id, organization_id, venue_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return SpaceListResponse(spaces=[_space_view(item) for item in spaces])


@router.get("/spaces/{space_id}", response_model=SpaceView)
def get_space(
    organization_id: UUID,
    venue_id: UUID,
    space_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> SpaceView:
    service = _service(session, storage)
    try:
        record = service.get_space(current.user_id, organization_id, venue_id, space_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return _space_view(record)


@router.patch("/spaces/{space_id}", response_model=SpaceView)
def update_space(
    organization_id: UUID,
    venue_id: UUID,
    space_id: UUID,
    payload: SpaceUpdate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> SpaceView:
    service = _service(session, storage)
    try:
        service.update_space(
            current.user_id,
            organization_id,
            venue_id,
            space_id,
            changes=payload.model_dump(exclude_unset=True),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _space_view(service.get_space(current.user_id, organization_id, venue_id, space_id))


@router.delete("/spaces/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_space(
    organization_id: UUID,
    venue_id: UUID,
    space_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> None:
    service = _service(session, storage)
    try:
        service.delete_space(current.user_id, organization_id, venue_id, space_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None


@router.put("/spaces/{space_id}/sports", response_model=list[SportView])
def replace_space_sports(
    organization_id: UUID,
    venue_id: UUID,
    space_id: UUID,
    payload: SportsReplace,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> list[SportView]:
    service = _service(session, storage)
    try:
        sports = service.replace_sports(
            current.user_id,
            organization_id,
            venue_id,
            space_id,
            payload.sport_ids,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return [_sport_view(sport) for sport in sports]


# -- agenda ------------------------------------------------------------------


@router.post(
    "/spaces/{space_id}/availability",
    response_model=AvailabilityView,
    status_code=status.HTTP_201_CREATED,
)
def create_availability(
    organization_id: UUID,
    venue_id: UUID,
    space_id: UUID,
    payload: AvailabilityCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> AvailabilityView:
    service = _service(session, storage)
    try:
        item = service.create_availability(
            current.user_id,
            organization_id,
            venue_id,
            space_id,
            weekday=payload.weekday,
            start_time=payload.start_time,
            end_time=payload.end_time,
            price_cents=payload.price_cents,
            slot_minutes=payload.slot_minutes,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _availability_view(item)


@router.get("/spaces/{space_id}/availability", response_model=AvailabilityListResponse)
def list_availability(
    organization_id: UUID,
    venue_id: UUID,
    space_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> AvailabilityListResponse:
    service = _service(session, storage)
    try:
        items = service.list_availability(current.user_id, organization_id, venue_id, space_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return AvailabilityListResponse(availability=[_availability_view(item) for item in items])


@router.patch(
    "/spaces/{space_id}/availability/{availability_id}",
    response_model=AvailabilityView,
)
def update_availability(
    organization_id: UUID,
    venue_id: UUID,
    space_id: UUID,
    availability_id: UUID,
    payload: AvailabilityUpdate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> AvailabilityView:
    service = _service(session, storage)
    try:
        item = service.update_availability(
            current.user_id,
            organization_id,
            venue_id,
            space_id,
            availability_id,
            changes=payload.model_dump(exclude_unset=True),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _availability_view(item)


@router.delete(
    "/spaces/{space_id}/availability/{availability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_availability(
    organization_id: UUID,
    venue_id: UUID,
    space_id: UUID,
    availability_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> None:
    service = _service(session, storage)
    try:
        service.delete_availability(
            current.user_id,
            organization_id,
            venue_id,
            space_id,
            availability_id,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None


# -- bloqueios ---------------------------------------------------------------


@router.post(
    "/spaces/{space_id}/blackouts",
    response_model=BlackoutView,
    status_code=status.HTTP_201_CREATED,
)
def create_blackout(
    organization_id: UUID,
    venue_id: UUID,
    space_id: UUID,
    payload: BlackoutCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> BlackoutView:
    service = _service(session, storage)
    try:
        item = service.create_blackout(
            current.user_id,
            organization_id,
            venue_id,
            space_id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            reason=payload.reason,
            external_reference=payload.external_reference,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _blackout_view(item)


@router.get("/spaces/{space_id}/blackouts", response_model=BlackoutListResponse)
def list_blackouts(
    organization_id: UUID,
    venue_id: UUID,
    space_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> BlackoutListResponse:
    service = _service(session, storage)
    try:
        items = service.list_blackouts(current.user_id, organization_id, venue_id, space_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return BlackoutListResponse(blackouts=[_blackout_view(item) for item in items])


@router.delete(
    "/spaces/{space_id}/blackouts/{blackout_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_blackout(
    organization_id: UUID,
    venue_id: UUID,
    space_id: UUID,
    blackout_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> None:
    service = _service(session, storage)
    try:
        service.delete_blackout(
            current.user_id,
            organization_id,
            venue_id,
            space_id,
            blackout_id,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None


# -- fotos -------------------------------------------------------------------


@router.post("/photos", response_model=PhotoView, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    organization_id: UUID,
    venue_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File()],
    caption: Annotated[str | None, Form()] = None,
    space_id: Annotated[UUID | None, Form()] = None,
) -> PhotoView:
    raw = await file.read(settings.venue_photo_max_bytes + 1)
    if len(raw) > settings.venue_photo_max_bytes:
        raise _error("photo_too_large", status.HTTP_413_CONTENT_TOO_LARGE)
    service = _service(session, storage)
    try:
        photo = service.create_photo(
            current.user_id,
            organization_id,
            venue_id,
            raw=raw,
            caption=caption,
            space_id=space_id,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _photo_view(
        photo.photo,
        organization_id=organization_id,
        venue_id=venue_id,
        can_review=photo.can_review,
    )


@router.get("/photos", response_model=PhotoListResponse)
def list_photos(
    organization_id: UUID,
    venue_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    include_removed: bool = False,
) -> PhotoListResponse:
    service = _service(session, storage)
    try:
        records = service.list_photos(
            current.user_id,
            organization_id,
            venue_id,
            include_removed=include_removed,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return PhotoListResponse(
        photos=[
            _photo_view(
                record.photo,
                organization_id=organization_id,
                venue_id=venue_id,
                can_review=record.can_review,
            )
            for record in records.photos
        ],
        can_review=records.can_review,
    )


@router.post("/photos/{photo_id}/review", response_model=PhotoView)
def review_photo(
    organization_id: UUID,
    venue_id: UUID,
    photo_id: UUID,
    payload: PhotoReview,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> PhotoView:
    service = _service(session, storage)
    try:
        photo = service.review_photo(
            current.user_id,
            organization_id,
            venue_id,
            photo_id,
            decision=payload.decision,
            reason=payload.reason,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _photo_view(
        photo,
        organization_id=organization_id,
        venue_id=venue_id,
        can_review=True,
    )


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_photo(
    organization_id: UUID,
    venue_id: UUID,
    photo_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> None:
    service = _service(session, storage)
    try:
        service.remove_photo(current.user_id, organization_id, venue_id, photo_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None


@router.get("/photos/{photo_id}/content")
def photo_content(
    organization_id: UUID,
    venue_id: UUID,
    photo_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> Response:
    service = _service(session, storage)
    try:
        data, content_type = service.photo_content(
            current.user_id,
            organization_id,
            venue_id,
            photo_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": 'inline; filename="venue-photo.jpg"',
        },
    )
