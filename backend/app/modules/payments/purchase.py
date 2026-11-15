"""Cobrança Pix de compras de ingresso e de passe (Fase 14D.13).

O fluxo de ingresso não tem reserva, participante nem repasse. A cobrança é
uma única ordem Pix por compra, conciliada por ``kind`` + ``reference_id``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import utcnow
from app.modules.identity.models import User
from app.modules.passes.service import PassNotFound, activate_subscription
from app.modules.payments.adapter import (
    PixChargeRequest,
    ProviderStatus,
    PspAdapter,
)
from app.modules.payments.models import PurchasePayment
from app.modules.payments.status import map_provider_status
from app.modules.tickets.service import PurchaseNotFound, confirm_purchase


class PurchasePaymentError(Exception):
    """Erro de cobrança de compra."""


class PayerEmailRequired(PurchasePaymentError):
    """O Mercado Pago exige e-mail do pagador e o usuário não informou."""


class PurchasePaymentNotFound(PurchasePaymentError):
    """Cobrança inexistente."""


class PurchasePaymentMismatch(PurchasePaymentError):
    """Valor ou referência divergente do registro interno."""


def payment_for(session: Session, kind: str, reference_id: uuid.UUID) -> PurchasePayment | None:
    return session.scalars(
        select(PurchasePayment).where(
            PurchasePayment.kind == kind,
            PurchasePayment.reference_id == reference_id,
        )
    ).first()


def find_by_provider(
    session: Session,
    *,
    provider_order_id: str | None,
    provider_payment_id: str | None,
) -> PurchasePayment | None:
    payment: PurchasePayment | None = None
    if provider_order_id is not None:
        payment = session.scalars(
            select(PurchasePayment).where(PurchasePayment.provider_order_id == provider_order_id)
        ).first()
    if payment is None and provider_payment_id is not None:
        payment = session.scalars(
            select(PurchasePayment).where(
                PurchasePayment.provider_payment_id == provider_payment_id
            )
        ).first()
    return payment


def open_charge(
    session: Session,
    adapter: PspAdapter,
    *,
    kind: str,
    reference_id: uuid.UUID,
    user_id: uuid.UUID,
    amount_cents: int,
    description: str,
) -> PurchasePayment:
    """Abre (ou reaproveita) a ordem Pix de uma compra. Idempotente por compra."""

    if amount_cents <= 0:
        raise PurchasePaymentError("amount_invalid")
    existing = payment_for(session, kind, reference_id)
    if existing is not None:
        if existing.amount_cents != amount_cents:
            raise PurchasePaymentMismatch
        return existing

    payment = PurchasePayment(
        user_id=user_id,
        kind=kind,
        reference_id=reference_id,
        amount_cents=amount_cents,
    )
    session.add(payment)
    session.flush()

    payer_email: str | None = None
    if adapter.provider_name == "mercadopago":
        payer_email = session.scalar(select(User.email).where(User.id == user_id))
        if not payer_email:
            raise PayerEmailRequired
    result = adapter.create_pix_charge(
        PixChargeRequest(
            external_reference=f"{kind}:{reference_id}",
            amount_cents=amount_cents,
            description=description,
            payer_email=payer_email or f"user-{user_id}@simulator.invalid",
            expiration_minutes=30,
            metadata={
                "kind": kind,
                "reference_id": str(reference_id),
                "user_id": str(user_id),
            },
        )
    )
    if result.amount_cents != amount_cents:
        raise PurchasePaymentMismatch

    payment.provider = result.provider
    payment.provider_order_id = result.provider_order_id
    payment.provider_payment_id = result.provider_payment_id
    payment.provider_status = result.status
    payment.payer_email = payer_email
    payment.qr_code = result.qr_code
    payment.qr_code_base64 = result.qr_code_base64
    payment.ticket_url = result.ticket_url
    payment.expires_at = result.expires_at
    payment.last_synced_at = utcnow()
    session.flush()
    return payment


def sync_charge(session: Session, adapter: PspAdapter, payment: PurchasePayment) -> str:
    """Consulta o PSP e aplica o status. Devolve o status interno."""

    if payment.provider_order_id is None:
        raise PurchasePaymentNotFound
    status = adapter.get_order(payment.provider_order_id)
    return apply_status(session, payment, status)


def apply_status(
    session: Session,
    payment: PurchasePayment,
    status: ProviderStatus,
    *,
    now: datetime | None = None,
) -> str:
    """Aplica o status do PSP. Repetição não duplica ingresso nem assinatura."""

    moment = now or utcnow()
    if status.amount_cents is not None and status.amount_cents != payment.amount_cents:
        raise PurchasePaymentMismatch
    if (
        status.external_reference is not None
        and status.external_reference != f"{payment.kind}:{payment.reference_id}"
    ):
        raise PurchasePaymentMismatch

    payment.provider = status.provider or payment.provider
    payment.provider_order_id = status.provider_order_id or payment.provider_order_id
    payment.provider_payment_id = status.provider_payment_id or payment.provider_payment_id
    payment.provider_status = status.status
    payment.last_synced_at = moment

    internal = map_provider_status(status.status)
    if internal == "PAID":
        payment.paid_at = payment.paid_at or moment
        _settle(session, payment, moment)
    session.flush()
    return internal


def _settle(session: Session, payment: PurchasePayment, moment: datetime) -> None:
    if payment.kind == "ticket_pack":
        try:
            confirm_purchase(session, payment.user_id, payment.reference_id)
        except PurchaseNotFound as exc:
            raise PurchasePaymentNotFound from exc
        return
    if payment.kind == "pass":
        try:
            activate_subscription(session, payment.reference_id, now=moment)
        except PassNotFound as exc:
            raise PurchasePaymentNotFound from exc
        return
    raise PurchasePaymentError("kind_invalid")
