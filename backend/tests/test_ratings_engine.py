"""Testes puros do motor Glicko-2 e das divisões."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.ratings.engine import (
    MAX_DELTA,
    MAX_RATING_DEVIATION,
    PLACEMENT_MATCHES,
    OpponentResult,
    RatingState,
    division_for,
    division_progress,
    expected_score,
    inflate_rating_deviation,
    rate_match,
    update_player,
)

NOW = datetime(2026, 11, 6, 21, 0, tzinfo=UTC)


def test_glicko2_known_example() -> None:
    state = RatingState(rating=1500, rating_deviation=200, volatility=0.06)
    opponents = [
        OpponentResult(1400, 30, 1.0),
        OpponentResult(1550, 100, 0.0),
        OpponentResult(1700, 300, 0.0),
    ]

    update = update_player(state, opponents, now=NOW)

    assert update.rating_after == pytest.approx(1464.05, abs=0.05)
    assert update.rating_deviation_after == pytest.approx(151.52, abs=0.05)
    assert update.volatility_after == pytest.approx(0.059996, abs=1e-5)


def test_favorite_has_higher_expected_score() -> None:
    favorite = expected_score(1700, 1500, 100)
    underdog = expected_score(1300, 1500, 100)

    assert favorite > 0.5
    assert underdog < 0.5
    assert favorite == pytest.approx(1 - underdog, abs=1e-9)


def test_upset_moves_more_than_expected_win() -> None:
    state = RatingState(rating=1500, rating_deviation=100)

    upset = update_player(state, [OpponentResult(1700, 100, 1.0)], now=NOW)
    expected = update_player(state, [OpponentResult(1300, 100, 1.0)], now=NOW)

    assert upset.delta > expected.delta
    assert upset.delta > 0


def test_new_player_moves_more_than_established_player() -> None:
    newcomer = RatingState(rating=1500, rating_deviation=350)
    veteran = RatingState(rating=1500, rating_deviation=60)
    opponent = [OpponentResult(1500, 100, 1.0)]

    newcomer_update = update_player(newcomer, opponent, now=NOW)
    veteran_update = update_player(veteran, opponent, now=NOW)

    assert newcomer_update.delta > veteran_update.delta


def test_rating_deviation_decreases_after_match() -> None:
    state = RatingState(rating=1500, rating_deviation=350)

    update = update_player(state, [OpponentResult(1500, 100, 1.0)], now=NOW)

    assert update.rating_deviation_after < state.rating_deviation


def test_inactivity_inflates_rd_without_changing_rating() -> None:
    state = RatingState(
        rating=1500,
        rating_deviation=80,
        last_rated_at=NOW - timedelta(days=30),
    )

    inflated = inflate_rating_deviation(state, now=NOW)

    assert inflated > state.rating_deviation
    assert inflated <= MAX_RATING_DEVIATION
    assert state.rating == 1500


def test_delta_is_capped() -> None:
    state = RatingState(rating=500, rating_deviation=350)

    update = update_player(state, [OpponentResult(2500, 30, 1.0)], now=NOW)

    assert abs(update.delta) <= MAX_DELTA
    assert abs(update.rating_after - update.rating_before) <= MAX_DELTA


def test_team_match_returns_updates_for_everyone() -> None:
    team_1 = [
        RatingState(rating=1600, rating_deviation=100),
        RatingState(rating=1550, rating_deviation=100),
    ]
    team_2 = [
        RatingState(rating=1500, rating_deviation=100),
        RatingState(rating=1450, rating_deviation=100),
    ]

    updates = rate_match(team_1, team_2, result="TEAM_1", now=NOW)

    assert len(updates) == 4
    assert sum(update.delta for update in updates[:2]) > 0
    assert sum(update.delta for update in updates[2:]) < 0


def test_draw_gives_half_score() -> None:
    team_1 = [RatingState(rating=1500, rating_deviation=100)]
    team_2 = [RatingState(rating=1500, rating_deviation=100)]

    updates = rate_match(team_1, team_2, result="DRAW", now=NOW)

    assert updates[0].result == "DRAW"
    assert updates[1].result == "DRAW"
    assert updates[0].delta == pytest.approx(0, abs=1e-6)
    assert updates[1].delta == pytest.approx(0, abs=1e-6)


def test_divisions_and_placement() -> None:
    assert division_for(1100, PLACEMENT_MATCHES) == "BRONZE"
    assert division_for(1300, PLACEMENT_MATCHES) == "SILVER"
    assert division_for(1500, PLACEMENT_MATCHES) == "GOLD"
    assert division_for(1700, PLACEMENT_MATCHES) == "PLATINUM"
    assert division_for(1900, PLACEMENT_MATCHES) == "DIAMOND"
    assert division_for(1900, 0) == "PROVISIONAL"

    progress = division_progress(1500, PLACEMENT_MATCHES)
    assert progress["division"] == "GOLD"
    assert progress["provisional"] is False
    assert 0.0 <= float(progress["progress"]) <= 1.0

    provisional = division_progress(1500, 2)
    assert provisional["provisional"] is True
    assert provisional["placement_matches_remaining"] == PLACEMENT_MATCHES - 2


def test_simulation_separates_stronger_players() -> None:
    from app.modules.ratings.simulation import simulate_ladder

    result = simulate_ladder(players=40, matches=2000, seed=11)

    assert result.high_quartile_rating > result.low_quartile_rating
    assert result.high_quartile_rating - result.low_quartile_rating > 50
    assert abs(result.average_rating - 1500) < 200
