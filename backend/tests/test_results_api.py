"""Testes HTTP dos resultados, confirmações, relatos e evidências."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_TOKEN_HASH_SECRET, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import SessionService
from app.modules.matches.models import Match, MatchParticipant
from app.modules.ratelimit import service as ratelimit_service
from app.modules.results.models import MatchResultRound
from app.modules.results.service import ResultsService
from tests.helpers_results import build_match, make_user


@pytest.fixture
def api(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def make_token(session: Session, user_id: uuid.UUID) -> str:
    tokens = SessionService(
        session,
        DEFAULT_TOKEN_HASH_SECRET,
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user_id)
    session.commit()
    return tokens.access_token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def setup_open_round(
    session: Session,
    *,
    sport_slug: str = "futebol",
    team_size: int = 5,
) -> tuple[Match, list[uuid.UUID], list[MatchParticipant], MatchResultRound]:
    now = datetime.now(UTC)
    match, users, participants, _ = build_match(
        session,
        sport_slug=sport_slug,
        team_size=team_size,
        checked_in=team_size * 2,
        start=now - timedelta(hours=1),
        end=now - timedelta(minutes=1),
    )
    ResultsService(session).advance(now=now)
    round_row = ResultsService(session).current_round(match.id)
    assert round_row is not None
    assert round_row.status == "OPEN"
    session.commit()
    return match, users, participants, round_row


def post_report(
    api: TestClient,
    token: str,
    match_id: uuid.UUID,
    *,
    outcome: str = "TEAM_1",
    round_number: int = 1,
    key: str = "key-1",
) -> object:
    return api.post(
        f"/api/v1/matches/{match_id}/result-reports",
        headers={**bearer(token), "Idempotency-Key": key},
        json={"round": round_number, "outcome": outcome},
    )


def test_result_requires_authentication(api: TestClient) -> None:
    response = api.get(f"/api/v1/matches/{uuid.uuid4()}/result")
    assert response.status_code == 401


def test_non_participant_gets_not_found(api: TestClient, db_session: Session) -> None:
    match, _, _, _ = setup_open_round(db_session)
    outsider = make_user(db_session)
    db_session.commit()
    token = make_token(db_session, outsider)

    assert api.get(f"/api/v1/matches/{match.id}/result", headers=bearer(token)).status_code == 404
    assert post_report(api, token, match.id).status_code == 404


def test_participant_submits_and_reads_own_vote(api: TestClient, db_session: Session) -> None:
    match, users, _, _ = setup_open_round(db_session)
    token = make_token(db_session, users[0])

    first = post_report(api, token, match.id)
    assert first.status_code == 201
    body = first.json()
    assert body["outcome"] == "TEAM_1"
    assert body["effective"] is True

    detail = api.get(f"/api/v1/matches/{match.id}/result", headers=bearer(token))
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["round"] == 1
    assert payload["round_status"] == "OPEN"
    assert payload["my_vote"]["outcome"] == "TEAM_1"
    assert payload["valid_votes"] == 1
    assert payload["aggregate_visible"] is False
    assert payload["aggregate"] is None
    assert payload["can_vote"] is False

    reports = api.get(f"/api/v1/matches/{match.id}/result-reports?round=1", headers=bearer(token))
    assert reports.status_code == 200
    participant = next(
        item for item in _participants(db_session, match.id) if item.user_id == users[0]
    )
    assert reports.json()["reports"][0]["participant_id"] == str(participant.id)

    replay = post_report(api, token, match.id, key="key-1")
    assert replay.status_code == 201
    assert replay.json()["report_id"] == body["report_id"]

    conflict = post_report(api, token, match.id, outcome="TEAM_2", key="key-1")
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": {"code": "idempotency_conflict"}}

    duplicate = post_report(api, token, match.id, key="key-2")
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": {"code": "result_report_already_submitted"}}


def test_idempotency_key_is_required(api: TestClient, db_session: Session) -> None:
    match, users, _, _ = setup_open_round(db_session)
    token = make_token(db_session, users[0])

    response = api.post(
        f"/api/v1/matches/{match.id}/result-reports",
        headers=bearer(token),
        json={"round": 1, "outcome": "TEAM_1"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "missing_idempotency_key"}}


def test_invalid_outcome_returns_business_code(api: TestClient, db_session: Session) -> None:
    match, users, _, _ = setup_open_round(db_session)
    token = make_token(db_session, users[0])

    response = post_report(api, token, match.id, outcome="TEAM_3", key="invalid")
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "invalid_outcome"}}


def test_vote_after_deadline_is_rejected(api: TestClient, db_session: Session) -> None:
    match, users, _, round_row = setup_open_round(db_session)
    round_row.deadline = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    token = make_token(db_session, users[0])

    response = post_report(api, token, match.id)
    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "result_window_closed"}}


def test_draw_is_rejected_for_volleyball_via_api(api: TestClient, db_session: Session) -> None:
    match, users, _, _ = setup_open_round(db_session, sport_slug="volei", team_size=6)
    token = make_token(db_session, users[0])

    response = post_report(api, token, match.id, outcome="DRAW", key="draw")
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "draw_not_allowed"}}


def test_aggregate_is_hidden_until_round_closes(api: TestClient, db_session: Session) -> None:
    match, users, _, round_row = setup_open_round(db_session)
    service = ResultsService(db_session)
    for index, user_id in enumerate(users[:5]):
        service.submit_report(
            match_id=match.id,
            user_id=user_id,
            round_number=1,
            outcome="TEAM_1",
            idempotency_key=f"setup-{index}",
            request_hash=f"setup-{index}",
            now=datetime.now(UTC),
        )
    db_session.commit()
    token = make_token(db_session, users[0])

    while_open = api.get(f"/api/v1/matches/{match.id}/result", headers=bearer(token))
    assert while_open.status_code == 200
    assert while_open.json()["valid_votes"] == 5
    assert while_open.json()["aggregate_visible"] is False
    assert while_open.json()["aggregate"] is None

    service.advance(now=round_row.deadline + timedelta(seconds=1))
    db_session.commit()

    closed = api.get(f"/api/v1/matches/{match.id}/result", headers=bearer(token))
    payload = closed.json()
    assert payload["round_status"] == "CLOSED"
    assert payload["aggregate_visible"] is True
    assert payload["aggregate"]["counts"] == {"TEAM_1": 5, "TEAM_2": 0, "DRAW": 0}
    assert payload["aggregate"]["evaluated"] == "TEAM_1"
    assert payload["final_result"] == "TEAM_1"
    assert payload["state"] == "FINALIZED"


def test_captain_confirmation_endpoint(api: TestClient, db_session: Session) -> None:
    match, users, participants, round_row = setup_open_round(db_session)
    captain = next(item for item in participants if item.is_captain)
    non_captain = next(item for item in participants if not item.is_captain)
    captain_token = make_token(db_session, captain.user_id)
    other_token = make_token(db_session, non_captain.user_id)

    forbidden = api.post(
        f"/api/v1/matches/{match.id}/result-confirmations",
        headers={**bearer(other_token), "Idempotency-Key": "conf-other"},
        json={"round": 1, "outcome": "TEAM_1"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": {"code": "not_captain"}}

    created = api.post(
        f"/api/v1/matches/{match.id}/result-confirmations",
        headers={**bearer(captain_token), "Idempotency-Key": "conf-1"},
        json={"round": 1, "outcome": "TEAM_1"},
    )
    assert created.status_code == 201

    replay = api.post(
        f"/api/v1/matches/{match.id}/result-confirmations",
        headers={**bearer(captain_token), "Idempotency-Key": "conf-1"},
        json={"round": 1, "outcome": "TEAM_1"},
    )
    assert replay.status_code == 201
    assert replay.json()["confirmation_id"] == created.json()["confirmation_id"]

    duplicate = api.post(
        f"/api/v1/matches/{match.id}/result-confirmations",
        headers={**bearer(captain_token), "Idempotency-Key": "conf-2"},
        json={"round": 1, "outcome": "TEAM_2"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": {"code": "captain_confirmation_already_submitted"}}

    ResultsService(db_session).advance(now=round_row.deadline + timedelta(seconds=1))
    db_session.commit()
    detail = api.get(f"/api/v1/matches/{match.id}/result", headers=bearer(captain_token)).json()
    assert detail["captain_confirmations_visible"] is True
    assert len(detail["captain_confirmations"]) == 1
    assert detail["captain_confirmations"][0]["outcome"] == "TEAM_1"


def test_evidence_is_private_and_limited(api: TestClient, db_session: Session) -> None:
    match, users, _, round_row = setup_open_round(db_session)
    service = ResultsService(db_session)
    now = datetime.now(UTC)
    outcomes = ["TEAM_1"] * 3 + ["TEAM_2"] * 4 + ["DRAW"] * 3
    for index, (user_id, outcome) in enumerate(zip(users, outcomes, strict=True)):
        service.submit_report(
            match_id=match.id,
            user_id=user_id,
            round_number=1,
            outcome=outcome,
            idempotency_key=f"dispute-{index}",
            request_hash=f"dispute-{index}",
            now=now,
        )
    service.advance(now=round_row.deadline + timedelta(seconds=1))
    db_session.commit()
    dispute = service.latest_open_dispute(match.id)
    assert dispute is not None
    token_one = make_token(db_session, users[0])
    token_two = make_token(db_session, users[1])

    empty = api.post(
        f"/api/v1/matches/{match.id}/disputes/{dispute.id}/evidence",
        headers={**bearer(token_two), "Idempotency-Key": "ev-empty"},
        json={"text": "   "},
    )
    assert empty.status_code == 422
    assert empty.json() == {"detail": {"code": "evidence_empty"}}

    too_long = api.post(
        f"/api/v1/matches/{match.id}/disputes/{dispute.id}/evidence",
        headers={**bearer(token_two), "Idempotency-Key": "ev-long"},
        json={"text": "x" * 2001},
    )
    assert too_long.status_code == 422
    assert too_long.json() == {"detail": {"code": "evidence_too_long"}}

    created = api.post(
        f"/api/v1/matches/{match.id}/disputes/{dispute.id}/evidence",
        headers={**bearer(token_one), "Idempotency-Key": "ev-1"},
        json={"text": "Justificativa privada."},
    )
    assert created.status_code == 201
    assert created.json()["char_count"] == len("Justificativa privada.")

    replay = api.post(
        f"/api/v1/matches/{match.id}/disputes/{dispute.id}/evidence",
        headers={**bearer(token_one), "Idempotency-Key": "ev-1"},
        json={"text": "Justificativa privada."},
    )
    assert replay.status_code == 201
    assert replay.json()["evidence_id"] == created.json()["evidence_id"]

    mine = api.get(
        f"/api/v1/matches/{match.id}/disputes/{dispute.id}/evidence/me",
        headers=bearer(token_one),
    )
    assert mine.status_code == 200
    assert mine.json()["text"] == "Justificativa privada."

    other = api.get(
        f"/api/v1/matches/{match.id}/disputes/{dispute.id}/evidence/me",
        headers=bearer(token_two),
    )
    assert other.status_code == 404
    assert other.json() == {"detail": {"code": "evidence_not_found"}}

    duplicate = api.post(
        f"/api/v1/matches/{match.id}/disputes/{dispute.id}/evidence",
        headers={**bearer(token_one), "Idempotency-Key": "ev-2"},
        json={"text": "Outra justificativa."},
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": {"code": "evidence_already_submitted"}}


def test_second_round_accepts_multiple_submissions(api: TestClient, db_session: Session) -> None:
    match, users, _, first = setup_open_round(db_session)
    service = ResultsService(db_session)
    now = datetime.now(UTC)
    vote_now = now - timedelta(seconds=30)
    for index, outcome in enumerate(["TEAM_1"] * 5 + ["TEAM_2"] * 5):
        service.submit_report(
            match_id=match.id,
            user_id=users[index],
            round_number=1,
            outcome=outcome,
            idempotency_key=f"first-{index}",
            request_hash=f"first-{index}",
            now=vote_now,
        )
    first.deadline = now - timedelta(seconds=1)
    service.advance(now=now)
    db_session.commit()
    token = make_token(db_session, users[0])

    first_vote = post_report(api, token, match.id, outcome="TEAM_1", round_number=2, key="second-a")
    second_vote = post_report(
        api, token, match.id, outcome="TEAM_2", round_number=2, key="second-b"
    )
    assert first_vote.status_code == 201
    assert second_vote.status_code == 201

    detail = api.get(f"/api/v1/matches/{match.id}/result", headers=bearer(token)).json()
    assert detail["round"] == 2
    assert detail["my_vote"]["outcome"] == "TEAM_2"
    assert detail["valid_votes"] == 1
    assert detail["aggregate_visible"] is False

    reports = api.get(
        f"/api/v1/matches/{match.id}/result-reports?round=2", headers=bearer(token)
    ).json()
    assert len(reports["reports"]) == 1
    assert reports["reports"][0]["outcome"] == "TEAM_2"


def _participants(session: Session, match_id: uuid.UUID) -> list[MatchParticipant]:
    return list(session.query(MatchParticipant).filter(MatchParticipant.match_id == match_id).all())


def test_rate_limit_returns_429_with_retry_after(
    api: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    match, users, _, _ = setup_open_round(db_session)
    token = make_token(db_session, users[0])

    settings = get_settings()
    monkeypatch.setattr(settings, "results_rate_limit_per_minute", 1)
    fixed = datetime.now(UTC)
    monkeypatch.setattr(ratelimit_service, "utcnow", lambda: fixed)

    first = post_report(api, token, match.id, key="rate-limit-1")
    assert first.status_code == 201

    second = post_report(api, token, match.id, key="rate-limit-2")
    assert second.status_code == 429
    assert second.json() == {"detail": {"code": "rate_limited"}}
    retry_after = int(second.headers["Retry-After"])
    assert 1 <= retry_after <= 60


def test_invalid_attempt_consumes_rate_limit(
    api: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    match, users, _, _ = setup_open_round(db_session)
    token = make_token(db_session, users[0])

    settings = get_settings()
    monkeypatch.setattr(settings, "results_rate_limit_per_minute", 1)
    monkeypatch.setattr(ratelimit_service, "utcnow", lambda: datetime.now(UTC))

    invalid = post_report(api, token, match.id, outcome="TEAM_3", key="invalid-attempt")
    assert invalid.status_code == 422
    assert invalid.json() == {"detail": {"code": "invalid_outcome"}}

    blocked = post_report(api, token, match.id, key="valid-after-invalid")
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": {"code": "rate_limited"}}
