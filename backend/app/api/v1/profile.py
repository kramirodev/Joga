"""Endpoints de perfil esportivo, disponibilidade, região e descoberta."""

from __future__ import annotations

from datetime import datetime, time
from functools import lru_cache
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.profile.cep import (
    BrasilApiCepResolver,
    CepNotFound,
    CepProviderUnavailable,
    CepResolver,
    InvalidCep,
)
from app.modules.profile.models import Sport, SportFormat
from app.modules.profile.service import (
    DiscoveryError,
    InvalidAvailability,
    InvalidProfile,
    InvalidSportFormat,
    ProfileService,
    ProfileSnapshot,
    RegionRequired,
)

router = APIRouter(tags=["profile"])

Level = Literal["beginner", "intermediate", "advanced"]
CourtPreference = Literal["PUBLIC_ONLY", "PRIVATE_ONLY", "ANY"]


class SportFormatResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    team_size: int
    total_participants: int
    play_minutes: int
    break_minutes: int
    duration_minutes: int
    version: int


class SportResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    formats: list[SportFormatResponse]


class CatalogResponse(BaseModel):
    sports: list[SportResponse]


class UserSportResponse(BaseModel):
    format_id: UUID
    sport_slug: str
    sport_name: str
    format_name: str
    level: str
    court_preference: str


class AvailabilityResponse(BaseModel):
    weekday: int
    start_time: time
    end_time: time
    timezone: str


class RegionResponse(BaseModel):
    source: str
    cep: str | None
    city: str | None
    state: str | None
    radius_km: int
    updated_at: datetime


class ProfileResponse(BaseModel):
    user_id: UUID
    display_name: str | None
    bio: str | None
    sports: list[UserSportResponse]
    availability: list[AvailabilityResponse]
    region: RegionResponse | None


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=60)
    bio: str | None = Field(default=None, max_length=280)


class SportProfileRequest(BaseModel):
    format_id: UUID
    level: Level
    court_preference: CourtPreference = "ANY"


class SportsReplaceRequest(BaseModel):
    sports: list[SportProfileRequest] = Field(default_factory=list, max_length=20)


class AvailabilityRequest(BaseModel):
    weekday: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    timezone: str | None = Field(default=None, max_length=64)


class AvailabilityReplaceRequest(BaseModel):
    windows: list[AvailabilityRequest] = Field(default_factory=list, max_length=50)


class CepRegionRequest(BaseModel):
    cep: str = Field(min_length=8, max_length=9)
    radius_km: int | None = Field(default=None, ge=1, le=200)


class LocationRegionRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    radius_km: int | None = Field(default=None, ge=1, le=200)


class VenueResponse(BaseModel):
    id: UUID
    name: str
    kind: str
    city: str
    state: str
    cep: str | None
    address: str | None
    lat: float
    lng: float


class VenuePageResponse(BaseModel):
    items: list[VenueResponse]
    total: int
    page: int
    page_size: int


@lru_cache(maxsize=4)
def _build_cep_resolver(base_url: str, timeout_seconds: int) -> CepResolver:
    return BrasilApiCepResolver(base_url, timeout_seconds=timeout_seconds)


def get_cep_resolver(settings: Annotated[Settings, Depends(get_settings)]) -> CepResolver:
    return _build_cep_resolver(
        settings.cep_api_base_url,
        settings.cep_timeout_seconds,
    )


def get_profile_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    cep_resolver: Annotated[CepResolver, Depends(get_cep_resolver)],
) -> ProfileService:
    return ProfileService(
        session,
        cep_resolver,
        max_radius_km=settings.discovery_max_radius_km,
        default_radius_km=settings.discovery_default_radius_km,
        max_page_size=settings.discovery_page_size,
        location_round_decimals=settings.location_round_decimals,
        default_timezone=settings.default_timezone,
    )


def _error(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _profile_response(session: Session, snapshot: ProfileSnapshot) -> ProfileResponse:
    sports: list[UserSportResponse] = []
    for item in snapshot.sports:
        sport_format = session.get(SportFormat, item.format_id)
        sport = session.get(Sport, sport_format.sport_id) if sport_format else None
        if sport_format is None or sport is None:
            continue
        sports.append(
            UserSportResponse(
                format_id=item.format_id,
                sport_slug=sport.slug,
                sport_name=sport.name,
                format_name=sport_format.name,
                level=item.level,
                court_preference=item.court_preference,
            )
        )

    region = snapshot.region
    return ProfileResponse(
        user_id=snapshot.user_id,
        display_name=snapshot.display_name,
        bio=snapshot.bio,
        sports=sports,
        availability=[
            AvailabilityResponse(
                weekday=item.weekday,
                start_time=item.start_time,
                end_time=item.end_time,
                timezone=item.timezone,
            )
            for item in snapshot.availability
        ],
        region=(
            RegionResponse(
                source=region.source,
                cep=region.cep,
                city=region.city,
                state=region.state,
                radius_km=region.radius_km,
                updated_at=region.updated_at,
            )
            if region is not None
            else None
        ),
    )


@router.get("/sports", response_model=CatalogResponse)
def list_sports(
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> CatalogResponse:
    """Catálogo público de modalidades e formatos ativos."""
    return CatalogResponse(sports=[SportResponse(**item) for item in service.catalog()])


@router.get("/me/profile", response_model=ProfileResponse)
def get_my_profile(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileResponse:
    return _profile_response(session, service.get_profile(current.user_id))


@router.put("/me/profile", response_model=ProfileResponse)
def update_my_profile(
    payload: ProfileUpdateRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileResponse:
    snapshot = service.update_basic_profile(
        current.user_id,
        display_name=payload.display_name,
        bio=payload.bio,
    )
    session.commit()
    return _profile_response(session, snapshot)


@router.put("/me/sports", response_model=ProfileResponse)
def replace_my_sports(
    payload: SportsReplaceRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileResponse:
    try:
        snapshot = service.replace_sports(
            current.user_id,
            [
                {
                    "format_id": item.format_id,
                    "level": item.level,
                    "court_preference": item.court_preference,
                }
                for item in payload.sports
            ],
        )
    except InvalidSportFormat:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_sport_format") from None
    except InvalidProfile:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_profile") from None
    session.commit()
    return _profile_response(session, snapshot)


@router.put("/me/availability", response_model=ProfileResponse)
def replace_my_availability(
    payload: AvailabilityReplaceRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileResponse:
    try:
        snapshot = service.replace_availability(
            current.user_id,
            [
                {
                    "weekday": item.weekday,
                    "start_time": item.start_time,
                    "end_time": item.end_time,
                    "timezone": item.timezone,
                }
                for item in payload.windows
            ],
        )
    except InvalidAvailability:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_availability") from None
    session.commit()
    return _profile_response(session, snapshot)


@router.put("/me/region", response_model=ProfileResponse)
def set_my_region_by_cep(
    payload: CepRegionRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileResponse:
    try:
        snapshot = service.set_region_by_cep(
            current.user_id,
            payload.cep,
            payload.radius_km,
        )
    except InvalidCep:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_cep") from None
    except CepNotFound:
        raise _error(status.HTTP_404_NOT_FOUND, "cep_not_found") from None
    except CepProviderUnavailable:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "cep_unavailable",
        ) from None
    except InvalidProfile:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_region") from None
    session.commit()
    return _profile_response(session, snapshot)


@router.put("/me/location", response_model=ProfileResponse)
def set_my_region_by_location(
    payload: LocationRegionRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileResponse:
    try:
        snapshot = service.set_region_by_location(
            current.user_id,
            payload.lat,
            payload.lng,
            payload.radius_km,
        )
    except InvalidProfile:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_region") from None
    session.commit()
    return _profile_response(session, snapshot)


@router.get("/discovery/venues", response_model=VenuePageResponse)
def discover_venues(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> VenuePageResponse:
    try:
        result = service.discover_venues(
            current.user_id,
            page=page,
            page_size=page_size,
        )
    except RegionRequired:
        raise _error(status.HTTP_409_CONFLICT, "region_required") from None
    except DiscoveryError:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_discovery") from None

    return VenuePageResponse(
        items=[
            VenueResponse(
                id=item.id,
                name=item.name,
                kind=item.kind,
                city=item.city,
                state=item.state,
                cep=item.cep,
                address=item.address,
                lat=item.lat,
                lng=item.lng,
            )
            for item in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
