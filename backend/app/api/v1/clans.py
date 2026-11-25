"""Clãs, membros, chat, denúncias e troféus (Fase 16)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.core.text import (
    FreeText,
    MultilineText,
    OptionalFreeText,
    OptionalMultilineText,
    escape_like,
)
from app.infrastructure.database.dependency import get_session
from app.modules.clans.models import Clan, ClanInvite, ClanJoinRequest, ClanMember, ClanReport
from app.modules.clans.service import (
    MAX_MEMBERS,
    ClanConflict,
    ClanCooldown,
    ClanError,
    ClanForbidden,
    ClanFull,
    ClanNotFound,
    ClanValidation,
    accept_invite,
    active_clan_for,
    cancel_invite,
    cancel_join_request,
    clan_ranking,
    create_clan,
    decide_report,
    decide_request,
    decline_invite,
    get_clan,
    invite_to_clan,
    latest_request_for,
    latest_requests_for_clans,
    leave_clan,
    list_clan_invites,
    list_join_requests,
    list_messages,
    list_my_requests,
    list_pending_invites,
    list_reports,
    member_count,
    membership_of,
    remove_member,
    report_message,
    request_join,
    require_member,
    send_message,
    set_role,
    transfer_ownership,
    trophy_total,
    update_clan,
)
from app.modules.identity.clock import utcnow
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.season.service import SeasonNotFound, active_season

router = APIRouter(tags=["clans"])


class MyRequestSummaryView(BaseModel):
    """Resumo embutido no clã para o app não refazer a consulta do pedido."""

    id: UUID
    status: str
    message: str | None = None
    created_at: datetime
    decision_note: str | None


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
    is_member: bool
    my_request: MyRequestSummaryView | None = None


class ClanListView(BaseModel):
    clans: list[ClanSummaryView]


class ClanInviteView(BaseModel):
    id: UUID
    clan_id: UUID
    clan_name: str
    clan_tag: str
    inviter_id: UUID
    inviter_display_name: str | None
    inviter_tag: str
    invitee_id: UUID
    invitee_display_name: str | None
    invitee_tag: str
    status: str
    created_at: datetime
    expires_at: datetime
    answered_at: datetime | None


class ClanInviteListView(BaseModel):
    invites: list[ClanInviteView]


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
    tag: str
    role: str
    joined_at: datetime


class MemberListView(BaseModel):
    members: list[MemberView]


class RequestView(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str | None
    tag: str
    status: str
    message: str | None
    created_at: datetime
    decided_at: datetime | None = None
    decided_by: UUID | None = None
    decision_note: str | None = None


class RequestListView(BaseModel):
    requests: list[RequestView]


class MyRequestView(BaseModel):
    """Pedido do próprio jogador, com o clã de destino."""

    id: UUID
    clan_id: UUID
    clan_name: str
    clan_tag: str
    status: str
    message: str | None
    decision_note: str | None
    created_at: datetime
    decided_at: datetime | None


class MyRequestListView(BaseModel):
    requests: list[MyRequestView]


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


@dataclass(frozen=True)
class _PlayerLabel:
    display_name: str | None
    tag: str


def _player_labels(session: Session, user_ids: list[UUID]) -> dict[UUID, _PlayerLabel]:
    """Nome e tag pública de vários jogadores, em uma única consulta."""

    from app.modules.identity.models import User
    from app.modules.profile.models import UserProfile

    unique_ids = list(dict.fromkeys(user_ids))
    if not unique_ids:
        return {}
    rows = session.execute(
        select(User.id, User.tag, UserProfile.display_name)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .where(User.id.in_(unique_ids))
    ).all()
    return {row.id: _PlayerLabel(display_name=row.display_name, tag=row.tag) for row in rows}


def _player_label(session: Session, user_id: UUID) -> _PlayerLabel:
    return _player_labels(session, [user_id]).get(user_id, _PlayerLabel(None, ""))


def _my_request_summary(request: ClanJoinRequest | None) -> MyRequestSummaryView | None:
    if request is None:
        return None
    return MyRequestSummaryView(
        id=request.id,
        status=request.status,
        message=request.message,
        created_at=request.created_at,
        decision_note=request.decision_note,
    )


def _my_request_view(request: ClanJoinRequest, clan: Clan) -> MyRequestView:
    return MyRequestView(
        id=request.id,
        clan_id=clan.id,
        clan_name=clan.name,
        clan_tag=clan.tag,
        status=request.status,
        message=request.message,
        decision_note=request.decision_note,
        created_at=request.created_at,
        decided_at=request.decided_at,
    )


def _clan_view(
    session: Session,
    clan: Clan,
    user_id: UUID,
    *,
    format_id: UUID | None = None,
    my_request: ClanJoinRequest | None = None,
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
        is_member=membership is not None,
        my_request=_my_request_summary(my_request),
    )


def _invite_view(
    session: Session,
    invite: ClanInvite,
    label: _PlayerLabel | None = None,
    invitee_label: _PlayerLabel | None = None,
) -> ClanInviteView:
    clan = session.get(Clan, invite.clan_id)
    inviter = label if label is not None else _player_label(session, invite.inviter_id)
    invitee = (
        invitee_label if invitee_label is not None else _player_label(session, invite.invitee_id)
    )
    return ClanInviteView(
        id=invite.id,
        clan_id=invite.clan_id,
        clan_name=clan.name if clan is not None else "",
        clan_tag=clan.tag if clan is not None else "",
        inviter_id=invite.inviter_id,
        inviter_display_name=inviter.display_name,
        inviter_tag=inviter.tag,
        invitee_id=invite.invitee_id,
        invitee_display_name=invitee.display_name,
        invitee_tag=invitee.tag,
        status=invite.status,
        created_at=invite.created_at,
        expires_at=invite.expires_at,
        answered_at=invite.answered_at,
    )


def _request_view(
    session: Session,
    request: ClanJoinRequest,
    label: _PlayerLabel | None = None,
) -> RequestView:
    player = label if label is not None else _player_label(session, request.user_id)
    return RequestView(
        id=request.id,
        user_id=request.user_id,
        display_name=player.display_name,
        tag=player.tag,
        status=request.status,
        message=request.message,
        created_at=request.created_at,
        decided_at=request.decided_at,
        decided_by=request.decided_by,
        decision_note=request.decision_note,
    )


def _member_view(
    session: Session,
    member: ClanMember,
    label: _PlayerLabel | None = None,
) -> MemberView:
    player = label if label is not None else _player_label(session, member.user_id)
    return MemberView(
        user_id=member.user_id,
        display_name=player.display_name,
        tag=player.tag,
        role=member.role,
        joined_at=member.joined_at,
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
    if isinstance(exc, ClanValidation):
        code = exc.args[0] if exc.args else "invalid"
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": code}
        )
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
    name: FreeText = Field(min_length=3, max_length=40)
    # O serviço normaliza e valida o miolo (2 a 7), aceitando "#" e espaços.
    tag: FreeText = Field(min_length=1, max_length=16)
    description: OptionalMultilineText = Field(default=None, max_length=280)


class ClanUpdateRequest(BaseModel):
    """Edição de clã. ``tag`` é proibida no corpo e responde 422."""

    model_config = ConfigDict(extra="forbid")

    name: FreeText | None = Field(default=None, min_length=3, max_length=40)
    description: OptionalMultilineText = Field(default=None, max_length=280)
    join_policy: Literal["approval", "open", "closed"] | None = None


class ClanInviteCreateRequest(BaseModel):
    user_id: UUID


class JoinRequestCreate(BaseModel):
    message: OptionalFreeText = Field(default=None, max_length=200)


class DecisionRequest(BaseModel):
    approve: bool
    note: OptionalMultilineText = Field(default=None, max_length=200)


class RoleRequest(BaseModel):
    role: str = Field(pattern="^(admin|member)$")


class TransferRequest(BaseModel):
    user_id: UUID


class MessageCreate(BaseModel):
    body: MultilineText = Field(min_length=1, max_length=2000)


class ReportCreate(BaseModel):
    reason: FreeText = Field(min_length=1, max_length=300)


class ReportDecision(BaseModel):
    decision: str = Field(pattern="^(KEEP_HIDDEN|RESTORE)$")
    note: OptionalMultilineText = Field(default=None, max_length=300)


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


@router.patch("/clans/{clan_id}", response_model=ClanSummaryView)
def edit_clan(
    clan_id: UUID,
    payload: ClanUpdateRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ClanSummaryView:
    provided = payload.model_fields_set
    changes: dict[str, str | None] = {}
    if "name" in provided and payload.name is not None:
        changes["name"] = payload.name
    if "description" in provided:
        changes["description"] = payload.description
    if "join_policy" in provided and payload.join_policy is not None:
        changes["join_policy"] = payload.join_policy
    try:
        clan = update_clan(session, current.user_id, clan_id, changes=changes)
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
    open_only: Annotated[bool | None, Query(alias="open")] = None,
    has_slots: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ClanListView:
    statement = select(Clan).where(Clan.status == "active")
    if q:
        # A tag canônica tem "#", mas a busca aceita o miolo ou a forma com "#".
        text = q.strip()
        if text.startswith("#"):
            text = text[1:].strip()
        term = f"%{escape_like(text)}%"
        statement = statement.where(
            Clan.name.ilike(term, escape="\\") | Clan.tag.ilike(term, escape="\\")
        )
    if open_only is not None:
        if open_only:
            statement = statement.where(Clan.join_policy == "open")
        else:
            statement = statement.where(Clan.join_policy != "open")
    member_total = (
        select(func.count())
        .select_from(ClanMember)
        .where(
            ClanMember.clan_id == Clan.id,
            ClanMember.status == "active",
        )
        .correlate(Clan)
        .scalar_subquery()
    )
    if has_slots is not None:
        if has_slots:
            statement = statement.where(member_total < MAX_MEMBERS)
        else:
            statement = statement.where(member_total >= MAX_MEMBERS)
    clans = session.scalars(statement.order_by(Clan.name.asc()).limit(limit)).all()
    # Uma consulta por página resolve ``my_request`` de todos os clãs, sem N+1.
    my_requests = latest_requests_for_clans(
        session,
        current.user_id,
        [clan.id for clan in clans],
    )
    return ClanListView(
        clans=[
            _clan_view(
                session,
                clan,
                current.user_id,
                my_request=my_requests.get(clan.id),
            )
            for clan in clans
        ]
    )


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
    return _clan_view(
        session,
        clan,
        current.user_id,
        my_request=latest_request_for(session, clan.id, current.user_id),
    )


@router.get("/me/clan-requests", response_model=MyRequestListView)
def my_clan_requests(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    request_status: Annotated[Literal["pending", "history"], Query(alias="status")] = "pending",
) -> MyRequestListView:
    try:
        rows = list_my_requests(session, current.user_id, status=request_status)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return MyRequestListView(requests=[_my_request_view(request, clan) for request, clan in rows])


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
    return _clan_view(
        session,
        clan,
        current.user_id,
        format_id=format_id,
        my_request=latest_request_for(session, clan.id, current.user_id),
    )


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
    request_status: Annotated[Literal["pending", "history"], Query(alias="status")] = "pending",
) -> RequestListView:
    try:
        requests = list_join_requests(
            session,
            clan_id,
            current.user_id,
            status=request_status,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    labels = _player_labels(session, [item.user_id for item in requests])
    return RequestListView(
        requests=[_request_view(session, item, labels.get(item.user_id)) for item in requests]
    )


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


@router.delete("/clans/{clan_id}/requests/{request_id}", response_model=RequestView)
def cancel_request(
    clan_id: UUID,
    request_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> RequestView:
    try:
        request = cancel_join_request(session, clan_id, request_id, current.user_id)
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
    labels = _player_labels(session, [row.user_id for row in rows])
    return MemberListView(
        members=[_member_view(session, row, labels.get(row.user_id)) for row in rows]
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
    return _member_view(session, member)


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
    return _member_view(session, member)


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
    return _member_view(session, member)


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


@router.post(
    "/clans/{clan_id}/invites",
    response_model=ClanInviteView,
    status_code=status.HTTP_201_CREATED,
)
def invite(
    clan_id: UUID,
    payload: ClanInviteCreateRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ClanInviteView:
    try:
        invite_row = invite_to_clan(session, current.user_id, clan_id, payload.user_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _invite_view(session, invite_row)


@router.get("/clans/{clan_id}/invites", response_model=ClanInviteListView)
def read_clan_invites(
    clan_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    invite_status: Annotated[Literal["pending", "history"], Query(alias="status")] = "pending",
) -> ClanInviteListView:
    """Convites do clã para dono/admin; ``history`` inclui respondidos/expirados."""

    try:
        invites = list_clan_invites(
            session,
            current.user_id,
            clan_id,
            status=invite_status,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    labels = _player_labels(
        session,
        [item.inviter_id for item in invites] + [item.invitee_id for item in invites],
    )
    return ClanInviteListView(
        invites=[
            _invite_view(
                session,
                item,
                labels.get(item.inviter_id),
                labels.get(item.invitee_id),
            )
            for item in invites
        ]
    )


@router.get("/me/clan-invites", response_model=ClanInviteListView)
def my_clan_invites(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ClanInviteListView:
    invites = list_pending_invites(session, current.user_id)
    session.commit()
    labels = _player_labels(
        session,
        [item.inviter_id for item in invites] + [item.invitee_id for item in invites],
    )
    return ClanInviteListView(
        invites=[
            _invite_view(
                session,
                item,
                labels.get(item.inviter_id),
                labels.get(item.invitee_id),
            )
            for item in invites
        ]
    )


@router.post("/clans/invites/{invite_id}/accept", response_model=ClanSummaryView)
def accept_clan_invite(
    invite_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ClanSummaryView:
    try:
        invite_row = accept_invite(session, current.user_id, invite_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    clan = get_clan(session, invite_row.clan_id)
    return _clan_view(session, clan, current.user_id)


@router.post("/clans/invites/{invite_id}/decline", response_model=ClanInviteView)
def decline_clan_invite(
    invite_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ClanInviteView:
    try:
        invite_row = decline_invite(session, current.user_id, invite_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _invite_view(session, invite_row)


@router.delete("/clans/{clan_id}/invites/{invite_id}", response_model=ClanInviteView)
def cancel_clan_invite(
    clan_id: UUID,
    invite_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> ClanInviteView:
    try:
        invite_row = cancel_invite(session, current.user_id, clan_id, invite_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _invite_view(session, invite_row)
