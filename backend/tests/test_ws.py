"""Testes do endpoint WebSocket e da autorização de salas."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

from app.api.v1 import ws as ws_module
from app.infrastructure.database.base import Base
from app.main import create_app
from app.modules.realtime.manager import manager
from tests.helpers_results import build_match, make_token


@pytest.fixture
def ws_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, uuid.UUID, str]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        match, users, _, _ = build_match(session, checked_in=10)
        token = make_token(session, users[0])
        lobby_id = match.lobby_id

    monkeypatch.setattr(ws_module, "get_session_factory", lambda: factory)
    manager.clear()
    client = TestClient(create_app())
    yield client, lobby_id, token
    manager.clear()
    engine.dispose()


def test_websocket_ping_and_subscribe(ws_client) -> None:
    client, lobby_id, token = ws_client

    with client.websocket_connect(
        "/api/v1/ws",
        headers={"Authorization": f"Bearer {token}"},
    ) as socket:
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}

        socket.send_json({"type": "subscribe", "lobby_id": str(lobby_id)})
        assert socket.receive_json() == {
            "type": "subscribed",
            "lobby_id": str(lobby_id),
        }

        socket.send_json({"type": "subscribe", "lobby_id": str(uuid.uuid4())})
        assert socket.receive_json() == {
            "type": "error",
            "code": "lobby_access_denied",
        }


def test_websocket_rejects_missing_token(ws_client) -> None:
    client, _, _ = ws_client

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws"):
            pass
