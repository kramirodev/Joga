"""Testes das políticas puras de matchmaking."""

import uuid
from datetime import UTC, datetime, time

import pytest

from app.modules.matchmaking.policy import (
    AvailabilityWindow,
    Candidate,
    RegionPoint,
    balance_teams,
    court_intersection,
    haversine_km,
    level_value,
    meeting_region,
    select_start,
)


@pytest.mark.parametrize(
    ("level", "value"),
    [("beginner", 1), ("intermediate", 2), ("advanced", 3)],
)
def test_level_value(level: str, value: int) -> None:
    assert level_value(level) == value


def test_unknown_level_falls_back_to_beginner() -> None:
    assert level_value("unknown") == 1


@pytest.mark.parametrize(
    ("preferences", "expected"),
    [
        (["PUBLIC_ONLY", "ANY"], "PUBLIC_ONLY"),
        (["PRIVATE_ONLY", "ANY"], "PRIVATE_ONLY"),
        (["ANY", "ANY"], "ANY"),
        (["PUBLIC_ONLY", "PRIVATE_ONLY"], None),
        (["PRIVATE_ONLY", "PUBLIC_ONLY", "ANY"], None),
        (["PUBLIC_ONLY"], "PUBLIC_ONLY"),
    ],
)
def test_court_intersection(preferences: list[str], expected: str | None) -> None:
    assert court_intersection(preferences) == expected


def test_court_intersection_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        court_intersection(["SOMETHING"])


def test_meeting_region_uses_mean_and_smallest_radius() -> None:
    region = meeting_region(
        [
            RegionPoint(lat=-23.55, lng=-46.63, radius_km=10),
            RegionPoint(lat=-23.56, lng=-46.64, radius_km=20),
        ],
        max_radius_km=30,
    )

    assert region is not None
    assert region.radius_km == 10
    assert region.lat == pytest.approx(-23.555)
    assert region.lng == pytest.approx(-46.635)


def test_meeting_region_rejects_distant_participants() -> None:
    region = meeting_region(
        [
            RegionPoint(lat=-23.55, lng=-46.63, radius_km=5),
            RegionPoint(lat=-22.90, lng=-43.18, radius_km=5),
        ],
        max_radius_km=30,
    )

    assert region is None


def test_meeting_region_caps_radius() -> None:
    region = meeting_region(
        [RegionPoint(lat=-23.55, lng=-46.63, radius_km=150)],
        max_radius_km=30,
    )

    assert region is not None
    assert region.radius_km == 30


def test_haversine_known_distance() -> None:
    # São Paulo (Praça da Sé) até Rio (Av. Atlântica) ~ 360 km em linha reta.
    distance = haversine_km(-23.5504, -46.6331, -22.9064, -43.1822)
    assert 355 <= distance <= 365


def test_balance_teams_splits_evenly_by_level() -> None:
    levels = [
        "advanced",
        "advanced",
        "intermediate",
        "intermediate",
        "intermediate",
        "intermediate",
        "beginner",
        "beginner",
        "beginner",
        "beginner",
    ]
    candidates = [
        Candidate(
            user_id=uuid.UUID(int=index + 1),
            level=level,
            region=RegionPoint(lat=-23.55, lng=-46.63, radius_km=10),
        )
        for index, level in enumerate(levels)
    ]

    assignment = balance_teams(candidates)

    assert len(assignment) == 10
    totals = {1: 0, 2: 0}
    counts = {1: 0, 2: 0}
    for candidate in candidates:
        team = assignment[candidate.user_id]
        totals[team] += level_value(candidate.level)
        counts[team] += 1
    assert counts == {1: 5, 2: 5}
    assert abs(totals[1] - totals[2]) <= 2


def window(weekday: int, start: time, end: time) -> AvailabilityWindow:
    return AvailabilityWindow(
        weekday=weekday,
        start_time=start,
        end_time=end,
        timezone="America/Sao_Paulo",
    )


def test_select_start_picks_first_common_slot() -> None:
    # 2026-11-03 é uma terça-feira; 10:00 UTC = 07:00 em São Paulo.
    now = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)

    start = select_start(
        [[window(2, time(18, 0), time(22, 0))], [window(2, time(17, 0), time(20, 0))]],
        duration_minutes=60,
        now=now,
        min_lead_minutes=120,
        search_days=0,
    )

    assert start == datetime(2026, 11, 3, 21, 0, tzinfo=UTC)


def test_select_start_skips_when_duration_does_not_fit() -> None:
    now = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)

    start = select_start(
        [[window(2, time(18, 0), time(22, 0))]],
        duration_minutes=300,
        now=now,
        min_lead_minutes=120,
        search_days=0,
    )

    assert start is None


def test_select_start_requires_every_participant() -> None:
    now = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)

    start = select_start(
        [[window(2, time(18, 0), time(22, 0))], []],
        duration_minutes=60,
        now=now,
        min_lead_minutes=120,
        search_days=0,
    )

    assert start is None


def test_select_start_respects_minimum_lead_time() -> None:
    # 23:00 UTC = 20:00 local; com 2 h de antecedência o início seria 22:00 e não cabe.
    now = datetime(2026, 11, 3, 23, 0, tzinfo=UTC)

    start = select_start(
        [[window(2, time(18, 0), time(22, 0))]],
        duration_minutes=60,
        now=now,
        min_lead_minutes=120,
        search_days=0,
    )

    assert start is None


def test_select_start_finds_next_week_window() -> None:
    now = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)

    start = select_start(
        [[window(4, time(18, 0), time(20, 0))]],
        duration_minutes=60,
        now=now,
        min_lead_minutes=120,
        search_days=7,
    )

    assert start == datetime(2026, 11, 5, 21, 0, tzinfo=UTC)


def test_balance_teams_by_rating_minimizes_average_and_spread() -> None:
    from app.modules.matchmaking.policy import balance_teams_by_rating

    ratings = [
        (uuid.UUID(int=index), rating)
        for index, rating in enumerate(
            [1600, 1550, 1500, 1450, 1400, 1350, 1300, 1250, 1200, 1150],
            start=1,
        )
    ]

    assignment = balance_teams_by_rating(ratings, team_size=5)

    team_1 = [rating for user_id, rating in ratings if assignment[user_id] == 1]
    team_2 = [rating for user_id, rating in ratings if assignment[user_id] == 2]
    assert len(team_1) == 5
    assert len(team_2) == 5
    assert abs(sum(team_1) - sum(team_2)) <= 50
    assert max(team_1) - min(team_1) <= 450


def test_balance_teams_by_rating_is_deterministic() -> None:
    from app.modules.matchmaking.policy import balance_teams_by_rating

    ratings = [(uuid.UUID(int=index), 1500 + index * 10) for index in range(1, 11)]

    first = balance_teams_by_rating(ratings, team_size=5)
    second = balance_teams_by_rating(list(reversed(ratings)), team_size=5)

    assert first == second


def test_balance_teams_by_rating_rejects_invalid_input() -> None:
    from app.modules.matchmaking.policy import balance_teams_by_rating

    with pytest.raises(ValueError):
        balance_teams_by_rating([(uuid.uuid4(), 1500)], team_size=2)
    with pytest.raises(ValueError):
        balance_teams_by_rating(
            [(uuid.UUID(int=1), 1500), (uuid.UUID(int=1), 1500)],
            team_size=1,
        )


def test_balance_teams_by_rating_works_above_combination_limit() -> None:
    from app.modules.matchmaking.policy import balance_teams_by_rating

    ratings = [(uuid.UUID(int=index), 1500.0) for index in range(1, 19)]

    assignment = balance_teams_by_rating(ratings, team_size=9)

    assert set(assignment.values()) == {1, 2}
    assert sum(1 for team in assignment.values() if team == 1) == 9


def test_balance_teams_by_rating_respects_max_span() -> None:
    from app.modules.matchmaking.policy import RatingBalanceError, balance_teams_by_rating

    ratings = [(uuid.UUID(int=index), 3000.0 if index == 1 else 1000.0) for index in range(1, 11)]

    with pytest.raises(RatingBalanceError):
        balance_teams_by_rating(ratings, team_size=5, max_span=500)
