"""Fila, idempotência, orçamento e provedores de e-mail (sem rede)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.email.alerts import primary_email
from app.modules.email.deliveries import (
    EmailBudgetExhausted,
    EmailDeliveryService,
    mark_hard_bounce,
)
from app.modules.email.dispatcher import dispatch_email_deliveries
from app.modules.email.models import EmailDelivery, UserEmail
from app.modules.email.sender import (
    BREVO_ENDPOINT,
    RESEND_ENDPOINT,
    BrevoSender,
    EmailMessage,
    EmailSenderError,
    FakeSender,
    ResendSender,
    build_email_sender,
)
from app.modules.identity.clock import ensure_utc
from app.modules.identity.events import EMAIL_BUDGET_WARNING
from app.modules.identity.models import SecurityEvent
from app.modules.outbox.models import OutboxEvent
from scripts.deliver_emails import run_once_with_sender
from tests.email_helpers import IDENTITY_SECRET, email_settings, seed_user_with_email

BASE_TIME = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def build_service(session: Session, *, budget: int = 250) -> EmailDeliveryService:
    return EmailDeliveryService(
        session,
        provider="fake",
        daily_budget=budget,
        secret=IDENTITY_SECRET,
        max_attempts=5,
        bounce_threshold=2,
    )


def test_enqueue_writes_delivery_and_outbox_without_plain_address(
    db_session: Session,
) -> None:
    delivery = build_service(db_session).enqueue(
        "email_verification",
        to="jogador@example.com",
        user_id=None,
        reference="challenge-1",
        code="123456",
        context={"ttl_minutes": 10},
        now=BASE_TIME,
    )
    db_session.flush()

    assert delivery.status == "queued"
    assert delivery.provider == "fake"
    assert delivery.email_hash != "jogador@example.com"
    assert "jogador@example.com" not in repr(delivery.__dict__)
    assert "123456" not in repr(delivery.__dict__)

    event = db_session.scalar(
        select(OutboxEvent).where(OutboxEvent.event_type == "email.delivery_requested")
    )
    assert event is not None
    assert event.payload["code"] == "123456"
    assert event.payload["to"] == "jogador@example.com"


def test_enqueue_is_idempotent_by_user_kind_and_reference(db_session: Session) -> None:
    service = build_service(db_session)
    first = service.enqueue(
        "welcome",
        to="jogador@example.com",
        user_id=None,
        reference="same",
        context={},
        now=BASE_TIME,
    )
    second = service.enqueue(
        "welcome",
        to="jogador@example.com",
        user_id=None,
        reference="same",
        context={},
        now=BASE_TIME,
    )
    db_session.flush()

    assert first.id == second.id
    events = list(
        db_session.scalars(
            select(OutboxEvent).where(OutboxEvent.event_type == "email.delivery_requested")
        )
    )
    assert len(events) == 1


def test_budget_warns_at_80_percent_and_blocks_new_delivery(db_session: Session) -> None:
    service = build_service(db_session, budget=5)
    for index in range(4):
        service.enqueue(
            "welcome",
            to=f"j{index}@example.com",
            user_id=None,
            reference=f"w{index}",
            now=BASE_TIME,
        )
    db_session.flush()
    warnings = list(
        db_session.scalars(
            select(SecurityEvent).where(SecurityEvent.event_type == EMAIL_BUDGET_WARNING)
        )
    )
    assert len(warnings) == 1

    service.enqueue(
        "welcome",
        to="quinto@example.com",
        user_id=None,
        reference="w4",
        now=BASE_TIME,
    )
    with pytest.raises(EmailBudgetExhausted):
        service.enqueue(
            "welcome",
            to="sexto@example.com",
            user_id=None,
            reference="w5",
            now=BASE_TIME,
        )
    db_session.flush()
    assert len(list(db_session.scalars(select(EmailDelivery)))) == 5


def test_dispatch_sends_once_and_retry_does_not_duplicate(db_session: Session) -> None:
    service = build_service(db_session)
    service.enqueue(
        "email_login",
        to="jogador@example.com",
        user_id=None,
        reference="challenge-2",
        code="111111",
        context={"ttl_minutes": 10},
        now=BASE_TIME,
    )
    db_session.commit()

    sender = FakeSender()
    first = dispatch_email_deliveries(db_session, sender, now=BASE_TIME)
    db_session.commit()
    second = dispatch_email_deliveries(db_session, sender, now=BASE_TIME)
    db_session.commit()

    assert first.sent == 1
    assert second.sent == 0
    assert len(sender.sent) == 1
    assert sender.sent[0].code == "111111"
    delivery = db_session.scalar(select(EmailDelivery))
    assert delivery is not None and delivery.status == "sent"
    event = db_session.scalar(select(OutboxEvent))
    assert event is not None and event.status == "DISPATCHED"


def test_transient_failure_retries_once_immediately(db_session: Session) -> None:
    build_service(db_session).enqueue(
        "email_login",
        to="jogador@example.com",
        user_id=None,
        reference="challenge-3",
        code="222222",
        now=BASE_TIME,
    )
    db_session.commit()

    sender = FakeSender(failures=[("timeout", False)])
    report = dispatch_email_deliveries(db_session, sender, now=BASE_TIME)
    db_session.commit()

    assert report.sent == 1
    delivery = db_session.scalar(select(EmailDelivery))
    assert delivery is not None
    assert delivery.status == "sent" and delivery.attempts == 2


def test_persistent_failure_stays_in_queue_with_backoff(db_session: Session) -> None:
    build_service(db_session).enqueue(
        "email_login",
        to="jogador@example.com",
        user_id=None,
        reference="challenge-4",
        code="333333",
        now=BASE_TIME,
    )
    db_session.commit()

    sender = FakeSender(failures=[("provider_unavailable", False)] * 2)
    report = dispatch_email_deliveries(db_session, sender, max_attempts=2, now=BASE_TIME)
    db_session.commit()

    assert report.failed == 1
    delivery = db_session.scalar(select(EmailDelivery))
    assert delivery is not None
    assert delivery.status == "failed" and delivery.attempts == 2
    event = db_session.scalar(select(OutboxEvent))
    assert event is not None and event.status == "FAILED"
    assert ensure_utc(event.available_at) > BASE_TIME


def test_permanent_rejection_marks_credential_undeliverable_after_threshold(
    db_session: Session,
) -> None:
    user_id, _ = seed_user_with_email(db_session, "jogador@example.com")
    build_service(db_session).enqueue(
        "email_login",
        to="jogador@example.com",
        user_id=user_id,
        reference="challenge-5",
        code="444444",
        now=BASE_TIME,
    )
    db_session.commit()

    sender = FakeSender(failures=[("provider_rejected", True)])
    report = dispatch_email_deliveries(
        db_session,
        sender,
        bounce_threshold=2,
        now=BASE_TIME,
    )
    db_session.commit()

    assert report.bounced == 1
    credential = db_session.scalar(select(UserEmail))
    assert credential is not None
    assert credential.hard_bounce_count == 1
    assert credential.undeliverable_at is None

    mark_hard_bounce(
        db_session,
        email_normalized="jogador@example.com",
        user_id=user_id,
        kind="email_login",
        threshold=2,
        now=BASE_TIME,
    )
    db_session.commit()
    assert credential.undeliverable_at is not None


def test_primary_email_returns_only_active_primary(db_session: Session) -> None:
    user_id, _ = seed_user_with_email(db_session, "jogador@example.com")
    assert primary_email(db_session, user_id) == "jogador@example.com"


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _message() -> EmailMessage:
    return EmailMessage(
        to="destino@example.com",
        subject="Assunto fixo",
        text="texto",
        html="<p>texto</p>",
        kind="email_login",
        code="123456",
    )


def test_brevo_sender_builds_expected_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["key"] = request.headers.get("api-key")
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"messageId": "brevo-1"})

    sender = BrevoSender(
        api_key="secret-key",
        from_email="no-reply@joga.example",
        from_name="JOGA",
        reply_to="suporte@joga.example",
        client=_mock_client(handler),
    )
    assert sender.send(_message()) == "brevo-1"
    assert captured["url"] == BREVO_ENDPOINT
    assert captured["key"] == "secret-key"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["to"] == [{"email": "destino@example.com"}]
    assert body["sender"] == {"email": "no-reply@joga.example", "name": "JOGA"}
    assert body["replyTo"] == {"email": "suporte@joga.example"}


def test_resend_sender_builds_expected_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "resend-1"})

    sender = ResendSender(
        api_key="secret-key",
        from_email="no-reply@joga.example",
        from_name="JOGA",
        client=_mock_client(handler),
    )
    assert sender.send(_message()) == "resend-1"
    assert captured["url"] == RESEND_ENDPOINT
    assert captured["auth"] == "Bearer secret-key"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["from"] == "JOGA <no-reply@joga.example>"
    assert body["to"] == ["destino@example.com"]


@pytest.mark.parametrize(
    ("status_code", "code", "permanent"),
    [
        (429, "provider_rate_limited", False),
        (500, "provider_unavailable", False),
        (401, "provider_auth_failed", True),
        (422, "provider_rejected", True),
    ],
)
def test_provider_error_classification(status_code: int, code: str, permanent: bool) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"message": "provider body"})

    sender = BrevoSender(
        api_key="secret-key",
        from_email="no-reply@joga.example",
        from_name="JOGA",
        client=_mock_client(handler),
    )
    with pytest.raises(EmailSenderError) as error:
        sender.send(_message())
    assert error.value.code == code
    assert error.value.permanent is permanent
    assert "provider body" not in str(error.value)


def test_provider_timeout_is_transient() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    sender = BrevoSender(
        api_key="secret-key",
        from_email="no-reply@joga.example",
        from_name="JOGA",
        client=_mock_client(handler),
    )
    with pytest.raises(EmailSenderError) as error:
        sender.send(_message())
    assert error.value.code == "timeout"
    assert error.value.permanent is False


def test_build_email_sender_respects_provider_and_normalizes_from() -> None:
    brevo = build_email_sender(
        email_settings(
            email_provider="brevo",
            email_from=" No-Reply@Joga.Example ",
        )
    )
    assert isinstance(brevo, BrevoSender)
    assert brevo._from_email == "no-reply@joga.example"
    brevo.close()

    assert isinstance(build_email_sender(email_settings()), FakeSender)
    assert (
        build_email_sender(
            email_settings(
                email_provider="none",
                auth_email_enabled=False,
                auth_phone_enabled=True,
                allow_phone_registration=True,
            )
        )
        is None
    )


def test_fake_sender_never_opens_network() -> None:
    sender = FakeSender()
    assert sender.send(_message()) == "fake-1"
    assert sender.last_message() is not None
    assert sender.last_message().code == "123456"
    assert sender.last_message().code not in repr(sender.last_message())


def test_scheduled_drain_uses_fake_sender_without_provider(
    db_session: Session,
) -> None:
    build_service(db_session).enqueue(
        "email_verification",
        to="agendado@example.com",
        user_id=None,
        reference="scheduled-1",
        code="555555",
        now=BASE_TIME,
    )
    db_session.commit()

    sender = FakeSender()
    report = run_once_with_sender(
        db_session,
        sender,
        max_attempts=5,
        bounce_threshold=3,
        now=BASE_TIME,
    )

    assert report.sent == 1
    assert sender.last_message() is not None
    assert sender.last_message().code == "555555"
    delivery = db_session.scalar(select(EmailDelivery))
    assert delivery is not None and delivery.status == "sent"
    event = db_session.scalar(select(OutboxEvent))
    assert event is not None and event.status == "DISPATCHED"


def test_retry_delay_grows_and_is_capped() -> None:
    service = EmailDeliveryService(
        None,  # type: ignore[arg-type]
        provider="fake",
        daily_budget=10,
        secret=IDENTITY_SECRET,
    )
    assert service.next_retry_delay(1) == timedelta(seconds=60)
    assert service.next_retry_delay(2) == timedelta(seconds=120)
    assert service.next_retry_delay(20) == timedelta(seconds=3_600)
