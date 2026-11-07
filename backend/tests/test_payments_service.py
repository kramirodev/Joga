"""Testes de serviço/API de pagamentos Pix e webhook (Fase 14A)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking, BookingHold, BookingPayment
from app.modules.bookings.service import BookingNotFound, BookingService
from app.modules.identity.clock import utcnow
from app.modules.payments.adapter import (
    PixChargeRequest,
    ProviderStatus,
    RefundResult,
    SimulatorPspAdapter,
)
from app.modules.payments.models import (
    LedgerEntry,
    PaymentEvent,
    PaymentRefund,
    PspWebhookEvent,
)
from app.modules.payments.service import PaymentMismatch, PaymentNotFound, PaymentService
from tests.helpers_results import make_token, make_user
from tests.test_bookings_api import (
    api_client,
    bearer,
    confirm_all,
    create_booking,
    setup_booking,
)


class FakeAdapter:
    provider_name = "mercadopago"

    def __init__(self, orders: dict[str, ProviderStatus]) -> None:
        self.orders = orders

    def create_pix_charge(self, request: PixChargeRequest):  # noqa: ANN201
        raise AssertionError("não deve criar cobrança neste teste")

    def get_order(self, provider_order_id: str) -> ProviderStatus:
        return self.orders[provider_order_id]

    def get_payment(self, provider_payment_id: str) -> ProviderStatus:
        for status in self.orders.values():
            if status.provider_payment_id == provider_payment_id:
                return status
        raise KeyError(provider_payment_id)

    def refund(
        self,
        *,
        provider_order_id: str,
        provider_payment_id: str | None,
        amount_cents: int,
    ) -> RefundResult:
        return RefundResult(
            provider="mercadopago",
            refund_id=f"REF-{provider_order_id}",
            status="processed",
            amount_cents=amount_cents,
            raw={"test": True},
        )


def accepted_booking(api, context) -> dict:
    booking = create_booking(api, context, context["lobbies"][0])
    confirm_all(api, context, booking["id"])
    accepted = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{booking['id']}/accept",
        headers=bearer(context["tokens"][0]),
    )
    assert accepted.status_code == 200, accepted.text
    return accepted.json()


def fake_orders(accepted: dict) -> dict[str, ProviderStatus]:
    return {
        payment["provider_order_id"]: ProviderStatus(
            provider="mercadopago",
            provider_order_id=payment["provider_order_id"],
            provider_payment_id=payment["provider_payment_id"],
            status="processed",
            status_detail="accredited",
            amount_cents=payment["amount_cents"],
            external_reference=payment["id"],
            raw={"test": True},
        )
        for payment in accepted["payments"]
    }


def test_open_charges_and_webhooks_confirm_booking(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)

    assert len(accepted["payments"]) == 4
    for payment in accepted["payments"]:
        assert payment["provider"] == "simulator"
        assert payment["provider_order_id"]
        assert payment["status"] == "PENDING"

    player_view = api.get(
        f"/api/v1/bookings/{accepted['id']}",
        headers=bearer(context["tokens"][1]),
    )
    assert player_view.status_code == 200
    player_payment = player_view.json()["payments"][0]
    assert player_payment["qr_code"]
    assert player_payment["provider"] == "simulator"

    ledger_count = db_session.scalar(select(func.count()).select_from(LedgerEntry))
    assert ledger_count == 4

    adapter = FakeAdapter(fake_orders(accepted))
    service = PaymentService(db_session, adapter)
    for index, payment in enumerate(accepted["payments"]):
        service.handle_webhook(
            provider="mercadopago",
            event_id=f"evt-{payment['id']}",
            event_type="order",
            data_id=payment["provider_order_id"],
            payload={"id": f"evt-{payment['id']}", "type": "order"},
        )
        db_session.commit()
        db_session.expire_all()
        if index < 3:
            assert db_session.get(Booking, uuid.UUID(accepted["id"])).status == "PAYMENT_PENDING"

    booking = db_session.get(Booking, uuid.UUID(accepted["id"]))
    assert booking is not None
    assert booking.status == "CONFIRMED"
    hold = db_session.scalar(select(BookingHold).where(BookingHold.booking_id == booking.id))
    assert hold is not None and hold.status == "RELEASED"
    ledger_count = db_session.scalar(select(func.count()).select_from(LedgerEntry))
    assert ledger_count == 8

    first = accepted["payments"][0]
    service.handle_webhook(
        provider="mercadopago",
        event_id=f"evt-{first['id']}",
        event_type="order",
        data_id=first["provider_order_id"],
        payload={"id": f"evt-{first['id']}", "type": "order"},
    )
    db_session.commit()
    assert db_session.scalar(select(func.count()).select_from(PspWebhookEvent)) == 4
    assert db_session.scalar(select(func.count()).select_from(PaymentEvent)) == 8

    completed = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{accepted['id']}/complete",
        headers=bearer(context["tokens"][0]),
    )
    assert completed.status_code == 200, completed.text
    releases = db_session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.booking_id == booking.id,
            LedgerEntry.entry_type == "VENUE_RELEASE",
        )
    ).all()
    assert len(releases) == 1
    assert releases[0].amount_cents == 40_000


def test_amount_mismatch_does_not_confirm(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)
    orders = fake_orders(accepted)
    first = accepted["payments"][0]
    orders[first["provider_order_id"]] = replace(
        orders[first["provider_order_id"]],
        amount_cents=orders[first["provider_order_id"]].amount_cents + 1,
    )
    service = PaymentService(db_session, FakeAdapter(orders))

    with pytest.raises(PaymentMismatch):
        service.handle_webhook(
            provider="mercadopago",
            event_id=f"evt-{first['id']}",
            event_type="order",
            data_id=first["provider_order_id"],
            payload={"id": f"evt-{first['id']}", "type": "order"},
        )
    db_session.rollback()
    payment = db_session.get(BookingPayment, uuid.UUID(first["id"]))
    assert payment is not None and payment.status == "PENDING"
    assert db_session.get(Booking, uuid.UUID(accepted["id"])).status == "PAYMENT_PENDING"


def test_sync_payment_requires_participant_or_org(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)
    orders = fake_orders(accepted)
    first = accepted["payments"][0]
    service = PaymentService(db_session, FakeAdapter(orders))

    outsider = make_user(db_session)
    with pytest.raises(BookingNotFound):
        service.sync_payment(
            outsider,
            uuid.UUID(accepted["id"]),
            uuid.UUID(first["id"]),
        )

    user1_participant = next(
        item for item in accepted["participants"] if item["user_id"] == str(context["users"][1])
    )
    own_payment = next(
        item for item in accepted["payments"] if item["participant_id"] == user1_participant["id"]
    )
    with pytest.raises(PaymentNotFound):
        service.sync_payment(
            context["users"][1],
            uuid.UUID(accepted["id"]),
            uuid.UUID(first["id"]),
        )

    bundle = service.sync_payment(
        context["users"][1],
        uuid.UUID(accepted["id"]),
        uuid.UUID(own_payment["id"]),
    )
    synced = next(item for item in bundle.payments if item.id == uuid.UUID(own_payment["id"]))
    assert synced.status == "PAID"


def test_outside_participant_does_not_see_other_payment(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)
    outsider = make_user(db_session)

    response = api.get(
        f"/api/v1/bookings/{accepted['id']}",
        headers=bearer(context["tokens"][1]),
    )
    assert response.status_code == 200
    assert len(response.json()["payments"]) == 1

    outsider_response = api.get(
        f"/api/v1/bookings/{accepted['id']}",
        headers=bearer(str(outsider)),
    )
    assert outsider_response.status_code in {401, 404}


def test_booking_service_can_register_payment_result_idempotently(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)
    first = accepted["payments"][0]
    service = BookingService(db_session)

    bundle = service.register_payment_result(
        uuid.UUID(accepted["id"]),
        uuid.UUID(first["id"]),
        status="PAID",
    )
    assert any(item.status == "PAID" for item in bundle.payments)
    again = service.register_payment_result(
        uuid.UUID(accepted["id"]),
        uuid.UUID(first["id"]),
        status="PAID",
    )
    assert again.booking.status == "PAYMENT_PENDING"


def pay_all(api, context, booking_id: str) -> None:
    for token in context["tokens"]:
        response = api.post(
            f"/api/v1/bookings/{booking_id}/payments/simulate",
            headers=bearer(token),
        )
        assert response.status_code == 200, response.text


def test_venue_cancel_refunds_all_paid_participants(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)
    pay_all(api, context, accepted["id"])

    cancelled = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{accepted['id']}/cancel",
        headers=bearer(context["tokens"][0]),
        json={"reason": "Falha operacional da quadra"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED_BY_VENUE"
    assert {item["status"] for item in cancelled.json()["payments"]} == {"REFUNDED"}

    refunds = db_session.scalars(
        select(PaymentRefund).where(PaymentRefund.booking_id == uuid.UUID(accepted["id"]))
    ).all()
    assert len(refunds) == 4
    assert {item.status for item in refunds} == {"PROCESSED"}
    ledger_count = db_session.scalar(select(func.count()).select_from(LedgerEntry))
    assert ledger_count == 12

    again = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{accepted['id']}/refund",
        headers=bearer(context["tokens"][0]),
        json={"reason": "Repetição idempotente"},
    )
    assert again.status_code == 200, again.text
    assert again.json()["refunded"] == 0
    assert (
        len(
            db_session.scalars(
                select(PaymentRefund).where(PaymentRefund.booking_id == uuid.UUID(accepted["id"]))
            ).all()
        )
        == 4
    )


def test_substitution_refunds_only_replaced_participant(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)
    user1 = context["users"][1]
    participant = next(item for item in accepted["participants"] if item["user_id"] == str(user1))
    payment = next(
        item for item in accepted["payments"] if item["participant_id"] == participant["id"]
    )
    paid = api.post(
        f"/api/v1/bookings/{accepted['id']}/payments/simulate",
        headers=bearer(context["tokens"][1]),
    )
    assert paid.status_code == 200, paid.text

    new_user = make_user(db_session)
    substituted = api.post(
        f"/api/v1/bookings/{accepted['id']}/substitutions",
        headers=bearer(context["tokens"][0]),
        json={"replace_user_id": str(user1), "new_user_id": str(new_user)},
    )
    assert substituted.status_code == 200, substituted.text
    old_payment = db_session.get(BookingPayment, uuid.UUID(payment["id"]))
    assert old_payment is not None and old_payment.status == "REFUNDED"
    refunds = db_session.scalars(
        select(PaymentRefund).where(PaymentRefund.booking_payment_id == uuid.UUID(payment["id"]))
    ).all()
    assert len(refunds) == 1


def test_t3_expiry_refunds_paid_participants(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)
    for token in context["tokens"][:3]:
        response = api.post(
            f"/api/v1/bookings/{accepted['id']}/payments/simulate",
            headers=bearer(token),
        )
        assert response.status_code == 200, response.text

    BookingService(db_session).expire_due(now=utcnow() + timedelta(hours=2))
    PaymentService(db_session, SimulatorPspAdapter()).refund_cancelled_bookings()
    db_session.commit()
    booking = db_session.get(Booking, uuid.UUID(accepted["id"]))
    assert booking is not None and booking.status == "CANCELLED"
    refunds = db_session.scalars(
        select(PaymentRefund).where(PaymentRefund.booking_id == uuid.UUID(accepted["id"]))
    ).all()
    assert len(refunds) == 3
    assert {item.status for item in refunds} == {"PROCESSED"}


def test_financial_summary_and_booking_ledger(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)

    summary = api.get(
        f"/api/v1/organizations/{context['organization'].id}/financial/summary",
        headers=bearer(context["tokens"][0]),
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["charged_cents"] == 40_000
    assert summary.json()["pending_cents"] == 40_000

    pay_all(api, context, accepted["id"])
    summary = api.get(
        f"/api/v1/organizations/{context['organization'].id}/financial/summary",
        headers=bearer(context["tokens"][0]),
    )
    assert summary.json()["paid_cents"] == 40_000
    assert summary.json()["pending_cents"] == 0

    complete = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{accepted['id']}/complete",
        headers=bearer(context["tokens"][0]),
    )
    assert complete.status_code == 200, complete.text
    summary = api.get(
        f"/api/v1/organizations/{context['organization'].id}/financial/summary",
        headers=bearer(context["tokens"][0]),
    )
    assert summary.json()["released_cents"] == 40_000

    financial = api.get(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{accepted['id']}/financial",
        headers=bearer(context["tokens"][0]),
    )
    assert financial.status_code == 200, financial.text
    body = financial.json()
    assert len(body["ledger"]) == 9
    assert body["refunds"] == []


def test_refund_endpoint_rejects_other_organization(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)
    outsider = make_user(db_session)
    outsider_token = make_token(db_session, outsider)
    response = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{accepted['id']}/refund",
        headers=bearer(outsider_token),
        json={"reason": "Tentativa externa"},
    )
    assert response.status_code == 404
