"""Testes do gancho de XP e missões na partida concluída (Fase 14D.9)."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking, BookingParticipant
from app.modules.bookings.service import BookingService
from app.modules.matchmaking.models import Lobby
from app.modules.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationVenue,
)
from app.modules.organizations.permissions import Role
from app.modules.season.models import MissionProgress
from app.modules.season.service import (
    MATCH_XP,
    NEW_VENUE_XP,
    get_progress,
    seed_current_season,
)
from app.modules.venues.models import VenueAvailability, VenueSpace
from tests.helpers_results import make_format, make_token, make_user

START = datetime.now(UTC) + timedelta(days=3)
START = START.replace(hour=19, minute=0, second=0, microsecond=0)
END = START + timedelta(minutes=60)


def build_confirmed_booking(db_session: Session) -> tuple[dict, Booking]:
    owner_id = make_user(db_session)
    player_id = make_user(db_session)
    _, format_ = make_format(db_session, team_size=3)

    organization = Organization(name="Arena XP")
    db_session.add(organization)
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=owner_id,
            role=Role.OWNER.value,
        )
    )
    venue = OrganizationVenue(
        organization_id=organization.id, name="Arena XP Centro", timezone="UTC"
    )
    db_session.add(venue)
    db_session.flush()
    space = VenueSpace(organization_venue_id=venue.id, name="Quadra 1")
    db_session.add(space)
    db_session.flush()
    db_session.add(
        VenueAvailability(
            venue_space_id=space.id,
            weekday=START.isoweekday(),
            start_time=time(17, 0),
            end_time=time(23, 0),
            price_cents=12_000,
            slot_minutes=60,
        )
    )
    lobby = Lobby(
        format_id=format_.id,
        format_version=1,
        origin="manual",
        mode="casual",
        status="scheduled",
        court_preference="PRIVATE_ONLY",
        scheduled_start_at=START,
        scheduled_end_at=END,
        duration_minutes=60,
        center_lat=-22.9,
        center_lng=-43.2,
        radius_km=10,
        algorithm_version="manual_v1",
    )
    db_session.add(lobby)
    db_session.flush()
    booking = Booking(
        lobby_id=lobby.id,
        organization_id=organization.id,
        organization_venue_id=venue.id,
        venue_space_id=space.id,
        created_by=owner_id,
        status="CONFIRMED",
        starts_at=START,
        ends_at=END,
        price_cents=12_000,
        seats=1,
        policy_version="v1",
        cancellation_policy="full_refund_until_confirmed",
        payment_version=1,
    )
    db_session.add(booking)
    db_session.flush()
    db_session.add(
        BookingParticipant(
            booking_id=booking.id,
            user_id=player_id,
            seat=1,
            contribution_cents=12_000,
            payment_status="PAID",
            confirmed_at=START,
            presence_status="PRESENT",
        )
    )
    db_session.flush()
    return {"owner_id": owner_id, "player_id": player_id, "space": space}, booking


def test_completion_awards_xp_and_missions(client: TestClient, db_session: Session) -> None:
    context, booking = build_confirmed_booking(db_session)
    season = seed_current_season(db_session)
    db_session.flush()

    BookingService(db_session).complete(context["owner_id"], booking.id)
    db_session.flush()

    progress = get_progress(db_session, context["player_id"], season)
    assert progress is not None
    assert progress.xp_total == MATCH_XP + 40 + NEW_VENUE_XP + 40

    missions = {
        row.mission_code: row
        for row in db_session.scalars(
            select(MissionProgress).where(
                MissionProgress.user_id == context["player_id"],
                MissionProgress.season_id == season.id,
            )
        ).all()
    }
    assert missions["play_one"].completed_at is not None
    assert missions["new_venue"].completed_at is not None


def test_completion_is_idempotent_for_xp(client: TestClient, db_session: Session) -> None:
    context, booking = build_confirmed_booking(db_session)
    season = seed_current_season(db_session)
    db_session.flush()

    service = BookingService(db_session)
    service.complete(context["owner_id"], booking.id)
    service.complete(context["owner_id"], booking.id)
    db_session.flush()

    progress = get_progress(db_session, context["player_id"], season)
    assert progress is not None
    assert progress.xp_total == MATCH_XP + 40 + NEW_VENUE_XP + 40


def test_missions_endpoint_lists_three(client: TestClient, db_session: Session) -> None:
    from app.infrastructure.database.dependency import get_session

    def override_session():
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    seed_current_season(db_session)
    db_session.commit()

    response = client.get(
        "/api/v1/me/progress/missions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert {item["code"] for item in body["missions"]} == {
        "play_one",
        "new_venue",
        "on_time_checkin",
    }
    assert all(item["progress"] == 0 for item in body["missions"])
