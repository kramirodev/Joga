"""Testes de amizades, bloqueios e convites de lobby."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc
from app.modules.matchmaking.models import LobbyParticipant
from app.modules.notifications.models import Notification
from app.modules.profile.models import UserSportProfile
from app.modules.ratelimit.service import RateLimitExceeded
from app.modules.social import service as social_service
from app.modules.social.models import Friendship, LobbyInvite, UserBlock
from app.modules.social.service import (
    AlreadyFriends,
    BlockedRelationship,
    CannotTargetSelf,
    FriendshipNotFound,
    IncomingRequestExists,
    InviteAlreadyExists,
    InviteNotPending,
    LobbyFull,
    SocialError,
    SocialService,
    ordered_pair,
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


def test_friend_request_lists_and_accept_flow(db_session: Session) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    service = SocialService(db_session)

    request = service.send_friend_request(first, second, now=AT)

    incoming = service.list_friend_requests(second, direction="incoming", status="pending")
    assert [entry.id for entry in incoming] == [request.id]
    assert incoming[0].counterpart_id == first
    assert incoming[0].counterpart_name is None
    assert incoming[0].direction == "incoming"
    assert incoming[0].status == "PENDING"
    assert ensure_utc(incoming[0].created_at) == AT
    assert incoming[0].responded_at is None

    outgoing = service.list_friend_requests(first, direction="outgoing")
    assert [entry.id for entry in outgoing] == [request.id]
    assert outgoing[0].direction == "outgoing"
    assert service.list_friend_requests(first, direction="incoming") == []
    assert [entry.id for entry in service.list_friend_requests(first, direction="all")] == [
        request.id
    ]

    accepted_at = AT + timedelta(minutes=1)
    accepted = service.accept_friend_request(request.id, second, now=accepted_at)
    assert accepted.status == "ACCEPTED"
    assert ensure_utc(accepted.responded_at) == accepted_at

    assert service.are_friends(first, second) is True
    assert service.list_friends(first) == [(second, None)]
    assert service.list_friend_requests(second, status="pending") == []
    history = service.list_friend_requests(second, direction="incoming", status="history")
    assert [entry.status for entry in history] == ["ACCEPTED"]


def test_decline_only_recipient_and_reopen(db_session: Session) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    outsider = make_user(db_session)
    service = SocialService(db_session)

    request = service.send_friend_request(first, second, now=AT)
    with pytest.raises(FriendshipNotFound):
        service.decline_friend_request(request.id, first, now=AT)
    with pytest.raises(FriendshipNotFound):
        service.decline_friend_request(request.id, outsider, now=AT)

    declined_at = AT + timedelta(minutes=1)
    declined = service.decline_friend_request(request.id, second, now=declined_at)
    assert declined.status == "DECLINED"
    assert ensure_utc(declined.responded_at) == declined_at

    with pytest.raises(FriendshipNotFound):
        service.accept_friend_request(request.id, second, now=declined_at)
    with pytest.raises(FriendshipNotFound):
        service.decline_friend_request(request.id, second, now=declined_at)

    reopened_at = AT + timedelta(minutes=2)
    reopened = service.send_friend_request(first, second, now=reopened_at)
    assert reopened.id == request.id
    assert reopened.status == "PENDING"
    assert reopened.requested_by == first
    assert ensure_utc(reopened.created_at) == reopened_at
    assert reopened.responded_at is None
    assert [entry.id for entry in service.list_friend_requests(second)] == [request.id]


def test_cancel_only_author_and_reopen_by_other_side(db_session: Session) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    service = SocialService(db_session)

    request = service.send_friend_request(first, second, now=AT)
    with pytest.raises(FriendshipNotFound):
        service.cancel_friend_request(request.id, second, now=AT)
    with pytest.raises(FriendshipNotFound):
        service.cancel_friend_request(request.id, make_user(db_session), now=AT)

    cancelled_at = AT + timedelta(minutes=1)
    cancelled = service.cancel_friend_request(request.id, first, now=cancelled_at)
    assert cancelled.status == "CANCELLED"
    assert ensure_utc(cancelled.responded_at) == cancelled_at

    history = service.list_friend_requests(first, direction="outgoing", status="history")
    assert [entry.status for entry in history] == ["CANCELLED"]
    assert service.list_friend_requests(second, status="pending") == []

    reopened = service.send_friend_request(second, first, now=AT + timedelta(minutes=2))
    assert reopened.id == request.id
    assert reopened.requested_by == second
    assert reopened.status == "PENDING"
    assert [entry.direction for entry in service.list_friend_requests(first)] == ["incoming"]


def test_resend_same_author_is_idempotent_and_opposite_returns_id(
    db_session: Session,
) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    service = SocialService(db_session)

    request = service.send_friend_request(first, second, now=AT)
    replay = service.send_friend_request(first, second, now=AT + timedelta(minutes=1))
    assert replay.id == request.id
    assert db_session.scalar(select(func.count()).select_from(Friendship)) == 1

    with pytest.raises(IncomingRequestExists) as exc_info:
        service.send_friend_request(second, first, now=AT + timedelta(minutes=2))
    assert exc_info.value.friendship_id == request.id


def test_author_cannot_accept_own_request(db_session: Session) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    service = SocialService(db_session)

    request = service.send_friend_request(first, second, now=AT)
    with pytest.raises(FriendshipNotFound):
        service.accept_friend_request(request.id, first, now=AT)
    with pytest.raises(FriendshipNotFound):
        service.accept_friend_request(request.id, make_user(db_session), now=AT)


def test_send_friend_request_recovers_from_unique_conflict(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    low, high = ordered_pair(first, second)
    existing = Friendship(
        user_low_id=low,
        user_high_id=high,
        requested_by=first,
        status="PENDING",
        created_at=AT,
        updated_at=AT,
    )
    db_session.add(existing)
    db_session.flush()

    service = SocialService(db_session)
    original_find = service._find_friendship
    calls = {"count": 0}

    def find_after_lost_race(low_id, high_id, *, for_update: bool = False) -> Friendship | None:
        calls["count"] += 1
        if calls["count"] == 1:
            # Simula a janela entre a leitura e o INSERT perdido.
            return None
        return original_find(low_id, high_id, for_update=for_update)

    monkeypatch.setattr(service, "_find_friendship", find_after_lost_race)

    result = service.send_friend_request(first, second, now=AT + timedelta(minutes=5))
    assert result.id == existing.id
    assert calls["count"] >= 2
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.kind == "friend_request_received")
        )
        == 0
    )


def test_send_friend_request_conflict_with_incoming_carries_id(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    low, high = ordered_pair(first, second)
    existing = Friendship(
        user_low_id=low,
        user_high_id=high,
        requested_by=second,
        status="PENDING",
        created_at=AT,
        updated_at=AT,
    )
    db_session.add(existing)
    db_session.flush()

    service = SocialService(db_session)
    original_find = service._find_friendship
    calls = {"count": 0}

    def find_after_lost_race(low_id, high_id, *, for_update: bool = False) -> Friendship | None:
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return original_find(low_id, high_id, for_update=for_update)

    monkeypatch.setattr(service, "_find_friendship", find_after_lost_race)

    with pytest.raises(IncomingRequestExists) as exc_info:
        service.send_friend_request(first, second, now=AT + timedelta(minutes=5))
    assert exc_info.value.friendship_id == existing.id


def test_friend_request_notifications_once_per_event(db_session: Session) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    third = make_user(db_session)
    fourth = make_user(db_session)
    service = SocialService(db_session)

    request = service.send_friend_request(first, second, now=AT)
    service.send_friend_request(first, second, now=AT + timedelta(seconds=1))
    received = list(
        db_session.scalars(
            select(Notification).where(Notification.kind == "friend_request_received")
        )
    )
    assert len(received) == 1
    assert received[0].user_id == second
    assert received[0].data == {
        "friendship_id": str(request.id),
        "counterpart_id": str(first),
    }
    assert str(second) in received[0].idempotency_key

    accepted_at = AT + timedelta(minutes=1)
    service.accept_friend_request(request.id, second, now=accepted_at)
    with pytest.raises(FriendshipNotFound):
        service.accept_friend_request(request.id, second, now=accepted_at)
    accepted = list(
        db_session.scalars(select(Notification).where(Notification.kind == "friend_accepted"))
    )
    assert len(accepted) == 1
    assert accepted[0].user_id == first
    assert accepted[0].data == {
        "friendship_id": str(request.id),
        "counterpart_id": str(second),
    }

    declined_request = service.send_friend_request(first, third, now=AT + timedelta(minutes=2))
    service.decline_friend_request(declined_request.id, third, now=AT + timedelta(minutes=3))
    with pytest.raises(FriendshipNotFound):
        service.decline_friend_request(
            declined_request.id,
            third,
            now=AT + timedelta(minutes=3),
        )
    declined = list(
        db_session.scalars(select(Notification).where(Notification.kind == "friend_declined"))
    )
    assert len(declined) == 1
    assert declined[0].user_id == first
    assert declined[0].data["counterpart_id"] == str(third)

    cancelled_request = service.send_friend_request(
        first,
        fourth,
        now=AT + timedelta(minutes=4),
    )
    service.cancel_friend_request(
        cancelled_request.id,
        first,
        now=AT + timedelta(minutes=5),
    )
    with pytest.raises(FriendshipNotFound):
        service.cancel_friend_request(
            cancelled_request.id,
            first,
            now=AT + timedelta(minutes=5),
        )
    cancelled = list(
        db_session.scalars(select(Notification).where(Notification.kind == "friend_cancelled"))
    )
    assert len(cancelled) == 1
    assert cancelled[0].user_id == fourth
    assert cancelled[0].data["counterpart_id"] == str(first)

    third_notifications = list(
        db_session.scalars(select(Notification).where(Notification.user_id == third))
    )
    assert [item.kind for item in third_notifications] == ["friend_request_received"]


def test_friend_request_rate_limit_does_not_block_idempotent_replay(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    third = make_user(db_session)
    monkeypatch.setattr(social_service, "FRIEND_REQUEST_HOURLY_LIMIT", 1)
    service = SocialService(db_session)

    request = service.send_friend_request(first, second, now=AT)
    with pytest.raises(RateLimitExceeded):
        service.send_friend_request(first, third, now=AT + timedelta(seconds=1))

    replay = service.send_friend_request(first, second, now=AT + timedelta(seconds=2))
    assert replay.id == request.id


def test_list_blocks_returns_only_own_blocks(db_session: Session) -> None:
    first = make_user(db_session)
    second = make_user(db_session)
    third = make_user(db_session)
    service = SocialService(db_session)

    service.block(first, second, now=AT)
    service.block(third, first, now=AT)
    assert service.list_blocks(first) == [(second, None)]
    assert service.list_blocks(second) == []
