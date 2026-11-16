"""Central de notificações do jogador (Fase 9D/13E)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.notifications.service import (
    NotificationNotFound,
    NotificationService,
)

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


class NotificationView(BaseModel):
    id: UUID
    kind: str
    title: str
    body: str
    data: dict[str, Any] | None
    created_at: datetime
    read_at: datetime | None


class NotificationListResponse(BaseModel):
    notifications: list[NotificationView]
    unread_count: int
    limit: int
    offset: int


class MarkAllReadResponse(BaseModel):
    marked: int
    unread_count: int


def notification_view(item: Any) -> NotificationView:
    return NotificationView(
        id=item.id,
        kind=item.kind,
        title=item.title,
        body=item.body,
        data=item.data,
        created_at=item.created_at,
        read_at=item.read_at,
    )


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationListResponse:
    service = NotificationService(session)
    rows = service.list_for_user(
        current.user_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return NotificationListResponse(
        notifications=[notification_view(item) for item in rows],
        unread_count=service.unread_count(current.user_id),
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count")
def unread_count(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    return {"unread_count": NotificationService(session).unread_count(current.user_id)}


@router.post("/{notification_id}/read", response_model=NotificationView)
def mark_notification_read(
    notification_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> NotificationView:
    try:
        notification = NotificationService(session).mark_read(
            current.user_id,
            notification_id,
        )
        session.commit()
    except NotificationNotFound as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "notification_not_found"},
        ) from exc
    return notification_view(notification)


@router.post("/read-all", response_model=MarkAllReadResponse)
def mark_all_notifications_read(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> MarkAllReadResponse:
    service = NotificationService(session)
    marked = service.mark_all_read(current.user_id)
    session.commit()
    return MarkAllReadResponse(marked=marked, unread_count=service.unread_count(current.user_id))


__all__ = ["router"]
