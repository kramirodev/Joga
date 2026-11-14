"""Clãs, membros, chat, denúncias e troféus (Fase 16)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.clans.models import Clan, ClanJoinRequest, ClanMember, ClanReport
from app.modules.clans.service import (
    MAX_MEMBERS,
    ClanConflict,
    ClanCooldown,
    ClanError,
    ClanForbidden,
    ClanFull,
    ClanNotFound,
    active_clan_for,
    clan_ranking,
    create_clan,
    decide_report,
    decide_request,
    get_clan,
    leave_clan,
    list_messages,
    list_reports,
    member_count,
    membership_of,
    remove_member,
    report_message,
    request_join,
    require_admin,
    require_member,
    send_message,
    set_role,
    transfer_ownership,
    trophy_total,
)
from app.modules.identity.clock import utcnow
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.season.service import SeasonNotFound, active_season

router = APIRouter(tags=["clans"])


class ClanSummaryView(BaseModel):
    id: UUID
    name: str
    tag: str
    description: str | None
    join_policy: str
    members: int
    max_members: int
    trophies: int
    my_role: str | None


class ClanListView(BaseModel):
    clans: list[ClanSummaryView]


class ClanRankingEntry(BaseModel):
    clan_id: UUID
    name: str
    tag: str
    trophies: int
    position: int


class ClanRankingView(BaseModel):
    season_code: str | None
    format_id: UUID | None
    entries: list[ClanRankingEntry]


class MemberView(BaseModel):
    user_id: UUID
    display_name: str | None
    role: str
    joined_at: datetime


class MemberListView(BaseModel):
    members: list[MemberView]


class RequestView(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str | None
    status: str
    message: str | None
    created_at: datetime


class RequestListView(BaseModel):
    requests: list[RequestView]


class JoinResultView(BaseModel):
    status: str
    request: RequestView | None = None


class MessageView(BaseModel):
    id: UUID
    sender_id: UUID
    display_name: str | None
    body: str
    hidden: bool
    created_at: datetime


class MessageListView(BaseModel):
    messages: list[MessageView]


class ReportView(BaseModel):
    id: UUID
    message_id: UUID
    reporter_id: UUID
    reason: str
    status: str
    created_at: datetime
    reviewed_at: datetime | None
    decision_note: str | None


class ReportListView(BaseModel):
    reports: list[ReportView]


def _season(session: Session) -> tuple[UUID | None, str | None]:
    try:
        season = active_season(session, utcnow())
    except SeasonNotFound:
        return None, None
    return season.id, season.code


def _display_name(session: Session, user_id: UUID) -> str | None:
    from app.modules.profile.models import UserProfile

    return session.scalar(select(UserProfile.display_name).where(UserProfile.user_id == user_id))


def _clan_view(
    session: Session,
    clan: Clan,
    user_id: UUID,
    *,
    format_id: UUID | None = None,
) -> ClanSummaryView:
    season_id, _ = _season(session)
    membership = membership_of(session, clan.id, user_id)
    return ClanSummaryView(
        id=clan.id,
        name=clan.name,
        tag=clan.tag,
        description=clan.description,
        join_policy=clan.join_policy,
        members=member_count(session, clan.id),
        max_members=MAX_MEMBERS,
        trophies=trophy_total(
            session,
            clan.id,
            season_id=season_id,
            format_id=format_id,
        ),
        my_role=membership.role if membership else None,
    )


def _request_view(session: Session, request: ClanJoinRequest) -> RequestView:
    return RequestView(
        id=request.id,
        user_id=request.user_id,
        display_name=_display_name(session, request.user_id),
        status=request.status,
        message=request.message,
        created_at=request.created_at,
    )


def _report_view(report: ClanReport) -> ReportView:
    return ReportView(
        id=report.id,
        message_id=report.message_id,
        reporter_id=report.reporter_id,
        reason=report.reason,
        status=report.status,
        created_at=report.created_at,
        reviewed_at=report.reviewed_at,
        decision_note=report.decision_note,
    )


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, ClanNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "not_found"})
    if isinstance(exc, ClanForbidden):
        code = exc.args[0] if exc.args else "forbidden"
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": code})
    if isinstance(exc, ClanFull):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "clan_full"})
    if isinstance(exc, ClanCooldown):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "clan_cooldown"})
    if isinstance(exc, ClanConflict):
        code = exc.args[0] if exc.args else "clan_conflict"
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": code})
    if isinstance(exc, ClanError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "clan_error"})
    raise exc


class ClanCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=40)
    tag: str = Field(min_length=2, max_length=8)
    description: str | None = Field(default=None, max_length=280)


class JoinRequestCreate(BaseModel):
    message: str | None = Field(default=None, max_length=200)


class DecisionRequest(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=200)


class RoleRequest(BaseModel):
    role: str = Field(pattern="^(admin|member)$")


class TransferRequest(BaseModel):
    user_id: UUID


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class ReportCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


class ReportDecision(BaseModel):
    decision: str = Field(pattern="^(KEEP_HIDDEN|RESTORE)$")
    note: str | None = Field(default=None, max_length=300)


@router.post("/clans", response_model=ClanSummaryView, status_code=status.HTTP_201_CREATED)
def create(
    payload: ClanCreateRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ClanSummaryView:
    try:
        clan = create_clan(
            session,
            current.user_id,
            name=payload.name,
            tag=payload.tag,
            description=payload.description,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _clan_view(session, clan, current.user_id)


@router.get("/clans", response_model=ClanListView)
def list_clans(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ClanListView:
    statement = select(Clan).where(Clan.status == "active")
    if q:
        term = f"%{q.strip()}%"
        statement = statement.where(Clan.name.ilike(term) | Clan.tag.ilike(term))
    clans = session.scalars(statement.order_by(Clan.name.asc()).limit(limit)).all()
    return ClanListView(clans=[_clan_view(session, clan, current.user_id) for clan in clans])


@router.get("/clans/ranking", response_model=ClanRankingView)
def ranking(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    format_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ClanRankingView:
    season_id, code = _season(session)
    rows = clan_ranking(session, season_id=season_id, format_id=format_id, limit=limit)
    return ClanRankingView(
        season_code=code,
        format_id=format_id,
        entries=[
            ClanRankingEntry(
                clan_id=clan.id,
                name=clan.name,
                tag=clan.tag,
                trophies=total,
                position=index + 1,
            )
            for index, (clan, total) in enumerate(rows)
        ],
    )


@router.get("/me/clan", response_model=ClanSummaryView | None)
def my_clan(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ClanSummaryView | None:
    clan = active_clan_for(session, current.user_id)
    if clan is None:
        return None
    return _clan_view(session, clan, current.user_id)


@router.get("/clans/{clan_id}", response_model=ClanSummaryView)
def read_clan(
    clan_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    format_id: Annotated[UUID | None, Query()] = None,
) -> ClanSummaryView:
    try:
        clan = get_clan(session, clan_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return _clan_view(session, clan, current.user_id, format_id=format_id)


@router.post("/clans/{clan_id}/join", response_model=JoinResultView)
def join(
    clan_id: UUID,
    payload: JoinRequestCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> JoinResultView:
    try:
        request = request_join(
            session,
            current.user_id,
            clan_id,
            message=payload.message,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    if request is None:
        return JoinResultView(status="joined")
    return JoinResultView(status="pending", request=_request_view(session, request))


@router.get("/clans/{clan_id}/requests", response_model=RequestListView)
def read_requests(
    clan_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> RequestListView:
    try:
        require_admin(session, clan_id, current.user_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    requests = session.scalars(
        select(ClanJoinRequest)
        .where(
            ClanJoinRequest.clan_id == clan_id,
            ClanJoinRequest.status == "pending",
        )
        .order_by(ClanJoinRequest.created_at.asc())
    ).all()
    return RequestListView(requests=[_request_view(session, item) for item in requests])


@router.post(
    "/clans/{clan_id}/requests/{request_id}/decide",
    response_model=RequestView,
)
def decide(
    clan_id: UUID,
    request_id: UUID,
    payload: DecisionRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> RequestView:
    try:
        request = decide_request(
            session,
            current.user_id,
            clan_id,
            request_id,
            approve=payload.approve,
            note=payload.note,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _request_view(session, request)


@router.get("/clans/{clan_id}/members", response_model=MemberListView)
def read_members(
    clan_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> MemberListView:
    try:
        require_member(session, clan_id, current.user_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    rows = session.scalars(
        select(ClanMember)
        .where(ClanMember.clan_id == clan_id, ClanMember.status == "active")
        .order_by(ClanMember.joined_at.asc())
    ).all()
    return MemberListView(
        members=[
            MemberView(
                user_id=row.user_id,
                display_name=_display_name(session, row.user_id),
                role=row.role,
                joined_at=row.joined_at,
            )
            for row in rows
        ]
    )


@router.delete("/clans/{clan_id}/members/{user_id}", response_model=MemberView)
def remove(
    clan_id: UUID,
    user_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> MemberView:
    try:
        member = remove_member(session, current.user_id, clan_id, user_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return MemberView(
        user_id=member.user_id,
        display_name=_display_name(session, member.user_id),
        role=member.role,
        joined_at=member.joined_at,
    )


@router.post("/clans/{clan_id}/members/{user_id}/role", response_model=MemberView)
def change_role(
    clan_id: UUID,
    user_id: UUID,
    payload: RoleRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> MemberView:
    try:
        member = set_role(session, current.user_id, clan_id, user_id, role=payload.role)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return MemberView(
        user_id=member.user_id,
        display_name=_display_name(session, member.user_id),
        role=member.role,
        joined_at=member.joined_at,
    )


@router.post("/clans/{clan_id}/transfer", response_model=MemberView)
def transfer(
    clan_id: UUID,
    payload: TransferRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> MemberView:
    try:
        member = transfer_ownership(session, current.user_id, clan_id, payload.user_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return MemberView(
        user_id=member.user_id,
        display_name=_display_name(session, member.user_id),
        role=member.role,
        joined_at=member.joined_at,
    )


@router.post("/clans/{clan_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave(
    clan_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    try:
        leave_clan(session, current.user_id, clan_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None


@router.get("/clans/{clan_id}/messages", response_model=MessageListView)
def read_messages(
    clan_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessageListView:
    try:
        messages = list_messages(session, current.user_id, clan_id, limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return MessageListView(
        messages=[
            MessageView(
                id=message.id,
                sender_id=message.sender_id,
                display_name=_display_name(session, message.sender_id),
                body=message.body,
                hidden=message.hidden_at is not None,
                created_at=message.created_at,
            )
            for message in messages
        ]
    )


@router.post(
    "/clans/{clan_id}/messages",
    response_model=MessageView,
    status_code=status.HTTP_201_CREATED,
)
def send(
    clan_id: UUID,
    payload: MessageCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> MessageView:
    try:
        message = send_message(session, current.user_id, clan_id, payload.body)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return MessageView(
        id=message.id,
        sender_id=message.sender_id,
        display_name=_display_name(session, message.sender_id),
        body=message.body,
        hidden=False,
        created_at=message.created_at,
    )


@router.post(
    "/clans/{clan_id}/messages/{message_id}/report",
    response_model=ReportView,
    status_code=status.HTTP_201_CREATED,
)
def report(
    clan_id: UUID,
    message_id: UUID,
    payload: ReportCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ReportView:
    try:
        report_row = report_message(
            session,
            current.user_id,
            clan_id,
            message_id,
            payload.reason,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _report_view(report_row)


@router.get("/clans/{clan_id}/reports", response_model=ReportListView)
def read_reports(
    clan_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    status_filter: Annotated[str | None, Query(max_length=14)] = None,
) -> ReportListView:
    try:
        reports = list_reports(session, current.user_id, clan_id, status_filter=status_filter)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return ReportListView(reports=[_report_view(item) for item in reports])


@router.post(
    "/clans/{clan_id}/reports/{report_id}/decide",
    response_model=ReportView,
)
def decide_report_route(
    clan_id: UUID,
    report_id: UUID,
    payload: ReportDecision,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ReportView:
    try:
        report_row = decide_report(
            session,
            current.user_id,
            clan_id,
            report_id,
            decision=payload.decision,
            note=payload.note,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _report_view(report_row)
