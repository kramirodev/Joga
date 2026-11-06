"""Endpoints de amigos, bloqueios, convites e tokens de push."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.push.service import PushError, PushService
from app.modules.ratelimit.service import RateLimitExceeded
from app.modules.realtime.manager import manager
from app.modules.social.models import Friendship, LobbyInvite
from app.modules.social.service import (
    AlreadyFriends,
    BlockedRelationship,
    CannotTargetSelf,
    FriendshipNotFound,
    IncomingRequestExists,
    InviteAlreadyExists,
    InviteExpired,
    InviteNotFound,
    InviteNotPending,
    LobbyFull,
    LobbyUnavailable,
    RequestAlreadyExists,
    SocialError,
    SocialService,
    UserNotFound,
)

router = APIRouter(tags=["social"])


class FriendView(BaseModel):
    user_id: UUID
    display_name: str | None


class FriendsResponse(BaseModel):
    friends: list[FriendView]


class FriendRequest(BaseModel):
    user_id: UUID


class FriendshipView(BaseModel):
    id: UUID
    user_low_id: UUID
    user_high_id: UUID
    requested_by: UUID
    status: str


class BlockRequest(BaseModel):
    user_id: UUID


class InviteRequest(BaseModel):
    user_id: UUID


class InviteView(BaseModel):
    id: UUID
    lobby_id: UUID
    inviter_id: UUID
    invitee_id: UUID
    status: str
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None


class InvitesResponse(BaseModel):
    invites: list[InviteView]


class PushTokenRequest(BaseModel):
    token: str
    platform: str


class PushTokenView(BaseModel):
    token: str
    platform: str
    revoked_at: datetime | None


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _handle(exc: Exception) -> HTTPException:
    mapping = {
        UserNotFound: ("user_not_found", status.HTTP_404_NOT_FOUND),
        CannotTargetSelf: ("cannot_target_self", status.HTTP_422_UNPROCESSABLE_CONTENT),
        BlockedRelationship: ("blocked_relationship", status.HTTP_409_CONFLICT),
        AlreadyFriends: ("already_friends", status.HTTP_409_CONFLICT),
        RequestAlreadyExists: ("friend_request_exists", status.HTTP_409_CONFLICT),
        IncomingRequestExists: ("incoming_friend_request", status.HTTP_409_CONFLICT),
        FriendshipNotFound: ("friendship_not_found", status.HTTP_404_NOT_FOUND),
        InviteNotFound: ("invite_not_found", status.HTTP_404_NOT_FOUND),
        InviteAlreadyExists: ("invite_already_exists", status.HTTP_409_CONFLICT),
        InviteNotPending: ("invite_not_pending", status.HTTP_409_CONFLICT),
        InviteExpired: ("invite_expired", status.HTTP_409_CONFLICT),
        LobbyUnavailable: ("lobby_unavailable", status.HTTP_409_CONFLICT),
        LobbyFull: ("lobby_full", status.HTTP_409_CONFLICT),
        SocialError: ("social_error", status.HTTP_409_CONFLICT),
    }
    if isinstance(exc, RateLimitExceeded):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited"},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )
    for error_type, (code, status_code) in mapping.items():
        if isinstance(exc, error_type):
            return _error(code, status_code)
    raise exc


def _friendship_view(row: Friendship) -> FriendshipView:
    return FriendshipView(
        id=row.id,
        user_low_id=row.user_low_id,
        user_high_id=row.user_high_id,
        requested_by=row.requested_by,
        status=row.status,
    )


def _invite_view(row: LobbyInvite) -> InviteView:
    return InviteView(
        id=row.id,
        lobby_id=row.lobby_id,
        inviter_id=row.inviter_id,
        invitee_id=row.invitee_id,
        status=row.status,
        created_at=row.created_at,
        expires_at=row.expires_at,
        responded_at=row.responded_at,
    )


@router.get("/friends", response_model=FriendsResponse)
def list_friends(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> FriendsResponse:
    rows = SocialService(session).list_friends(current.user_id)
    return FriendsResponse(
        friends=[FriendView(user_id=user_id, display_name=name) for user_id, name in rows]
    )


@router.post(
    "/friends/requests",
    response_model=FriendshipView,
    status_code=status.HTTP_201_CREATED,
)
def request_friend(
    payload: FriendRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> FriendshipView:
    try:
        row = SocialService(session).send_friend_request(current.user_id, payload.user_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _friendship_view(row)


@router.post("/friends/requests/{request_id}/accept", response_model=FriendshipView)
def accept_friend(
    request_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> FriendshipView:
    try:
        row = SocialService(session).accept_friend_request(request_id, current.user_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _friendship_view(row)


@router.delete("/friends/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_friend(
    user_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    try:
        SocialService(session).remove_friend(current.user_id, user_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None


@router.post("/blocks", status_code=status.HTTP_201_CREATED)
def block_user(
    payload: BlockRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, str]:
    try:
        SocialService(session).block(current.user_id, payload.user_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return {"status": "blocked"}


@router.delete("/blocks/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unblock_user(
    user_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    SocialService(session).unblock(current.user_id, user_id)
    session.commit()


@router.get("/lobby-invites", response_model=InvitesResponse)
def list_invites(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> InvitesResponse:
    rows = SocialService(session).pending_invites(current.user_id)
    return InvitesResponse(invites=[_invite_view(row) for row in rows])


@router.post(
    "/lobbies/{lobby_id}/invites",
    response_model=InviteView,
    status_code=status.HTTP_201_CREATED,
)
async def invite_to_lobby(
    lobby_id: UUID,
    payload: InviteRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> InviteView:
    try:
        invite = SocialService(session).invite_to_lobby(
            current.user_id,
            lobby_id,
            payload.user_id,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    view = _invite_view(invite)
    await manager.publish_user(
        invite.invitee_id,
        {"type": "lobby.invite.created", "data": view.model_dump(mode="json")},
    )
    return view


@router.post("/lobby-invites/{invite_id}/accept", response_model=InviteView)
async def accept_invite(
    invite_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> InviteView:
    try:
        invite = SocialService(session).respond_invite(
            invite_id,
            current.user_id,
            accept=True,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    view = _invite_view(invite)
    await manager.publish_lobby(
        invite.lobby_id,
        {"type": "lobby.invite.accepted", "data": view.model_dump(mode="json")},
    )
    return view


@router.post("/lobby-invites/{invite_id}/decline", response_model=InviteView)
def decline_invite(
    invite_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> InviteView:
    try:
        invite = SocialService(session).respond_invite(
            invite_id,
            current.user_id,
            accept=False,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _invite_view(invite)


@router.put("/push-tokens", response_model=PushTokenView)
def register_push_token(
    payload: PushTokenRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PushTokenView:
    try:
        row = PushService(session).register_token(
            current.user_id,
            payload.token,
            payload.platform,
        )
        session.commit()
    except PushError as exc:
        session.rollback()
        raise _error("invalid_push_token", status.HTTP_422_UNPROCESSABLE_CONTENT) from exc
    return PushTokenView(token=row.token, platform=row.platform, revoked_at=row.revoked_at)


@router.delete("/push-tokens/{token}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_push_token(
    token: str,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    try:
        PushService(session).revoke_token(current.user_id, token)
        session.commit()
    except PushError as exc:
        session.rollback()
        raise _error("push_token_not_found", status.HTTP_404_NOT_FOUND) from exc
