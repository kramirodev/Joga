"""Clãs: entrada, papéis, chat, denúncia e troféus (Fase 16)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.text import normalize_display_name
from app.infrastructure.database.dependency import get_session
from app.modules.clans import service as clans_service
from app.modules.clans.models import (
    Clan,
    ClanInvite,
    ClanJoinRequest,
    ClanMember,
    ClanTrophyEvent,
)
from app.modules.clans.service import (
    clan_ranking,
    create_clan,
    record_match_trophies,
    snapshot_season,
    trophy_total,
)
from app.modules.identity.clock import utcnow
from app.modules.identity.models import AuditLog, User
from app.modules.identity.tags import tag_from_uuid
from app.modules.notifications.models import Notification
from app.modules.profile.models import UserProfile
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
    owner_id, owner_token = make_player(db_session)
    member_id, member_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)

    joined = api.post(
        f"/api/v1/clans/{clan['id']}/join",
        headers=bearer(member_token),
        json={"message": "quero entrar"},
    )
    assert joined.status_code == 200, joined.text
    assert joined.json()["status"] == "pending"
    assert joined.json()["request"]["tag"] == db_session.get(User, member_id).tag

    requests = api.get(f"/api/v1/clans/{clan['id']}/requests", headers=bearer(owner_token))
    assert requests.status_code == 200
    request_id = requests.json()["requests"][0]["id"]
    assert requests.json()["requests"][0]["tag"] == db_session.get(User, member_id).tag

    decided = api.post(
        f"/api/v1/clans/{clan['id']}/requests/{request_id}/decide",
        headers=bearer(owner_token),
        json={"approve": True},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "approved"
    assert decided.json()["tag"] == db_session.get(User, member_id).tag

    view = api.get(f"/api/v1/clans/{clan['id']}", headers=bearer(member_token))
    assert view.json()["members"] == 2
    assert view.json()["my_role"] == "member"

    members = api.get(f"/api/v1/clans/{clan['id']}/members", headers=bearer(member_token))
    assert len(members.json()["members"]) == 2
    tags = {item["user_id"]: item["tag"] for item in members.json()["members"]}
    assert tags == {
        str(owner_id): db_session.get(User, owner_id).tag,
        str(member_id): db_session.get(User, member_id).tag,
    }


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
    assert body["inviter_tag"] == db_session.get(User, owner_id).tag
    assert body["invitee_id"] == str(friend_id)
    assert body["invitee_tag"] == db_session.get(User, friend_id).tag
    assert body["invitee_display_name"] is None

    listed = api.get("/api/v1/me/clan-invites", headers=bearer(friend_token))
    assert listed.status_code == 200, listed.text
    invites = listed.json()["invites"]
    assert [item["id"] for item in invites] == [body["id"]]
    assert invites[0]["clan_name"] == "Tijuca FC"
    assert invites[0]["inviter_tag"] == db_session.get(User, owner_id).tag
    assert invites[0]["invitee_id"] == str(friend_id)
    assert invites[0]["invitee_tag"] == body["invitee_tag"]

    notification = (
        db_session.query(Notification).filter_by(user_id=friend_id, kind="clan_invite").one()
    )
    assert notification.data == {
        "invite_id": body["id"],
        "clan_id": clan["id"],
        "clan_name": "Tijuca FC",
        "clan_tag": "#TFC",
        "inviter_id": str(owner_id),
    }


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


# Pedidos de entrada: ciclo completo --------------------------------------


def join_api(api: TestClient, clan_id: str, token: str, message: str | None = None) -> object:
    payload = {} if message is None else {"message": message}
    return api.post(f"/api/v1/clans/{clan_id}/join", headers=bearer(token), json=payload)


def test_repeated_join_returns_same_request_without_duplicate_notification(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    requester_id, requester_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)

    first = join_api(api, clan["id"], requester_token, "quero entrar")
    assert first.status_code == 200, first.text
    request_id = first.json()["request"]["id"]

    again = join_api(api, clan["id"], requester_token, "texto novo")
    assert again.status_code == 200, again.text
    assert again.json()["request"]["id"] == request_id
    # O replay não sobrescreve a mensagem original.
    assert again.json()["request"]["message"] == "quero entrar"

    stored = (
        db_session.query(ClanJoinRequest)
        .filter_by(clan_id=uuid.UUID(clan["id"]), user_id=requester_id)
        .all()
    )
    assert len(stored) == 1
    assert str(stored[0].id) == request_id

    notifications = (
        db_session.query(Notification).filter_by(user_id=owner_id, kind="clan_join_request").all()
    )
    assert len(notifications) == 1
    assert notifications[0].data["request_id"] == request_id
    assert notifications[0].data["clan_id"] == clan["id"]


def test_join_race_recovers_the_pending_row_instead_of_500(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    _, requester_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    request_id = join_api(api, clan["id"], requester_token, "primeiro").json()["request"]["id"]

    original = clans_service._pending_request
    calls: list[dict] = []

    def miss_once(*args: object, **kwargs: object) -> object:
        calls.append(kwargs)
        if len(calls) == 1:
            # Simula a leitura que não vê a linha concorrente antes do INSERT.
            return None
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(clans_service, "_pending_request", miss_once)
    recovered = join_api(api, clan["id"], requester_token, "corrida")
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["request"]["id"] == request_id
    assert recovered.json()["request"]["message"] == "primeiro"
    assert len(calls) == 2
    assert db_session.query(ClanJoinRequest).filter_by(clan_id=uuid.UUID(clan["id"])).count() == 1
    # A recuperação da corrida não repete a notificação do pedido.
    assert db_session.query(Notification).filter_by(kind="clan_join_request").count() == 1


def test_my_request_appears_in_clan_detail_and_list(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    _, requester_token = make_player(db_session)
    _, outsider_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    request_id = join_api(api, clan["id"], requester_token, "quero entrar").json()["request"]["id"]

    detail = api.get(f"/api/v1/clans/{clan['id']}", headers=bearer(requester_token)).json()
    assert detail["my_request"]["id"] == request_id
    assert detail["my_request"]["status"] == "pending"
    assert detail["my_request"]["message"] == "quero entrar"
    assert detail["my_request"]["decision_note"] is None

    listed = api.get("/api/v1/clans", headers=bearer(requester_token)).json()["clans"]
    mine = next(item for item in listed if item["id"] == clan["id"])
    assert mine["my_request"]["id"] == request_id
    assert mine["my_request"]["message"] == "quero entrar"

    owner_view = api.get(f"/api/v1/clans/{clan['id']}", headers=bearer(owner_token)).json()
    assert owner_view["my_request"] is None
    outsider_list = api.get("/api/v1/clans", headers=bearer(outsider_token)).json()["clans"]
    assert next(item for item in outsider_list if item["id"] == clan["id"])["my_request"] is None


def test_my_clan_requests_pending_and_history(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    _, requester_token = make_player(db_session)
    _, outsider_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    request_id = join_api(api, clan["id"], requester_token, "quero entrar").json()["request"]["id"]

    pending = api.get("/api/v1/me/clan-requests", headers=bearer(requester_token))
    assert pending.status_code == 200, pending.text
    items = pending.json()["requests"]
    assert [item["id"] for item in items] == [request_id]
    assert items[0]["clan_id"] == clan["id"]
    assert items[0]["clan_name"] == "Tijuca FC"
    assert items[0]["clan_tag"] == "#TFC"
    assert items[0]["status"] == "pending"
    assert items[0]["message"] == "quero entrar"
    assert items[0]["decision_note"] is None
    assert items[0]["decided_at"] is None

    history = api.get(
        "/api/v1/me/clan-requests", headers=bearer(requester_token), params={"status": "history"}
    ).json()["requests"]
    assert history == []

    outsider = api.get("/api/v1/me/clan-requests", headers=bearer(outsider_token)).json()
    assert outsider["requests"] == []

    decided = api.post(
        f"/api/v1/clans/{clan['id']}/requests/{request_id}/decide",
        headers=bearer(owner_token),
        json={"approve": True, "note": "bem-vindo"},
    )
    assert decided.status_code == 200, decided.text

    assert (
        api.get("/api/v1/me/clan-requests", headers=bearer(requester_token)).json()["requests"]
        == []
    )
    history = api.get(
        "/api/v1/me/clan-requests", headers=bearer(requester_token), params={"status": "history"}
    ).json()["requests"]
    assert [item["id"] for item in history] == [request_id]
    assert history[0]["status"] == "approved"
    assert history[0]["decision_note"] == "bem-vindo"
    assert history[0]["decided_at"] is not None

    invalid = api.get(
        "/api/v1/me/clan-requests", headers=bearer(requester_token), params={"status": "all"}
    )
    assert invalid.status_code == 422


def test_admin_lists_decides_and_note_keeps_the_player_message(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    _, requester_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    request_id = join_api(api, clan["id"], requester_token, "quero entrar").json()["request"]["id"]

    listed = api.get(f"/api/v1/clans/{clan['id']}/requests", headers=bearer(owner_token))
    assert listed.status_code == 200, listed.text
    item = listed.json()["requests"][0]
    assert item["message"] == "quero entrar"
    assert item["decision_note"] is None
    assert item["decided_at"] is None
    assert item["decided_by"] is None

    decided = api.post(
        f"/api/v1/clans/{clan['id']}/requests/{request_id}/decide",
        headers=bearer(owner_token),
        json={"approve": True, "note": "bem-vindo"},
    )
    assert decided.status_code == 200, decided.text
    body = decided.json()
    assert body["status"] == "approved"
    assert body["message"] == "quero entrar"
    assert body["decision_note"] == "bem-vindo"
    assert body["decided_by"] == str(owner_id)
    assert body["decided_at"] is not None

    stored = db_session.get(ClanJoinRequest, uuid.UUID(request_id))
    assert stored is not None
    assert stored.message == "quero entrar"
    assert stored.decision_note == "bem-vindo"

    pending = api.get(f"/api/v1/clans/{clan['id']}/requests", headers=bearer(owner_token)).json()
    assert pending["requests"] == []
    history = api.get(
        f"/api/v1/clans/{clan['id']}/requests",
        headers=bearer(owner_token),
        params={"status": "history"},
    ).json()["requests"]
    assert [row["id"] for row in history] == [request_id]
    assert history[0]["status"] == "approved"


def test_second_decision_is_a_conflict(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    _, requester_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    request_id = join_api(api, clan["id"], requester_token).json()["request"]["id"]

    first = api.post(
        f"/api/v1/clans/{clan['id']}/requests/{request_id}/decide",
        headers=bearer(owner_token),
        json={"approve": False, "note": "sem vaga"},
    )
    assert first.status_code == 200, first.text

    again = api.post(
        f"/api/v1/clans/{clan['id']}/requests/{request_id}/decide",
        headers=bearer(owner_token),
        json={"approve": True},
    )
    assert again.status_code == 409, again.text
    assert again.json()["detail"]["code"] == "request_not_pending"


def test_only_the_author_cancels_a_pending_request(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    requester_id, requester_token = make_player(db_session)
    _, outsider_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    request_id = join_api(api, clan["id"], requester_token).json()["request"]["id"]
    url = f"/api/v1/clans/{clan['id']}/requests/{request_id}"

    outsider = api.delete(url, headers=bearer(outsider_token))
    assert outsider.status_code == 404, outsider.text
    owner = api.delete(url, headers=bearer(owner_token))
    assert owner.status_code == 404, owner.text

    cancelled = api.delete(url, headers=bearer(requester_token))
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["decided_by"] == str(requester_id)
    assert cancelled.json()["decided_at"] is not None
    assert cancelled.json()["message"] is None

    again = api.delete(url, headers=bearer(requester_token))
    assert again.status_code == 409, again.text
    assert again.json()["detail"]["code"] == "request_not_pending"

    detail = api.get(f"/api/v1/clans/{clan['id']}", headers=bearer(requester_token)).json()
    assert detail["my_request"]["status"] == "cancelled"
    assert owner_id != requester_id


def test_common_member_cannot_list_or_decide_requests(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    _, member_token = make_player(db_session)
    _, requester_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    _join_approved(api, clan["id"], owner_token, member_token)
    request_id = join_api(api, clan["id"], requester_token).json()["request"]["id"]

    listed = api.get(f"/api/v1/clans/{clan['id']}/requests", headers=bearer(member_token))
    assert listed.status_code == 403, listed.text
    assert listed.json()["detail"]["code"] == "admin_required"

    decided = api.post(
        f"/api/v1/clans/{clan['id']}/requests/{request_id}/decide",
        headers=bearer(member_token),
        json={"approve": True},
    )
    assert decided.status_code == 403, decided.text
    assert decided.json()["detail"]["code"] == "admin_required"


def test_join_notifies_owner_and_admins_and_decision_notifies_requester(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    admin_id, admin_token = make_player(db_session)
    requester_id, requester_token = make_player(db_session)
    db_session.add(UserProfile(user_id=requester_id, display_name="JOGADOR PEDIDO"))
    db_session.flush()
    clan = create_clan_api(api, owner_token)
    _join_approved(api, clan["id"], owner_token, admin_token)
    promote_admin(api, clan["id"], owner_token, admin_id)

    request_id = join_api(api, clan["id"], requester_token, "entrar").json()["request"]["id"]

    for user_id in (owner_id, admin_id):
        notifications = [
            row
            for row in db_session.query(Notification)
            .filter_by(user_id=user_id, kind="clan_join_request")
            .all()
            if row.data["request_id"] == request_id
        ]
        assert len(notifications) == 1
        assert notifications[0].data == {
            "clan_id": clan["id"],
            "request_id": request_id,
            "requester_name": "JOGADOR PEDIDO",
            "requester_tag": db_session.get(User, requester_id).tag,
        }
    assert (
        db_session.query(Notification)
        .filter_by(user_id=requester_id, kind="clan_join_request")
        .count()
        == 0
    )

    decided = api.post(
        f"/api/v1/clans/{clan['id']}/requests/{request_id}/decide",
        headers=bearer(admin_token),
        json={"approve": True, "note": "bem-vindo"},
    )
    assert decided.status_code == 200, decided.text

    approved = (
        db_session.query(Notification)
        .filter_by(user_id=requester_id, kind="clan_join_approved")
        .all()
    )
    assert len(approved) == 1
    assert approved[0].data["request_id"] == request_id
    assert approved[0].data["clan_id"] == clan["id"]
    assert approved[0].data["decision_note"] == "bem-vindo"
    assert (
        db_session.query(Notification)
        .filter_by(user_id=owner_id, kind="clan_join_approved")
        .count()
        == 0
    )


def test_rejected_decision_notifies_requester(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    requester_id, requester_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    request_id = join_api(api, clan["id"], requester_token).json()["request"]["id"]

    rejected = api.post(
        f"/api/v1/clans/{clan['id']}/requests/{request_id}/decide",
        headers=bearer(owner_token),
        json={"approve": False, "note": "sem vaga"},
    )
    assert rejected.status_code == 200, rejected.text

    notifications = (
        db_session.query(Notification)
        .filter_by(user_id=requester_id, kind="clan_join_rejected")
        .all()
    )
    assert len(notifications) == 1
    assert notifications[0].data["clan_id"] == clan["id"]
    assert notifications[0].data["request_id"] == request_id
    assert notifications[0].data["decision_note"] == "sem vaga"


def test_invite_answer_notifies_the_inviter(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    accepting_id, accepting_token = make_player(db_session)
    declining_id, declining_token = make_player(db_session)
    make_friends(db_session, owner_id, accepting_id)
    make_friends(db_session, owner_id, declining_id)
    clan = create_clan_api(api, owner_token)
    accepted_invite = invite_api(api, clan["id"], owner_token, accepting_id).json()
    declined_invite = invite_api(api, clan["id"], owner_token, declining_id).json()

    accepted = api.post(
        f"/api/v1/clans/invites/{accepted_invite['id']}/accept",
        headers=bearer(accepting_token),
    )
    assert accepted.status_code == 200, accepted.text
    declined = api.post(
        f"/api/v1/clans/invites/{declined_invite['id']}/decline",
        headers=bearer(declining_token),
    )
    assert declined.status_code == 200, declined.text

    accepted_notes = (
        db_session.query(Notification)
        .filter_by(user_id=owner_id, kind="clan_invite_accepted")
        .all()
    )
    assert len(accepted_notes) == 1
    assert accepted_notes[0].data["invite_id"] == accepted_invite["id"]
    assert accepted_notes[0].data["clan_id"] == clan["id"]
    assert accepted_notes[0].data["invitee_id"] == str(accepting_id)

    declined_notes = (
        db_session.query(Notification)
        .filter_by(user_id=owner_id, kind="clan_invite_declined")
        .all()
    )
    assert len(declined_notes) == 1
    assert declined_notes[0].data["invite_id"] == declined_invite["id"]
    assert declined_notes[0].data["clan_id"] == clan["id"]
    assert declined_notes[0].data["invitee_id"] == str(declining_id)


def test_clan_invites_listing_for_owner_and_admin(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    admin_id, admin_token = make_player(db_session)
    pending_id, _ = make_player(db_session)
    declined_id, declined_token = make_player(db_session)
    expired_id, _ = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    _join_approved(api, clan["id"], owner_token, admin_token)
    promote_admin(api, clan["id"], owner_token, admin_id)

    for friend_id in (pending_id, declined_id, expired_id):
        make_friends(db_session, owner_id, friend_id)
    pending_invite = invite_api(api, clan["id"], owner_token, pending_id).json()
    declined_invite = invite_api(api, clan["id"], owner_token, declined_id).json()
    expired_invite = invite_api(api, clan["id"], owner_token, expired_id).json()
    declined = api.post(
        f"/api/v1/clans/invites/{declined_invite['id']}/decline",
        headers=bearer(declined_token),
    )
    assert declined.status_code == 200, declined.text

    other_owner_id, other_owner_token = make_player(db_session)
    other_friend_id, _ = make_player(db_session)
    other_clan = create_clan_api(api, other_owner_token, name="Outro Clã", tag="OUT")
    make_friends(db_session, other_owner_id, other_friend_id)
    other_invite = invite_api(api, other_clan["id"], other_owner_token, other_friend_id).json()

    expired_row = db_session.get(ClanInvite, uuid.UUID(expired_invite["id"]))
    assert expired_row is not None
    expired_row.expires_at = utcnow() - timedelta(days=1)
    db_session.commit()

    for token in (owner_token, admin_token):
        pending = api.get(f"/api/v1/clans/{clan['id']}/invites", headers=bearer(token))
        assert pending.status_code == 200, pending.text
        invites = pending.json()["invites"]
        assert [item["id"] for item in invites] == [pending_invite["id"]]
        assert invites[0]["status"] == "pending"
        assert invites[0]["inviter_tag"] == db_session.get(User, owner_id).tag
        assert invites[0]["invitee_id"] == str(pending_id)
        assert invites[0]["invitee_tag"] == db_session.get(User, pending_id).tag
        assert other_invite["id"] not in {item["id"] for item in invites}

    history = api.get(
        f"/api/v1/clans/{clan['id']}/invites",
        headers=bearer(owner_token),
        params={"status": "history"},
    )
    assert history.status_code == 200, history.text
    by_id = {item["id"]: item for item in history.json()["invites"]}
    assert set(by_id) == {declined_invite["id"], expired_invite["id"]}
    assert by_id[declined_invite["id"]]["status"] == "declined"
    assert by_id[expired_invite["id"]]["status"] == "expired"
    assert other_invite["id"] not in by_id

    # O convite expirado virou ``expired`` na leitura e saiu de ``pending``.
    pending_again = api.get(f"/api/v1/clans/{clan['id']}/invites", headers=bearer(owner_token))
    assert [item["id"] for item in pending_again.json()["invites"]] == [pending_invite["id"]]


def test_clan_invites_requires_admin_and_known_clan(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    _, owner_token = make_player(db_session)
    _, member_token = make_player(db_session)
    _, outsider_token = make_player(db_session)
    clan = create_clan_api(api, owner_token)
    _join_approved(api, clan["id"], owner_token, member_token)

    common_member = api.get(f"/api/v1/clans/{clan['id']}/invites", headers=bearer(member_token))
    assert common_member.status_code == 403, common_member.text
    assert common_member.json()["detail"]["code"] == "admin_required"

    outsider = api.get(f"/api/v1/clans/{clan['id']}/invites", headers=bearer(outsider_token))
    assert outsider.status_code == 403, outsider.text
    assert outsider.json()["detail"]["code"] == "not_a_member"

    unknown = api.get(f"/api/v1/clans/{uuid.uuid4()}/invites", headers=bearer(owner_token))
    assert unknown.status_code == 404, unknown.text
    assert unknown.json()["detail"]["code"] == "not_found"

    assert client.get(f"/api/v1/clans/{clan['id']}/invites").status_code == 401


def test_clan_invites_expose_invitee_identity_without_pii(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    owner_id, owner_token = make_player(db_session)
    invitee_id, invitee_token = make_player(db_session)
    make_friends(db_session, owner_id, invitee_id)
    invitee_row = db_session.get(User, invitee_id)
    assert invitee_row is not None
    invitee_row.email = "convidado@example.test"
    db_session.commit()
    profile = api.put(
        "/api/v1/me/profile",
        headers=bearer(invitee_token),
        json={"display_name": "  jogador   convidado "},
    )
    assert profile.status_code == 200, profile.text
    clan = create_clan_api(api, owner_token)
    invite = invite_api(api, clan["id"], owner_token, invitee_id).json()

    other_owner_id, other_owner_token = make_player(db_session)
    other_invitee_id, _ = make_player(db_session)
    other_clan = create_clan_api(api, other_owner_token, name="Outro Clã", tag="OUT")
    make_friends(db_session, other_owner_id, other_invitee_id)
    other_invite = invite_api(api, other_clan["id"], other_owner_token, other_invitee_id).json()

    owner_list = api.get(f"/api/v1/clans/{clan['id']}/invites", headers=bearer(owner_token))
    assert owner_list.status_code == 200, owner_list.text
    listed = owner_list.json()["invites"]
    assert [item["id"] for item in listed] == [invite["id"]]
    pending = listed[0]
    assert pending["invitee_id"] == str(invitee_id)
    assert pending["invitee_tag"] == tag_from_uuid(invitee_id)
    assert re.fullmatch(r"#[0-9A-F]{8,12}", pending["invitee_tag"])
    assert pending["invitee_display_name"] == normalize_display_name("  jogador   convidado ")
    assert pending["invitee_display_name"] == "JOGADOR CONVIDADO"
    assert other_invite["id"] not in {item["id"] for item in listed}

    own_list = api.get("/api/v1/me/clan-invites", headers=bearer(invitee_token))
    assert own_list.status_code == 200, own_list.text
    own = own_list.json()["invites"]
    assert [item["id"] for item in own] == [invite["id"]]
    assert own[0]["invitee_id"] == str(invitee_id)
    assert own[0]["invitee_tag"] == pending["invitee_tag"]
    assert own[0]["invitee_display_name"] == pending["invitee_display_name"]

    # O convite expõe apenas identidade pública; nenhum dado pessoal vaza.
    for item in (pending, own[0]):
        assert set(item) == {
            "id",
            "clan_id",
            "clan_name",
            "clan_tag",
            "inviter_id",
            "inviter_display_name",
            "inviter_tag",
            "invitee_id",
            "invitee_display_name",
            "invitee_tag",
            "status",
            "created_at",
            "expires_at",
            "answered_at",
        }
    for response in (owner_list, own_list):
        assert "convidado@example.test" not in response.text
        assert "phone" not in response.text
        assert "cpf" not in response.text
