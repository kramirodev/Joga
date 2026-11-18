"""Testes de serviço/API de pagamentos Pix e webhook (Fase 14A)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import (
    Booking,
    BookingHold,
    BookingParticipant,
    BookingPayment,
)
from app.modules.bookings.service import BookingNotFound, BookingService
from app.modules.identity.clock import utcnow
from app.modules.ledger.models import LedgerTransaction
from app.modules.payments.adapter import (
    PixChargeRequest,
    ProviderStatus,
    RefundResult,
    SimulatorPspAdapter,
)
from app.modules.payments.dependency import get_psp_adapter
from app.modules.payments.models import (
    PaymentEvent,
    PaymentRefund,
    PspWebhookEvent,
    VenueRelease,
)
from app.modules.payments.service import PaymentMismatch, PaymentNotFound, PaymentService
from app.modules.pricing.models import PricingBandTicket
from app.modules.pricing.service import resolve_band
from app.modules.tickets.service import get_balance, grant
from app.modules.venues.models import VenueAvailability
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

    def __init__(
        self,
        orders: dict[str, ProviderStatus],
        *,
        refund_status: str = "processed",
    ) -> None:
        self.orders = orders
        self.refund_status = refund_status

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
            status=self.refund_status,
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


def enable_ticket_settlement(session: Session, context: dict) -> None:
    availability = session.scalar(
        select(VenueAvailability).where(VenueAvailability.venue_space_id == context["space"].id)
    )
    assert availability is not None
    band = resolve_band(session, 30_000)
    availability.band_id = band.id
    configured = session.scalar(
        select(PricingBandTicket).where(
            PricingBandTicket.band_id == band.id,
            PricingBandTicket.team_size == 2,
        )
    )
    if configured is None:
        session.add(PricingBandTicket(band_id=band.id, team_size=2, tickets=6))
    session.commit()


def test_accept_without_payer_email_returns_422(client, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking = create_booking(api, context, context["lobbies"][0])
    confirm_all(api, context, booking["id"])
    client.app.dependency_overrides[get_psp_adapter] = lambda: FakeAdapter({})

    accepted = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{booking['id']}/accept",
        headers=bearer(context["tokens"][0]),
    )
    assert accepted.status_code == 422, accepted.text
    assert accepted.json() == {"detail": {"code": "payer_email_required"}}

    stored = api.get(
        f"/api/v1/bookings/{booking['id']}",
        headers=bearer(context["tokens"][1]),
    )
    assert stored.status_code == 200
    assert stored.json()["status"] != "CONFIRMED"


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

    ledger_count = db_session.scalar(select(func.count()).select_from(PaymentEvent))
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
    release = db_session.scalar(select(VenueRelease).where(VenueRelease.booking_id == booking.id))
    assert release is not None
    assert release.status == "PENDING"
    assert release.amount_cents == 40_000
    release_ledger = db_session.scalar(
        select(func.count())
        .select_from(LedgerTransaction)
        .where(
            LedgerTransaction.ref_type == "venue_release",
            LedgerTransaction.ref_id == release.id,
            LedgerTransaction.kind == "venue_release",
        )
    )
    assert release_ledger == 0


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
    refund_transactions = db_session.scalar(
        select(func.count())
        .select_from(LedgerTransaction)
        .join(BookingPayment, BookingPayment.id == LedgerTransaction.ref_id)
        .where(
            LedgerTransaction.kind == "payment_refund",
            BookingPayment.booking_id == uuid.UUID(accepted["id"]),
        )
    )
    assert refund_transactions == 4

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
    assert summary.json()["charged_cents"] == 48_000
    assert summary.json()["pending_cents"] == 48_000

    pay_all(api, context, accepted["id"])
    summary = api.get(
        f"/api/v1/organizations/{context['organization'].id}/financial/summary",
        headers=bearer(context["tokens"][0]),
    )
    assert summary.json()["paid_cents"] == 48_000
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
    assert summary.json()["released_cents"] == 0
    assert summary.json()["pending_release_cents"] == 40_000

    financial = api.get(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{accepted['id']}/financial",
        headers=bearer(context["tokens"][0]),
    )
    assert financial.status_code == 200, financial.text
    body = financial.json()
    assert len(body["ledger"]) == 1
    entry = body["ledger"][0]
    assert entry["entry_type"] == "PAYMENT_CONFIRMED"
    assert entry["direction"] == "CREDIT"
    assert entry["amount_cents"] == 40_000
    assert entry["booking_payment_id"] is None
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


def test_t3_expiry_returns_tickets(client, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    enable_ticket_settlement(db_session, context)
    accepted = accepted_booking(api, context)
    token = bearer(context["tokens"][1])
    user_id = context["users"][1]
    grant(
        db_session,
        user_id,
        40,
        source="admin",
        idempotency_key=f"test-grant:{user_id}",
    )
    db_session.commit()
    before = get_balance(db_session, user_id)

    settled = api.post(
        f"/api/v1/bookings/{accepted['id']}/settle-with-tickets",
        headers=token,
    )
    assert settled.status_code == 200, settled.text
    assert get_balance(db_session, user_id) < before

    BookingService(db_session).expire_due(now=utcnow() + timedelta(hours=2))
    db_session.commit()
    booking = db_session.get(Booking, uuid.UUID(accepted["id"]))
    assert booking is not None and booking.status == "CANCELLED"
    assert get_balance(db_session, user_id) == before


def test_pix_paid_seat_cannot_be_settled_with_tickets(client, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    enable_ticket_settlement(db_session, context)
    accepted = accepted_booking(api, context)
    token = bearer(context["tokens"][1])
    user_id = context["users"][1]
    grant(
        db_session,
        user_id,
        20,
        source="admin",
        idempotency_key=f"test-grant:{user_id}",
    )
    db_session.commit()
    before = get_balance(db_session, user_id)

    paid = api.post(
        f"/api/v1/bookings/{accepted['id']}/payments/simulate",
        headers=token,
    )
    assert paid.status_code == 200, paid.text

    settled = api.post(
        f"/api/v1/bookings/{accepted['id']}/settle-with-tickets",
        headers=token,
    )
    assert settled.status_code == 200, settled.text
    assert get_balance(db_session, user_id) == before

    participant = next(
        item for item in settled.json()["participants"] if item["user_id"] == str(user_id)
    )
    assert participant["payment_status"] == "PAID"
    assert participant["tickets_consumed"] == 0


def test_refund_processing_does_not_mark_refunded(client, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)
    pay_all(api, context, accepted["id"])

    adapter = FakeAdapter(fake_orders(accepted), refund_status="processing")
    service = PaymentService(db_session, adapter)
    refunded = service.refund_booking(uuid.UUID(accepted["id"]), reason="teste")
    db_session.commit()

    assert refunded == 4
    refunds = db_session.scalars(
        select(PaymentRefund).where(PaymentRefund.booking_id == uuid.UUID(accepted["id"]))
    ).all()
    assert len(refunds) == 4
    assert {item.status for item in refunds} == {"PENDING"}
    payments = db_session.scalars(
        select(BookingPayment).where(BookingPayment.booking_id == uuid.UUID(accepted["id"]))
    ).all()
    assert {item.status for item in payments} == {"PAID"}
    participants = db_session.scalars(
        select(BookingParticipant).where(BookingParticipant.booking_id == uuid.UUID(accepted["id"]))
    ).all()
    assert {item.payment_status for item in participants} == {"PAID"}


def test_refund_reverses_venue_release(client, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)
    pay_all(api, context, accepted["id"])
    completed = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{accepted['id']}/complete",
        headers=bearer(context["tokens"][0]),
    )
    assert completed.status_code == 200, completed.text

    release = db_session.scalar(
        select(VenueRelease).where(VenueRelease.booking_id == uuid.UUID(accepted["id"]))
    )
    assert release is not None and release.status == "PENDING"

    PaymentService(db_session, SimulatorPspAdapter()).refund_booking(
        uuid.UUID(accepted["id"]),
        reason="teste de reversão",
    )
    db_session.commit()
    db_session.refresh(release)
    assert release.status == "REVERSED"
    assert release.reversed_at is not None


def test_participant_accepts_expired_payment_status(
    client,
    db_session: Session,
) -> None:
    context = setup_booking(db_session)
    booking = create_booking(
        api_client(client, db_session),
        context,
        context["lobbies"][0],
    )
    participant = db_session.scalar(
        select(BookingParticipant).where(BookingParticipant.booking_id == uuid.UUID(booking["id"]))
    )
    assert participant is not None
    participant.payment_status = "EXPIRED"
    db_session.commit()
    db_session.refresh(participant)
    assert participant.payment_status == "EXPIRED"
