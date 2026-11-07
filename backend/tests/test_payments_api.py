"""Testes HTTP do webhook Mercado Pago (Fase 14A)."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterator

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session


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


def test_webhook_requires_secret_outside_local(client: TestClient, db_session: Session) -> None:
    settings = Settings(
        environment="production",
        phone_hash_secret=SecretStr("phone-secret"),
        token_hash_secret=SecretStr("token-secret"),
        psp_provider="simulator",
        mercado_pago_webhook_secret=None,
    )
    api = api_client(client, db_session, settings)
    response = api.post(
        "/api/v1/payments/mercadopago/webhook",
        json={"id": "evt-1", "type": "order", "data": {"id": "ORD01"}},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "webhook_secret_required"
