"""Card público do jogador: mesmo snapshot do dono, tema e privacidade."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.bookings.models import Booking
from app.modules.identity.clock import utcnow
from app.modules.identity.models import User
from app.modules.matches.models import Match, MatchParticipant
from app.modules.matchmaking.models import Lobby
from app.modules.profile.models import UserProfile, UserSportProfile
from app.modules.ratings.models import RatingAccount, SeasonPlacement
from app.modules.season.models import Badge, PlayerBadge, SeasonProgress, WinStreak
from app.modules.season.service import active_season, quarter_bounds, week_start
from app.modules.venues.models import VenueSpace
from app.modules.visual.models import UserVisualIdentity
from app.modules.visual.seed import DEFAULT_IDENTITY_KEYS
from tests.helpers_results import make_format, make_token, make_user

MATCH_AT = datetime(2026, 11, 10, 22, 0, tzinfo=UTC)


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def add_player(
    session: Session,
    display_name: str | None,
    *,
    status: str = "active",
    tag: str | None = None,
    email: str | None = None,
) -> uuid.UUID:
    user_id = make_user(session, available=False)
    user = session.get(User, user_id)
    assert user is not None
    user.status = status
    if tag is not None:
        user.tag = tag
    if email is not None:
        user.email = email
    session.add(UserProfile(user_id=user_id, display_name=display_name))
    session.flush()
    return user_id


def add_finished_match(
    session: Session,
    *,
    user_id: uuid.UUID,
    when: datetime = MATCH_AT,
) -> None:
    space = VenueSpace(organization_venue_id=uuid.uuid4(), name="Arena Card", is_covered=True)
    session.add(space)
    session.flush()
    _, sport_format = make_format(session)
    lobby = Lobby(
        format_id=sport_format.id,
        format_version=1,
        origin="matchmaking",
        mode="casual",
        status="completed",
        court_preference="ANY",
        scheduled_start_at=when,
        scheduled_end_at=when + timedelta(minutes=60),
        duration_minutes=60,
        center_lat=-23.55,
        center_lng=-46.63,
        radius_km=10,
        algorithm_version="level_v1",
    )
    session.add(lobby)
    session.flush()
    match = Match(
        lobby_id=lobby.id,
        state="FINALIZED",
        scheduled_start_at=when,
        scheduled_end_at=when + timedelta(minutes=60),
        confirmation_deadline=when - timedelta(hours=24),
        check_in_opens_at=when - timedelta(hours=1),
        check_in_deadline=when - timedelta(minutes=30),
        substitution_deadline=when - timedelta(minutes=15),
        final_result="TEAM_1",
        finalized_at=when + timedelta(minutes=60),
    )
    session.add(match)
    session.flush()
    session.add(
        Booking(
            lobby_id=lobby.id,
            organization_id=uuid.uuid4(),
            organization_venue_id=space.organization_venue_id,
            venue_space_id=space.id,
            starts_at=when,
            ends_at=when + timedelta(minutes=60),
            price_cents=0,
            seats=10,
            policy_version="v1",
            cancellation_policy="standard",
        )
    )
    session.add(
        MatchParticipant(
            match_id=match.id,
            user_id=user_id,
            team=1,
            level="intermediate",
            status="checked_in",
        )
    )
    session.flush()


def expected_season_label() -> str:
    now = utcnow()
    quarter, _starts, _ends = quarter_bounds(now)
    return f"T{quarter} {now.year}"


def test_public_card_matches_owner_snapshot(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, add_player(db_session, "VISITANTE CARD"))
    target = add_player(db_session, "CARD COMPLETO", tag="#CARD0001")
    season = active_season(db_session, utcnow())

    profile = db_session.get(UserProfile, target)
    assert profile is not None
    profile.theme_id = "noite-quadra"
    db_session.add(
        UserVisualIdentity(
            user_id=target,
            icon_key="icon-sport-volei-6x6",
            frame_key=DEFAULT_IDENTITY_KEYS["frame"],
            accent_key=DEFAULT_IDENTITY_KEYS["accent"],
            entry_key=DEFAULT_IDENTITY_KEYS["entry"],
            emote_key=DEFAULT_IDENTITY_KEYS["emote"],
            badge_key=DEFAULT_IDENTITY_KEYS["badge"],
            catalog_version=1,
        )
    )
    _sport, sport_format = make_format(db_session)
    db_session.add(
        UserSportProfile(
            user_id=target,
            format_id=sport_format.id,
            level="intermediate",
            court_preference="ANY",
        )
    )
    db_session.add(
        RatingAccount(
            user_id=target,
            format_id=sport_format.id,
            rating=1250.0,
            rating_deviation=80.0,
            volatility=0.06,
            matches_played=5,
        )
    )
    db_session.add(SeasonPlacement(user_id=target, season_id=season.id, matches_played=5))
    db_session.add(SeasonProgress(user_id=target, season_id=season.id, xp_total=1600, level=10))
    db_session.add(
        WinStreak(
            user_id=target,
            current_wins=3,
            best_wins=4,
            last_match_week=week_start(utcnow()),
        )
    )
    founder = Badge(code="fundador", name="Fundadora", kind="founder")
    season_badge = Badge(code="temporada_t4", name="Temporada T4", kind="season")
    medal = Badge(code="medalha_x", name="Medalha X", kind="medal")
    unused = Badge(code="nao_equipada", name="Não equipada", kind="medal")
    db_session.add_all([founder, season_badge, medal, unused])
    db_session.flush()
    db_session.add_all(
        [
            PlayerBadge(user_id=target, badge_id=season_badge.id, equipped_slot=2),
            PlayerBadge(user_id=target, badge_id=founder.id, equipped_slot=1),
            PlayerBadge(user_id=target, badge_id=medal.id, equipped_slot=3),
            PlayerBadge(user_id=target, badge_id=unused.id, equipped_slot=None),
        ]
    )
    add_finished_match(db_session, user_id=target)
    db_session.flush()

    response = api.get(f"/api/v1/users/{target}", headers=bearer(token))

    assert response.status_code == 200, response.text
    card = response.json()["card"]
    assert card["theme_id"] == "noite-quadra"
    assert card["visual"] == {
        "icon_key": "icon-sport-volei-6x6",
        "frame_key": DEFAULT_IDENTITY_KEYS["frame"],
        "accent_key": DEFAULT_IDENTITY_KEYS["accent"],
        "entry_key": DEFAULT_IDENTITY_KEYS["entry"],
        "emote_key": DEFAULT_IDENTITY_KEYS["emote"],
        "badge_key": DEFAULT_IDENTITY_KEYS["badge"],
        "catalog_version": 1,
    }
    assert card["tier"] == "prata"
    assert card["level"] == 10
    assert card["qualifier"] == "PRATA"
    assert card["season_label"] == expected_season_label()
    assert card["record"] == 1
    assert card["win_streak"] == 3
    assert card["badges"] == [
        {"code": "fundador", "name": "Fundadora", "kind": "founder"},
        {"code": "temporada_t4", "name": "Temporada T4", "kind": "season"},
        {"code": "medalha_x", "name": "Medalha X", "kind": "medal"},
    ]


def test_public_card_without_data_uses_defaults_and_nulls(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, add_player(db_session, "VISITANTE VAZIO"))
    target = add_player(db_session, "CARD VAZIO")

    response = api.get(f"/api/v1/users/{target}", headers=bearer(token))

    assert response.status_code == 200, response.text
    card = response.json()["card"]
    assert card["theme_id"] is None
    assert card["visual"]["icon_key"] == DEFAULT_IDENTITY_KEYS["icon"]
    assert card["visual"]["badge_key"] == DEFAULT_IDENTITY_KEYS["badge"]
    assert card["visual"]["catalog_version"] == 1
    assert card["tier"] == "bronze"
    assert card["level"] == 0
    assert card["qualifier"] is None
    assert card["season_label"] == expected_season_label()
    assert card["record"] == 0
    assert card["win_streak"] == 0
    assert card["badges"] == []


def test_public_card_qualifier_is_provisional_without_rating(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, add_player(db_session, "VISITANTE PROVISORIO"))
    target = add_player(db_session, "CARD PROVISORIO")
    _, sport_format = make_format(db_session)
    db_session.add(
        UserSportProfile(
            user_id=target,
            format_id=sport_format.id,
            level="beginner",
            court_preference="ANY",
        )
    )
    db_session.flush()

    response = api.get(f"/api/v1/users/{target}", headers=bearer(token))

    assert response.status_code == 200, response.text
    assert response.json()["card"]["qualifier"] == "PROVISÓRIO"


def test_theme_is_persisted_and_served_publicly(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    owner = add_player(db_session, "DONO DO TEMA")
    owner_token = make_token(db_session, owner)
    viewer_token = make_token(db_session, add_player(db_session, "VISITANTE TEMA"))

    updated = api.put(
        "/api/v1/me/theme",
        headers=bearer(owner_token),
        json={"theme_id": "noite-quadra"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json() == {"theme_id": "noite-quadra"}

    profile = api.get("/api/v1/me/profile", headers=bearer(owner_token))
    assert profile.status_code == 200, profile.text
    assert profile.json()["theme_id"] == "noite-quadra"

    public = api.get(f"/api/v1/users/{owner}", headers=bearer(viewer_token))
    assert public.json()["card"]["theme_id"] == "noite-quadra"

    cleared = api.put("/api/v1/me/theme", headers=bearer(owner_token), json={"theme_id": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json() == {"theme_id": None}
    assert (
        api.get(f"/api/v1/users/{owner}", headers=bearer(viewer_token)).json()["card"]["theme_id"]
        is None
    )

    assert client.get("/api/v1/users/" + str(owner)).status_code == 401
    assert api.put("/api/v1/me/theme", json={"theme_id": "noite-quadra"}).status_code == 401


def test_theme_rejects_invalid_shapes(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, add_player(db_session, "DONO INVALIDO"))

    for value in ("Noite-Quadra", "noite_quadra", " noite", "-noite", "a" * 41, ""):
        response = api.put(
            "/api/v1/me/theme",
            headers=bearer(token),
            json={"theme_id": value},
        )
        assert response.status_code == 422, (value, response.text)

    profile = api.get("/api/v1/me/profile", headers=bearer(token))
    assert profile.json()["theme_id"] is None


def test_public_card_never_exposes_pii_or_mmr(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, add_player(db_session, "VISITANTE PII"))
    target = add_player(db_session, "CARD PII", email="segredo@example.com")

    response = api.get(f"/api/v1/users/{target}", headers=bearer(token))

    assert response.status_code == 200, response.text
    body = response.json()
    assert "segredo@example.com" not in response.text
    for forbidden_key in (
        "email",
        "phone",
        "cpf",
        "lat",
        "lng",
        "coordinates",
        "mmr",
        "rating",
        "rating_deviation",
    ):
        assert forbidden_key not in body["card"]
    assert api.get(f"/api/v1/users/{uuid.uuid4()}", headers=bearer(token)).status_code == 404


def test_public_card_uses_a_bounded_number_of_queries(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, add_player(db_session, "VISITANTE N+1"))
    target = add_player(db_session, "CARD N+1")
    founder = Badge(code="fundador", name="Fundadora", kind="founder")
    db_session.add(founder)
    db_session.flush()
    db_session.add(PlayerBadge(user_id=target, badge_id=founder.id, equipped_slot=1))
    db_session.flush()

    statements: list[str] = []

    def before_cursor_execute(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    bind = db_session.get_bind()
    event.listen(bind, "before_cursor_execute", before_cursor_execute)
    try:
        response = api.get(f"/api/v1/users/{target}", headers=bearer(token))
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor_execute)

    assert response.status_code == 200, response.text
    selects = [item for item in statements if item.lstrip().upper().startswith("SELECT")]
    assert len(selects) <= 16, "\n---\n".join(selects)
