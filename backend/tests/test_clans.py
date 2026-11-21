"""Clãs: entrada, papéis, chat, denúncia e troféus (Fase 16)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.clans.models import Clan, ClanInvite, ClanMember, ClanTrophyEvent
from app.modules.clans.service import (
    clan_ranking,
    create_clan,
    record_match_trophies,
    snapshot_season,
    trophy_total,
)
from app.modules.identity.clock import utcnow
from app.modules.identity.models import AuditLog
from app.modules.notifications.models import Notification
from app.modules.season.service import active_season
from app.modules.social.models import Friendship, UserBlock
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
    assert clan["tag"] == "#TFC"
    assert clan["members"] == 1
    assert clan["max_members"] == 30
    assert clan["my_role"] == "owner"
    assert clan["is_member"] is True
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


def test_tag_is_canonical_with_hash(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)

    for raw, expected in (("6666", "#6666"), (" #abcd ", "#ABCD"), ("##tfc", "#TFC")):
        _, token = make_player(db_session)
        clan = create_clan_api(api, token, name=f"Clã {expected}", tag=raw)
        assert clan["tag"] == expected


def test_tag_rejects_invalid_core(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, token = make_player(db_session)

    for index, raw in enumerate(("A", "ABCDEFGH", "A-B", "A B", "ÁBC")):
        rejected = api.post(
            "/api/v1/clans",
            headers=bearer(token),
            json={"name": f"Clã Inválido {index}", "tag": raw},
        )
        assert rejected.status_code == 409, (raw, rejected.text)
        assert rejected.json()["detail"]["code"] == "tag_invalid"


def test_tag_collision_after_normalization(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, first_token = make_player(db_session)
    _, second_token = make_player(db_session)
    create_clan_api(api, first_token, name="Primeiro", tag="TAG1")

    rejected = api.post(
        "/api/v1/clans",
        headers=bearer(second_token),
        json={"name": "Segundo", "tag": "#tag1"},
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "tag_taken"


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


def test_list_marks_own_clan_and_filters_open_and_slots(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    _, other_token = make_player(db_session)
    mine = create_clan_api(api, owner_token, name="Tijuca FC", tag="TFC")
    other = create_clan_api(api, other_token, name="Andaraí", tag="AND")
    other_clan = db_session.get(Clan, uuid.UUID(other["id"]))
    assert other_clan is not None
    other_clan.join_policy = "open"
    db_session.commit()

    listed = api.get("/api/v1/clans", headers=bearer(owner_token)).json()["clans"]
    by_id = {item["id"]: item for item in listed}
    assert by_id[mine["id"]]["my_role"] == "owner"
    assert by_id[mine["id"]]["is_member"] is True
    assert by_id[other["id"]]["my_role"] is None
    assert by_id[other["id"]]["is_member"] is False

    already_member = api.post(
        f"/api/v1/clans/{mine['id']}/join", headers=bearer(owner_token), json={}
    )
    assert already_member.status_code == 409, already_member.text
    assert already_member.json()["detail"]["code"] == "already_member"

    open_clans = api.get(
        "/api/v1/clans", headers=bearer(owner_token), params={"open": "true"}
    ).json()["clans"]
    assert [item["id"] for item in open_clans] == [other["id"]]
    closed_clans = api.get(
        "/api/v1/clans", headers=bearer(owner_token), params={"open": "false"}
    ).json()["clans"]
    assert [item["id"] for item in closed_clans] == [mine["id"]]

    for term in ("TFC", "#TFC"):
        found = api.get("/api/v1/clans", headers=bearer(owner_token), params={"q": term}).json()[
            "clans"
        ]
        assert [item["id"] for item in found] == [mine["id"]]

    for _ in range(29):
        db_session.add(
            ClanMember(
                clan_id=uuid.UUID(mine["id"]),
                user_id=make_user(db_session, available=False),
                role="member",
                status="active",
                joined_at=utcnow(),
            )
        )
    db_session.commit()

    full = api.get(
        "/api/v1/clans", headers=bearer(owner_token), params={"has_slots": "false"}
    ).json()["clans"]
    assert [item["id"] for item in full] == [mine["id"]]
    assert full[0]["members"] == 30
    with_slots = api.get(
        "/api/v1/clans", headers=bearer(owner_token), params={"has_slots": "true"}
    ).json()["clans"]
    assert [item["id"] for item in with_slots] == [other["id"]]


def test_member_count_excludes_pending_requests_and_left_members(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    _, active_token = make_player(db_session)
    _, pending_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)

    for token in (active_token, pending_token):
        joined = api.post(f"/api/v1/clans/{clan['id']}/join", headers=bearer(token), json={}).json()
        if token == active_token:
            approved = api.post(
                f"/api/v1/clans/{clan['id']}/requests/{joined['request']['id']}/decide",
                headers=bearer(owner_token),
                json={"approve": True},
            )
            assert approved.status_code == 200, approved.text

    view = api.get(f"/api/v1/clans/{clan['id']}", headers=bearer(owner_token)).json()
    assert view["members"] == 2

    left = api.post(f"/api/v1/clans/{clan['id']}/leave", headers=bearer(active_token))
    assert left.status_code == 204, left.text

    after = api.get(f"/api/v1/clans/{clan['id']}", headers=bearer(owner_token)).json()
    assert after["members"] == 1
    requests = api.get(f"/api/v1/clans/{clan['id']}/requests", headers=bearer(owner_token)).json()[
        "requests"
    ]
    assert [item["status"] for item in requests] == ["pending"]


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


def _join_approved(api: TestClient, clan_id: str, owner_token: str, token: str) -> None:
    joined = api.post(f"/api/v1/clans/{clan_id}/join", headers=bearer(token), json={}).json()
    decided = api.post(
        f"/api/v1/clans/{clan_id}/requests/{joined['request']['id']}/decide",
        headers=bearer(owner_token),
        json={"approve": True},
    )
    assert decided.status_code == 200, decided.text


def test_transfer_promotes_target_demotes_owner_and_audits(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    member_id, member_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    _join_approved(api, clan["id"], owner_token, member_token)

    transferred = api.post(
        f"/api/v1/clans/{clan['id']}/transfer",
        headers=bearer(owner_token),
        json={"user_id": str(member_id)},
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["role"] == "owner"

    members = api.get(f"/api/v1/clans/{clan['id']}/members", headers=bearer(member_token)).json()[
        "members"
    ]
    roles = {item["user_id"]: item["role"] for item in members}
    assert roles[str(owner_id)] == "member"
    assert roles[str(member_id)] == "owner"

    old_owner_view = api.get(f"/api/v1/clans/{clan['id']}", headers=bearer(owner_token)).json()
    assert old_owner_view["my_role"] == "member"
    assert old_owner_view["is_member"] is True

    audit = db_session.query(AuditLog).filter_by(action="clan.ownership_transferred").one()
    assert audit.actor_user_id == owner_id
    assert audit.resource_id == clan["id"]


def test_transfer_rejects_target_outside_the_clan(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    outsider_id, _ = make_player(db_session)
    clan = create_clan_api(api, owner_token)

    rejected = api.post(
        f"/api/v1/clans/{clan['id']}/transfer",
        headers=bearer(owner_token),
        json={"user_id": str(outsider_id)},
    )
    assert rejected.status_code == 404, rejected.text
    assert rejected.json()["detail"]["code"] == "not_found"


def test_transfer_requires_the_current_owner(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    _, member_token = make_player(db_session)
    third_id, _ = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    _join_approved(api, clan["id"], owner_token, member_token)

    rejected = api.post(
        f"/api/v1/clans/{clan['id']}/transfer",
        headers=bearer(member_token),
        json={"user_id": str(third_id)},
    )
    assert rejected.status_code == 403, rejected.text
    assert rejected.json()["detail"]["code"] == "owner_required"


def test_transfer_to_self_is_rejected(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)

    rejected = api.post(
        f"/api/v1/clans/{clan['id']}/transfer",
        headers=bearer(owner_token),
        json={"user_id": str(owner_id)},
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "already_owner"


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


# Edição de clã -----------------------------------------------------------


def make_friends(session: Session, first: uuid.UUID, second: uuid.UUID) -> None:
    low, high = (first, second) if str(first) < str(second) else (second, first)
    session.add(
        Friendship(
            user_low_id=low,
            user_high_id=high,
            requested_by=first,
            status="ACCEPTED",
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    )
    session.commit()


def block_user(session: Session, blocker: uuid.UUID, blocked: uuid.UUID) -> None:
    session.add(UserBlock(blocker_id=blocker, blocked_id=blocked, created_at=utcnow()))
    session.commit()


def promote_admin(api: TestClient, clan_id: str, owner_token: str, user_id: uuid.UUID) -> None:
    promoted = api.post(
        f"/api/v1/clans/{clan_id}/members/{user_id}/role",
        headers=bearer(owner_token),
        json={"role": "admin"},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "admin"


def test_owner_edits_name_description_and_policy_with_audit(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)

    edited = api.patch(
        f"/api/v1/clans/{clan['id']}",
        headers=bearer(owner_token),
        json={
            "name": "Tijuca United",
            "description": "Treino as terças",
            "join_policy": "open",
        },
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["name"] == "Tijuca United"
    assert body["description"] == "Treino as terças"
    assert body["join_policy"] == "open"
    assert body["tag"] == "#TFC"
    assert body["my_role"] == "owner"

    audit = db_session.query(AuditLog).filter_by(action="clan.updated").one()
    assert audit.actor_user_id == owner_id
    assert audit.resource_id == clan["id"]
    assert audit.details["changes"] == {
        "name": {"from": "Tijuca FC", "to": "Tijuca United"},
        "description": {"from": None, "to": "Treino as terças"},
        "join_policy": {"from": "approval", "to": "open"},
    }

    cleared = api.patch(
        f"/api/v1/clans/{clan['id']}",
        headers=bearer(owner_token),
        json={"description": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["description"] is None
    assert db_session.query(AuditLog).filter_by(action="clan.updated").count() == 2

    unchanged = api.patch(
        f"/api/v1/clans/{clan['id']}",
        headers=bearer(owner_token),
        json={"join_policy": "open"},
    )
    assert unchanged.status_code == 200, unchanged.text
    assert db_session.query(AuditLog).filter_by(action="clan.updated").count() == 2


def test_admin_edits_but_common_member_cannot(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    admin_id, admin_token = make_player(db_session)
    _, member_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    _join_approved(api, clan["id"], owner_token, admin_token)
    _join_approved(api, clan["id"], owner_token, member_token)
    promote_admin(api, clan["id"], owner_token, admin_id)

    admin_edit = api.patch(
        f"/api/v1/clans/{clan['id']}",
        headers=bearer(admin_token),
        json={"description": "descrição do admin"},
    )
    assert admin_edit.status_code == 200, admin_edit.text
    assert admin_edit.json()["description"] == "descrição do admin"

    forbidden = api.patch(
        f"/api/v1/clans/{clan['id']}",
        headers=bearer(member_token),
        json={"description": "não pode"},
    )
    assert forbidden.status_code == 403, forbidden.text
    assert forbidden.json()["detail"]["code"] == "admin_required"


def test_tag_cannot_be_changed(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)

    rejected = api.patch(
        f"/api/v1/clans/{clan['id']}",
        headers=bearer(owner_token),
        json={"tag": "#NOVA"},
    )
    assert rejected.status_code == 422, rejected.text
    stored = db_session.get(Clan, uuid.UUID(clan["id"]))
    assert stored is not None
    assert stored.tag == "#TFC"

    still = api.get(f"/api/v1/clans/{clan['id']}", headers=bearer(owner_token))
    assert still.json()["tag"] == "#TFC"


def test_duplicate_name_is_conflict(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, first_token = make_player(db_session)
    _, second_token = make_player(db_session)
    create_clan_api(api, first_token, name="Tijuca FC", tag="TFC")
    other = create_clan_api(api, second_token, name="Andaraí", tag="AND")

    rejected = api.patch(
        f"/api/v1/clans/{other['id']}",
        headers=bearer(second_token),
        json={"name": "Tijuca FC"},
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "name_taken"


def test_invalid_fields_are_rejected(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)

    long_description = api.patch(
        f"/api/v1/clans/{clan['id']}",
        headers=bearer(owner_token),
        json={"description": "x" * 281},
    )
    assert long_description.status_code == 422, long_description.text

    invalid_policy = api.patch(
        f"/api/v1/clans/{clan['id']}",
        headers=bearer(owner_token),
        json={"join_policy": "aberto"},
    )
    assert invalid_policy.status_code == 422, invalid_policy.text

    short_name = api.patch(
        f"/api/v1/clans/{clan['id']}",
        headers=bearer(owner_token),
        json={"name": "ab"},
    )
    assert short_name.status_code == 422, short_name.text


# Convites de clã ---------------------------------------------------------


def invite_api(
    api: TestClient,
    clan_id: str,
    token: str,
    invitee_id: uuid.UUID,
) -> object:
    return api.post(
        f"/api/v1/clans/{clan_id}/invites",
        headers=bearer(token),
        json={"user_id": str(invitee_id)},
    )


def test_invite_friend_lists_and_notifies(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    friend_id, friend_token = make_player(db_session)
    make_friends(db_session, owner_id, friend_id)
    clan = create_clan_api(api, owner_token)

    created = invite_api(api, clan["id"], owner_token, friend_id)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "pending"
    assert body["clan_id"] == clan["id"]
    assert body["clan_name"] == "Tijuca FC"
    assert body["clan_tag"] == "#TFC"
    assert body["inviter_id"] == str(owner_id)

    listed = api.get("/api/v1/me/clan-invites", headers=bearer(friend_token))
    assert listed.status_code == 200, listed.text
    invites = listed.json()["invites"]
    assert [item["id"] for item in invites] == [body["id"]]
    assert invites[0]["clan_name"] == "Tijuca FC"

    notification = (
        db_session.query(Notification).filter_by(user_id=friend_id, kind="clan_invite").one()
    )
    assert notification.data["clan_id"] == clan["id"]
    assert notification.data["invite_id"] == body["id"]


def test_invite_requires_friendship_and_rejects_block(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    stranger_id, _ = make_player(db_session)
    friend_id, _ = make_player(db_session)
    clan = create_clan_api(api, owner_token)

    not_friend = invite_api(api, clan["id"], owner_token, stranger_id)
    assert not_friend.status_code == 403, not_friend.text
    assert not_friend.json()["detail"]["code"] == "not_friends"

    make_friends(db_session, owner_id, friend_id)
    block_user(db_session, owner_id, friend_id)
    blocked = invite_api(api, clan["id"], owner_token, friend_id)
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["detail"]["code"] == "blocked"


def test_invite_rejects_full_clan_and_duplicates(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    friend_id, _ = make_player(db_session)
    make_friends(db_session, owner_id, friend_id)
    clan = create_clan_api(api, owner_token)

    first = invite_api(api, clan["id"], owner_token, friend_id)
    assert first.status_code == 201, first.text

    duplicate = invite_api(api, clan["id"], owner_token, friend_id)
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["detail"]["code"] == "already_invited"

    db_session.query(ClanInvite).filter_by(id=uuid.UUID(first.json()["id"])).delete()
    for _ in range(29):
        db_session.add(
            ClanMember(
                clan_id=uuid.UUID(clan["id"]),
                user_id=make_user(db_session, available=False),
                role="member",
                status="active",
                joined_at=utcnow(),
            )
        )
    db_session.commit()

    roomless = invite_api(api, clan["id"], owner_token, friend_id)
    assert roomless.status_code == 409, roomless.text
    assert roomless.json()["detail"]["code"] == "clan_full"


def test_accept_invite_makes_active_member_and_audits(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    friend_id, friend_token = make_player(db_session)
    make_friends(db_session, owner_id, friend_id)
    clan = create_clan_api(api, owner_token)
    invite = invite_api(api, clan["id"], owner_token, friend_id).json()

    accepted = api.post(
        f"/api/v1/clans/invites/{invite['id']}/accept", headers=bearer(friend_token)
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["id"] == clan["id"]
    assert body["members"] == 2
    assert body["my_role"] == "member"
    assert body["is_member"] is True

    stored = db_session.get(ClanInvite, uuid.UUID(invite["id"]))
    assert stored is not None
    assert stored.status == "accepted"
    assert stored.answered_at is not None

    audit = db_session.query(AuditLog).filter_by(action="clan.invite_accepted").one()
    assert audit.actor_user_id == friend_id
    assert audit.details["invite_id"] == invite["id"]


def test_accept_invite_with_active_clan_is_conflict(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    friend_id, friend_token = make_player(db_session)
    make_friends(db_session, owner_id, friend_id)
    clan = create_clan_api(api, owner_token)
    invite = invite_api(api, clan["id"], owner_token, friend_id).json()
    create_clan_api(api, friend_token, name="Clã do Amigo", tag="AMG")

    rejected = api.post(
        f"/api/v1/clans/invites/{invite['id']}/accept", headers=bearer(friend_token)
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "already_in_clan"


def test_expired_invite_cannot_be_accepted(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    friend_id, friend_token = make_player(db_session)
    make_friends(db_session, owner_id, friend_id)
    clan = create_clan_api(api, owner_token)
    invite = invite_api(api, clan["id"], owner_token, friend_id).json()

    stored = db_session.get(ClanInvite, uuid.UUID(invite["id"]))
    assert stored is not None
    stored.expires_at = utcnow() - timedelta(minutes=1)
    db_session.commit()

    rejected = api.post(
        f"/api/v1/clans/invites/{invite['id']}/accept", headers=bearer(friend_token)
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "invite_expired"

    listed = api.get("/api/v1/me/clan-invites", headers=bearer(friend_token)).json()["invites"]
    assert listed == []
    db_session.refresh(stored)
    assert stored.status == "expired"


def test_decline_own_invite_but_not_someone_elses(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    friend_id, friend_token = make_player(db_session)
    stranger_id, stranger_token = make_player(db_session)
    make_friends(db_session, owner_id, friend_id)
    clan = create_clan_api(api, owner_token)
    invite = invite_api(api, clan["id"], owner_token, friend_id).json()

    foreign = api.post(
        f"/api/v1/clans/invites/{invite['id']}/decline", headers=bearer(stranger_token)
    )
    assert foreign.status_code == 404, foreign.text

    declined = api.post(
        f"/api/v1/clans/invites/{invite['id']}/decline", headers=bearer(friend_token)
    )
    assert declined.status_code == 200, declined.text
    assert declined.json()["status"] == "declined"
    assert declined.json()["answered_at"] is not None

    again = api.post(f"/api/v1/clans/invites/{invite['id']}/accept", headers=bearer(friend_token))
    assert again.status_code == 409, again.text
    assert again.json()["detail"]["code"] == "invite_not_pending"


def test_admin_cancels_pending_invite_but_member_cannot(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    admin_id, admin_token = make_player(db_session)
    friend_id, friend_token = make_player(db_session)
    _, member_token = make_player(db_session)
    make_friends(db_session, owner_id, friend_id)
    clan = create_clan_api(api, owner_token)
    _join_approved(api, clan["id"], owner_token, admin_token)
    _join_approved(api, clan["id"], owner_token, member_token)
    promote_admin(api, clan["id"], owner_token, admin_id)
    invite = invite_api(api, clan["id"], owner_token, friend_id).json()

    forbidden = api.delete(
        f"/api/v1/clans/{clan['id']}/invites/{invite['id']}", headers=bearer(member_token)
    )
    assert forbidden.status_code == 403, forbidden.text
    assert forbidden.json()["detail"]["code"] == "admin_required"

    cancelled = api.delete(
        f"/api/v1/clans/{clan['id']}/invites/{invite['id']}", headers=bearer(admin_token)
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "expired"

    listed = api.get("/api/v1/me/clan-invites", headers=bearer(friend_token)).json()["invites"]
    assert listed == []

    audit = db_session.query(AuditLog).filter_by(action="clan.invite_cancelled").one()
    assert audit.actor_user_id == admin_id
    assert audit.details["invite_id"] == invite["id"]

    after = api.post(f"/api/v1/clans/invites/{invite['id']}/accept", headers=bearer(friend_token))
    assert after.status_code == 409, after.text
    assert after.json()["detail"]["code"] == "invite_expired"


def test_invitee_only_sees_own_invites(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    first_id, first_token = make_player(db_session)
    second_id, second_token = make_player(db_session)
    third_id, third_token = make_player(db_session)
    make_friends(db_session, owner_id, first_id)
    make_friends(db_session, owner_id, second_id)
    clan = create_clan_api(api, owner_token)
    first_invite = invite_api(api, clan["id"], owner_token, first_id).json()
    invite_api(api, clan["id"], owner_token, second_id)

    first_list = api.get("/api/v1/me/clan-invites", headers=bearer(first_token)).json()["invites"]
    assert [item["id"] for item in first_list] == [first_invite["id"]]

    third_list = api.get("/api/v1/me/clan-invites", headers=bearer(third_token)).json()["invites"]
    assert third_list == []

    foreign_accept = api.post(
        f"/api/v1/clans/invites/{first_invite['id']}/accept", headers=bearer(third_token)
    )
    assert foreign_accept.status_code == 404, foreign_accept.text
