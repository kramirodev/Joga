"""Glicko-2 adaptado para partidas em equipe, sem dependência de banco."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from app.modules.identity.clock import ensure_utc

SCALE = 173.7178
DEFAULT_RATING = 1500.0
DEFAULT_RATING_DEVIATION = 350.0
DEFAULT_VOLATILITY = 0.06
MAX_RATING_DEVIATION = 350.0
MIN_RATING_DEVIATION = 30.0
MAX_DELTA = 100.0
INACTIVITY_PERIOD_DAYS = 7
PERIODS_TO_MAX_RD = 50
TAU = 0.5
EPSILON = 1e-6
PLACEMENT_MATCHES = 5

# c do Glicko-2 para levar RD de 50 até o teto em 50 períodos.
RD_INFLATION_C = math.sqrt((MAX_RATING_DEVIATION**2 - MIN_RATING_DEVIATION**2) / PERIODS_TO_MAX_RD)

DIVISIONS = ("BRONZE", "SILVER", "GOLD", "PLATINUM", "DIAMOND")


@dataclass(frozen=True)
class RatingState:
    """Rating de um jogador antes da partida."""

    rating: float = DEFAULT_RATING
    rating_deviation: float = DEFAULT_RATING_DEVIATION
    volatility: float = DEFAULT_VOLATILITY
    matches_played: int = 0
    last_rated_at: datetime | None = None


@dataclass(frozen=True)
class OpponentResult:
    """Resultado contra um adversário/pseudo-adversário."""

    rating: float
    rating_deviation: float
    score: float  # 1.0 vitória, 0.5 empate, 0.0 derrota


@dataclass(frozen=True)
class RatingUpdate:
    """Resultado do cálculo para um jogador."""

    rating_before: float
    rating_after: float
    rating_deviation_before: float
    rating_deviation_after: float
    volatility_before: float
    volatility_after: float
    expected_score: float
    delta: float
    result: str


@dataclass(frozen=True)
class TeamRating:
    """Agregado usado como adversário de uma equipe."""

    rating: float
    rating_deviation: float


def glicko_g(rating_deviation: float) -> float:
    """Fator g do Glicko-2, calculado na escala phi."""
    phi = max(rating_deviation, 0.0) / SCALE
    return 1.0 / math.sqrt(1.0 + (3.0 * phi * phi) / (math.pi * math.pi))


def expected_score(
    rating: float,
    opponent_rating: float,
    opponent_rating_deviation: float,
) -> float:
    """Probabilidade esperada de vitória em uma partida individual."""
    mu = (rating - DEFAULT_RATING) / SCALE
    opponent_mu = (opponent_rating - DEFAULT_RATING) / SCALE
    g = glicko_g(opponent_rating_deviation)
    return 1.0 / (1.0 + math.exp(-g * (mu - opponent_mu)))


def team_rating(states: list[RatingState], *, now: datetime | None = None) -> TeamRating:
    """Média de rating e de incerteza da equipe."""
    if not states:
        raise ValueError("equipe sem jogadores")
    deviations = [
        inflate_rating_deviation(state, now=now) if now is not None else state.rating_deviation
        for state in states
    ]
    return TeamRating(
        rating=sum(state.rating for state in states) / len(states),
        rating_deviation=sum(deviations) / len(deviations),
    )


def inflate_rating_deviation(
    state: RatingState,
    *,
    now: datetime,
) -> float:
    """Aumenta RD por inatividade; nunca altera o rating."""
    if state.last_rated_at is None:
        return min(max(state.rating_deviation, 0.0), MAX_RATING_DEVIATION)

    elapsed = ensure_utc(now) - ensure_utc(state.last_rated_at)
    elapsed_days = max(0.0, elapsed.total_seconds() / 86400)
    periods = elapsed_days / INACTIVITY_PERIOD_DAYS
    inflated = math.sqrt(state.rating_deviation**2 + RD_INFLATION_C**2 * periods)
    return min(inflated, MAX_RATING_DEVIATION)


def update_player(
    state: RatingState,
    opponents: list[OpponentResult],
    *,
    now: datetime,
) -> RatingUpdate:
    """Aplica uma rodada Glicko-2 a um jogador.

    Em partidas de equipe, ``opponents`` contém um único pseudo-adversário com
    a média da equipe oposta.
    """
    if not opponents:
        raise ValueError("jogador sem adversários")

    rd_before = inflate_rating_deviation(state, now=now)
    mu = (state.rating - DEFAULT_RATING) / SCALE
    phi = rd_before / SCALE
    sigma = max(state.volatility, 1e-6)

    v_inverse = 0.0
    delta_sum = 0.0
    weighted_expected = 0.0
    weight_sum = 0.0

    for opponent in opponents:
        opponent_mu = (opponent.rating - DEFAULT_RATING) / SCALE
        opponent_phi = max(opponent.rating_deviation, 0.0) / SCALE
        g = 1.0 / math.sqrt(1.0 + (3.0 * opponent_phi * opponent_phi) / (math.pi * math.pi))
        expected = 1.0 / (1.0 + math.exp(-g * (mu - opponent_mu)))
        expected = min(max(expected, 1e-9), 1.0 - 1e-9)
        v_inverse += g * g * expected * (1.0 - expected)
        delta_sum += g * (opponent.score - expected)
        weighted_expected += g * expected
        weight_sum += g

    if v_inverse <= 0:
        raise ValueError("variância de rating inválida")

    v = 1.0 / v_inverse
    delta = v * delta_sum
    sigma_new = _new_volatility(phi, v, delta, sigma)
    phi_star = math.sqrt(phi * phi + sigma_new * sigma_new)
    phi_new = 1.0 / math.sqrt((1.0 / (phi_star * phi_star)) + (1.0 / v))
    mu_new = mu + (phi_new * phi_new) * delta_sum

    rating_after = DEFAULT_RATING + SCALE * mu_new
    rating_delta = rating_after - state.rating
    if abs(rating_delta) > MAX_DELTA:
        rating_after = state.rating + math.copysign(MAX_DELTA, rating_delta)
        rating_delta = rating_after - state.rating

    rd_after = min(max(SCALE * phi_new, 0.0), MAX_RATING_DEVIATION)
    expected = weighted_expected / weight_sum if weight_sum else 0.5

    return RatingUpdate(
        rating_before=state.rating,
        rating_after=rating_after,
        rating_deviation_before=rd_before,
        rating_deviation_after=rd_after,
        volatility_before=state.volatility,
        volatility_after=sigma_new,
        expected_score=expected,
        delta=rating_delta,
        result=_result_for_score(opponents[0].score),
    )


def rate_match(
    team_1: list[RatingState],
    team_2: list[RatingState],
    *,
    result: str,
    now: datetime,
) -> list[RatingUpdate]:
    """Calcula atualizações para as duas equipes a partir do estado pré-partida."""
    if result not in ("TEAM_1", "TEAM_2", "DRAW"):
        raise ValueError("resultado inválido")

    aggregate_1 = team_rating(team_1, now=now)
    aggregate_2 = team_rating(team_2, now=now)

    if result == "TEAM_1":
        score_1, score_2 = 1.0, 0.0
    elif result == "TEAM_2":
        score_1, score_2 = 0.0, 1.0
    else:
        score_1 = score_2 = 0.5

    opponent_1 = OpponentResult(
        rating=aggregate_2.rating,
        rating_deviation=aggregate_2.rating_deviation,
        score=score_1,
    )
    opponent_2 = OpponentResult(
        rating=aggregate_1.rating,
        rating_deviation=aggregate_1.rating_deviation,
        score=score_2,
    )

    updates = [update_player(player, [opponent_1], now=now) for player in team_1]
    updates.extend(update_player(player, [opponent_2], now=now) for player in team_2)
    return updates


def division_for(rating: float, matches_played: int) -> str:
    """Divisão visível; jogadores em colocação ficam como PROVISIONAL."""
    if matches_played < PLACEMENT_MATCHES:
        return "PROVISIONAL"
    if rating >= 1800:
        return "DIAMOND"
    if rating >= 1600:
        return "PLATINUM"
    if rating >= 1400:
        return "GOLD"
    if rating >= 1200:
        return "SILVER"
    return "BRONZE"


def division_progress(rating: float, matches_played: int) -> dict[str, float | str | bool | None]:
    """Faixa e progresso para a interface, sem expor o MMR bruto."""
    division = division_for(rating, matches_played)
    if division == "PROVISIONAL":
        remaining = max(0, PLACEMENT_MATCHES - matches_played)
        return {
            "division": division,
            "provisional": True,
            "placement_matches_remaining": remaining,
            "progress": None,
            "next_division": None,
        }

    thresholds = {
        "BRONZE": (0.0, 1200.0),
        "SILVER": (1200.0, 1400.0),
        "GOLD": (1400.0, 1600.0),
        "PLATINUM": (1600.0, 1800.0),
        "DIAMOND": (1800.0, None),
    }
    low, high = thresholds[division]
    if high is None:
        progress = 1.0
        next_division = None
    else:
        progress = min(max((rating - low) / (high - low), 0.0), 1.0)
        next_division = DIVISIONS[DIVISIONS.index(division) + 1]
    return {
        "division": division,
        "provisional": False,
        "placement_matches_remaining": 0,
        "progress": progress,
        "next_division": next_division,
    }


def _new_volatility(phi: float, v: float, delta: float, sigma: float) -> float:
    """Iteração de Illinois do Glicko-2 para a nova volatilidade."""
    a = math.log(sigma * sigma)

    def f(x: float) -> float:
        ex = math.exp(x)
        numerator = ex * (delta * delta - phi * phi - v - ex)
        denominator = 2.0 * (phi * phi + v + ex) ** 2
        return numerator / denominator - (x - a) / (TAU * TAU)

    big_a = a
    if delta * delta > phi * phi + v:
        big_b = math.log(delta * delta - phi * phi - v)
    else:
        k = 1
        while f(a - k * TAU) < 0 and k < 100:
            k += 1
        big_b = a - k * TAU

    f_a = f(big_a)
    f_b = f(big_b)
    while abs(big_b - big_a) > EPSILON:
        denominator = f_b - f_a
        if abs(denominator) < 1e-12:
            break
        big_c = big_a + (big_a - big_b) * f_a / denominator
        f_c = f(big_c)
        if f_c * f_b <= 0:
            big_a, f_a = big_b, f_b
        else:
            f_a /= 2.0
        big_b, f_b = big_c, f_c

    return max(math.exp(big_a / 2.0), 1e-6)


def _result_for_score(score: float) -> str:
    if score > 0.5:
        return "WIN"
    if score < 0.5:
        return "LOSS"
    return "DRAW"
