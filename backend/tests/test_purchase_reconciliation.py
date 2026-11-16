"""Testes da conciliação de compras de ingresso/passe (Fase 14D.16)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.payments.adapter import ProviderStatus, PspUnavailable
from app.modules.payments.models import PurchasePayment
from app.modules.payments.purchase_reconciliation import reconcile_purchases
from tests.helpers_results import make_user


class StubAdapter:
    provider_name = "stub"

    def __init__(self, *, status: str = "action_required", amount: int = 1_000) -> None:
        self.status = status
        self.amount = amount

    def get_order(self, provider_order_id: str) -> ProviderStatus:
        return ProviderStatus(
            provider="stub",
            provider_order_id=provider_order_id,
            provider_payment_id=None,
            status=self.status,
            status_detail=None,
            amount_cents=self.amount,
            external_reference=None,
            raw={},
        )

    def get_payment(self, provider_payment_id: str) -> ProviderStatus:
        return self.get_order(provider_payment_id)


class BrokenAdapter(StubAdapter):
    def get_order(self, provider_order_id: str) -> ProviderStatus:
        raise PspUnavailable("offline")


def make_payment(db_session: Session, *, paid: bool = False) -> PurchasePayment:
    user_id = make_user(db_session)
    payment = PurchasePayment(
        user_id=user_id,
        kind="ticket_pack",
        reference_id=uuid.uuid4(),
        amount_cents=1_000,
        provider="stub",
        provider_order_id="order-1",
    )
    if paid:
        from app.modules.identity.clock import utcnow

        payment.paid_at = utcnow()
    db_session.add(payment)
    db_session.flush()
    return payment


def test_reconcile_accepts_pending_purchase(db_session: Session) -> None:
    make_payment(db_session)
    assert reconcile_purchases(db_session, StubAdapter()) == []


def test_reconcile_detects_provider_paid_but_not_settled(db_session: Session) -> None:
    make_payment(db_session)
    issues = reconcile_purchases(db_session, StubAdapter(status="processed"))
    assert [item["code"] for item in issues] == ["purchase_paid_not_settled"]


def test_reconcile_detects_amount_mismatch(db_session: Session) -> None:
    make_payment(db_session, paid=True)
    issues = reconcile_purchases(db_session, StubAdapter(status="processed", amount=900))
    assert [item["code"] for item in issues] == ["purchase_amount_mismatch"]


def test_reconcile_detects_provider_unavailable(db_session: Session) -> None:
    make_payment(db_session)
    issues = reconcile_purchases(db_session, BrokenAdapter())
    assert [item["code"] for item in issues] == ["purchase_provider_unavailable"]
