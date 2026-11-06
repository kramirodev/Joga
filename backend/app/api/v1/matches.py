"""Endpoints de consulta e ações do ciclo de partida."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.matches.models import Match, MatchParticipant
from app.modules.matches.service import (
    ActionNotAllowed,
    CheckInClosed,
    InvalidTransition,
    MatchNotFound,
    MatchService,
)
from app.modules.profile.models import UserProfile

router = APIRouter(prefix="/matches", tags=["matches"])


class MatchParticipantResponse(BaseModel):
    user_id: UUID
    display_name: str | None
    team: int
    level: str
    status: str
    is_substitute: bool
    confirmed_at: datetime | None
    checked_in_at: datetime | None


class MatchSummary(BaseModel):
    id: UUID
    lobby_id: UUID
    state: str
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    confirmation_deadline: datetime
    check_in_opens_at: datetime
    check_in_deadline: datetime
    substitution_deadline: datetime
    cancelled_reason: str | None
    my_status: str
    participants: list[MatchParticipantResponse] | None = None


class MatchListResponse(BaseModel):
    matches: list[MatchSummary]


def get_match_service(
    session: Annotated[Session, Depends(get_session)],
) -> MatchService:
    return MatchService(session)


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _status_for(session: Session, match_id: UUID, user_id: UUID) -> str:
    participant = session.scalar(
        select(MatchParticipant).where(
            MatchParticipant.match_id == match_id,
            MatchParticipant.user_id == user_id,
        )
    )
    return participant.status if participant else "unknown"


def _summary(
    session: Session,
    match: Match,
    user_id: UUID,
    *,
    with_participants: bool,
) -> MatchSummary:
    participants = None
    if with_participants:
        rows = session.scalars(
            select(MatchParticipant)
            .where(MatchParticipant.match_id == match.id)
            .order_by(MatchParticipant.team, MatchParticipant.is_substitute)
        )
        participants = []
        for row in rows:
            profile = session.get(UserProfile, row.user_id)
            participants.append(
                MatchParticipantResponse(
                    user_id=row.user_id,
                    display_name=profile.display_name if profile else None,
                    team=row.team,
                    level=row.level,
                    status=row.status,
                    is_substitute=row.is_substitute,
                    confirmed_at=row.confirmed_at,
                    checked_in_at=row.checked_in_at,
                )
            )
    return MatchSummary(
        id=match.id,
        lobby_id=match.lobby_id,
        state=match.state,
        scheduled_start_at=match.scheduled_start_at,
        scheduled_end_at=match.scheduled_end_at,
        confirmation_deadline=match.confirmation_deadline,
        check_in_opens_at=match.check_in_opens_at,
        check_in_deadline=match.check_in_deadline,
        substitution_deadline=match.substitution_deadline,
        cancelled_reason=match.cancelled_reason,
        my_status=_status_for(session, match.id, user_id),
        participants=participants,
    )


@router.get("", response_model=MatchListResponse)
def list_matches(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[MatchService, Depends(get_match_service)],
) -> MatchListResponse:
    """Partidas do usuário autenticado."""
    matches = service.list_for_user(current.user_id)
    return MatchListResponse(
        matches=[
            _summary(session, match, current.user_id, with_participants=False) for match in matches
        ]
    )


@router.get("/{match_id}", response_model=MatchSummary)
def get_match(
    match_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[MatchService, Depends(get_match_service)],
) -> MatchSummary:
    """Detalhe visível apenas para participantes."""
    try:
        match = service.get_for_user(match_id, current.user_id)
    except MatchNotFound:
        raise _error("match_not_found", status.HTTP_404_NOT_FOUND) from None
    return _summary(session, match, current.user_id, with_participants=True)


@router.post("/{match_id}/confirm", response_model=MatchSummary)
def confirm_match(
    match_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[MatchService, Depends(get_match_service)],
) -> MatchSummary:
    try:
        match = service.confirm(match_id, current.user_id)
        session.commit()
    except MatchNotFound:
        raise _error("match_not_found", status.HTTP_404_NOT_FOUND) from None
    except ActionNotAllowed:
        raise _error("action_not_allowed", status.HTTP_409_CONFLICT) from None
    except InvalidTransition:
        raise _error("invalid_transition", status.HTTP_409_CONFLICT) from None
    session.refresh(match)
    return _summary(session, match, current.user_id, with_participants=True)


@router.post("/{match_id}/decline", response_model=MatchSummary)
def decline_match(
    match_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[MatchService, Depends(get_match_service)],
) -> MatchSummary:
    try:
        match = service.decline(match_id, current.user_id)
        session.commit()
    except MatchNotFound:
        raise _error("match_not_found", status.HTTP_404_NOT_FOUND) from None
    except (ActionNotAllowed, InvalidTransition):
        raise _error("action_not_allowed", status.HTTP_409_CONFLICT) from None
    session.refresh(match)
    return _summary(session, match, current.user_id, with_participants=True)


@router.post("/{match_id}/check-in", response_model=MatchSummary)
def check_in(
    match_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[MatchService, Depends(get_match_service)],
) -> MatchSummary:
    try:
        match = service.check_in(match_id, current.user_id)
        session.commit()
    except MatchNotFound:
        raise _error("match_not_found", status.HTTP_404_NOT_FOUND) from None
    except CheckInClosed:
        raise _error("check_in_closed", status.HTTP_409_CONFLICT) from None
    except ActionNotAllowed:
        raise _error("action_not_allowed", status.HTTP_409_CONFLICT) from None
    session.refresh(match)
    return _summary(session, match, current.user_id, with_participants=True)
