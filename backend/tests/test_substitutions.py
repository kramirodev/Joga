"""Testes da fila de substitutos e cancelamento individual (ADR 0039)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import (
    Booking,
    BookingParticipant,
    BookingPayment,
    BookingRefundExclusion,
    BookingSubstitution,
)
from app.modules.bookings.substitutions import (
    BookingSubstitutionService,
    CancellationClosed,
    SubstitutionConflict,
)
from app.modules.matchmaking.models import Lobby, LobbySubstitute
from app.modules.payments.adapter import SimulatorPspAdapter
from app.modules.payments.models import PaymentRefund
from app.modules.payments.service import PaymentService
from tests.helpers_results import make_token, make_user
from tests.test_bookings_api import api_client, bearer, setup_booking
from tests.test_payments_service import accepted_booking, pay_all


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def confirmed_booking(api, context) -> dict:
    accepted = accepted_booking(api, context)
    pay_all(api, context, accepted["id"])
    booking = api.get(
        f"/api/v1/bookings/{accepted['id']}",
        headers=bearer(context["tokens"][0]),
    )
    assert booking.status_code == 200, booking.text
    assert booking.json()["status"] == "CONFIRMED"
    return booking.json()


def test_substitute_queue_join_list_and_leave(client, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    lobby_id = context["lobbies"][0].id
    outsider = make_user(db_session)
    outsider_token = make_token(db_session, outsider)

    joined = api.post(
        f"/api/v1/lobbies/{lobby_id}/substitutes",
        headers=bearer(outsider_token),
    )
    assert joined.status_code == 201, joined.text
    assert joined.json()["status"] == "STANDBY"
    assert joined.json()["position"] == 1

    duplicate = api.post(
        f"/api/v1/lobbies/{lobby_id}/substitutes",
        headers=bearer(outsider_token),
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == joined.json()["id"]
    assert db_session.scalar(select(func.count()).select_from(LobbySubstitute)) == 1

    visible = api.get(
        f"/api/v1/lobbies/{lobby_id}/substitutes",
        headers=bearer(context["tokens"][0]),
    )
    assert visible.status_code == 200
    assert visible.json()["count"] == 1

    hidden = api.get(
        f"/api/v1/lobbies/{lobby_id}/substitutes",
        headers=bearer(make_token(db_session, make_user(db_session))),
    )
    assert hidden.status_code == 403

    left = api.delete(
        f"/api/v1/lobbies/{lobby_id}/substitutes",
        headers=bearer(outsider_token),
    )
    assert left.status_code == 204
    assert db_session.scalar(select(func.count()).select_from(LobbySubstitute)) == 0


def test_participant_cancellation_opens_t4_without_refund(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking_id = uuid.UUID(booking_view["id"])

    response = api.post(
        f"/api/v1/bookings/{booking_id}/participant-cancellations",
        headers=bearer(context["tokens"][0]),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "OPEN"
    assert body["outgoing_user_id"] == str(context["users"][0])
    assert aware(datetime.fromisoformat(body["deadline_at"])) > datetime.now(UTC)

    db_session.expire_all()
    booking = db_session.get(Booking, booking_id)
    assert booking is not None and booking.status == "CONFIRMED"
    participant = db_session.scalar(
        select(BookingParticipant).where(
            BookingParticipant.booking_id == booking_id,
            BookingParticipant.user_id == context["users"][0],
        )
    )
    assert participant is not None and participant.active is False
    assert participant.left_at is not None
    assert db_session.scalar(select(func.count()).select_from(PaymentRefund)) == 0
    assert db_session.scalar(select(func.count()).select_from(BookingRefundExclusion)) == 1

    again = api.post(
        f"/api/v1/bookings/{booking_id}/participant-cancellations",
        headers=bearer(context["tokens"][0]),
    )
    assert again.status_code == 201
    assert again.json()["id"] == body["id"]

    listed = api.get(
        f"/api/v1/bookings/{booking_id}/substitutions",
        headers=bearer(context["tokens"][0]),
    )
    assert listed.status_code == 200
    assert len(listed.json()["substitutions"]) == 1


def test_participant_cancellation_after_cutoff_is_rejected(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking = db_session.get(Booking, uuid.UUID(booking_view["id"]))
    assert booking is not None

    with pytest.raises(CancellationClosed):
        BookingSubstitutionService(db_session).cancel_participant(
            context["users"][0],
            booking.id,
            now=aware(booking.starts_at) - timedelta(hours=5),
        )
    db_session.rollback()


def test_expiry_cancels_lobby_and_refunds_others_not_canceller(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking_id = uuid.UUID(booking_view["id"])
    service = BookingSubstitutionService(db_session)

    substitution = service.cancel_participant(context["users"][0], booking_id)
    db_session.commit()
    expired = service.expire_due(now=aware(substitution.deadline_at) + timedelta(minutes=1))
    db_session.commit()
    assert expired == 1
    refunded = PaymentService(db_session, SimulatorPspAdapter()).refund_cancelled_bookings()
    db_session.commit()
    assert refunded == 3

    db_session.expire_all()
    booking = db_session.get(Booking, booking_id)
    assert booking is not None
    assert booking.status == "CANCELLED"
    assert booking.cancellation_reason == "no_substitute"
    lobby = db_session.get(Lobby, booking.lobby_id)
    assert lobby is not None and lobby.status == "cancelled"
    substitution = db_session.get(BookingSubstitution, substitution.id)
    assert substitution is not None and substitution.status == "EXPIRED"

    payments = db_session.scalars(
        select(BookingParticipant).where(BookingParticipant.booking_id == booking_id)
    ).all()
    canceller = next(item for item in payments if item.user_id == context["users"][0])
    assert canceller.payment_status == "PAID"
    others = [item for item in payments if item.user_id != context["users"][0]]
    assert {item.payment_status for item in others} == {"REFUNDED"}
    assert db_session.scalar(select(func.count()).select_from(PaymentRefund)) == 3

    # Worker também respeita a exclusão.
    again = PaymentService(db_session, SimulatorPspAdapter()).refund_cancelled_bookings()
    db_session.commit()
    assert again == 0
    assert db_session.scalar(select(func.count()).select_from(PaymentRefund)) == 3

    summary = api.get(
        f"/api/v1/organizations/{context['organization'].id}/financial/summary",
        headers=bearer(context["tokens"][0]),
    )
    assert summary.status_code == 200
    assert summary.json()["refunded_cents"] == 30_000
    assert summary.json()["paid_cents"] == 10_000


def test_assign_substitute_opens_payment_and_refunds_outgoing(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking_id = uuid.UUID(booking_view["id"])
    lobby_id = context["lobbies"][0].id
    substitute = make_user(db_session)
    substitute_token = make_token(db_session, substitute)

    joined = api.post(
        f"/api/v1/lobbies/{lobby_id}/substitutes",
        headers=bearer(substitute_token),
    )
    assert joined.status_code == 201, joined.text

    cancellation = api.post(
        f"/api/v1/bookings/{booking_id}/participant-cancellations",
        headers=bearer(context["tokens"][0]),
    )
    assert cancellation.status_code == 201, cancellation.text

    assigned = api.post(
        f"/api/v1/bookings/{booking_id}/substitutions/{cancellation.json()['id']}/assign",
        headers=bearer(context["tokens"][0]),
        json={"substitute_user_id": str(substitute)},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status"] == "AWAITING_PAYMENT"
    assert assigned.json()["filled_by_user_id"] == str(substitute)
    assert assigned.json()["substitute_payment_id"]

    db_session.expire_all()
    booking = db_session.get(Booking, booking_id)
    assert booking is not None and booking.status == "PAYMENT_PENDING"
    queue_entry = db_session.scalar(
        select(LobbySubstitute).where(
            LobbySubstitute.lobby_id == lobby_id,
            LobbySubstitute.user_id == substitute,
        )
    )
    assert queue_entry is not None and queue_entry.status == "CONFIRMED"

    paid = api.post(
        f"/api/v1/bookings/{booking_id}/payments/simulate",
        headers=bearer(substitute_token),
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "CONFIRMED"

    db_session.expire_all()
    substitution = db_session.get(BookingSubstitution, uuid.UUID(assigned.json()["id"]))
    assert substitution is not None and substitution.status == "FILLED"
    outgoing_participant = db_session.scalar(
        select(BookingParticipant).where(
            BookingParticipant.booking_id == booking_id,
            BookingParticipant.user_id == context["users"][0],
        )
    )
    assert outgoing_participant is not None
    assert outgoing_participant.payment_status == "REFUNDED"
    assert db_session.scalar(select(func.count()).select_from(PaymentRefund)) == 1


def test_assignment_expires_if_substitute_does_not_pay(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking_id = uuid.UUID(booking_view["id"])
    substitute = make_user(db_session)

    cancellation = api.post(
        f"/api/v1/bookings/{booking_id}/participant-cancellations",
        headers=bearer(context["tokens"][0]),
    )
    assert cancellation.status_code == 201, cancellation.text
    assigned = api.post(
        f"/api/v1/bookings/{booking_id}/substitutions/{cancellation.json()['id']}/assign",
        headers=bearer(context["tokens"][0]),
        json={"substitute_user_id": str(substitute)},
    )
    assert assigned.status_code == 200, assigned.text
    substitution = db_session.get(BookingSubstitution, uuid.UUID(assigned.json()["id"]))
    assert substitution is not None

    service = BookingSubstitutionService(db_session)
    expired = service.expire_due(now=aware(substitution.deadline_at) + timedelta(minutes=1))
    db_session.commit()
    assert expired == 1
    refunded = PaymentService(db_session, SimulatorPspAdapter()).refund_cancelled_bookings()
    db_session.commit()
    assert refunded == 3

    db_session.expire_all()
    booking = db_session.get(Booking, booking_id)
    assert booking is not None and booking.status == "CANCELLED"
    substitution = db_session.get(BookingSubstitution, substitution.id)
    assert substitution is not None and substitution.status == "EXPIRED"
    participant = db_session.scalar(
        select(BookingParticipant).where(
            BookingParticipant.booking_id == booking_id,
            BookingParticipant.user_id == substitute,
        )
    )
    assert participant is not None and participant.active is False
    assert participant.payment_status == "FAILED"
    assert db_session.scalar(select(func.count()).select_from(PaymentRefund)) == 3


def test_cancel_calls_queue_and_called_substitute_accepts(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking_id = uuid.UUID(booking_view["id"])
    lobby_id = context["lobbies"][0].id
    substitute = make_user(db_session)
    substitute_token = make_token(db_session, substitute)
    joined = api.post(
        f"/api/v1/lobbies/{lobby_id}/substitutes",
        headers=bearer(substitute_token),
    )
    assert joined.status_code == 201, joined.text

    cancellation = api.post(
        f"/api/v1/bookings/{booking_id}/participant-cancellations",
        headers=bearer(context["tokens"][0]),
    )
    assert cancellation.status_code == 201, cancellation.text
    assert cancellation.json()["status"] == "CALLED"
    assert cancellation.json()["called_user_id"] == str(substitute)
    assert cancellation.json()["call_deadline_at"]

    accepted = api.post(
        f"/api/v1/bookings/{booking_id}/substitutions/{cancellation.json()['id']}/accept",
        headers=bearer(substitute_token),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "AWAITING_PAYMENT"

    paid = api.post(
        f"/api/v1/bookings/{booking_id}/payments/simulate",
        headers=bearer(substitute_token),
    )
    assert paid.status_code == 200, paid.text
    db_session.expire_all()
    substitution = db_session.get(BookingSubstitution, uuid.UUID(cancellation.json()["id"]))
    assert substitution is not None and substitution.status == "FILLED"
    assert db_session.scalar(select(func.count()).select_from(PaymentRefund)) == 1


def test_declining_call_moves_to_next_and_timeout_retries(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking_id = uuid.UUID(booking_view["id"])
    lobby_id = context["lobbies"][0].id
    first = make_user(db_session)
    second = make_user(db_session)
    first_token = make_token(db_session, first)
    second_token = make_token(db_session, second)
    for token in (first_token, second_token):
        joined = api.post(
            f"/api/v1/lobbies/{lobby_id}/substitutes",
            headers=bearer(token),
        )
        assert joined.status_code == 201, joined.text

    cancellation = api.post(
        f"/api/v1/bookings/{booking_id}/participant-cancellations",
        headers=bearer(context["tokens"][0]),
    )
    assert cancellation.status_code == 201, cancellation.text
    substitution_id = uuid.UUID(cancellation.json()["id"])
    assert cancellation.json()["called_user_id"] == str(first)

    declined = api.post(
        f"/api/v1/bookings/{booking_id}/substitutions/{substitution_id}/decline",
        headers=bearer(first_token),
    )
    assert declined.status_code == 200, declined.text
    assert declined.json()["called_user_id"] == str(second)

    substitution = db_session.get(BookingSubstitution, substitution_id)
    assert substitution is not None and substitution.call_deadline_at is not None
    service = BookingSubstitutionService(db_session)
    service.expire_due(now=aware(substitution.call_deadline_at) + timedelta(minutes=1))
    db_session.commit()
    db_session.expire_all()
    substitution = db_session.get(BookingSubstitution, substitution_id)
    assert substitution is not None
    # Sem terceiro substituto, a vaga volta para OPEN.
    assert substitution.status == "OPEN"
    queues = db_session.scalars(
        select(LobbySubstitute)
        .where(LobbySubstitute.lobby_id == lobby_id)
        .order_by(LobbySubstitute.position)
    ).all()
    assert {item.status for item in queues} == {"DECLINED"}


def test_two_cancellations_make_even_and_cancel_pending_call(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking_id = uuid.UUID(booking_view["id"])
    lobby_id = context["lobbies"][0].id
    substitute = make_user(db_session)
    substitute_token = make_token(db_session, substitute)
    joined = api.post(
        f"/api/v1/lobbies/{lobby_id}/substitutes",
        headers=bearer(substitute_token),
    )
    assert joined.status_code == 201, joined.text

    first = api.post(
        f"/api/v1/bookings/{booking_id}/participant-cancellations",
        headers=bearer(context["tokens"][0]),
    )
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "CALLED"

    second = api.post(
        f"/api/v1/bookings/{booking_id}/participant-cancellations",
        headers=bearer(context["tokens"][1]),
    )
    assert second.status_code == 201, second.text
    assert second.json()["status"] == "OPEN"

    db_session.expire_all()
    first_sub = db_session.get(BookingSubstitution, uuid.UUID(first.json()["id"]))
    assert first_sub is not None and first_sub.status == "OPEN"
    queue_entry = db_session.scalar(
        select(LobbySubstitute).where(
            LobbySubstitute.lobby_id == lobby_id,
            LobbySubstitute.user_id == substitute,
        )
    )
    assert queue_entry is not None and queue_entry.status == "STANDBY"


def test_paid_seat_no_show_substitute_plays_without_new_charge(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking_id = uuid.UUID(booking_view["id"])
    booking = db_session.get(Booking, booking_id)
    assert booking is not None
    substitute = make_user(db_session)
    substitute_token = make_token(db_session, substitute)
    joined = api.post(
        f"/api/v1/lobbies/{booking.lobby_id}/substitutes",
        headers=bearer(substitute_token),
    )
    assert joined.status_code == 201, joined.text

    service = BookingSubstitutionService(db_session)
    no_show_at = aware(booking.starts_at) - timedelta(hours=1)
    substitution = service.mark_no_show(
        context["users"][0],
        booking_id,
        context["users"][1],
        reason="Não chegou",
        now=no_show_at,
    )
    db_session.commit()
    assert substitution.paid_seat is True
    assert substitution.status == "CALLED"
    assert substitution.called_user_id == substitute

    assigned = api.post(
        f"/api/v1/bookings/{booking_id}/substitutions/{substitution.id}/accept",
        headers=bearer(substitute_token),
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["paid_seat"] is True
    assert assigned.json()["status"] == "FILLED"
    assert assigned.json()["substitute_payment_id"] is None

    db_session.expire_all()
    booking = db_session.get(Booking, booking_id)
    assert booking is not None and booking.status == "CONFIRMED"
    outgoing = db_session.scalar(
        select(BookingParticipant).where(
            BookingParticipant.booking_id == booking_id,
            BookingParticipant.user_id == context["users"][1],
        )
    )
    assert outgoing is not None and outgoing.active is False
    outgoing_payment = db_session.scalar(
        select(BookingPayment).where(
            BookingPayment.booking_id == booking_id,
            BookingPayment.participant_id == outgoing.id,
            BookingPayment.status == "PAID",
        )
    )
    assert outgoing_payment is not None
    incoming = db_session.scalar(
        select(BookingParticipant).where(
            BookingParticipant.booking_id == booking_id,
            BookingParticipant.user_id == substitute,
        )
    )
    assert incoming is not None and incoming.active is True
    assert incoming.payment_status == "WAIVED"
    substitution = db_session.get(BookingSubstitution, substitution.id)
    assert substitution is not None
    assert substitution.covered_by_payment_id == outgoing_payment.id
    assert db_session.scalar(select(func.count()).select_from(PaymentRefund)) == 0
    queue_entry = db_session.scalar(
        select(LobbySubstitute).where(
            LobbySubstitute.lobby_id == booking.lobby_id,
            LobbySubstitute.user_id == substitute,
        )
    )
    assert queue_entry is not None and queue_entry.status == "PLAYED"


def test_paid_seat_without_substitute_does_not_cancel_booking(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking_id = uuid.UUID(booking_view["id"])
    booking = db_session.get(Booking, booking_id)
    assert booking is not None
    service = BookingSubstitutionService(db_session)
    substitution = service.mark_no_show(
        context["users"][0],
        booking_id,
        context["users"][1],
        now=aware(booking.starts_at) - timedelta(hours=1),
    )
    db_session.commit()

    expired = service.expire_due(now=aware(substitution.deadline_at) + timedelta(minutes=1))
    db_session.commit()
    assert expired == 1

    db_session.expire_all()
    booking = db_session.get(Booking, booking_id)
    assert booking is not None and booking.status == "CONFIRMED"
    substitution = db_session.get(BookingSubstitution, substitution.id)
    assert substitution is not None and substitution.status == "EXPIRED"
    assert db_session.scalar(select(func.count()).select_from(PaymentRefund)) == 0


def test_no_show_before_cutoff_is_rejected(client, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking = db_session.get(Booking, uuid.UUID(booking_view["id"]))
    assert booking is not None

    with pytest.raises(SubstitutionConflict):
        BookingSubstitutionService(db_session).mark_no_show(
            context["users"][0],
            booking.id,
            context["users"][1],
            now=aware(booking.starts_at) - timedelta(hours=7),
        )
    db_session.rollback()


def test_outsider_cannot_assign_substitute(client, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking_id = uuid.UUID(booking_view["id"])
    cancellation = api.post(
        f"/api/v1/bookings/{booking_id}/participant-cancellations",
        headers=bearer(context["tokens"][0]),
    )
    assert cancellation.status_code == 201, cancellation.text
    outsider_token = make_token(db_session, make_user(db_session))
    substitute = make_user(db_session)

    response = api.post(
        f"/api/v1/bookings/{booking_id}/substitutions/{cancellation.json()['id']}/assign",
        headers=bearer(outsider_token),
        json={"substitute_user_id": str(substitute)},
    )
    assert response.status_code == 403


def test_player_whole_booking_cancel_does_not_refund_initiator(
    client,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    booking_id = uuid.UUID(booking_view["id"])

    response = api.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        headers=bearer(context["tokens"][0]),
        json={"reason": "Não vamos jogar"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED_BY_PLAYER"

    db_session.expire_all()
    participants = db_session.scalars(
        select(BookingParticipant).where(BookingParticipant.booking_id == booking_id)
    ).all()
    canceller = next(item for item in participants if item.user_id == context["users"][0])
    assert canceller.payment_status == "PAID"
    others = [item for item in participants if item.user_id != context["users"][0]]
    assert {item.payment_status for item in others} == {"REFUNDED"}
    assert db_session.scalar(select(func.count()).select_from(PaymentRefund)) == 3


def test_outsider_cannot_cancel_participant(client, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = setup_booking(db_session)
    booking_view = confirmed_booking(api, context)
    outsider_token = make_token(db_session, make_user(db_session))

    response = api.post(
        f"/api/v1/bookings/{booking_view['id']}/participant-cancellations",
        headers=bearer(outsider_token),
    )
    assert response.status_code == 404
