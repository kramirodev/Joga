"""Testes da API de fila de matchmaking."""

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_TOKEN_HASH_SECRET
from app.infrastructure.database.dependency import get_session
from app.modules.identity.models import User
from app.modules.identity.sessions import SessionService
from app.modules.matchmaking.models import Lobby, QueueEntry
from app.modules.matchmaking.service import MatchmakingService
from app.modules.profile.models import (
    Availability,
    Sport,
    SportFormat,
    UserRegion,
    UserSportProfile,
)


@pytest.fixture
def api(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def make_user_with_tokens(session: Session) -> tuple[UUID, str]:
    user = User(status="active")
    session.add(user)
    session.flush()
    tokens = SessionService(
        session,
        DEFAULT_TOKEN_HASH_SECRET,
        access_ttl_seconds=600,
        refresh_absolute_ttl_days=30,
        refresh_idle_ttl_days=7,
    ).issue(user.id)
    session.commit()
    return user.id, tokens.access_token


def seed_format(
    session: Session,
    *,
    sport_slug: str = "futebol",
    format_slug: str = "futebol-5x5",
    name: str = "Futebol 5x5",
    team_size: int = 5,
) -> SportFormat:
    sport = Sport(slug=sport_slug, name=sport_slug.title())
    session.add(sport)
    session.flush()
    sport_format = SportFormat(
        sport_id=sport.id,
        slug=format_slug,
        name=name,
        team_size=team_size,
        total_participants=team_size * 2,
        play_minutes=50,
        break_minutes=10,
        duration_minutes=60,
        version=1,
    )
    session.add(sport_format)
    session.flush()
    return sport_format


def give_region(session: Session, user_id: UUID) -> None:
    session.add(
        UserRegion(
            user_id=user_id,
            source="cep",
            cep="01001000",
            city="São Paulo",
            state="SP",
            radius_km=10,
            center_lat=-23.55,
            center_lng=-46.63,
        )
    )
    session.flush()


def give_sport_profile(
    session: Session,
    user_id: UUID,
    format_id: UUID,
    *,
    level: str = "intermediate",
    court: str = "ANY",
) -> None:
    session.add(
        UserSportProfile(
            user_id=user_id,
            format_id=format_id,
            level=level,
            court_preference=court,
        )
    )
    session.flush()


def get_sport_profile(
    session: Session,
    user_id: UUID,
    format_id: UUID,
) -> UserSportProfile | None:
    return session.scalar(
        select(UserSportProfile).where(
            UserSportProfile.user_id == user_id,
            UserSportProfile.format_id == format_id,
        )
    )


def give_availability(session: Session, user_id: UUID) -> None:
    session.add(
        Availability(
            user_id=user_id,
            weekday=2,
            start_time=time(18, 0),
            end_time=time(22, 0),
            timezone="America/Sao_Paulo",
        )
    )
    session.flush()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_lobby(
    session: Session,
    sport_format: SportFormat,
    *,
    start: datetime,
    status: str = "scheduled",
) -> Lobby:
    lobby = Lobby(
        format_id=sport_format.id,
        format_version=sport_format.version,
        origin="matchmaking",
        mode="casual",
        status=status,
        court_preference="ANY",
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(minutes=sport_format.duration_minutes),
        duration_minutes=sport_format.duration_minutes,
        center_lat=-23.55,
        center_lng=-46.63,
        radius_km=10,
        algorithm_version="level_v1",
    )
    session.add(lobby)
    session.flush()
    return lobby


def mark_matched(
    session: Session,
    entry_id: str | UUID,
    *,
    matched_at: datetime,
    created_at: datetime | None = None,
    lobby: Lobby | None = None,
    expires_at: datetime | None = None,
) -> None:
    entry = session.get(QueueEntry, UUID(str(entry_id)))
    assert entry is not None
    entry.status = "matched"
    entry.matched_at = matched_at
    entry.lobby_id = lobby.id if lobby is not None else None
    if created_at is not None:
        entry.created_at = created_at
    if expires_at is not None:
        entry.expires_at = expires_at
    session.flush()


def test_queue_requires_authentication(api: TestClient) -> None:
    assert api.get("/api/v1/matchmaking/queue").status_code == 401
    assert api.post("/api/v1/matchmaking/queue", json={}).status_code == 401


def test_enqueue_requires_region(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_sport_profile(db_session, user_id, sport_format.id)

    response = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "region_required"}}


def test_enqueue_requires_sport_profile(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)

    response = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "sport_profile_required"}}


def test_enqueue_accepts_ranked(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    response = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id), "mode": "ranked"},
    )

    assert response.status_code == 201
    assert response.json()["mode"] == "ranked"


def test_enqueue_rejects_unknown_format(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    give_region(db_session, user_id)

    response = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_format"}}


def test_enqueue_and_leave(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, court="PUBLIC_ONLY")

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "waiting"
    assert body["mode"] == "casual"
    assert body["court_preference"] == "PUBLIC_ONLY"
    assert body["level"] == "intermediate"
    assert body["radius_km"] == 10
    assert body["lobby"] is None
    assert "center_lat" not in body and "center_lng" not in body

    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token))
    assert state.status_code == 200
    assert state.json()["entry"]["id"] == body["id"]

    left = api.delete("/api/v1/matchmaking/queue", headers=bearer(token))
    assert left.status_code == 204

    empty = api.get("/api/v1/matchmaking/queue", headers=bearer(token))
    assert empty.json() == {"entry": None, "entries": [], "matched": []}

    again = api.delete("/api/v1/matchmaking/queue", headers=bearer(token))
    assert again.status_code == 404
    assert again.json() == {"detail": {"code": "not_queued"}}


def test_enqueue_rejects_duplicate(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)
    payload = {"format_id": str(sport_format.id)}

    first = api.post("/api/v1/matchmaking/queue", headers=bearer(token), json=payload)
    second = api.post("/api/v1/matchmaking/queue", headers=bearer(token), json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": {"code": "already_queued"}}


def test_enqueue_overrides_court_preference(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, court="ANY")

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id), "court_preference": "PRIVATE_ONLY"},
    )

    assert created.status_code == 201
    assert created.json()["court_preference"] == "PRIVATE_ONLY"
    db_session.expire_all()
    profile = get_sport_profile(db_session, user_id, sport_format.id)
    assert profile is not None
    assert profile.court_preference == "PRIVATE_ONLY"


def test_enqueue_accepts_without_availability(api: TestClient, db_session: Session) -> None:
    """A ausência de agenda não impede entrar na fila; só impede a formação."""
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )

    assert created.status_code == 201


def _queued_statuses(session: Session, user_id: UUID) -> list[str]:
    session.expire_all()
    return list(
        session.scalars(
            select(QueueEntry.status)
            .where(QueueEntry.user_id == user_id)
            .order_by(QueueEntry.status)
        )
    )


def test_put_replaces_selection_preserving_common_entries(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol = seed_format(db_session)
    volei = seed_format(
        db_session,
        sport_slug="volei",
        format_slug="volei-2x2",
        name="Vôlei 2x2",
        team_size=2,
    )
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)

    first = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(futebol.id)},
    )
    assert first.status_code == 201

    replaced = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            # Repetições são deduplicadas antes de montar o produto cartesiano.
            "formats": [str(futebol.id), str(volei.id), str(futebol.id)],
            "modes": ["casual", "ranked", "casual"],
        },
    )

    assert replaced.status_code == 200
    body = replaced.json()
    assert {(item["format_id"], item["mode"]) for item in body["entries"]} == {
        (str(futebol.id), "casual"),
        (str(futebol.id), "ranked"),
        (str(volei.id), "casual"),
        (str(volei.id), "ranked"),
    }
    assert len(body["entries"]) == 4
    # A entrada que já existia para ``futebol/casual`` permaneceu: mesmo id e
    # sem cancelamento.
    assert first.json()["id"] in {item["id"] for item in body["entries"]}
    assert body["entry"] is not None
    assert body["entry"]["status"] == "waiting"
    assert _queued_statuses(db_session, user_id) == ["waiting"] * 4

    # Reduzir a seleção cancela apenas o que saiu; ``futebol/casual`` fica.
    again = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(futebol.id)], "modes": ["casual"]},
    )
    assert again.status_code == 200
    assert len(again.json()["entries"]) == 1
    assert again.json()["entries"][0]["id"] == first.json()["id"]
    statuses = _queued_statuses(db_session, user_id)
    assert statuses.count("waiting") == 1
    assert statuses.count("cancelled") == 3


def _pin_created_at(session: Session, entry_id: str, when: datetime) -> None:
    """Congela ``created_at`` para provar que o ``PUT`` não reinicia o relógio."""
    entry = session.get(QueueEntry, UUID(entry_id))
    assert entry is not None
    entry.created_at = when
    session.commit()


def _entries_by_format(body: dict[str, object]) -> dict[str, dict[str, object]]:
    entries = body["entries"]
    assert isinstance(entries, list)
    return {str(item["format_id"]): item for item in entries}


def test_put_adding_format_preserves_existing_entry_and_created_at(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol = seed_format(db_session)
    volei = seed_format(
        db_session,
        sport_slug="volei",
        format_slug="volei-2x2",
        name="Vôlei 2x2",
        team_size=2,
    )
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)

    created = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(futebol.id)]},
    )
    assert created.status_code == 200
    original = _entries_by_format(created.json())[str(futebol.id)]
    # Data antiga artificial: se o PUT recriasse a linha, o valor seria "agora".
    _pin_created_at(db_session, str(original["id"]), datetime(2026, 1, 5, 12, 0, tzinfo=UTC))
    before = _entries_by_format(api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json())[
        str(futebol.id)
    ]
    assert str(before["created_at"]).startswith("2026-01-05T12:00:00")

    replaced = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(futebol.id), str(volei.id)], "modes": ["casual"]},
    )
    assert replaced.status_code == 200
    after = _entries_by_format(replaced.json())

    assert after[str(futebol.id)]["id"] == original["id"]
    assert after[str(futebol.id)]["created_at"] == before["created_at"]
    assert after[str(volei.id)]["status"] == "waiting"
    assert after[str(volei.id)]["id"] != original["id"]


def test_put_removing_format_cancels_only_removed_entry(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol = seed_format(db_session)
    volei = seed_format(
        db_session,
        sport_slug="volei",
        format_slug="volei-2x2",
        name="Vôlei 2x2",
        team_size=2,
    )
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)

    created = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(futebol.id), str(volei.id)], "modes": ["casual"]},
    )
    assert created.status_code == 200
    original = _entries_by_format(created.json())
    _pin_created_at(
        db_session, str(original[str(futebol.id)]["id"]), datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
    )
    before = _entries_by_format(api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json())

    replaced = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(futebol.id)], "modes": ["casual"]},
    )
    assert replaced.status_code == 200
    body = replaced.json()

    assert [item["format_id"] for item in body["entries"]] == [str(futebol.id)]
    assert body["entries"][0]["id"] == original[str(futebol.id)]["id"]
    assert body["entries"][0]["created_at"] == before[str(futebol.id)]["created_at"]
    db_session.expire_all()
    removed = db_session.get(QueueEntry, UUID(str(original[str(volei.id)]["id"])))
    kept = db_session.get(QueueEntry, UUID(str(original[str(futebol.id)]["id"])))
    assert removed is not None and removed.status == "cancelled"
    assert kept is not None and kept.status == "waiting"


def test_put_switching_format_cancels_old_and_creates_new(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol = seed_format(db_session)
    volei = seed_format(
        db_session,
        sport_slug="volei",
        format_slug="volei-2x2",
        name="Vôlei 2x2",
        team_size=2,
    )
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)

    first = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(futebol.id)], "modes": ["casual"]},
    )
    assert first.status_code == 200
    futebol_id = first.json()["entries"][0]["id"]

    switched = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(volei.id)], "modes": ["casual"]},
    )
    assert switched.status_code == 200
    entries = switched.json()["entries"]
    assert [item["format_id"] for item in entries] == [str(volei.id)]
    assert entries[0]["id"] != futebol_id
    db_session.expire_all()
    old = db_session.get(QueueEntry, UUID(futebol_id))
    assert old is not None and old.status == "cancelled"


def test_put_same_selection_does_not_recreate_entries(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol = seed_format(db_session)
    volei = seed_format(
        db_session,
        sport_slug="volei",
        format_slug="volei-2x2",
        name="Vôlei 2x2",
        team_size=2,
    )
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)
    selection = {"formats": [str(futebol.id), str(volei.id)], "modes": ["casual", "ranked"]}

    first = api.put("/api/v1/matchmaking/queue", headers=bearer(token), json=selection)
    assert first.status_code == 200

    second = api.put("/api/v1/matchmaking/queue", headers=bearer(token), json=selection)
    assert second.status_code == 200

    first_entries = first.json()["entries"]
    second_entries = second.json()["entries"]
    assert {(item["id"], item["created_at"]) for item in first_entries} == {
        (item["id"], item["created_at"]) for item in second_entries
    }
    # Reenviar a mesma seleção não cria nem cancela nada.
    db_session.expire_all()
    rows = list(db_session.scalars(select(QueueEntry).where(QueueEntry.user_id == user_id)))
    assert len(rows) == 4
    assert {row.status for row in rows} == {"waiting"}


def test_put_invalid_format_keeps_previous_selection(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    previous = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(sport_format.id)], "modes": ["casual"]},
    )
    assert previous.status_code == 200

    failed = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(sport_format.id), str(uuid4())], "modes": ["casual"]},
    )

    assert failed.status_code == 400
    assert failed.json() == {"detail": {"code": "invalid_format"}}
    db_session.expire_all()
    rows = list(db_session.scalars(select(QueueEntry).where(QueueEntry.user_id == user_id)))
    assert [(str(row.id), row.status) for row in rows] == [
        (previous.json()["entries"][0]["id"], "waiting")
    ]


def test_put_does_not_touch_matched_entry(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol = seed_format(db_session)
    volei = seed_format(
        db_session,
        sport_slug="volei",
        format_slug="volei-2x2",
        name="Vôlei 2x2",
        team_size=2,
    )
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(futebol.id)},
    )
    assert created.status_code == 201
    matched_id = created.json()["id"]
    matched_at = datetime(2026, 11, 18, 20, 0, tzinfo=UTC)
    lobby = make_lobby(db_session, futebol, start=datetime(2026, 11, 22, 21, 0, tzinfo=UTC))
    mark_matched(db_session, matched_id, matched_at=matched_at, lobby=lobby)
    db_session.commit()
    db_session.expire_all()
    before = db_session.get(QueueEntry, UUID(matched_id))
    assert before is not None

    replaced = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(volei.id)], "modes": ["casual"]},
    )
    assert replaced.status_code == 200
    body = replaced.json()
    assert [item["format_id"] for item in body["entries"]] == [str(volei.id)]
    assert [item["id"] for item in body["matched"]] == [matched_id]

    db_session.expire_all()
    entry = db_session.get(QueueEntry, UUID(matched_id))
    assert entry is not None
    assert entry.status == "matched"
    assert entry.lobby_id == lobby.id
    assert entry.matched_at == before.matched_at


def test_put_updates_court_preference_in_place(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, court="ANY")

    created = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(sport_format.id)], "modes": ["casual"]},
    )
    assert created.status_code == 200
    original = created.json()["entries"][0]
    _pin_created_at(db_session, original["id"], datetime(2026, 1, 5, 12, 0, tzinfo=UTC))
    before = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()["entries"][0]

    updated = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "formats": [str(sport_format.id)],
            "modes": ["casual"],
            "court_preference": "PUBLIC_ONLY",
        },
    )
    assert updated.status_code == 200
    entry = updated.json()["entries"][0]

    assert entry["id"] == original["id"]
    assert entry["created_at"] == before["created_at"]
    assert entry["court_preference"] == "PUBLIC_ONLY"
    db_session.expire_all()
    row = db_session.get(QueueEntry, UUID(original["id"]))
    assert row is not None
    assert row.court_preference == "PUBLIC_ONLY"
    assert row.status == "waiting"


def test_put_without_levels_uses_sport_profile_level(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, level="advanced")

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(sport_format.id)], "modes": ["casual", "ranked"]},
    )

    assert response.status_code == 200
    assert {item["level"] for item in response.json()["entries"]} == {"advanced"}


def test_put_applies_level_per_entry(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, level="intermediate")

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "formats": [str(sport_format.id)],
            "modes": ["casual", "ranked"],
            # ``level`` só se aplica a casual; ranqueada fica com o nível do perfil.
            "levels": [
                {"format_id": str(sport_format.id), "mode": "casual", "level": "beginner"},
            ],
        },
    )

    assert response.status_code == 200
    levels = {item["mode"]: item["level"] for item in response.json()["entries"]}
    # O nível casual explícito também vira a preferência do perfil (ADR 0064);
    # a entrada ranqueada do mesmo formato registra o perfil já atualizado.
    assert levels == {"casual": "beginner", "ranked": "beginner"}


def test_put_level_override_outside_selection_is_atomic(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol = seed_format(db_session)
    volei = seed_format(
        db_session,
        sport_slug="volei",
        format_slug="volei-2x2",
        name="Vôlei 2x2",
        team_size=2,
    )
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id, level="intermediate")
    give_sport_profile(db_session, user_id, volei.id)

    previous = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(futebol.id)], "modes": ["casual"]},
    )
    assert previous.status_code == 200
    original = previous.json()["entries"][0]

    failed = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "formats": [str(futebol.id), str(volei.id)],
            "modes": ["casual"],
            "levels": [
                # Override válido que não pode ser aplicado por causa do inválido.
                {"format_id": str(futebol.id), "mode": "casual", "level": "advanced"},
                {"format_id": str(uuid4()), "mode": "casual", "level": "beginner"},
            ],
        },
    )

    assert failed.status_code == 422
    assert failed.json() == {"detail": {"code": "invalid_level_override"}}
    db_session.expire_all()
    rows = list(db_session.scalars(select(QueueEntry).where(QueueEntry.user_id == user_id)))
    assert [(str(row.id), row.status, row.level) for row in rows] == [
        (original["id"], "waiting", "intermediate")
    ]


def test_put_invalid_level_is_rejected(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "formats": [str(sport_format.id)],
            "modes": ["casual"],
            "levels": [{"format_id": str(sport_format.id), "mode": "casual", "level": "expert"}],
        },
    )

    assert response.status_code == 422
    assert db_session.scalar(select(QueueEntry).where(QueueEntry.user_id == user_id)) is None


def test_put_duplicate_level_override_is_rejected(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "formats": [str(sport_format.id)],
            "modes": ["casual"],
            "levels": [
                {"format_id": str(sport_format.id), "mode": "casual", "level": "beginner"},
                {"format_id": str(sport_format.id), "mode": "casual", "level": "advanced"},
            ],
        },
    )

    assert response.status_code == 422
    assert db_session.scalar(select(QueueEntry).where(QueueEntry.user_id == user_id)) is None


def test_put_preserved_entry_updates_level_without_resetting_created_at(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, level="advanced")

    created = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(sport_format.id)], "modes": ["casual"]},
    )
    assert created.status_code == 200
    original = created.json()["entries"][0]
    _pin_created_at(db_session, original["id"], datetime(2026, 1, 5, 12, 0, tzinfo=UTC))
    before = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()["entries"][0]

    updated = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "formats": [str(sport_format.id)],
            "modes": ["casual"],
            "levels": [{"format_id": str(sport_format.id), "mode": "casual", "level": "beginner"}],
        },
    )
    assert updated.status_code == 200
    entry = updated.json()["entries"][0]

    assert entry["id"] == original["id"]
    assert entry["created_at"] == before["created_at"]
    assert entry["level"] == "beginner"
    db_session.expire_all()
    row = db_session.get(QueueEntry, UUID(original["id"]))
    assert row is not None
    assert row.level == "beginner"
    assert row.status == "waiting"


def test_put_empty_selection_with_level_override_is_rejected(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)
    previous = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(sport_format.id)], "modes": ["casual"]},
    )
    assert previous.status_code == 200

    failed = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "formats": [],
            "levels": [{"format_id": str(sport_format.id), "mode": "casual", "level": "beginner"}],
        },
    )

    assert failed.status_code == 422
    assert failed.json() == {"detail": {"code": "invalid_level_override"}}
    db_session.expire_all()
    rows = list(db_session.scalars(select(QueueEntry).where(QueueEntry.user_id == user_id)))
    assert [(str(row.id), row.status) for row in rows] == [
        (previous.json()["entries"][0]["id"], "waiting")
    ]


def test_put_preserved_entry_without_override_uses_updated_profile_level(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, level="advanced")

    created = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "formats": [str(sport_format.id)],
            "modes": ["casual"],
            "levels": [{"format_id": str(sport_format.id), "mode": "casual", "level": "beginner"}],
        },
    )
    assert created.status_code == 200
    original = created.json()["entries"][0]
    assert original["level"] == "beginner"

    # A escolha anterior virou a preferência do perfil (ADR 0064). Sem
    # ``levels``, a entrada preservada e o perfil usam esse nível atualizado.
    reset = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(sport_format.id)], "modes": ["casual"]},
    )

    assert reset.status_code == 200
    entry = reset.json()["entries"][0]
    assert entry["id"] == original["id"]
    assert entry["created_at"] == original["created_at"]
    assert entry["level"] == "beginner"
    db_session.expire_all()
    profile = db_session.scalar(
        select(UserSportProfile).where(
            UserSportProfile.user_id == user_id,
            UserSportProfile.format_id == sport_format.id,
        )
    )
    assert profile is not None and profile.level == "beginner"


def test_put_empty_selection_cancels_everything(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(sport_format.id)], "modes": ["casual", "ranked"]},
    )

    cleared = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": []},
    )

    assert cleared.status_code == 200
    assert cleared.json() == {"entry": None, "entries": [], "matched": []}
    assert _queued_statuses(db_session, user_id) == ["cancelled", "cancelled"]


def test_put_validation_failure_keeps_previous_selection(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol = seed_format(db_session)
    volei = seed_format(
        db_session,
        sport_slug="volei",
        format_slug="volei-2x2",
        name="Vôlei 2x2",
        team_size=2,
    )
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)  # sem perfil de vôlei

    previous = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(futebol.id)},
    )
    assert previous.status_code == 201

    failed = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(futebol.id), str(volei.id)], "modes": ["casual"]},
    )

    assert failed.status_code == 409
    assert failed.json() == {"detail": {"code": "sport_profile_required"}}
    assert _queued_statuses(db_session, user_id) == ["waiting"]
    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()
    assert [item["id"] for item in state["entries"]] == [previous.json()["id"]]


def test_put_requires_region_when_creating_entries(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_sport_profile(db_session, user_id, sport_format.id)

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(sport_format.id)]},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "region_required"}}


def test_queue_routes_are_scoped_to_the_owner(api: TestClient, db_session: Session) -> None:
    owner_id, owner_token = make_user_with_tokens(db_session)
    other_id, other_token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    for user_id in (owner_id, other_id):
        give_region(db_session, user_id)
        give_sport_profile(db_session, user_id, sport_format.id)

    other_entry = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(other_token),
        json={"format_id": str(sport_format.id)},
    )
    assert other_entry.status_code == 201

    owner_state = api.get("/api/v1/matchmaking/queue", headers=bearer(owner_token))
    assert owner_state.status_code == 200
    assert owner_state.json() == {"entry": None, "entries": [], "matched": []}

    replaced = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(owner_token),
        json={"formats": [str(sport_format.id)]},
    )
    assert replaced.status_code == 200
    assert {item["format_id"] for item in replaced.json()["entries"]} == {str(sport_format.id)}

    assert api.delete("/api/v1/matchmaking/queue", headers=bearer(owner_token)).status_code == 204
    other_state = api.get("/api/v1/matchmaking/queue", headers=bearer(other_token)).json()
    assert [item["id"] for item in other_state["entries"]] == [other_entry.json()["id"]]
    assert api.delete("/api/v1/matchmaking/queue", headers=bearer(owner_token)).status_code == 404
    assert (
        api.get("/api/v1/matchmaking/queue", headers=bearer(other_token)).json()["entry"]["id"]
        == (other_entry.json()["id"])
    )


def test_queue_state_without_entries_is_empty(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    give_region(db_session, user_id)

    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token))

    assert state.status_code == 200
    assert state.json() == {"entry": None, "entries": [], "matched": []}


def test_queue_state_with_only_waiting_has_empty_matched(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )
    assert created.status_code == 201

    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()

    assert [item["id"] for item in state["entries"]] == [created.json()["id"]]
    assert state["matched"] == []
    assert state["entry"]["id"] == created.json()["id"]


def test_queue_state_matched_appears_in_matched_and_entry(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )
    assert created.status_code == 201
    entry_id = created.json()["id"]
    matched_at = datetime(2026, 11, 18, 20, 0, tzinfo=UTC)
    lobby = make_lobby(db_session, sport_format, start=datetime(2026, 11, 22, 21, 0, tzinfo=UTC))
    mark_matched(
        db_session,
        entry_id,
        matched_at=matched_at,
        created_at=matched_at - timedelta(hours=1),
        lobby=lobby,
    )
    db_session.commit()

    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()

    assert [item["id"] for item in state["matched"]] == [entry_id]
    assert state["matched"][0]["status"] == "matched"
    assert state["matched"][0]["lobby"]["id"] == str(lobby.id)
    assert state["entries"] == []
    # Compatibilidade: ``entry`` continua trazendo a entrada pareada.
    assert state["entry"]["id"] == entry_id
    assert state["entry"]["status"] == "matched"


def test_queue_state_keeps_matched_when_new_waiting_entry_is_latest(
    api: TestClient, db_session: Session
) -> None:
    """Defeito original: voltar para a fila não pode esconder a partida encontrada."""
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    old = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )
    assert old.status_code == 201
    old_id = old.json()["id"]
    matched_at = datetime(2026, 11, 1, 15, 0, tzinfo=UTC)
    lobby = make_lobby(db_session, sport_format, start=datetime(2026, 11, 5, 21, 0, tzinfo=UTC))
    mark_matched(
        db_session,
        old_id,
        matched_at=matched_at,
        created_at=matched_at - timedelta(days=1),
        lobby=lobby,
    )
    db_session.commit()

    replaced = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(sport_format.id)], "modes": ["casual"]},
    )
    assert replaced.status_code == 200
    new_id = replaced.json()["entries"][0]["id"]
    assert new_id != old_id
    assert [item["id"] for item in replaced.json()["matched"]] == [old_id]

    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()

    assert [item["id"] for item in state["entries"]] == [new_id]
    assert [item["id"] for item in state["matched"]] == [old_id]
    # O campo legado continua sendo a waiting mais recente, não a matched.
    assert state["entry"]["id"] == new_id
    assert state["entry"]["status"] == "waiting"


def test_queue_state_lists_all_matched_newest_match_first(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol = seed_format(db_session)
    volei = seed_format(
        db_session,
        sport_slug="volei",
        format_slug="volei-2x2",
        name="Vôlei 2x2",
        team_size=2,
    )
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)

    created = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(futebol.id), str(volei.id)], "modes": ["casual"]},
    )
    assert created.status_code == 200
    by_format = {item["format_id"]: item["id"] for item in created.json()["entries"]}
    futebol_id = by_format[str(futebol.id)]
    volei_id = by_format[str(volei.id)]
    earlier = datetime(2026, 11, 10, 18, 0, tzinfo=UTC)
    later = datetime(2026, 11, 12, 18, 0, tzinfo=UTC)
    # Futebol foi criado antes, mas pareado depois: a ordem segue ``matched_at``.
    mark_matched(
        db_session,
        futebol_id,
        matched_at=later,
        created_at=earlier - timedelta(hours=1),
        lobby=make_lobby(db_session, futebol, start=datetime(2026, 11, 22, 21, 0, tzinfo=UTC)),
    )
    mark_matched(
        db_session,
        volei_id,
        matched_at=earlier,
        created_at=earlier,
        lobby=make_lobby(db_session, volei, start=datetime(2026, 11, 23, 21, 0, tzinfo=UTC)),
    )
    db_session.commit()

    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()

    assert [item["id"] for item in state["matched"]] == [futebol_id, volei_id]
    assert state["entries"] == []


def test_queue_state_includes_matched_with_past_expires_at(
    api: TestClient, db_session: Session
) -> None:
    """``expires_at`` é TTL da fila waiting; não invalida uma partida já encontrada."""
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )
    assert created.status_code == 201
    entry_id = created.json()["id"]
    now = datetime.now(UTC)
    mark_matched(
        db_session,
        entry_id,
        matched_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
        lobby=make_lobby(
            db_session,
            sport_format,
            start=now + timedelta(days=1),
        ),
    )
    db_session.commit()

    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()

    assert [item["id"] for item in state["matched"]] == [entry_id]


def test_queue_state_hides_matched_with_cancelled_lobby(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )
    assert created.status_code == 201
    mark_matched(
        db_session,
        created.json()["id"],
        matched_at=datetime(2026, 11, 18, 20, 0, tzinfo=UTC),
        lobby=make_lobby(
            db_session,
            sport_format,
            start=datetime(2026, 11, 22, 21, 0, tzinfo=UTC),
            status="cancelled",
        ),
    )
    db_session.commit()

    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()

    assert state["matched"] == []


def test_queue_state_hides_matched_with_completed_lobby(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )
    assert created.status_code == 201
    mark_matched(
        db_session,
        created.json()["id"],
        matched_at=datetime(2026, 11, 18, 20, 0, tzinfo=UTC),
        lobby=make_lobby(
            db_session,
            sport_format,
            start=datetime(2026, 11, 22, 21, 0, tzinfo=UTC),
            status="completed",
        ),
    )
    db_session.commit()

    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()

    assert state["matched"] == []


def test_queue_state_hides_matched_without_lobby(api: TestClient, db_session: Session) -> None:
    """Entrada ``matched`` sem lobby é inconsistência: não é partida encontrável."""
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )
    assert created.status_code == 201
    mark_matched(
        db_session,
        created.json()["id"],
        matched_at=datetime(2026, 11, 18, 20, 0, tzinfo=UTC),
    )
    db_session.commit()

    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()

    assert state["matched"] == []


def test_queue_state_lists_only_scheduled_among_matched(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol = seed_format(db_session)
    volei = seed_format(
        db_session,
        sport_slug="volei",
        format_slug="volei-2x2",
        name="Vôlei 2x2",
        team_size=2,
    )
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)

    created = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(futebol.id), str(volei.id)], "modes": ["casual"]},
    )
    assert created.status_code == 200
    by_format = {item["format_id"]: item["id"] for item in created.json()["entries"]}
    scheduled_id = by_format[str(futebol.id)]
    completed_id = by_format[str(volei.id)]
    mark_matched(
        db_session,
        scheduled_id,
        matched_at=datetime(2026, 11, 10, 18, 0, tzinfo=UTC),
        lobby=make_lobby(
            db_session,
            futebol,
            start=datetime(2026, 11, 22, 21, 0, tzinfo=UTC),
        ),
    )
    mark_matched(
        db_session,
        completed_id,
        matched_at=datetime(2026, 11, 12, 18, 0, tzinfo=UTC),
        lobby=make_lobby(
            db_session,
            volei,
            start=datetime(2026, 11, 23, 21, 0, tzinfo=UTC),
            status="completed",
        ),
    )
    db_session.commit()

    state = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()

    # A partida concluída é a mais recente, mas só a agendada deve aparecer.
    assert [item["id"] for item in state["matched"]] == [scheduled_id]


def test_put_returns_same_queue_state_shape_as_get(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    created = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id)},
    )
    assert created.status_code == 201
    entry_id = created.json()["id"]
    matched_at = datetime(2026, 11, 1, 15, 0, tzinfo=UTC)
    mark_matched(
        db_session,
        entry_id,
        matched_at=matched_at,
        created_at=matched_at - timedelta(days=1),
        lobby=make_lobby(db_session, sport_format, start=datetime(2026, 11, 5, 21, 0, tzinfo=UTC)),
    )
    db_session.commit()

    replaced = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(sport_format.id)], "modes": ["casual"]},
    )
    assert replaced.status_code == 200
    put_body = replaced.json()
    assert set(put_body) == {"entry", "entries", "matched"}
    assert [item["id"] for item in put_body["matched"]] == [entry_id]
    assert put_body == api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()


def _seed_two_formats(session: Session) -> tuple[SportFormat, SportFormat]:
    futebol = seed_format(session)
    volei = seed_format(
        session,
        sport_slug="volei",
        format_slug="volei-2x2",
        name="Vôlei 2x2",
        team_size=2,
    )
    return futebol, volei


def _pairs(body: dict[str, object]) -> set[tuple[str, str]]:
    entries = body["entries"]
    assert isinstance(entries, list)
    return {(str(item["format_id"]), str(item["mode"])) for item in entries}


def test_put_selections_creates_only_requested_pairs(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol, volei = _seed_two_formats(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(futebol.id), "mode": "ranked"},
                {"format_id": str(volei.id), "mode": "casual"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert _pairs(body) == {
        (str(futebol.id), "ranked"),
        (str(volei.id), "casual"),
    }
    assert len(body["entries"]) == 2
    assert _queued_statuses(db_session, user_id) == ["waiting", "waiting"]


def test_put_selections_applies_level_per_pair(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol, volei = _seed_two_formats(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id, level="intermediate")
    give_sport_profile(db_session, user_id, volei.id, level="intermediate")

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(futebol.id), "mode": "casual", "level": "advanced"},
                {"format_id": str(volei.id), "mode": "casual", "level": "beginner"},
            ],
        },
    )

    assert response.status_code == 200
    levels = {
        (item["format_id"], item["mode"]): item["level"] for item in response.json()["entries"]
    }
    assert levels == {
        (str(futebol.id), "casual"): "advanced",
        (str(volei.id), "casual"): "beginner",
    }


def test_put_selections_without_level_uses_profile_level(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, level="advanced")

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"selections": [{"format_id": str(sport_format.id), "mode": "casual"}]},
    )

    assert response.status_code == 200
    assert [item["level"] for item in response.json()["entries"]] == ["advanced"]


def test_put_selections_rejects_level_on_ranked(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, level="intermediate")

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(sport_format.id), "mode": "ranked", "level": "advanced"},
            ],
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "level_not_applicable_for_ranked"}}
    assert db_session.scalar(select(QueueEntry).where(QueueEntry.user_id == user_id)) is None


def test_put_selections_accepts_casual_level_and_ranked_without_level(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol, volei = _seed_two_formats(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id, level="intermediate")
    give_sport_profile(db_session, user_id, volei.id, level="intermediate")

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                # Casual aceita nível explícito.
                {"format_id": str(volei.id), "mode": "casual", "level": "beginner"},
                # Ranqueada aceita o par, mas sem nível.
                {"format_id": str(futebol.id), "mode": "ranked"},
            ],
        },
    )

    assert response.status_code == 200
    by_pair = {(item["format_id"], item["mode"]): item for item in response.json()["entries"]}
    assert by_pair[(str(volei.id), "casual")]["level"] == "beginner"
    # Sem override, ranqueada continua usando o nível do perfil.
    assert by_pair[(str(futebol.id), "ranked")]["level"] == "intermediate"


def test_put_legacy_rejects_level_on_ranked(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, level="intermediate")

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "formats": [str(sport_format.id)],
            "modes": ["ranked"],
            "levels": [
                {"format_id": str(sport_format.id), "mode": "ranked", "level": "advanced"},
            ],
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "level_not_applicable_for_ranked"}}
    assert db_session.scalar(select(QueueEntry).where(QueueEntry.user_id == user_id)) is None


def test_put_legacy_accepts_level_on_casual(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, level="intermediate")

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "formats": [str(sport_format.id)],
            "modes": ["casual"],
            "levels": [
                {"format_id": str(sport_format.id), "mode": "casual", "level": "advanced"},
            ],
        },
    )

    assert response.status_code == 200
    assert [item["level"] for item in response.json()["entries"]] == ["advanced"]


def test_put_selections_duplicate_pair_is_rejected(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(sport_format.id), "mode": "casual", "level": "beginner"},
                {"format_id": str(sport_format.id), "mode": "casual", "level": "advanced"},
            ],
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "duplicate_queue_selection"}}
    assert db_session.scalar(select(QueueEntry).where(QueueEntry.user_id == user_id)) is None


@pytest.mark.parametrize(
    "extra",
    [
        {"formats": []},
        {"modes": ["casual"]},
        {
            "levels": [
                {
                    "format_id": "00000000-0000-0000-0000-000000000001",
                    "mode": "casual",
                    "level": "beginner",
                }
            ]
        },
    ],
)
def test_put_selections_with_legacy_fields_is_ambiguous(
    api: TestClient, db_session: Session, extra: dict[str, object]
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [{"format_id": str(sport_format.id), "mode": "casual"}],
            **extra,
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "ambiguous_queue_selection"}}
    assert db_session.scalar(select(QueueEntry).where(QueueEntry.user_id == user_id)) is None


def test_put_empty_selections_cancels_everything(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol, volei = _seed_two_formats(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)

    created = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(futebol.id), "mode": "ranked"},
                {"format_id": str(volei.id), "mode": "casual"},
            ],
        },
    )
    assert created.status_code == 200

    cleared = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"selections": []},
    )

    assert cleared.status_code == 200
    assert cleared.json() == {"entry": None, "entries": [], "matched": []}
    assert _queued_statuses(db_session, user_id) == ["cancelled", "cancelled"]


def test_put_selections_adding_pair_preserves_created_at(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol, volei = _seed_two_formats(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)

    first = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"selections": [{"format_id": str(futebol.id), "mode": "ranked"}]},
    )
    assert first.status_code == 200
    original = first.json()["entries"][0]
    assert (original["format_id"], original["mode"]) == (str(futebol.id), "ranked")
    _pin_created_at(db_session, original["id"], datetime(2026, 1, 5, 12, 0, tzinfo=UTC))
    pinned = api.get("/api/v1/matchmaking/queue", headers=bearer(token)).json()["entries"][0]

    expanded = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(futebol.id), "mode": "ranked"},
                {"format_id": str(volei.id), "mode": "casual"},
            ],
        },
    )
    assert expanded.status_code == 200
    after = {(item["format_id"], item["mode"]): item for item in expanded.json()["entries"]}
    kept = after[(str(futebol.id), "ranked")]
    added = after[(str(volei.id), "casual")]
    assert kept["id"] == original["id"]
    assert kept["created_at"] == pinned["created_at"]
    assert str(kept["created_at"]).startswith("2026-01-05T12:00:00")
    assert added["id"] != original["id"]
    assert added["status"] == "waiting"


def test_put_selections_removing_pair_cancels_only_it(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol, volei = _seed_two_formats(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)

    created = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(futebol.id), "mode": "ranked"},
                {"format_id": str(volei.id), "mode": "casual"},
            ],
        },
    )
    assert created.status_code == 200
    original = {(item["format_id"], item["mode"]): item for item in created.json()["entries"]}
    futebol_entry = original[(str(futebol.id), "ranked")]
    volei_entry = original[(str(volei.id), "casual")]
    _pin_created_at(db_session, futebol_entry["id"], datetime(2026, 1, 5, 12, 0, tzinfo=UTC))

    reduced = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"selections": [{"format_id": str(volei.id), "mode": "casual"}]},
    )
    assert reduced.status_code == 200
    body = reduced.json()
    assert [item["id"] for item in body["entries"]] == [volei_entry["id"]]
    assert body["entries"][0]["created_at"] == volei_entry["created_at"]

    db_session.expire_all()
    removed = db_session.get(QueueEntry, UUID(futebol_entry["id"]))
    kept = db_session.get(QueueEntry, UUID(volei_entry["id"]))
    assert removed is not None and removed.status == "cancelled"
    assert kept is not None and kept.status == "waiting"


def test_put_selections_invalid_mode_is_rejected(api: TestClient, db_session: Session) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id)

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"selections": [{"format_id": str(sport_format.id), "mode": "competitive"}]},
    )

    assert response.status_code == 422
    assert db_session.scalar(select(QueueEntry).where(QueueEntry.user_id == user_id)) is None


def test_put_formats_and_modes_still_apply_cartesian_product(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol, volei = _seed_two_formats(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id)
    give_sport_profile(db_session, user_id, volei.id)

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(futebol.id), str(volei.id)], "modes": ["casual", "ranked"]},
    )

    assert response.status_code == 200
    assert _pairs(response.json()) == {
        (str(futebol.id), "casual"),
        (str(futebol.id), "ranked"),
        (str(volei.id), "casual"),
        (str(volei.id), "ranked"),
    }


def test_put_casual_level_without_profile_creates_sport_profile(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(sport_format.id), "mode": "casual", "level": "beginner"},
            ],
        },
    )

    assert response.status_code == 200
    assert [item["level"] for item in response.json()["entries"]] == ["beginner"]

    db_session.expire_all()
    profile = get_sport_profile(db_session, user_id, sport_format.id)
    assert profile is not None
    assert profile.level == "beginner"
    assert profile.court_preference == "ANY"

    visible = api.get("/api/v1/me/profile", headers=bearer(token))
    assert visible.status_code == 200
    sports = {item["format_id"]: item for item in visible.json()["sports"]}
    assert sports[str(sport_format.id)]["level"] == "beginner"
    assert sports[str(sport_format.id)]["court_preference"] == "ANY"


def test_put_creates_profile_only_for_selected_formats(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol, volei = _seed_two_formats(db_session)
    give_region(db_session, user_id)

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(futebol.id), "mode": "casual", "level": "advanced"},
            ],
        },
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert get_sport_profile(db_session, user_id, futebol.id) is not None
    assert get_sport_profile(db_session, user_id, volei.id) is None


def test_put_court_preference_updates_selected_profiles_only(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol, volei = _seed_two_formats(db_session)
    basquete = seed_format(
        db_session,
        sport_slug="basquete",
        format_slug="basquete-3x3",
        name="Basquete 3x3",
        team_size=3,
    )
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, futebol.id, level="advanced", court="ANY")
    give_sport_profile(db_session, user_id, volei.id, level="beginner", court="ANY")
    give_sport_profile(db_session, user_id, basquete.id, level="intermediate", court="ANY")

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(futebol.id), "mode": "casual"},
                {"format_id": str(volei.id), "mode": "ranked"},
            ],
            "court_preference": "PRIVATE_ONLY",
        },
    )

    assert response.status_code == 200
    assert {item["court_preference"] for item in response.json()["entries"]} == {"PRIVATE_ONLY"}
    db_session.expire_all()
    futebol_profile = get_sport_profile(db_session, user_id, futebol.id)
    volei_profile = get_sport_profile(db_session, user_id, volei.id)
    basquete_profile = get_sport_profile(db_session, user_id, basquete.id)
    assert futebol_profile is not None
    assert volei_profile is not None
    assert basquete_profile is not None
    assert futebol_profile.court_preference == "PRIVATE_ONLY"
    assert volei_profile.court_preference == "PRIVATE_ONLY"
    assert futebol_profile.level == "advanced"
    assert volei_profile.level == "beginner"
    # Formato fora da seleção não é tocado.
    assert basquete_profile.court_preference == "ANY"


def test_put_ranked_creates_default_profile_only_when_missing(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    futebol, volei = _seed_two_formats(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, volei.id, level="advanced")

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(futebol.id), "mode": "ranked"},
                {"format_id": str(volei.id), "mode": "ranked"},
            ],
        },
    )

    assert response.status_code == 200
    levels = {item["format_id"]: item["level"] for item in response.json()["entries"]}
    assert levels == {
        str(futebol.id): "intermediate",
        str(volei.id): "advanced",
    }
    db_session.expire_all()
    futebol_profile = get_sport_profile(db_session, user_id, futebol.id)
    volei_profile = get_sport_profile(db_session, user_id, volei.id)
    assert futebol_profile is not None
    assert futebol_profile.level == "intermediate"
    assert futebol_profile.court_preference == "ANY"
    assert volei_profile is not None
    assert volei_profile.level == "advanced"


def test_enqueue_ranked_without_profile_creates_default_profile(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)

    response = api.post(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"format_id": str(sport_format.id), "mode": "ranked"},
    )

    assert response.status_code == 201
    assert response.json()["level"] == "intermediate"
    db_session.expire_all()
    profile = get_sport_profile(db_session, user_id, sport_format.id)
    assert profile is not None
    assert profile.level == "intermediate"
    assert profile.court_preference == "ANY"


def test_put_replacing_casual_level_updates_sport_profile(
    api: TestClient, db_session: Session
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)
    give_sport_profile(db_session, user_id, sport_format.id, level="intermediate")

    first = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(sport_format.id), "mode": "casual", "level": "beginner"},
            ],
        },
    )
    assert first.status_code == 200
    db_session.expire_all()
    profile = get_sport_profile(db_session, user_id, sport_format.id)
    assert profile is not None and profile.level == "beginner"

    second = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(sport_format.id), "mode": "casual", "level": "advanced"},
            ],
        },
    )
    assert second.status_code == 200
    assert [item["level"] for item in second.json()["entries"]] == ["advanced"]
    db_session.expire_all()
    profile = get_sport_profile(db_session, user_id, sport_format.id)
    assert profile is not None and profile.level == "advanced"


def test_put_failure_after_profile_upsert_rolls_back_sport_profile(
    api: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id, token = make_user_with_tokens(db_session)
    sport_format = seed_format(db_session)
    give_region(db_session, user_id)

    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("falha simulada após o upsert do perfil")

    monkeypatch.setattr(MatchmakingService, "_build_entry", explode)

    response = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={
            "selections": [
                {"format_id": str(sport_format.id), "mode": "casual", "level": "beginner"},
            ],
        },
    )
    assert response.status_code == 500

    db_session.expire_all()
    assert get_sport_profile(db_session, user_id, sport_format.id) is None
    assert db_session.scalar(select(QueueEntry).where(QueueEntry.user_id == user_id)) is None
