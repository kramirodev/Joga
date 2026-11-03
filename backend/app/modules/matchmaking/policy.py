"""Políticas puras do matchmaking: compatibilidade, horário, região e balanceamento."""

from __future__ import annotations

import math
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LEVEL_VALUES = {"beginner": 1, "intermediate": 2, "advanced": 3}
COURT_VALUES = ("PUBLIC_ONLY", "PRIVATE_ONLY", "ANY")
EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class AvailabilityWindow:
    weekday: int
    start_time: time
    end_time: time
    timezone: str


@dataclass(frozen=True)
class RegionPoint:
    lat: float
    lng: float
    radius_km: int


@dataclass(frozen=True)
class MeetingRegion:
    lat: float
    lng: float
    radius_km: int


@dataclass(frozen=True)
class Candidate:
    user_id: uuid.UUID
    level: str
    region: RegionPoint


def level_value(level: str) -> int:
    return LEVEL_VALUES.get(level, 1)


def court_intersection(preferences: Iterable[str]) -> str | None:
    """Interseção das preferências; None quando pública e particular se excluem."""
    has_public = False
    has_private = False
    for preference in preferences:
        if preference == "PUBLIC_ONLY":
            has_public = True
        elif preference == "PRIVATE_ONLY":
            has_private = True
        elif preference != "ANY":
            raise ValueError("preferência de quadra desconhecida")
    if has_public and has_private:
        return None
    if has_public:
        return "PUBLIC_ONLY"
    if has_private:
        return "PRIVATE_ONLY"
    return "ANY"


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def meeting_region(points: Sequence[RegionPoint], max_radius_km: int) -> MeetingRegion | None:
    """Média geográfica dos centros, desde que o ponto caiba no raio de todos."""
    if not points:
        return None
    lat = sum(point.lat for point in points) / len(points)
    lng = sum(point.lng for point in points) / len(points)
    radius = min(point.radius_km for point in points)
    radius = max(1, min(radius, max_radius_km))
    if any(haversine_km(lat, lng, point.lat, point.lng) > point.radius_km for point in points):
        return None
    return MeetingRegion(lat=round(lat, 6), lng=round(lng, 6), radius_km=radius)


def balance_teams(candidates: Sequence[Candidate]) -> dict[uuid.UUID, int]:
    """Divide em duas equipes minimizando a diferença de soma de níveis (`level_v1`)."""
    ordered = sorted(candidates, key=lambda item: (-level_value(item.level), str(item.user_id)))
    totals = {1: 0, 2: 0}
    assignment: dict[uuid.UUID, int] = {}
    for candidate in ordered:
        team = 1 if totals[1] <= totals[2] else 2
        assignment[candidate.user_id] = team
        totals[team] += level_value(candidate.level)
    return assignment


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("America/Sao_Paulo")


def window_covers(window: AvailabilityWindow, start: datetime, end: datetime) -> bool:
    """Verifica se o intervalo [start, end] cabe inteiro na janela local."""
    zone = _zone(window.timezone)
    local_start = start.astimezone(zone)
    local_end = end.astimezone(zone)
    if local_start.date() != local_end.date():
        return False
    if local_start.isoweekday() != window.weekday:
        return False
    return local_start.time() >= window.start_time and local_end.time() <= window.end_time


def windows_cover(
    windows: Sequence[AvailabilityWindow],
    start: datetime,
    end: datetime,
) -> bool:
    return any(window_covers(window, start, end) for window in windows)


def _within_windows(
    windows: Sequence[AvailabilityWindow],
    start: datetime,
    end: datetime,
) -> bool:
    return windows_cover(windows, start, end)


def select_start(
    availability: Sequence[Sequence[AvailabilityWindow]],
    *,
    duration_minutes: int,
    now: datetime,
    search_days: int = 7,
    slot_minutes: int = 30,
    min_lead_minutes: int = 120,
    default_timezone: str = "America/Sao_Paulo",
) -> datetime | None:
    """Primeiro horário em que todos os participantes estão disponíveis."""
    if not availability or any(not windows for windows in availability):
        return None
    zone = _zone(default_timezone)
    earliest = now.astimezone(zone) + timedelta(minutes=min_lead_minutes)
    duration = timedelta(minutes=duration_minutes)
    slots_per_day = (24 * 60) // slot_minutes

    for day_offset in range(search_days + 1):
        day: date = earliest.date() + timedelta(days=day_offset)
        for index in range(slots_per_day):
            minutes = index * slot_minutes
            start_local = datetime(
                day.year,
                day.month,
                day.day,
                minutes // 60,
                minutes % 60,
                tzinfo=zone,
            )
            if start_local < earliest:
                continue
            start = start_local.astimezone(UTC)
            end = start + duration
            if all(_within_windows(windows, start, end) for windows in availability):
                return start
    return None
