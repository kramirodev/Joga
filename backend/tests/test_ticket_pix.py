"""Testes da cobranÃ§a Pix de pacote de ingressos (Fase 14D.13)."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.payments.adapter import PixChargeRequest, ProviderStatus, RefundResult
from app.modules.payments.dependency import get_psp_adapter
from app.modules.payments.models import PurchasePayment
from app.modules.payments.purchase import (
    PurchasePaymentMismatch,
    apply_status,
    payment_for,
)
from app.modules.payments.service import PaymentService
from app.modules.tickets.service import get_balance
from tests.helpers_results import make_token, make_user


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class PaidOrderAdapter:
    """Simula o PSP devolvendo a ordem como paga."""

    provider_name = "simulator"

    def __init__(self, payment: PurchasePayment) -> None:
        self.payment = payment

    def create_pix_charge(self, request: PixChargeRequest) -> ProviderStatus:  # noqa: ANN201
        raise AssertionError("nÃ£o deve criar cobranÃ§a neste teste")

    def get_order(self, provider_order_id: str) -> ProviderStatus:
        return ProviderStatus(
            provider="simulator",
            provider_order_id=provider_order_id,
            provider_payment_id=self.payment.provider_payment_id,
            status="processed",
            status_detail="accredited",
            amount_cents=self.payment.amount_cents,
            external_reference=f"{self.payment.kind}:{self.payment.reference_id}",
            raw={"test": True},
        )

    def get_payment(self, provider_payment_id: str) -> ProviderStatus:
        return self.get_order(self.payment.provider_order_id or provider_payment_id)

    def refund(
        self,
        *,
        provider_order_id: str,
        provider_payment_id: str | None,
        amount_cents: int,
    ) -> RefundResult:
        return RefundResult(
            provider="simulator",
            refund_id="REF-TEST",
            status="processed",
            amount_cents=amount_cents,
            raw={"test": True},
        )


def create_purchase(api: TestClient, token: str, pack: str) -> dict:
    response = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": pack},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_purchase_opens_pix_without_crediting(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    purchase = create_purchase(api, token, "pequeno")
    assert purchase["status"] == "pending"
    assert purchase["payment"]["qr_code"]
    assert purchase["payment"]["paid"] is False

    wallet = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert wallet.json()["balance"] == 0


def test_paid_status_credits_once(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    purchase = create_purchase(api, token, "pequeno")

    payment = payment_for(db_session, "ticket_pack", UUID(purchase["id"]))
    assert payment is not None
    status = ProviderStatus(
        provider="simulator",
        provider_order_id=payment.provider_order_id or "",
        provider_payment_id=payment.provider_payment_id,
        status="processed",
        status_detail="accredited",
        amount_cents=payment.amount_cents,
        external_reference=f"ticket_pack:{payment.reference_id}",
        raw={"test": True},
    )
    assert apply_status(db_session, payment, status) == "PAID"
    db_session.commit()
    assert get_balance(db_session, user_id) == 10

    assert apply_status(db_session, payment, status) == "PAID"
    db_session.commit()
    assert get_balance(db_session, user_id) == 10


def test_amount_mismatch_is_rejected(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    purchase = create_purchase(api, token, "avulso")

    payment = payment_for(db_session, "ticket_pack", UUID(purchase["id"]))
    assert payment is not None
    status = ProviderStatus(
        provider="simulator",
        provider_order_id=payment.provider_order_id or "",
        provider_payment_id=payment.provider_payment_id,
        status="processed",
        status_detail="accredited",
        amount_cents=payment.amount_cents + 100,
        external_reference=f"ticket_pack:{payment.reference_id}",
        raw={"test": True},
    )
    with pytest.raises(PurchasePaymentMismatch):
        apply_status(db_session, payment, status)
    db_session.rollback()
    assert get_balance(db_session, user_id) == 0


def test_webhook_credits_and_replay_does_not_duplicate(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    purchase = create_purchase(api, token, "medio")

    payment = payment_for(db_session, "ticket_pack", UUID(purchase["id"]))
    assert payment is not None
    service = PaymentService(db_session, PaidOrderAdapter(payment))  # type: ignore[arg-type]
    service.handle_webhook(
        provider="simulator",
        event_id="evt-ticket-1",
        event_type="order.updated",
        data_id=payment.provider_order_id or "",
        payload={"id": payment.provider_order_id},
    )
    db_session.commit()
    assert get_balance(db_session, user_id) == 30

    service.handle_webhook(
        provider="simulator",
        event_id="evt-ticket-1",
        event_type="order.updated",
        data_id=payment.provider_order_id or "",
        payload={"id": payment.provider_order_id},
    )
    db_session.commit()
    assert get_balance(db_session, user_id) == 30


def test_sync_endpoint_reports_paid_purchase(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    purchase = create_purchase(api, token, "pequeno")
    payment = payment_for(db_session, "ticket_pack", UUID(purchase["id"]))
    assert payment is not None

    api.app.dependency_overrides[get_psp_adapter] = lambda: PaidOrderAdapter(payment)  # noqa: E501

    synced = api.post(f"/api/v1/me/tickets/purchases/{purchase['id']}/sync", headers=bearer(token))
    assert synced.status_code == 200, synced.text
    body = synced.json()
    assert body["status"] == "paid"
    assert body["payment"]["paid"] is True
    assert get_balance(db_session, user_id) == 10
