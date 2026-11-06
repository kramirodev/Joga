"""Serviço de fila e formação transacional de lobbies."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.matches.service import create_match_for_lobby
from app.modules.matchmaking.models import Lobby, LobbyParticipant, MatchmakingRun, QueueEntry
from app.modules.matchmaking.policy import (
    AvailabilityWindow,
    Candidate,
    MeetingRegion,
    RatingBalanceError,
    RegionPoint,
    balance_teams,
    balance_teams_by_rating,
    court_intersection,
    meeting_region,
    select_start,
)
from app.modules.profile.models import Availability, SportFormat, UserRegion, UserSportProfile
from app.modules.ratings.models import RatingAccount

MMR_ALGORITHM_VERSION = "mmr_v1"
MAX_RANKED_TEAM_SPAN = 800.0


class QueueError(Exception):
    """Erro base da fila de matchmaking."""


class InvalidMode(QueueError):
    """Modo de partida desconhecido."""


class InvalidFormat(QueueError):
    """Formato inexistente ou inativo."""


class SportProfileRequired(QueueError):
    """Usuário não configurou nível para o formato."""


class RegionRequired(QueueError):
    """Usuário não definiu região de busca."""


class AlreadyQueued(QueueError):
    """Já existe entrada ativa para o mesmo usuário, formato e modo."""


@dataclass(frozen=True)
class RunResult:
    run_id: uuid.UUID
    entries_expired: int
    lobbies_formed: int


@dataclass(frozen=True)
class Formation:
    court: str
    region: MeetingRegion
    start: datetime


class MatchmakingService:
    """Orquestra fila, compatibilidade e criação do lobby."""

    def __init__(
        self,
        session: Session,
        *,
        algorithm_version: str = "level_v1",
        max_radius_km: int = 30,
        search_days: int = 7,
        slot_minutes: int = 30,
        min_lead_minutes: int = 120,
        queue_ttl_hours: int = 24,
        default_timezone: str = "America/Sao_Paulo",
    ) -> None:
        self._session = session
        self._algorithm = algorithm_version
        self._max_radius = max_radius_km
        self._search_days = search_days
        self._slot_minutes = slot_minutes
        self._min_lead = min_lead_minutes
        self._ttl = timedelta(hours=queue_ttl_hours)
        self._timezone = default_timezone

    # Fila ---------------------------------------------------------------

    def enqueue(
        self,
        user_id: uuid.UUID,
        format_id: uuid.UUID,
        *,
        court_preference: str | None = None,
        mode: str = "casual",
        now: datetime | None = None,
    ) -> QueueEntry:
        if mode not in ("casual", "ranked"):
            raise InvalidMode("modo de partida inválido")

        sport_format = self._session.get(SportFormat, format_id)
        if sport_format is None or not sport_format.active:
            raise InvalidFormat("formato inexistente ou inativo")

        sport_profile = self._session.scalar(
            select(UserSportProfile).where(
                UserSportProfile.user_id == user_id,
                UserSportProfile.format_id == format_id,
            )
        )
        if sport_profile is None:
            raise SportProfileRequired("defina nível e preferência para o formato")

        region = self._session.get(UserRegion, user_id)
        if region is None:
            raise RegionRequired("defina uma região antes de entrar na fila")

        current = ensure_utc(now or utcnow())
        existing = self._session.scalar(
            select(QueueEntry).where(
                QueueEntry.user_id == user_id,
                QueueEntry.format_id == format_id,
                QueueEntry.mode == mode,
                QueueEntry.status == "waiting",
            )
        )
        if existing is not None:
            raise AlreadyQueued("já existe entrada ativa na fila")

        entry = QueueEntry(
            user_id=user_id,
            format_id=format_id,
            mode=mode,
            court_preference=court_preference or sport_profile.court_preference,
            level=sport_profile.level,
            status="waiting",
            center_lat=region.center_lat,
            center_lng=region.center_lng,
            radius_km=region.radius_km,
            expires_at=current + self._ttl,
        )
        self._session.add(entry)
        self._session.flush()
        return entry

    def latest_entry(self, user_id: uuid.UUID) -> QueueEntry | None:
        return self._session.scalar(
            select(QueueEntry)
            .where(
                QueueEntry.user_id == user_id,
                QueueEntry.status.in_(("waiting", "matched")),
            )
            .order_by(QueueEntry.created_at.desc())
            .limit(1)
        )

    def leave(self, user_id: uuid.UUID) -> bool:
        entry = self._session.scalar(
            select(QueueEntry).where(
                QueueEntry.user_id == user_id,
                QueueEntry.status == "waiting",
            )
        )
        if entry is None:
            return False
        entry.status = "cancelled"
        entry.updated_at = utcnow()
        self._session.flush()
        return True

    # Worker -------------------------------------------------------------

    def run_once(self, now: datetime | None = None) -> RunResult:
        current = ensure_utc(now or utcnow())
        run = MatchmakingRun(status="running", algorithm_version=self._algorithm)
        self._session.add(run)
        self._session.flush()

        try:
            expired = self._expire(current)
            with self._session.begin_nested():
                formed = self._form_all(current)
            run.entries_expired = expired
            run.lobbies_formed = formed
            run.status = "completed"
            run.finished_at = utcnow()
            self._session.flush()
            return RunResult(
                run_id=run.id,
                entries_expired=expired,
                lobbies_formed=formed,
            )
        except Exception:
            run.status = "failed"
            run.finished_at = utcnow()
            self._session.flush()
            raise

    def _expire(self, now: datetime) -> int:
        result = cast(
            "CursorResult[Any]",
            self._session.execute(
                update(QueueEntry)
                .where(QueueEntry.status == "waiting", QueueEntry.expires_at <= now)
                .values(status="expired", updated_at=now)
                .execution_options(synchronize_session=False)
            ),
        )
        return int(result.rowcount or 0)

    def _form_all(self, now: datetime) -> int:
        groups: dict[tuple[uuid.UUID, str], list[QueueEntry]] = defaultdict(list)
        for entry in self._lock_waiting(now):
            groups[(entry.format_id, entry.mode)].append(entry)

        formed = 0
        for (format_id, mode), entries in groups.items():
            sport_format = self._session.get(SportFormat, format_id)
            if sport_format is None or not sport_format.active:
                continue
            ratings = self._ratings_for_format(format_id) if mode == "ranked" else None
            formed += self._form_group(
                sport_format,
                mode,
                entries,
                now,
                ratings=ratings,
            )
        return formed

    def _ratings_for_format(self, format_id: uuid.UUID) -> dict[uuid.UUID, float]:
        rows = self._session.execute(
            select(RatingAccount.user_id, RatingAccount.rating).where(
                RatingAccount.format_id == format_id
            )
        )
        return {user_id: rating for user_id, rating in rows}

    def _lock_waiting(self, now: datetime) -> list[QueueEntry]:
        statement = (
            select(QueueEntry)
            .where(QueueEntry.status == "waiting", QueueEntry.expires_at > now)
            .order_by(QueueEntry.created_at, QueueEntry.id)
        )
        if self._session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        return list(self._session.scalars(statement))

    def _form_group(
        self,
        sport_format: SportFormat,
        mode: str,
        entries: Sequence[QueueEntry],
        now: datetime,
        *,
        ratings: dict[uuid.UUID, float] | None = None,
    ) -> int:
        needed = sport_format.total_participants
        if needed < 2:
            return 0

        pending = list(entries)
        formed = 0
        while len(pending) >= needed:
            base = pending[0]
            selected = [base]
            formation: Formation | None = None
            candidates = pending[1:]
            if mode == "ranked" and ratings is not None:
                anchor_rating = ratings.get(base.user_id, 1500.0)
                candidates = sorted(
                    candidates,
                    key=lambda entry: (
                        abs(ratings.get(entry.user_id, 1500.0) - anchor_rating),
                        entry.created_at,
                        str(entry.id),
                    ),
                )
            for candidate in candidates:
                if len(selected) == needed:
                    break
                trial = [*selected, candidate]
                trial_formation = self._evaluate(trial, sport_format, now)
                if trial_formation is not None:
                    selected.append(candidate)
                    formation = trial_formation
            if len(selected) != needed or formation is None:
                # A entrada mais antiga não fecha grupo; tenta a próxima sem bloqueá-la.
                pending = pending[1:]
                continue

            teams = None
            if mode == "ranked" and ratings is not None:
                try:
                    teams = balance_teams_by_rating(
                        [(entry.user_id, ratings.get(entry.user_id, 1500.0)) for entry in selected],
                        team_size=needed // 2,
                        max_span=MAX_RANKED_TEAM_SPAN,
                    )
                except RatingBalanceError:
                    pending = pending[1:]
                    continue

            self._create_lobby(
                sport_format,
                mode,
                selected,
                formation,
                now,
                ratings=ratings,
                teams=teams,
            )
            formed += 1
            pending = [entry for entry in pending if entry not in selected]
        return formed

    def _evaluate(
        self,
        entries: Sequence[QueueEntry],
        sport_format: SportFormat,
        now: datetime,
    ) -> Formation | None:
        court = court_intersection(entry.court_preference for entry in entries)
        if court is None:
            return None

        region = meeting_region(
            [
                RegionPoint(
                    lat=entry.center_lat,
                    lng=entry.center_lng,
                    radius_km=entry.radius_km,
                )
                for entry in entries
            ],
            self._max_radius,
        )
        if region is None:
            return None

        availability = [self._availability(entry.user_id) for entry in entries]
        start = select_start(
            availability,
            duration_minutes=sport_format.duration_minutes,
            now=now,
            search_days=self._search_days,
            slot_minutes=self._slot_minutes,
            min_lead_minutes=self._min_lead,
            default_timezone=self._timezone,
        )
        if start is None:
            return None
        return Formation(court=court, region=region, start=start)

    def _availability(self, user_id: uuid.UUID) -> list[AvailabilityWindow]:
        rows = self._session.scalars(select(Availability).where(Availability.user_id == user_id))
        return [
            AvailabilityWindow(
                weekday=row.weekday,
                start_time=row.start_time,
                end_time=row.end_time,
                timezone=row.timezone,
            )
            for row in rows
        ]

    def _create_lobby(
        self,
        sport_format: SportFormat,
        mode: str,
        entries: Sequence[QueueEntry],
        formation: Formation,
        now: datetime,
        *,
        ratings: dict[uuid.UUID, float] | None = None,
        teams: dict[uuid.UUID, int] | None = None,
    ) -> Lobby:
        algorithm_version = MMR_ALGORITHM_VERSION if mode == "ranked" else self._algorithm
        lobby = Lobby(
            format_id=sport_format.id,
            format_version=sport_format.version,
            origin="matchmaking",
            mode=mode,
            status="scheduled",
            court_preference=formation.court,
            scheduled_start_at=formation.start,
            scheduled_end_at=formation.start + timedelta(minutes=sport_format.duration_minutes),
            duration_minutes=sport_format.duration_minutes,
            center_lat=formation.region.lat,
            center_lng=formation.region.lng,
            radius_km=formation.region.radius_km,
            algorithm_version=algorithm_version,
        )
        self._session.add(lobby)
        self._session.flush()

        if teams is None:
            if mode == "ranked":
                teams = balance_teams_by_rating(
                    [
                        (
                            entry.user_id,
                            (ratings or {}).get(entry.user_id, 1500.0),
                        )
                        for entry in entries
                    ],
                    team_size=sport_format.total_participants // 2,
                    max_span=MAX_RANKED_TEAM_SPAN,
                )
            else:
                teams = balance_teams(
                    [
                        Candidate(
                            user_id=entry.user_id,
                            level=entry.level,
                            region=RegionPoint(entry.center_lat, entry.center_lng, entry.radius_km),
                        )
                        for entry in entries
                    ]
                )
        participants: list[LobbyParticipant] = []
        for entry in entries:
            participant = LobbyParticipant(
                lobby_id=lobby.id,
                user_id=entry.user_id,
                queue_entry_id=entry.id,
                team=teams[entry.user_id],
                level=entry.level,
            )
            participants.append(participant)
            self._session.add(participant)
            entry.status = "matched"
            entry.lobby_id = lobby.id
            entry.matched_at = now
            entry.updated_at = now
        self._session.flush()
        create_match_for_lobby(self._session, lobby, participants, now=now)
        return lobby
