"""Testes de amizades, bloqueios e convites de lobby."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.matchmaking.models import LobbyParticipant
from app.modules.profile.models import UserSportProfile
from app.modules.social.models import LobbyInvite, UserBlock
from app.modules.social.service import (
    AlreadyFriends,
    BlockedRelationship,
    CannotTargetSelf,
    IncomingRequestExists,
    InviteAlreadyExists,
    InviteNotPending,
    LobbyFull,
    SocialError,
    SocialService,
)
from tests.helpers_results import END, build_match, make_user

AT = END + timedelta(minutes=2)


def make_friend(session: Session, format_id):
    user_id = make_user(session)
    session.add(
        UserSportProfile(
            user_id=user_id,
            format_id=format_id,
            level="intermediate",
            court_preference="ANY",
        )
    )
    session.flush()
    return user_id


def accept_friendship(session: Session, requester, target):
    service = SocialService(session)
    request = service.send_friend_request(requester, target, now=AT)
    service.accept_friend_request(request.id, target, now=AT)
    return request


def test_friend_request_accept_and_remove(db_session: Session) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    service = SocialService(db_session)

    with pytest.raises(CannotTargetSelf):
        service.send_friend_request(first, first, now=AT)
    with pytest.raises(IncomingRequestExists):
        request = service.send_friend_request(first, second, now=AT)
        service.send_friend_request(second, first, now=AT)

    assert service.accept_friend_request(request.id, second, now=AT).status == "ACCEPTED"
    assert service.are_friends(first, second) is True
    with pytest.raises(AlreadyFriends):
        service.send_friend_request(first, second, now=AT)

    service.remove_friend(first, second, now=AT)
    assert service.are_friends(first, second) is False


def test_block_cancels_friendship_and_prevents_invite(db_session: Session) -> None:
    match, users, _, sport_format = build_match(db_session, checked_in=10)
    friend = make_friend(db_session, sport_format.id)
    accept_friendship(db_session, users[0], friend)

    service = SocialService(db_session)
    service.block(users[0], friend, now=AT)

    assert service.is_blocked(users[0], friend) is True
    assert service.are_friends(users[0], friend) is False
    with pytest.raises(BlockedRelationship):
        service.send_friend_request(users[0], friend, now=AT)
    with pytest.raises(BlockedRelationship):
        service.invite_to_lobby(users[0], match.lobby_id, friend, now=AT)


def test_invite_requires_friendship_and_free_slot(db_session: Session) -> None:
    match, users, participants, sport_format = build_match(db_session, checked_in=10)
    service = SocialService(db_session)
    outsider = make_friend(db_session, sport_format.id)

    with pytest.raises(SocialError):
        service.invite_to_lobby(users[0], match.lobby_id, outsider, now=AT)

    accept_friendship(db_session, users[0], outsider)
    with pytest.raises(LobbyFull):
        service.invite_to_lobby(users[0], match.lobby_id, outsider, now=AT)

    participant = db_session.scalar(
        select(LobbyParticipant).where(
            LobbyParticipant.lobby_id == match.lobby_id,
            LobbyParticipant.user_id == users[1],
        )
    )
    assert participant is not None
    db_session.delete(participant)
    db_session.flush()

    invite = service.invite_to_lobby(users[0], match.lobby_id, outsider, now=AT)
    assert invite.status == "PENDING"
    assert db_session.scalar(select(func.count()).select_from(LobbyInvite)) == 1

    accepted = service.respond_invite(invite.id, outsider, accept=True, now=AT)
    assert accepted.status == "ACCEPTED"
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(LobbyParticipant)
            .where(LobbyParticipant.lobby_id == match.lobby_id)
        )
        == 10
    )


def test_duplicate_invite_and_non_pending_response(db_session: Session) -> None:
    match, users, participants, sport_format = build_match(db_session, checked_in=10)
    service = SocialService(db_session)
    invitee = make_friend(db_session, sport_format.id)
    accept_friendship(db_session, users[0], invitee)
    participant = db_session.scalar(
        select(LobbyParticipant).where(
            LobbyParticipant.lobby_id == match.lobby_id,
            LobbyParticipant.user_id == users[1],
        )
    )
    assert participant is not None
    db_session.delete(participant)
    db_session.flush()

    invite = service.invite_to_lobby(users[0], match.lobby_id, invitee, now=AT)
    with pytest.raises(InviteAlreadyExists):
        service.invite_to_lobby(users[0], match.lobby_id, invitee, now=AT)

    service.respond_invite(invite.id, invitee, accept=False, now=AT)
    with pytest.raises(InviteNotPending):
        service.respond_invite(invite.id, invitee, accept=True, now=AT)


def test_unblock_removes_block(db_session: Session) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    service = SocialService(db_session)

    service.block(first, second, now=AT)
    assert db_session.scalar(select(func.count()).select_from(UserBlock)) == 1
    service.unblock(first, second)
    assert db_session.scalar(select(func.count()).select_from(UserBlock)) == 0
