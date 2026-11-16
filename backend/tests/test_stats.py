"""Estatísticas, passaporte e rede (Fase 14D.15)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.bookings.models import Booking
from app.modules.matches.models import Match, MatchParticipant
from app.modules.matchmaking.models import Lobby
from app.modules.venues.models import VenueSpace
from tests.helpers_results import build_match, make_format, make_token, make_user

MATCH_AT = datetime(2026, 11, 10, 22, 0, tzinfo=UTC)  # 19h em São Paulo


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def buy_pass(api: TestClient, token: str) -> None:
    created = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(token),
        json={"plan_code": "jogador"},
    )
    assert created.status_code == 201, created.text
    confirmed = api.post(
        f"/api/v1/me/pass/subscriptions/{created.json()['id']}/confirm",
        headers=bearer(token),
    )
    assert confirmed.status_code == 200, confirmed.text


def add_space(session: Session, name: str = "Arena Teste") -> VenueSpace:
    space = VenueSpace(
        organization_venue_id=uuid.uuid4(),
        name=name,
        is_covered=True,
    )
    session.add(space)
    session.flush()
    return space


def add_finished_match(
    session: Session,
    space: VenueSpace,
    *,
    when: datetime,
    user_id: uuid.UUID | None = None,
    result: str = "TEAM_1",
    team: int = 1,
) -> Match:
    _, sport_format = make_format(session)
    lobby = Lobby(
        format_id=sport_format.id,
        format_version=1,
        origin="matchmaking",
        mode="casual",
        status="completed",
        court_preference="ANY",
        scheduled_start_at=when,
        scheduled_end_at=when + timedelta(minutes=60),
        duration_minutes=60,
        center_lat=-23.55,
        center_lng=-46.63,
        radius_km=10,
        algorithm_version="level_v1",
    )
    session.add(lobby)
    session.flush()
    match = Match(
        lobby_id=lobby.id,
        state="FINALIZED",
        scheduled_start_at=when,
        scheduled_end_at=when + timedelta(minutes=60),
        confirmation_deadline=when - timedelta(hours=24),
        check_in_opens_at=when - timedelta(hours=1),
        check_in_deadline=when - timedelta(minutes=30),
        substitution_deadline=when - timedelta(minutes=15),
        final_result=result,
        finalized_at=when + timedelta(minutes=60),
    )
    session.add(match)
    session.flush()
    session.add(
        Booking(
            lobby_id=lobby.id,
            organization_id=uuid.uuid4(),
            organization_venue_id=space.organization_venue_id,
            venue_space_id=space.id,
            starts_at=when,
            ends_at=when + timedelta(minutes=60),
            price_cents=0,
            seats=10,
            policy_version="v1",
            cancellation_policy="standard",
        )
    )
    if user_id is not None:
        session.add(
            MatchParticipant(
                match_id=match.id,
                user_id=user_id,
                team=team,
                level="intermediate",
                status="checked_in",
            )
        )
    session.flush()
    return match


def test_essential_stats_are_free_and_do_not_expose_mmr(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    match, _users, participants, _ = build_match(db_session, checked_in=10)
    match.state = "FINALIZED"
    match.final_result = "TEAM_1"
    match.finalized_at = MATCH_AT
    db_session.flush()
    winner = next(row for row in participants if row.team == 1).user_id
    loser = next(row for row in participants if row.team == 2).user_id

    winner_token = make_token(db_session, winner)
    response = api.get("/api/v1/me/stats", headers=bearer(winner_token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert "rating" not in body and "mmr" not in body
    assert body["totals"]["matches"] == 1
    assert body["totals"]["wins"] == 1
    assert body["totals"]["losses"] == 0
    assert body["by_format"][0]["wins"] == 1

    loser_token = make_token(db_session, loser)
    loser_body = api.get("/api/v1/me/stats", headers=bearer(loser_token)).json()
    assert loser_body["totals"]["wins"] == 0
    assert loser_body["totals"]["losses"] == 1

    history = api.get("/api/v1/me/stats/courts", headers=bearer(loser_token))
    assert history.status_code == 403
    assert history.json()["detail"]["code"] == "pass_required"


def test_courts_and_passport_require_pass_and_show_aggregates(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    space = add_space(db_session)
    add_finished_match(db_session, space, when=MATCH_AT, user_id=user_id)
    buy_pass(api, token)

    courts = api.get("/api/v1/me/stats/courts", headers=bearer(token))
    assert courts.status_code == 200, courts.text
    body = courts.json()
    assert body["courts"][0]["name"] == "Arena Teste"
    assert body["courts"][0]["matches"] == 1
    assert body["courts"][0]["wins"] == 1

    passport = api.get("/api/v1/me/stats/passport", headers=bearer(token))
    assert passport.status_code == 200, passport.text
    assert passport.json()["courts"] == 1
    assert passport.json()["totals"]["matches"] == 1


def test_network_hides_cells_below_minimum_and_gates_bands(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    space = add_space(db_session)

    for _ in range(19):
        add_finished_match(db_session, space, when=MATCH_AT)
    hidden = api.get("/api/v1/me/network", headers=bearer(token))
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["venues"] == []
    assert hidden.json()["cells"] == []

    add_finished_match(db_session, space, when=MATCH_AT)
    visible = api.get("/api/v1/me/network", headers=bearer(token))
    body = visible.json()
    assert body["sample_size"] == 20
    assert body["min_sample"] == 20
    assert body["venues"][0]["name"] == "Arena Teste"
    assert body["venues"][0]["level"] == "média"
    assert body["cells"] == []
    assert body["has_pass"] is False
    assert body["peak_band"] == "noite"

    buy_pass(api, token)
    with_pass = api.get("/api/v1/me/network", headers=bearer(token)).json()
    assert with_pass["cells"]
    assert with_pass["cells"][0]["band"] == "noite"
    assert with_pass["updated_on"] == datetime.now(UTC).date().isoformat()
