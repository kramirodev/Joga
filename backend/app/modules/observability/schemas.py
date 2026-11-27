"""Contrato de resposta da observabilidade administrativa (Fase 1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventView(BaseModel):
    """Evento em listagem; o IP aparece mascarado por padrão."""

    id: UUID
    occurred_at: datetime
    level: str
    category: str
    source: str
    module: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    user_id: UUID | None = None
    ip: str | None = None
    ip_masked: bool = True
    user_agent: str | None = None
    endpoint: str | None = None
    status: int | None = None
    duration_ms: int | None = None
    message: str | None = None
    error_code: str | None = None
    details: dict[str, Any] | None = None


class EventDetail(EventView):
    ip_masked: bool = False
    stack: str | None = None
    result: str | None = None


class EventListResponse(BaseModel):
    events: list[EventView]
    next_cursor: str | None = None


class UserActivityResponse(BaseModel):
    user_id: UUID
    events: list[EventView]
    next_cursor: str | None = None


class IpUserEntry(BaseModel):
    user_id: UUID
    events: int
    last_seen_at: datetime


class IpReportResponse(BaseModel):
    ip: str
    ip_hash: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    total_events: int
    security_events: int
    failed_logins: int
    users: list[IpUserEntry]
    events: list[EventView]


class LevelCount(BaseModel):
    level: str
    count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class LevelCategoryCount(BaseModel):
    level: str
    category: str
    count: int


class SuspiciousUser(BaseModel):
    user_id: UUID
    events: int
    security_events: int
    last_seen_at: datetime


class HttpSummary(BaseModel):
    requests: int
    status_4xx: int
    status_5xx: int
    slow_requests: int
    avg_duration_ms: float | None = None


class AuthSummary(BaseModel):
    unauthorized: int
    forbidden: int
    rate_limited: int
    failed_logins: int


class JobSummary(BaseModel):
    started: int
    finished: int
    failed: int


class SummaryWindow(BaseModel):
    from_at: datetime
    to_at: datetime
    total_events: int
    by_level: list[LevelCount]
    by_category: list[CategoryCount]
    http: HttpSummary
    auth: AuthSummary
    jobs: JobSummary
    audit_events: int
    security_events: int
    suspicious_users: list[SuspiciousUser]


class SummaryResponse(BaseModel):
    window: str
    current: SummaryWindow
    previous: SummaryWindow


class ObservabilityFilters(BaseModel):
    """Filtros normalizados usados por listagem e exportação."""

    from_at: datetime | None = None
    to_at: datetime | None = None
    level: str | None = None
    category: str | None = None
    user_id: UUID | None = None
    ip: str | None = None
    endpoint: str | None = None
    status: int | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    q: str | None = None


class ClientEventIn(BaseModel):
    """Evento de erro enviado pelo painel ou aplicativo móvel.

    Campos de identidade (``user_id``, IP, e-mail, telefone) e ``details`` livre
    não são aceitos: campos extras são ignorados e a identidade vem do contexto
    da requisição.
    """

    model_config = ConfigDict(extra="ignore")

    level: Literal["debug", "info", "warn", "error", "fatal"] = "error"
    message: str | None = Field(default=None, max_length=500)
    stack: str | None = Field(default=None, max_length=8_000)
    error_code: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_.:-]*$")
    module: str | None = Field(default=None, max_length=80)
    platform: Literal["web", "android", "ios"]
    app_version: str = Field(min_length=1, max_length=40)
    screen: str | None = Field(default=None, max_length=120)
    build: str | None = Field(default=None, max_length=40)
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._:-]{1,64}$")
    correlation_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._:-]{1,64}$")


class ClientEventsRequest(BaseModel):
    """Lote de 1 a 20 eventos do cliente."""

    events: list[ClientEventIn] = Field(min_length=1, max_length=20)


class ClientEventsResponse(BaseModel):
    accepted: int
    dropped: int


class AlertItem(BaseModel):
    code: str
    level: Literal["warning", "critical"]
    count: int
    threshold: int


class AlertsResponse(BaseModel):
    window: str
    from_at: datetime
    to_at: datetime
    alerts: list[AlertItem]


__all__ = [
    "AlertItem",
    "AlertsResponse",
    "AuthSummary",
    "CategoryCount",
    "ClientEventIn",
    "ClientEventsRequest",
    "ClientEventsResponse",
    "EventDetail",
    "EventListResponse",
    "EventView",
    "HttpSummary",
    "IpReportResponse",
    "IpUserEntry",
    "JobSummary",
    "LevelCategoryCount",
    "LevelCount",
    "ObservabilityFilters",
    "SummaryResponse",
    "SummaryWindow",
    "SuspiciousUser",
    "UserActivityResponse",
]
