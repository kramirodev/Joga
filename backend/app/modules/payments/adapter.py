"""Adaptadores de PSP: simulador local e Mercado Pago Orders API (Fase 14A)."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx

from app.core.config import Settings, get_settings


class PspError(Exception):
    """Erro base de comunicação com o PSP."""


class PspUnavailable(PspError):
    """PSP indisponível ou credenciais ausentes."""


class PspInvalidResponse(PspError):
    """Resposta do PSP fora do contrato esperado."""


@dataclass(frozen=True)
class PixChargeRequest:
    """Dados mínimos para criar uma cobrança Pix por participante."""

    external_reference: str
    amount_cents: int
    description: str
    payer_email: str
    expiration_minutes: int = 30
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class PixChargeResult:
    """Cobrança Pix criada no PSP."""

    provider: str
    provider_order_id: str
    provider_payment_id: str | None
    status: str
    status_detail: str | None
    qr_code: str | None
    qr_code_base64: str | None
    ticket_url: str | None
    expires_at: datetime | None
    amount_cents: int
    external_reference: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class ProviderStatus:
    """Status atual de uma ordem/pagamento no PSP."""

    provider: str
    provider_order_id: str
    provider_payment_id: str | None
    status: str
    status_detail: str | None
    amount_cents: int | None
    external_reference: str | None
    raw: dict[str, Any]


class PspAdapter(Protocol):
    """Contrato mínimo para cobrança Pix e consulta de status."""

    provider_name: str

    def create_pix_charge(self, request: PixChargeRequest) -> PixChargeResult: ...

    def get_order(self, provider_order_id: str) -> ProviderStatus: ...

    def get_payment(self, provider_payment_id: str) -> ProviderStatus: ...


class SimulatorPspAdapter:
    """PSP simulado, sem rede, para desenvolvimento e CI."""

    provider_name = "simulator"

    def create_pix_charge(self, request: PixChargeRequest) -> PixChargeResult:
        order_id = f"SIM-{uuid.uuid4().hex.upper()}"
        payment_id = f"SIMPAY-{uuid.uuid4().hex.upper()}"
        return PixChargeResult(
            provider=self.provider_name,
            provider_order_id=order_id,
            provider_payment_id=payment_id,
            status="action_required",
            status_detail="waiting_transfer",
            qr_code=f"000201SIMULADO{order_id}",
            qr_code_base64="c2ltdWxhZG9y",
            ticket_url=None,
            expires_at=datetime.now(UTC) + timedelta(minutes=request.expiration_minutes),
            amount_cents=request.amount_cents,
            external_reference=request.external_reference,
            raw={"simulated": True, "external_reference": request.external_reference},
        )

    def get_order(self, provider_order_id: str) -> ProviderStatus:
        return ProviderStatus(
            provider=self.provider_name,
            provider_order_id=provider_order_id,
            provider_payment_id=None,
            status="action_required",
            status_detail="waiting_transfer",
            amount_cents=None,
            external_reference=None,
            raw={"simulated": True},
        )

    def get_payment(self, provider_payment_id: str) -> ProviderStatus:
        return ProviderStatus(
            provider=self.provider_name,
            provider_order_id=provider_payment_id,
            provider_payment_id=provider_payment_id,
            status="action_required",
            status_detail="waiting_transfer",
            amount_cents=None,
            external_reference=None,
            raw={"simulated": True},
        )


class MercadoPagoAdapter:
    """Mercado Pago Checkout Transparente via Orders API (Pix).

    Sem split nesta fase. O token deve ser de sandbox; nenhuma cobrança real
    deve ser acionada no protótipo/beta sem autorização.
    """

    provider_name = "mercadopago"

    def __init__(
        self,
        access_token: str,
        *,
        base_url: str,
        notification_url: str | None,
        timeout_seconds: int,
        client: httpx.Client | None = None,
    ) -> None:
        if not access_token:
            raise PspUnavailable("token do Mercado Pago ausente")
        self.base_url = base_url.rstrip("/")
        self.notification_url = notification_url
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._client = client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout_seconds,
            headers=self._headers,
        )

    def close(self) -> None:
        self._client.close()

    def create_pix_charge(self, request: PixChargeRequest) -> PixChargeResult:
        payload: dict[str, Any] = {
            "type": "online",
            "total_amount": _amount_string(request.amount_cents),
            "external_reference": request.external_reference,
            "processing_mode": "automatic",
            "transactions": {
                "payments": [
                    {
                        "amount": _amount_string(request.amount_cents),
                        "payment_method": {"id": "pix", "type": "bank_transfer"},
                        "expiration_time": f"PT{request.expiration_minutes}M",
                    }
                ]
            },
            "payer": {"email": request.payer_email},
        }
        if request.description:
            payload["description"] = request.description
        if request.metadata:
            payload["metadata"] = request.metadata
        if self.notification_url:
            payload["notification_url"] = self.notification_url
        headers = {**self._headers, "X-Idempotency-Key": request.external_reference}
        try:
            response = self._client.post("/v1/orders", json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PspUnavailable("falha ao criar ordem no Mercado Pago") from exc
        try:
            return _parse_order(response.json(), request)
        except (KeyError, TypeError, ValueError) as exc:
            raise PspInvalidResponse("resposta inválida do Mercado Pago") from exc

    def get_order(self, provider_order_id: str) -> ProviderStatus:
        try:
            response = self._client.get(f"/v1/orders/{provider_order_id}", headers=self._headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PspUnavailable("falha ao consultar ordem no Mercado Pago") from exc
        try:
            return _parse_status(response.json())
        except (KeyError, TypeError, ValueError) as exc:
            raise PspInvalidResponse("resposta inválida do Mercado Pago") from exc

    def get_payment(self, provider_payment_id: str) -> ProviderStatus:
        try:
            response = self._client.get(
                f"/v1/payments/{provider_payment_id}", headers=self._headers
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PspUnavailable("falha ao consultar pagamento no Mercado Pago") from exc
        try:
            return _parse_payment_status(response.json())
        except (KeyError, TypeError, ValueError) as exc:
            raise PspInvalidResponse("resposta inválida do Mercado Pago") from exc


def _parse_order(raw: dict[str, Any], request: PixChargeRequest) -> PixChargeResult:
    payments = (raw.get("transactions") or {}).get("payments") or []
    payment = payments[0] if payments else {}
    payment_method = payment.get("payment_method") or {}
    status = str(raw.get("status") or payment.get("status") or "action_required")
    status_detail = raw.get("status_detail") or payment.get("status_detail")
    order_id = str(raw["id"])
    provider_payment_id = str(payment["id"]) if payment.get("id") else None
    return PixChargeResult(
        provider="mercadopago",
        provider_order_id=order_id,
        provider_payment_id=provider_payment_id,
        status=status,
        status_detail=str(status_detail) if status_detail else None,
        qr_code=payment_method.get("qr_code"),
        qr_code_base64=payment_method.get("qr_code_base64"),
        ticket_url=payment_method.get("ticket_url"),
        expires_at=datetime.now(UTC) + timedelta(minutes=request.expiration_minutes),
        amount_cents=request.amount_cents,
        external_reference=request.external_reference,
        raw=raw,
    )


def _parse_status(raw: dict[str, Any]) -> ProviderStatus:
    payments = (raw.get("transactions") or {}).get("payments") or []
    payment = payments[0] if payments else {}
    total = raw.get("total_amount") or payment.get("amount")
    return ProviderStatus(
        provider="mercadopago",
        provider_order_id=str(raw["id"]),
        provider_payment_id=str(payment["id"]) if payment.get("id") else None,
        status=str(raw.get("status") or payment.get("status") or "unknown"),
        status_detail=raw.get("status_detail") or payment.get("status_detail"),
        amount_cents=_amount_cents(total) if total is not None else None,
        external_reference=raw.get("external_reference"),
        raw=raw,
    )


def _parse_payment_status(raw: dict[str, Any]) -> ProviderStatus:
    total = raw.get("transaction_amount")
    return ProviderStatus(
        provider="mercadopago",
        provider_order_id=str(raw.get("order_id") or raw["id"]),
        provider_payment_id=str(raw["id"]),
        status=str(raw.get("status") or "unknown"),
        status_detail=raw.get("status_detail"),
        amount_cents=_amount_cents(total) if total is not None else None,
        external_reference=raw.get("external_reference"),
        raw=raw,
    )


def _amount_string(cents: int) -> str:
    return f"{cents / 100:.2f}"


def _amount_cents(value: Any) -> int:
    return round(float(value) * 100)


def verify_webhook_signature(
    *,
    secret: str,
    signature_header: str | None,
    request_id: str | None,
    data_id: str | None,
) -> bool:
    """Valida o formato HMAC do webhook do Mercado Pago.

    Formato esperado: `ts=...,v1=...`. Se o segredo não estiver configurado,
    o chamador decide se aceita apenas em ambiente local/teste.
    """

    if not signature_header or not request_id or not data_id:
        return False
    parts = {}
    for item in signature_header.split(","):
        key, _, value = item.strip().partition("=")
        if key and value:
            parts[key] = value
    timestamp = parts.get("ts")
    received = parts.get("v1")
    if not timestamp or not received:
        return False
    manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)


def psp_provider_name() -> str:
    return get_settings().psp_provider


def build_psp_adapter(settings: Settings | None = None) -> PspAdapter:
    resolved = settings or get_settings()
    if resolved.psp_provider == "simulator":
        return SimulatorPspAdapter()
    token = (
        resolved.mercado_pago_access_token.get_secret_value()
        if resolved.mercado_pago_access_token is not None
        else ""
    )
    return MercadoPagoAdapter(
        token,
        base_url=resolved.mercado_pago_base_url,
        notification_url=resolved.mercado_pago_notification_url,
        timeout_seconds=resolved.psp_timeout_seconds,
    )


__all__ = [
    "MercadoPagoAdapter",
    "PixChargeRequest",
    "PixChargeResult",
    "ProviderStatus",
    "PspAdapter",
    "PspError",
    "PspInvalidResponse",
    "PspUnavailable",
    "SimulatorPspAdapter",
    "build_psp_adapter",
    "verify_webhook_signature",
]
