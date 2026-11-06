"""Testes da retenção provisória dos dados de resultado."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.matches.models import Match, MatchParticipant
from app.modules.ratelimit.models import RateLimitCounter
from app.modules.ratelimit.service import enforce as enforce_rate_limit
from app.modules.results.cleanup import cleanup_results
from app.modules.results.models import (
    MatchDispute,
    MatchDisputeEvidence,
    MatchResultAnalysis,
    MatchResultCaptainConfirmation,
    MatchResultDecision,
    MatchResultReport,
    MatchResultReview,
    MatchResultRound,
)
from app.modules.results.service import ResultsService
from tests.helpers_results import END, build_match

AT = END + timedelta(minutes=2)
NOW = END + timedelta(days=1000)


def make_match_with_data(
    session: Session,
    *,
    closed_at: datetime,
    state: str = "FINALIZED",
) -> tuple[Match, list[MatchParticipant], MatchResultRound]:
    match, users, participants, _ = build_match(session, checked_in=10)
    service = ResultsService(session)
    service.advance(now=END)
    round_row = service.current_round(match.id)
    assert round_row is not None

    for index in range(5):
        service.submit_report(
            match_id=match.id,
            user_id=users[index],
            round_number=1,
            outcome="TEAM_1",
            idempotency_key=f"retention-report-{index}",
            request_hash=f"retention-report-{index}",
            now=AT,
        )

    captain = next(participant for participant in participants if participant.is_captain)
    service.submit_confirmation(
        match_id=match.id,
        user_id=captain.user_id,
        round_number=1,
        outcome="TEAM_1",
        idempotency_key="retention-confirmation",
        request_hash="retention-confirmation",
        now=AT,
    )

    round_row.status = "CLOSED"
    round_row.closed_at = closed_at
    match.state = state
    match.finalized_at = closed_at if state == "FINALIZED" else None
    match.voided_reason = None if state == "FINALIZED" else "teste"
    match.updated_at = closed_at
    session.flush()
    return match, participants, round_row


def add_dispute_data(
    session: Session,
    match: Match,
    participants: list[MatchParticipant],
    round_row: MatchResultRound,
    *,
    closed_at: datetime,
) -> tuple[MatchDispute, MatchResultReview]:
    dispute = MatchDispute(
        match_id=match.id,
        round_id=round_row.id,
        reason="QUORUM",
        status="CLOSED",
        opened_at=closed_at,
        closed_at=closed_at,
    )
    session.add(dispute)
    session.flush()
    session.add(
        MatchDisputeEvidence(
            dispute_id=dispute.id,
            participant_id=participants[0].id,
            text="evidência de teste",
            char_count=len("evidência de teste"),
            created_at=closed_at,
            idempotency_key="retention-evidence",
            request_hash="retention-evidence",
        )
    )
    review = MatchResultReview(
        match_id=match.id,
        round_id=round_row.id,
        reason="QUORUM",
        status="RESOLVED",
        created_at=closed_at,
        resolved_at=closed_at,
    )
    session.add(review)
    session.flush()
    session.add(
        MatchResultDecision(
            match_id=match.id,
            review_id=review.id,
            decision="FINALIZE",
            outcome="TEAM_1",
            reason="decisão de teste",
            operator_id="operator-test",
            origin="HUMAN",
            created_at=closed_at,
        )
    )
    session.add(
        MatchResultAnalysis(
            match_id=match.id,
            round_id=round_row.id,
            signals={},
            conclusion="INCONCLUSIVE",
            created_at=closed_at,
        )
    )
    session.flush()
    return dispute, review


def count(session: Session, model, *conditions) -> int:  # noqa: ANN001
    return int(session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)


def test_cleanup_removes_old_finalized_data_and_preserves_recent(
    db_session: Session,
) -> None:
    old_match, old_participants, old_round = make_match_with_data(
        db_session,
        closed_at=NOW - timedelta(days=800),
    )
    _, _, recent_round = make_match_with_data(
        db_session,
        closed_at=NOW - timedelta(days=100),
    )
    add_dispute_data(
        db_session,
        old_match,
        old_participants,
        old_round,
        closed_at=NOW - timedelta(days=800),
    )

    result = cleanup_results(db_session, now=NOW)

    assert result.reports == 5
    assert result.confirmations == 1
    assert result.evidence == 1
    assert result.decisions == 1
    assert result.reviews == 1
    assert result.analyses == 1

    assert count(db_session, MatchResultReport, MatchResultReport.round_id == old_round.id) == 0
    assert (
        count(
            db_session,
            MatchResultCaptainConfirmation,
            MatchResultCaptainConfirmation.round_id == old_round.id,
        )
        == 0
    )
    assert count(db_session, MatchResultReport, MatchResultReport.round_id == recent_round.id) == 5
    assert count(db_session, MatchResultReport) == 5
    assert count(db_session, MatchDisputeEvidence) == 0
    assert count(db_session, MatchResultDecision) == 0
    assert count(db_session, MatchResultReview) == 0
    assert count(db_session, MatchResultAnalysis) == 0


def test_cleanup_preserves_active_match_data(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service = ResultsService(db_session)
    service.advance(now=END)
    round_row = service.current_round(match.id)
    assert round_row is not None
    service.submit_report(
        match_id=match.id,
        user_id=users[0],
        round_number=1,
        outcome="TEAM_1",
        idempotency_key="active-report",
        request_hash="active-report",
        now=AT,
    )

    result = cleanup_results(db_session, now=NOW)

    assert result.reports == 0
    assert count(db_session, MatchResultReport, MatchResultReport.round_id == round_row.id) == 1


def test_cleanup_removes_old_voided_match_data(db_session: Session) -> None:
    match, _, round_row = make_match_with_data(
        db_session,
        closed_at=NOW - timedelta(days=800),
        state="VOIDED",
    )

    result = cleanup_results(db_session, now=NOW)

    assert result.reports == 5
    assert count(db_session, MatchResultReport, MatchResultReport.round_id == round_row.id) == 0
    assert count(db_session, MatchResultCaptainConfirmation) == 0
    assert db_session.get(Match, match.id) is not None


def test_cleanup_uses_separate_cutoffs(db_session: Session) -> None:
    match, participants, round_row = make_match_with_data(
        db_session,
        closed_at=NOW - timedelta(days=800),
    )
    add_dispute_data(
        db_session,
        match,
        participants,
        round_row,
        closed_at=NOW - timedelta(days=100),
    )

    result = cleanup_results(db_session, now=NOW, report_days=730, evidence_days=365)

    assert result.reports == 5
    assert result.evidence == 0
    assert result.decisions == 0
    assert result.reviews == 0
    assert count(db_session, MatchDisputeEvidence) == 1
    assert count(db_session, MatchResultDecision) == 1
    assert count(db_session, MatchResultReview) == 1


def test_cleanup_removes_old_rate_limit_counters(db_session: Session) -> None:
    enforce_rate_limit(
        db_session,
        scope="cleanup-test",
        key="old",
        limit=10,
        now=NOW - timedelta(days=2),
    )
    enforce_rate_limit(
        db_session,
        scope="cleanup-test",
        key="recent",
        limit=10,
        now=NOW,
    )

    result = cleanup_results(db_session, now=NOW, rate_limit_hours=24)

    assert result.rate_limits == 1
    assert count(db_session, RateLimitCounter, RateLimitCounter.key == "old") == 0
    assert count(db_session, RateLimitCounter, RateLimitCounter.key == "recent") == 1


def test_negative_retention_is_rejected(db_session: Session) -> None:
    with pytest.raises(ValueError):
        cleanup_results(db_session, report_days=-1, now=NOW)


def test_evidence_older_than_its_cutoff_is_deleted(db_session: Session) -> None:
    match, participants, round_row = make_match_with_data(
        db_session,
        closed_at=NOW - timedelta(days=800),
    )
    add_dispute_data(
        db_session,
        match,
        participants,
        round_row,
        closed_at=NOW - timedelta(days=400),
    )

    result = cleanup_results(db_session, now=NOW, evidence_days=365)

    assert result.evidence == 1
    assert count(db_session, MatchDisputeEvidence) == 0
