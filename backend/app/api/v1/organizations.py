"""Endpoints de organizações, membros, estabelecimentos e auditoria."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.organizations.models import OrganizationVenue
from app.modules.organizations.permissions import Role
from app.modules.organizations.service import (
    AlreadyMember,
    CannotManageRole,
    Forbidden,
    InvalidInput,
    LastOwner,
    MemberNotFound,
    MemberRecord,
    OrganizationAccess,
    OrganizationError,
    OrganizationNotFound,
    OrganizationService,
    UserNotActive,
    UserNotFound,
    VenueNotFound,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class OrganizationUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class OrganizationView(BaseModel):
    id: UUID
    name: str
    status: str
    role: str
    created_at: datetime
    updated_at: datetime


class OrganizationListResponse(BaseModel):
    organizations: list[OrganizationView]


class MemberCreate(BaseModel):
    user_id: UUID
    role: Role


class MemberUpdate(BaseModel):
    role: Role


class MemberView(BaseModel):
    user_id: UUID
    display_name: str | None
    role: str
    created_at: datetime


class MemberListResponse(BaseModel):
    members: list[MemberView]


class VenueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    address_line: str | None = Field(default=None, max_length=200)
    timezone: str | None = Field(default=None, max_length=64)
    venue_id: UUID | None = None

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class VenueUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    address_line: str | None = Field(default=None, max_length=200)
    timezone: str | None = Field(default=None, max_length=64)
    venue_id: UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class VenueView(BaseModel):
    id: UUID
    organization_id: UUID
    venue_id: UUID | None
    name: str
    city: str | None
    state: str | None
    address_line: str | None
    timezone: str
    status: str
    created_at: datetime
    updated_at: datetime


class VenueListResponse(BaseModel):
    venues: list[VenueView]


class AuditView(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict[str, Any] | None
    created_at: datetime


class AuditListResponse(BaseModel):
    audit: list[AuditView]
    limit: int
    offset: int


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _handle(exc: Exception) -> HTTPException:
    mapping = {
        OrganizationNotFound: ("organization_not_found", status.HTTP_404_NOT_FOUND),
        VenueNotFound: ("venue_not_found", status.HTTP_404_NOT_FOUND),
        MemberNotFound: ("member_not_found", status.HTTP_404_NOT_FOUND),
        UserNotFound: ("user_not_found", status.HTTP_404_NOT_FOUND),
        UserNotActive: ("user_not_active", status.HTTP_409_CONFLICT),
        AlreadyMember: ("member_already_exists", status.HTTP_409_CONFLICT),
        Forbidden: ("forbidden", status.HTTP_403_FORBIDDEN),
        CannotManageRole: ("role_not_allowed", status.HTTP_403_FORBIDDEN),
        LastOwner: ("last_owner_required", status.HTTP_409_CONFLICT),
        InvalidInput: ("invalid_input", status.HTTP_422_UNPROCESSABLE_CONTENT),
        OrganizationError: ("organization_error", status.HTTP_409_CONFLICT),
    }
    for error_type, (code, status_code) in mapping.items():
        if isinstance(exc, error_type):
            return _error(code, status_code)
    raise exc


def _organization_view(access: OrganizationAccess) -> OrganizationView:
    organization = access.organization
    return OrganizationView(
        id=organization.id,
        name=organization.name,
        status=organization.status,
        role=access.role.value,
        created_at=organization.created_at,
        updated_at=organization.updated_at,
    )


def _member_view(item: MemberRecord) -> MemberView:
    return MemberView(
        user_id=item.membership.user_id,
        display_name=item.display_name,
        role=item.membership.role,
        created_at=item.membership.created_at,
    )


def _venue_view(venue: OrganizationVenue) -> VenueView:
    return VenueView(
        id=venue.id,
        organization_id=venue.organization_id,
        venue_id=venue.venue_id,
        name=venue.name,
        city=venue.city,
        state=venue.state,
        address_line=venue.address_line,
        timezone=venue.timezone,
        status=venue.status,
        created_at=venue.created_at,
        updated_at=venue.updated_at,
    )


@router.post("", response_model=OrganizationView, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> OrganizationView:
    service = OrganizationService(session)
    try:
        organization = service.create(current.user_id, payload.name)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _organization_view(
        service.get(current.user_id, organization.id),
    )


@router.get("", response_model=OrganizationListResponse)
def list_organizations(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> OrganizationListResponse:
    service = OrganizationService(session)
    access = service.list_for_user(current.user_id)
    return OrganizationListResponse(organizations=[_organization_view(item) for item in access])


@router.get("/{organization_id}", response_model=OrganizationView)
def get_organization(
    organization_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> OrganizationView:
    service = OrganizationService(session)
    try:
        access = service.get(current.user_id, organization_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return _organization_view(access)


@router.patch("/{organization_id}", response_model=OrganizationView)
def update_organization(
    organization_id: UUID,
    payload: OrganizationUpdate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> OrganizationView:
    service = OrganizationService(session)
    try:
        organization = service.update(current.user_id, organization_id, payload.name)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _organization_view(
        service.get(current.user_id, organization.id),
    )


@router.get("/{organization_id}/members", response_model=MemberListResponse)
def list_members(
    organization_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> MemberListResponse:
    service = OrganizationService(session)
    try:
        rows = service.list_members(current.user_id, organization_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return MemberListResponse(members=[_member_view(row) for row in rows])


@router.post(
    "/{organization_id}/members",
    response_model=MemberView,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    organization_id: UUID,
    payload: MemberCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> MemberView:
    service = OrganizationService(session)
    try:
        member = service.add_member(
            current.user_id,
            organization_id,
            payload.user_id,
            Role(payload.role),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _member_view(member)


@router.patch("/{organization_id}/members/{user_id}", response_model=MemberView)
def change_member_role(
    organization_id: UUID,
    user_id: UUID,
    payload: MemberUpdate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> MemberView:
    service = OrganizationService(session)
    try:
        member = service.change_member_role(
            current.user_id,
            organization_id,
            user_id,
            Role(payload.role),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _member_view(member)


@router.delete(
    "/{organization_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_member(
    organization_id: UUID,
    user_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    service = OrganizationService(session)
    try:
        service.remove_member(current.user_id, organization_id, user_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None


@router.post(
    "/{organization_id}/venues",
    response_model=VenueView,
    status_code=status.HTTP_201_CREATED,
)
def create_venue(
    organization_id: UUID,
    payload: VenueCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> VenueView:
    service = OrganizationService(session)
    try:
        venue = service.create_venue(
            current.user_id,
            organization_id,
            name=payload.name,
            city=payload.city,
            state=payload.state,
            address_line=payload.address_line,
            timezone=payload.timezone,
            venue_id=payload.venue_id,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _venue_view(venue)


@router.get("/{organization_id}/venues", response_model=VenueListResponse)
def list_venues(
    organization_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> VenueListResponse:
    service = OrganizationService(session)
    try:
        venues = service.list_venues(current.user_id, organization_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return VenueListResponse(venues=[_venue_view(venue) for venue in venues])


@router.get("/{organization_id}/venues/{venue_id}", response_model=VenueView)
def get_venue(
    organization_id: UUID,
    venue_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> VenueView:
    service = OrganizationService(session)
    try:
        venue = service.get_venue(current.user_id, organization_id, venue_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return _venue_view(venue)


@router.patch("/{organization_id}/venues/{venue_id}", response_model=VenueView)
def update_venue(
    organization_id: UUID,
    venue_id: UUID,
    payload: VenueUpdate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> VenueView:
    service = OrganizationService(session)
    try:
        venue = service.update_venue(
            current.user_id,
            organization_id,
            venue_id,
            changes=payload.model_dump(exclude_unset=True),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _venue_view(venue)


@router.get("/{organization_id}/audit", response_model=AuditListResponse)
def list_audit(
    organization_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditListResponse:
    service = OrganizationService(session)
    try:
        events = service.list_audit(
            current.user_id,
            organization_id,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return AuditListResponse(
        audit=[
            AuditView(
                id=event.id,
                actor_user_id=event.actor_user_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                details=event.details,
                created_at=event.created_at,
            )
            for event in events
        ],
        limit=limit,
        offset=offset,
    )
