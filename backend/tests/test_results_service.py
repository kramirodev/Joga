"""Testes do serviço de resultados, disputas e decisão humana."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc
from app.modules.results.models import (
    MatchDispute,
    MatchResultAnalysis,
    MatchResultDecision,
    MatchResultReport,
    MatchResultReview,
    MatchResultRound,
)
from app.modules.results.service import (
    ConfirmationAlreadySubmitted,
    DrawNotAllowed,
    EvidenceAlreadySubmitted,
    EvidenceEmpty,
    EvidenceNotFound,
    EvidenceTooLong,
    IneligibleParticipant,
    NotCaptain,
    ReportAlreadySubmitted,
    ResultsService,
    ResultWindowNotOpen,
    ReviewNotFound,
)
from tests.helpers_results import END, START, build_match

AT = END + timedelta(minutes=2)


def open_round(session: Session, match_id: uuid.UUID) -> tuple[ResultsService, MatchResultRound]:
    service = ResultsService(session)
    service.advance(now=END)
    round_row = service.current_round(match_id)
    assert round_row is not None
    assert round_row.status == "OPEN"
    return service, round_row


def submit(
    service: ResultsService,
    match_id: uuid.UUID,
    users: list[uuid.UUID],
    outcomes: list[str],
    *,
    round_number: int = 1,
    now=AT,
) -> None:
    for index, (user_id, outcome) in enumerate(zip(users, outcomes, strict=True)):
        service.submit_report(
            match_id=match_id,
            user_id=user_id,
            round_number=round_number,
            outcome=outcome,
            idempotency_key=f"{round_number}-{index}-{outcome}",
            request_hash=f"hash-{round_number}-{index}",
            now=now,
        )


def close_round(session: Session, round_row: MatchResultRound) -> None:
    ResultsService(session).advance(now=ensure_utc(round_row.deadline) + timedelta(seconds=1))


def test_open_first_round_freezes_eligible_and_is_idempotent(db_session: Session) -> None:
    match, users, participants, _ = build_match(db_session, checked_in=10)

    service, round_row = open_round(db_session, match.id)

    assert match.state == "RESULT_PENDING"
    assert round_row.round_number == 1
    assert round_row.eligible_count == 10
    assert round_row.quorum == 5
    assert all(service.eligible_for_user(match.id, user_id) for user_id in users)

    again = service.advance(now=END)
    assert again.rounds_opened == 0
    rounds = db_session.scalars(
        select(MatchResultRound).where(MatchResultRound.match_id == match.id)
    ).all()
    assert len(rounds) == 1
    assert len(participants) == 10


def test_eligible_freezes_checked_in_at_opening(db_session: Session) -> None:
    match, users, participants, _ = build_match(db_session, checked_in=8)

    service, round_row = open_round(db_session, match.id)

    assert round_row.eligible_count == 8
    assert round_row.quorum == 4
    confirmed = next(item for item in participants if item.status == "confirmed")
    assert service.eligible_for_user(match.id, confirmed.user_id) is None
    with pytest.raises(IneligibleParticipant):
        service.submit_report(
            match_id=match.id,
            user_id=confirmed.user_id,
            round_number=1,
            outcome="TEAM_1",
            idempotency_key="ineligible",
            request_hash="ineligible",
            now=AT,
        )


def test_vote_before_window_is_rejected(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)

    with pytest.raises(ResultWindowNotOpen):
        ResultsService(db_session).submit_report(
            match_id=match.id,
            user_id=users[0],
            round_number=1,
            outcome="TEAM_1",
            idempotency_key="early",
            request_hash="early",
            now=AT,
        )


def test_plurality_below_fifty_finalizes(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, round_row = open_round(db_session, match.id)

    submit(
        service,
        match.id,
        users,
        ["TEAM_1"] * 6 + ["TEAM_2"] * 2 + ["DRAW"] * 2,
    )
    close_round(db_session, round_row)

    db_session.refresh(match)
    db_session.refresh(round_row)
    assert match.state == "FINALIZED"
    assert match.final_result == "TEAM_1"
    assert match.finalized_at is not None
    assert match.result_version == 1
    assert round_row.outcome == "FINALIZED"
    assert round_row.valid_votes == 10
    assert round_row.divergent_votes == 4
    assert round_row.evaluated_outcome == "TEAM_1"


def test_exact_fifty_opens_second_round(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)

    submit(service, match.id, users, ["TEAM_1"] * 5 + ["TEAM_2"] * 5)
    close_round(db_session, first)

    db_session.refresh(first)
    assert first.outcome == "SECOND_ROUND"
    assert match.state == "RESULT_PENDING"
    second = service.round_by_number(match.id, 2)
    assert second is not None
    assert second.status == "OPEN"
    assert second.eligible_count == 10
    assert second.quorum == 5
    assert ensure_utc(second.opens_at) == ensure_utc(first.deadline)
    assert ensure_utc(second.deadline) == ensure_utc(first.deadline) + timedelta(minutes=5)


def test_tie_in_first_round_opens_second_round(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)

    submit(
        service,
        match.id,
        users,
        ["TEAM_1"] * 4 + ["TEAM_2"] * 4 + ["DRAW"] * 2,
    )
    close_round(db_session, first)

    db_session.refresh(first)
    assert first.outcome == "SECOND_ROUND"
    assert service.round_by_number(match.id, 2) is not None


def test_above_fifty_opens_dispute_and_review(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)

    submit(
        service,
        match.id,
        users,
        ["TEAM_1"] * 3 + ["TEAM_2"] * 4 + ["DRAW"] * 3,
    )
    close_round(db_session, first)

    db_session.refresh(match)
    db_session.refresh(first)
    assert first.outcome == "DISPUTED"
    assert match.state == "DISPUTED"
    review = service.pending_review(match.id)
    assert review is not None and review.reason == "DIVERGENCE"
    dispute = service.latest_open_dispute(match.id)
    assert dispute is not None and dispute.reason == "DIVERGENCE"


def test_quorum_failure_goes_to_human_review(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)

    submit(service, match.id, users[:4], ["TEAM_1"] * 4)
    close_round(db_session, first)

    db_session.refresh(match)
    db_session.refresh(first)
    assert first.outcome == "REVIEW"
    assert first.valid_votes == 4
    assert match.state == "RESULT_PENDING"
    review = service.pending_review(match.id)
    assert review is not None and review.reason == "QUORUM"


def test_closing_the_same_round_twice_does_not_duplicate_review(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)
    submit(service, match.id, users[:4], ["TEAM_1"] * 4)
    close_round(db_session, first)

    reviews_before = len(
        db_session.scalars(
            select(MatchResultReview).where(MatchResultReview.match_id == match.id)
        ).all()
    )
    disputes_before = len(
        db_session.scalars(select(MatchDispute).where(MatchDispute.match_id == match.id)).all()
    )
    assert reviews_before == 1
    assert disputes_before == 1

    service.advance(now=ensure_utc(first.deadline) + timedelta(minutes=1))

    reviews_after = len(
        db_session.scalars(
            select(MatchResultReview).where(MatchResultReview.match_id == match.id)
        ).all()
    )
    disputes_after = len(
        db_session.scalars(select(MatchDispute).where(MatchDispute.match_id == match.id)).all()
    )
    assert reviews_after == reviews_before
    assert disputes_after == disputes_before


def test_late_votes_are_outside_the_denominator(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)

    submit(service, match.id, users[:4], ["TEAM_1"] * 4)
    participant = service.participant_for_user(match.id, users[4])
    assert participant is not None
    db_session.add(
        MatchResultReport(
            round_id=first.id,
            participant_id=participant.id,
            outcome="TEAM_2",
            submitted_at=ensure_utc(first.deadline) + timedelta(minutes=1),
            idempotency_key="late",
            request_hash="late",
        )
    )
    db_session.flush()
    close_round(db_session, first)

    db_session.refresh(first)
    assert first.valid_votes == 4
    assert len(service.effective_votes(first)) == 4


def test_second_round_finalizes_below_fifty(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)
    submit(service, match.id, users, ["TEAM_1"] * 5 + ["TEAM_2"] * 5)
    close_round(db_session, first)

    second = service.round_by_number(match.id, 2)
    assert second is not None
    submit(
        service,
        match.id,
        users,
        ["TEAM_1"] * 7 + ["TEAM_2"] * 2 + ["DRAW"] * 1,
        round_number=2,
        now=ensure_utc(second.opens_at) + timedelta(minutes=2),
    )
    close_round(db_session, second)

    db_session.refresh(match)
    db_session.refresh(second)
    assert second.outcome == "FINALIZED"
    assert match.state == "FINALIZED"
    assert match.final_result == "TEAM_1"


def test_second_round_exact_fifty_records_analysis_for_review(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)
    submit(service, match.id, users, ["TEAM_1"] * 5 + ["TEAM_2"] * 5)
    close_round(db_session, first)

    second = service.round_by_number(match.id, 2)
    assert second is not None
    submit(
        service,
        match.id,
        users,
        ["TEAM_1"] * 5 + ["TEAM_2"] * 3 + ["DRAW"] * 2,
        round_number=2,
        now=ensure_utc(second.opens_at) + timedelta(minutes=2),
    )
    close_round(db_session, second)

    db_session.refresh(match)
    db_session.refresh(second)
    assert second.outcome == "REVIEW"
    assert match.state == "DISPUTED"
    review = service.pending_review(match.id)
    assert review is not None and review.reason == "SECOND_ROUND_50"
    analysis = db_session.scalar(
        select(MatchResultAnalysis).where(MatchResultAnalysis.match_id == match.id)
    )
    assert analysis is not None
    assert analysis.conclusion == "INCONCLUSIVE"
    assert analysis.signals["conclusion"] == "INCONCLUSIVE"


def test_second_round_tie_goes_to_human_review(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)
    submit(service, match.id, users, ["TEAM_1"] * 5 + ["TEAM_2"] * 5)
    close_round(db_session, first)

    second = service.round_by_number(match.id, 2)
    assert second is not None
    submit(
        service,
        match.id,
        users,
        ["TEAM_1"] * 4 + ["TEAM_2"] * 4 + ["DRAW"] * 2,
        round_number=2,
        now=ensure_utc(second.opens_at) + timedelta(minutes=2),
    )
    close_round(db_session, second)

    db_session.refresh(match)
    db_session.refresh(second)
    assert second.outcome == "DISPUTED"
    assert match.state == "DISPUTED"
    review = service.pending_review(match.id)
    assert review is not None and review.reason == "NO_UNIQUE_RESULT"


def test_round_one_rejects_duplicate_report(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, _ = open_round(db_session, match.id)

    submit(service, match.id, users[:1], ["TEAM_1"])
    with pytest.raises(ReportAlreadySubmitted):
        service.submit_report(
            match_id=match.id,
            user_id=users[0],
            round_number=1,
            outcome="TEAM_2",
            idempotency_key="duplicate",
            request_hash="duplicate",
            now=AT + timedelta(seconds=1),
        )


def test_round_two_keeps_history_and_uses_last_vote(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)
    submit(service, match.id, users, ["TEAM_1"] * 5 + ["TEAM_2"] * 5)
    close_round(db_session, first)

    second = service.round_by_number(match.id, 2)
    assert second is not None
    participant = service.participant_for_user(match.id, users[0])
    assert participant is not None
    now = ensure_utc(second.opens_at) + timedelta(minutes=1)
    service.submit_report(
        match_id=match.id,
        user_id=users[0],
        round_number=2,
        outcome="TEAM_1",
        idempotency_key="second-a",
        request_hash="second-a",
        now=now,
    )
    service.submit_report(
        match_id=match.id,
        user_id=users[0],
        round_number=2,
        outcome="TEAM_2",
        idempotency_key="second-b",
        request_hash="second-b",
        now=now + timedelta(seconds=1),
    )

    votes = service.effective_votes(second)
    assert votes[participant.id].outcome == "TEAM_2"
    reports = db_session.scalars(
        select(MatchResultReport).where(MatchResultReport.round_id == second.id)
    ).all()
    assert len(reports) == 2


def test_draw_is_rejected_for_volleyball(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, sport_slug="volei", team_size=6, checked_in=12)
    service, _ = open_round(db_session, match.id)

    with pytest.raises(DrawNotAllowed):
        service.submit_report(
            match_id=match.id,
            user_id=users[0],
            round_number=1,
            outcome="DRAW",
            idempotency_key="draw",
            request_hash="draw",
            now=AT,
        )

    report = service.submit_report(
        match_id=match.id,
        user_id=users[0],
        round_number=1,
        outcome="TEAM_1",
        idempotency_key="team-1",
        request_hash="team-1",
        now=AT,
    )
    assert report.outcome == "TEAM_1"


def test_captain_confirmation_is_separate_from_vote(db_session: Session) -> None:
    match, users, participants, _ = build_match(db_session, checked_in=10)
    service, round_row = open_round(db_session, match.id)

    captains = [item for item in participants if item.is_captain]
    assert len(captains) == 2
    assert {item.team for item in captains} == {1, 2}
    assert all(item.captain_selection_version == "provisional_v1" for item in captains)
    assert all(item.captain_selected_at is not None for item in captains)

    team_one = next(item for item in captains if item.team == 1)
    non_captain = next(item for item in participants if not item.is_captain)
    with pytest.raises(NotCaptain):
        service.submit_confirmation(
            match_id=match.id,
            user_id=non_captain.user_id,
            round_number=1,
            outcome="TEAM_1",
            idempotency_key="non-captain",
            request_hash="non-captain",
            now=AT,
        )

    service.submit_confirmation(
        match_id=match.id,
        user_id=team_one.user_id,
        round_number=1,
        outcome="TEAM_1",
        idempotency_key="captain-1",
        request_hash="captain-1",
        now=AT,
    )
    with pytest.raises(ConfirmationAlreadySubmitted):
        service.submit_confirmation(
            match_id=match.id,
            user_id=team_one.user_id,
            round_number=1,
            outcome="TEAM_2",
            idempotency_key="captain-2",
            request_hash="captain-2",
            now=AT,
        )

    assert service.counts_for(round_row) == {"TEAM_1": 0, "TEAM_2": 0, "DRAW": 0}
    assert len(service.captain_confirmations(round_row)) == 1


def test_captain_selection_uses_finalized_history_and_uuid(db_session: Session) -> None:
    match, users, participants, _ = build_match(
        db_session,
        checked_in=10,
        history={0: 2, 1: 1, 2: 2},
    )

    team_one = [item for item in participants if item.team == 1 and not item.is_substitute]
    expected = min(
        (item for item in team_one if item.user_id in {users[0], users[2]}),
        key=lambda item: str(item.user_id),
    )
    captain_team_one = next(item for item in team_one if item.is_captain)
    assert captain_team_one.id == expected.id

    team_two = [item for item in participants if item.team == 2]
    expected_two = min(team_two, key=lambda item: str(item.user_id))
    captain_team_two = next(item for item in team_two if item.is_captain)
    assert captain_team_two.id == expected_two.id
    assert match.state == "IN_PROGRESS"


def test_manual_lobby_has_no_captains(db_session: Session) -> None:
    _, _, participants, _ = build_match(db_session, checked_in=10, origin="manual")
    assert not any(item.is_captain for item in participants)


def test_evidence_is_private_limited_and_unique(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)
    submit(
        service,
        match.id,
        users,
        ["TEAM_1"] * 3 + ["TEAM_2"] * 4 + ["DRAW"] * 3,
    )
    close_round(db_session, first)
    dispute = service.latest_open_dispute(match.id)
    assert dispute is not None

    with pytest.raises(EvidenceEmpty):
        service.submit_evidence(
            match_id=match.id,
            dispute_id=dispute.id,
            user_id=users[0],
            text="   ",
            idempotency_key="empty",
            request_hash="empty",
            now=AT,
        )
    with pytest.raises(EvidenceTooLong):
        service.submit_evidence(
            match_id=match.id,
            dispute_id=dispute.id,
            user_id=users[0],
            text="x" * 2001,
            idempotency_key="long",
            request_hash="long",
            now=AT,
        )

    evidence = service.submit_evidence(
        match_id=match.id,
        dispute_id=dispute.id,
        user_id=users[0],
        text="Justificativa privada.",
        idempotency_key="one",
        request_hash="one",
        now=AT,
    )
    assert evidence.char_count == len("Justificativa privada.")
    assert (
        service.get_evidence(match_id=match.id, dispute_id=dispute.id, user_id=users[0]).text
        == "Justificativa privada."
    )

    with pytest.raises(EvidenceAlreadySubmitted):
        service.submit_evidence(
            match_id=match.id,
            dispute_id=dispute.id,
            user_id=users[0],
            text="outra",
            idempotency_key="two",
            request_hash="two",
            now=AT,
        )

    with pytest.raises(EvidenceNotFound):
        service.get_evidence(match_id=match.id, dispute_id=dispute.id, user_id=users[1])

    service.submit_evidence(
        match_id=match.id,
        dispute_id=dispute.id,
        user_id=users[1],
        text="Outra versão.",
        idempotency_key="three",
        request_hash="three",
        now=AT,
    )
    assert (
        service.get_evidence(match_id=match.id, dispute_id=dispute.id, user_id=users[1]).text
        == "Outra versão."
    )


def test_human_decision_finalizes_and_voids(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)
    submit(service, match.id, users[:4], ["TEAM_1"] * 4)
    close_round(db_session, first)

    decision = service.decide(
        match_id=match.id,
        decision="FINALIZE",
        outcome="TEAM_1",
        reason="Quórum insuficiente, mas relatos convergem",
        operator_id="op-1",
        now=AT,
    )
    db_session.refresh(match)
    assert decision.origin == "HUMAN"
    assert decision.operator_id == "op-1"
    assert match.state == "FINALIZED"
    assert match.final_result == "TEAM_1"
    review = db_session.get(MatchResultReview, decision.review_id)
    assert review is not None and review.status == "RESOLVED"
    dispute = db_session.scalar(select(MatchDispute).where(MatchDispute.match_id == match.id))
    assert dispute is not None and dispute.status == "CLOSED"
    with pytest.raises(ReviewNotFound):
        service.decide(
            match_id=match.id,
            decision="VOID",
            reason="duplicada",
            operator_id="op-1",
            now=AT,
        )

    void_match, void_users, _, _ = build_match(
        db_session,
        checked_in=10,
        start=START + timedelta(days=1),
        end=END + timedelta(days=1),
    )
    void_service = ResultsService(db_session)
    void_service.advance(now=END + timedelta(days=1))
    void_round = void_service.current_round(void_match.id)
    assert void_round is not None
    for index, user_id in enumerate(void_users[:4]):
        void_service.submit_report(
            match_id=void_match.id,
            user_id=user_id,
            round_number=1,
            outcome="TEAM_2",
            idempotency_key=f"void-{index}",
            request_hash=f"void-{index}",
            now=END + timedelta(days=1, minutes=2),
        )
    void_service.advance(now=ensure_utc(void_round.deadline) + timedelta(seconds=1))
    void_service.decide(
        match_id=void_match.id,
        decision="VOID",
        reason="Sem condições de apurar",
        operator_id="op-2",
        now=AT,
    )
    db_session.refresh(void_match)
    assert void_match.state == "VOIDED"
    assert void_match.final_result is None
    assert void_match.voided_reason == "Sem condições de apurar"


def test_decision_request_more_info_keeps_review_pending(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)
    submit(service, match.id, users[:4], ["TEAM_1"] * 4)
    close_round(db_session, first)

    service.decide(
        match_id=match.id,
        decision="REQUEST_MORE_INFO",
        reason="Aguardando relatos complementares",
        operator_id="op-1",
        now=AT,
    )
    db_session.refresh(match)
    assert match.state == "RESULT_PENDING"
    review = service.pending_review(match.id)
    assert review is not None
    assert review.status == "PENDING"


def test_decision_is_auditable(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, first = open_round(db_session, match.id)
    submit(service, match.id, users[:4], ["TEAM_1"] * 4)
    close_round(db_session, first)

    service.decide(
        match_id=match.id,
        decision="FINALIZE",
        outcome="TEAM_1",
        reason="Relatos suficientes",
        operator_id="op-audit",
        now=AT,
    )
    decisions = db_session.scalars(
        select(MatchResultDecision).where(MatchResultDecision.match_id == match.id)
    ).all()
    assert len(decisions) == 1
    assert decisions[0].reason == "Relatos suficientes"
    assert decisions[0].operator_id == "op-audit"
    assert decisions[0].origin == "HUMAN"
