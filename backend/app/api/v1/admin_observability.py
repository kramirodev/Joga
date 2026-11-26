"""Endpoints administrativos de observabilidade (Fase 1, ADR 0078).

Acesso restrito ao ``platform_admin`` (mesma dependência de ``/admin/*``).
Step-up (SEC-003) ainda não existe: por isso toda consulta e exportação é
registrada em ``audit_logs`` com filtros e quantidade. Listagens mascaram IP;
detalhe e consulta por IP devolvem o valor completo.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.admin_guards import require_platform_admin
from app.core.config import Settings, get_settings
from app.core.request_context import normalize_ip
from app.infrastructure.database.dependency import get_session
from app.modules.identity.audit import record_audit
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.observability.models import LOG_CATEGORIES, LOG_LEVELS
from app.modules.observability.queries import (
    InvalidCursor,
    count_events,
    decode_cursor,
    get_event,
    ip_report,
    iter_events,
    list_events,
    normalize_window,
    summary,
    user_activity,
)
from app.modules.observability.schemas import (
    EventDetail,
    EventListResponse,
    IpReportResponse,
    ObservabilityFilters,
    SummaryResponse,
    UserActivityResponse,
)
from app.modules.ratelimit.service import RateLimitExceeded, enforce

router = APIRouter(prefix="/admin/observability", tags=["admin-observability"])

ADMIN_RATE_LIMIT_PER_MINUTE = 60
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

FromQuery = Annotated[datetime | None, Query(alias="from")]
ToQuery = Annotated[datetime | None, Query(alias="to")]
WindowQuery = Annotated[str, Query()]
LimitQuery = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
CursorQuery = Annotated[str | None, Query(max_length=512)]
EndpointQuery = Annotated[str | None, Query(max_length=255)]
StatusQuery = Annotated[int | None, Query(alias="status", ge=100, le=599)]
RequestIdQuery = Annotated[str | None, Query(max_length=64)]
CorrelationIdQuery = Annotated[str | None, Query(max_length=64)]
SearchQuery = Annotated[str | None, Query(max_length=100)]
FormatQuery = Annotated[str, Query(alias="format", pattern="^(csv|json)$")]


def _error(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def require_observability_access(
    admin: Annotated[AuthenticatedSession, Depends(require_platform_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> AuthenticatedSession:
    """Exige platform_admin e aplica limite próprio por minuto."""
    try:
        enforce(
            session,
            scope="observability_admin",
            key=str(admin.user_id),
            limit=ADMIN_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
        )
        session.commit()
    except RateLimitExceeded as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited"},
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from None
    return admin


Admin = Annotated[AuthenticatedSession, Depends(require_observability_access)]
DbSession = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _filters(
    *,
    from_at: datetime | None,
    to_at: datetime | None,
    level: str | None,
    category: str | None,
    user_id: uuid.UUID | None,
    ip: str | None,
    endpoint: str | None,
    status_code: int | None,
    request_id: str | None,
    correlation_id: str | None,
    q: str | None,
) -> ObservabilityFilters:
    if level is not None and level not in LOG_LEVELS:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_level")
    if category is not None and category not in LOG_CATEGORIES:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_category")
    if from_at is not None and to_at is not None and from_at > to_at:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_time_range")
    normalized_ip = None
    if ip is not None:
        normalized_ip = normalize_ip(ip)
        if normalized_ip is None:
            raise _error(status.HTTP_400_BAD_REQUEST, "invalid_ip")
    return ObservabilityFilters(
        from_at=from_at,
        to_at=to_at,
        level=level,
        category=category,
        user_id=user_id,
        ip=normalized_ip,
        endpoint=endpoint,
        status=status_code,
        request_id=request_id,
        correlation_id=correlation_id,
        q=q,
    )


def _filters_payload(filters: ObservabilityFilters) -> dict[str, Any]:
    payload = {key: value for key, value in filters.model_dump().items() if value is not None}
    for key, value in list(payload.items()):
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            payload[key] = str(value)
    payload["has_ip_filter"] = filters.ip is not None
    payload["has_user_filter"] = filters.user_id is not None
    return payload


def _audit_query(
    session: Session,
    admin: AuthenticatedSession,
    *,
    action: str,
    filters: ObservabilityFilters,
    count: int,
    extra: dict[str, Any] | None = None,
) -> None:
    record_audit(
        session,
        actor_user_id=admin.user_id,
        action=action,
        resource_type="observability",
        resource_id=None,
        details={
            "filters": _filters_payload(filters),
            "count": count,
            **(extra or {}),
        },
    )
    session.commit()


def _cursor(value: str | None) -> tuple[datetime, uuid.UUID] | None:
    if value is None:
        return None
    try:
        return decode_cursor(value)
    except InvalidCursor:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_cursor") from None


@router.get("/summary", response_model=SummaryResponse)
def read_summary(
    admin: Admin,
    session: DbSession,
    window: WindowQuery = "24h",
) -> SummaryResponse:
    try:
        normalize_window(window)
    except ValueError:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_window") from None
    current, previous = summary(session, window)
    _audit_query(
        session,
        admin,
        action="observability.query",
        filters=ObservabilityFilters(),
        count=current.total_events,
        extra={"view": "summary", "window": window},
    )
    return SummaryResponse(window=window, current=current, previous=previous)


@router.get("/events", response_model=EventListResponse)
def read_events(
    admin: Admin,
    session: DbSession,
    from_at: FromQuery = None,
    to_at: ToQuery = None,
    level: str | None = None,
    category: str | None = None,
    user_id: uuid.UUID | None = None,
    ip: str | None = None,
    endpoint: EndpointQuery = None,
    status_code: StatusQuery = None,
    request_id: RequestIdQuery = None,
    correlation_id: CorrelationIdQuery = None,
    q: SearchQuery = None,
    cursor: CursorQuery = None,
    limit: LimitQuery = DEFAULT_PAGE_SIZE,
) -> EventListResponse:
    filters = _filters(
        from_at=from_at,
        to_at=to_at,
        level=level,
        category=category,
        user_id=user_id,
        ip=ip,
        endpoint=endpoint,
        status_code=status_code,
        request_id=request_id,
        correlation_id=correlation_id,
        q=q,
    )
    page = list_events(session, filters, limit=limit, cursor=_cursor(cursor))
    _audit_query(
        session,
        admin,
        action="observability.query",
        filters=filters,
        count=len(page.events),
        extra={"view": "events", "limit": limit, "cursor": cursor is not None},
    )
    return EventListResponse(events=page.events, next_cursor=page.next_cursor)


@router.get("/events/{event_id}", response_model=EventDetail)
def read_event(
    event_id: uuid.UUID,
    admin: Admin,
    session: DbSession,
) -> EventDetail:
    detail = get_event(session, event_id)
    if detail is None:
        raise _error(status.HTTP_404_NOT_FOUND, "event_not_found")
    _audit_query(
        session,
        admin,
        action="observability.query",
        filters=ObservabilityFilters(),
        count=1,
        extra={"view": "event_detail", "event_id": str(event_id)},
    )
    return detail


@router.get("/users/{user_id}/activity", response_model=UserActivityResponse)
def read_user_activity(
    user_id: uuid.UUID,
    admin: Admin,
    session: DbSession,
    from_at: FromQuery = None,
    to_at: ToQuery = None,
    category: str | None = None,
    cursor: CursorQuery = None,
    limit: LimitQuery = DEFAULT_PAGE_SIZE,
) -> UserActivityResponse:
    if category is not None and category not in LOG_CATEGORIES:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_category")
    filters = _filters(
        from_at=from_at,
        to_at=to_at,
        level=None,
        category=category,
        user_id=user_id,
        ip=None,
        endpoint=None,
        status_code=None,
        request_id=None,
        correlation_id=None,
        q=None,
    )
    page = user_activity(session, user_id, filters, limit=limit, cursor=_cursor(cursor))
    _audit_query(
        session,
        admin,
        action="observability.query",
        filters=filters,
        count=len(page.events),
        extra={"view": "user_activity", "user_id": str(user_id)},
    )
    return UserActivityResponse(user_id=user_id, events=page.events, next_cursor=page.next_cursor)


@router.get("/ips/{ip}", response_model=IpReportResponse)
def read_ip(
    ip: Annotated[str, Path(min_length=2, max_length=45)],
    admin: Admin,
    session: DbSession,
) -> IpReportResponse:
    normalized = normalize_ip(ip)
    if normalized is None:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_ip")
    report = ip_report(session, normalized)
    _audit_query(
        session,
        admin,
        action="observability.query",
        filters=ObservabilityFilters(ip=normalized),
        count=report.total_events,
        extra={"view": "ip", "security_events": report.security_events},
    )
    return report


EXPORT_COLUMNS = (
    "id",
    "occurred_at",
    "level",
    "category",
    "source",
    "module",
    "request_id",
    "correlation_id",
    "user_id",
    "ip",
    "user_agent",
    "endpoint",
    "status",
    "duration_ms",
    "message",
    "error_code",
)


def _csv_stream(rows: Iterator[Any]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(EXPORT_COLUMNS)
    yield buffer.getvalue()
    for view in rows:
        buffer.seek(0)
        buffer.truncate()
        payload = view.model_dump(mode="json")
        writer.writerow([payload.get(column) for column in EXPORT_COLUMNS])
        yield buffer.getvalue()


def _json_stream(rows: Iterator[Any]) -> Iterator[str]:
    yield "["
    first = True
    for view in rows:
        if not first:
            yield ","
        yield json.dumps(view.model_dump(mode="json"), ensure_ascii=False)
        first = False
    yield "]"


@router.get("/export")
def export_events(
    admin: Admin,
    session: DbSession,
    settings: SettingsDep,
    format_: FormatQuery = "csv",
    from_at: FromQuery = None,
    to_at: ToQuery = None,
    level: str | None = None,
    category: str | None = None,
    user_id: uuid.UUID | None = None,
    ip: str | None = None,
    endpoint: EndpointQuery = None,
    status_code: StatusQuery = None,
    request_id: RequestIdQuery = None,
    correlation_id: CorrelationIdQuery = None,
    q: SearchQuery = None,
    full_ip: bool = False,
) -> StreamingResponse:
    filters = _filters(
        from_at=from_at,
        to_at=to_at,
        level=level,
        category=category,
        user_id=user_id,
        ip=ip,
        endpoint=endpoint,
        status_code=status_code,
        request_id=request_id,
        correlation_id=correlation_id,
        q=q,
    )
    total = count_events(session, filters)
    exported = min(total, settings.log_max_export_rows)
    _audit_query(
        session,
        admin,
        action="observability.export",
        filters=filters,
        count=exported,
        extra={
            "format": format_,
            "full_ip": full_ip,
            "truncated": total > exported,
            "max_rows": settings.log_max_export_rows,
        },
    )
    rows = iter_events(
        session,
        filters,
        max_rows=exported,
        mask=not full_ip,
    )
    stream = _csv_stream(rows) if format_ == "csv" else _json_stream(rows)
    media_type = "text/csv; charset=utf-8" if format_ == "csv" else "application/json"
    filename = f"observability-{datetime.now().strftime('%Y%m%dT%H%M%SZ')}.{format_}"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Export-Rows": str(exported),
        "X-Export-Truncated": "true" if total > exported else "false",
    }
    return StreamingResponse(stream, media_type=media_type, headers=headers)


__all__ = ["router"]
