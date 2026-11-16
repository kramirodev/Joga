"""Testes HTTP do webhook Mercado Pago (Fase 14A)."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterator

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.payments.adapter import ProviderStatus, PspUnavailable
from app.modules.payments.dependency import get_psp_adapter
from app.modules.payments.models import PspWebhookEvent


def api_client(client: TestClient, db_session: Session, settings: Settings) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_settings] = lambda: settings
    return client


def signature(secret: str, timestamp: str, request_id: str, data_id: str) -> str:
    manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={timestamp},v1={digest}"


def test_webhook_rejects_invalid_signature(client: TestClient, db_session: Session) -> None:
    settings = Settings(
        environment="test",
        mercado_pago_webhook_secret=SecretStr("segredo"),
    )
    api = api_client(client, db_session, settings)
    payload = {"id": "evt-1", "type": "order", "data": {"id": "ORD01"}}

    response = api.post(
        "/api/v1/payments/mercadopago/webhook",
        json=payload,
        headers={"x-signature": "ts=1,v1=invalido", "x-request-id": "req-1"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_webhook_signature"


def test_webhook_accepts_valid_signature_and_is_idempotent(
    client: TestClient,
    db_session: Session,
) -> None:
    settings = Settings(
        environment="test",
        mercado_pago_webhook_secret=SecretStr("segredo"),
    )
    api = api_client(client, db_session, settings)
    payload = {"id": "evt-1", "type": "order", "data": {"id": "ORD01"}}
    headers = {
        "x-signature": signature("segredo", "1", "req-1", "ORD01"),
        "x-request-id": "req-1",
    }

    first = api.post("/api/v1/payments/mercadopago/webhook", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    second = api.post("/api/v1/payments/mercadopago/webhook", json=payload, headers=headers)
    assert second.status_code == 200, second.text


def test_webhook_replay_does_not_call_psp_again(client: TestClient, db_session: Session) -> None:
    settings = Settings(
        environment="test",
        mercado_pago_webhook_secret=SecretStr("segredo"),
    )
    api = api_client(client, db_session, settings)
    adapter = CountingOrderAdapter()
    client.app.dependency_overrides[get_psp_adapter] = lambda: adapter
    payload = {"id": "evt-replay", "type": "order", "data": {"id": "ORD-REPLAY"}}
    headers = {
        "x-signature": signature("segredo", "1", "req-replay", "ORD-REPLAY"),
        "x-request-id": "req-replay",
    }

    first = api.post("/api/v1/payments/mercadopago/webhook", json=payload, headers=headers)
    second = api.post("/api/v1/payments/mercadopago/webhook", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert adapter.calls == 1


def test_webhook_failure_is_persisted_with_retry_schedule(
    client: TestClient,
    db_session: Session,
) -> None:
    settings = Settings(
        environment="test",
        mercado_pago_webhook_secret=SecretStr("segredo"),
    )
    api = api_client(client, db_session, settings)
    client.app.dependency_overrides[get_psp_adapter] = lambda: FailingOrderAdapter()
    payload = {"id": "evt-fail", "type": "order", "data": {"id": "ORD-FAIL"}}
    headers = {
        "x-signature": signature("segredo", "1", "req-fail", "ORD-FAIL"),
        "x-request-id": "req-fail",
    }

    response = api.post("/api/v1/payments/mercadopago/webhook", json=payload, headers=headers)
    assert response.status_code == 503
    event = db_session.scalar(
        select(PspWebhookEvent).where(PspWebhookEvent.provider_event_id == "evt-fail")
    )
    assert event is not None
    assert event.processed_at is None
    assert event.attempts == 1
    assert event.last_error == "PspUnavailable"
    assert event.next_attempt_at is not None
    assert event.payload == payload


class CountingOrderAdapter:
    provider_name = "mercadopago"

    def __init__(self) -> None:
        self.calls = 0

    def get_order(self, provider_order_id: str) -> ProviderStatus:
        self.calls += 1
        return ProviderStatus(
            provider=self.provider_name,
            provider_order_id=provider_order_id,
            provider_payment_id=None,
            status="action_required",
            status_detail="waiting_transfer",
            amount_cents=None,
            external_reference=None,
            raw={},
        )

    def get_payment(self, provider_payment_id: str) -> ProviderStatus:
        raise AssertionError("get_payment não deve ser chamado")

    def refund(self, **_kwargs: object) -> object:
        raise AssertionError("refund não deve ser chamado")


class FailingOrderAdapter:
    provider_name = "mercadopago"

    def get_order(self, provider_order_id: str) -> ProviderStatus:
        raise PspUnavailable("fora do ar")

    def get_payment(self, provider_payment_id: str) -> ProviderStatus:
        raise PspUnavailable("fora do ar")

    def refund(self, **_kwargs: object) -> object:
        raise AssertionError("refund não deve ser chamado")


def test_webhook_requires_signature_outside_local(client: TestClient, db_session: Session) -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        phone_hash_secret=SecretStr("phone-secret"),
        token_hash_secret=SecretStr("token-secret"),
        psp_provider="mercadopago",
        mercado_pago_access_token=SecretStr("mp-access-token"),
        mercado_pago_webhook_secret=SecretStr("segredo"),
        mercado_pago_notification_url="https://api.joga.example/payments/mercadopago/webhook",
    )
    api = api_client(client, db_session, settings)
    response = api.post(
        "/api/v1/payments/mercadopago/webhook",
        json={"id": "evt-1", "type": "order", "data": {"id": "ORD01"}},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_webhook_signature"
