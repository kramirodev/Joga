"""Simulações determinísticas do motor de rating."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime

from app.modules.ratings.engine import OpponentResult, RatingState, update_player


@dataclass(frozen=True)
class SimulationResult:
    players: int
    matches: int
    low_quartile_rating: float
    high_quartile_rating: float
    average_rating: float


def simulate_ladder(
    *,
    players: int = 60,
    matches: int = 3000,
    seed: int = 7,
    now: datetime | None = None,
) -> SimulationResult:
    """Simula partidas 1v1 com habilidade latente e retorna a separação final."""
    if players < 4 or players % 4 != 0:
        raise ValueError("players deve ser múltiplo de 4 e >= 4")
    if matches <= 0:
        raise ValueError("matches deve ser positivo")

    moment = now or datetime(2026, 11, 6, tzinfo=UTC)
    rng = random.Random(seed)
    skills = [rng.gauss(0, 200) for _ in range(players)]
    states = [RatingState() for _ in range(players)]

    for _ in range(matches):
        first, second = rng.sample(range(players), 2)
        win_probability = 1.0 / (1.0 + math.exp(-(skills[first] - skills[second]) / 200.0))
        score_first = 1.0 if rng.random() < win_probability else 0.0
        score_second = 1.0 - score_first

        first_state = states[first]
        second_state = states[second]
        states[first] = _apply(
            first_state,
            second_state,
            score_first,
            moment,
        )
        states[second] = _apply(
            second_state,
            first_state,
            score_second,
            moment,
        )

    ordered = sorted(zip(skills, states, strict=True), key=lambda item: item[0])
    quartile = players // 4
    low = ordered[:quartile]
    high = ordered[-quartile:]
    low_rating = sum(state.rating for _, state in low) / len(low)
    high_rating = sum(state.rating for _, state in high) / len(high)
    average = sum(state.rating for _, state in ordered) / len(ordered)

    return SimulationResult(
        players=players,
        matches=matches,
        low_quartile_rating=low_rating,
        high_quartile_rating=high_rating,
        average_rating=average,
    )


def _apply(
    state: RatingState,
    opponent: RatingState,
    score: float,
    now: datetime,
) -> RatingState:
    update = update_player(
        state,
        [OpponentResult(opponent.rating, opponent.rating_deviation, score)],
        now=now,
    )
    return RatingState(
        rating=update.rating_after,
        rating_deviation=update.rating_deviation_after,
        volatility=update.volatility_after,
        matches_played=state.matches_played + 1,
        last_rated_at=now,
    )
