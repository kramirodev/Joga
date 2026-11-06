"""Testes HTTP de chat por lobby."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.outbox.models import OutboxEvent
from tests.helpers_results import build_match, make_token, make_user


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def post_message(
    api: TestClient,
    token: str,
    lobby_id: uuid.UUID,
    *,
    body: str = "olá",
    key: str = "chat-key-1",
):
    return api.post(
        f"/api/v1/lobbies/{lobby_id}/messages",
        headers={**bearer(token), "Idempotency-Key": key},
        json={"body": body},
    )


def test_chat_requires_authentication(client: TestClient) -> None:
    response = client.get(f"/api/v1/lobbies/{uuid.uuid4()}/messages")
    assert response.status_code == 401


def test_send_list_and_replay_message(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    match, users, _, _ = build_match(db_session, checked_in=10)
    token = make_token(db_session, users[0])

    first = post_message(api, token, match.lobby_id, body="bom jogo")
    assert first.status_code == 201
    body = first.json()
    assert body["body"] == "bom jogo"

    replay = post_message(api, token, match.lobby_id, body="bom jogo")
    assert replay.status_code == 201
    assert replay.json()["id"] == body["id"]

    listed = api.get(
        f"/api/v1/lobbies/{match.lobby_id}/messages",
        headers=bearer(token),
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["messages"]] == [body["id"]]

    assert (
        db_session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "lobby.message.created")
        )
        == 1
    )


def test_non_participant_cannot_read_or_send(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    match, _, _, _ = build_match(db_session, checked_in=10)
    outsider = make_user(db_session)
    token = make_token(db_session, outsider)

    assert (
        api.get(
            f"/api/v1/lobbies/{match.lobby_id}/messages",
            headers=bearer(token),
        ).status_code
        == 404
    )
    assert post_message(api, token, match.lobby_id).status_code == 404


def test_missing_idempotency_and_invalid_body(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    match, users, _, _ = build_match(db_session, checked_in=10)
    token = make_token(db_session, users[0])

    missing = api.post(
        f"/api/v1/lobbies/{match.lobby_id}/messages",
        headers=bearer(token),
        json={"body": "oi"},
    )
    assert missing.status_code == 422
    assert missing.json() == {"detail": {"code": "missing_idempotency_key"}}

    empty = post_message(api, token, match.lobby_id, body="   ", key="empty")
    assert empty.status_code == 422
    assert empty.json() == {"detail": {"code": "invalid_message"}}

    long = post_message(api, token, match.lobby_id, body="x" * 2001, key="long")
    assert long.status_code == 422
    assert long.json() == {"detail": {"code": "invalid_message"}}
