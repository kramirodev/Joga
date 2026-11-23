"""Testes do dispatcher de notificações, do worker e do evento em tempo real."""

from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.modules.identity.clock import ensure_utc
from app.modules.notifications.dispatch import (
    DEFAULT_RETRY_SECONDS,
    DispatchReport,
    dispatch_notifications,
)
from app.modules.notifications.service import NotificationService
from app.modules.outbox.models import OutboxEvent
from app.modules.outbox.service import OutboxService
from app.modules.push.service import PushError, PushService, RecordingPushSender
from app.modules.realtime import notifications as realtime_notifications
from app.modules.realtime.manager import ConnectionManager
from app.modules.social.models import DevicePushToken
from tests.helpers_results import END, make_user
from workers.notification_dispatch import NotificationDispatchWorker

AT = END + timedelta(minutes=2)


class RecordingPublisher:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, dict[str, Any]]] = []

    def __call__(self, user_id: uuid.UUID, payload: dict[str, Any]) -> int:
        self.calls.append((user_id, payload))
        return 1


class FailingSender:
    def __init__(self, code: str) -> None:
        self.code = code
        self.calls = 0

    def send_batch(self, messages: list[Any]) -> list[Any]:
        self.calls += 1
        raise PushError(self.code)

    def close(self) -> None:
        return None


def create_notification(
    session: Session,
    user_id: uuid.UUID,
    *,
    key: str = "dispatch:1",
    kind: str = "booking_requested",
    channel: str = "player",
) -> uuid.UUID:
    notification, _ = NotificationService(session).create(
        user_id=user_id,
        kind=kind,
        title="Título",
        body="Corpo",
        idempotency_key=key,
        data={"ref": "x"},
        channel=channel,
        now=AT,
    )
    return notification.id


def only_event(session: Session) -> OutboxEvent:
    event = session.scalar(
        select(OutboxEvent).where(OutboxEvent.event_type == "notification.created")
    )
    assert event is not None
    return event


def test_dispatch_delivers_batch_and_does_not_duplicate(db_session: Session) -> None:
    user = make_user(db_session)
    push = PushService(db_session)
    push.register_token(user, "token-android", "android", now=AT)
    push.register_token(user, "token-ios", "ios", now=AT)
    create_notification(db_session, user)
    sender = RecordingPushSender()

    report = dispatch_notifications(db_session, sender, now=AT)

    assert report == DispatchReport(processed=1, delivered=1)
    assert {item["token"] for item in sender.sent} == {"token-android", "token-ios"}
    assert only_event(db_session).status == "DISPATCHED"

    again = dispatch_notifications(db_session, sender, now=AT)
    assert again.processed == 0
    assert len(sender.sent) == 2


def test_no_tokens_marks_outbox_and_respects_retry_window(db_session: Session) -> None:
    user = make_user(db_session)
    create_notification(db_session, user)
    sender = RecordingPushSender()

    first = dispatch_notifications(db_session, sender, now=AT)

    assert first.no_tokens == 1
    event = only_event(db_session)
    assert event.status == "FAILED"
    assert event.last_error == "no_active_tokens"
    assert ensure_utc(event.available_at) == AT + timedelta(seconds=DEFAULT_RETRY_SECONDS)
    assert sender.sent == []

    # Ainda dentro da janela: não é reenviado no ciclo seguinte.
    assert dispatch_notifications(db_session, sender, now=AT).processed == 0

    PushService(db_session).register_token(user, "late-token", "android", now=AT)
    later = dispatch_notifications(
        db_session,
        sender,
        now=AT + timedelta(seconds=DEFAULT_RETRY_SECONDS + 1),
    )
    assert later.delivered == 1
    assert only_event(db_session).status == "DISPATCHED"


def test_moderation_notification_has_no_push_or_realtime(db_session: Session) -> None:
    user = make_user(db_session)
    PushService(db_session).register_token(user, "token-1", "android", now=AT)
    create_notification(db_session, user, kind="moderation_report", channel="moderation")
    sender = RecordingPushSender()
    publisher = RecordingPublisher()

    report = dispatch_notifications(db_session, sender, publisher=publisher, now=AT)

    assert report.skipped == 1
    assert sender.sent == []
    assert publisher.calls == []
    assert only_event(db_session).status == "DISPATCHED"


def test_dispatch_publishes_websocket_payload(db_session: Session) -> None:
    user = make_user(db_session)
    notification_id = create_notification(db_session, user)
    publisher = RecordingPublisher()

    report = dispatch_notifications(
        db_session,
        RecordingPushSender(),
        publisher=publisher,
        now=AT,
    )

    # Sem token o push falha, mas o tempo real não depende dele.
    assert report.published == 1
    assert report.no_tokens == 1
    published_user, payload = publisher.calls[0]
    assert published_user == user
    assert payload == {
        "type": "notification.created",
        "notification_id": str(notification_id),
        "kind": "booking_requested",
        "title": "Título",
        "body": "Corpo",
        "data": {"ref": "x"},
    }

    # O retry da Outbox não republica o mesmo evento no WebSocket.
    dispatch_notifications(
        db_session,
        RecordingPushSender(),
        publisher=publisher,
        now=AT + timedelta(seconds=DEFAULT_RETRY_SECONDS + 1),
    )
    assert len(publisher.calls) == 1


def test_dispatch_revokes_only_definitive_ticket_errors(db_session: Session) -> None:
    user = make_user(db_session)
    push = PushService(db_session)
    push.register_token(user, "good-token", "android", now=AT)
    push.register_token(user, "gone-token", "android", now=AT)
    push.register_token(user, "malformed-token", "ios", now=AT)
    create_notification(db_session, user)
    sender = RecordingPushSender(
        errors={
            "gone-token": "DeviceNotRegistered",
            "malformed-token": "InvalidPushToken",
        }
    )

    report = dispatch_notifications(db_session, sender, now=AT)

    assert report.delivered == 1
    assert report.revoked == 2
    rows = {row.token: row for row in db_session.scalars(select(DevicePushToken))}
    assert rows["gone-token"].revoked_at is not None
    assert rows["malformed-token"].revoked_at is not None
    assert rows["good-token"].revoked_at is None


def test_dispatch_transport_error_respects_retry(db_session: Session) -> None:
    user = make_user(db_session)
    PushService(db_session).register_token(user, "token-1", "android", now=AT)
    create_notification(db_session, user)
    failing = FailingSender("push_unavailable")

    first = dispatch_notifications(db_session, failing, now=AT)

    assert first.failed == 1
    event = only_event(db_session)
    assert event.status == "FAILED"
    assert event.last_error == "push_unavailable"
    assert ensure_utc(event.available_at) == AT + timedelta(seconds=DEFAULT_RETRY_SECONDS)

    retried = dispatch_notifications(
        db_session,
        RecordingPushSender(),
        now=AT + timedelta(seconds=DEFAULT_RETRY_SECONDS + 1),
    )
    assert retried.delivered == 1
    assert only_event(db_session).status == "DISPATCHED"


def test_dispatch_without_sender_preserves_outbox(db_session: Session) -> None:
    user = make_user(db_session)
    create_notification(db_session, user)

    report = dispatch_notifications(db_session, None, now=AT)

    assert report.processed == 0
    event = only_event(db_session)
    assert event.status == "PENDING"
    assert event.attempts == 0


def test_invalid_payload_fails_without_sending(db_session: Session) -> None:
    OutboxService(db_session).enqueue(
        event_type="notification.created",
        aggregate_type="notification",
        aggregate_id=None,
        payload={"title": "sem usuário"},
        now=AT,
    )
    sender = RecordingPushSender()

    report = dispatch_notifications(db_session, sender, now=AT)

    assert report.failed == 1
    assert sender.sent == []
    event = only_event(db_session)
    assert event.status == "FAILED"
    assert event.last_error == "invalid_payload"


def test_worker_runs_one_cycle_and_marks_outbox(db_session: Session) -> None:
    user = make_user(db_session)
    PushService(db_session).register_token(user, "token-1", "android", now=AT)
    create_notification(db_session, user)
    db_session.commit()
    factory = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    sender = RecordingPushSender()
    worker = NotificationDispatchWorker(
        get_settings(),
        session_factory=factory,
        sender_factory=lambda _settings: sender,
        publisher=None,
        stop_event=threading.Event(),
        interval_seconds=1,
        now=lambda: AT,
    )

    worker.run(max_cycles=1)

    assert len(sender.sent) == 1
    event = only_event(db_session)
    db_session.refresh(event)
    assert event.status == "DISPATCHED"


def test_worker_stops_before_first_cycle_when_signaled(db_session: Session) -> None:
    stop = threading.Event()
    stop.set()
    sender = RecordingPushSender()
    worker = NotificationDispatchWorker(
        get_settings(),
        session_factory=sessionmaker(bind=db_session.get_bind(), expire_on_commit=False),
        sender_factory=lambda _settings: sender,
        stop_event=stop,
    )

    worker.run()

    assert sender.sent == []


def test_worker_without_sender_does_not_touch_outbox(db_session: Session) -> None:
    user = make_user(db_session)
    create_notification(db_session, user)
    db_session.commit()
    calls: list[int] = []

    def no_sender(_settings: Any) -> None:
        calls.append(1)
        return None

    worker = NotificationDispatchWorker(
        get_settings(),
        session_factory=sessionmaker(bind=db_session.get_bind(), expire_on_commit=False),
        sender_factory=no_sender,
    )

    assert worker.run_cycle() is None
    # O worker desiste do provedor ausente em vez de repetir um ciclo inútil.
    assert worker.run_cycle() is None
    assert calls == [1]
    event = only_event(db_session)
    db_session.refresh(event)
    assert event.status == "PENDING"


class FakeSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.messages.append(payload)


def test_notification_event_payload_shape() -> None:
    payload = realtime_notifications.notification_event_payload(
        notification_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        kind="booking_accepted",
        title="Reserva aceita",
        body="Sua quadra foi confirmada",
        data={"booking_id": "b-1"},
    )

    assert payload == {
        "type": "notification.created",
        "notification_id": "00000000-0000-0000-0000-000000000001",
        "kind": "booking_accepted",
        "title": "Reserva aceita",
        "body": "Sua quadra foi confirmada",
        "data": {"booking_id": "b-1"},
    }


def test_publish_notification_event_delivers_to_connected_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fresh = ConnectionManager()
    monkeypatch.setattr(realtime_notifications, "manager", fresh)

    async def scenario() -> None:
        user_id = uuid.uuid4()
        socket = FakeSocket()
        await fresh.connect(socket, user_id)
        delivered = await realtime_notifications.publish_notification_event(
            user_id,
            {"type": "notification.created"},
        )
        assert delivered == 1
        assert socket.messages == [{"type": "notification.created"}]

    asyncio.run(scenario())


def test_sync_publisher_is_skipped_inside_running_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(realtime_notifications, "manager", ConnectionManager())

    async def scenario() -> int:
        return realtime_notifications.publish_notification_event_sync(
            uuid.uuid4(),
            {"type": "notification.created"},
        )

    assert asyncio.run(scenario()) == 0


def test_sync_publisher_without_connections_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(realtime_notifications, "manager", ConnectionManager())

    delivered = realtime_notifications.publish_notification_event_sync(
        uuid.uuid4(),
        {"type": "notification.created"},
    )

    assert delivered == 0
