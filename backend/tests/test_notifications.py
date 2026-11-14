"""Testes da central de notificações e gatilhos de reserva."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.notifications.service import NotificationService
from app.modules.outbox.models import OutboxEvent
from tests.helpers_results import make_token, make_user
from tests.test_bookings_api import api_client as booking_api_client
from tests.test_bookings_api import bearer, setup_booking


def test_notification_list_read_and_ownership(client: TestClient, db_session: Session) -> None:
    api = booking_api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    service = NotificationService(db_session)
    notification, created = service.create(
        user_id=user_id,
        kind="test",
        title="Título",
        body="Corpo",
        idempotency_key="test:1",
        data={"ref": "x"},
    )
    _same, duplicate = service.create(
        user_id=user_id,
        kind="test",
        title="Título",
        body="Corpo",
        idempotency_key="test:1",
    )
    assert created is True and duplicate is False
    event = db_session.scalar(
        select(OutboxEvent).where(OutboxEvent.event_type == "notification.created")
    )
    assert event is not None
    db_session.commit()

    listing = api.get("/api/v1/me/notifications", headers=bearer(token))
    assert listing.status_code == 200, listing.text
    assert listing.json()["unread_count"] == 1
    assert listing.json()["notifications"][0]["title"] == "Título"

    read = api.post(f"/api/v1/me/notifications/{notification.id}/read", headers=bearer(token))
    assert read.status_code == 200, read.text
    assert read.json()["read_at"] is not None

    other_id = make_user(db_session)
    other_token = make_token(db_session, other_id)
    foreign = api.post(
        f"/api/v1/me/notifications/{notification.id}/read",
        headers=bearer(other_token),
    )
    assert foreign.status_code == 404

    marked = api.post("/api/v1/me/notifications/read-all", headers=bearer(token))
    assert marked.status_code == 200, marked.text
    assert marked.json()["marked"] == 0


def test_booking_creates_notifications_for_venue_and_participants(
    client: TestClient,
    db_session: Session,
) -> None:
    api = booking_api_client(client, db_session)
    context = setup_booking(db_session)
    from tests.test_bookings_api import confirm_all, create_booking

    booking = create_booking(api, context, context["lobbies"][0])
    confirm_all(api, context, booking["id"])
    owner_view = api.get("/api/v1/me/notifications", headers=bearer(context["tokens"][0]))
    assert owner_view.status_code == 200, owner_view.text
    assert any(item["kind"] == "booking_requested" for item in owner_view.json()["notifications"])

    accepted = api.post(
        f"/api/v1/organizations/{context['organization'].id}/bookings/{booking['id']}/accept",
        headers=bearer(context["tokens"][0]),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "PAYMENT_PENDING"
    participant_view = api.get(
        "/api/v1/me/notifications",
        headers=bearer(context["tokens"][1]),
    )
    assert participant_view.status_code == 200, participant_view.text
    assert any(
        item["kind"] == "booking_accepted" for item in participant_view.json()["notifications"]
    )
