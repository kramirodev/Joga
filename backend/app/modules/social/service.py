"""Amizades, bloqueios e convites de lobby."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import User
from app.modules.matchmaking.models import Lobby, LobbyParticipant
from app.modules.outbox.service import OutboxService
from app.modules.profile.models import UserProfile, UserSportProfile
from app.modules.ratelimit.service import enforce as enforce_rate_limit
from app.modules.social.models import Friendship, LobbyInvite, UserBlock

INVITE_TTL = timedelta(hours=24)
INVITE_HOURLY_LIMIT = 20


class SocialError(Exception):
    """Erro base de relações sociais."""


class UserNotFound(SocialError):
    pass


class CannotTargetSelf(SocialError):
    pass


class BlockedRelationship(SocialError):
    pass


class AlreadyFriends(SocialError):
    pass


class RequestAlreadyExists(SocialError):
    pass


class IncomingRequestExists(SocialError):
    pass


class FriendshipNotFound(SocialError):
    pass


class InviteNotFound(SocialError):
    pass


class InviteAlreadyExists(SocialError):
    pass


class InviteNotPending(SocialError):
    pass


class InviteExpired(SocialError):
    pass


class LobbyUnavailable(SocialError):
    pass


class LobbyFull(SocialError):
    pass


def ordered_pair(first: uuid.UUID, second: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (first, second) if str(first) < str(second) else (second, first)


class SocialService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # Amizades ----------------------------------------------------------

    def are_friends(self, first: uuid.UUID, second: uuid.UUID) -> bool:
        low, high = ordered_pair(first, second)
        row = self._session.scalar(
            select(Friendship).where(
                Friendship.user_low_id == low,
                Friendship.user_high_id == high,
                Friendship.status == "ACCEPTED",
            )
        )
        return row is not None

    def is_blocked(self, first: uuid.UUID, second: uuid.UUID) -> bool:
        return (
            self._session.scalar(
                select(UserBlock.id).where(
                    or_(
                        (UserBlock.blocker_id == first) & (UserBlock.blocked_id == second),
                        (UserBlock.blocker_id == second) & (UserBlock.blocked_id == first),
                    )
                )
            )
            is not None
        )

    def list_friends(self, user_id: uuid.UUID) -> list[tuple[uuid.UUID, str | None]]:
        rows = list(
            self._session.scalars(
                select(Friendship).where(
                    Friendship.status == "ACCEPTED",
                    or_(
                        Friendship.user_low_id == user_id,
                        Friendship.user_high_id == user_id,
                    ),
                )
            )
        )
        result: list[tuple[uuid.UUID, str | None]] = []
        for row in rows:
            other = row.user_high_id if row.user_low_id == user_id else row.user_low_id
            profile = self._session.get(UserProfile, other)
            result.append((other, profile.display_name if profile else None))
        result.sort(key=lambda item: str(item[0]))
        return result

    def send_friend_request(
        self,
        actor_id: uuid.UUID,
        target_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> Friendship:
        if actor_id == target_id:
            raise CannotTargetSelf("não é possível adicionar a si mesmo")
        if self._session.get(User, target_id) is None:
            raise UserNotFound("usuário não encontrado")
        if self.is_blocked(actor_id, target_id):
            raise BlockedRelationship("relação bloqueada")

        low, high = ordered_pair(actor_id, target_id)
        existing = self._session.scalar(
            select(Friendship).where(
                Friendship.user_low_id == low,
                Friendship.user_high_id == high,
            )
        )
        moment = ensure_utc(now or utcnow())
        if existing is not None:
            if existing.status == "ACCEPTED":
                raise AlreadyFriends("já são amigos")
            if existing.status == "PENDING":
                if existing.requested_by == actor_id:
                    raise RequestAlreadyExists("solicitação já enviada")
                raise IncomingRequestExists("existe solicitação pendente do outro usuário")
            existing.status = "PENDING"
            existing.requested_by = actor_id
            existing.updated_at = moment
            self._session.flush()
            return existing

        friendship = Friendship(
            user_low_id=low,
            user_high_id=high,
            requested_by=actor_id,
            status="PENDING",
            created_at=moment,
            updated_at=moment,
        )
        self._session.add(friendship)
        self._session.flush()
        return friendship

    def accept_friend_request(
        self,
        request_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> Friendship:
        friendship = self._session.get(Friendship, request_id)
        if (
            friendship is None
            or friendship.status != "PENDING"
            or user_id not in (friendship.user_low_id, friendship.user_high_id)
            or friendship.requested_by == user_id
        ):
            raise FriendshipNotFound("solicitação não encontrada")
        if self.is_blocked(friendship.user_low_id, friendship.user_high_id):
            raise BlockedRelationship("relação bloqueada")
        friendship.status = "ACCEPTED"
        friendship.updated_at = ensure_utc(now or utcnow())
        self._session.flush()
        return friendship

    def remove_friend(
        self,
        user_id: uuid.UUID,
        other_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> Friendship:
        low, high = ordered_pair(user_id, other_id)
        friendship = self._session.scalar(
            select(Friendship).where(
                Friendship.user_low_id == low,
                Friendship.user_high_id == high,
                Friendship.status == "ACCEPTED",
            )
        )
        if friendship is None:
            raise FriendshipNotFound("amizade não encontrada")
        friendship.status = "REMOVED"
        friendship.updated_at = ensure_utc(now or utcnow())
        self._session.flush()
        return friendship

    def block(
        self,
        blocker_id: uuid.UUID,
        blocked_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> UserBlock:
        if blocker_id == blocked_id:
            raise CannotTargetSelf("não é possível bloquear a si mesmo")
        if self._session.get(User, blocked_id) is None:
            raise UserNotFound("usuário não encontrado")
        moment = ensure_utc(now or utcnow())
        existing = self._session.scalar(
            select(UserBlock).where(
                UserBlock.blocker_id == blocker_id,
                UserBlock.blocked_id == blocked_id,
            )
        )
        if existing is None:
            existing = UserBlock(
                blocker_id=blocker_id,
                blocked_id=blocked_id,
                created_at=moment,
            )
            self._session.add(existing)
        low, high = ordered_pair(blocker_id, blocked_id)
        friendship = self._session.scalar(
            select(Friendship).where(
                Friendship.user_low_id == low,
                Friendship.user_high_id == high,
            )
        )
        if friendship is not None and friendship.status != "REMOVED":
            friendship.status = "REMOVED"
            friendship.updated_at = moment
        invites = self._session.scalars(
            select(LobbyInvite).where(
                LobbyInvite.status == "PENDING",
                or_(
                    (LobbyInvite.inviter_id == blocker_id) & (LobbyInvite.invitee_id == blocked_id),
                    (LobbyInvite.inviter_id == blocked_id) & (LobbyInvite.invitee_id == blocker_id),
                ),
            )
        )
        for invite in invites:
            invite.status = "CANCELLED"
            invite.responded_at = moment
        self._session.flush()
        return existing

    def unblock(self, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> None:
        row = self._session.scalar(
            select(UserBlock).where(
                UserBlock.blocker_id == blocker_id,
                UserBlock.blocked_id == blocked_id,
            )
        )
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    # Convites ----------------------------------------------------------

    def invite_to_lobby(
        self,
        inviter_id: uuid.UUID,
        lobby_id: uuid.UUID,
        invitee_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> LobbyInvite:
        lobby = self._session.get(Lobby, lobby_id)
        if lobby is None or lobby.status != "scheduled":
            raise LobbyUnavailable("lobby indisponível")
        if not self._is_participant(lobby_id, inviter_id):
            raise LobbyUnavailable("usuário não participa do lobby")
        if inviter_id == invitee_id:
            raise CannotTargetSelf("não é possível convidar a si mesmo")
        if self.is_blocked(inviter_id, invitee_id):
            raise BlockedRelationship("relação bloqueada")
        if not self.are_friends(inviter_id, invitee_id):
            raise SocialError("convite exige amizade")
        if self._is_participant(lobby_id, invitee_id):
            raise InviteAlreadyExists("usuário já participa do lobby")
        if self._participant_count(lobby_id) >= self._capacity(lobby):
            raise LobbyFull("lobby sem vagas")

        moment = ensure_utc(now or utcnow())
        enforce_rate_limit(
            self._session,
            scope="lobby-invite",
            key=str(inviter_id),
            limit=INVITE_HOURLY_LIMIT,
            window_seconds=3600,
            now=moment,
        )
        invite = self._session.scalar(
            select(LobbyInvite).where(
                LobbyInvite.lobby_id == lobby_id,
                LobbyInvite.invitee_id == invitee_id,
            )
        )
        if invite is not None and invite.status in ("PENDING", "ACCEPTED"):
            raise InviteAlreadyExists("convite já existe")
        if invite is None:
            invite = LobbyInvite(
                lobby_id=lobby_id,
                inviter_id=inviter_id,
                invitee_id=invitee_id,
                status="PENDING",
                created_at=moment,
                expires_at=moment + INVITE_TTL,
            )
            self._session.add(invite)
        else:
            invite.inviter_id = inviter_id
            invite.status = "PENDING"
            invite.created_at = moment
            invite.expires_at = moment + INVITE_TTL
            invite.responded_at = None
        self._session.flush()
        OutboxService(self._session).enqueue(
            event_type="lobby.invite.created",
            aggregate_type="lobby",
            aggregate_id=lobby_id,
            payload={
                "invite_id": str(invite.id),
                "lobby_id": str(lobby_id),
                "inviter_id": str(inviter_id),
                "invitee_id": str(invitee_id),
                "expires_at": invite.expires_at.isoformat(),
            },
            now=moment,
        )
        return invite

    def respond_invite(
        self,
        invite_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        accept: bool,
        now: datetime | None = None,
    ) -> LobbyInvite:
        invite = self._session.get(LobbyInvite, invite_id)
        if invite is None or invite.invitee_id != user_id:
            raise InviteNotFound("convite não encontrado")
        if invite.status != "PENDING":
            raise InviteNotPending("convite não está pendente")
        moment = ensure_utc(now or utcnow())
        if ensure_utc(invite.expires_at) <= moment:
            invite.status = "EXPIRED"
            invite.responded_at = moment
            self._session.flush()
            raise InviteExpired("convite expirado")
        if not accept:
            invite.status = "DECLINED"
            invite.responded_at = moment
            self._session.flush()
            return invite

        if self.is_blocked(invite.inviter_id, invite.invitee_id):
            raise BlockedRelationship("relação bloqueada")
        lobby = self._session.get(Lobby, invite.lobby_id)
        if lobby is None or lobby.status != "scheduled":
            raise LobbyUnavailable("lobby indisponível")
        if self._is_participant(lobby.id, user_id):
            raise InviteAlreadyExists("usuário já participa do lobby")
        if self._participant_count(lobby.id) >= self._capacity(lobby):
            raise LobbyFull("lobby sem vagas")

        profile = self._session.scalar(
            select(UserSportProfile).where(
                UserSportProfile.user_id == user_id,
                UserSportProfile.format_id == lobby.format_id,
            )
        )
        teams = {
            team: int(
                self._session.scalar(
                    select(func.count())
                    .select_from(LobbyParticipant)
                    .where(
                        LobbyParticipant.lobby_id == lobby.id,
                        LobbyParticipant.team == team,
                    )
                )
                or 0
            )
            for team in (1, 2)
        }
        team = 1 if teams[1] <= teams[2] else 2
        self._session.add(
            LobbyParticipant(
                lobby_id=lobby.id,
                user_id=user_id,
                team=team,
                level=profile.level if profile else "beginner",
            )
        )
        invite.status = "ACCEPTED"
        invite.responded_at = moment
        self._session.flush()
        OutboxService(self._session).enqueue(
            event_type="lobby.invite.accepted",
            aggregate_type="lobby",
            aggregate_id=lobby.id,
            payload={
                "invite_id": str(invite.id),
                "lobby_id": str(lobby.id),
                "invitee_id": str(user_id),
                "team": team,
            },
            now=moment,
        )
        return invite

    def pending_invites(self, user_id: uuid.UUID) -> list[LobbyInvite]:
        return list(
            self._session.scalars(
                select(LobbyInvite)
                .where(
                    LobbyInvite.invitee_id == user_id,
                    LobbyInvite.status == "PENDING",
                )
                .order_by(LobbyInvite.created_at.desc())
            )
        )

    # Internos ----------------------------------------------------------

    def _is_participant(self, lobby_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return (
            self._session.scalar(
                select(LobbyParticipant.id).where(
                    LobbyParticipant.lobby_id == lobby_id,
                    LobbyParticipant.user_id == user_id,
                )
            )
            is not None
        )

    def _participant_count(self, lobby_id: uuid.UUID) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(LobbyParticipant)
                .where(LobbyParticipant.lobby_id == lobby_id)
            )
            or 0
        )

    def _capacity(self, lobby: Lobby) -> int:
        from app.modules.profile.models import SportFormat

        sport_format = self._session.get(SportFormat, lobby.format_id)
        if sport_format is None:
            raise LobbyUnavailable("formato indisponível")
        return sport_format.total_participants
