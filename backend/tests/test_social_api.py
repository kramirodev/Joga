"""Testes HTTP de amigos, bloqueios, convites e push."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.matchmaking.models import LobbyParticipant
from app.modules.profile.models import UserSportProfile
from tests.helpers_results import build_match, make_token, make_user


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_friend(session: Session, format_id):
    user_id = make_user(session)
    session.add(
        UserSportProfile(
            user_id=user_id,
            format_id=format_id,
            level="intermediate",
            court_preference="ANY",
        )
    )
    session.flush()
    return user_id


def test_friend_request_flow(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    first = make_user(db_session)
    second = make_user(db_session)
    first_token = make_token(db_session, first)
    second_token = make_token(db_session, second)

    request = api.post(
        "/api/v1/friends/requests",
        headers=bearer(first_token),
        json={"user_id": str(second)},
    )
    assert request.status_code == 201

    accepted = api.post(
        f"/api/v1/friends/requests/{request.json()['id']}/accept",
        headers=bearer(second_token),
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"

    friends = api.get("/api/v1/friends", headers=bearer(first_token))
    assert friends.status_code == 200
    assert [item["user_id"] for item in friends.json()["friends"]] == [str(second)]

    removed = api.delete(f"/api/v1/friends/{second}", headers=bearer(first_token))
    assert removed.status_code == 204


def test_block_prevents_friend_request(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    first = make_user(db_session)
    second = make_user(db_session)
    first_token = make_token(db_session, first)
    second_token = make_token(db_session, second)

    blocked = api.post(
        "/api/v1/blocks",
        headers=bearer(first_token),
        json={"user_id": str(second)},
    )
    assert blocked.status_code == 201

    response = api.post(
        "/api/v1/friends/requests",
        headers=bearer(second_token),
        json={"user_id": str(first)},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "blocked_relationship"}}


def test_lobby_invite_accepts_friend(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    match, users, _, sport_format = build_match(db_session, checked_in=10)
    friend = make_friend(db_session, sport_format.id)
    inviter_token = make_token(db_session, users[0])
    friend_token = make_token(db_session, friend)

    request = api.post(
        "/api/v1/friends/requests",
        headers=bearer(inviter_token),
        json={"user_id": str(friend)},
    )
    api.post(
        f"/api/v1/friends/requests/{request.json()['id']}/accept",
        headers=bearer(friend_token),
    )

    participant = db_session.scalar(
        select(LobbyParticipant).where(
            LobbyParticipant.lobby_id == match.lobby_id,
            LobbyParticipant.user_id == users[1],
        )
    )
    assert participant is not None
    db_session.delete(participant)
    db_session.commit()

    invite = api.post(
        f"/api/v1/lobbies/{match.lobby_id}/invites",
        headers=bearer(inviter_token),
        json={"user_id": str(friend)},
    )
    assert invite.status_code == 201

    accepted = api.post(
        f"/api/v1/lobby-invites/{invite.json()['id']}/accept",
        headers=bearer(friend_token),
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"


def test_push_token_register_and_revoke(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user = make_user(db_session)
    token = make_token(db_session, user)

    registered = api.put(
        "/api/v1/push-tokens",
        headers=bearer(token),
        json={"token": "push-token-1", "platform": "android"},
    )
    assert registered.status_code == 200
    assert registered.json()["token"] == "push-token-1"

    revoked = api.delete("/api/v1/push-tokens/push-token-1", headers=bearer(token))
    assert revoked.status_code == 204


def test_social_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/friends").status_code == 401
    assert client.get("/api/v1/lobby-invites").status_code == 401
