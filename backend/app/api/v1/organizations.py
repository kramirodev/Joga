"""Endpoints de organizações, membros, estabelecimentos e auditoria."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.api.v1.geo import get_postal_code_service
from app.core.config import Settings, get_settings
from app.core.text import (
    OptionalAddressText,
    OptionalFreeText,
    OptionalVenueName,
    OrganizationName,
    VenueName,
)
from app.infrastructure.database.dependency import get_session
from app.modules.geo.geocoding import GeocodeOverrides, geocode_if_needed
from app.modules.geo.service import (
    CepNotFound,
    CepProviderUnavailable,
    CepTimeout,
    InvalidCep,
    PostalCodeService,
)
from app.modules.identity.audit import record_audit
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.organizations.cnpj import CnpjLookup, mask_cnpj
from app.modules.organizations.dependency import get_cnpj_lookup
from app.modules.organizations.models import OrganizationVenue
from app.modules.organizations.permissions import Role
from app.modules.organizations.service import (
    AlreadyMember,
    CannotManageRole,
    CnpjAlreadyRegistered,
    CnpjChangeNotAllowed,
    Forbidden,
    InvalidInput,
    LastOwner,
    MemberNotFound,
    MemberRecord,
    OrganizationAccess,
    OrganizationError,
    OrganizationNotFound,
    OrganizationNotVerifiable,
    OrganizationNotVerified,
    OrganizationService,
    UserNotActive,
    UserNotFound,
    VenueNotFound,
    mask_pix_key,
    payout_ready,
)
from app.modules.organizations.verification import (
    CnpjVerificationError,
    verify_new_organization,
)
from app.modules.ratelimit.service import RateLimitExceeded
from app.modules.ratelimit.service import enforce as enforce_rate_limit

router = APIRouter(prefix="/organizations", tags=["organizations"])


class OrganizationCreate(BaseModel):
    name: OrganizationName = Field(min_length=2, max_length=120)
    cnpj: str = Field(min_length=14, max_length=20)
    # O CPF é pessoal e só existe em claro no corpo da requisição. Ele nunca é
    # devolvido, auditado ou registrado em log.
    cpf: str = Field(min_length=11, max_length=14)


class OrganizationUpdate(BaseModel):
    name: OrganizationName = Field(min_length=2, max_length=120)


class OrganizationVerificationRequest(BaseModel):
    cnpj: str = Field(min_length=14, max_length=20)
    cpf: str = Field(min_length=11, max_length=14)


class OrganizationView(BaseModel):
    id: UUID
    name: str
    status: str
    role: str
    cnpj: str | None
    cnpj_status: str | None
    verification_status: str
    cnpj_verified_at: datetime | None
    cnpj_next_check_at: datetime | None
    payout_ready: bool
    payout_status: str
    pix_key_type: str | None
    pix_key_masked: str | None
    created_at: datetime
    updated_at: datetime


class PayoutUpdate(BaseModel):
    legal_document: str = Field(min_length=14, max_length=20)
    pix_key_type: str = Field(pattern="^(cnpj|email|phone|random)$")
    pix_key: str = Field(min_length=1, max_length=77)


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
    name: VenueName = Field(min_length=2, max_length=120)
    city: OptionalFreeText = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    address_line: OptionalAddressText = Field(default=None, max_length=200)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    postal_code: str | None = Field(default=None, max_length=9)
    geocoding_source: str | None = Field(default=None, pattern="^[a-z0-9+._-]{1,40}$")
    geocoding_precision: str | None = Field(
        default=None, pattern="^(street|venue|approximate|manual)$"
    )
    timezone: str | None = Field(default=None, max_length=64)
    venue_id: UUID | None = None

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class VenueUpdate(BaseModel):
    name: OptionalVenueName = Field(default=None, min_length=2, max_length=120)
    city: OptionalFreeText = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    address_line: OptionalAddressText = Field(default=None, max_length=200)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    postal_code: str | None = Field(default=None, max_length=9)
    geocoding_source: str | None = Field(default=None, pattern="^[a-z0-9+._-]{1,40}$")
    geocoding_precision: str | None = Field(
        default=None, pattern="^(street|venue|approximate|manual)$"
    )
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
    latitude: float | None
    longitude: float | None
    postal_code: str | None
    geocoding_source: str | None
    geocoding_precision: str | None
    geocoded_at: datetime | None
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
    total: int
    limit: int
    offset: int


def _error(
    code: str,
    status_code: int,
    *,
    retry_after: int | None = None,
) -> HTTPException:
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
    return HTTPException(status_code=status_code, detail={"code": code}, headers=headers)


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, CnpjVerificationError):
        return _error(exc.code, exc.http_status)
    if isinstance(exc, CepTimeout):
        return _error("geocoding_timeout", status.HTTP_504_GATEWAY_TIMEOUT)
    if isinstance(exc, CepProviderUnavailable):
        return _error("geocoding_provider_error", status.HTTP_502_BAD_GATEWAY)
    if isinstance(exc, InvalidCep):
        return _error("invalid_postal_code", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if isinstance(exc, CepNotFound):
        return _error("postal_code_not_found", status.HTTP_422_UNPROCESSABLE_CONTENT)
    mapping = {
        OrganizationNotFound: ("organization_not_found", status.HTTP_404_NOT_FOUND),
        VenueNotFound: ("venue_not_found", status.HTTP_404_NOT_FOUND),
        MemberNotFound: ("member_not_found", status.HTTP_404_NOT_FOUND),
        UserNotFound: ("user_not_found", status.HTTP_404_NOT_FOUND),
        UserNotActive: ("user_not_active", status.HTTP_409_CONFLICT),
        AlreadyMember: ("member_already_exists", status.HTTP_409_CONFLICT),
        CnpjAlreadyRegistered: ("cnpj_already_registered", status.HTTP_409_CONFLICT),
        CnpjChangeNotAllowed: ("cnpj_change_not_allowed", status.HTTP_409_CONFLICT),
        OrganizationNotVerified: ("organization_not_verified", status.HTTP_409_CONFLICT),
        OrganizationNotVerifiable: ("organization_not_verifiable", status.HTTP_409_CONFLICT),
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
        cnpj=organization.cnpj,
        cnpj_status=organization.cnpj_status,
        verification_status=organization.verification_status,
        cnpj_verified_at=organization.cnpj_verified_at,
        cnpj_next_check_at=organization.cnpj_next_check_at,
        payout_ready=payout_ready(organization),
        payout_status=organization.payout_status,
        pix_key_type=organization.pix_key_type,
        pix_key_masked=(
            mask_pix_key(organization.pix_key_type, organization.pix_key)
            if organization.pix_key and organization.pix_key_type
            else None
        ),
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
        latitude=venue.latitude,
        longitude=venue.longitude,
        postal_code=venue.postal_code,
        geocoding_source=venue.geocoding_source,
        geocoding_precision=venue.geocoding_precision,
        geocoded_at=venue.geocoded_at,
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
    settings: Annotated[Settings, Depends(get_settings)],
    lookup: Annotated[CnpjLookup, Depends(get_cnpj_lookup)],
) -> OrganizationView:
    service = OrganizationService(session)
    try:
        verification = verify_new_organization(
            session,
            actor_user_id=current.user_id,
            cnpj=payload.cnpj,
            cpf=payload.cpf,
            settings=settings,
            lookup=lookup,
        )
        organization = service.create_verified(
            current.user_id,
            payload.name,
            verification,
            recheck_days=settings.organization_cnpj_recheck_days,
        )
        session.commit()
    except CnpjVerificationError as exc:
        session.rollback()
        _audit_rejected_verification(session, current.user_id, payload.cnpj, exc)
        raise _handle(exc) from None
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _organization_view(
        service.get(current.user_id, organization.id),
    )


@router.post("/{organization_id}/verification", response_model=OrganizationView)
def verify_organization(
    organization_id: UUID,
    payload: OrganizationVerificationRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    lookup: Annotated[CnpjLookup, Depends(get_cnpj_lookup)],
) -> OrganizationView:
    """Regulariza organização existente (legado ``pending`` ou retry)."""

    service = OrganizationService(session)
    try:
        verification = verify_new_organization(
            session,
            actor_user_id=current.user_id,
            cnpj=payload.cnpj,
            cpf=payload.cpf,
            settings=settings,
            lookup=lookup,
        )
        organization = service.apply_verification(
            current.user_id,
            organization_id,
            verification,
            recheck_days=settings.organization_cnpj_recheck_days,
        )
        session.commit()
    except CnpjVerificationError as exc:
        session.rollback()
        _audit_rejected_verification(
            session,
            current.user_id,
            payload.cnpj,
            exc,
            organization_id=organization_id,
        )
        raise _handle(exc) from None
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _organization_view(
        service.get(current.user_id, organization.id),
    )


def _audit_rejected_verification(
    session: Session,
    actor_user_id: UUID,
    cnpj: str,
    exc: CnpjVerificationError,
    *,
    organization_id: UUID | None = None,
) -> None:
    """Persiste a recusa em transação própria; a operação principal falhou.

    A trilha não recebe CPF nem CNPJ completo. Se a gravação falhar, o erro
    original continua sendo devolvido ao painel.
    """

    details = {"result": "rejected", **exc.details}
    try:
        details.setdefault("cnpj_masked", mask_cnpj(cnpj))
    except Exception:  # noqa: BLE001
        details.setdefault("cnpj_masked", None)
    try:
        record_audit(
            session,
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="organization.cnpj_rejected",
            resource_type="organization" if organization_id else "organization_registration",
            resource_id=organization_id,
            details=details,
        )
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()


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


@router.put("/{organization_id}/payout", response_model=OrganizationView)
def update_payout(
    organization_id: UUID,
    payload: PayoutUpdate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> OrganizationView:
    service = OrganizationService(session)
    try:
        organization = service.set_payout(
            current.user_id,
            organization_id,
            legal_document=payload.legal_document,
            pix_key_type=payload.pix_key_type,
            pix_key=payload.pix_key,
        )
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
    settings: Annotated[Settings, Depends(get_settings)],
    postal_service: Annotated[PostalCodeService, Depends(get_postal_code_service)],
) -> VenueView:
    """Cadastra a quadra; com CEP, o servidor resolve as coordenadas."""

    geocoded = GeocodeOverrides()
    if payload.postal_code and (payload.latitude is None or payload.longitude is None):
        try:
            enforce_rate_limit(
                session,
                scope="org_venue_geocode",
                key=str(current.user_id),
                limit=settings.geo_rate_limit_per_minute,
            )
        except RateLimitExceeded as exc:
            session.rollback()
            raise _error(
                "rate_limited",
                status.HTTP_429_TOO_MANY_REQUESTS,
                retry_after=exc.retry_after_seconds,
            ) from None
        # Persistir o contador mesmo se o provedor falhar.
        session.commit()
        try:
            geocoded = geocode_if_needed(
                postal_service=postal_service,
                postal_code=payload.postal_code,
                latitude=payload.latitude,
                longitude=payload.longitude,
                city=payload.city,
                state=payload.state,
                address_line=payload.address_line,
            )
        except (InvalidCep, CepNotFound, CepTimeout, CepProviderUnavailable) as exc:
            session.rollback()
            raise _handle(exc) from None

    latitude = geocoded.latitude if geocoded.latitude is not None else payload.latitude
    longitude = geocoded.longitude if geocoded.longitude is not None else payload.longitude
    if latitude is None or longitude is None:
        raise _error(
            "geocoding_unresolved" if payload.postal_code else "geocoding_required",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    service = OrganizationService(session)
    try:
        venue = service.create_venue(
            current.user_id,
            organization_id,
            name=payload.name,
            city=geocoded.city if geocoded.city is not None else payload.city,
            state=geocoded.state if geocoded.state is not None else payload.state,
            address_line=(
                geocoded.address_line if geocoded.address_line is not None else payload.address_line
            ),
            latitude=latitude,
            longitude=longitude,
            postal_code=(
                geocoded.postal_code if geocoded.postal_code is not None else payload.postal_code
            ),
            geocoding_source=(
                geocoded.geocoding_source
                if geocoded.geocoding_source is not None
                else payload.geocoding_source
            ),
            geocoding_precision=(
                geocoded.geocoding_precision
                if geocoded.geocoding_precision is not None
                else payload.geocoding_precision
            ),
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
        total = service.count_audit(current.user_id, organization_id)
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
        total=total,
        limit=limit,
        offset=offset,
    )
