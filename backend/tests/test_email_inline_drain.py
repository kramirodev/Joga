"""Drenagem inline da Outbox: ciclo, lock, falha, shutdown e intervalo."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.modules.email.deliveries import EmailDeliveryService
from app.modules.email.drain_lock import email_drain_lock
from app.modules.email.inline_drain import (
    InlineEmailDrain,
    delivery_latency_percentiles,
    percentile,
)
from app.modules.email.models import EmailDelivery
from app.modules.email.sender import FakeSender
from app.modules.outbox.models import OutboxEvent
from tests.email_helpers import IDENTITY_SECRET, email_settings

BASE_TIME = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def _seed(db_session: Session) -> None:
    EmailDeliveryService(
        db_session,
        provider="fake",
        daily_budget=250,
        secret=IDENTITY_SECRET,
        max_attempts=5,
        bounce_threshold=2,
    ).enqueue(
        "email_login",
        to="jogador@example.com",
        user_id=None,
        reference="inline-1",
        code="424242",
        now=BASE_TIME,
    )
    db_session.commit()


def _drain(
    db_session: Session,
    *,
    sender: FakeSender | None = None,
    lock: Callable[[Engine | Connection], AbstractContextManager[bool]] = email_drain_lock,
    interval: int = 30,
) -> InlineEmailDrain:
    engine = db_session.get_bind()
    assert isinstance(engine, Engine)
    return InlineEmailDrain(
        email_settings(email_inline_drain_enabled=True),
        session_factory=sessionmaker(bind=engine, expire_on_commit=False),
        engine=engine,
        sender_factory=lambda _settings: sender if sender is not None else FakeSender(),
        lock=lock,
        now=lambda: BASE_TIME,
        interval_seconds=interval,
    )


@contextmanager
def _held_by_other_process() -> Iterator[bool]:
    yield False


def test_cycle_drains_pending_email_and_records_sent_at(db_session: Session) -> None:
    _seed(db_session)
    sender = FakeSender()
    drain = _drain(db_session, sender=sender)

    report = drain.run_cycle()

    assert report is not None
    assert report.sent == 1
    assert sender.last_message() is not None
    assert sender.last_message().code == "424242"
    delivery = db_session.scalar(select(EmailDelivery))
    assert delivery is not None
    db_session.refresh(delivery)
    assert delivery.status == "sent"
    assert delivery.sent_at is not None
    event = db_session.scalar(select(OutboxEvent))
    assert event is not None
    db_session.refresh(event)
    assert event.status == "DISPATCHED"


def test_cycle_skips_when_another_drainer_holds_the_lock(db_session: Session) -> None:
    _seed(db_session)
    sender = FakeSender()
    drain = _drain(db_session, sender=sender, lock=lambda _bind: _held_by_other_process())

    report = drain.run_cycle()

    assert report is None
    assert sender.attempts == []
    delivery = db_session.scalar(select(EmailDelivery))
    assert delivery is not None
    db_session.refresh(delivery)
    assert delivery.status == "queued"


def test_provider_failure_does_not_raise_and_keeps_message_queued(
    db_session: Session,
) -> None:
    _seed(db_session)
    sender = FakeSender(failures=[("provider_unavailable", False)] * 2)
    drain = _drain(db_session, sender=sender)

    report = drain.run_cycle()

    assert report is not None
    assert report.failed == 1
    assert len(sender.attempts) == 2
    assert sender.sent == []
    delivery = db_session.scalar(select(EmailDelivery))
    assert delivery is not None
    db_session.refresh(delivery)
    assert delivery.status == "failed"
    assert delivery.sent_at is None


def test_next_cycle_respects_backoff_after_failure(db_session: Session) -> None:
    _seed(db_session)
    sender = FakeSender(failures=[("provider_unavailable", False)] * 2)
    drain = _drain(db_session, sender=sender)

    drain.run_cycle()
    drain.run_cycle()

    assert sender.sent == []
    assert len(sender.attempts) == 2
    event = db_session.scalar(select(OutboxEvent))
    assert event is not None
    db_session.refresh(event)
    assert event.status == "FAILED"


def test_start_and_stop_cancel_the_task_without_leaking(db_session: Session) -> None:
    drain = _drain(db_session)

    async def scenario() -> None:
        await drain.start()
        assert drain.running
        task = drain._task  # noqa: SLF001 - o teste verifica o ciclo de vida
        await drain.stop()
        assert not drain.running
        assert task is not None
        assert task.done()

    asyncio.run(scenario())


def test_invalid_interval_fails_at_startup() -> None:
    for value in (5, 9, 301):
        with pytest.raises(ValidationError):
            email_settings(email_inline_drain_interval_seconds=value)


def test_constructor_rejects_invalid_interval(db_session: Session) -> None:
    with pytest.raises(ValueError):
        _drain(db_session, interval=5)


def test_latency_percentiles_use_sent_at(db_session: Session) -> None:
    _seed(db_session)
    drain = _drain(db_session, sender=FakeSender())
    drain.run_cycle()

    samples, p50, p95 = delivery_latency_percentiles(
        db_session,
        day_start=BASE_TIME.replace(hour=0, minute=0, second=0, microsecond=0),
    )

    assert samples == 1
    assert p50 == 0.0
    assert p95 == 0.0


def test_percentile_interpolates_between_samples() -> None:
    assert percentile([1.0], 0.95) == 1.0
    assert percentile([0.0, 10.0], 0.50) == 5.0
    assert percentile([0.0, 10.0], 0.95) == pytest.approx(9.5)
    with pytest.raises(ValueError):
        percentile([], 0.5)


def test_app_keeps_inline_drain_disabled_by_default(client) -> None:
    assert client.app.state.email_inline_drain is None
