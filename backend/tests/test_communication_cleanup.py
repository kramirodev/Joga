"""Testes da retenção provisória da comunicação."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.chat.models import LobbyMessage
from app.modules.outbox.models import OutboxEvent
from app.modules.social.cleanup import cleanup_communication
from app.modules.social.models import DevicePushToken, LobbyInvite
from tests.helpers_results import END, build_match

NOW = END + timedelta(days=1000)


def test_cleanup_removes_only_expired_communication(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    old = NOW - timedelta(days=800)
    recent = NOW - timedelta(days=10)

    db_session.add(
        LobbyMessage(
            lobby_id=match.lobby_id,
            sender_id=users[0],
            body="antiga",
            created_at=old,
        )
    )
    db_session.add(
        LobbyMessage(
            lobby_id=match.lobby_id,
            sender_id=users[0],
            body="recente",
            created_at=recent,
        )
    )

    for invitee, status, moment in (
        (users[1], "DECLINED", old),
        (users[2], "DECLINED", recent),
    ):
        db_session.add(
            LobbyInvite(
                lobby_id=match.lobby_id,
                inviter_id=users[0],
                invitee_id=invitee,
                status=status,
                created_at=moment,
                expires_at=moment + timedelta(days=1),
                responded_at=moment,
            )
        )

    for status, moment in (("DISPATCHED", old), ("DISPATCHED", recent), ("PENDING", old)):
        db_session.add(
            OutboxEvent(
                event_type="test",
                aggregate_type="test",
                payload={},
                status=status,
                created_at=moment,
                available_at=moment,
                dispatched_at=moment if status == "DISPATCHED" else None,
            )
        )

    db_session.add(
        DevicePushToken(
            user_id=users[0],
            token="old-token",
            platform="android",
            created_at=old,
            last_seen_at=old,
            revoked_at=old,
        )
    )
    db_session.add(
        DevicePushToken(
            user_id=users[0],
            token="recent-token",
            platform="android",
            created_at=recent,
            last_seen_at=recent,
            revoked_at=recent,
        )
    )
    db_session.flush()

    result = cleanup_communication(db_session, now=NOW)

    assert result.messages == 1
    assert result.invites == 1
    assert result.outbox_events == 1
    assert result.push_tokens == 1
    assert db_session.scalar(select(func.count()).select_from(LobbyMessage)) == 1
    assert db_session.scalar(select(func.count()).select_from(LobbyInvite)) == 1
    assert db_session.scalar(select(func.count()).select_from(OutboxEvent)) == 2
    assert db_session.scalar(select(func.count()).select_from(DevicePushToken)) == 1


def test_cleanup_rejects_negative_retention(db_session: Session) -> None:
    with pytest.raises(ValueError):
        cleanup_communication(db_session, message_days=-1, now=NOW)
