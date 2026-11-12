"""Endpoints de fila de substitutos e cancelamento individual (ADR 0039)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.bookings.models import BookingSubstitution
from app.modules.bookings.service import BookingNotFound
from app.modules.bookings.substitutions import (
    BookingSubstitutionService,
    CancellationClosed,
    LobbyNotFound,
    LobbySubstituteService,
    ParticipantNotFound,
    QueueConflict,
    QueueForbidden,
    SubstituteIneligible,
    SubstitutionConflict,
    SubstitutionForbidden,
    SubstitutionNotFound,
)
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.matchmaking.models import LobbySubstitute

router = APIRouter(tags=["substitutions"])


class SubstituteView(BaseModel):
    id: UUID
    lobby_id: UUID
    user_id: UUID
    status: str
    position: int
    called_at: datetime | None
    confirmed_at: datetime | None
    played_at: datetime | None
    created_at: datetime


class SubstituteListResponse(BaseModel):
    substitutes: list[SubstituteView]
    count: int


class AssignSubstituteRequest(BaseModel):
    substitute_user_id: UUID


class NoShowRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


class SubstitutionView(BaseModel):
    id: UUID
    booking_id: UUID
    seat: int
    outgoing_user_id: UUID
    filled_by_user_id: UUID | None
    substitute_payment_id: UUID | None
    covered_by_payment_id: UUID | None
    called_user_id: UUID | None
    call_deadline_at: datetime | None
    call_attempts: int
    paid_seat: bool
    status: str
    deadline_at: datetime
    resolved_at: datetime | None
    reason: str | None
    created_at: datetime


class SubstitutionListResponse(BaseModel):
    substitutions: list[SubstitutionView]


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _substitute_view(item: LobbySubstitute) -> SubstituteView:
    return SubstituteView(
        id=item.id,
        lobby_id=item.lobby_id,
        user_id=item.user_id,
        status=item.status,
        position=item.position,
        called_at=item.called_at,
        confirmed_at=item.confirmed_at,
        played_at=item.played_at,
        created_at=item.created_at,
    )


def _substitution_view(item: BookingSubstitution) -> SubstitutionView:
    return SubstitutionView(
        id=item.id,
        booking_id=item.booking_id,
        seat=item.seat,
        outgoing_user_id=item.outgoing_user_id,
        filled_by_user_id=item.filled_by_user_id,
        substitute_payment_id=item.substitute_payment_id,
        covered_by_payment_id=item.covered_by_payment_id,
        called_user_id=item.called_user_id,
        call_deadline_at=item.call_deadline_at,
        call_attempts=item.call_attempts,
        paid_seat=item.paid_seat,
        status=item.status,
        deadline_at=item.deadline_at,
        resolved_at=item.resolved_at,
        reason=item.reason,
        created_at=item.created_at,
    )


@router.post(
    "/lobbies/{lobby_id}/substitutes",
    response_model=SubstituteView,
    status_code=http_status.HTTP_201_CREATED,
)
def join_substitute_queue(
    lobby_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> SubstituteView:
    try:
        substitute = LobbySubstituteService(session).join(current.user_id, lobby_id)
        session.commit()
    except LobbyNotFound as exc:
        session.rollback()
        raise _error("lobby_not_found", http_status.HTTP_404_NOT_FOUND) from exc
    except QueueConflict as exc:
        session.rollback()
        raise _error(str(exc), http_status.HTTP_409_CONFLICT) from exc
    return _substitute_view(substitute)


@router.delete("/lobbies/{lobby_id}/substitutes", status_code=http_status.HTTP_204_NO_CONTENT)
def leave_substitute_queue(
    lobby_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    try:
        LobbySubstituteService(session).leave(current.user_id, lobby_id)
        session.commit()
    except QueueConflict as exc:
        session.rollback()
        raise _error(str(exc), http_status.HTTP_409_CONFLICT) from exc


@router.get(
    "/lobbies/{lobby_id}/substitutes",
    response_model=SubstituteListResponse,
)
def list_substitute_queue(
    lobby_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> SubstituteListResponse:
    try:
        substitutes = LobbySubstituteService(session).list_for_lobby(current.user_id, lobby_id)
    except QueueForbidden as exc:
        raise _error("forbidden", http_status.HTTP_403_FORBIDDEN) from exc
    return SubstituteListResponse(
        substitutes=[_substitute_view(item) for item in substitutes],
        count=len(substitutes),
    )


@router.post(
    "/bookings/{booking_id}/participant-cancellations",
    response_model=SubstitutionView,
    status_code=http_status.HTTP_201_CREATED,
)
def cancel_participant(
    booking_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> SubstitutionView:
    try:
        substitution = BookingSubstitutionService(session).cancel_participant(
            current.user_id, booking_id
        )
        session.commit()
    except BookingNotFound as exc:
        session.rollback()
        raise _error("booking_not_found", http_status.HTTP_404_NOT_FOUND) from exc
    except ParticipantNotFound as exc:
        session.rollback()
        raise _error("participant_not_found", http_status.HTTP_404_NOT_FOUND) from exc
    except (CancellationClosed, SubstitutionConflict) as exc:
        session.rollback()
        raise _error(str(exc), http_status.HTTP_409_CONFLICT) from exc
    return _substitution_view(substitution)


@router.post(
    "/bookings/{booking_id}/participants/{user_id}/no-show",
    response_model=SubstitutionView,
    status_code=http_status.HTTP_201_CREATED,
)
def mark_no_show(
    booking_id: UUID,
    user_id: UUID,
    payload: NoShowRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> SubstitutionView:
    try:
        substitution = BookingSubstitutionService(session).mark_no_show(
            current.user_id,
            booking_id,
            user_id,
            reason=payload.reason,
        )
        session.commit()
    except (BookingNotFound, ParticipantNotFound) as exc:
        session.rollback()
        raise _error("participant_not_found", http_status.HTTP_404_NOT_FOUND) from exc
    except SubstitutionForbidden as exc:
        session.rollback()
        raise _error("forbidden", http_status.HTTP_403_FORBIDDEN) from exc
    except SubstitutionConflict as exc:
        session.rollback()
        raise _error(str(exc), http_status.HTTP_409_CONFLICT) from exc
    return _substitution_view(substitution)


@router.post(
    "/bookings/{booking_id}/substitutions/{substitution_id}/assign",
    response_model=SubstitutionView,
)
def assign_substitute(
    booking_id: UUID,
    substitution_id: UUID,
    payload: AssignSubstituteRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> SubstitutionView:
    try:
        substitution = BookingSubstitutionService(session).assign(
            current.user_id,
            booking_id,
            substitution_id,
            payload.substitute_user_id,
        )
        session.commit()
    except (BookingNotFound, SubstitutionNotFound) as exc:
        session.rollback()
        raise _error("substitution_not_found", http_status.HTTP_404_NOT_FOUND) from exc
    except SubstitutionForbidden as exc:
        session.rollback()
        raise _error("forbidden", http_status.HTTP_403_FORBIDDEN) from exc
    except (SubstitutionConflict, SubstituteIneligible) as exc:
        session.rollback()
        raise _error(str(exc), http_status.HTTP_409_CONFLICT) from exc
    return _substitution_view(substitution)


@router.post(
    "/bookings/{booking_id}/substitutions/{substitution_id}/accept",
    response_model=SubstitutionView,
)
def accept_call(
    booking_id: UUID,
    substitution_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> SubstitutionView:
    try:
        substitution = BookingSubstitutionService(session).accept_call(
            current.user_id, booking_id, substitution_id
        )
        session.commit()
    except (BookingNotFound, SubstitutionNotFound) as exc:
        session.rollback()
        raise _error("substitution_not_found", http_status.HTTP_404_NOT_FOUND) from exc
    except SubstitutionForbidden as exc:
        session.rollback()
        raise _error("forbidden", http_status.HTTP_403_FORBIDDEN) from exc
    except (SubstitutionConflict, SubstituteIneligible) as exc:
        session.rollback()
        raise _error(str(exc), http_status.HTTP_409_CONFLICT) from exc
    return _substitution_view(substitution)


@router.post(
    "/bookings/{booking_id}/substitutions/{substitution_id}/decline",
    response_model=SubstitutionView,
)
def decline_call(
    booking_id: UUID,
    substitution_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> SubstitutionView:
    try:
        substitution = BookingSubstitutionService(session).decline_call(
            current.user_id, booking_id, substitution_id
        )
        session.commit()
    except (BookingNotFound, SubstitutionNotFound) as exc:
        session.rollback()
        raise _error("substitution_not_found", http_status.HTTP_404_NOT_FOUND) from exc
    except SubstitutionForbidden as exc:
        session.rollback()
        raise _error("forbidden", http_status.HTTP_403_FORBIDDEN) from exc
    return _substitution_view(substitution)


@router.get(
    "/bookings/{booking_id}/substitutions",
    response_model=SubstitutionListResponse,
)
def list_substitutions(
    booking_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> SubstitutionListResponse:
    try:
        substitutions = BookingSubstitutionService(session).list_for_booking(
            current.user_id, booking_id
        )
    except BookingNotFound as exc:
        raise _error("booking_not_found", http_status.HTTP_404_NOT_FOUND) from exc
    return SubstitutionListResponse(
        substitutions=[_substitution_view(item) for item in substitutions]
    )
