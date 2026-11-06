"""Regras puras de apuração da rodada de resultado."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.modules.results.models import OUTCOMES

DRAW_ALLOWED_SPORT_SLUGS = frozenset({"futebol"})

DECISION_FINALIZE = "FINALIZE"
DECISION_SECOND_ROUND = "SECOND_ROUND"
DECISION_DISPUTE = "DISPUTE"
DECISION_REVIEW = "REVIEW"
DECISION_ANALYSIS = "ANALYSIS"


def format_allows_draw(sport_slug: str | None) -> bool:
    """Empate esportivo permitido apenas nas modalidades aprovadas."""
    return sport_slug is not None and sport_slug in DRAW_ALLOWED_SPORT_SLUGS


def quorum_for(eligible_count: int) -> int:
    """Quórum mínimo: metade dos elegíveis, arredondada para cima."""
    if eligible_count <= 0:
        return 0
    return (eligible_count + 1) // 2


@dataclass(frozen=True)
class RoundEvaluation:
    """Resultado da apuração, sem efeitos colaterais."""

    quorum: int
    valid_votes: int
    counts: dict[str, int]
    leaders: tuple[str, ...]
    evaluated_outcome: str | None
    divergent_votes: int | None
    decision: str
    review_reason: str | None


def count_votes(votes: list[str]) -> dict[str, int]:
    counts = {outcome: 0 for outcome in OUTCOMES}
    for vote in votes:
        counts[vote] = counts.get(vote, 0) + 1
    return counts


def evaluate_round(
    counts: Mapping[str, int],
    *,
    eligible_count: int,
    round_number: int,
) -> RoundEvaluation:
    """Aplica quórum, pluralidade e a regra de divergência de 50%.

    Todas as comparações são feitas em inteiros.
    """
    normalized = {outcome: int(counts.get(outcome, 0)) for outcome in OUTCOMES}
    valid = sum(normalized.values())
    quorum = quorum_for(eligible_count)

    if valid == 0 or valid < quorum:
        return RoundEvaluation(
            quorum=quorum,
            valid_votes=valid,
            counts=normalized,
            leaders=(),
            evaluated_outcome=None,
            divergent_votes=None,
            decision=DECISION_REVIEW,
            review_reason="QUORUM",
        )

    max_count = max(normalized.values())
    leaders = tuple(outcome for outcome in OUTCOMES if normalized[outcome] == max_count)

    if len(leaders) != 1:
        if round_number == 1:
            return RoundEvaluation(
                quorum=quorum,
                valid_votes=valid,
                counts=normalized,
                leaders=leaders,
                evaluated_outcome=None,
                divergent_votes=None,
                decision=DECISION_SECOND_ROUND,
                review_reason=None,
            )
        return RoundEvaluation(
            quorum=quorum,
            valid_votes=valid,
            counts=normalized,
            leaders=leaders,
            evaluated_outcome=None,
            divergent_votes=None,
            decision=DECISION_DISPUTE,
            review_reason="NO_UNIQUE_RESULT",
        )

    evaluated = leaders[0]
    divergent = valid - normalized[evaluated]

    if divergent * 2 < valid:
        decision = DECISION_FINALIZE
        reason = None
    elif divergent * 2 == valid:
        if round_number == 1:
            decision = DECISION_SECOND_ROUND
            reason = None
        else:
            decision = DECISION_ANALYSIS
            reason = "SECOND_ROUND_50"
    else:
        decision = DECISION_DISPUTE
        reason = "DIVERGENCE"

    return RoundEvaluation(
        quorum=quorum,
        valid_votes=valid,
        counts=normalized,
        leaders=leaders,
        evaluated_outcome=evaluated,
        divergent_votes=divergent,
        decision=decision,
        review_reason=reason,
    )
