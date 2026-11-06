"""Registro local de conexões WebSocket e entrega de eventos."""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Entrega best-effort para conexões do processo atual.

    Não é fonte de verdade nem mecanismo de coordenação entre processos.
    """

    def __init__(self) -> None:
        self._lobbies: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        self._users: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, socket: WebSocket, user_id: uuid.UUID) -> None:
        async with self._lock:
            self._users[user_id].add(socket)

    async def disconnect(self, socket: WebSocket, user_id: uuid.UUID) -> None:
        async with self._lock:
            self._users[user_id].discard(socket)
            for sockets in self._lobbies.values():
                sockets.discard(socket)

    async def subscribe(self, socket: WebSocket, lobby_id: uuid.UUID) -> None:
        async with self._lock:
            self._lobbies[lobby_id].add(socket)

    async def unsubscribe(self, socket: WebSocket, lobby_id: uuid.UUID) -> None:
        async with self._lock:
            self._lobbies[lobby_id].discard(socket)

    async def publish_lobby(self, lobby_id: uuid.UUID, payload: dict[str, Any]) -> int:
        async with self._lock:
            sockets = list(self._lobbies.get(lobby_id, ()))
        return await self._send_many(sockets, payload)

    async def publish_user(self, user_id: uuid.UUID, payload: dict[str, Any]) -> int:
        async with self._lock:
            sockets = list(self._users.get(user_id, ()))
        return await self._send_many(sockets, payload)

    async def _send_many(self, sockets: list[WebSocket], payload: dict[str, Any]) -> int:
        delivered = 0
        for socket in sockets:
            try:
                await socket.send_json(payload)
                delivered += 1
            except Exception:
                # Entrega é best-effort; o histórico continua disponível na API.
                continue
        return delivered

    def clear(self) -> None:
        self._lobbies.clear()
        self._users.clear()


manager = ConnectionManager()
