"""Administração de plataforma: esportes, preço e usuários.

Todas as rotas exigem `JOGA_PLATFORM_ADMINS`. Escritas exigem `reason` e geram
auditoria append-only. O painel não altera MMR, ledger, tickets ou resultado.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.admin_guards import require_platform_admin
from app.api.v1.admin_reason import clean_reason
from app.api.v1.auth import get_session_service
from app.api.v1.catalog import SportCategory, SportFormatView
from app.api.v1.email_auth import (
    get_email_challenge_service,
    get_email_delivery_service,
    get_password_service,
)
from app.api.v1.request_context import request_ip_hash
from app.core.config import Settings, get_settings
from app.core.text import (
    FreeText,
    LatinName,
    OptionalDisplayName,
    OptionalFreeText,
    OptionalLatinName,
)
from app.infrastructure.database.dependency import get_session
from app.modules.catalog.sports import (
    FormatInput,
    FormatInUse,
    FormatNotFound,
    FormatSlugConflict,
    InvalidFormat,
    InvalidSport,
    InvalidSportIcon,
    PricingNotConfigured,
    SportNotFound,
    SportNotPublishable,
    SportSlugConflict,
    activate_format,
    activate_sport,
    add_format,
    all_formats,
    create_sport,
    deactivate_format,
    deactivate_sport,
    format_in_use,
    get_format,
    get_sport,
    list_admin_catalog,
    update_format,
    update_sport,
)
from app.modules.email.addresses import InvalidEmail
from app.modules.email.deliveries import EmailBudgetExhausted, EmailDeliveryService
from app.modules.identity.audit import record_audit
from app.modules.identity.email_challenges import DisposableEmailDomain, EmailChallengeService
from app.modules.identity.otp import HourlyLimitReached, IpLimitReached, ResendTooSoon
from app.modules.identity.passwords import PasswordInput, PasswordPolicyError, PasswordService
from app.modules.identity.sessions import AuthenticatedSession, SessionService
from app.modules.identity.user_admin import (
    AdminEmailConflict,
    AdminEmailUnchanged,
    AdminUserNotFound,
    AdminUserView,
    InvalidAdminUser,
    ReasonRequired,
    change_email,
    create_user,
    get_user,
    list_audit,
    reactivate_user,
    request_password_reset,
    revoke_sessions,
    search_users,
    suspend_user,
)
from app.modules.pricing.suggest import (
    InvalidBandTicketsFloor,
    InvalidPricingMode,
    InvalidPricingTeamSize,
    PricingBandNotFound,
    PricingModeRequired,
    build_suggestion,
    override_band_tickets,
)
from app.modules.profile.models import Sport, SportFormat

router = APIRouter(prefix="/admin", tags=["admin"])


def _error(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _format_snapshot(item: SportFormat) -> dict[str, object]:
    return {
        "name": item.name,
        "team_size": item.team_size,
        "players_per_team": item.players_per_team,
        "total_participants": item.total_participants,
        "duration_minutes": item.duration_minutes,
        "period_count": item.period_count,
        "score_model": item.score_model,
        "positions": list(item.positions or []),
        "active": item.active,
        "version": item.version,
    }


def _admin_format_view(session: Session, item: SportFormat) -> AdminSportFormatView:
    return AdminSportFormatView(
        id=item.id,
        slug=item.slug,
        name=item.name,
        team_size=item.team_size,
        players_per_team=item.players_per_team,
        total_participants=item.total_participants,
        duration_minutes=item.duration_minutes,
        period_count=item.period_count,
        score_model=item.score_model,
        positions=list(item.positions or []),
        active=item.active,
        version=item.version,
        in_use=format_in_use(session, item.id),
    )


def _admin_sport_view(session: Session, sport: Sport, formats: list[SportFormat]) -> AdminSportView:
    return AdminSportView(
        id=sport.id,
        slug=sport.slug,
        name=sport.name,
        category=cast(SportCategory, sport.category),
        icon_key=sport.icon_key,
        sort_order=sport.sort_order,
        active=sport.active,
        formats=[_admin_format_view(session, item) for item in formats],
    )


def _admin_user_view(item: AdminUserView) -> AdminUserResponse:
    return AdminUserResponse(
        id=item.id,
        tag=item.tag,
        status=item.status,
        email=item.email,
        display_name=item.display_name,
        email_verified=item.email_verified,
        cpf_masked=item.cpf_masked,
        suspended_until=item.suspended_until,
        created_at=item.created_at,
    )


def _sport_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SportNotFound):
        return _error(status.HTTP_404_NOT_FOUND, "sport_not_found")
    if isinstance(exc, SportSlugConflict):
        return _error(status.HTTP_409_CONFLICT, "sport_slug_conflict")
    if isinstance(exc, InvalidSportIcon):
        return _error(status.HTTP_400_BAD_REQUEST, "invalid_sport_icon")
    if isinstance(exc, SportNotPublishable):
        return _error(status.HTTP_409_CONFLICT, "sport_not_publishable")
    if isinstance(exc, FormatNotFound):
        return _error(status.HTTP_404_NOT_FOUND, "format_not_found")
    if isinstance(exc, FormatSlugConflict):
        return _error(status.HTTP_409_CONFLICT, "format_slug_conflict")
    if isinstance(exc, FormatInUse):
        return _error(status.HTTP_409_CONFLICT, "format_in_use")
    if isinstance(exc, PricingNotConfigured):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "pricing_not_configured")
    if isinstance(exc, InvalidFormat):
        return _error(status.HTTP_400_BAD_REQUEST, "invalid_format")
    if isinstance(exc, InvalidSport):
        return _error(status.HTTP_400_BAD_REQUEST, "invalid_sport")
    raise exc


def _pricing_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PricingModeRequired):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "pricing_mode_required")
    if isinstance(exc, (InvalidPricingMode, InvalidPricingTeamSize)):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_pricing_mode")
    if isinstance(exc, PricingBandNotFound):
        return _error(status.HTTP_404_NOT_FOUND, "band_not_found")
    if isinstance(exc, InvalidBandTicketsFloor):
        return _error(status.HTTP_409_CONFLICT, "ticket_floor_violation")
    raise exc


def _user_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ReasonRequired):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    if isinstance(exc, AdminUserNotFound):
        return _error(status.HTTP_404_NOT_FOUND, "user_not_found")
    if isinstance(exc, AdminEmailConflict):
        return _error(status.HTTP_409_CONFLICT, "email_already_registered")
    if isinstance(exc, AdminEmailUnchanged):
        return _error(status.HTTP_409_CONFLICT, "email_unchanged")
    if isinstance(exc, (InvalidEmail, DisposableEmailDomain)):
        return _error(status.HTTP_400_BAD_REQUEST, "invalid_email")
    if isinstance(exc, PasswordPolicyError):
        return _error(status.HTTP_400_BAD_REQUEST, "weak_password")
    if isinstance(exc, (ResendTooSoon, HourlyLimitReached, IpLimitReached)):
        return _error(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")
    if isinstance(exc, InvalidAdminUser):
        return _error(status.HTTP_400_BAD_REQUEST, "invalid_user")
    raise exc


class SportFormatInput(BaseModel):
    slug: FreeText = Field(min_length=2, max_length=40)
    name: LatinName = Field(min_length=2, max_length=80)
    team_size: int = Field(ge=1, le=20)
    players_per_team: int | None = Field(default=None, ge=1, le=20)
    duration_minutes: int = Field(ge=5, le=240)
    period_count: int = Field(default=1, ge=1, le=20)
    score_model: str = Field(default="sets_points", pattern="^(sets_points|goals)$")
    positions: list[str] = Field(default_factory=list, max_length=20)


class SportCreateRequest(BaseModel):
    slug: FreeText = Field(min_length=2, max_length=40)
    name: LatinName = Field(min_length=2, max_length=80)
    category: SportCategory = "collective"
    icon_key: FreeText = Field(min_length=2, max_length=64)
    sort_order: int = Field(default=0, ge=0)
    formats: list[SportFormatInput] = Field(min_length=1, max_length=10)
    reason: FreeText = Field(min_length=1, max_length=500)


class SportUpdateRequest(BaseModel):
    name: OptionalLatinName = Field(default=None, min_length=2, max_length=80)
    category: SportCategory | None = None
    icon_key: OptionalFreeText = Field(default=None, min_length=2, max_length=64)
    sort_order: int | None = Field(default=None, ge=0)
    reason: FreeText = Field(min_length=1, max_length=500)


class AdminSportFormatView(SportFormatView):
    """Formato administrativo com o indicador de uso histórico."""

    in_use: bool


class AdminSportView(BaseModel):
    id: UUID
    slug: str
    name: str
    category: SportCategory
    icon_key: str
    sort_order: int
    active: bool
    formats: list[AdminSportFormatView]


class SportFormatAddRequest(SportFormatInput):
    reason: FreeText = Field(min_length=1, max_length=500)


class SportFormatUpdateRequest(BaseModel):
    name: OptionalLatinName = Field(default=None, min_length=2, max_length=80)
    team_size: int | None = Field(default=None, ge=1, le=20)
    players_per_team: int | None = Field(default=None, ge=1, le=20)
    duration_minutes: int | None = Field(default=None, ge=5, le=240)
    period_count: int | None = Field(default=None, ge=1, le=20)
    score_model: str | None = Field(default=None, pattern="^(sets_points|goals)$")
    positions: list[str] | None = Field(default=None, max_length=20)
    active: bool | None = None
    reason: FreeText = Field(min_length=1, max_length=500)


class SportListResponse(BaseModel):
    sports: list[AdminSportView]


class BandSuggestionView(BaseModel):
    code: str
    label: str
    max_price_cents: int
    tickets: int
    player_price_cents: int
    invariant_ok: bool


class PricingSuggestionView(BaseModel):
    team_size: int
    mode: str
    calibration_cents: int
    bands: list[BandSuggestionView]


class BandTicketsOverrideRequest(BaseModel):
    band_code: str = Field(min_length=2, max_length=40)
    team_size: int = Field(ge=1, le=20)
    tickets: int = Field(ge=1, le=1000)
    mode: str | None = Field(default=None, pattern="^(standard|contingency)$")
    reason: FreeText = Field(min_length=1, max_length=500)


class BandTicketsOverrideResponse(BaseModel):
    band_code: str
    team_size: int
    tickets: int
    player_price_cents: int
    mode: str
    invariant_ok: bool


class AdminUserResponse(BaseModel):
    id: UUID
    tag: str
    status: str
    email: str | None
    display_name: str | None
    email_verified: bool
    cpf_masked: str | None
    suspended_until: datetime | None
    created_at: datetime


class AdminUserListResponse(BaseModel):
    users: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminUserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: PasswordInput = Field(min_length=1, max_length=256)
    display_name: OptionalDisplayName = Field(default=None)
    verify_email: bool = False
    reason: FreeText = Field(min_length=1, max_length=500)


class AdminUserEmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    reason: FreeText = Field(min_length=1, max_length=500)


class AdminReasonRequest(BaseModel):
    reason: FreeText = Field(min_length=1, max_length=500)


class AdminSuspendRequest(BaseModel):
    reason: FreeText = Field(min_length=1, max_length=500)
    until: datetime | None = None


class AdminSessionRevokeResponse(BaseModel):
    revoked: int


class AuditLogResponse(BaseModel):
    id: UUID
    action: str
    actor_user_id: UUID | None
    reason: str | None
    details: dict[str, object] | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    events: list[AuditLogResponse]


@router.get("/sports", response_model=SportListResponse)
def list_admin_sports(
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> SportListResponse:
    del admin
    return SportListResponse(
        sports=[
            _admin_sport_view(session, sport, formats)
            for sport, formats in list_admin_catalog(session)
        ]
    )


@router.post("/sports", response_model=AdminSportView, status_code=status.HTTP_201_CREATED)
def create_admin_sport(
    payload: SportCreateRequest,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> AdminSportView:
    """Cria esporte + formatos em uma transação; o esporte nasce inativo."""

    try:
        sport = create_sport(
            session,
            slug=payload.slug,
            name=payload.name,
            category=payload.category,
            icon_key=payload.icon_key,
            sort_order=payload.sort_order,
            formats=[
                FormatInput(
                    slug=item.slug,
                    name=item.name,
                    team_size=item.team_size,
                    players_per_team=item.players_per_team,
                    duration_minutes=item.duration_minutes,
                    period_count=item.period_count,
                    score_model=item.score_model,
                    positions=item.positions,
                )
                for item in payload.formats
            ],
        )
        formats = all_formats(session, sport.id)
        record_audit(
            session,
            actor_user_id=admin.user_id,
            action="admin.sport.create",
            resource_type="sport",
            resource_id=sport.id,
            reason=clean_reason(payload.reason),
            details={"slug": sport.slug, "active": False, "category": sport.category},
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _sport_error(exc) from None
    return _admin_sport_view(session, sport, formats)


@router.patch("/sports/{slug}", response_model=AdminSportView)
def update_admin_sport(
    slug: str,
    payload: SportUpdateRequest,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> AdminSportView:
    try:
        sport = update_sport(
            session,
            slug=slug,
            name=payload.name,
            icon_key=payload.icon_key,
            sort_order=payload.sort_order,
            category=payload.category,
        )
        formats = all_formats(session, sport.id)
        record_audit(
            session,
            actor_user_id=admin.user_id,
            action="admin.sport.update",
            resource_type="sport",
            resource_id=sport.id,
            reason=clean_reason(payload.reason),
            details={"slug": sport.slug, "category": sport.category},
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _sport_error(exc) from None
    return _admin_sport_view(session, sport, formats)


@router.post("/sports/{slug}/activate", response_model=AdminSportView)
def activate_admin_sport(
    slug: str,
    payload: AdminReasonRequest,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> AdminSportView:
    try:
        sport = activate_sport(session, slug)
        formats = all_formats(session, sport.id)
        record_audit(
            session,
            actor_user_id=admin.user_id,
            action="admin.sport.activate",
            resource_type="sport",
            resource_id=sport.id,
            reason=clean_reason(payload.reason),
            details={"slug": sport.slug},
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _sport_error(exc) from None
    return _admin_sport_view(session, sport, formats)


@router.post("/sports/{slug}/deactivate", response_model=AdminSportView)
def deactivate_admin_sport(
    slug: str,
    payload: AdminReasonRequest,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> AdminSportView:
    """Despublica preservando formatos, preços e referências históricas."""

    try:
        sport = deactivate_sport(session, slug)
        formats = all_formats(session, sport.id)
        record_audit(
            session,
            actor_user_id=admin.user_id,
            action="admin.sport.deactivate",
            resource_type="sport",
            resource_id=sport.id,
            reason=clean_reason(payload.reason),
            details={"slug": sport.slug},
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _sport_error(exc) from None
    return _admin_sport_view(session, sport, formats)


@router.post(
    "/sports/{slug}/formats",
    response_model=AdminSportFormatView,
    status_code=status.HTTP_201_CREATED,
)
def add_admin_sport_format(
    slug: str,
    payload: SportFormatAddRequest,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminSportFormatView:
    """Adiciona formato ativo; exige preço em todas as faixas ativas."""

    try:
        row = add_format(
            session,
            slug=slug,
            spec=FormatInput(
                slug=payload.slug,
                name=payload.name,
                team_size=payload.team_size,
                players_per_team=payload.players_per_team,
                duration_minutes=payload.duration_minutes,
                period_count=payload.period_count,
                score_model=payload.score_model,
                positions=payload.positions,
            ),
        )
        record_audit(
            session,
            actor_user_id=admin.user_id,
            action="admin.sport.format.create",
            resource_type="sport_format",
            resource_id=row.id,
            reason=clean_reason(payload.reason),
            details={
                "sport_slug": slug,
                "format_slug": row.slug,
                "team_size": row.team_size,
                "version": row.version,
                "ip_hash": request_ip_hash(request, settings),
            },
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _sport_error(exc) from None
    return _admin_format_view(session, row)


@router.patch(
    "/sports/{slug}/formats/{format_id}",
    response_model=AdminSportFormatView,
)
def update_admin_sport_format(
    slug: str,
    format_id: UUID,
    payload: SportFormatUpdateRequest,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminSportFormatView:
    """Edita nome/duração/períodos/pontuação/posições; team_size só sem uso."""

    try:
        sport = get_sport(session, slug)
        before = _format_snapshot(get_format(session, sport, format_id))
        row = update_format(
            session,
            slug=slug,
            format_id=format_id,
            name=payload.name,
            team_size=payload.team_size,
            players_per_team=payload.players_per_team,
            duration_minutes=payload.duration_minutes,
            period_count=payload.period_count,
            score_model=payload.score_model,
            positions=payload.positions,
            active=payload.active,
        )
        after = _format_snapshot(row)
        changed = {
            key: {"before": before[key], "after": after[key]}
            for key in before
            if before[key] != after[key]
        }
        record_audit(
            session,
            actor_user_id=admin.user_id,
            action="admin.sport.format.update",
            resource_type="sport_format",
            resource_id=row.id,
            reason=clean_reason(payload.reason),
            details={
                "sport_slug": slug,
                "format_slug": row.slug,
                "changed": changed,
                "ip_hash": request_ip_hash(request, settings),
            },
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _sport_error(exc) from None
    return _admin_format_view(session, row)


@router.post(
    "/sports/{slug}/formats/{format_id}/activate",
    response_model=AdminSportFormatView,
)
def activate_admin_sport_format(
    slug: str,
    format_id: UUID,
    payload: AdminReasonRequest,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminSportFormatView:
    try:
        row = activate_format(session, slug=slug, format_id=format_id)
        record_audit(
            session,
            actor_user_id=admin.user_id,
            action="admin.sport.format.activate",
            resource_type="sport_format",
            resource_id=row.id,
            reason=clean_reason(payload.reason),
            details={
                "sport_slug": slug,
                "format_slug": row.slug,
                "active": True,
                "ip_hash": request_ip_hash(request, settings),
            },
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _sport_error(exc) from None
    return _admin_format_view(session, row)


@router.post(
    "/sports/{slug}/formats/{format_id}/deactivate",
    response_model=AdminSportFormatView,
)
def deactivate_admin_sport_format(
    slug: str,
    format_id: UUID,
    payload: AdminReasonRequest,
    request: Request,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminSportFormatView:
    try:
        row = deactivate_format(session, slug=slug, format_id=format_id)
        record_audit(
            session,
            actor_user_id=admin.user_id,
            action="admin.sport.format.deactivate",
            resource_type="sport_format",
            resource_id=row.id,
            reason=clean_reason(payload.reason),
            details={
                "sport_slug": slug,
                "format_slug": row.slug,
                "active": False,
                "ip_hash": request_ip_hash(request, settings),
            },
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _sport_error(exc) from None
    return _admin_format_view(session, row)


@router.get("/pricing/suggest", response_model=PricingSuggestionView)
def suggest_pricing(
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    team_size: Annotated[int, Query(ge=1, le=20)],
    mode: Annotated[str | None, Query(pattern="^(standard|contingency)$")] = None,
) -> PricingSuggestionView:
    del admin
    try:
        suggestion = build_suggestion(session, team_size=team_size, mode=mode)
    except Exception as exc:  # noqa: BLE001
        raise _pricing_error(exc) from None
    return PricingSuggestionView(
        team_size=suggestion.team_size,
        mode=suggestion.mode,
        calibration_cents=suggestion.calibration_cents,
        bands=[
            BandSuggestionView(
                code=band.code,
                label=band.label,
                max_price_cents=band.max_price_cents,
                tickets=band.tickets,
                player_price_cents=band.player_price_cents,
                invariant_ok=band.invariant_ok,
            )
            for band in suggestion.bands
        ],
    )


@router.put("/pricing/band-tickets", response_model=BandTicketsOverrideResponse)
def override_pricing_band_tickets(
    payload: BandTicketsOverrideRequest,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> BandTicketsOverrideResponse:
    try:
        row = override_band_tickets(
            session,
            band_code=payload.band_code,
            team_size=payload.team_size,
            tickets=payload.tickets,
            mode=payload.mode,
        )
        suggestion = build_suggestion(session, team_size=payload.team_size, mode=payload.mode)
        band = next(item for item in suggestion.bands if item.code == payload.band_code)
        record_audit(
            session,
            actor_user_id=admin.user_id,
            action="admin.pricing.band_tickets_override",
            resource_type="pricing_band_tickets",
            resource_id=row.id,
            reason=clean_reason(payload.reason),
            details={
                "band_code": payload.band_code,
                "team_size": payload.team_size,
                "tickets": payload.tickets,
                "mode": suggestion.mode,
            },
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _pricing_error(exc) from None
    return BandTicketsOverrideResponse(
        band_code=payload.band_code,
        team_size=payload.team_size,
        tickets=row.tickets,
        player_price_cents=row.tickets * suggestion.calibration_cents,
        mode=suggestion.mode,
        invariant_ok=band.invariant_ok,
    )


@router.get("/users", response_model=AdminUserListResponse)
def list_admin_users(
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[str | None, Query(max_length=120)] = None,
    user_status: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> AdminUserListResponse:
    del admin
    try:
        users, total = search_users(
            session,
            search=q,
            status=user_status,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:  # noqa: BLE001
        raise _user_error(exc) from None
    return AdminUserListResponse(
        users=[_admin_user_view(item) for item in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=AdminUserResponse)
def read_admin_user(
    user_id: UUID,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> AdminUserResponse:
    """Detalhe mínimo: CPF mascarado; sem hash, token, OTP ou senha."""

    del admin
    try:
        item = get_user(session, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _user_error(exc) from None
    return _admin_user_view(item)


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_admin_user(
    payload: AdminUserCreateRequest,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    passwords: Annotated[PasswordService, Depends(get_password_service)],
) -> AdminUserResponse:
    try:
        item = create_user(
            session,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
            verify_email=payload.verify_email,
            passwords=passwords,
            actor_user_id=admin.user_id,
            reason=clean_reason(payload.reason),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _user_error(exc) from None
    return _admin_user_view(item)


@router.patch("/users/{user_id}/email", response_model=AdminUserResponse)
def change_admin_user_email(
    user_id: UUID,
    payload: AdminUserEmailRequest,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    deliveries: Annotated[EmailDeliveryService, Depends(get_email_delivery_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> AdminUserResponse:
    """Troca o e-mail, avisa o endereço antigo e revoga todas as sessões."""

    try:
        change_email(
            session,
            user_id=user_id,
            email=payload.email,
            deliveries=deliveries,
            actor_user_id=admin.user_id,
            reason=clean_reason(payload.reason),
        )
        sessions.revoke_all(user_id, reason="admin_email_change")
        item = get_user(session, user_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _user_error(exc) from None
    return _admin_user_view(item)


@router.post("/users/{user_id}/password-reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_admin_user_password(
    user_id: UUID,
    payload: AdminReasonRequest,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    challenges: Annotated[EmailChallengeService, Depends(get_email_challenge_service)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> Response:
    """Envia código de redefinição; nenhum código/hash volta na resposta."""

    try:
        request_password_reset(
            session,
            user_id=user_id,
            challenges=challenges,
            actor_user_id=admin.user_id,
            reason=clean_reason(payload.reason),
        )
        sessions.revoke_all(user_id, reason="admin_password_reset")
        session.commit()
    except EmailBudgetExhausted:
        session.rollback()
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "email_unavailable") from None
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _user_error(exc) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/suspend", response_model=AdminUserResponse)
def suspend_admin_user(
    user_id: UUID,
    payload: AdminSuspendRequest,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> AdminUserResponse:
    try:
        item = suspend_user(
            session,
            user_id=user_id,
            until=payload.until,
            sessions=sessions,
            actor_user_id=admin.user_id,
            reason=clean_reason(payload.reason),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _user_error(exc) from None
    return _admin_user_view(item)


@router.post("/users/{user_id}/reactivate", response_model=AdminUserResponse)
def reactivate_admin_user(
    user_id: UUID,
    payload: AdminReasonRequest,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> AdminUserResponse:
    try:
        item = reactivate_user(
            session,
            user_id=user_id,
            actor_user_id=admin.user_id,
            reason=clean_reason(payload.reason),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _user_error(exc) from None
    return _admin_user_view(item)


@router.post("/users/{user_id}/sessions/revoke", response_model=AdminSessionRevokeResponse)
def revoke_admin_user_sessions(
    user_id: UUID,
    payload: AdminReasonRequest,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> AdminSessionRevokeResponse:
    try:
        revoked = revoke_sessions(
            session,
            user_id=user_id,
            sessions=sessions,
            actor_user_id=admin.user_id,
            reason=clean_reason(payload.reason),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _user_error(exc) from None
    return AdminSessionRevokeResponse(revoked=revoked)


@router.get("/users/{user_id}/audit", response_model=AuditLogListResponse)
def read_admin_user_audit(
    user_id: UUID,
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> AuditLogListResponse:
    del admin
    try:
        events = list_audit(session, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _user_error(exc) from None
    return AuditLogListResponse(
        events=[
            AuditLogResponse(
                id=event.id,
                action=event.action,
                actor_user_id=event.actor_user_id,
                reason=event.reason,
                details=event.details,
                created_at=event.created_at,
            )
            for event in events
        ]
    )


__all__ = ["router"]
