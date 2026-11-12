"""Endpoints de fila de matchmaking."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.matchmaking.models import Lobby, QueueEntry
from app.modules.matchmaking.service import (
    AlreadyQueued,
    InvalidFormat,
    InvalidMode,
    MatchmakingService,
    RankedRestricted,
    RegionRequired,
    SportProfileRequired,
)

router = APIRouter(prefix="/matchmaking", tags=["matchmaking"])

CourtPreference = Literal["PUBLIC_ONLY", "PRIVATE_ONLY", "ANY"]
Mode = Literal["casual", "ranked"]


class EnqueueRequest(BaseModel):
    format_id: UUID
    court_preference: CourtPreference | None = None
    mode: Mode = "casual"


class LobbySummary(BaseModel):
    id: UUID
    mode: str
    court_preference: str
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    duration_minutes: int


class QueueEntryResponse(BaseModel):
    id: UUID
    format_id: UUID
    mode: str
    court_preference: str
    level: str
    status: str
    radius_km: int
    created_at: datetime
    expires_at: datetime
    lobby: LobbySummary | None


class QueueStateResponse(BaseModel):
    entry: QueueEntryResponse | None


def get_matchmaking_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MatchmakingService:
    return MatchmakingService(
        session,
        algorithm_version=settings.matchmaking_algorithm_version,
        max_radius_km=settings.matchmaking_max_radius_km,
        search_days=settings.matchmaking_search_days,
        slot_minutes=settings.matchmaking_slot_minutes,
        min_lead_minutes=settings.matchmaking_min_lead_minutes,
        queue_ttl_hours=settings.matchmaking_queue_ttl_hours,
        default_timezone=settings.default_timezone,
    )


def _error(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _entry_response(session: Session, entry: QueueEntry) -> QueueEntryResponse:
    lobby = session.get(Lobby, entry.lobby_id) if entry.lobby_id else None
    return QueueEntryResponse(
        id=entry.id,
        format_id=entry.format_id,
        mode=entry.mode,
        court_preference=entry.court_preference,
        level=entry.level,
        status=entry.status,
        radius_km=entry.radius_km,
        created_at=entry.created_at,
        expires_at=entry.expires_at,
        lobby=(
            LobbySummary(
                id=lobby.id,
                mode=lobby.mode,
                court_preference=lobby.court_preference,
                scheduled_start_at=lobby.scheduled_start_at,
                scheduled_end_at=lobby.scheduled_end_at,
                duration_minutes=lobby.duration_minutes,
            )
            if lobby is not None
            else None
        ),
    )


@router.post("/queue", response_model=QueueEntryResponse, status_code=status.HTTP_201_CREATED)
def enqueue(
    payload: EnqueueRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[MatchmakingService, Depends(get_matchmaking_service)],
) -> QueueEntryResponse:
    """Entra na fila casual ou ranqueada do formato escolhido."""
    try:
        entry = service.enqueue(
            current.user_id,
            payload.format_id,
            court_preference=payload.court_preference,
            mode=payload.mode,
        )
        session.commit()
    except InvalidMode:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_mode") from None
    except InvalidFormat:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_format") from None
    except SportProfileRequired:
        raise _error(status.HTTP_409_CONFLICT, "sport_profile_required") from None
    except RegionRequired:
        raise _error(status.HTTP_409_CONFLICT, "region_required") from None
    except AlreadyQueued:
        raise _error(status.HTTP_409_CONFLICT, "already_queued") from None
    except RankedRestricted:
        raise _error(status.HTTP_403_FORBIDDEN, "ranked_restricted") from None
    except IntegrityError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "already_queued") from None
    session.refresh(entry)
    return _entry_response(session, entry)


@router.get("/queue", response_model=QueueStateResponse)
def queue_state(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[MatchmakingService, Depends(get_matchmaking_service)],
) -> QueueStateResponse:
    """Estado atual da fila: aguardando, pareado ou vazio."""
    entry = service.latest_entry(current.user_id)
    return QueueStateResponse(entry=_entry_response(session, entry) if entry else None)


@router.delete("/queue", status_code=status.HTTP_204_NO_CONTENT)
def leave_queue(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[MatchmakingService, Depends(get_matchmaking_service)],
) -> None:
    """Sai da fila ativa."""
    if not service.leave(current.user_id):
        raise _error(status.HTTP_404_NOT_FOUND, "not_queued")
    session.commit()
