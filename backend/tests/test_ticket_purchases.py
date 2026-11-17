"""Testes de pacotes e compra de ingressos (Fase 14D.4)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.models import User
from app.modules.identity.sessions import SessionService
from app.modules.payments.adapter import (
    PixChargeRequest,
    PixChargeResult,
    ProviderStatus,
    RefundResult,
)
from app.modules.payments.dependency import get_psp_adapter
from app.modules.payments.models import PurchasePayment
from app.modules.payments.purchase import apply_status
from app.modules.tickets.models import TicketPurchase
from app.modules.tickets.service import get_balance
from tests.compliance_helpers import cpf_key_kwargs
from tests.helpers_results import make_token, make_user


def production_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="production",
        phone_hash_secret="phone-secret",
        token_hash_secret="token-secret",
        psp_provider="mercadopago",
        mercado_pago_access_token="mp-access-token",
        mercado_pago_webhook_secret="mp-webhook-secret",
        mercado_pago_notification_url="https://api.joga.example/payments/mercadopago/webhook",
        **cpf_key_kwargs(),
    )


def production_token(session: Session, user_id: UUID) -> str:
    settings = production_settings()
    tokens = SessionService(
        session,
        settings.token_hash_secret.get_secret_value(),
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user_id)
    session.commit()
    return tokens.access_token


class RecordingMercadoPagoAdapter:
    provider_name = "mercadopago"

    def __init__(self) -> None:
        self.requests: list[PixChargeRequest] = []

    def create_pix_charge(self, request: PixChargeRequest) -> PixChargeResult:
        self.requests.append(request)
        return PixChargeResult(
            provider=self.provider_name,
            provider_order_id="MP-ORDER-1",
            provider_payment_id="MP-PAY-1",
            status="action_required",
            status_detail="waiting_transfer",
            qr_code="000201MP",
            qr_code_base64="bXAx",
            ticket_url="https://mp.example/ticket",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            amount_cents=request.amount_cents,
            external_reference=request.external_reference,
            raw={},
        )

    def get_order(self, provider_order_id: str) -> ProviderStatus:
        raise AssertionError("get_order não deve ser chamado")

    def get_payment(self, provider_payment_id: str) -> ProviderStatus:
        raise AssertionError("get_payment não deve ser chamado")

    def refund(self, **_kwargs: object) -> RefundResult:
        raise AssertionError("refund não deve ser chamado")


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_packs_follow_the_price_ladder(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    response = api.get("/api/v1/me/tickets/packs", headers=bearer(token))
    assert response.status_code == 200, response.text
    packs = response.json()["packs"]
    assert [pack["code"] for pack in packs] == ["avulso", "pequeno", "medio", "grande"]
    units = [pack["unit_price_cents"] for pack in packs]
    assert units == sorted(units, reverse=True)
    assert packs[0]["unit_price_cents"] == 370
    assert packs[-1]["unit_price_cents"] == 310


def test_confirm_purchase_is_dev_only(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    created = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "avulso"},
    )
    assert created.status_code == 201, created.text

    client.app.dependency_overrides[get_settings] = production_settings
    confirm = api.post(
        f"/api/v1/me/tickets/purchases/{created.json()['id']}/confirm",
        headers=bearer(production_token(db_session, user_id)),
    )
    assert confirm.status_code == 403
    assert confirm.json() == {"detail": {"code": "confirmation_requires_psp"}}


def test_purchase_then_confirm_credits_the_wallet(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    created = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "pequeno"},
    )
    assert created.status_code == 201, created.text
    purchase = created.json()
    assert purchase["tickets"] == 10
    assert purchase["amount_cents"] == 3_400
    assert purchase["status"] == "pending"
    payment = purchase["payment"]
    assert payment["provider"] == "simulator"
    assert payment["provider_status"] == "action_required"
    assert payment["status_detail"] == "waiting_transfer"
    assert payment["amount_cents"] == 3_400
    assert payment["external_reference"] == f"ticket_pack:{purchase['id']}"
    assert payment["qr_code"]

    confirmed = api.post(
        f"/api/v1/me/tickets/purchases/{purchase['id']}/confirm", headers=bearer(token)
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "paid"

    wallet = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert wallet.json()["balance"] == 10


def test_confirming_twice_does_not_double_credit(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    purchase = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "avulso"},
    ).json()
    first = api.post(
        f"/api/v1/me/tickets/purchases/{purchase['id']}/confirm", headers=bearer(token)
    )
    second = api.post(
        f"/api/v1/me/tickets/purchases/{purchase['id']}/confirm", headers=bearer(token)
    )
    assert first.status_code == 200
    assert second.status_code == 200

    wallet = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert wallet.json()["balance"] == 3


def test_unknown_pack_is_rejected(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    response = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "inexistente"},
    )
    assert response.status_code == 404, response.text


def test_purchase_is_not_readable_by_another_user(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id = make_user(db_session)
    owner_token = make_token(db_session, owner_id)
    purchase = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(owner_token),
        json={"pack_code": "medio"},
    ).json()

    other_id = make_user(db_session)
    other_token = make_token(db_session, other_id)
    response = api.get(
        f"/api/v1/me/tickets/purchases/{purchase['id']}", headers=bearer(other_token)
    )
    assert response.status_code == 404, response.text


def test_mercadopago_requires_payer_email_and_snapshots_it(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    adapter = RecordingMercadoPagoAdapter()
    client.app.dependency_overrides[get_psp_adapter] = lambda: adapter

    missing = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "avulso"},
    )
    assert missing.status_code == 422, missing.text
    assert missing.json() == {"detail": {"code": "payer_email_required"}}
    assert adapter.requests == []

    user = db_session.get(User, user_id)
    assert user is not None
    user.email = "pagador@example.com"
    db_session.commit()

    created = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "avulso"},
    )
    assert created.status_code == 201, created.text
    assert adapter.requests[0].payer_email == "pagador@example.com"
    purchase_id = UUID(created.json()["id"])
    stored = db_session.scalar(
        select(PurchasePayment).where(PurchasePayment.reference_id == purchase_id)
    )
    assert stored is not None
    assert stored.payer_email == "pagador@example.com"


def test_ticket_purchase_is_idempotent_while_pending(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    first = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "pequeno"},
    )
    second = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "pequeno"},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]

    purchases = db_session.scalars(
        select(TicketPurchase).where(
            TicketPurchase.user_id == user_id,
            TicketPurchase.status == "pending",
        )
    ).all()
    assert len(purchases) == 1
    payments = db_session.scalars(
        select(PurchasePayment).where(
            PurchasePayment.kind == "ticket_pack",
            PurchasePayment.reference_id == purchases[0].id,
        )
    ).all()
    assert len(payments) == 1


def test_purchase_idempotency_key_replays_without_second_charge(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    headers = {**bearer(token), "Idempotency-Key": "compra-1"}

    first = api.post(
        "/api/v1/me/tickets/purchases",
        headers=headers,
        json={"pack_code": "pequeno"},
    )
    second = api.post(
        "/api/v1/me/tickets/purchases",
        headers=headers,
        json={"pack_code": "pequeno"},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]

    purchases = db_session.scalars(
        select(TicketPurchase).where(TicketPurchase.user_id == user_id)
    ).all()
    assert len(purchases) == 1
    payments = db_session.scalars(
        select(PurchasePayment).where(PurchasePayment.reference_id == purchases[0].id)
    ).all()
    assert len(payments) == 1

    conflict = api.post(
        "/api/v1/me/tickets/purchases",
        headers=headers,
        json={"pack_code": "medio"},
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"


def test_purchase_refund_revokes_unused_credit(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    created = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "pequeno"},
    )
    assert created.status_code == 201, created.text
    purchase_id = UUID(created.json()["id"])
    purchase = db_session.get(TicketPurchase, purchase_id)
    assert purchase is not None
    assert get_balance(db_session, user_id) == 0

    confirmed = api.post(
        f"/api/v1/me/tickets/purchases/{purchase_id}/confirm",
        headers=bearer(token),
    )
    assert confirmed.status_code == 200, confirmed.text
    assert get_balance(db_session, user_id) == purchase.tickets

    payment = db_session.scalar(
        select(PurchasePayment).where(
            PurchasePayment.reference_id == purchase_id,
        )
    )
    assert payment is not None
    apply_status(
        db_session,
        payment,
        ProviderStatus(
            provider="simulator",
            provider_order_id=payment.provider_order_id,
            provider_payment_id=payment.provider_payment_id,
            status="refunded",
            status_detail=None,
            amount_cents=payment.amount_cents,
            external_reference=f"{payment.kind}:{payment.reference_id}",
            raw={},
        ),
    )
    db_session.commit()
    db_session.refresh(purchase)
    assert purchase.status == "cancelled"
    assert get_balance(db_session, user_id) == 0
