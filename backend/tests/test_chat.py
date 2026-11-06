"""Testes de Outbox, chat por lobby e publicação."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.chat.models import LobbyMessage
from app.modules.chat.service import (
    ChatAccessDenied,
    ChatClosed,
    ChatService,
    InvalidMessage,
)
from app.modules.identity.clock import ensure_utc
from app.modules.matchmaking.models import Lobby
from app.modules.outbox.models import OutboxEvent
from app.modules.outbox.service import OutboxService
from tests.helpers_results import END, build_match, make_user

AT = END + timedelta(minutes=2)


def test_outbox_is_created_and_dispatched(db_session: Session) -> None:
    event = OutboxService(db_session).enqueue(
        event_type="lobby.message.created",
        aggregate_type="lobby",
        aggregate_id=None,
        payload={"hello": "world"},
        now=AT,
    )

    pending = OutboxService(db_session).pending(now=AT)
    assert pending == [event]

    OutboxService(db_session).mark_dispatched(event, now=AT)
    assert event.status == "DISPATCHED"
    assert OutboxService(db_session).pending(now=AT) == []


def test_message_is_persisted_before_outbox(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service = ChatService(db_session)

    message = service.send_message(match.lobby_id, users[0], "olá lobby", now=AT)

    assert db_session.get(LobbyMessage, message.id) is not None
    events = list(
        db_session.scalars(
            select(OutboxEvent).where(OutboxEvent.event_type == "lobby.message.created")
        )
    )
    assert len(events) == 1
    assert events[0].payload["body"] == "olá lobby"


def test_non_participant_cannot_read_or_write(db_session: Session) -> None:
    match, _, _, _ = build_match(db_session, checked_in=10)
    outsider = make_user(db_session)

    with pytest.raises(ChatAccessDenied):
        ChatService(db_session).list_messages(match.lobby_id, outsider)
    with pytest.raises(ChatAccessDenied):
        ChatService(db_session).send_message(match.lobby_id, outsider, "oi", now=AT)


def test_message_validation_and_closed_lobby(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service = ChatService(db_session)

    with pytest.raises(InvalidMessage):
        service.send_message(match.lobby_id, users[0], "   ", now=AT)
    with pytest.raises(InvalidMessage):
        service.send_message(match.lobby_id, users[0], "x" * 2001, now=AT)

    lobby = db_session.get(Lobby, match.lobby_id)
    assert lobby is not None
    lobby.status = "cancelled"
    db_session.flush()
    with pytest.raises(ChatClosed):
        service.send_message(match.lobby_id, users[0], "oi", now=AT)


def test_history_is_paginated_and_ordered(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service = ChatService(db_session)
    first = service.send_message(match.lobby_id, users[0], "primeira", now=AT)
    second = service.send_message(
        match.lobby_id,
        users[1],
        "segunda",
        now=AT + timedelta(seconds=1),
    )

    messages = service.list_messages(match.lobby_id, users[0], limit=10)
    assert [message.id for message in messages] == [first.id, second.id]

    older = service.list_messages(
        match.lobby_id,
        users[0],
        before=ensure_utc(second.created_at),
        limit=10,
    )
    assert [message.id for message in older] == [first.id]
