"""Testes do passe trimestral e da trilha paga (Fase 14D.12)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.clock import utcnow
from app.modules.identity.sessions import SessionService
from app.modules.passes.models import PassSubscription
from app.modules.passes.service import (
    activate_subscription,
    active_subscription,
    add_months,
    create_subscription,
    deliver_all_due,
    deliver_due,
    deliveries_for,
    expire_due,
    get_subscription,
)
from app.modules.payments.adapter import ProviderStatus
from app.modules.payments.models import PurchasePayment
from app.modules.payments.purchase import apply_status
from app.modules.season.service import active_season, award_xp
from app.modules.tickets.models import TicketLot
from app.modules.tickets.service import expire_due as expire_tickets
from app.modules.tickets.service import get_balance
from tests.compliance_helpers import cpf_key_kwargs
from tests.helpers_results import make_token, make_user
from tests.settings_helpers import demo_settings

START = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_plans_are_the_four_quarter_sizes(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    response = api.get("/api/v1/me/pass/plans", headers=bearer(token))
    assert response.status_code == 200, response.text
    plans = response.json()["plans"]
    assert [plan["tickets_per_month"] for plan in plans] == [10, 20, 30, 50]
    assert [plan["quarter_cents"] for plan in plans] == [9_750, 19_500, 29_250, 48_750]
    assert {plan["unit_price_cents"] for plan in plans} == {325}


def test_confirm_subscription_is_dev_only(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    created = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(token),
        json={"plan_code": "craque"},
    )
    assert created.status_code == 201, created.text

    client.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        environment="production",
        phone_hash_secret="phone-secret",
        token_hash_secret="token-secret",
        psp_provider="mercadopago",
        mercado_pago_access_token="mp-access-token",
        mercado_pago_webhook_secret="mp-webhook-secret",
        mercado_pago_notification_url="https://api.joga.example/payments/mercadopago/webhook",
        web_cookie_secure=True,
        **cpf_key_kwargs(),
    )
    production_tokens = SessionService(
        db_session,
        "token-secret",
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user_id)
    db_session.commit()
    confirm = api.post(
        f"/api/v1/me/pass/subscriptions/{created.json()['id']}/confirm",
        headers=bearer(production_tokens.access_token),
    )
    assert confirm.status_code == 403
    assert confirm.json() == {"detail": {"code": "confirmation_requires_psp"}}


def test_confirm_subscription_is_allowed_for_owner_in_demo(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    created = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(token),
        json={"plan_code": "craque"},
    )
    assert created.status_code == 201, created.text

    client.app.dependency_overrides[get_settings] = lambda: demo_settings()
    demo_tokens = SessionService(
        db_session,
        "demo-token-hash-secret",
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user_id)
    db_session.commit()
    confirm = api.post(
        f"/api/v1/me/pass/subscriptions/{created.json()['id']}/confirm",
        headers=bearer(demo_tokens.access_token),
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "active"
    assert confirm.json()["paid_at"] is not None


def test_pass_purchase_is_idempotent_while_pending(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    first = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(token),
        json={"plan_code": "craque"},
    )
    second = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(token),
        json={"plan_code": "craque"},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]


def test_pass_idempotency_key_replays_and_rejects_different_plan(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    headers = {**bearer(token), "Idempotency-Key": "passe-1"}

    first = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=headers,
        json={"plan_code": "craque"},
    )
    second = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=headers,
        json={"plan_code": "craque"},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]

    conflict = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=headers,
        json={"plan_code": "time"},
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"


def test_pass_refund_cancels_subscription(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    created = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(token),
        json={"plan_code": "craque"},
    )
    assert created.status_code == 201, created.text
    subscription_id = uuid.UUID(created.json()["id"])
    confirmed = api.post(
        f"/api/v1/me/pass/subscriptions/{subscription_id}/confirm",
        headers=bearer(token),
    )
    assert confirmed.status_code == 200, confirmed.text

    payment = db_session.scalar(
        select(PurchasePayment).where(
            PurchasePayment.kind == "pass",
            PurchasePayment.reference_id == subscription_id,
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
            external_reference=f"pass:{subscription_id}",
            raw={},
        ),
    )
    db_session.commit()
    subscription = db_session.get(PassSubscription, subscription_id)
    assert subscription is not None
    assert subscription.status == "cancelled"


def test_subscribe_opens_pix_and_only_payment_activates(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    created = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(token),
        json={"plan_code": "craque"},
    )
    assert created.status_code == 201, created.text
    subscription = created.json()
    assert subscription["status"] == "pending"
    assert subscription["amount_cents"] == 19_500
    assert subscription["payment"]["qr_code"]
    assert subscription["payment"]["paid"] is False

    wallet = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert wallet.json()["balance"] == 0

    confirmed = api.post(
        f"/api/v1/me/pass/subscriptions/{subscription['id']}/confirm",
        headers=bearer(token),
    )
    assert confirmed.status_code == 200, confirmed.text
    active = confirmed.json()
    assert active["status"] == "active"
    assert len(active["deliveries"]) == 1
    assert active["next_delivery_at"] is not None

    wallet = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert wallet.json()["balance"] == 20

    again = api.post(
        f"/api/v1/me/pass/subscriptions/{subscription['id']}/confirm",
        headers=bearer(token),
    )
    assert again.status_code == 200
    wallet = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert wallet.json()["balance"] == 20


def test_second_subscription_is_refused_while_active(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    first = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(token),
        json={"plan_code": "jogador"},
    ).json()
    api.post(f"/api/v1/me/pass/subscriptions/{first['id']}/confirm", headers=bearer(token))

    second = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(token),
        json={"plan_code": "elenco"},
    )
    assert second.status_code == 409, second.text
    assert second.json()["detail"]["code"] == "pass_already_active"


def test_delivery_is_monthly_idempotent_and_expires(db_session: Session) -> None:
    user_id = make_user(db_session)
    subscription = create_subscription(db_session, user_id, "time", now=START)
    assert subscription.status == "pending"
    assert get_balance(db_session, user_id, now=START) == 0

    activate_subscription(db_session, subscription.id, now=START)
    assert get_balance(db_session, user_id, now=START) == 30
    first_lot = db_session.scalar(
        select(TicketLot).where(TicketLot.user_id == user_id, TicketLot.source == "pass")
    )
    assert first_lot is not None
    assert first_lot.period == "2026-11"
    assert first_lot.expires_at is None

    deliver_due(db_session, subscription, now=START + timedelta(days=3))
    assert get_balance(db_session, user_id, now=START + timedelta(days=3)) == 30

    deliver_due(db_session, subscription, now=add_months(START, 1))
    expire_tickets(db_session, now=add_months(START, 1))
    assert get_balance(db_session, user_id, now=add_months(START, 1)) == 30
    db_session.refresh(first_lot)
    assert first_lot.remaining == 0

    deliver_due(db_session, subscription, now=add_months(START, 2))
    expire_tickets(db_session, now=add_months(START, 2))
    assert get_balance(db_session, user_id, now=add_months(START, 2)) == 30
    assert len(deliveries_for(db_session, subscription.id)) == 3

    deliver_due(db_session, subscription, now=add_months(START, 4))
    expire_tickets(db_session, now=add_months(START, 4))
    assert get_balance(db_session, user_id, now=add_months(START, 4)) == 0

    assert expire_due(db_session, now=add_months(START, 3)) == 1
    assert active_subscription(db_session, user_id, add_months(START, 3)) is None
    assert get_subscription(db_session, user_id, subscription.id).status == "expired"

    assert deliver_all_due(db_session, now=add_months(START, 4)) == 0


def test_pass_track_requires_active_subscription(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    season = active_season(db_session, utcnow())
    award_xp(
        db_session,
        user_id=user_id,
        season=season,
        amount=3_000,
        source="admin",
        idempotency_key=f"test:{user_id}",
    )
    db_session.commit()

    blocked = api.post("/api/v1/me/progress/track/12/claim", headers=bearer(token))
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["detail"]["code"] == "pass_required"

    subscription = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(token),
        json={"plan_code": "jogador"},
    ).json()
    api.post(
        f"/api/v1/me/pass/subscriptions/{subscription['id']}/confirm",
        headers=bearer(token),
    )

    claimed = api.post("/api/v1/me/progress/track/12/claim", headers=bearer(token))
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["track"] == "pass"

    track = api.get("/api/v1/me/progress/track", headers=bearer(token))
    assert track.json()["has_pass"] is True


def test_subscription_is_private_to_its_owner(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id = make_user(db_session)
    owner_token = make_token(db_session, owner_id)
    subscription = api.post(
        "/api/v1/me/pass/subscriptions",
        headers=bearer(owner_token),
        json={"plan_code": "jogador"},
    ).json()

    other_id = make_user(db_session)
    other_token = make_token(db_session, other_id)
    response = api.get(
        f"/api/v1/me/pass/subscriptions/{subscription['id']}",
        headers=bearer(other_token),
    )
    assert response.status_code == 404, response.text
