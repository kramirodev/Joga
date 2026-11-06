"""Endpoints de resultado, confirmação de capitão e evidência de disputa."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.core.config import get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.idempotency import service as idempotency
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.matches.models import MatchParticipant
from app.modules.matches.service import MatchNotFound, MatchService
from app.modules.ratelimit.service import RateLimitExceeded
from app.modules.ratelimit.service import enforce as enforce_rate_limit
from app.modules.results.models import OUTCOMES, MatchDispute
from app.modules.results.service import (
    ConfirmationAlreadySubmitted,
    DisputeNotFound,
    DrawNotAllowed,
    EvidenceAlreadySubmitted,
    EvidenceEmpty,
    EvidenceNotFound,
    EvidenceTooLong,
    EvidenceWindowClosed,
    IneligibleParticipant,
    InvalidOutcome,
    InvalidRound,
    NotCaptain,
    ReportAlreadySubmitted,
    ResultsService,
    ResultWindowClosed,
    ResultWindowNotOpen,
    RoundNotOpen,
)

router = APIRouter(prefix="/matches", tags=["results"])

Outcome = str


class MyVote(BaseModel):
    outcome: str
    submitted_at: datetime


class Aggregate(BaseModel):
    valid_votes: int
    counts: dict[str, int]
    leaders: list[str]
    evaluated: str | None
    divergent: int | None
    divergence_ratio: float | None


class CaptainConfirmationView(BaseModel):
    participant_id: UUID
    team: int
    outcome: str
    submitted_at: datetime


class ReviewSummary(BaseModel):
    pending: bool
    reason: str


class ResultView(BaseModel):
    match_id: UUID
    state: str
    round: int | None
    round_status: str | None
    opens_at: datetime | None
    deadline: datetime | None
    eligible_count: int | None
    quorum: int | None
    valid_votes: int | None
    can_vote: bool
    my_vote: MyVote | None
    aggregate_visible: bool
    aggregate: Aggregate | None
    captain_confirmations_visible: bool
    captain_confirmations: list[CaptainConfirmationView] | None
    final_result: str | None
    dispute_id: UUID | None
    review: ReviewSummary | None


class ReportView(BaseModel):
    participant_id: UUID
    display_name: str | None
    outcome: str
    is_captain: bool
    submitted_at: datetime


class ReportsResponse(BaseModel):
    round: int
    status: str
    reports: list[ReportView]


class ResultSubmissionRequest(BaseModel):
    round: int
    outcome: Outcome


class ReportSubmissionResponse(BaseModel):
    report_id: UUID
    round: int
    outcome: str
    submitted_at: datetime
    effective: bool


class ConfirmationSubmissionResponse(BaseModel):
    confirmation_id: UUID
    round: int
    outcome: str
    submitted_at: datetime


class EvidenceRequest(BaseModel):
    text: str


class EvidenceSubmissionResponse(BaseModel):
    evidence_id: UUID
    char_count: int
    created_at: datetime


class EvidenceDetailResponse(BaseModel):
    evidence_id: UUID
    text: str
    char_count: int
    created_at: datetime


def get_results_service(
    session: Annotated[Session, Depends(get_session)],
) -> ResultsService:
    return ResultsService(session)


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _require_idempotency_key(value: str | None) -> str:
    if value is None or not value.strip():
        raise _error("missing_idempotency_key", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if len(value) > 120:
        raise _error("invalid_idempotency_key", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return value


def _scope(endpoint: str, user_id: UUID, match_id: UUID, round_number: int | None) -> str:
    parts = [endpoint, str(user_id), str(match_id)]
    if round_number is not None:
        parts.append(str(round_number))
    return ":".join(parts)[:200]


def _enforce_write_rate_limit(session: Session, user_id: UUID) -> None:
    """Limita POSTs de resultado por usuário em janela fixa de 60 segundos."""
    enforce_rate_limit(
        session,
        scope="results-write",
        key=str(user_id),
        limit=get_settings().results_rate_limit_per_minute,
    )


def _apply_write_rate_limit(session: Session, user_id: UUID) -> None:
    """Contabiliza a tentativa antes da ação e persiste o contador.

    O contador é commitado separadamente para que tentativas inválidas também
    consumam o limite. A ação de negócio continua em sua própria transação.
    """
    try:
        _enforce_write_rate_limit(session, user_id)
        session.commit()
    except RateLimitExceeded as exc:
        session.rollback()
        raise _handle(exc) from None
    except Exception:
        session.rollback()
        raise


def _replay(stored: idempotency.StoredResponse) -> JSONResponse:
    return JSONResponse(status_code=stored.status_code, content=stored.body)


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, MatchNotFound):
        return _error("match_not_found", status.HTTP_404_NOT_FOUND)
    if isinstance(exc, ResultWindowNotOpen):
        return _error("result_window_not_open", status.HTTP_409_CONFLICT)
    if isinstance(exc, ResultWindowClosed):
        return _error("result_window_closed", status.HTTP_409_CONFLICT)
    if isinstance(exc, RoundNotOpen):
        return _error("round_not_open", status.HTTP_409_CONFLICT)
    if isinstance(exc, IneligibleParticipant):
        return _error("ineligible_participant", status.HTTP_409_CONFLICT)
    if isinstance(exc, ReportAlreadySubmitted):
        return _error("result_report_already_submitted", status.HTTP_409_CONFLICT)
    if isinstance(exc, InvalidOutcome):
        return _error("invalid_outcome", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if isinstance(exc, DrawNotAllowed):
        return _error("draw_not_allowed", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if isinstance(exc, NotCaptain):
        return _error("not_captain", status.HTTP_403_FORBIDDEN)
    if isinstance(exc, ConfirmationAlreadySubmitted):
        return _error("captain_confirmation_already_submitted", status.HTTP_409_CONFLICT)
    if isinstance(exc, DisputeNotFound):
        return _error("dispute_not_found", status.HTTP_404_NOT_FOUND)
    if isinstance(exc, EvidenceNotFound):
        return _error("evidence_not_found", status.HTTP_404_NOT_FOUND)
    if isinstance(exc, EvidenceWindowClosed):
        return _error("evidence_window_closed", status.HTTP_409_CONFLICT)
    if isinstance(exc, EvidenceAlreadySubmitted):
        return _error("evidence_already_submitted", status.HTTP_409_CONFLICT)
    if isinstance(exc, EvidenceEmpty):
        return _error("evidence_empty", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if isinstance(exc, EvidenceTooLong):
        return _error("evidence_too_long", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if isinstance(exc, InvalidRound):
        return _error("invalid_round", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if isinstance(exc, idempotency.IdempotencyConflict):
        return _error("idempotency_conflict", status.HTTP_409_CONFLICT)
    if isinstance(exc, idempotency.IdempotencyInProgress):
        return _error("idempotency_in_progress", status.HTTP_409_CONFLICT)
    if isinstance(exc, RateLimitExceeded):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited"},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )
    raise exc


@router.get("/{match_id}/result", response_model=ResultView)
def get_result(
    match_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[ResultsService, Depends(get_results_service)],
) -> ResultView:
    """Estado da rodada atual; agregado somente após o fechamento."""
    try:
        match = MatchService(session).get_for_user(match_id, current.user_id)
    except MatchNotFound:
        raise _error("match_not_found", status.HTTP_404_NOT_FOUND) from None

    round_row = service.current_round(match.id)
    if round_row is None:
        return ResultView(
            match_id=match.id,
            state=match.state,
            round=None,
            round_status=None,
            opens_at=None,
            deadline=None,
            eligible_count=None,
            quorum=None,
            valid_votes=None,
            can_vote=False,
            my_vote=None,
            aggregate_visible=False,
            aggregate=None,
            captain_confirmations_visible=False,
            captain_confirmations=None,
            final_result=match.final_result,
            dispute_id=None,
            review=None,
        )

    now = utcnow()
    votes = service.effective_votes(round_row)
    my_report = service.my_vote(round_row, current.user_id)
    eligible = service.eligible_for_user(match.id, current.user_id)
    can_vote = bool(
        eligible
        and round_row.status == "OPEN"
        and match.state == "RESULT_PENDING"
        and now <= ensure_utc(round_row.deadline)
        and (round_row.round_number == 2 or my_report is None)
    )

    aggregate = None
    confirmations = None
    closed = round_row.status == "CLOSED"
    if closed:
        counts = service.counts_for(round_row)
        leaders = _leaders(counts)
        ratio = None
        if round_row.divergent_votes is not None and round_row.valid_votes:
            ratio = round_row.divergent_votes / round_row.valid_votes
        aggregate = Aggregate(
            valid_votes=round_row.valid_votes or 0,
            counts=counts,
            leaders=leaders,
            evaluated=round_row.evaluated_outcome,
            divergent=round_row.divergent_votes,
            divergence_ratio=ratio,
        )
        confirmations = [
            CaptainConfirmationView(
                participant_id=row.participant_id,
                team=_team_for(session, row.participant_id),
                outcome=row.outcome,
                submitted_at=row.submitted_at,
            )
            for row in service.captain_confirmations(round_row)
        ]

    dispute: MatchDispute | None = service.latest_open_dispute(match.id)
    review = service.pending_review(match.id)

    return ResultView(
        match_id=match.id,
        state=match.state,
        round=round_row.round_number,
        round_status=round_row.status,
        opens_at=round_row.opens_at,
        deadline=round_row.deadline,
        eligible_count=round_row.eligible_count,
        quorum=round_row.quorum,
        valid_votes=round_row.valid_votes if closed else len(votes),
        can_vote=can_vote,
        my_vote=(
            MyVote(outcome=my_report.outcome, submitted_at=my_report.submitted_at)
            if my_report is not None
            else None
        ),
        aggregate_visible=closed,
        aggregate=aggregate,
        captain_confirmations_visible=closed,
        captain_confirmations=confirmations,
        final_result=match.final_result,
        dispute_id=dispute.id if dispute is not None else None,
        review=(ReviewSummary(pending=True, reason=review.reason) if review is not None else None),
    )


@router.get("/{match_id}/result-reports", response_model=ReportsResponse)
def list_result_reports(
    match_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[ResultsService, Depends(get_results_service)],
    round_number: Annotated[int | None, Query(alias="round")] = None,
) -> ReportsResponse:
    """Votos efetivos por participante; histórico de correções não é exposto."""
    try:
        match = MatchService(session).get_for_user(match_id, current.user_id)
    except MatchNotFound:
        raise _error("match_not_found", status.HTTP_404_NOT_FOUND) from None

    if round_number is not None and round_number not in (1, 2):
        raise _error("invalid_round", status.HTTP_422_UNPROCESSABLE_CONTENT)

    round_row = (
        service.round_by_number(match.id, round_number)
        if round_number is not None
        else service.current_round(match.id)
    )
    if round_row is None:
        raise _error("invalid_round", status.HTTP_422_UNPROCESSABLE_CONTENT)

    reports: list[ReportView] = []
    for participant_id, report in service.effective_votes(round_row).items():
        participant = session.get(MatchParticipant, participant_id)
        if participant is None:
            continue
        reports.append(
            ReportView(
                participant_id=participant_id,
                display_name=service.display_name(participant.user_id),
                outcome=report.outcome,
                is_captain=participant.is_captain,
                submitted_at=report.submitted_at,
            )
        )
    reports.sort(key=lambda item: (item.submitted_at, str(item.participant_id)))
    return ReportsResponse(
        round=round_row.round_number,
        status=round_row.status,
        reports=reports,
    )


@router.post(
    "/{match_id}/result-reports",
    response_model=ReportSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_result_report(
    match_id: UUID,
    payload: ResultSubmissionRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[ResultsService, Depends(get_results_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReportSubmissionResponse | JSONResponse:
    key = _require_idempotency_key(idempotency_key)
    scope = _scope("result-report", current.user_id, match_id, payload.round)
    request_hash = idempotency.payload_hash({"round": payload.round, "outcome": payload.outcome})
    _apply_write_rate_limit(session, current.user_id)
    try:
        stored = idempotency.begin(session, scope=scope, key=key, request_hash=request_hash)
    except (idempotency.IdempotencyConflict, idempotency.IdempotencyInProgress) as exc:
        session.rollback()
        raise _handle(exc) from None
    if stored is not None:
        return _replay(stored)

    try:
        report = service.submit_report(
            match_id=match_id,
            user_id=current.user_id,
            round_number=payload.round,
            outcome=payload.outcome,
            idempotency_key=key,
            request_hash=request_hash,
        )
        response = ReportSubmissionResponse(
            report_id=report.id,
            round=payload.round,
            outcome=report.outcome,
            submitted_at=report.submitted_at,
            effective=True,
        )
        idempotency.finish(
            session,
            scope=scope,
            key=key,
            status_code=status.HTTP_201_CREATED,
            body=response.model_dump(mode="json"),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001 - convertido para erro de negócio
        session.rollback()
        raise _handle(exc) from None
    return response


@router.post(
    "/{match_id}/result-confirmations",
    response_model=ConfirmationSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_result_confirmation(
    match_id: UUID,
    payload: ResultSubmissionRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[ResultsService, Depends(get_results_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ConfirmationSubmissionResponse | JSONResponse:
    """Confirmação do capitão; não conta como voto adicional."""
    key = _require_idempotency_key(idempotency_key)
    scope = _scope("result-confirmation", current.user_id, match_id, payload.round)
    request_hash = idempotency.payload_hash({"round": payload.round, "outcome": payload.outcome})
    _apply_write_rate_limit(session, current.user_id)
    try:
        stored = idempotency.begin(session, scope=scope, key=key, request_hash=request_hash)
    except (idempotency.IdempotencyConflict, idempotency.IdempotencyInProgress) as exc:
        session.rollback()
        raise _handle(exc) from None
    if stored is not None:
        return _replay(stored)

    try:
        confirmation = service.submit_confirmation(
            match_id=match_id,
            user_id=current.user_id,
            round_number=payload.round,
            outcome=payload.outcome,
            idempotency_key=key,
            request_hash=request_hash,
        )
        response = ConfirmationSubmissionResponse(
            confirmation_id=confirmation.id,
            round=payload.round,
            outcome=confirmation.outcome,
            submitted_at=confirmation.submitted_at,
        )
        idempotency.finish(
            session,
            scope=scope,
            key=key,
            status_code=status.HTTP_201_CREATED,
            body=response.model_dump(mode="json"),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return response


@router.post(
    "/{match_id}/disputes/{dispute_id}/evidence",
    response_model=EvidenceSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_evidence(
    match_id: UUID,
    dispute_id: UUID,
    payload: EvidenceRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[ResultsService, Depends(get_results_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> EvidenceSubmissionResponse | JSONResponse:
    key = _require_idempotency_key(idempotency_key)
    scope = _scope("dispute-evidence", current.user_id, match_id, None) + f":{dispute_id}"
    request_hash = idempotency.payload_hash({"text": payload.text})
    _apply_write_rate_limit(session, current.user_id)
    try:
        stored = idempotency.begin(session, scope=scope, key=key, request_hash=request_hash)
    except (idempotency.IdempotencyConflict, idempotency.IdempotencyInProgress) as exc:
        session.rollback()
        raise _handle(exc) from None
    if stored is not None:
        return _replay(stored)

    try:
        evidence = service.submit_evidence(
            match_id=match_id,
            dispute_id=dispute_id,
            user_id=current.user_id,
            text=payload.text,
            idempotency_key=key,
            request_hash=request_hash,
        )
        response = EvidenceSubmissionResponse(
            evidence_id=evidence.id,
            char_count=evidence.char_count,
            created_at=evidence.created_at,
        )
        idempotency.finish(
            session,
            scope=scope,
            key=key,
            status_code=status.HTTP_201_CREATED,
            body=response.model_dump(mode="json"),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return response


@router.get(
    "/{match_id}/disputes/{dispute_id}/evidence/me",
    response_model=EvidenceDetailResponse,
)
def get_my_evidence(
    match_id: UUID,
    dispute_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[ResultsService, Depends(get_results_service)],
) -> EvidenceDetailResponse:
    try:
        evidence = service.get_evidence(
            match_id=match_id,
            dispute_id=dispute_id,
            user_id=current.user_id,
        )
    except (MatchNotFound, DisputeNotFound, EvidenceNotFound) as exc:
        raise _handle(exc) from None
    return EvidenceDetailResponse(
        evidence_id=evidence.id,
        text=evidence.text,
        char_count=evidence.char_count,
        created_at=evidence.created_at,
    )


def _leaders(counts: dict[str, int]) -> list[str]:
    if not counts or max(counts.values()) == 0:
        return []
    top = max(counts.values())
    return [outcome for outcome in OUTCOMES if counts.get(outcome) == top]


def _team_for(session: Session, participant_id: UUID) -> int:
    participant = session.get(MatchParticipant, participant_id)
    return participant.team if participant is not None else 0
