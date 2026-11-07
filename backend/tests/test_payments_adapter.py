"""Testes do adaptador Mercado Pago e da assinatura de webhook (Fase 14A)."""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx

from app.modules.payments.adapter import (
    MercadoPagoAdapter,
    PixChargeRequest,
    SimulatorPspAdapter,
    verify_webhook_signature,
)


def test_simulator_creates_deterministic_pix_shape() -> None:
    result = SimulatorPspAdapter().create_pix_charge(
        PixChargeRequest(
            external_reference="pay-1",
            amount_cents=10000,
            description="Reserva",
            payer_email="test@example.com",
        )
    )
    assert result.provider == "simulator"
    assert result.status == "action_required"
    assert result.qr_code is not None
    assert result.qr_code_base64 is not None
    assert result.amount_cents == 10000
    assert result.external_reference == "pay-1"


def test_mercadopago_create_order_payload_and_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers.get("authorization")
        captured["idempotency"] = request.headers.get("x-idempotency-key")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "id": "ORD01",
                "status": "action_required",
                "status_detail": "waiting_transfer",
                "total_amount": "100.00",
                "external_reference": "pay-1",
                "transactions": {
                    "payments": [
                        {
                            "id": "PAY01",
                            "status": "action_required",
                            "payment_method": {
                                "id": "pix",
                                "type": "bank_transfer",
                                "qr_code": "000201PIX",
                                "qr_code_base64": "aW1hZ2Vt",
                                "ticket_url": "https://example.test/ticket",
                            },
                        }
                    ]
                },
            },
        )

    client = httpx.Client(
        base_url="https://api.mercadopago.test",
        transport=httpx.MockTransport(handler),
    )
    adapter = MercadoPagoAdapter(
        "TEST-TOKEN",
        base_url="https://api.mercadopago.test",
        notification_url="https://example.test/webhook",
        timeout_seconds=5,
        client=client,
    )
    result = adapter.create_pix_charge(
        PixChargeRequest(
            external_reference="pay-1",
            amount_cents=10000,
            description="Reserva 1",
            payer_email="test@example.com",
        )
    )

    assert captured["path"] == "/v1/orders"
    assert captured["authorization"] == "Bearer TEST-TOKEN"
    assert captured["idempotency"] == "pay-1"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["total_amount"] == "100.00"
    assert payload["payer"]["email"] == "test@example.com"
    assert payload["transactions"]["payments"][0]["payment_method"]["id"] == "pix"
    assert result.provider_order_id == "ORD01"
    assert result.provider_payment_id == "PAY01"
    assert result.qr_code == "000201PIX"
    assert result.ticket_url == "https://example.test/ticket"


def test_mercadopago_get_order_maps_processed_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/orders/ORD01"
        return httpx.Response(
            200,
            json={
                "id": "ORD01",
                "status": "processed",
                "total_amount": "100.00",
                "external_reference": "pay-1",
                "transactions": {
                    "payments": [{"id": "PAY01", "status": "processed"}],
                },
            },
        )

    client = httpx.Client(
        base_url="https://api.mercadopago.test",
        transport=httpx.MockTransport(handler),
    )
    adapter = MercadoPagoAdapter(
        "TEST-TOKEN",
        base_url="https://api.mercadopago.test",
        notification_url=None,
        timeout_seconds=5,
        client=client,
    )
    status = adapter.get_order("ORD01")
    assert status.status == "processed"
    assert status.provider_payment_id == "PAY01"
    assert status.amount_cents == 10000
    assert status.external_reference == "pay-1"


def test_webhook_signature_round_trip() -> None:
    secret = "segredo"
    timestamp = "1700000000"
    request_id = "req-1"
    data_id = "ORD01"
    manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
    signature = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()

    assert verify_webhook_signature(
        secret=secret,
        signature_header=f"ts={timestamp},v1={signature}",
        request_id=request_id,
        data_id=data_id,
    )
    assert not verify_webhook_signature(
        secret=secret,
        signature_header=f"ts={timestamp},v1=invalido",
        request_id=request_id,
        data_id=data_id,
    )
    assert not verify_webhook_signature(
        secret=secret,
        signature_header=None,
        request_id=request_id,
        data_id=data_id,
    )
