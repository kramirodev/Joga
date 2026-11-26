"""Administração de quadras públicas da organização da plataforma."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.admin_guards import require_platform_admin
from app.api.v1.admin_reason import clean_reason
from app.api.v1.geo import get_postal_code_service
from app.api.v1.request_context import request_ip_hash
from app.core.config import Settings, get_settings
from app.core.text import (
    FreeText,
    OptionalAddressText,
    OptionalFreeText,
    OptionalMultilineText,
    OptionalVenueName,
    VenueName,
)
from app.infrastructure.database.dependency import get_session
from app.modules.catalog.platform_venues import (
    GeocodingRequired,
    InvalidPlatformSpace,
    PlatformVenueError,
    PricingNotConfigured,
    VenueNotPublishable,
    validate_publication,
    validate_space_pricing,
)
from app.modules.geo.service import (
    CepNotFound,
    CepProviderUnavailable,
    CepTimeout,
    InvalidCep,
    PostalCodeService,
)
from app.modules.identity.audit import record_audit
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.organizations.models import Organization, OrganizationVenue
from app.modules.organizations.platform import platform_organization
from app.modules.organizations.service import (
    Forbidden,
    InvalidInput,
    OrganizationNotFound,
    OrganizationService,
    VenueNotFound,
)
from app.modules.venues.admin_moderation import (
    AdminVenueInvalid,
    AdminVenueModerationService,
    AdminVenueNotFound,
    AdminVenueRecord,
)
from app.modules.venues.models import VenueAvailability, VenueBusinessHour, VenueSpace
from app.modules.venues.service import (
    AvailabilityNotFound,
    VenueConflict,
    VenueInvalid,
    VenueService,
)
from app.modules.venues.storage import PhotoStorage, get_photo_storage

router = APIRouter(prefix="/admin/venues", tags=["admin-venues"])


def _error(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, GeocodingRequired):
        return _error(status.HTTP_409_CONFLICT, "geocoding_required")
    if isinstance(exc, VenueNotPublishable):
        return _error(status.HTTP_409_CONFLICT, "venue_not_publishable")
    if isinstance(exc, PricingNotConfigured):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "pricing_not_configured")
    if isinstance(exc, InvalidCep):
        return _error(status.HTTP_400_BAD_REQUEST, "invalid_postal_code")
    if isinstance(exc, CepNotFound):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "geocoding_required")
    if isinstance(exc, (CepProviderUnavailable, CepTimeout)):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "geocoding_unavailable")
    if isinstance(exc, InvalidPlatformSpace):
        return _error(status.HTTP_400_BAD_REQUEST, "invalid_space")
    if isinstance(
        exc, (OrganizationNotFound, VenueNotFound, AdminVenueNotFound, AvailabilityNotFound)
    ):
        return _error(status.HTTP_404_NOT_FOUND, "venue_not_found")
    if isinstance(exc, Forbidden):
        return _error(status.HTTP_403_FORBIDDEN, "forbidden")
    if isinstance(exc, (VenueInvalid, InvalidInput, AdminVenueInvalid)):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_input")
    if isinstance(exc, VenueConflict):
        return _error(status.HTTP_409_CONFLICT, getattr(exc, "code", "conflict"))
    if isinstance(exc, PlatformVenueError):
        return _error(status.HTTP_409_CONFLICT, "venue_error")
    raise exc


def _platform_org(session: Session, settings: Settings) -> Organization:
    try:
        return platform_organization(session, settings.platform_org_slug)
    except LookupError:
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "platform_organization_missing") from None


def get_platform_org_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OrganizationService:
    return OrganizationService(
        session,
        platform_admin_ids=settings.platform_admin_ids,
        platform_org_slug=settings.platform_org_slug,
    )


def get_platform_venue_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> VenueService:
    return VenueService(
        session,
        storage,
        platform_admin_ids=settings.platform_admin_ids,
        platform_org_slug=settings.platform_org_slug,
    )


def get_venue_moderation_service(
    session: Annotated[Session, Depends(get_session)],
) -> AdminVenueModerationService:
    return AdminVenueModerationService(session)


class AdminVenueView(BaseModel):
    id: UUID
    organization_id: UUID
    organization_name: str
    organization_is_platform: bool
    organization_status: str
    name: str
    city: str | None
    state: str | None
    address_line: str | None
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    geocoding_source: str | None
    geocoding_precision: str | None
    is_public: bool
    status: str
    spaces_count: int
    active_spaces_count: int
    created_at: datetime
    updated_at: datetime


class AdminVenueDetailView(AdminVenueView):
    spaces: list[AdminSpaceView]


class AdminVenueListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    venues: list[AdminVenueView]


class AdminVenueCreateRequest(BaseModel):
    name: VenueName = Field(min_length=1, max_length=120)
    city: OptionalFreeText = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    address_line: OptionalAddressText = Field(default=None, max_length=200)
    postal_code: str | None = Field(default=None, max_length=9)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_public: bool = True
    reason: FreeText = Field(min_length=1, max_length=500)


class AdminVenueUpdateRequest(BaseModel):
    name: OptionalVenueName = Field(default=None, min_length=1, max_length=120)
    city: OptionalFreeText = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    address_line: OptionalAddressText = Field(default=None, max_length=200)
    postal_code: str | None = Field(default=None, max_length=9)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_public: bool | None = None
    reason: FreeText = Field(min_length=1, max_length=500)


class AdminSpaceCreateRequest(BaseModel):
    name: VenueName = Field(min_length=1, max_length=120)
    description: OptionalMultilineText = Field(default=None, max_length=280)
    is_covered: bool = False
    sport_id: UUID
    format_id: UUID
    price_cents: int = Field(gt=0, le=100_000_000)
    status: Literal["active", "inactive"] = "active"
    reason: FreeText = Field(min_length=1, max_length=500)


class AdminSpaceUpdateRequest(BaseModel):
    name: OptionalVenueName = Field(default=None, min_length=1, max_length=120)
    description: OptionalMultilineText = Field(default=None, max_length=280)
    is_covered: bool | None = None
    sport_id: UUID | None = None
    format_id: UUID | None = None
    price_cents: int | None = Field(default=None, gt=0, le=100_000_000)
    status: Literal["active", "inactive"] | None = None
    reason: FreeText = Field(min_length=1, max_length=500)


class AdminSpaceView(BaseModel):
    id: UUID
    venue_id: UUID
    name: str
    description: str | None
    is_covered: bool
    status: str
    sport_id: UUID | None
    format_id: UUID | None
    price_cents: int | None
    created_at: datetime
    updated_at: datetime


class AdminAvailabilityCreate(BaseModel):
    space_id: UUID
    weekday: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    price_cents: int = Field(ge=0, le=100_000_000)
    slot_minutes: int = Field(default=60, ge=15, le=240)
    reason: FreeText = Field(min_length=1, max_length=500)


class AdminAvailabilityUpdate(BaseModel):
    space_id: UUID
    weekday: int | None = Field(default=None, ge=1, le=7)
    start_time: time | None = None
    end_time: time | None = None
    price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    slot_minutes: int | None = Field(default=None, ge=15, le=240)
    reason: FreeText = Field(min_length=1, max_length=500)


class AdminAvailabilityView(BaseModel):
    id: UUID
    space_id: UUID
    weekday: int
    start_time: time
    end_time: time
    price_cents: int
    slot_minutes: int


class AdminBusinessHourCreate(BaseModel):
    weekday: int = Field(ge=1, le=7)
    opens_at: time
    closes_at: time
    reason: FreeText = Field(min_length=1, max_length=500)


class AdminBusinessHourUpdate(BaseModel):
    weekday: int | None = Field(default=None, ge=1, le=7)
    opens_at: time | None = None
    closes_at: time | None = None
    reason: FreeText = Field(min_length=1, max_length=500)


class AdminBusinessHourView(BaseModel):
    id: UUID
    weekday: int
    opens_at: time
    closes_at: time


def _venue_view(
    session: Session,
    venue: OrganizationVenue,
    *,
    organization: Organization | None = None,
    spaces_count: int | None = None,
    active_spaces_count: int | None = None,
) -> AdminVenueView:
    if organization is None:
        organization = session.get(Organization, venue.organization_id)
    if spaces_count is None or active_spaces_count is None:
        total_spaces, active_spaces = session.execute(
            select(
                func.count(VenueSpace.id),
                func.count(VenueSpace.id).filter(VenueSpace.status == "active"),
            ).where(VenueSpace.organization_venue_id == venue.id)
        ).one()
        spaces_count = int(total_spaces)
        active_spaces_count = int(active_spaces)
    return AdminVenueView(
        id=venue.id,
        organization_id=venue.organization_id,
        organization_name=organization.name if organization is not None else "",
        organization_is_platform=bool(organization is not None and organization.is_platform),
        organization_status=organization.status if organization is not None else "unknown",
        name=venue.name,
        city=venue.city,
        state=venue.state,
        address_line=venue.address_line,
        postal_code=venue.postal_code,
        latitude=venue.latitude,
        longitude=venue.longitude,
        geocoding_source=venue.geocoding_source,
        geocoding_precision=venue.geocoding_precision,
        is_public=venue.is_public,
        status=venue.status,
        spaces_count=spaces_count,
        active_spaces_count=active_spaces_count,
        created_at=venue.created_at,
        updated_at=venue.updated_at,
    )


def _record_view(record: AdminVenueRecord) -> AdminVenueView:
    return AdminVenueView(
        id=record.venue.id,
        organization_id=record.venue.organization_id,
        organization_name=record.organization.name,
        organization_is_platform=record.organization.is_platform,
        organization_status=record.organization.status,
        name=record.venue.name,
        city=record.venue.city,
        state=record.venue.state,
        address_line=record.venue.address_line,
        postal_code=record.venue.postal_code,
        latitude=record.venue.latitude,
        longitude=record.venue.longitude,
        geocoding_source=record.venue.geocoding_source,
        geocoding_precision=record.venue.geocoding_precision,
        is_public=record.venue.is_public,
        status=record.venue.status,
        spaces_count=record.spaces_count,
        active_spaces_count=record.active_spaces_count,
        created_at=record.venue.created_at,
        updated_at=record.venue.updated_at,
    )


def _space_view(space: VenueSpace, sport_id: UUID | None = None) -> AdminSpaceView:
    return AdminSpaceView(
        id=space.id,
        venue_id=space.organization_venue_id,
        name=space.name,
        description=space.description,
        is_covered=space.is_covered,
        status=space.status,
        sport_id=sport_id,
        format_id=space.format_id,
        price_cents=space.price_cents,
        created_at=space.created_at,
        updated_at=space.updated_at,
    )


def _audit_details(
    request: Request | None, settings: Settings, **extra: object
) -> dict[str, object]:
    details: dict[str, object] = dict(extra)
    if request is not None:
        details["ip_hash"] = request_ip_hash(request, settings)
    return details


@dataclass(frozen=True)
class GeocodeOverrides:
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = None
    state: str | None = None
    address_line: str | None = None
    geocoding_source: str | None = None
    geocoding_precision: str | None = None


def _geocode_if_needed(
    *,
    postal_service: PostalCodeService,
    postal_code: str | None,
    latitude: float | None,
    longitude: float | None,
    city: str | None,
    state: str | None,
    address_line: str | None,
) -> GeocodeOverrides:
    if not postal_code:
        return GeocodeOverrides()
    if latitude is not None and longitude is not None:
        return GeocodeOverrides(postal_code=postal_code)
    result = postal_service.resolve(postal_code)
    location = result.location
    return GeocodeOverrides(
        postal_code=location.cep,
        latitude=location.lat if latitude is None else latitude,
        longitude=location.lng if longitude is None else longitude,
        city=location.city if city is None else city,
        state=location.state if state is None else state,
        address_line=location.street if address_line is None and location.street else address_line,
        geocoding_source=location.source,
        geocoding_precision=location.precision,
    )


@router.get("", response_model=AdminVenueListResponse)
def list_admin_venues(
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    moderation: Annotated[AdminVenueModerationService, Depends(get_venue_moderation_service)],
    q: Annotated[str | None, Query(max_length=120)] = None,
    venue_status: Annotated[Literal["active", "inactive"] | None, Query(alias="status")] = None,
    is_public: bool | None = None,
    organization_id: UUID | None = None,
    active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> AdminVenueListResponse:
    """Lista todas as quadras, de qualquer organização, para a plataforma."""

    del admin
    records, total = moderation.list_venues(
        q=q,
        status=venue_status,
        is_public=is_public,
        organization_id=organization_id,
        active=active,
        page=page,
        page_size=page_size,
    )
    return AdminVenueListResponse(
        total=total,
        page=page,
        page_size=page_size,
        venues=[_record_view(record) for record in records],
    )


@router.get("/{venue_id}", response_model=AdminVenueDetailView)
def read_admin_venue(
    venue_id: UUID,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    moderation: Annotated[AdminVenueModerationService, Depends(get_venue_moderation_service)],
) -> AdminVenueDetailView:
    del admin
    try:
        record = moderation.get_venue(venue_id)
        spaces = moderation.list_spaces(venue_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return AdminVenueDetailView(
        **_record_view(record).model_dump(),
        spaces=[_space_view(space, sport_id) for space, sport_id in spaces],
    )


@router.get("/{venue_id}/spaces", response_model=list[AdminSpaceView])
def list_admin_venue_spaces(
    venue_id: UUID,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    moderation: Annotated[AdminVenueModerationService, Depends(get_venue_moderation_service)],
) -> list[AdminSpaceView]:
    del admin
    try:
        moderation.get_venue(venue_id)
        spaces = moderation.list_spaces(venue_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return [_space_view(space, sport_id) for space, sport_id in spaces]


@router.post("", response_model=AdminVenueView, status_code=status.HTTP_201_CREATED)
def create_admin_venue(
    payload: AdminVenueCreateRequest,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    organization_service: Annotated[OrganizationService, Depends(get_platform_org_service)],
    postal_service: Annotated[PostalCodeService, Depends(get_postal_code_service)],
) -> AdminVenueView:
    try:
        organization = _platform_org(session, settings)
        geocoded = _geocode_if_needed(
            postal_service=postal_service,
            postal_code=payload.postal_code,
            latitude=payload.latitude,
            longitude=payload.longitude,
            city=payload.city,
            state=payload.state,
            address_line=payload.address_line,
        )
        venue = organization_service.create_venue(
            admin.user_id,
            organization.id,
            name=payload.name,
            city=geocoded.city if geocoded.city is not None else payload.city,
            state=geocoded.state if geocoded.state is not None else payload.state,
            address_line=(
                geocoded.address_line if geocoded.address_line is not None else payload.address_line
            ),
            latitude=geocoded.latitude if geocoded.latitude is not None else payload.latitude,
            longitude=(geocoded.longitude if geocoded.longitude is not None else payload.longitude),
            postal_code=(
                geocoded.postal_code if geocoded.postal_code is not None else payload.postal_code
            ),
            geocoding_source=geocoded.geocoding_source,
            geocoding_precision=geocoded.geocoding_precision,
            is_public=payload.is_public,
            allow_missing_coordinates=True,
        )
        venue.status = "inactive"
        record_audit(
            session,
            actor_user_id=admin.user_id,
            organization_id=organization.id,
            action="admin.venue.create",
            resource_type="organization_venue",
            resource_id=venue.id,
            reason=clean_reason(payload.reason),
            details=_audit_details(request, settings, is_public=venue.is_public),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _venue_view(session, venue)


@router.patch("/{venue_id}", response_model=AdminVenueView)
def update_admin_venue(
    venue_id: UUID,
    payload: AdminVenueUpdateRequest,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    moderation: Annotated[AdminVenueModerationService, Depends(get_venue_moderation_service)],
    postal_service: Annotated[PostalCodeService, Depends(get_postal_code_service)],
) -> AdminVenueView:
    """Edita campos cadastrais seguros de qualquer quadra, sem tocar em preços."""

    try:
        current = moderation.get_venue(venue_id).venue
        geocoded = _geocode_if_needed(
            postal_service=postal_service,
            postal_code=payload.postal_code,
            latitude=payload.latitude if payload.latitude is not None else current.latitude,
            longitude=payload.longitude if payload.longitude is not None else current.longitude,
            city=payload.city,
            state=payload.state,
            address_line=payload.address_line,
        )
        changes: dict[str, object] = {}
        for field in ("name", "city", "state", "address_line"):
            value = getattr(payload, field)
            if value is not None:
                changes[field] = value
        if geocoded.postal_code is not None:
            changes["postal_code"] = geocoded.postal_code
        if geocoded.latitude is not None:
            changes["latitude"] = geocoded.latitude
        if geocoded.longitude is not None:
            changes["longitude"] = geocoded.longitude
        if geocoded.geocoding_source is not None:
            changes["geocoding_source"] = geocoded.geocoding_source
            changes["geocoding_precision"] = geocoded.geocoding_precision or "manual"
        if payload.is_public is not None:
            changes["is_public"] = payload.is_public
        record = moderation.update(
            admin.user_id,
            venue_id,
            changes=changes,
            reason=clean_reason(payload.reason),
            context=_audit_details(request, settings),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _record_view(record)


@router.post("/{venue_id}/suspend", response_model=AdminVenueView)
def suspend_admin_venue(
    venue_id: UUID,
    payload: AdminReasonRequest,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    moderation: Annotated[AdminVenueModerationService, Depends(get_venue_moderation_service)],
) -> AdminVenueView:
    """Suspende qualquer quadra; reservas e histórico permanecem intactos."""

    try:
        record = moderation.suspend(
            admin.user_id,
            venue_id,
            reason=clean_reason(payload.reason),
            context=_audit_details(request, settings),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _record_view(record)


@router.post("/{venue_id}/reactivate", response_model=AdminVenueView)
def reactivate_admin_venue(
    venue_id: UUID,
    payload: AdminReasonRequest,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    moderation: Annotated[AdminVenueModerationService, Depends(get_venue_moderation_service)],
) -> AdminVenueView:
    """Reativa qualquer quadra moderada, com motivo e auditoria."""

    try:
        record = moderation.reactivate(
            admin.user_id,
            venue_id,
            reason=clean_reason(payload.reason),
            context=_audit_details(request, settings),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _record_view(record)


@router.post("/{venue_id}/activate", response_model=AdminVenueView)
def activate_admin_venue(
    venue_id: UUID,
    payload: AdminReasonRequest,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    organization_service: Annotated[OrganizationService, Depends(get_platform_org_service)],
) -> AdminVenueView:
    try:
        organization = _platform_org(session, settings)
        venue = organization_service.get_venue(admin.user_id, organization.id, venue_id)
        validate_publication(session, venue)
        venue = organization_service.update_venue(
            admin.user_id,
            organization.id,
            venue_id,
            changes={"status": "active"},
        )
        record_audit(
            session,
            actor_user_id=admin.user_id,
            organization_id=organization.id,
            action="admin.venue.activate",
            resource_type="organization_venue",
            resource_id=venue.id,
            reason=clean_reason(payload.reason),
            details=_audit_details(request, settings),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _venue_view(session, venue)


@router.post("/{venue_id}/deactivate", response_model=AdminVenueView)
def deactivate_admin_venue(
    venue_id: UUID,
    payload: AdminReasonRequest,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    organization_service: Annotated[OrganizationService, Depends(get_platform_org_service)],
) -> AdminVenueView:
    try:
        organization = _platform_org(session, settings)
        venue = organization_service.get_venue(admin.user_id, organization.id, venue_id)
        venue = organization_service.update_venue(
            admin.user_id,
            organization.id,
            venue_id,
            changes={"status": "inactive"},
        )
        record_audit(
            session,
            actor_user_id=admin.user_id,
            organization_id=organization.id,
            action="admin.venue.deactivate",
            resource_type="organization_venue",
            resource_id=venue.id,
            reason=clean_reason(payload.reason),
            details=_audit_details(request, settings),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _venue_view(session, venue)


class AdminReasonRequest(BaseModel):
    reason: FreeText = Field(min_length=3, max_length=500)


@router.post(
    "/{venue_id}/spaces", response_model=AdminSpaceView, status_code=status.HTTP_201_CREATED
)
def create_admin_space(
    venue_id: UUID,
    payload: AdminSpaceCreateRequest,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    organization_service: Annotated[OrganizationService, Depends(get_platform_org_service)],
    venue_service: Annotated[VenueService, Depends(get_platform_venue_service)],
) -> AdminSpaceView:
    try:
        organization = _platform_org(session, settings)
        format_, _ = validate_space_pricing(
            session,
            sport_id=payload.sport_id,
            format_id=payload.format_id,
            price_cents=payload.price_cents,
        )
        space = venue_service.create_space(
            admin.user_id,
            organization.id,
            venue_id,
            name=payload.name,
            description=payload.description,
            is_covered=payload.is_covered,
            format_id=format_.id,
            price_cents=payload.price_cents,
        )
        venue_service.replace_sports(
            admin.user_id,
            organization.id,
            venue_id,
            space.id,
            [payload.sport_id],
        )
        if payload.status != "active":
            space = venue_service.update_space(
                admin.user_id,
                organization.id,
                venue_id,
                space.id,
                changes={"status": payload.status},
            )
        record_audit(
            session,
            actor_user_id=admin.user_id,
            organization_id=organization.id,
            action="admin.venue_space.create",
            resource_type="venue_space",
            resource_id=space.id,
            reason=clean_reason(payload.reason),
            details=_audit_details(
                request,
                settings,
                venue_id=str(venue_id),
                format_id=str(format_.id),
                price_cents=payload.price_cents,
            ),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _space_view(space, payload.sport_id)


@router.patch("/{venue_id}/spaces/{space_id}", response_model=AdminSpaceView)
def update_admin_space(
    venue_id: UUID,
    space_id: UUID,
    payload: AdminSpaceUpdateRequest,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    organization_service: Annotated[OrganizationService, Depends(get_platform_org_service)],
    venue_service: Annotated[VenueService, Depends(get_platform_venue_service)],
) -> AdminSpaceView:
    try:
        organization = _platform_org(session, settings)
        record = venue_service.get_space(admin.user_id, organization.id, venue_id, space_id)
        space = record.space
        sport_id = payload.sport_id or (record.sports[0].id if record.sports else None)
        format_id = payload.format_id or space.format_id
        price_cents = payload.price_cents or space.price_cents
        if (
            payload.sport_id is not None
            or payload.format_id is not None
            or payload.price_cents is not None
        ):
            if sport_id is None or format_id is None or price_cents is None:
                raise InvalidPlatformSpace
            format_, _ = validate_space_pricing(
                session,
                sport_id=sport_id,
                format_id=format_id,
                price_cents=price_cents,
            )
            format_id = format_.id
        changes: dict[str, object] = {}
        for field in ("name", "description", "is_covered", "status"):
            value = getattr(payload, field)
            if value is not None:
                changes[field] = value
        if payload.format_id is not None or payload.price_cents is not None:
            changes["format_id"] = format_id
            changes["price_cents"] = price_cents
        space = venue_service.update_space(
            admin.user_id,
            organization.id,
            venue_id,
            space_id,
            changes=changes,
        )
        if payload.sport_id is not None:
            venue_service.replace_sports(
                admin.user_id,
                organization.id,
                venue_id,
                space.id,
                [payload.sport_id],
            )
        record_audit(
            session,
            actor_user_id=admin.user_id,
            organization_id=organization.id,
            action="admin.venue_space.update",
            resource_type="venue_space",
            resource_id=space.id,
            reason=clean_reason(payload.reason),
            details=_audit_details(request, settings, changes=sorted(changes)),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _space_view(space, sport_id)


def _availability_view(row: VenueAvailability) -> AdminAvailabilityView:
    return AdminAvailabilityView(
        id=row.id,
        space_id=row.venue_space_id,
        weekday=row.weekday,
        start_time=row.start_time,
        end_time=row.end_time,
        price_cents=row.price_cents,
        slot_minutes=row.slot_minutes,
    )


def _business_hour_view(row: VenueBusinessHour) -> AdminBusinessHourView:
    return AdminBusinessHourView(
        id=row.id,
        weekday=row.weekday,
        opens_at=row.opens_at,
        closes_at=row.closes_at,
    )


@router.get("/{venue_id}/availability", response_model=list[AdminAvailabilityView])
def list_admin_availability(
    venue_id: UUID,
    space_id: UUID,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    venue_service: Annotated[VenueService, Depends(get_platform_venue_service)],
) -> list[AdminAvailabilityView]:
    organization = _platform_org(session, settings)
    rows = venue_service.list_availability(admin.user_id, organization.id, venue_id, space_id)
    return [_availability_view(row) for row in rows]


@router.post(
    "/{venue_id}/availability",
    response_model=AdminAvailabilityView,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_availability(
    venue_id: UUID,
    payload: AdminAvailabilityCreate,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    venue_service: Annotated[VenueService, Depends(get_platform_venue_service)],
) -> AdminAvailabilityView:
    try:
        organization = _platform_org(session, settings)
        row = venue_service.create_availability(
            admin.user_id,
            organization.id,
            venue_id,
            payload.space_id,
            weekday=payload.weekday,
            start_time=payload.start_time,
            end_time=payload.end_time,
            price_cents=payload.price_cents,
            slot_minutes=payload.slot_minutes,
        )
        record_audit(
            session,
            actor_user_id=admin.user_id,
            organization_id=organization.id,
            action="admin.venue_availability.create",
            resource_type="venue_availability",
            resource_id=row.id,
            reason=clean_reason(payload.reason),
            details=_audit_details(request, settings, space_id=str(payload.space_id)),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _availability_view(row)


@router.patch(
    "/{venue_id}/availability/{availability_id}",
    response_model=AdminAvailabilityView,
)
def update_admin_availability(
    venue_id: UUID,
    availability_id: UUID,
    payload: AdminAvailabilityUpdate,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    venue_service: Annotated[VenueService, Depends(get_platform_venue_service)],
) -> AdminAvailabilityView:
    try:
        organization = _platform_org(session, settings)
        changes = {
            field: getattr(payload, field)
            for field in ("weekday", "start_time", "end_time", "price_cents", "slot_minutes")
            if getattr(payload, field) is not None
        }
        row = venue_service.update_availability(
            admin.user_id,
            organization.id,
            venue_id,
            payload.space_id,
            availability_id,
            changes=changes,
        )
        record_audit(
            session,
            actor_user_id=admin.user_id,
            organization_id=organization.id,
            action="admin.venue_availability.update",
            resource_type="venue_availability",
            resource_id=row.id,
            reason=clean_reason(payload.reason),
            details=_audit_details(request, settings, space_id=str(payload.space_id)),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _availability_view(row)


@router.delete("/{venue_id}/availability/{availability_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_availability(
    venue_id: UUID,
    availability_id: UUID,
    space_id: UUID,
    reason: Annotated[str, Query(min_length=1, max_length=500)],
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    venue_service: Annotated[VenueService, Depends(get_platform_venue_service)],
) -> Response:
    try:
        organization = _platform_org(session, settings)
        venue_service.delete_availability(
            admin.user_id,
            organization.id,
            venue_id,
            space_id,
            availability_id,
        )
        record_audit(
            session,
            actor_user_id=admin.user_id,
            organization_id=organization.id,
            action="admin.venue_availability.delete",
            resource_type="venue_availability",
            resource_id=availability_id,
            reason=clean_reason(reason),
            details=_audit_details(request, settings, space_id=str(space_id)),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{venue_id}/business-hours", response_model=list[AdminBusinessHourView])
def list_admin_business_hours(
    venue_id: UUID,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    venue_service: Annotated[VenueService, Depends(get_platform_venue_service)],
) -> list[AdminBusinessHourView]:
    organization = _platform_org(session, settings)
    rows = venue_service.list_business_hours(admin.user_id, organization.id, venue_id)
    return [_business_hour_view(row) for row in rows]


@router.post(
    "/{venue_id}/business-hours",
    response_model=AdminBusinessHourView,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_business_hour(
    venue_id: UUID,
    payload: AdminBusinessHourCreate,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    venue_service: Annotated[VenueService, Depends(get_platform_venue_service)],
) -> AdminBusinessHourView:
    try:
        organization = _platform_org(session, settings)
        row = venue_service.create_business_hour(
            admin.user_id,
            organization.id,
            venue_id,
            weekday=payload.weekday,
            opens_at=payload.opens_at,
            closes_at=payload.closes_at,
        )
        record_audit(
            session,
            actor_user_id=admin.user_id,
            organization_id=organization.id,
            action="admin.venue_business_hour.create",
            resource_type="venue_business_hour",
            resource_id=row.id,
            reason=clean_reason(payload.reason),
            details=_audit_details(request, settings),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _business_hour_view(row)


@router.patch(
    "/{venue_id}/business-hours/{business_hour_id}",
    response_model=AdminBusinessHourView,
)
def update_admin_business_hour(
    venue_id: UUID,
    business_hour_id: UUID,
    payload: AdminBusinessHourUpdate,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    venue_service: Annotated[VenueService, Depends(get_platform_venue_service)],
) -> AdminBusinessHourView:
    try:
        organization = _platform_org(session, settings)
        row = venue_service.update_business_hour(
            admin.user_id,
            organization.id,
            venue_id,
            business_hour_id,
            weekday=payload.weekday,
            opens_at=payload.opens_at,
            closes_at=payload.closes_at,
        )
        record_audit(
            session,
            actor_user_id=admin.user_id,
            organization_id=organization.id,
            action="admin.venue_business_hour.update",
            resource_type="venue_business_hour",
            resource_id=row.id,
            reason=clean_reason(payload.reason),
            details=_audit_details(request, settings),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _business_hour_view(row)


@router.delete(
    "/{venue_id}/business-hours/{business_hour_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_admin_business_hour(
    venue_id: UUID,
    business_hour_id: UUID,
    reason: Annotated[str, Query(min_length=1, max_length=500)],
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    venue_service: Annotated[VenueService, Depends(get_platform_venue_service)],
) -> Response:
    try:
        organization = _platform_org(session, settings)
        venue_service.delete_business_hour(
            admin.user_id,
            organization.id,
            venue_id,
            business_hour_id,
        )
        record_audit(
            session,
            actor_user_id=admin.user_id,
            organization_id=organization.id,
            action="admin.venue_business_hour.delete",
            resource_type="venue_business_hour",
            resource_id=business_hour_id,
            reason=clean_reason(reason),
            details=_audit_details(request, settings),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
