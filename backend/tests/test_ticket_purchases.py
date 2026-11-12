"""Testes de pacotes e compra de ingressos (Fase 14D.4)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from tests.helpers_results import make_token, make_user


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_packs_follow_the_price_ladder(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    response = api.get("/api/v1/me/tickets/packs", headers=bearer(token))
    assert response.status_code == 200, response.text
    packs = response.json()["packs"]
    assert [pack["code"] for pack in packs] == ["avulso", "pequeno", "medio", "grande"]
    units = [pack["unit_price_cents"] for pack in packs]
    assert units == sorted(units, reverse=True)
    assert packs[0]["unit_price_cents"] == 370
    assert packs[-1]["unit_price_cents"] == 310


def test_purchase_then_confirm_credits_the_wallet(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    created = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "pequeno"},
    )
    assert created.status_code == 201, created.text
    purchase = created.json()
    assert purchase["tickets"] == 10
    assert purchase["amount_cents"] == 3_400
    assert purchase["status"] == "pending"

    confirmed = api.post(
        f"/api/v1/me/tickets/purchases/{purchase['id']}/confirm", headers=bearer(token)
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "paid"

    wallet = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert wallet.json()["balance"] == 10


def test_confirming_twice_does_not_double_credit(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    purchase = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "avulso"},
    ).json()
    first = api.post(
        f"/api/v1/me/tickets/purchases/{purchase['id']}/confirm", headers=bearer(token)
    )
    second = api.post(
        f"/api/v1/me/tickets/purchases/{purchase['id']}/confirm", headers=bearer(token)
    )
    assert first.status_code == 200
    assert second.status_code == 200

    wallet = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert wallet.json()["balance"] == 3


def test_unknown_pack_is_rejected(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    response = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "inexistente"},
    )
    assert response.status_code == 404, response.text


def test_purchase_is_not_readable_by_another_user(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    owner_id = make_user(db_session)
    owner_token = make_token(db_session, owner_id)
    purchase = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(owner_token),
        json={"pack_code": "medio"},
    ).json()

    other_id = make_user(db_session)
    other_token = make_token(db_session, other_id)
    response = api.get(
        f"/api/v1/me/tickets/purchases/{purchase['id']}", headers=bearer(other_token)
    )
    assert response.status_code == 404, response.text
