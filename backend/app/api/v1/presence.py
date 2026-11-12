"""Endpoints de pré-check-in e presença no local (ADR 0039)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.bookings.models import BookingParticipant
from app.modules.bookings.presence import (
    BookingPresenceService,
    PresenceClosed,
    PresenceForbidden,
    PresenceInvalid,
    PresenceWindowError,
)
from app.modules.bookings.service import BookingNotFound
from app.modules.bookings.substitutions import ParticipantNotFound
from app.modules.identity.sessions import AuthenticatedSession

router = APIRouter(tags=["presence"])


class PresenceConfirmRequest(BaseModel):
    target_user_id: UUID | None = None
    method: Literal["GPS", "VENUE"]
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_m: int | None = Field(default=None, ge=0, le=5000)


class PresenceView(BaseModel):
    user_id: UUID
    seat: int
    active: bool
    pre_checked_in_at: datetime | None
    status: str
    method: str | None
    confirmed_at: datetime | None
    distance_m: int | None
    accuracy_m: int | None


class PresenceListResponse(BaseModel):
    participants: list[PresenceView]


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _view(item: BookingParticipant) -> PresenceView:
    return PresenceView(
        user_id=item.user_id,
        seat=item.seat,
        active=item.active,
        pre_checked_in_at=item.pre_checked_in_at,
        status=item.presence_status,
        method=item.presence_method,
        confirmed_at=item.presence_confirmed_at,
        distance_m=item.presence_distance_m,
        accuracy_m=item.presence_accuracy_m,
    )


@router.post(
    "/bookings/{booking_id}/pre-check-in",
    response_model=PresenceView,
)
def pre_check_in(
    booking_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PresenceView:
    try:
        participant = BookingPresenceService(session).pre_check_in(current.user_id, booking_id)
        session.commit()
    except BookingNotFound as exc:
        session.rollback()
        raise _error("booking_not_found", http_status.HTTP_404_NOT_FOUND) from exc
    except PresenceForbidden as exc:
        session.rollback()
        raise _error("forbidden", http_status.HTTP_403_FORBIDDEN) from exc
    except (PresenceWindowError, PresenceInvalid) as exc:
        session.rollback()
        code = exc.args[0] if exc.args else "presence_window_closed"
        raise _error(str(code), http_status.HTTP_409_CONFLICT) from exc
    return _view(participant)


@router.post(
    "/bookings/{booking_id}/presence",
    response_model=PresenceView,
)
def confirm_presence(
    booking_id: UUID,
    payload: PresenceConfirmRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PresenceView:
    target = payload.target_user_id or current.user_id
    try:
        participant = BookingPresenceService(session).confirm(
            current.user_id,
            booking_id,
            target,
            method=payload.method,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy_m=payload.accuracy_m,
        )
        session.commit()
    except BookingNotFound as exc:
        session.rollback()
        raise _error("booking_not_found", http_status.HTTP_404_NOT_FOUND) from exc
    except ParticipantNotFound as exc:
        session.rollback()
        raise _error("participant_not_found", http_status.HTTP_404_NOT_FOUND) from exc
    except PresenceForbidden as exc:
        session.rollback()
        raise _error("forbidden", http_status.HTTP_403_FORBIDDEN) from exc
    except PresenceClosed as exc:
        session.rollback()
        raise _error("presence_closed", http_status.HTTP_409_CONFLICT) from exc
    except (PresenceWindowError, PresenceInvalid) as exc:
        session.rollback()
        code = exc.args[0] if exc.args else "presence_window_closed"
        raise _error(str(code), http_status.HTTP_409_CONFLICT) from exc
    return _view(participant)


@router.get(
    "/bookings/{booking_id}/presence",
    response_model=PresenceListResponse,
)
def list_presence(
    booking_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PresenceListResponse:
    try:
        participants = BookingPresenceService(session).list_presence(current.user_id, booking_id)
    except BookingNotFound as exc:
        raise _error("booking_not_found", http_status.HTTP_404_NOT_FOUND) from exc
    return PresenceListResponse(participants=[_view(item) for item in participants])
