"""Conciliação de compras de pacote/passe com o PSP (Fase 14D.16)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.payments.adapter import PspAdapter, PspError
from app.modules.payments.models import PurchasePayment
from app.modules.payments.status import map_provider_status


def reconcile_purchases(session: Session, adapter: PspAdapter) -> list[dict[str, Any]]:
    """Compara `purchase_payments` com a ordem/pagamento do PSP.

    Não corrige nada: devolve divergências para análise e evento compensatório.
    """

    issues: list[dict[str, Any]] = []
    payments = list(
        session.scalars(
            select(PurchasePayment).where(
                PurchasePayment.provider_order_id.is_not(None)
                | PurchasePayment.provider_payment_id.is_not(None)
            )
        ).all()
    )
    for payment in payments:
        try:
            if payment.provider_order_id:
                status = adapter.get_order(payment.provider_order_id)
            elif payment.provider_payment_id:
                status = adapter.get_payment(payment.provider_payment_id)
            else:  # pragma: no cover - filtro da query
                continue
        except PspError:
            issues.append(
                {
                    "code": "purchase_provider_unavailable",
                    "purchase_payment_id": str(payment.id),
                    "kind": payment.kind,
                    "reference_id": str(payment.reference_id),
                }
            )
            continue

        if status.amount_cents is not None and status.amount_cents != payment.amount_cents:
            issues.append(
                {
                    "code": "purchase_amount_mismatch",
                    "purchase_payment_id": str(payment.id),
                    "kind": payment.kind,
                    "reference_id": str(payment.reference_id),
                    "amount_cents": payment.amount_cents,
                    "provider_amount_cents": status.amount_cents,
                }
            )
            continue

        expected = map_provider_status(status.status)
        settled = payment.paid_at is not None
        if expected == "PAID" and not settled:
            issues.append(
                {
                    "code": "purchase_paid_not_settled",
                    "purchase_payment_id": str(payment.id),
                    "kind": payment.kind,
                    "reference_id": str(payment.reference_id),
                }
            )
        elif expected in {"FAILED", "EXPIRED"} and settled:
            issues.append(
                {
                    "code": "purchase_settled_but_provider_not_paid",
                    "purchase_payment_id": str(payment.id),
                    "kind": payment.kind,
                    "reference_id": str(payment.reference_id),
                    "provider_status": status.status,
                }
            )
        elif expected == "REFUNDED":
            issues.append(
                {
                    "code": "purchase_provider_refund_without_internal_refund",
                    "purchase_payment_id": str(payment.id),
                    "kind": payment.kind,
                    "reference_id": str(payment.reference_id),
                }
            )
    return issues


__all__ = ["reconcile_purchases"]
