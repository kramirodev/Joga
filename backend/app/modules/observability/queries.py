"""Consultas administrativas de observabilidade (ADR 0078).

Listagens mascaram o IP; detalhe e consulta por IP devolvem o valor completo.
Somente ``platform_admin`` chega aqui, e a camada de rota audita cada consulta.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc
from app.modules.identity.events import (
    EMAIL_LOGIN_FAILED,
    EMAIL_VERIFICATION_FAILED,
    HTTP_FORBIDDEN,
    HTTP_RATE_LIMITED,
    HTTP_UNAUTHORIZED,
    OTP_RATE_LIMITED,
    OTP_VERIFICATION_FAILED,
    PASSKEY_FAILED,
    PASSKEY_RATE_LIMITED,
)
from app.modules.identity.models import AuditLog, SecurityEvent
from app.modules.observability.models import LogEvent
from app.modules.observability.redaction import mask_ip
from app.modules.observability.schemas import (
    AlertItem,
    AlertsResponse,
    AuthSummary,
    CategoryCount,
    EventDetail,
    EventView,
    HttpSummary,
    IpReportResponse,
    IpUserEntry,
    JobSummary,
    LevelCount,
    ObservabilityFilters,
    SummaryWindow,
    SuspiciousUser,
)

FAILURE_RESULTS = ("failure", "blocked")
WINDOW_SIZES = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}
LOGIN_FAILURE_MARKERS = (
    "%login_failed%",
    "%verification_failed%",
    "%otp.failed%",
    "%passkey.failed%",
)
RATE_LIMITED_TYPES = (
    HTTP_RATE_LIMITED,
    OTP_RATE_LIMITED,
    PASSKEY_RATE_LIMITED,
)


class InvalidCursor(ValueError):
    """Cursor de paginação malformado."""


@dataclass(frozen=True, slots=True)
class Page:
    events: list[EventView]
    next_cursor: str | None


def normalize_window(value: str) -> timedelta:
    size = WINDOW_SIZES.get(value)
    if size is None:
        raise ValueError("window deve ser 24h ou 7d")
    return size


def encode_cursor(moment: datetime, event_id: uuid.UUID) -> str:
    raw = f"{ensure_utc(moment).isoformat()}|{event_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(value: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
        moment_text, id_text = raw.rsplit("|", 1)
        return ensure_utc(datetime.fromisoformat(moment_text)), uuid.UUID(id_text)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise InvalidCursor("cursor inválido") from exc


def _pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _in_window(column: Any, filters: ObservabilityFilters) -> list[Any]:
    clauses: list[Any] = []
    if filters.from_at is not None:
        clauses.append(column >= ensure_utc(filters.from_at))
    if filters.to_at is not None:
        clauses.append(column <= ensure_utc(filters.to_at))
    return clauses


def _before_cursor(column: Any, id_column: Any, cursor: tuple[datetime, uuid.UUID]) -> Any:
    moment, event_id = cursor
    return or_(
        column < moment,
        and_(column == moment, id_column < event_id),
    )


def _log_filters(filters: ObservabilityFilters) -> list[Any]:
    clauses = _in_window(LogEvent.occurred_at, filters)
    if filters.level:
        clauses.append(LogEvent.level == filters.level)
    if filters.category:
        clauses.append(LogEvent.category == filters.category)
    if filters.user_id:
        clauses.append(LogEvent.user_id == filters.user_id)
    if filters.ip:
        clauses.append(LogEvent.ip == filters.ip)
    if filters.endpoint:
        clauses.append(LogEvent.endpoint == filters.endpoint)
    if filters.status is not None:
        clauses.append(LogEvent.status == filters.status)
    if filters.request_id:
        clauses.append(LogEvent.request_id == filters.request_id)
    if filters.correlation_id:
        clauses.append(LogEvent.correlation_id == filters.correlation_id)
    if filters.q:
        term = _pattern(filters.q[:100])
        clauses.append(
            or_(
                LogEvent.message.ilike(term, escape="\\"),
                LogEvent.endpoint.ilike(term, escape="\\"),
                LogEvent.error_code.ilike(term, escape="\\"),
            )
        )
    return clauses


def _security_level_filter(filters: ObservabilityFilters) -> list[Any]:
    """Na trilha de segurança, ``level`` é derivado de ``result``."""
    if not filters.level:
        return []
    if filters.level == "warn":
        return [
            or_(
                SecurityEvent.result.in_(FAILURE_RESULTS),
                SecurityEvent.event_type.ilike("%failed%"),
                SecurityEvent.event_type.ilike("%rate_limited%"),
            )
        ]
    if filters.level == "info":
        return [
            or_(
                SecurityEvent.result.is_(None),
                SecurityEvent.result == "success",
            )
        ]
    return [SecurityEvent.id.is_(None)]  # nenhum evento de segurança nesse nível


def _security_filters(filters: ObservabilityFilters) -> list[Any]:
    clauses = _in_window(SecurityEvent.created_at, filters)
    clauses.extend(_security_level_filter(filters))
    if filters.user_id:
        clauses.append(SecurityEvent.user_id == filters.user_id)
    if filters.ip:
        clauses.append(SecurityEvent.ip == filters.ip)
    if filters.endpoint:
        clauses.append(SecurityEvent.endpoint == filters.endpoint)
    if filters.request_id:
        clauses.append(SecurityEvent.request_id == filters.request_id)
    if filters.q:
        clauses.append(SecurityEvent.event_type.ilike(_pattern(filters.q[:100]), escape="\\"))
    if filters.status is not None or filters.correlation_id:
        clauses.append(SecurityEvent.id.is_(None))
    return clauses


def _audit_filters(filters: ObservabilityFilters) -> list[Any]:
    clauses = _in_window(AuditLog.created_at, filters)
    if filters.level:
        if filters.level in ("warn", "error", "fatal"):
            clauses.append(and_(AuditLog.result.is_not(None), AuditLog.result != "success"))
        elif filters.level == "debug":
            clauses.append(AuditLog.id.is_(None))
    if filters.user_id:
        clauses.append(AuditLog.actor_user_id == filters.user_id)
    if filters.ip:
        clauses.append(AuditLog.ip == filters.ip)
    if filters.endpoint:
        clauses.append(AuditLog.endpoint == filters.endpoint)
    if filters.request_id:
        clauses.append(AuditLog.request_id == filters.request_id)
    if filters.q:
        term = _pattern(filters.q[:100])
        clauses.append(
            or_(
                AuditLog.action.ilike(term, escape="\\"),
                AuditLog.reason.ilike(term, escape="\\"),
                AuditLog.resource_type.ilike(term, escape="\\"),
            )
        )
    if filters.status is not None or filters.correlation_id:
        clauses.append(AuditLog.id.is_(None))
    return clauses


def _event_view(
    row: LogEvent | SecurityEvent | AuditLog,
    *,
    mask: bool,
    category: str,
    level: str,
    message: str | None,
) -> EventView:
    raw_ip = getattr(row, "ip", None)
    return EventView(
        id=row.id,
        occurred_at=ensure_utc(row.occurred_at if isinstance(row, LogEvent) else row.created_at),
        level=level,
        category=category,
        source=(
            "log_events"
            if isinstance(row, LogEvent)
            else "security_events"
            if isinstance(row, SecurityEvent)
            else "audit_logs"
        ),
        module=getattr(row, "module", None)
        or (row.event_type.split(".", 1)[0] if isinstance(row, SecurityEvent) else None),
        request_id=row.request_id,
        correlation_id=getattr(row, "correlation_id", None),
        user_id=row.user_id if isinstance(row, (LogEvent, SecurityEvent)) else row.actor_user_id,
        ip=mask_ip(raw_ip) if mask else raw_ip,
        ip_masked=mask,
        user_agent=row.user_agent,
        endpoint=row.endpoint,
        status=getattr(row, "status", None),
        duration_ms=getattr(row, "duration_ms", None),
        message=message,
        error_code=getattr(row, "error_code", None),
        details=row.details,
    )


def _security_view(row: SecurityEvent, *, mask: bool) -> EventView:
    failed = row.result in FAILURE_RESULTS or any(
        marker in row.event_type for marker in ("failed", "rate_limited", "reuse")
    )
    return _event_view(
        row,
        mask=mask,
        category="security",
        level="warn" if failed else "info",
        message=row.event_type,
    )


def _audit_view(row: AuditLog, *, mask: bool) -> EventView:
    failed = row.result is not None and row.result != "success"
    return _event_view(
        row,
        mask=mask,
        category="audit",
        level="warn" if failed else "info",
        message=row.action,
    )


def _log_view(row: LogEvent, *, mask: bool) -> EventView:
    return _event_view(
        row,
        mask=mask,
        category=row.category,
        level=row.level,
        message=row.message,
    )


def list_events(
    session: Session,
    filters: ObservabilityFilters,
    *,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
    mask: bool = True,
) -> Page:
    views: list[EventView] = []
    next_cursor: str | None = None
    if filters.category == "security":
        clauses = _security_filters(filters)
        if cursor is not None:
            clauses.append(_before_cursor(SecurityEvent.created_at, SecurityEvent.id, cursor))
        security_rows = list(
            session.scalars(
                select(SecurityEvent)
                .where(*clauses)
                .order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc())
                .limit(limit + 1)
            )
        )
        if len(security_rows) > limit:
            next_cursor = encode_cursor(
                security_rows[limit - 1].created_at, security_rows[limit - 1].id
            )
            security_rows = security_rows[:limit]
        views = [_security_view(row, mask=mask) for row in security_rows]
        return Page(views, next_cursor)

    if filters.category == "audit":
        clauses = _audit_filters(filters)
        if cursor is not None:
            clauses.append(_before_cursor(AuditLog.created_at, AuditLog.id, cursor))
        audit_rows = list(
            session.scalars(
                select(AuditLog)
                .where(*clauses)
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .limit(limit + 1)
            )
        )
        if len(audit_rows) > limit:
            next_cursor = encode_cursor(audit_rows[limit - 1].created_at, audit_rows[limit - 1].id)
            audit_rows = audit_rows[:limit]
        views = [_audit_view(row, mask=mask) for row in audit_rows]
        return Page(views, next_cursor)

    clauses = _log_filters(filters)
    if cursor is not None:
        clauses.append(_before_cursor(LogEvent.occurred_at, LogEvent.id, cursor))
    log_rows = list(
        session.scalars(
            select(LogEvent)
            .where(*clauses)
            .order_by(LogEvent.occurred_at.desc(), LogEvent.id.desc())
            .limit(limit + 1)
        )
    )
    if len(log_rows) > limit:
        next_cursor = encode_cursor(log_rows[limit - 1].occurred_at, log_rows[limit - 1].id)
        log_rows = log_rows[:limit]
    views = [_log_view(row, mask=mask) for row in log_rows]
    return Page(views, next_cursor)


def count_events(session: Session, filters: ObservabilityFilters) -> int:
    if filters.category == "security":
        return int(
            session.scalar(
                select(func.count()).select_from(SecurityEvent).where(*_security_filters(filters))
            )
            or 0
        )
    if filters.category == "audit":
        return int(
            session.scalar(
                select(func.count()).select_from(AuditLog).where(*_audit_filters(filters))
            )
            or 0
        )
    return int(
        session.scalar(select(func.count()).select_from(LogEvent).where(*_log_filters(filters)))
        or 0
    )


def iter_events(
    session: Session,
    filters: ObservabilityFilters,
    *,
    max_rows: int,
    batch_size: int = 500,
    mask: bool = True,
) -> Iterator[EventView]:
    """Itera em lotes por keyset, sem carregar mais que ``batch_size`` por vez."""
    remaining = max_rows
    cursor: tuple[datetime, uuid.UUID] | None = None
    while remaining > 0:
        page = list_events(
            session,
            filters,
            limit=min(batch_size, remaining),
            cursor=cursor,
            mask=mask,
        )
        if not page.events:
            return
        yield from page.events
        remaining -= len(page.events)
        if page.next_cursor is None:
            return
        cursor = decode_cursor(page.next_cursor)


def get_event(session: Session, event_id: uuid.UUID) -> EventDetail | None:
    log_row = session.get(LogEvent, event_id)
    if log_row is not None:
        view = _log_view(log_row, mask=False)
        return EventDetail(**view.model_dump(), stack=log_row.stack)
    security_row = session.get(SecurityEvent, event_id)
    if security_row is not None:
        view = _security_view(security_row, mask=False)
        return EventDetail(**view.model_dump(), result=security_row.result)
    audit_row = session.get(AuditLog, event_id)
    if audit_row is not None:
        view = _audit_view(audit_row, mask=False)
        return EventDetail(
            **view.model_dump(),
            result=audit_row.result,
            stack=None,
        )
    return None


def _merge_sources(
    session: Session,
    filters: ObservabilityFilters,
    *,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None,
) -> Page:
    """Une log_events, security_events e audit_logs do usuário, mais recentes primeiro."""
    views: list[EventView] = []
    if filters.user_id is None:
        return Page([], None)
    log_filters = ObservabilityFilters(
        **{
            **filters.model_dump(),
            "category": filters.category
            if filters.category in {"http", "app", "job", "client"}
            else None,
        }
    )
    # log_events
    if filters.category is None or filters.category in {"http", "app", "job", "client"}:
        clauses = _log_filters(log_filters)
        clauses.append(LogEvent.user_id == filters.user_id)
        if cursor is not None:
            clauses.append(_before_cursor(LogEvent.occurred_at, LogEvent.id, cursor))
        log_rows = session.scalars(
            select(LogEvent)
            .where(*clauses)
            .order_by(LogEvent.occurred_at.desc(), LogEvent.id.desc())
            .limit(limit + 1)
        )
        views.extend(_log_view(row, mask=True) for row in log_rows)
    # security_events
    if filters.category in (None, "security"):
        clauses = _security_filters(
            ObservabilityFilters(**{**filters.model_dump(), "category": "security"})
        )
        clauses.append(SecurityEvent.user_id == filters.user_id)
        if cursor is not None:
            clauses.append(_before_cursor(SecurityEvent.created_at, SecurityEvent.id, cursor))
        security_rows = session.scalars(
            select(SecurityEvent)
            .where(*clauses)
            .order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc())
            .limit(limit + 1)
        )
        views.extend(_security_view(row, mask=True) for row in security_rows)
    # audit_logs
    if filters.category in (None, "audit"):
        clauses = _audit_filters(
            ObservabilityFilters(**{**filters.model_dump(), "category": "audit"})
        )
        clauses.append(AuditLog.actor_user_id == filters.user_id)
        if cursor is not None:
            clauses.append(_before_cursor(AuditLog.created_at, AuditLog.id, cursor))
        audit_rows = session.scalars(
            select(AuditLog)
            .where(*clauses)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit + 1)
        )
        views.extend(_audit_view(row, mask=True) for row in audit_rows)

    views.sort(key=lambda item: (item.occurred_at, item.id), reverse=True)
    has_more = len(views) > limit
    page = views[:limit]
    next_cursor = encode_cursor(page[-1].occurred_at, page[-1].id) if has_more and page else None
    return Page(page, next_cursor)


def user_activity(
    session: Session,
    user_id: uuid.UUID,
    filters: ObservabilityFilters,
    *,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
) -> Page:
    scoped = ObservabilityFilters(**{**filters.model_dump(), "user_id": user_id})
    return _merge_sources(session, scoped, limit=limit, cursor=cursor)


def _security_failure_clause() -> Any:
    return or_(
        SecurityEvent.result.in_(FAILURE_RESULTS),
        SecurityEvent.event_type.ilike("%failed%"),
        SecurityEvent.event_type.ilike("%rate_limited%"),
    )


def ip_report(session: Session, ip: str, *, limit: int = 100) -> IpReportResponse:
    log_total = int(
        session.scalar(select(func.count()).select_from(LogEvent).where(LogEvent.ip == ip)) or 0
    )
    security_total = int(
        session.scalar(
            select(func.count()).select_from(SecurityEvent).where(SecurityEvent.ip == ip)
        )
        or 0
    )
    failed_logins = int(
        session.scalar(
            select(func.count())
            .select_from(SecurityEvent)
            .where(
                SecurityEvent.ip == ip,
                or_(
                    SecurityEvent.event_type.ilike("%login_failed%"),
                    SecurityEvent.event_type.ilike("%verification_failed%"),
                    SecurityEvent.event_type == EMAIL_LOGIN_FAILED,
                    SecurityEvent.event_type == OTP_VERIFICATION_FAILED,
                    SecurityEvent.event_type == EMAIL_VERIFICATION_FAILED,
                    SecurityEvent.event_type == PASSKEY_FAILED,
                ),
            )
        )
        or 0
    )

    events: list[EventView] = []
    log_rows = session.scalars(
        select(LogEvent).where(LogEvent.ip == ip).order_by(LogEvent.occurred_at.desc()).limit(limit)
    )
    events.extend(_log_view(row, mask=False) for row in log_rows)
    security_rows = session.scalars(
        select(SecurityEvent)
        .where(SecurityEvent.ip == ip)
        .order_by(SecurityEvent.created_at.desc())
        .limit(limit)
    )
    events.extend(_security_view(row, mask=False) for row in security_rows)
    events.sort(key=lambda item: item.occurred_at, reverse=True)
    events = events[:limit]

    user_stats: dict[uuid.UUID, tuple[int, datetime]] = {}
    user_statements = (
        select(LogEvent.user_id, func.count(), func.max(LogEvent.occurred_at))
        .where(LogEvent.ip == ip, LogEvent.user_id.is_not(None))
        .group_by(LogEvent.user_id),
        select(SecurityEvent.user_id, func.count(), func.max(SecurityEvent.created_at))
        .where(SecurityEvent.ip == ip, SecurityEvent.user_id.is_not(None))
        .group_by(SecurityEvent.user_id),
    )
    for statement in user_statements:
        for user_id, total, last_seen in session.execute(statement):
            if user_id is None:
                continue
            previous = user_stats.get(user_id)
            count = int(total)
            moment = ensure_utc(last_seen)
            if previous is None:
                user_stats[user_id] = (count, moment)
            else:
                user_stats[user_id] = (previous[0] + count, max(previous[1], moment))

    users = [
        IpUserEntry(user_id=user_id, events=count, last_seen_at=moment)
        for user_id, (count, moment) in sorted(
            user_stats.items(), key=lambda item: item[1][1], reverse=True
        )
    ][:20]

    log_first, log_last = session.execute(
        select(func.min(LogEvent.occurred_at), func.max(LogEvent.occurred_at)).where(
            LogEvent.ip == ip
        )
    ).one()
    security_first, security_last = session.execute(
        select(func.min(SecurityEvent.created_at), func.max(SecurityEvent.created_at)).where(
            SecurityEvent.ip == ip
        )
    ).one()
    known = [value for value in (log_first, log_last, security_first, security_last) if value]
    ip_hash = session.scalar(select(LogEvent.ip_hash).where(LogEvent.ip == ip).limit(1))
    if ip_hash is None:
        ip_hash = session.scalar(
            select(SecurityEvent.ip_hash).where(SecurityEvent.ip == ip).limit(1)
        )
    return IpReportResponse(
        ip=ip,
        ip_hash=ip_hash,
        first_seen_at=ensure_utc(min(known)) if known else None,
        last_seen_at=ensure_utc(max(known)) if known else None,
        total_events=log_total,
        security_events=security_total,
        failed_logins=failed_logins,
        users=users,
        events=events,
    )


def _count_where(session: Session, model: Any, clauses: list[Any]) -> int:
    return int(session.scalar(select(func.count()).select_from(model).where(*clauses)) or 0)


def _failed_logins_clause() -> Any:
    """Mesma definição de ``auth.failed_logins`` da summary."""
    return or_(
        SecurityEvent.event_type.in_((EMAIL_LOGIN_FAILED, OTP_VERIFICATION_FAILED, PASSKEY_FAILED)),
        SecurityEvent.event_type.ilike("%login_failed%"),
    )


def _summary_window(session: Session, from_at: datetime, to_at: datetime) -> SummaryWindow:
    filters = ObservabilityFilters(from_at=from_at, to_at=to_at)
    log_clauses = _in_window(LogEvent.occurred_at, filters)
    security_clauses = _in_window(SecurityEvent.created_at, filters)
    audit_clauses = _in_window(AuditLog.created_at, filters)

    total_events = _count_where(session, LogEvent, log_clauses)
    by_level = [
        LevelCount(level=str(level), count=int(count))
        for level, count in session.execute(
            select(LogEvent.level, func.count())
            .where(*log_clauses)
            .group_by(LogEvent.level)
            .order_by(LogEvent.level)
        )
    ]
    by_category = [
        CategoryCount(category=str(category), count=int(count))
        for category, count in session.execute(
            select(LogEvent.category, func.count())
            .where(*log_clauses)
            .group_by(LogEvent.category)
            .order_by(LogEvent.category)
        )
    ]

    http_row = session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(case((LogEvent.status >= 400, 1), else_=0)), 0),
            func.coalesce(func.sum(case((LogEvent.status >= 500, 1), else_=0)), 0),
            func.coalesce(func.sum(case((LogEvent.duration_ms > 1_000, 1), else_=0)), 0),
            func.avg(LogEvent.duration_ms),
        ).where(*log_clauses, LogEvent.category == "http")
    ).one()
    http = HttpSummary(
        requests=int(http_row[0] or 0),
        status_4xx=int(http_row[1] or 0),
        status_5xx=int(http_row[2] or 0),
        slow_requests=int(http_row[3] or 0),
        avg_duration_ms=float(http_row[4]) if http_row[4] is not None else None,
    )

    security_events = _count_where(session, SecurityEvent, security_clauses)
    unauthorized = _count_where(
        session,
        SecurityEvent,
        [*security_clauses, SecurityEvent.event_type == HTTP_UNAUTHORIZED],
    )
    forbidden = _count_where(
        session,
        SecurityEvent,
        [*security_clauses, SecurityEvent.event_type == HTTP_FORBIDDEN],
    )
    rate_limited = _count_where(
        session,
        SecurityEvent,
        [*security_clauses, SecurityEvent.event_type.in_(RATE_LIMITED_TYPES)],
    )
    failed_logins = _count_where(
        session,
        SecurityEvent,
        [*security_clauses, _failed_logins_clause()],
    )
    auth = AuthSummary(
        unauthorized=unauthorized,
        forbidden=forbidden,
        rate_limited=rate_limited,
        failed_logins=failed_logins,
    )

    jobs = JobSummary(
        started=_count_where(
            session,
            LogEvent,
            [*log_clauses, LogEvent.category == "job", LogEvent.message.ilike("% started%")],
        ),
        finished=_count_where(
            session,
            LogEvent,
            [*log_clauses, LogEvent.category == "job", LogEvent.message.ilike("% finished%")],
        ),
        failed=_count_where(
            session,
            LogEvent,
            [*log_clauses, LogEvent.category == "job", LogEvent.level == "error"],
        ),
    )

    audit_events = _count_where(session, AuditLog, audit_clauses)

    suspicious: dict[uuid.UUID, tuple[int, int, datetime]] = {}
    for user_id, count, last_seen in session.execute(
        select(LogEvent.user_id, func.count(), func.max(LogEvent.occurred_at))
        .where(
            *log_clauses,
            LogEvent.user_id.is_not(None),
            LogEvent.level.in_(("warn", "error", "fatal")),
        )
        .group_by(LogEvent.user_id)
    ):
        if user_id is not None:
            suspicious[user_id] = (int(count), 0, ensure_utc(last_seen))
    for user_id, count, last_seen in session.execute(
        select(SecurityEvent.user_id, func.count(), func.max(SecurityEvent.created_at))
        .where(*security_clauses, SecurityEvent.user_id.is_not(None), _security_failure_clause())
        .group_by(SecurityEvent.user_id)
    ):
        if user_id is None:
            continue
        previous = suspicious.get(user_id)
        moment = ensure_utc(last_seen)
        if previous is None:
            suspicious[user_id] = (0, int(count), moment)
        else:
            suspicious[user_id] = (previous[0], previous[1] + int(count), max(previous[2], moment))

    suspicious_users = [
        SuspiciousUser(
            user_id=user_id,
            events=log_count,
            security_events=security_count,
            last_seen_at=moment,
        )
        for user_id, (log_count, security_count, moment) in sorted(
            suspicious.items(),
            key=lambda item: (item[1][0] + item[1][1], item[1][2]),
            reverse=True,
        )[:10]
    ]

    return SummaryWindow(
        from_at=from_at,
        to_at=to_at,
        total_events=total_events,
        by_level=by_level,
        by_category=by_category,
        http=http,
        auth=auth,
        jobs=jobs,
        audit_events=audit_events,
        security_events=security_events,
        suspicious_users=suspicious_users,
    )


def summary(
    session: Session, window: str, *, now: datetime | None = None
) -> tuple[SummaryWindow, SummaryWindow]:
    size = normalize_window(window)
    to_at = ensure_utc(now or datetime.now(UTC))
    from_at = to_at - size
    previous_from = from_at - size
    current = _summary_window(session, from_at, to_at)
    previous = _summary_window(session, previous_from, from_at)
    return current, previous


def alerts(
    session: Session,
    window: str,
    *,
    login_failures: int,
    server_errors: int,
    failed_jobs: int,
    client_errors: int,
    now: datetime | None = None,
) -> AlertsResponse:
    """Deriva alertas simples dos eventos da janela corrente.

    Cada alerta aparece somente quando a contagem atinge o limiar configurado.
    Não há escrita nem canal externo: a resposta é calculada a partir de
    ``log_events`` e ``security_events``.
    """
    size = normalize_window(window)
    to_at = ensure_utc(now or datetime.now(UTC))
    from_at = to_at - size
    filters = ObservabilityFilters(from_at=from_at, to_at=to_at)
    log_clauses = _in_window(LogEvent.occurred_at, filters)
    security_clauses = _in_window(SecurityEvent.created_at, filters)

    counts = {
        "login_failures": _count_where(
            session,
            SecurityEvent,
            [*security_clauses, _failed_logins_clause()],
        ),
        "server_errors": _count_where(
            session,
            LogEvent,
            [*log_clauses, LogEvent.category == "http", LogEvent.status >= 500],
        ),
        "failed_jobs": _count_where(
            session,
            LogEvent,
            [*log_clauses, LogEvent.category == "job", LogEvent.level == "error"],
        ),
        "client_errors": _count_where(
            session,
            LogEvent,
            [
                *log_clauses,
                LogEvent.category == "client",
                LogEvent.level.in_(("error", "fatal")),
            ],
        ),
    }
    specs: tuple[tuple[str, Literal["warning", "critical"], int], ...] = (
        ("login_failures", "warning", login_failures),
        ("server_errors", "critical", server_errors),
        ("failed_jobs", "warning", failed_jobs),
        ("client_errors", "warning", client_errors),
    )
    items = [
        AlertItem(code=code, level=level, count=counts[code], threshold=threshold)
        for code, level, threshold in specs
        if counts[code] >= threshold
    ]
    return AlertsResponse(
        window=window,
        from_at=from_at,
        to_at=to_at,
        alerts=items,
    )


__all__ = [
    "InvalidCursor",
    "Page",
    "WINDOW_SIZES",
    "alerts",
    "count_events",
    "decode_cursor",
    "encode_cursor",
    "get_event",
    "ip_report",
    "iter_events",
    "list_events",
    "normalize_window",
    "summary",
    "user_activity",
]
