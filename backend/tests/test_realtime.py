"""Testes do registro local de conexões WebSocket."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from app.modules.realtime.manager import ConnectionManager


class FakeSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.messages.append(payload)


def test_publish_only_to_subscribed_socket() -> None:
    async def scenario() -> None:
        manager = ConnectionManager()
        lobby_id = uuid.uuid4()
        user_id = uuid.uuid4()
        subscribed = FakeSocket()
        other = FakeSocket()

        await manager.connect(subscribed, user_id)
        await manager.connect(other, uuid.uuid4())
        await manager.subscribe(subscribed, lobby_id)

        delivered = await manager.publish_lobby(lobby_id, {"type": "message"})

        assert delivered == 1
        assert subscribed.messages == [{"type": "message"}]
        assert other.messages == []

        await manager.disconnect(subscribed, user_id)
        assert await manager.publish_lobby(lobby_id, {"type": "after"}) == 0

    asyncio.run(scenario())


def test_publish_to_user_room() -> None:
    async def scenario() -> None:
        manager = ConnectionManager()
        user_id = uuid.uuid4()
        socket = FakeSocket()
        await manager.connect(socket, user_id)

        delivered = await manager.publish_user(user_id, {"type": "invite"})

        assert delivered == 1
        assert socket.messages == [{"type": "invite"}]

    asyncio.run(scenario())
