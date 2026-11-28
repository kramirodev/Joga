"""Regras da assinatura nova: catálogo, ciclo de aniversário, ordem e recibo."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.passes.models import PassPlan
from app.modules.passes.plans import DEFAULT_PASS_PLANS
from app.modules.passes.service import (
    activate_subscription,
    add_months,
    create_subscription,
    current_delivery,
    deliveries_for,
)
from app.modules.payments.adapter import ProviderStatus, SimulatorPspAdapter
from app.modules.payments.purchase import apply_status, open_charge, payment_for
from app.modules.tickets.models import TicketLot, TicketPack
from app.modules.tickets.service import (
    InsufficientTickets,
    confirm_purchase,
    consume,
    create_purchase,
    grant,
)
from tests.helpers_results import make_token, make_user

START = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_add_months_keeps_the_purchase_day() -> None:
    assert add_months(datetime(2026, 1, 31, 12, tzinfo=UTC), 1) == datetime(
        2026, 2, 28, 12, tzinfo=UTC
    )
    assert add_months(datetime(2024, 2, 29, 12, tzinfo=UTC), 12) == datetime(
        2025, 2, 28, 12, tzinfo=UTC
    )
    assert add_months(datetime(2026, 11, 30, 12, tzinfo=UTC), 3) == datetime(
        2027, 2, 28, 12, tzinfo=UTC
    )


def test_semestral_contract_has_six_cycles_and_only_the_first_is_delivered(
    db_session: Session,
) -> None:
    user_id = make_user(db_session)
    subscription = create_subscription(db_session, user_id, "semestral_40", now=START)
    assert subscription.cycle_months == 6
    assert subscription.unit_price_cents == 300
    assert subscription.amount_cents == 72_000
    assert subscription.installments == 1

    activate_subscription(db_session, subscription.id, now=START)
    assert subscription.ends_at is not None
    assert subscription.ends_at.replace(tzinfo=UTC) == add_months(START, 6)
    assert subscription.refund_window_ends_at is not None
    assert subscription.refund_window_ends_at.replace(tzinfo=UTC) == START + timedelta(days=7)

    cycles = deliveries_for(db_session, subscription.id)
    assert len(cycles) == 6
    assert [cycle.month_index for cycle in cycles] == [1, 2, 3, 4, 5, 6]
    assert cycles[0].status == "delivered"
    assert all(cycle.status == "scheduled" for cycle in cycles[1:])
    assert cycles[0].period == "2026-11"
    assert cycles[1].period == "2026-12"

    lot = db_session.scalar(
        select(TicketLot).where(TicketLot.user_id == user_id, TicketLot.source == "pass")
    )
    assert lot is not None and lot.remaining == 40
    assert lot.expires_at is not None
    assert lot.expires_at.replace(tzinfo=UTC) == add_months(START, 1)

    current = current_delivery(subscription, cycles, now=START + timedelta(days=2))
    assert current is not None and current.month_index == 1
    assert current_delivery(subscription, cycles, now=add_months(START, 1)) is None


def test_paid_notification_is_idempotent(db_session: Session) -> None:
    user_id = make_user(db_session)
    subscription = create_subscription(db_session, user_id, "trimestral_20", now=START)
    payment = open_charge(
        db_session,
        SimulatorPspAdapter(),
        kind="pass",
        reference_id=subscription.id,
        user_id=user_id,
        amount_cents=subscription.amount_cents,
        description="teste",
    )
    provider_status = ProviderStatus(
        provider="simulator",
        provider_order_id=payment.provider_order_id or "SIM-1",
        provider_payment_id=payment.provider_payment_id,
        status="approved",
        status_detail=None,
        amount_cents=subscription.amount_cents,
        external_reference=f"pass:{subscription.id}",
        raw={},
    )
    assert apply_status(db_session, payment, provider_status, now=START) == "PAID"
    assert apply_status(db_session, payment, provider_status, now=START) == "PAID"

    assert subscription.status == "active"
    lots = db_session.scalars(
        select(TicketLot).where(TicketLot.user_id == user_id, TicketLot.source == "pass")
    ).all()
    assert len(lots) == 1
    assert lots[0].remaining == 20
    assert payment_for(db_session, "pass", subscription.id) is payment


def test_plan_constraints_reject_invalid_price_and_cycle(db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        db_session.add(
            PassPlan(
                code="invalido_meses",
                label="Inválido",
                months=2,
                tickets_per_month=20,
                unit_price_cents=320,
                cycle_amount_cents=12_800,
            )
        )
        db_session.flush()
    db_session.rollback()

    with pytest.raises(IntegrityError):
        db_session.add(
            PassPlan(
                code="invalido_preco",
                label="Inválido",
                months=1,
                tickets_per_month=20,
                unit_price_cents=299,
                cycle_amount_cents=5_980,
            )
        )
        db_session.flush()
    db_session.rollback()

    with pytest.raises(IntegrityError):
        db_session.add(
            PassPlan(
                code="invalido_total",
                label="Inválido",
                months=3,
                tickets_per_month=20,
                unit_price_cents=320,
                cycle_amount_cents=1,
            )
        )
        db_session.flush()
    db_session.rollback()

    codes = {plan.code for plan in db_session.scalars(select(PassPlan)).all()}
    assert codes == {definition.code for definition in DEFAULT_PASS_PLANS}


def test_consumption_order_is_franchise_then_purchased_then_courtesy(
    db_session: Session,
) -> None:
    user_id = make_user(db_session)
    grant(
        db_session,
        user_id,
        2,
        source="pass",
        idempotency_key="pass:priority",
        period="2026-11",
        expires_at=START + timedelta(days=30),
    )
    grant(db_session, user_id, 2, source="purchase", idempotency_key="purchase:priority")
    grant(
        db_session,
        user_id,
        2,
        source="free_level",
        idempotency_key="free:priority",
        expires_at=START + timedelta(days=30),
    )

    consume(db_session, user_id, 3, ref_type="booking", ref_id=uuid.uuid4())
    lots = {
        lot.source: lot
        for lot in db_session.scalars(select(TicketLot).where(TicketLot.user_id == user_id)).all()
    }
    assert lots["pass"].remaining == 0
    assert lots["purchase"].remaining == 1
    assert lots["free_level"].remaining == 2

    consume(db_session, user_id, 2, ref_type="booking", ref_id=uuid.uuid4())
    db_session.refresh(lots["purchase"])
    db_session.refresh(lots["free_level"])
    assert lots["purchase"].remaining == 0
    assert lots["free_level"].remaining == 1

    with pytest.raises(InsufficientTickets):
        consume(db_session, user_id, 2, ref_type="booking", ref_id=uuid.uuid4())


def test_cycle_expires_on_the_anniversary_not_on_the_calendar_month(
    db_session: Session,
) -> None:
    user_id = make_user(db_session)
    subscription = create_subscription(db_session, user_id, "trimestral_20", now=START)
    activate_subscription(db_session, subscription.id, now=START)
    lot = db_session.scalar(
        select(TicketLot).where(TicketLot.user_id == user_id, TicketLot.source == "pass")
    )
    assert lot is not None and lot.remaining == 20
    assert lot.period == "2026-11"

    # 05/12 continua dentro do ciclo de 20/11 a 20/12.
    from app.modules.tickets.service import get_balance

    assert get_balance(db_session, user_id, now=datetime(2026, 12, 5, tzinfo=UTC)) == 20
    # Depois do fim do ciclo, o saldo não conta mais, mesmo no mesmo mês civil.
    assert get_balance(db_session, user_id, now=datetime(2026, 12, 21, tzinfo=UTC)) == 0


def test_receipt_requires_payment_and_owner(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id = make_user(db_session)
    owner_token = make_token(db_session, owner_id)

    created = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(owner_token),
        json={"plan_code": "mensal_40"},
    )
    assert created.status_code == 201, created.text
    subscription_id = created.json()["id"]

    pending_receipt = api.get(
        f"/api/v1/me/pass/subscriptions/{subscription_id}/receipt",
        headers=bearer(owner_token),
    )
    assert pending_receipt.status_code == 409
    assert pending_receipt.json()["detail"]["code"] == "receipt_not_available"

    confirmed = api.post(
        f"/api/v1/me/pass/subscriptions/{subscription_id}/confirm",
        headers=bearer(owner_token),
    )
    assert confirmed.status_code == 200, confirmed.text
    receipt = api.get(
        f"/api/v1/me/pass/subscriptions/{subscription_id}/receipt",
        headers=bearer(owner_token),
    )
    assert receipt.status_code == 200, receipt.text
    body = receipt.json()
    assert body["amount_cents"] == 12_800
    assert body["cycle_total_cents"] == 12_800
    assert body["cycle_months"] == 1
    assert body["document_type"] == "internal_receipt"
    assert body["fiscal_document"] is None
    assert body["status"] == "paid"

    other_id = make_user(db_session)
    other_token = make_token(db_session, other_id)
    denied = api.get(
        f"/api/v1/me/pass/subscriptions/{subscription_id}/receipt",
        headers=bearer(other_token),
    )
    assert denied.status_code == 404


def test_standalone_pack_sale_is_discontinued_but_legacy_stays_readable(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    legacy = create_purchase(db_session, user_id, "avulso")
    confirm_purchase(db_session, user_id, legacy.id)
    db_session.commit()

    for pack in db_session.scalars(select(TicketPack)).all():
        pack.active = False
    db_session.commit()

    catalog = api.get("/api/v1/me/tickets/packs", headers=bearer(token))
    assert catalog.status_code == 200
    assert catalog.json()["packs"] == []

    blocked = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "avulso"},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "ticket_sales_discontinued"

    old_purchase = api.get(
        f"/api/v1/me/tickets/purchases/{legacy.id}",
        headers=bearer(token),
    )
    assert old_purchase.status_code == 200
    assert old_purchase.json()["status"] == "paid"

    wallet = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert wallet.json()["balance"] == 3


def test_pending_contract_has_no_cycles_and_cannot_have_receipt(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    created = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(token),
        json={"plan_code": "mensal_20"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["cycles"] == []
    assert body["current_cycle"] is None
    receipt = api.get(
        f"/api/v1/me/pass/subscriptions/{body['id']}/receipt",
        headers=bearer(token),
    )
    assert receipt.status_code == 409
    assert receipt.json()["detail"]["code"] == "receipt_not_available"
