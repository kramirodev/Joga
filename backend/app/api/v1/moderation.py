"""Denúncias e medidas de moderação do jogador (Fase 17A)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.moderation.models import (
    ModerationAction,
    ModerationAppeal,
    ModerationOperator,
    ModerationReport,
)
from app.modules.moderation.service import (
    ActionNotFound,
    AppealConflict,
    ModerationService,
    OperatorNotAuthorized,
    ReportConflict,
    ReportForbidden,
    ReportInvalid,
    ReportNotFound,
)

router = APIRouter(prefix="/moderation", tags=["moderation"])


@dataclass(frozen=True)
class ModeratorContext:
    user_id: UUID
    role: str


def get_moderator(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ModeratorContext:
    role = ModerationService(session).operator_role(current.user_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "moderator_required"},
        )
    return ModeratorContext(user_id=current.user_id, role=role)


def require_admin(
    moderator: Annotated[ModeratorContext, Depends(get_moderator)],
) -> ModeratorContext:
    if moderator.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "admin_required"},
        )
    return moderator


class ReportCreate(BaseModel):
    target_user_id: UUID
    lobby_id: UUID
    category: str = Field(pattern="^(HARASSMENT|HATE|THREAT|SEXUAL|SPAM|OTHER)$")
    description: str = Field(min_length=1, max_length=2000)
    message_ids: list[UUID] = Field(default_factory=list, max_length=5)


class ReportView(BaseModel):
    id: UUID
    category: str
    status: str
    severity: str
    priority: int
    created_at: datetime
    reviewed_at: datetime | None
    decision_reason: str | None


class ReportListResponse(BaseModel):
    reports: list[ReportView]


class ActionView(BaseModel):
    id: UUID
    action_type: str
    status: str
    starts_at: datetime
    ends_at: datetime | None
    reason: str
    created_at: datetime
    revoked_at: datetime | None


class ActionListResponse(BaseModel):
    actions: list[ActionView]


class AppealCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class AppealView(BaseModel):
    id: UUID
    action_id: UUID
    status: str
    reason: str
    created_at: datetime
    decided_at: datetime | None
    decision_reason: str | None


def _report_view(item: ModerationReport) -> ReportView:
    return ReportView(
        id=item.id,
        category=item.category,
        status=item.status,
        severity=item.severity,
        priority=item.priority,
        created_at=item.created_at,
        reviewed_at=item.reviewed_at,
        decision_reason=item.decision_reason,
    )


def _action_view(item: ModerationAction) -> ActionView:
    return ActionView(
        id=item.id,
        action_type=item.action_type,
        status=item.status,
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        reason=item.reason,
        created_at=item.created_at,
        revoked_at=item.revoked_at,
    )


def _appeal_view(item: ModerationAppeal) -> AppealView:
    return AppealView(
        id=item.id,
        action_id=item.action_id,
        status=item.status,
        reason=item.reason,
        created_at=item.created_at,
        decided_at=item.decided_at,
        decision_reason=item.decision_reason,
    )


class ModeratorView(BaseModel):
    user_id: UUID
    role: str


class AdminReportView(ReportView):
    reporter_id: UUID
    target_user_id: UUID
    lobby_id: UUID
    description: str
    context: list[dict[str, Any]]
    classifier_version: str
    classifier_signals: dict[str, Any] | None
    reviewed_by: str | None


class QueueResponse(BaseModel):
    reports: list[AdminReportView]
    stats: dict[str, int]


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(DISMISS|WARN|RESTRICT_RANKED|SUSPEND_TEMP)$")
    reason: str = Field(min_length=1, max_length=1000)
    days: int = Field(default=7, ge=1, le=90)


class AppealDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(ACCEPTED|REJECTED)$")
    reason: str = Field(min_length=1, max_length=1000)


class OperatorCreate(BaseModel):
    user_id: UUID
    role: str = Field(default="MODERATOR", pattern="^(ADMIN|MODERATOR)$")


class OperatorView(BaseModel):
    user_id: UUID
    role: str
    active: bool
    created_at: datetime
    deactivated_at: datetime | None


def _admin_report_view(item: ModerationReport) -> AdminReportView:
    return AdminReportView(
        id=item.id,
        category=item.category,
        status=item.status,
        severity=item.severity,
        priority=item.priority,
        created_at=item.created_at,
        reviewed_at=item.reviewed_at,
        decision_reason=item.decision_reason,
        reporter_id=item.reporter_id,
        target_user_id=item.target_user_id,
        lobby_id=item.lobby_id,
        description=item.description,
        context=item.context or [],
        classifier_version=item.classifier_version,
        classifier_signals=item.classifier_signals,
        reviewed_by=item.reviewed_by,
    )


def _operator_view(item: ModerationOperator) -> OperatorView:
    return OperatorView(
        user_id=item.user_id,
        role=item.role,
        active=item.active,
        created_at=item.created_at,
        deactivated_at=item.deactivated_at,
    )


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, (ReportNotFound, ActionNotFound)):
        return _error("not_found", status.HTTP_404_NOT_FOUND)
    if isinstance(exc, ReportForbidden):
        return _error("forbidden", status.HTTP_403_FORBIDDEN)
    if isinstance(exc, ReportConflict):
        return _error(str(exc), status.HTTP_409_CONFLICT)
    if isinstance(exc, AppealConflict):
        return _error(str(exc), status.HTTP_409_CONFLICT)
    if isinstance(exc, ReportInvalid):
        return _error(str(exc), status.HTTP_422_UNPROCESSABLE_CONTENT)
    if isinstance(exc, OperatorNotAuthorized):
        return _error("operator_not_authorized", status.HTTP_403_FORBIDDEN)
    raise exc


@router.post("/reports", response_model=ReportView, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ReportView:
    try:
        report = ModerationService(session).create_report(
            current.user_id,
            target_user_id=payload.target_user_id,
            lobby_id=payload.lobby_id,
            category=payload.category,
            description=payload.description,
            message_ids=payload.message_ids,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _report_view(report)


@router.get("/reports/me", response_model=ReportListResponse)
def list_my_reports(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReportListResponse:
    rows = ModerationService(session).list_my_reports(current.user_id, limit=limit, offset=offset)
    return ReportListResponse(reports=[_report_view(item) for item in rows])


@router.get("/actions/me", response_model=ActionListResponse)
def list_my_actions(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ActionListResponse:
    rows = ModerationService(session).list_actions(current.user_id)
    return ActionListResponse(actions=[_action_view(item) for item in rows])


@router.post("/actions/{action_id}/appeal", response_model=AppealView)
def appeal_action(
    action_id: UUID,
    payload: AppealCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> AppealView:
    try:
        appeal = ModerationService(session).appeal(
            action_id,
            user_id=current.user_id,
            reason=payload.reason,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _appeal_view(appeal)


@router.get("/me", response_model=ModeratorView)
def moderator_me(
    moderator: Annotated[ModeratorContext, Depends(get_moderator)],
) -> ModeratorView:
    return ModeratorView(user_id=moderator.user_id, role=moderator.role)


@router.get("/queue", response_model=QueueResponse)
def moderation_queue(
    moderator: Annotated[ModeratorContext, Depends(get_moderator)],
    session: Annotated[Session, Depends(get_session)],
    status_filter: Annotated[
        str, Query(pattern="^(OPEN|IN_REVIEW|RESOLVED|DISMISSED|APPEALED)$")
    ] = "OPEN",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> QueueResponse:
    service = ModerationService(session)
    rows = service.queue(status_filter=status_filter, limit=limit, offset=offset)
    return QueueResponse(
        reports=[_admin_report_view(item) for item in rows],
        stats=service.stats(),
    )


@router.get("/reports/{report_id}", response_model=AdminReportView)
def moderation_report_detail(
    report_id: UUID,
    moderator: Annotated[ModeratorContext, Depends(get_moderator)],
    session: Annotated[Session, Depends(get_session)],
) -> AdminReportView:
    try:
        report = ModerationService(session).get_report(report_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return _admin_report_view(report)


@router.post("/reports/{report_id}/decision", response_model=AdminReportView)
def moderation_decision(
    report_id: UUID,
    payload: DecisionRequest,
    moderator: Annotated[ModeratorContext, Depends(get_moderator)],
    session: Annotated[Session, Depends(get_session)],
) -> AdminReportView:
    service = ModerationService(session)
    try:
        report, _action = service.review(
            report_id,
            operator=str(moderator.user_id),
            decision=payload.decision,
            reason=payload.reason,
            days=payload.days,
            authorized_operators=frozenset({str(moderator.user_id)}),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _admin_report_view(report)


@router.get("/appeals", response_model=list[AppealView])
def moderation_appeals(
    moderator: Annotated[ModeratorContext, Depends(get_moderator)],
    session: Annotated[Session, Depends(get_session)],
    status_filter: Annotated[str, Query(pattern="^(OPEN|ACCEPTED|REJECTED)$")] = "OPEN",
) -> list[AppealView]:
    return [
        _appeal_view(item)
        for item in ModerationService(session).list_appeals(status_filter=status_filter)
    ]


@router.post("/appeals/{appeal_id}/decision", response_model=AppealView)
def moderation_appeal_decision(
    appeal_id: UUID,
    payload: AppealDecisionRequest,
    moderator: Annotated[ModeratorContext, Depends(get_moderator)],
    session: Annotated[Session, Depends(get_session)],
) -> AppealView:
    try:
        appeal = ModerationService(session).review_appeal(
            appeal_id,
            operator=str(moderator.user_id),
            decision=payload.decision,
            reason=payload.reason,
            authorized_operators=frozenset({str(moderator.user_id)}),
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _appeal_view(appeal)


@router.get("/operators", response_model=list[OperatorView])
def list_moderation_operators(
    admin: Annotated[ModeratorContext, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[OperatorView]:
    return [_operator_view(item) for item in ModerationService(session).list_operators()]


@router.post("/operators", response_model=OperatorView, status_code=status.HTTP_201_CREATED)
def upsert_moderation_operator(
    payload: OperatorCreate,
    admin: Annotated[ModeratorContext, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> OperatorView:
    try:
        row = ModerationService(session).add_operator(
            admin.user_id,
            payload.user_id,
            role=payload.role,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _operator_view(row)


@router.delete("/operators/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_moderation_operator(
    user_id: UUID,
    admin: Annotated[ModeratorContext, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    try:
        ModerationService(session).deactivate_operator(admin.user_id, user_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None


__all__ = ["router"]
