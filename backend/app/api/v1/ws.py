"""WebSocket autenticado para eventos de lobby."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.infrastructure.database.dependency import get_session_factory
from app.modules.chat.service import ChatService
from app.modules.identity.sessions import AuthenticatedSession, InvalidAccessToken, SessionService
from app.modules.realtime.manager import manager

router = APIRouter(tags=["realtime"])

HEARTBEAT_SECONDS = 30
CLOSE_UNAUTHORIZED = 4401


def _token_from_header(value: str | None) -> str | None:
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _authenticate(token: str) -> AuthenticatedSession | None:
    settings = get_settings()
    with get_session_factory()() as session:
        try:
            return SessionService(
                session,
                settings.token_hash_secret.get_secret_value(),
                access_ttl_seconds=settings.access_token_ttl_seconds,
                refresh_absolute_ttl_days=settings.refresh_absolute_ttl_days,
                refresh_idle_ttl_days=settings.refresh_idle_ttl_days,
            ).authenticate(token)
        except InvalidAccessToken:
            return None


def _can_subscribe(user_id: uuid.UUID, lobby_id: uuid.UUID) -> bool:
    with get_session_factory()() as session:
        return ChatService(session).is_participant(lobby_id, user_id)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = _token_from_header(websocket.headers.get("authorization"))
    if token is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return
    authenticated = _authenticate(token)
    if authenticated is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    await websocket.accept()
    await manager.connect(websocket, authenticated.user_id)
    try:
        while True:
            try:
                payload = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=HEARTBEAT_SECONDS,
                )
            except TimeoutError:
                if _authenticate(token) is None:
                    await websocket.close(code=CLOSE_UNAUTHORIZED)
                    break
                await websocket.send_json({"type": "ping"})
                continue
            except WebSocketDisconnect:
                break

            if _authenticate(token) is None:
                await websocket.close(code=CLOSE_UNAUTHORIZED)
                break

            message_type = payload.get("type")
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if message_type == "subscribe":
                try:
                    lobby_id = uuid.UUID(str(payload.get("lobby_id")))
                except (TypeError, ValueError):
                    await websocket.send_json({"type": "error", "code": "invalid_lobby_id"})
                    continue
                if not _can_subscribe(authenticated.user_id, lobby_id):
                    await websocket.send_json({"type": "error", "code": "lobby_access_denied"})
                    continue
                await manager.subscribe(websocket, lobby_id)
                await websocket.send_json({"type": "subscribed", "lobby_id": str(lobby_id)})
                continue
            if message_type == "unsubscribe":
                try:
                    lobby_id = uuid.UUID(str(payload.get("lobby_id")))
                except (TypeError, ValueError):
                    await websocket.send_json({"type": "error", "code": "invalid_lobby_id"})
                    continue
                await manager.unsubscribe(websocket, lobby_id)
                await websocket.send_json({"type": "unsubscribed", "lobby_id": str(lobby_id)})
                continue
            await websocket.send_json({"type": "error", "code": "unknown_type"})
    finally:
        await manager.disconnect(websocket, authenticated.user_id)
