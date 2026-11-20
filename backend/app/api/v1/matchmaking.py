"""Endpoints de fila de matchmaking."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.matchmaking.models import Lobby, QueueEntry
from app.modules.matchmaking.service import (
    AlreadyQueued,
    DuplicateSelection,
    InvalidFormat,
    InvalidLevelOverride,
    InvalidMode,
    MatchmakingService,
    RankedRestricted,
    RegionRequired,
    SportProfileRequired,
)

router = APIRouter(prefix="/matchmaking", tags=["matchmaking"])

CourtPreference = Literal["PUBLIC_ONLY", "PRIVATE_ONLY", "ANY"]
Mode = Literal["casual", "ranked"]
Level = Literal["beginner", "intermediate", "advanced"]
DEFAULT_MODES: list[Mode] = ["casual"]


class EnqueueRequest(BaseModel):
    format_id: UUID
    court_preference: CourtPreference | None = None
    mode: Mode = "casual"


class QueueLevelOverride(BaseModel):
    """Nível explícito para uma combinação ``format_id × mode`` da seleção."""

    format_id: UUID
    mode: Mode
    level: Level


class QueueSelection(BaseModel):
    """Par explícito ``format_id × mode`` da seleção da fila.

    ``level`` é opcional: quando presente, vale para esse par e substitui o
    nível do perfil; quando ausente, usa o nível atual do perfil esportivo.
    """

    format_id: UUID
    mode: Mode
    level: Level | None = None


class QueueReplaceRequest(BaseModel):
    """Seleção completa da fila.

    Duas formas, mutuamente exclusivas:

    - legado: ``formats × modes`` (produto cartesiano), com ``levels`` opcional;
    - explícito: ``selections``, lista de pares, sem produto cartesiano.
    """

    formats: list[UUID] = Field(default_factory=list, max_length=20)
    modes: list[Mode] = Field(default_factory=lambda: list(DEFAULT_MODES), max_length=2)
    levels: list[QueueLevelOverride] = Field(default_factory=list, max_length=40)
    selections: list[QueueSelection] | None = Field(default=None, max_length=40)
    court_preference: CourtPreference | None = None

    @field_validator("formats", "modes", mode="before")
    @classmethod
    def _dedupe(cls, value: object) -> object:
        """Deduplica antes dos limites, para repetição não virar 422."""
        if isinstance(value, list):
            return list(dict.fromkeys(value))
        return value

    @field_validator("levels")
    @classmethod
    def _unique_levels(cls, value: list[QueueLevelOverride]) -> list[QueueLevelOverride]:
        """Rejeita override duplicado: a combinação precisa ser inequívoca."""
        keys = [(item.format_id, item.mode) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("override de nível duplicado para formato e modo")
        return value


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
    # ``entry`` é o campo legado (última entrada waiting/matched) e continua
    # sendo devolvido para o app atual. ``entries`` lista todas as ``waiting``;
    # ``matched`` lista as partidas encontradas ainda agendadas (lobby
    # ``scheduled``), independentemente de o usuário ter voltado para a fila.
    entry: QueueEntryResponse | None
    entries: list[QueueEntryResponse] = Field(default_factory=list)
    matched: list[QueueEntryResponse] = Field(default_factory=list)


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


def _state_response(
    session: Session,
    service: MatchmakingService,
    user_id: UUID,
) -> QueueStateResponse:
    entries = service.waiting_entries(user_id)
    latest = service.latest_entry(user_id)
    matched = service.matched_entries(user_id)
    return QueueStateResponse(
        entry=_entry_response(session, latest) if latest else None,
        entries=[_entry_response(session, entry) for entry in entries],
        matched=[_entry_response(session, entry) for entry in matched],
    )


@router.put("/queue", response_model=QueueStateResponse)
def replace_queue(
    payload: QueueReplaceRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[MatchmakingService, Depends(get_matchmaking_service)],
) -> QueueStateResponse:
    """Aplica a seleção de fila de forma atômica, preservando o que continua.

    Aceita duas formas mutuamente exclusivas: ``selections`` (lista explícita
    de pares ``format_id × mode``) ou o legado ``formats × modes``. Compara a
    seleção com as entradas ``waiting`` do usuário: par que permanece mantém a
    mesma linha (``id`` e ``created_at`` estáveis, então o tempo de espera não
    reinicia), par novo é criado e par removido é cancelado. Lista vazia cancela
    todas.
    """
    has_explicit_selection = payload.selections is not None
    if has_explicit_selection and payload.model_fields_set & {"formats", "modes", "levels"}:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "ambiguous_queue_selection")

    try:
        if payload.selections is not None:
            service.replace_targets(
                current.user_id,
                [(item.format_id, item.mode) for item in payload.selections],
                court_preference=payload.court_preference,
                levels={
                    (item.format_id, item.mode): item.level
                    for item in payload.selections
                    if item.level is not None
                },
            )
        else:
            service.replace(
                current.user_id,
                payload.formats,
                payload.modes,
                court_preference=payload.court_preference,
                levels={(item.format_id, item.mode): item.level for item in payload.levels},
            )
        session.commit()
    except DuplicateSelection:
        session.rollback()
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "duplicate_queue_selection") from None
    except InvalidMode:
        session.rollback()
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_mode") from None
    except InvalidFormat:
        session.rollback()
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_format") from None
    except InvalidLevelOverride:
        session.rollback()
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_level_override") from None
    except SportProfileRequired:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "sport_profile_required") from None
    except RegionRequired:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "region_required") from None
    except RankedRestricted:
        session.rollback()
        raise _error(status.HTTP_403_FORBIDDEN, "ranked_restricted") from None
    except IntegrityError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "queue_conflict") from None
    except Exception:
        session.rollback()
        raise
    return _state_response(session, service, current.user_id)


@router.get("/queue", response_model=QueueStateResponse)
def queue_state(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[MatchmakingService, Depends(get_matchmaking_service)],
) -> QueueStateResponse:
    """Estado atual da fila: entradas aguardando e partidas já encontradas."""
    return _state_response(session, service, current.user_id)


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
