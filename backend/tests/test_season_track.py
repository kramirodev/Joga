"""Testes da trilha, itens e insígnias (Fase 14D.8)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.season.service import award_xp, seed_current_season
from app.modules.tickets.service import get_balance
from tests.helpers_results import make_token, make_user


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def give_xp(db_session: Session, user_id, amount: int) -> None:
    season = seed_current_season(db_session)
    award_xp(
        db_session,
        user_id=user_id,
        season=season,
        amount=amount,
        source="admin",
        idempotency_key=f"admin:{user_id}:{amount}",
    )
    db_session.flush()


def test_track_exposes_seven_items(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    response = api.get("/api/v1/me/progress/track", headers=bearer(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["levels"]) == 30
    items = [level for level in body["levels"] if level["item_code"]]
    assert len(items) == 7
    assert {level["track"] for level in items} == {"free", "pass"}
    tickets = [level for level in body["levels"] if level["free_tickets"]]
    assert len(tickets) == 6


def test_claim_requires_xp(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    response = api.post("/api/v1/me/progress/track/5/claim", headers=bearer(token))
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "level_locked"


def test_claim_grants_ticket_once(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    give_xp(db_session, user_id, 750)  # nível 5
    db_session.commit()

    first = api.post("/api/v1/me/progress/track/5/claim", headers=bearer(token))
    second = api.post("/api/v1/me/progress/track/5/claim", headers=bearer(token))
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert get_balance(db_session, user_id) == 1


def test_pass_level_is_blocked_without_pass(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    give_xp(db_session, user_id, 1_800)  # nível 12
    db_session.commit()

    response = api.post("/api/v1/me/progress/track/12/claim", headers=bearer(token))
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "pass_required"


def test_level_thirty_awards_badge_and_equips(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    give_xp(db_session, user_id, 4_500)  # nível 30
    db_session.commit()

    claimed = api.post("/api/v1/me/progress/track/30/claim", headers=bearer(token))
    assert claimed.status_code == 200, claimed.text

    badges = api.get("/api/v1/me/progress/badges", headers=bearer(token))
    assert badges.status_code == 200, badges.text
    items = badges.json()["badges"]
    assert len(items) == 1
    assert items[0]["kind"] == "season"
    assert items[0]["equipped_slot"] is None

    badge_id = items[0]["badge_id"]
    equipped = api.put(
        "/api/v1/me/progress/badges/equip",
        headers=bearer(token),
        json={"badge_id": badge_id, "slot": 1},
    )
    assert equipped.status_code == 200, equipped.text
    assert equipped.json()["equipped_slot"] == 1

    again = api.get("/api/v1/me/progress/badges", headers=bearer(token))
    assert again.json()["badges"][0]["equipped_slot"] == 1


def test_equipping_requires_ownership(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id = make_user(db_session)
    owner_token = make_token(db_session, owner_id)
    give_xp(db_session, owner_id, 4_500)
    db_session.commit()
    api.post("/api/v1/me/progress/track/30/claim", headers=bearer(owner_token))
    badge = api.get("/api/v1/me/progress/badges", headers=bearer(owner_token)).json()["badges"][0]

    other_id = make_user(db_session)
    other_token = make_token(db_session, other_id)
    response = api.put(
        "/api/v1/me/progress/badges/equip",
        headers=bearer(other_token),
        json={"badge_id": badge["badge_id"], "slot": 1},
    )
    assert response.status_code == 404, response.text
