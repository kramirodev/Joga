"""Testes da API de fila de matchmaking."""

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_TOKEN_HASH_SECRET
from app.infrastructure.database.dependency import get_session
from app.modules.identity.models import User
from app.modules.identity.sessions import SessionService
from app.modules.matchmaking.models import Lobby, QueueEntry
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


def test_put_replaces_selection_atomically(api: TestClient, db_session: Session) -> None:
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
    # A entrada legada foi cancelada e o campo de compatibilidade aponta para
    # uma das novas entradas ativas.
    assert first.json()["id"] not in {item["id"] for item in body["entries"]}
    assert body["entry"] is not None
    assert body["entry"]["status"] == "waiting"
    assert _queued_statuses(db_session, user_id) == [
        "cancelled",
        "waiting",
        "waiting",
        "waiting",
        "waiting",
    ]

    # Repetir a mesma seleção substitui de novo, sem conflito e sem duplicar.
    again = api.put(
        "/api/v1/matchmaking/queue",
        headers=bearer(token),
        json={"formats": [str(futebol.id)], "modes": ["casual"]},
    )
    assert again.status_code == 200
    assert len(again.json()["entries"]) == 1
    statuses = _queued_statuses(db_session, user_id)
    assert statuses.count("waiting") == 1
    assert statuses.count("cancelled") == 5


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
