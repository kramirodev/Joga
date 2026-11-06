"""Testes das regras puras de apuração de resultado."""

from app.modules.results.policy import (
    DECISION_ANALYSIS,
    DECISION_DISPUTE,
    DECISION_FINALIZE,
    DECISION_REVIEW,
    DECISION_SECOND_ROUND,
    evaluate_round,
    format_allows_draw,
    quorum_for,
)


def test_quorum_rounds_up() -> None:
    assert quorum_for(0) == 0
    assert quorum_for(1) == 1
    assert quorum_for(9) == 5
    assert quorum_for(10) == 5
    assert quorum_for(12) == 6


def test_draw_only_for_football() -> None:
    assert format_allows_draw("futebol")
    assert not format_allows_draw("volei")
    assert not format_allows_draw(None)


def test_plurality_below_fifty_finalizes() -> None:
    result = evaluate_round(
        {"TEAM_1": 6, "TEAM_2": 2, "DRAW": 2},
        eligible_count=10,
        round_number=1,
    )
    assert result.decision == DECISION_FINALIZE
    assert result.evaluated_outcome == "TEAM_1"
    assert result.divergent_votes == 4
    assert result.valid_votes == 10


def test_exactly_fifty_opens_second_round() -> None:
    result = evaluate_round(
        {"TEAM_1": 5, "TEAM_2": 5, "DRAW": 0},
        eligible_count=10,
        round_number=1,
    )
    assert result.decision == DECISION_SECOND_ROUND
    assert result.evaluated_outcome is None


def test_above_fifty_opens_dispute() -> None:
    result = evaluate_round(
        {"TEAM_1": 3, "TEAM_2": 4, "DRAW": 3},
        eligible_count=10,
        round_number=1,
    )
    assert result.decision == DECISION_DISPUTE
    assert result.evaluated_outcome == "TEAM_2"
    assert result.review_reason == "DIVERGENCE"


def test_quorum_uses_valid_votes_only() -> None:
    result = evaluate_round(
        {"TEAM_1": 4, "TEAM_2": 0, "DRAW": 0},
        eligible_count=10,
        round_number=1,
    )
    assert result.decision == DECISION_REVIEW
    assert result.review_reason == "QUORUM"
    assert result.valid_votes == 4


def test_tie_in_first_round_opens_second_round() -> None:
    result = evaluate_round(
        {"TEAM_1": 4, "TEAM_2": 4, "DRAW": 2},
        eligible_count=10,
        round_number=1,
    )
    assert result.decision == DECISION_SECOND_ROUND
    assert result.leaders == ("TEAM_1", "TEAM_2")


def test_tie_in_second_round_goes_to_review() -> None:
    result = evaluate_round(
        {"TEAM_1": 4, "TEAM_2": 4, "DRAW": 2},
        eligible_count=10,
        round_number=2,
    )
    assert result.decision == DECISION_DISPUTE
    assert result.review_reason == "NO_UNIQUE_RESULT"


def test_second_round_exact_fifty_runs_analysis() -> None:
    result = evaluate_round(
        {"TEAM_1": 5, "TEAM_2": 3, "DRAW": 2},
        eligible_count=10,
        round_number=2,
    )
    assert result.decision == DECISION_ANALYSIS
    assert result.review_reason == "SECOND_ROUND_50"


def test_second_round_below_fifty_finalizes() -> None:
    result = evaluate_round(
        {"TEAM_1": 7, "TEAM_2": 2, "DRAW": 1},
        eligible_count=10,
        round_number=2,
    )
    assert result.decision == DECISION_FINALIZE
    assert result.evaluated_outcome == "TEAM_1"
