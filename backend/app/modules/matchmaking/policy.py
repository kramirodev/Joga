"""Políticas puras do matchmaking: compatibilidade, horário, região e balanceamento."""

from __future__ import annotations

import math
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from itertools import combinations
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


class RatingBalanceError(ValueError):
    """Não há composição de equipes dentro da dispersão máxima."""


def balance_teams_by_rating(
    ratings: Sequence[tuple[uuid.UUID, float]],
    *,
    team_size: int,
    max_span: float | None = None,
) -> dict[uuid.UUID, int]:
    """Divide em duas equipes minimizando diferença de média e dispersão (`mmr_v1`).

    Para grupos pequenos, testa todas as combinações. Acima de 16 jogadores, usa
    um guloso determinístico. ``max_span`` rejeita composições em que a diferença
    entre o maior e o menor MMR de uma equipe ultrapasse o limite.
    """
    if team_size <= 0:
        raise ValueError("team_size deve ser positivo")
    if len(ratings) != team_size * 2:
        raise ValueError("quantidade de ratings incompatível com o tamanho das equipes")
    if len({user_id for user_id, _ in ratings}) != len(ratings):
        raise ValueError("usuários duplicados no balanceamento")

    ordered = sorted(ratings, key=lambda item: (-item[1], str(item[0])))
    if len(ordered) > 16:
        assignment = _greedy_rating_balance(ordered)
        _ensure_span(ordered, assignment, max_span)
        return assignment

    best_cost: tuple[float, tuple[str, ...]] | None = None
    best_team_1: tuple[int, ...] | None = None
    indexes = range(len(ordered))
    for team_1_indexes in combinations(indexes, team_size):
        team_1_set = set(team_1_indexes)
        team_1_values = [ordered[index][1] for index in team_1_indexes]
        team_2_values = [ordered[index][1] for index in indexes if index not in team_1_set]
        team_span = max(
            max(team_1_values) - min(team_1_values),
            max(team_2_values) - min(team_2_values),
        )
        if max_span is not None and team_span > max_span:
            continue
        average_difference = abs(sum(team_1_values) - sum(team_2_values)) / team_size
        dispersion = (
            (max(team_1_values) - min(team_1_values)) + (max(team_2_values) - min(team_2_values))
        ) / 2
        tie_break = tuple(sorted(str(ordered[index][0]) for index in team_1_indexes))
        cost = (average_difference + (dispersion * 0.5), tie_break)
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_team_1 = team_1_indexes

    if best_team_1 is None:
        raise RatingBalanceError("sem composição de equipes dentro da dispersão máxima")
    selected = set(best_team_1)
    return {user_id: (1 if index in selected else 2) for index, (user_id, _) in enumerate(ordered)}


def _greedy_rating_balance(
    ordered: Sequence[tuple[uuid.UUID, float]],
) -> dict[uuid.UUID, int]:
    totals = {1: 0.0, 2: 0.0}
    assignment: dict[uuid.UUID, int] = {}
    for user_id, rating in ordered:
        team = 1 if totals[1] <= totals[2] else 2
        assignment[user_id] = team
        totals[team] += rating
    return assignment


def _ensure_span(
    ordered: Sequence[tuple[uuid.UUID, float]],
    assignment: dict[uuid.UUID, int],
    max_span: float | None,
) -> None:
    if max_span is None:
        return
    for team in (1, 2):
        values = [rating for user_id, rating in ordered if assignment[user_id] == team]
        if max(values) - min(values) > max_span:
            raise RatingBalanceError("sem composição de equipes dentro da dispersão máxima")


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
