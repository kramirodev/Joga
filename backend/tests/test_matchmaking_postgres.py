"""Testes de formação de matchmaking em PostgreSQL real (locks e concorrência)."""

import os
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.modules.identity.models import User
from app.modules.matchmaking.models import (
    Lobby,
    LobbyParticipant,
    MatchmakingRun,
    QueueEntry,
)
from app.modules.matchmaking.service import MatchmakingService
from app.modules.profile.models import (
    Availability,
    Sport,
    SportFormat,
    UserRegion,
    UserSportProfile,
)
from app.modules.ratings.models import RatingAccount

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "matchmaking_test"
NOW = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="JOGA_TEST_DATABASE_URL não definido; teste de matchmaking ignorado",
)


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    assert TEST_DATABASE_URL is not None
    admin_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
    admin_engine.dispose()

    database_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True).execution_options(
        schema_translate_map={None: SCHEMA}
    )
    Base.metadata.create_all(database_engine)
    yield database_engine

    Base.metadata.drop_all(database_engine)
    database_engine.dispose()
    admin_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    admin_engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def clean_tables(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


def seed_format(session: Session) -> SportFormat:
    sport = Sport(slug="futebol", name="Futebol")
    session.add(sport)
    session.flush()
    sport_format = SportFormat(
        sport_id=sport.id,
        slug="futebol-5x5",
        name="Futebol 5x5",
        team_size=5,
        total_participants=10,
        play_minutes=50,
        break_minutes=10,
        duration_minutes=60,
        version=1,
    )
    session.add(sport_format)
    session.flush()
    return sport_format


def add_player(
    session: Session,
    sport_format: SportFormat,
    *,
    court: str = "ANY",
    level: str = "intermediate",
    lat: float = -23.55,
    lng: float = -46.63,
    radius: int = 10,
    available: bool = True,
    window_start: time = time(18, 0),
    window_end: time = time(22, 0),
) -> User:
    user = User(status="active")
    session.add(user)
    session.flush()
    session.add(
        UserSportProfile(
            user_id=user.id,
            format_id=sport_format.id,
            level=level,
            court_preference=court,
        )
    )
    session.add(
        UserRegion(
            user_id=user.id,
            source="cep",
            cep="01001000",
            city="São Paulo",
            state="SP",
            radius_km=radius,
            center_lat=lat,
            center_lng=lng,
        )
    )
    if available:
        session.add(
            Availability(
                user_id=user.id,
                weekday=2,
                start_time=window_start,
                end_time=window_end,
                timezone="America/Sao_Paulo",
            )
        )
    session.flush()
    return user


def queue_players(
    session: Session,
    sport_format: SportFormat,
    count: int,
    **kwargs: object,
) -> list[QueueEntry]:
    service = MatchmakingService(session)
    entries = []
    for _ in range(count):
        user = add_player(session, sport_format, **kwargs)  # type: ignore[arg-type]
        entries.append(service.enqueue(user.id, sport_format.id, now=NOW))
    session.flush()
    return entries


def service(session: Session) -> MatchmakingService:
    return MatchmakingService(session)


def test_forms_one_lobby_with_balanced_teams(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        levels = ["advanced", "advanced", "intermediate", "intermediate", "intermediate"] * 2
        entries = []
        for level in levels:
            user = add_player(session, sport_format, level=level)
            entries.append(service(session).enqueue(user.id, sport_format.id, now=NOW))
        session.flush()

        result = service(session).run_once(NOW)
        session.commit()

        assert result.lobbies_formed == 1
        lobby = session.scalar(select(Lobby))
        assert lobby is not None
        assert lobby.mode == "casual"
        assert lobby.algorithm_version == "level_v1"
        assert lobby.duration_minutes == 60
        assert lobby.scheduled_start_at.replace(tzinfo=UTC) == datetime(
            2026, 11, 3, 21, 0, tzinfo=UTC
        )
        assert lobby.court_preference == "ANY"

        participants = list(session.scalars(select(LobbyParticipant)))
        assert len(participants) == 10
        assert {item.team for item in participants} == {1, 2}
        assert sum(1 for item in participants if item.team == 1) == 5
        assert (
            session.scalar(
                select(func.count()).select_from(QueueEntry).where(QueueEntry.status == "matched")
            )
            == 10
        )

        run = session.scalar(select(MatchmakingRun))
        assert run is not None and run.status == "completed"
        assert run.lobbies_formed == 1


def test_rerun_does_not_duplicate(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        queue_players(session, sport_format, 10)
        session.commit()

        first = service(session).run_once(NOW)
        session.commit()
        second = service(session).run_once(NOW)
        session.commit()

        assert first.lobbies_formed == 1
        assert second.lobbies_formed == 0
        assert session.scalar(select(func.count()).select_from(Lobby)) == 1
        assert session.scalar(select(func.count()).select_from(LobbyParticipant)) == 10


def test_expired_entries_are_marked_and_not_formed(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        entries = queue_players(session, sport_format, 10)
        for entry in entries:
            entry.expires_at = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
        session.commit()

        result = service(session).run_once(NOW)
        session.commit()

        assert result.entries_expired == 10
        assert result.lobbies_formed == 0
        assert session.scalar(select(func.count()).select_from(Lobby)) == 0


def test_incompatible_court_preferences_do_not_form(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        queue_players(session, sport_format, 5, court="PUBLIC_ONLY")
        queue_players(session, sport_format, 5, court="PRIVATE_ONLY")
        session.commit()

        result = service(session).run_once(NOW)
        session.commit()

        assert result.lobbies_formed == 0
        assert session.scalar(select(func.count()).select_from(Lobby)) == 0


def test_distant_participants_do_not_form(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        queue_players(session, sport_format, 9, lat=-23.55, lng=-46.63, radius=5)
        queue_players(session, sport_format, 1, lat=-22.90, lng=-43.18, radius=5)
        session.commit()

        result = service(session).run_once(NOW)
        session.commit()

        assert result.lobbies_formed == 0


def test_missing_availability_blocks_formation(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        queue_players(session, sport_format, 9)
        queue_players(session, sport_format, 1, available=False)
        session.commit()

        result = service(session).run_once(NOW)
        session.commit()

        assert result.lobbies_formed == 0


def test_concurrent_workers_never_duplicate_participants(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        queue_players(session, sport_format, 20)
        session.commit()

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker() -> None:
        with session_factory() as session:
            try:
                barrier.wait(timeout=10)
                service(session).run_once(NOW)
                session.commit()
            except BaseException as error:  # noqa: BLE001 - falha é registrada e vista no teste
                session.commit()
                errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not any(thread.is_alive() for thread in threads)
    assert not errors, f"erros inesperados: {errors!r}"

    with session_factory() as session:
        lobbies = session.scalar(select(func.count()).select_from(Lobby))
        participants = list(session.scalars(select(LobbyParticipant)))
        matched_entries = session.scalar(
            select(func.count()).select_from(QueueEntry).where(QueueEntry.status == "matched")
        )

    assert lobbies == 2
    assert len(participants) == 20
    assert len({item.user_id for item in participants}) == 20
    assert matched_entries == 20


def test_ranked_lobby_uses_mmr_and_records_policy(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        users = [add_player(session, sport_format) for _ in range(10)]
        ratings = {user.id: 2000 - index * 100 for index, user in enumerate(users)}
        for user_id, rating in ratings.items():
            session.add(
                RatingAccount(
                    user_id=user_id,
                    format_id=sport_format.id,
                    rating=float(rating),
                    rating_deviation=100.0,
                    volatility=0.06,
                    matches_played=10,
                    algorithm_version="glicko2_team_v1",
                )
            )
        for user in users:
            service(session).enqueue(
                user.id,
                sport_format.id,
                mode="ranked",
                now=NOW,
            )
        session.commit()

        result = service(session).run_once(NOW)
        session.commit()

        assert result.lobbies_formed == 1
        lobby = session.scalar(select(Lobby))
        assert lobby is not None
        assert lobby.mode == "ranked"
        assert lobby.algorithm_version == "mmr_v1"
        participants = list(session.scalars(select(LobbyParticipant)))
        assert len(participants) == 10
        team_1 = [ratings[item.user_id] for item in participants if item.team == 1]
        team_2 = [ratings[item.user_id] for item in participants if item.team == 2]
        assert abs(sum(team_1) - sum(team_2)) <= 100
        assert max(team_1) - min(team_1) <= 800
        assert max(team_2) - min(team_2) <= 800


def add_format(
    session: Session,
    *,
    sport: Sport,
    slug: str,
    team_size: int = 1,
) -> SportFormat:
    sport_format = SportFormat(
        sport_id=sport.id,
        slug=slug,
        name=slug,
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


def test_tie_between_entries_of_same_user_draws_one(
    session_factory: sessionmaker[Session],
) -> None:
    """Duas entradas elegíveis no mesmo ciclo: exatamente uma forma lobby.

    Repete o cenário para provar que o sorteio não é determinístico e que a
    entrada perdedora continua ``waiting``.
    """
    rounds = 20
    winners: list[int] = []
    with session_factory() as session:
        sport = Sport(slug="multi", name="Multi")
        session.add(sport)
        session.flush()

        for index in range(rounds):
            first = add_format(session, sport=sport, slug=f"multi-{index}-a")
            second = add_format(session, sport=sport, slug=f"multi-{index}-b")
            anchor = add_player(session, first)
            session.add(
                UserSportProfile(
                    user_id=anchor.id,
                    format_id=second.id,
                    level="intermediate",
                    court_preference="ANY",
                )
            )
            partner_a = add_player(session, first)
            partner_b = add_player(session, second)

            service(session).enqueue(anchor.id, first.id, now=NOW)
            service(session).enqueue(anchor.id, second.id, now=NOW)
            service(session).enqueue(partner_a.id, first.id, now=NOW)
            service(session).enqueue(partner_b.id, second.id, now=NOW)
            session.flush()

            result = service(session).run_once(NOW)
            session.commit()

            assert result.lobbies_formed == 1
            lobby = session.scalar(select(Lobby).where(Lobby.format_id.in_((first.id, second.id))))
            assert lobby is not None
            winners.append(1 if lobby.format_id == first.id else 2)
            waiting = session.scalar(
                select(func.count())
                .select_from(QueueEntry)
                .where(QueueEntry.user_id == anchor.id, QueueEntry.status == "waiting")
            )
            assert waiting == 1
            matched = session.scalar(
                select(func.count())
                .select_from(QueueEntry)
                .where(QueueEntry.user_id == anchor.id, QueueEntry.status == "matched")
            )
            assert matched == 1

            # Limpa o restante deste cenário para o próximo ciclo não formar
            # outro lobby com as entradas perdedoras.
            for leftover in session.scalars(
                select(QueueEntry).where(
                    QueueEntry.format_id.in_((first.id, second.id)),
                    QueueEntry.status == "waiting",
                )
            ):
                leftover.status = "expired"
            session.commit()

    assert set(winners) == {1, 2}, f"sorteio sempre escolheu o mesmo grupo: {winners}"


def add_single_format(session: Session, slug: str) -> SportFormat:
    sport = Sport(slug=f"{slug}-sport", name=slug)
    session.add(sport)
    session.flush()
    return add_format(session, sport=sport, slug=slug, team_size=1)


def add_lobby(
    session: Session,
    sport_format: SportFormat,
    user: User,
    *,
    start: datetime,
    origin: str = "manual",
    status: str = "scheduled",
) -> Lobby:
    lobby = Lobby(
        format_id=sport_format.id,
        format_version=1,
        origin=origin,
        mode="casual",
        status=status,
        court_preference="ANY",
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(minutes=60),
        duration_minutes=60,
        center_lat=-23.55,
        center_lng=-46.63,
        radius_km=10,
        algorithm_version="test",
    )
    session.add(lobby)
    session.flush()
    session.add(
        LobbyParticipant(
            lobby_id=lobby.id,
            user_id=user.id,
            team=1,
            level="intermediate",
        )
    )
    session.flush()
    return lobby


# 2026-11-03 12:00 UTC = 09:00 em São Paulo; com 2 h de antecedência o primeiro
# slot local é 11:00.
SLOT_NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
BUSY_START = datetime(2026, 11, 3, 14, 0, tzinfo=UTC)  # 11:00 local
NEXT_FREE = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)  # 12:00 local


@pytest.mark.parametrize("origin", ["matchmaking", "manual"])
@pytest.mark.parametrize(
    ("now", "expected_start"),
    [
        # 08:00 local + 2 h = 10:00 local (13:00 UTC), antes do lobby ocupado.
        (
            datetime(2026, 11, 3, 11, 0, tzinfo=UTC),
            datetime(2026, 11, 3, 13, 0, tzinfo=UTC),
        ),
        # 09:00 local + 2 h = 11:00 local, ocupado; vai para 12:00 local.
        (SLOT_NOW, NEXT_FREE),
    ],
)
def test_existing_lobby_blocks_overlapping_slot(
    session_factory: sessionmaker[Session],
    origin: str,
    now: datetime,
    expected_start: datetime,
) -> None:
    """Lobby 11h–12h ocupa o tempo; a próxima partida do usuário não pode cruzar."""
    with session_factory() as session:
        sport_format = add_single_format(session, "block")
        anchor = add_player(session, sport_format, window_start=time(10, 0), window_end=time(14, 0))
        partner = add_player(
            session, sport_format, window_start=time(10, 0), window_end=time(14, 0)
        )
        previous = add_lobby(session, sport_format, anchor, start=BUSY_START, origin=origin)
        service(session).enqueue(anchor.id, sport_format.id, now=now)
        service(session).enqueue(partner.id, sport_format.id, now=now)
        session.commit()

        result = service(session).run_once(now)
        session.commit()

        assert result.lobbies_formed == 1
        created = session.scalar(select(Lobby).where(Lobby.id != previous.id))
        assert created is not None
        assert created.scheduled_start_at.replace(tzinfo=UTC) == expected_start


def test_cancelled_lobby_does_not_block_slot(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = add_single_format(session, "cancelled")
        anchor = add_player(session, sport_format, window_start=time(10, 0), window_end=time(14, 0))
        partner = add_player(
            session, sport_format, window_start=time(10, 0), window_end=time(14, 0)
        )
        add_lobby(
            session,
            sport_format,
            anchor,
            start=BUSY_START,
            origin="matchmaking",
            status="cancelled",
        )
        service(session).enqueue(anchor.id, sport_format.id, now=SLOT_NOW)
        service(session).enqueue(partner.id, sport_format.id, now=SLOT_NOW)
        session.commit()

        result = service(session).run_once(SLOT_NOW)
        session.commit()

        assert result.lobbies_formed == 1
        created = session.scalar(select(Lobby).where(Lobby.status == "scheduled"))
        assert created is not None
        assert created.scheduled_start_at.replace(tzinfo=UTC) == BUSY_START


def test_lobby_of_another_user_does_not_block_slot(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = add_single_format(session, "stranger")
        anchor = add_player(session, sport_format, window_start=time(10, 0), window_end=time(14, 0))
        partner = add_player(
            session, sport_format, window_start=time(10, 0), window_end=time(14, 0)
        )
        stranger = add_player(
            session, sport_format, window_start=time(10, 0), window_end=time(14, 0)
        )
        foreign = add_lobby(session, sport_format, stranger, start=BUSY_START)
        service(session).enqueue(anchor.id, sport_format.id, now=SLOT_NOW)
        service(session).enqueue(partner.id, sport_format.id, now=SLOT_NOW)
        session.commit()

        result = service(session).run_once(SLOT_NOW)
        session.commit()

        assert result.lobbies_formed == 1
        created = session.scalar(select(Lobby).where(Lobby.id != foreign.id))
        assert created is not None
        assert created.scheduled_start_at.replace(tzinfo=UTC) == BUSY_START


def test_replace_failure_leaves_no_partial_state(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with session_factory() as session:
        sport = Sport(slug="replace", name="Replace")
        session.add(sport)
        session.flush()
        first = add_format(session, sport=sport, slug="replace-a")
        add_format(session, sport=sport, slug="replace-b")
        user = add_player(session, first)
        old = service(session).enqueue(user.id, first.id, now=NOW)
        session.commit()
        old_id = old.id

        calls = {"count": 0}
        original = MatchmakingService._build_entry

        def flaky(
            self: MatchmakingService,
            *args: object,
            **kwargs: object,
        ) -> QueueEntry:
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("falha simulada no meio da substituição")
            return original(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(MatchmakingService, "_build_entry", flaky)

        with pytest.raises(RuntimeError):
            service(session).replace(user.id, [first.id], ["casual", "ranked"], now=NOW)
        session.rollback()

        rows = list(session.scalars(select(QueueEntry).where(QueueEntry.user_id == user.id)))
        assert [(row.id, row.status) for row in rows] == [(old_id, "waiting")]
        assert session.scalar(select(func.count()).select_from(Lobby)) == 0


def test_replace_never_leaves_two_active_entries_for_same_format_and_mode(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        user = add_player(session, sport_format)
        service(session).enqueue(user.id, sport_format.id, now=NOW)
        session.commit()

        service(session).replace(
            user.id,
            [sport_format.id, sport_format.id],
            ["casual", "casual"],
            now=NOW,
        )
        session.commit()

        statuses = list(
            session.scalars(select(QueueEntry.status).where(QueueEntry.user_id == user.id))
        )
        assert sorted(statuses) == ["cancelled", "waiting"]

        # Nova substituição pelo mesmo par cancela e recria sem violar o índice.
        service(session).replace(user.id, [sport_format.id], ["casual"], now=NOW)
        session.commit()
        statuses = list(
            session.scalars(select(QueueEntry.status).where(QueueEntry.user_id == user.id))
        )
        assert sorted(statuses) == ["cancelled", "cancelled", "waiting"]


def test_matched_entries_lists_only_scheduled_lobbies_newest_first(
    session_factory: sessionmaker[Session],
) -> None:
    """``matched_entries`` ignora TTL da fila e histórico de lobbies encerrados."""
    with session_factory() as session:
        older_format = add_single_format(session, "matched-a")
        newer_format = add_single_format(session, "matched-b")
        cancelled_format = add_single_format(session, "matched-c")
        completed_format = add_single_format(session, "matched-d")
        no_lobby_format = add_single_format(session, "matched-e")
        waiting_format = add_single_format(session, "matched-f")
        user = add_player(session, older_format)
        for extra_format in (
            newer_format,
            cancelled_format,
            completed_format,
            no_lobby_format,
            waiting_format,
        ):
            session.add(
                UserSportProfile(
                    user_id=user.id,
                    format_id=extra_format.id,
                    level="intermediate",
                    court_preference="ANY",
                )
            )
        session.flush()

        older = service(session).enqueue(user.id, older_format.id, now=NOW)
        newer = service(session).enqueue(user.id, newer_format.id, now=NOW)
        cancelled = service(session).enqueue(user.id, cancelled_format.id, now=NOW)
        completed = service(session).enqueue(user.id, completed_format.id, now=NOW)
        no_lobby = service(session).enqueue(user.id, no_lobby_format.id, now=NOW)
        waiting = service(session).enqueue(user.id, waiting_format.id, now=NOW)

        older.status = "matched"
        older.matched_at = NOW - timedelta(hours=2)
        # TTL vencido não invalida a partida: a autoridade é o lobby.
        older.expires_at = NOW - timedelta(hours=1)
        older.lobby_id = add_lobby(session, older_format, user, start=NOW + timedelta(days=1)).id

        newer.status = "matched"
        newer.matched_at = NOW
        newer.lobby_id = add_lobby(session, newer_format, user, start=NOW + timedelta(days=2)).id

        cancelled.status = "matched"
        cancelled.matched_at = NOW + timedelta(minutes=1)
        cancelled.lobby_id = add_lobby(
            session,
            cancelled_format,
            user,
            start=NOW + timedelta(days=3),
            status="cancelled",
        ).id

        completed.status = "matched"
        completed.matched_at = NOW + timedelta(minutes=2)
        completed.lobby_id = add_lobby(
            session,
            completed_format,
            user,
            start=NOW + timedelta(days=4),
            status="completed",
        ).id

        no_lobby.status = "matched"
        no_lobby.matched_at = NOW + timedelta(minutes=3)
        session.flush()

        entries = service(session).matched_entries(user.id)

        assert [entry.id for entry in entries] == [newer.id, older.id]
        assert waiting.id not in {entry.id for entry in entries}
