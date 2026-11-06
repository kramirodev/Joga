"""Testes de tokens de push e adaptador de envio."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.push.service import PushError, PushService, RecordingPushSender
from app.modules.social.models import DevicePushToken
from tests.helpers_results import END, make_user

AT = END + timedelta(minutes=2)


def test_register_reassign_and_revoke_token(db_session: Session) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    service = PushService(db_session)

    token = service.register_token(first, "token-1", "android", now=AT)
    assert token.user_id == first
    assert db_session.scalar(select(func.count()).select_from(DevicePushToken)) == 1

    reassigned = service.register_token(second, "token-1", "ios", now=AT)
    assert reassigned.user_id == second
    assert reassigned.platform == "ios"

    service.revoke_token(second, "token-1", now=AT)
    assert reassigned.revoked_at is not None

    with pytest.raises(PushError):
        service.revoke_token(first, "token-1", now=AT)
    with pytest.raises(PushError):
        service.register_token(first, "token-2", "desktop", now=AT)


def test_sender_receives_active_tokens_only(db_session: Session) -> None:
    user = make_user(db_session)
    sender = RecordingPushSender()
    service = PushService(db_session, sender=sender)
    service.register_token(user, "active", "android", now=AT)
    service.register_token(user, "revoked", "android", now=AT)
    service.revoke_token(user, "revoked", now=AT)

    sent = service.send_to_user(
        user,
        title="Convite",
        body="Você recebeu um convite",
        data={"lobby_id": "x"},
    )

    assert sent == 1
    assert sender.sent[0]["token"] == "active"
