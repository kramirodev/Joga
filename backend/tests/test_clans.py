"""Clãs: entrada, papéis, chat, denúncia e troféus (Fase 16)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.clans.models import ClanMember, ClanTrophyEvent
from app.modules.clans.service import (
    clan_ranking,
    create_clan,
    record_match_trophies,
    snapshot_season,
    trophy_total,
)
from app.modules.identity.clock import utcnow
from app.modules.season.service import active_season
from tests.helpers_results import build_match, make_token, make_user
from tests.test_results_service import AT, close_round, open_round, submit


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_player(session: Session) -> tuple[uuid.UUID, str]:
    user_id = make_user(session)
    return user_id, make_token(session, user_id)


def create_clan_api(api: TestClient, token: str, name: str = "Tijuca FC", tag: str = "TFC") -> dict:
    response = api.post(
        "/api/v1/clans",
        headers=bearer(token),
        json={"name": name, "tag": tag},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_clan_makes_the_creator_owner(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, token = make_player(db_session)

    clan = create_clan_api(api, token)
    assert clan["members"] == 1
    assert clan["max_members"] == 30
    assert clan["my_role"] == "owner"
    assert clan["join_policy"] == "approval"

    mine = api.get("/api/v1/me/clan", headers=bearer(token))
    assert mine.status_code == 200
    assert mine.json()["id"] == clan["id"]

    second = api.post(
        "/api/v1/clans",
        headers=bearer(token),
        json={"name": "Outro", "tag": "OUT"},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "already_in_clan"


def test_join_is_approved_by_an_admin(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    _, member_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)

    joined = api.post(
        f"/api/v1/clans/{clan['id']}/join",
        headers=bearer(member_token),
        json={"message": "quero entrar"},
    )
    assert joined.status_code == 200, joined.text
    assert joined.json()["status"] == "pending"

    requests = api.get(f"/api/v1/clans/{clan['id']}/requests", headers=bearer(owner_token))
    assert requests.status_code == 200
    request_id = requests.json()["requests"][0]["id"]

    decided = api.post(
        f"/api/v1/clans/{clan['id']}/requests/{request_id}/decide",
        headers=bearer(owner_token),
        json={"approve": True},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "approved"

    view = api.get(f"/api/v1/clans/{clan['id']}", headers=bearer(member_token))
    assert view.json()["members"] == 2
    assert view.json()["my_role"] == "member"

    members = api.get(f"/api/v1/clans/{clan['id']}/members", headers=bearer(member_token))
    assert len(members.json()["members"]) == 2


def test_leaving_starts_a_seven_day_cooldown(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    _, member_token = make_player(db_session)
    _, other_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    other = create_clan_api(api, other_token, name="Andaraí", tag="AND")

    joined = api.post(
        f"/api/v1/clans/{clan['id']}/join", headers=bearer(member_token), json={}
    ).json()
    api.post(
        f"/api/v1/clans/{clan['id']}/requests/{joined['request']['id']}/decide",
        headers=bearer(owner_token),
        json={"approve": True},
    )

    left = api.post(f"/api/v1/clans/{clan['id']}/leave", headers=bearer(member_token))
    assert left.status_code == 204, left.text

    blocked = api.post(f"/api/v1/clans/{other['id']}/join", headers=bearer(member_token), json={})
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "clan_cooldown"


def test_owner_must_transfer_before_leaving(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    member_id, member_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    joined = api.post(
        f"/api/v1/clans/{clan['id']}/join", headers=bearer(member_token), json={}
    ).json()
    api.post(
        f"/api/v1/clans/{clan['id']}/requests/{joined['request']['id']}/decide",
        headers=bearer(owner_token),
        json={"approve": True},
    )

    blocked = api.post(f"/api/v1/clans/{clan['id']}/leave", headers=bearer(owner_token))
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "transfer_ownership_first"

    transferred = api.post(
        f"/api/v1/clans/{clan['id']}/transfer",
        headers=bearer(owner_token),
        json={"user_id": str(member_id)},
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["role"] == "owner"

    promoted = api.post(
        f"/api/v1/clans/{clan['id']}/members/{owner_id}/role",
        headers=bearer(member_token),
        json={"role": "admin"},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "admin"

    left = api.post(f"/api/v1/clans/{clan['id']}/leave", headers=bearer(owner_token))
    assert left.status_code == 204


def test_chat_reports_hide_immediately_and_admin_can_restore(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    sender_id, sender_token = make_player(db_session)
    _, reporter_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)

    for token in (sender_token, reporter_token):
        joined = api.post(f"/api/v1/clans/{clan['id']}/join", headers=bearer(token), json={}).json()
        api.post(
            f"/api/v1/clans/{clan['id']}/requests/{joined['request']['id']}/decide",
            headers=bearer(owner_token),
            json={"approve": True},
        )

    message = api.post(
        f"/api/v1/clans/{clan['id']}/messages",
        headers=bearer(sender_token),
        json={"body": "mensagem ofensiva"},
    )
    assert message.status_code == 201, message.text
    message_id = message.json()["id"]
    assert message.json()["sender_id"] == str(sender_id)

    outsider_id, outsider_token = make_player(db_session)
    blocked = api.post(
        f"/api/v1/clans/{clan['id']}/messages",
        headers=bearer(outsider_token),
        json={"body": "oi"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "not_a_member"

    reported = api.post(
        f"/api/v1/clans/{clan['id']}/messages/{message_id}/report",
        headers=bearer(reporter_token),
        json={"reason": "ofensa"},
    )
    assert reported.status_code == 201, reported.text
    report_id = reported.json()["id"]

    visible = api.get(
        f"/api/v1/clans/{clan['id']}/messages", headers=bearer(reporter_token)
    ).json()["messages"]
    assert all(item["id"] != message_id for item in visible)

    admin_view = api.get(
        f"/api/v1/clans/{clan['id']}/messages", headers=bearer(owner_token)
    ).json()["messages"]
    hidden = next(item for item in admin_view if item["id"] == message_id)
    assert hidden["hidden"] is True

    reports = api.get(f"/api/v1/clans/{clan['id']}/reports", headers=bearer(owner_token))
    assert reports.status_code == 200
    assert reports.json()["reports"][0]["status"] == "OPEN"

    forbidden = api.get(f"/api/v1/clans/{clan['id']}/reports", headers=bearer(reporter_token))
    assert forbidden.status_code == 403

    restored = api.post(
        f"/api/v1/clans/{clan['id']}/reports/{report_id}/decide",
        headers=bearer(owner_token),
        json={"decision": "RESTORE"},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "RESTORED"

    visible_again = api.get(
        f"/api/v1/clans/{clan['id']}/messages", headers=bearer(reporter_token)
    ).json()["messages"]
    assert any(item["id"] == message_id for item in visible_again)


def test_trophies_are_idempotent_and_ranked_by_season(db_session: Session) -> None:
    owner_id = make_user(db_session)
    member_id = make_user(db_session)
    joined = utcnow() - timedelta(days=30)
    clan = create_clan(db_session, owner_id, name="Tijuca FC", tag="TFC", now=joined)
    db_session.add(
        ClanMember(
            clan_id=clan.id,
            user_id=member_id,
            role="member",
            status="active",
            joined_at=joined,
        )
    )
    db_session.flush()
    season = active_season(db_session, utcnow())
    match_id = uuid.uuid4()
    format_id = uuid.uuid4()

    applied = record_match_trophies(
        db_session,
        match_id=match_id,
        format_id=format_id,
        season_id=season.id,
        results={owner_id: "WIN", member_id: "LOSS"},
        now=utcnow(),
    )
    assert applied == 2
    assert trophy_total(db_session, clan.id, season_id=season.id) == 70
    assert trophy_total(db_session, clan.id, season_id=season.id, format_id=format_id) == 70

    again = record_match_trophies(
        db_session,
        match_id=match_id,
        format_id=format_id,
        season_id=season.id,
        results={owner_id: "WIN", member_id: "LOSS"},
        now=utcnow(),
    )
    assert again == 0
    assert db_session.query(ClanTrophyEvent).filter_by(clan_id=clan.id).count() == 2

    ranking = clan_ranking(db_session, season_id=season.id, format_id=format_id)
    assert ranking[0][0].id == clan.id
    assert ranking[0][1] == 70

    assert snapshot_season(db_session, season.id) == 1
    assert snapshot_season(db_session, season.id) == 0


def test_tenure_below_seven_days_does_not_earn_trophies(db_session: Session) -> None:
    owner_id = make_user(db_session)
    clan = create_clan(db_session, owner_id, name="Novo", tag="NOV")
    season = active_season(db_session, utcnow())

    applied = record_match_trophies(
        db_session,
        match_id=uuid.uuid4(),
        format_id=uuid.uuid4(),
        season_id=season.id,
        results={owner_id: "WIN"},
        now=utcnow(),
    )
    assert applied == 0
    assert trophy_total(db_session, clan.id, season_id=season.id) == 0


def test_finalized_match_credits_clan_trophies(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    joined = AT - timedelta(days=30)
    clan = create_clan(db_session, users[0], name="Tijuca FC", tag="TFC", now=joined)
    db_session.add(
        ClanMember(
            clan_id=clan.id,
            user_id=users[1],
            role="member",
            status="active",
            joined_at=joined,
        )
    )
    db_session.flush()

    service, round_row = open_round(db_session, match.id)
    submit(service, match.id, users, ["TEAM_1"] * len(users))
    close_round(db_session, round_row)

    season = active_season(db_session, AT)
    assert trophy_total(db_session, clan.id, season_id=season.id) == 100
