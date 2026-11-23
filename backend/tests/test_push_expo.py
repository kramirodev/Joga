"""Testes do adaptador do Expo Push Service e da revogação de tokens."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.push.expo import (
    DEFAULT_EXPO_PUSH_URL,
    MAX_BATCH_SIZE,
    ExpoPushSender,
    build_expo_push_sender,
)
from app.modules.push.service import (
    PushError,
    PushMessage,
    PushService,
    RecordingPushSender,
)
from app.modules.social.models import DevicePushToken
from tests.helpers_results import END, make_user

AT = END + timedelta(minutes=2)
URL = DEFAULT_EXPO_PUSH_URL


def message(token: str = "ExponentPushToken[a]", *, channel_id: str | None = None) -> PushMessage:
    return PushMessage(
        token=token,
        title="Título",
        body="Corpo",
        data={"ref": "1"},
        channel_id=channel_id,
    )


def sender_with(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    access_token: str | None = None,
) -> ExpoPushSender:
    return ExpoPushSender(
        URL,
        access_token=access_token,
        timeout_seconds=1,
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
            timeout=1,
            trust_env=False,
        ),
    )


def ok_handler(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    return httpx.Response(
        200,
        json={
            "data": [{"status": "ok", "id": f"ticket-{index}"} for index, _ in enumerate(payload)]
        },
    )


def test_send_batch_ok_builds_expo_payload() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={"data": [{"status": "ok", "id": "t-1"}, {"status": "ok", "id": "t-2"}]},
        )

    sender = sender_with(handler)
    try:
        tickets = sender.send_batch([message("token-a"), message("token-b")])
    finally:
        sender.close()

    assert [ticket.ok for ticket in tickets] == [True, True]
    assert [ticket.ticket_id for ticket in tickets] == ["t-1", "t-2"]
    request = captured[0]
    assert str(request.url) == URL
    assert request.headers["accept"] == "application/json"
    assert request.headers["content-type"] == "application/json"
    assert "authorization" not in request.headers
    payload = json.loads(request.content)
    assert payload[0]["to"] == "token-a"
    assert payload[0]["title"] == "Título"
    assert payload[0]["body"] == "Corpo"
    assert payload[0]["data"] == {"ref": "1"}
    assert payload[0]["sound"] == "default"
    assert "channelId" not in payload[0]


def test_send_uses_access_token_and_channel_id() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"data": [{"status": "ok", "id": "t-1"}]})

    sender = sender_with(handler, access_token="expo-secret-token")
    try:
        sender.send_batch([message(channel_id="default")])
    finally:
        sender.close()

    assert captured[0].headers["authorization"] == "Bearer expo-secret-token"
    assert json.loads(captured[0].content)[0]["channelId"] == "default"


def test_send_batch_chunks_at_provider_limit() -> None:
    sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        sizes.append(len(payload))
        return httpx.Response(
            200,
            json={"data": [{"status": "ok"} for _ in payload]},
        )

    sender = sender_with(handler)
    try:
        tickets = sender.send_batch(
            [message(f"token-{index}") for index in range(MAX_BATCH_SIZE + 1)]
        )
    finally:
        sender.close()

    assert sizes == [MAX_BATCH_SIZE, 1]
    assert len(tickets) == MAX_BATCH_SIZE + 1


def test_single_message_object_response_is_accepted() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"status": "ok", "id": "single"}})

    sender = sender_with(handler)
    try:
        tickets = sender.send_batch([message()])
    finally:
        sender.close()

    assert len(tickets) == 1
    assert tickets[0].ok is True
    assert tickets[0].ticket_id == "single"


@pytest.mark.parametrize(
    ("details", "expected"),
    [
        ("DeviceNotRegistered", "DeviceNotRegistered"),
        ("InvalidPushToken", "InvalidPushToken"),
        ("MessageTooBig", "MessageTooBig"),
        ("UnexpectedProviderCode", "push_error"),
    ],
)
def test_ticket_error_mapping_is_safe(details: str, expected: str) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"status": "error", "details": {"error": details}}]},
        )

    sender = sender_with(handler)
    try:
        tickets = sender.send_batch([message()])
    finally:
        sender.close()

    assert tickets[0].ok is False
    assert tickets[0].error == expected


@pytest.mark.parametrize(
    ("status_code", "code"),
    [
        (400, "push_rejected"),
        (401, "push_unauthorized"),
        (403, "push_unauthorized"),
        (429, "push_rate_limited"),
        (500, "push_unavailable"),
        (503, "push_unavailable"),
        (418, "push_http_418"),
    ],
)
def test_http_error_codes_are_internal(status_code: int, code: str) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="provedor fora do ar")

    sender = sender_with(handler)
    try:
        with pytest.raises(PushError, match=code):
            sender.send_batch([message()])
    finally:
        sender.close()


def test_transport_error_never_leaks_details() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("host secreto indisponível")

    sender = sender_with(handler)
    try:
        with pytest.raises(PushError, match="push_unavailable") as raised:
            sender.send_batch([message()])
    finally:
        sender.close()

    assert "secreto" not in str(raised.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="não é json"),
        httpx.Response(200, json={"data": []}),
        httpx.Response(200, json={"data": [{"status": "ok"}, {"status": "ok"}]}),
    ],
)
def test_malformed_responses_fail_closed(response: httpx.Response) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return response

    sender = sender_with(handler)
    try:
        with pytest.raises(PushError, match="push_invalid_response"):
            sender.send_batch([message()])
    finally:
        sender.close()


def test_device_not_registered_revokes_token(db_session: Session) -> None:
    user = make_user(db_session)
    PushService(db_session).register_token(user, "gone-token", "android", now=AT)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"status": "error", "details": {"error": "DeviceNotRegistered"}}]},
        )

    sender = sender_with(handler)
    try:
        tickets = PushService(db_session, sender).send_to_user(
            user,
            title="Título",
            body="Corpo",
            data={},
            now=AT,
        )
    finally:
        sender.close()

    assert tickets[0].error == "DeviceNotRegistered"
    row = db_session.scalar(select(DevicePushToken).where(DevicePushToken.token == "gone-token"))
    assert row is not None and row.revoked_at is not None


def test_invalid_push_token_revokes_token(db_session: Session) -> None:
    user = make_user(db_session)
    PushService(db_session).register_token(user, "malformed-token", "ios", now=AT)
    sender = RecordingPushSender(errors={"malformed-token": "InvalidPushToken"})

    tickets = PushService(db_session, sender).send_to_user(
        user,
        title="Título",
        body="Corpo",
        data={},
        now=AT,
    )

    assert tickets[0].should_revoke is True
    row = db_session.scalar(
        select(DevicePushToken).where(DevicePushToken.token == "malformed-token")
    )
    assert row is not None and row.revoked_at is not None


def test_temporary_ticket_error_keeps_token_active(db_session: Session) -> None:
    user = make_user(db_session)
    PushService(db_session).register_token(user, "busy-token", "android", now=AT)
    sender = RecordingPushSender(errors={"busy-token": "MessageRateExceeded"})

    PushService(db_session, sender).send_to_user(
        user,
        title="Título",
        body="Corpo",
        data={},
        now=AT,
    )

    row = db_session.scalar(select(DevicePushToken).where(DevicePushToken.token == "busy-token"))
    assert row is not None and row.revoked_at is None


def test_builder_returns_none_when_url_is_disabled() -> None:
    settings = Settings(_env_file=None, expo_push_url=None)

    assert build_expo_push_sender(settings) is None


def test_builder_uses_default_url_and_hides_access_token() -> None:
    settings = Settings(
        _env_file=None,
        expo_access_token="expo-secret-token",
    )

    sender = build_expo_push_sender(settings)
    assert sender is not None
    assert sender.url == URL
    assert "expo-secret-token" not in repr(settings)
    sender.close()
