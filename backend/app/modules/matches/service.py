"""Ciclo de vida da partida: confirmação, presença e cancelamento."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.matches.models import Match, MatchParticipant, MatchStateTransition
from app.modules.matchmaking.models import Lobby, LobbyParticipant, QueueEntry
from app.modules.matchmaking.policy import (
    AvailabilityWindow,
    court_intersection,
    haversine_km,
    windows_cover,
)
from app.modules.profile.models import Availability, SportFormat

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "PENDING_CONFIRMATION": {"READY", "CANCELLED", "EXPIRED"},
    "READY": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"RESULT_PENDING"},
    "RESULT_PENDING": {"FINALIZED", "DISPUTED", "VOIDED"},
    "FINALIZED": set(),
    "DISPUTED": {"FINALIZED", "VOIDED", "DISPUTED"},
    "VOIDED": set(),
    "CANCELLED": set(),
    "EXPIRED": set(),
}

CONFIRMATION_WINDOW = timedelta(hours=24)
CONFIRMATION_LEAD = timedelta(minutes=45)
CHECK_IN_OPEN_LEAD = timedelta(minutes=60)
CHECK_IN_CLOSE_LEAD = timedelta(minutes=30)
SUBSTITUTION_LEAD = timedelta(minutes=15)
SUBSTITUTE_WINDOW = timedelta(minutes=15)


class MatchError(Exception):
    """Erro base do ciclo de partida."""


class MatchNotFound(MatchError):
    """Partida inexistente ou usuário não participa."""


class InvalidTransition(MatchError):
    """Transição de estado não permitida."""


class ActionNotAllowed(MatchError):
    """Ação não permitida no estado atual."""


class CheckInClosed(MatchError):
    """Fora da janela de check-in."""


@dataclass(frozen=True)
class AdvanceResult:
    confirmed_expired: int
    cancelled: int
    started: int
    substitutes_invited: int


def create_match_for_lobby(
    session: Session,
    lobby: Lobby,
    participants: Sequence[LobbyParticipant],
    *,
    now: datetime | None = None,
) -> Match:
    """Cria a partida em PENDING_CONFIRMATION a partir do lobby formado."""
    current = ensure_utc(now or utcnow())
    start = ensure_utc(lobby.scheduled_start_at)
    end = ensure_utc(lobby.scheduled_end_at)
    match = Match(
        lobby_id=lobby.id,
        state="PENDING_CONFIRMATION",
        scheduled_start_at=start,
        scheduled_end_at=end,
        confirmation_deadline=min(current + CONFIRMATION_WINDOW, start - CONFIRMATION_LEAD),
        check_in_opens_at=start - CHECK_IN_OPEN_LEAD,
        check_in_deadline=start - CHECK_IN_CLOSE_LEAD,
        substitution_deadline=start - SUBSTITUTION_LEAD,
    )
    session.add(match)
    session.flush()
    rows: list[MatchParticipant] = []
    for item in participants:
        row = MatchParticipant(
            match_id=match.id,
            user_id=item.user_id,
            team=item.team,
            level=item.level,
            status="invited",
            queue_entry_id=item.queue_entry_id,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    select_captains(session, match, lobby, rows, now=current)
    _record(session, match, None, "PENDING_CONFIRMATION", None, "match_formed")
    return match


CAPTAIN_SELECTION_VERSION = "provisional_v1"


def select_captains(
    session: Session,
    match: Match,
    lobby: Lobby,
    participants: Sequence[MatchParticipant],
    *,
    now: datetime,
) -> None:
    """Seleciona um capitão simbólico por equipe, de forma determinística.

    Na Fase 7 o critério é o número de partidas ``FINALIZED`` do mesmo formato,
    concluídas antes da partida atual, com UUID como desempate. Lobbies manuais
    ficam sem capitão.
    """
    if lobby.origin != "matchmaking":
        return
    for team in (1, 2):
        candidates = [item for item in participants if item.team == team and not item.is_substitute]
        if not candidates:
            continue
        counts = {
            item.id: int(
                session.scalar(
                    select(func.count(Match.id))
                    .join(MatchParticipant, MatchParticipant.match_id == Match.id)
                    .join(Lobby, Lobby.id == Match.lobby_id)
                    .where(
                        Match.state == "FINALIZED",
                        Match.id != match.id,
                        Match.scheduled_end_at < match.scheduled_start_at,
                        MatchParticipant.user_id == item.user_id,
                        MatchParticipant.status == "checked_in",
                        Lobby.format_id == lobby.format_id,
                    )
                )
                or 0
            )
            for item in candidates
        }
        best = sorted(candidates, key=lambda item: (-counts[item.id], str(item.user_id)))[0]
        best.is_captain = True
        best.captain_selection_version = CAPTAIN_SELECTION_VERSION
        best.captain_selected_at = now
    session.flush()


def _record(
    session: Session,
    match: Match,
    from_state: str | None,
    to_state: str,
    actor_user_id: uuid.UUID | None,
    reason: str | None,
) -> None:
    session.add(
        MatchStateTransition(
            match_id=match.id,
            from_state=from_state,
            to_state=to_state,
            actor_user_id=actor_user_id,
            reason=reason,
        )
    )


def transition(
    session: Session,
    match: Match,
    to_state: str,
    *,
    actor_user_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> None:
    if to_state not in ALLOWED_TRANSITIONS.get(match.state, set()):
        raise InvalidTransition(f"{match.state} -> {to_state} não permitido")
    from_state = match.state
    match.state = to_state
    match.updated_at = utcnow()
    if to_state == "CANCELLED":
        match.cancelled_reason = reason
    _record(session, match, from_state, to_state, actor_user_id, reason)
    session.flush()


def active_participants(match_id: uuid.UUID, session: Session) -> list[MatchParticipant]:
    return list(
        session.scalars(
            select(MatchParticipant).where(
                MatchParticipant.match_id == match_id,
                MatchParticipant.status.in_(("invited", "confirmed", "checked_in")),
            )
        )
    )


def _all_confirmed(session: Session, match: Match) -> bool:
    active = active_participants(match.id, session)
    return bool(active) and all(item.status in ("confirmed", "checked_in") for item in active)


def _all_checked_in(session: Session, match: Match) -> bool:
    active = active_participants(match.id, session)
    return bool(active) and all(item.status == "checked_in" for item in active)


class MatchService:
    """Ações de participante e avanço por tempo."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_user(self, match_id: uuid.UUID, user_id: uuid.UUID) -> Match:
        match = self._session.get(Match, match_id)
        if match is None:
            raise MatchNotFound("partida não encontrada")
        participant = self._participant(match_id, user_id)
        if participant is None:
            raise MatchNotFound("partida não encontrada")
        return match

    def list_for_user(self, user_id: uuid.UUID) -> list[Match]:
        return list(
            self._session.scalars(
                select(Match)
                .join(MatchParticipant, MatchParticipant.match_id == Match.id)
                .where(MatchParticipant.user_id == user_id)
                .order_by(Match.scheduled_start_at.desc())
            )
        )

    def confirm(
        self, match_id: uuid.UUID, user_id: uuid.UUID, now: datetime | None = None
    ) -> Match:
        match = self.get_for_user(match_id, user_id)
        self._lock(match)
        participant = self._participant(match_id, user_id)
        assert participant is not None
        if participant.status in ("confirmed", "checked_in"):
            return match
        if participant.status in ("declined", "no_show"):
            raise ActionNotAllowed("participante não pode confirmar")
        if match.state == "PENDING_CONFIRMATION":
            pass
        elif not (match.state == "READY" and participant.is_substitute):
            raise ActionNotAllowed("partida não aceita confirmação")
        if (
            ensure_utc(now or utcnow()) > ensure_utc(match.confirmation_deadline)
            and not participant.is_substitute
        ):
            raise ActionNotAllowed("prazo de confirmação encerrado")

        participant.status = "confirmed"
        participant.confirmed_at = ensure_utc(now or utcnow())
        participant.updated_at = utcnow()
        self._session.flush()
        if match.state == "PENDING_CONFIRMATION" and _all_confirmed(self._session, match):
            transition(self._session, match, "READY", actor_user_id=user_id, reason="all_confirmed")
        return match

    def decline(
        self, match_id: uuid.UUID, user_id: uuid.UUID, now: datetime | None = None
    ) -> Match:
        match = self.get_for_user(match_id, user_id)
        self._lock(match)
        participant = self._participant(match_id, user_id)
        assert participant is not None
        if participant.status == "declined":
            return match
        if participant.status == "no_show":
            raise ActionNotAllowed("participante já marcado como ausente")
        if match.state not in ("PENDING_CONFIRMATION", "READY"):
            raise ActionNotAllowed("partida não aceita recusa")

        participant.status = "declined"
        participant.updated_at = utcnow()
        self._session.flush()
        self._dissolve(match, now or utcnow(), "declined")
        return match

    def check_in(
        self, match_id: uuid.UUID, user_id: uuid.UUID, now: datetime | None = None
    ) -> Match:
        match = self.get_for_user(match_id, user_id)
        self._lock(match)
        participant = self._participant(match_id, user_id)
        assert participant is not None
        current = ensure_utc(now or utcnow())
        if participant.status == "checked_in":
            return match
        if match.state != "READY":
            raise ActionNotAllowed("partida não está pronta para check-in")
        if not participant.is_substitute and current < ensure_utc(match.check_in_opens_at):
            raise CheckInClosed("check-in ainda não abriu")
        deadline = (
            match.substitution_deadline if participant.is_substitute else match.check_in_deadline
        )
        if current > ensure_utc(deadline):
            raise CheckInClosed("check-in encerrado")
        if participant.status not in ("confirmed",):
            raise ActionNotAllowed("confirme a partida antes do check-in")

        participant.status = "checked_in"
        participant.checked_in_at = current
        participant.updated_at = utcnow()
        self._session.flush()
        return match

    def advance(self, now: datetime | None = None) -> AdvanceResult:
        current = ensure_utc(now or utcnow())
        expired = cancelled = started = invited = 0
        matches = list(
            self._session.scalars(
                select(Match).where(Match.state.in_(("PENDING_CONFIRMATION", "READY")))
            )
        )
        for match in matches:
            if match.state == "PENDING_CONFIRMATION":
                if current >= ensure_utc(match.confirmation_deadline):
                    if _all_confirmed(self._session, match):
                        transition(self._session, match, "READY", reason="confirmation_deadline")
                    else:
                        self._dissolve(match, current, "confirmation_deadline")
                        expired += 1
                continue

            invited += self._fill_missing(match, current)

            if current >= ensure_utc(match.substitution_deadline):
                if not self._ready_to_start(match):
                    self._cancel(match, current, "no_substitute")
                    cancelled += 1
                    continue
                if current >= ensure_utc(match.scheduled_start_at):
                    transition(self._session, match, "IN_PROGRESS", reason="scheduled_start")
                    match.started_at = current
                    started += 1
                continue

            if current >= ensure_utc(match.scheduled_start_at):
                if self._ready_to_start(match):
                    transition(self._session, match, "IN_PROGRESS", reason="scheduled_start")
                    match.started_at = current
                    started += 1
                else:
                    self._cancel(match, current, "missing_check_in")
                    cancelled += 1
        self._session.flush()
        return AdvanceResult(
            confirmed_expired=expired,
            cancelled=cancelled,
            started=started,
            substitutes_invited=invited,
        )

    # Internos -----------------------------------------------------------

    def _lock(self, match: Match) -> None:
        """Serializa ações na mesma partida no PostgreSQL."""
        if self._session.get_bind().dialect.name == "postgresql":
            self._session.get(Match, match.id, with_for_update=True, populate_existing=True)

    def _participant(self, match_id: uuid.UUID, user_id: uuid.UUID) -> MatchParticipant | None:
        return self._session.scalar(
            select(MatchParticipant).where(
                MatchParticipant.match_id == match_id,
                MatchParticipant.user_id == user_id,
            )
        )

    def _ready_to_start(self, match: Match) -> bool:
        lobby = self._session.get(Lobby, match.lobby_id)
        if lobby is None:
            return False
        sport_format = self._session.get(SportFormat, lobby.format_id)
        if sport_format is None:
            return False
        active = active_participants(match.id, self._session)
        if len(active) != sport_format.total_participants:
            return False
        if any(item.status != "checked_in" for item in active):
            return False
        return all(
            sum(1 for item in active if item.team == team) == sport_format.team_size
            for team in (1, 2)
        )

    def _fill_missing(self, match: Match, now: datetime) -> int:
        """Marca ausentes no fechamento do check-in e convida suplentes."""
        if now < ensure_utc(match.check_in_deadline):
            return 0
        if now >= ensure_utc(match.substitution_deadline):
            return 0

        missing = [
            item
            for item in active_participants(match.id, self._session)
            if item.status in ("invited", "confirmed")
        ]
        if not missing:
            return 0

        invited = 0
        lobby = self._session.get(Lobby, match.lobby_id)
        if lobby is None:
            return 0
        sport_format = self._session.get(SportFormat, lobby.format_id)
        if sport_format is None:
            return 0

        for participant in missing:
            if participant.is_substitute:
                if now >= ensure_utc(participant.invited_at) + SUBSTITUTE_WINDOW:
                    participant.status = "declined"
                    participant.updated_at = utcnow()
                continue
            participant.status = "no_show"
            participant.updated_at = utcnow()
            replacement = self._pick_substitute(match, lobby, participant)
            if replacement is not None:
                invited += 1
        self._session.flush()
        return invited

    def _pick_substitute(
        self,
        match: Match,
        lobby: Lobby,
        missing: MatchParticipant,
    ) -> QueueEntry | None:
        candidates = list(
            self._session.scalars(
                select(QueueEntry)
                .where(
                    QueueEntry.status == "waiting",
                    QueueEntry.format_id == lobby.format_id,
                    QueueEntry.mode == lobby.mode,
                )
                .order_by(QueueEntry.created_at, QueueEntry.id)
            )
        )
        taken = {item.user_id for item in active_participants(match.id, self._session)}
        for candidate in candidates:
            if candidate.user_id in taken:
                continue
            if court_intersection((lobby.court_preference, candidate.court_preference)) is None:
                continue
            distance = haversine_km(
                lobby.center_lat, lobby.center_lng, candidate.center_lat, candidate.center_lng
            )
            if distance > candidate.radius_km:
                continue
            if distance > lobby.radius_km + 5:
                continue
            if not self._covers_slot(candidate.user_id, match):
                continue
            candidate.status = "matched"
            candidate.lobby_id = lobby.id
            candidate.matched_at = utcnow()
            candidate.updated_at = utcnow()
            self._session.add(
                MatchParticipant(
                    match_id=match.id,
                    user_id=candidate.user_id,
                    team=missing.team,
                    level=candidate.level,
                    status="invited",
                    is_substitute=True,
                    queue_entry_id=candidate.id,
                )
            )
            self._session.flush()
            return candidate
        return None

    def _covers_slot(self, user_id: uuid.UUID, match: Match) -> bool:
        rows = list(
            self._session.scalars(select(Availability).where(Availability.user_id == user_id))
        )
        windows = [
            AvailabilityWindow(
                weekday=row.weekday,
                start_time=row.start_time,
                end_time=row.end_time,
                timezone=row.timezone,
            )
            for row in rows
        ]
        return windows_cover(
            windows,
            ensure_utc(match.scheduled_start_at),
            ensure_utc(match.scheduled_end_at),
        )

    def _dissolve(self, match: Match, now: datetime, reason: str) -> None:
        """Cancela a partida e devolve quem confirmou para a fila com prioridade."""
        current = ensure_utc(now)
        for participant in self._session.scalars(
            select(MatchParticipant).where(MatchParticipant.match_id == match.id)
        ):
            entry = (
                self._session.get(QueueEntry, participant.queue_entry_id)
                if participant.queue_entry_id
                else None
            )
            if participant.status == "confirmed" or participant.status == "checked_in":
                if entry is not None:
                    entry.status = "waiting"
                    entry.lobby_id = None
                    entry.matched_at = None
                    entry.expires_at = current + timedelta(hours=24)
                    entry.updated_at = current
            elif entry is not None and entry.status in ("waiting", "matched"):
                entry.status = "cancelled" if participant.status == "declined" else "expired"
                entry.lobby_id = None
                entry.updated_at = current
            participant.updated_at = current
        self._cancel(match, current, reason)

    def _cancel(self, match: Match, now: datetime, reason: str) -> None:
        current = ensure_utc(now)
        transition(self._session, match, "CANCELLED", reason=reason)
        lobby = self._session.get(Lobby, match.lobby_id)
        if lobby is not None:
            lobby.status = "cancelled"
        for participant in self._session.scalars(
            select(MatchParticipant).where(MatchParticipant.match_id == match.id)
        ):
            if participant.status == "invited":
                participant.status = "declined"
                participant.updated_at = current
        self._session.flush()
