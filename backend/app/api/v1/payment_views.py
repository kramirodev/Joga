"""View compartilhada de cobrança Pix de compra (ingresso e passe)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.modules.payments.models import PurchasePayment


class PurchasePaymentView(BaseModel):
    provider: str | None
    provider_status: str | None
    qr_code: str | None
    qr_code_base64: str | None
    ticket_url: str | None
    expires_at: datetime | None
    paid: bool


def purchase_payment_view(payment: PurchasePayment | None) -> PurchasePaymentView | None:
    if payment is None:
        return None
    return PurchasePaymentView(
        provider=payment.provider,
        provider_status=payment.provider_status,
        qr_code=payment.qr_code,
        qr_code_base64=payment.qr_code_base64,
        ticket_url=payment.ticket_url,
        expires_at=payment.expires_at,
        paid=payment.paid_at is not None,
    )
