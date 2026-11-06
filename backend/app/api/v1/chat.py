"""Endpoints HTTP de chat por lobby."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.chat.models import LobbyMessage
from app.modules.chat.service import (
    ChatAccessDenied,
    ChatClosed,
    ChatService,
    InvalidMessage,
)
from app.modules.idempotency import service as idempotency
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.ratelimit.service import RateLimitExceeded
from app.modules.ratelimit.service import enforce as enforce_rate_limit
from app.modules.realtime.manager import manager

router = APIRouter(prefix="/lobbies", tags=["chat"])

CHAT_RATE_LIMIT_PER_MINUTE = 20


class MessageView(BaseModel):
    id: UUID
    lobby_id: UUID
    sender_id: UUID
    body: str
    created_at: datetime


class MessagesResponse(BaseModel):
    messages: list[MessageView]


class MessageRequest(BaseModel):
    body: str


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, ChatAccessDenied):
        return _error("lobby_access_denied", status.HTTP_404_NOT_FOUND)
    if isinstance(exc, ChatClosed):
        return _error("chat_closed", status.HTTP_409_CONFLICT)
    if isinstance(exc, InvalidMessage):
        return _error("invalid_message", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if isinstance(exc, RateLimitExceeded):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited"},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )
    if isinstance(exc, idempotency.IdempotencyConflict):
        return _error("idempotency_conflict", status.HTTP_409_CONFLICT)
    if isinstance(exc, idempotency.IdempotencyInProgress):
        return _error("idempotency_in_progress", status.HTTP_409_CONFLICT)
    raise exc


def _view(message: LobbyMessage) -> MessageView:
    return MessageView(
        id=message.id,
        lobby_id=message.lobby_id,
        sender_id=message.sender_id,
        body=message.body,
        created_at=message.created_at,
    )


@router.get("/{lobby_id}/messages", response_model=MessagesResponse)
def list_messages(
    lobby_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    before: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessagesResponse:
    try:
        messages = ChatService(session).list_messages(
            lobby_id,
            current.user_id,
            before=before,
            limit=limit,
        )
    except ChatAccessDenied as exc:
        raise _handle(exc) from None
    return MessagesResponse(messages=[_view(message) for message in messages])


@router.post(
    "/{lobby_id}/messages",
    response_model=MessageView,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    lobby_id: UUID,
    payload: MessageRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MessageView | JSONResponse:
    if idempotency_key is None or not idempotency_key.strip():
        raise _error("missing_idempotency_key", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if len(idempotency_key) > 120:
        raise _error("invalid_idempotency_key", status.HTTP_422_UNPROCESSABLE_CONTENT)
    scope = f"lobby-message:{current.user_id}:{lobby_id}"
    request_hash = idempotency.payload_hash({"body": payload.body})
    try:
        stored = idempotency.begin(
            session,
            scope=scope,
            key=idempotency_key,
            request_hash=request_hash,
        )
    except (idempotency.IdempotencyConflict, idempotency.IdempotencyInProgress) as exc:
        session.rollback()
        raise _handle(exc) from None
    if stored is not None:
        return JSONResponse(status_code=stored.status_code, content=stored.body)

    try:
        enforce_rate_limit(
            session,
            scope="lobby-message",
            key=f"{current.user_id}:{lobby_id}",
            limit=CHAT_RATE_LIMIT_PER_MINUTE,
            now=None,
        )
        message = ChatService(session).send_message(
            lobby_id,
            current.user_id,
            payload.body,
        )
        response = _view(message)
        idempotency.finish(
            session,
            scope=scope,
            key=idempotency_key,
            status_code=status.HTTP_201_CREATED,
            body=response.model_dump(mode="json"),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001 - convertido para erro de negócio
        session.rollback()
        raise _handle(exc) from None

    await manager.publish_lobby(
        lobby_id,
        {"type": "lobby.message.created", "data": response.model_dump(mode="json")},
    )
    return response
