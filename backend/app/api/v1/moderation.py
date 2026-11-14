"""Denúncias e medidas de moderação do jogador (Fase 17A)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.moderation.models import ModerationAction, ModerationAppeal, ModerationReport
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


__all__ = ["router"]
