"""Aplicação idempotente de MMR e registro de sinais de confiança."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.matches.models import Match, MatchParticipant
from app.modules.matches.service import MatchNotFound
from app.modules.matchmaking.models import Lobby
from app.modules.profile.models import UserProfile
from app.modules.ratings.engine import (
    DEFAULT_RATING,
    DEFAULT_RATING_DEVIATION,
    DEFAULT_VOLATILITY,
    PLACEMENT_MATCHES,
    RatingState,
    rate_match,
)
from app.modules.ratings.models import (
    ALGORITHM_VERSION,
    RatingAccount,
    RatingEvent,
    TrustAccount,
    TrustEvent,
)


class RatingNotApplicable(Exception):
    """Partida ou lobby não gera rating."""


@dataclass(frozen=True)
class RatingApplicationResult:
    match_id: uuid.UUID
    applied: int
    already_applied: bool = False


class RatingService:
    """Aplica rating uma única vez por partida/usuário/versão."""

    def __init__(self, session: Session, *, algorithm_version: str = ALGORITHM_VERSION) -> None:
        self._session = session
        self._algorithm_version = algorithm_version

    def pending_match_ids(self, *, limit: int = 100) -> list[uuid.UUID]:
        """Partidas ranqueadas finalizadas que ainda não têm eventos de rating."""
        if limit <= 0:
            raise ValueError("limit deve ser positivo")

        already_rated = (
            select(RatingEvent.id)
            .where(
                RatingEvent.match_id == Match.id,
                RatingEvent.algorithm_version == self._algorithm_version,
            )
            .exists()
        )
        statement = (
            select(Match.id)
            .join(Lobby, Lobby.id == Match.lobby_id)
            .where(
                Match.state == "FINALIZED",
                Lobby.mode == "ranked",
                ~already_rated,
            )
            .order_by(Match.finalized_at, Match.id)
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def apply_match(
        self,
        match_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> RatingApplicationResult:
        """Aplica MMR à partida; reexecução não duplica eventos."""
        moment = ensure_utc(now or utcnow())
        match = self._session.get(
            Match,
            match_id,
            with_for_update=True,
            populate_existing=True,
        )
        if match is None:
            raise MatchNotFound("partida não encontrada")
        if match.state != "FINALIZED" or match.final_result not in (
            "TEAM_1",
            "TEAM_2",
            "DRAW",
        ):
            raise RatingNotApplicable("partida não está finalizada")

        lobby = self._session.get(Lobby, match.lobby_id)
        if lobby is None or lobby.mode != "ranked":
            raise RatingNotApplicable("partida não é ranqueada")

        existing = self._session.scalar(
            select(func.count())
            .select_from(RatingEvent)
            .where(
                RatingEvent.match_id == match.id,
                RatingEvent.algorithm_version == self._algorithm_version,
            )
        )
        if (existing or 0) > 0:
            return RatingApplicationResult(
                match_id=match.id,
                applied=0,
                already_applied=True,
            )

        participants = list(
            self._session.scalars(
                select(MatchParticipant)
                .where(
                    MatchParticipant.match_id == match.id,
                    MatchParticipant.status == "checked_in",
                )
                .order_by(MatchParticipant.team, MatchParticipant.id)
            )
        )
        team_1 = [participant for participant in participants if participant.team == 1]
        team_2 = [participant for participant in participants if participant.team == 2]
        if not team_1 or not team_2:
            raise RatingNotApplicable("partida sem equipes completas")

        accounts = {
            participant.user_id: self._account_for(
                participant.user_id,
                lobby.format_id,
                moment,
            )
            for participant in participants
        }
        states = {
            user_id: RatingState(
                rating=account.rating,
                rating_deviation=account.rating_deviation,
                volatility=account.volatility,
                matches_played=account.matches_played,
                last_rated_at=account.last_rated_at,
            )
            for user_id, account in accounts.items()
        }

        updates = rate_match(
            [states[participant.user_id] for participant in team_1],
            [states[participant.user_id] for participant in team_2],
            result=match.final_result,
            now=moment,
        )
        update_by_user = {
            participant.user_id: update
            for participant, update in zip(participants, updates, strict=True)
        }

        applied = 0
        for participant in participants:
            account = accounts[participant.user_id]
            update = update_by_user[participant.user_id]
            account.rating = update.rating_after
            account.rating_deviation = update.rating_deviation_after
            account.volatility = update.volatility_after
            account.matches_played += 1
            account.last_rated_at = moment
            account.algorithm_version = self._algorithm_version
            self._session.add(
                RatingEvent(
                    match_id=match.id,
                    user_id=participant.user_id,
                    format_id=lobby.format_id,
                    algorithm_version=self._algorithm_version,
                    result=update.result,
                    expected_score=update.expected_score,
                    rating_before=update.rating_before,
                    rating_after=update.rating_after,
                    rating_deviation_before=update.rating_deviation_before,
                    rating_deviation_after=update.rating_deviation_after,
                    volatility_before=update.volatility_before,
                    volatility_after=update.volatility_after,
                    delta=update.delta,
                    created_at=moment,
                )
            )
            applied += 1

        self._session.flush()
        return RatingApplicationResult(match_id=match.id, applied=applied)

    def record_trust_event(
        self,
        user_id: uuid.UUID,
        event_type: str,
        *,
        match_id: uuid.UUID | None = None,
        severity: int = 0,
        details: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> TrustEvent:
        """Registra sinal auditável sem alterar o score automaticamente."""
        if severity < 0 or severity > 5:
            raise ValueError("severity deve estar entre 0 e 5")
        moment = ensure_utc(now or utcnow())
        account = self._session.get(TrustAccount, user_id, with_for_update=True)
        if account is None:
            account = TrustAccount(user_id=user_id, score=100, updated_at=moment)
            try:
                with self._session.begin_nested():
                    self._session.add(account)
                    self._session.flush()
            except IntegrityError:
                account = self._session.get(
                    TrustAccount,
                    user_id,
                    with_for_update=True,
                )
                if account is None:
                    raise

        event = TrustEvent(
            user_id=user_id,
            match_id=match_id,
            event_type=event_type,
            severity=severity,
            details=details,
            created_at=moment,
        )
        self._session.add(event)
        account.updated_at = moment
        self._session.flush()
        return event

    def account_for(
        self,
        user_id: uuid.UUID,
        format_id: uuid.UUID,
    ) -> RatingAccount | None:
        return self._session.scalar(
            select(RatingAccount).where(
                RatingAccount.user_id == user_id,
                RatingAccount.format_id == format_id,
            )
        )

    def position_for(self, account: RatingAccount) -> int | None:
        """Posição no ranking, considerando apenas contas já colocadas."""
        if account.matches_played < PLACEMENT_MATCHES:
            return None
        higher = self._session.scalar(
            select(func.count())
            .select_from(RatingAccount)
            .where(
                RatingAccount.format_id == account.format_id,
                RatingAccount.matches_played >= PLACEMENT_MATCHES,
                or_(
                    RatingAccount.rating > account.rating,
                    and_(
                        RatingAccount.rating == account.rating,
                        RatingAccount.user_id < account.user_id,
                    ),
                ),
            )
        )
        return int(higher or 0) + 1

    def leaderboard(
        self,
        format_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[RatingAccount, str | None]], int]:
        """Top de contas colocadas, com nome de exibição."""
        if limit <= 0 or offset < 0:
            raise ValueError("paginação inválida")
        filters = (
            RatingAccount.format_id == format_id,
            RatingAccount.matches_played >= PLACEMENT_MATCHES,
        )
        total = int(
            self._session.scalar(select(func.count()).select_from(RatingAccount).where(*filters))
            or 0
        )
        rows = self._session.execute(
            select(RatingAccount, UserProfile.display_name)
            .outerjoin(UserProfile, UserProfile.user_id == RatingAccount.user_id)
            .where(*filters)
            .order_by(
                RatingAccount.rating.desc(),
                RatingAccount.matches_played.desc(),
                RatingAccount.user_id,
            )
            .limit(limit)
            .offset(offset)
        )
        return [(account, display_name) for account, display_name in rows], total

    def _account_for(
        self,
        user_id: uuid.UUID,
        format_id: uuid.UUID,
        moment: datetime,
    ) -> RatingAccount:
        account = self._session.scalar(
            select(RatingAccount)
            .where(
                RatingAccount.user_id == user_id,
                RatingAccount.format_id == format_id,
            )
            .with_for_update()
        )
        if account is not None:
            return account

        account = RatingAccount(
            user_id=user_id,
            format_id=format_id,
            rating=DEFAULT_RATING,
            rating_deviation=DEFAULT_RATING_DEVIATION,
            volatility=DEFAULT_VOLATILITY,
            matches_played=0,
            last_rated_at=None,
            algorithm_version=self._algorithm_version,
            created_at=moment,
            updated_at=moment,
        )
        try:
            with self._session.begin_nested():
                self._session.add(account)
                self._session.flush()
        except IntegrityError:
            account = self._session.scalar(
                select(RatingAccount)
                .where(
                    RatingAccount.user_id == user_id,
                    RatingAccount.format_id == format_id,
                )
                .with_for_update()
            )
            if account is None:
                raise
        return account
