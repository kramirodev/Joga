"""Amizades, bloqueios e convites de lobby."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from re import fullmatch
from typing import Literal

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.text import escape_like
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import User
from app.modules.matchmaking.models import Lobby, LobbyParticipant
from app.modules.notifications.service import NotificationService
from app.modules.outbox.service import OutboxService
from app.modules.profile.models import UserProfile, UserSportProfile
from app.modules.ratelimit.service import enforce as enforce_rate_limit
from app.modules.social.models import Friendship, LobbyInvite, UserBlock

INVITE_TTL = timedelta(hours=24)
INVITE_HOURLY_LIMIT = 20
FRIEND_REQUEST_HOURLY_LIMIT = 20
FRIEND_REQUEST_DIRECTIONS = ("incoming", "outgoing", "all")
FRIEND_REQUEST_FILTERS = ("pending", "history")
PLAYER_SEARCH_HOURLY_LIMIT = 60
PLAYER_SEARCH_MAX_RESULTS = 50
PLAYER_SEARCH_MIN_QUERY = 3
PLAYER_SEARCH_MAX_QUERY = 40

PlayerRelation = Literal["friend", "incoming_request", "outgoing_request", "none"]


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
    """Pedido pendente na direção oposta; o id permite aceitar direto."""

    def __init__(self, message: str, friendship_id: uuid.UUID) -> None:
        super().__init__(message)
        self.friendship_id = friendship_id


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


class InvalidPlayerSearch(SocialError):
    """Consulta de jogador vazia, curta demais ou com limite inválido."""


@dataclass(frozen=True)
class PlayerSearchEntry:
    """Resultado mínimo da busca pública de jogador (sem PII sensível)."""

    user_id: uuid.UUID
    display_name: str | None
    tag: str
    relation: PlayerRelation


@dataclass(frozen=True)
class FriendEntry:
    """Amigo ou bloqueado na visão de quem consulta, sem PII."""

    user_id: uuid.UUID
    display_name: str | None
    tag: str


@dataclass(frozen=True)
class FriendRequestEntry:
    """Pedido de amizade na visão de um dos participantes."""

    id: uuid.UUID
    counterpart_id: uuid.UUID
    counterpart_name: str | None
    counterpart_tag: str
    direction: Literal["incoming", "outgoing"]
    status: str
    created_at: datetime
    responded_at: datetime | None


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

    def list_friends(self, user_id: uuid.UUID) -> list[FriendEntry]:
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
        other_ids = [
            row.user_high_id if row.user_low_id == user_id else row.user_low_id for row in rows
        ]
        labels = self._player_labels(other_ids)
        result = [
            FriendEntry(
                user_id=other_id,
                display_name=labels.get(other_id, (None, ""))[0],
                tag=labels.get(other_id, (None, ""))[1],
            )
            for other_id in other_ids
        ]
        result.sort(key=lambda item: str(item.user_id))
        return result

    def list_blocks(self, user_id: uuid.UUID) -> list[FriendEntry]:
        rows = list(
            self._session.scalars(
                select(UserBlock)
                .where(UserBlock.blocker_id == user_id)
                .order_by(UserBlock.created_at.desc(), UserBlock.id.desc())
            )
        )
        labels = self._player_labels([row.blocked_id for row in rows])
        return [
            FriendEntry(
                user_id=row.blocked_id,
                display_name=labels.get(row.blocked_id, (None, ""))[0],
                tag=labels.get(row.blocked_id, (None, ""))[1],
            )
            for row in rows
        ]

    def search_players(
        self,
        user_id: uuid.UUID,
        query: str,
        *,
        limit: int = 20,
        now: datetime | None = None,
    ) -> list[PlayerSearchEntry]:
        """Busca por nome parcial ou tag exata, sem vazar PII.

        Consultas com ``#`` (``nome#TAG`` ou ``#TAG``) casam a tag exata;
        uma consulta que seja apenas 8/10/12 hexadecimais também é tag. As
        demais buscam ``display_name`` com ``ILIKE`` escapado. Bloqueios em
        qualquer direção, o próprio usuário e contas não ativas ficam fora do
        resultado.
        """

        term = " ".join(query.split())
        if len(term) < PLAYER_SEARCH_MIN_QUERY or len(term) > PLAYER_SEARCH_MAX_QUERY:
            raise InvalidPlayerSearch("consulta deve ter entre 3 e 40 caracteres")
        if limit < 1 or limit > PLAYER_SEARCH_MAX_RESULTS:
            raise InvalidPlayerSearch("limite de resultados inválido")

        moment = ensure_utc(now or utcnow())
        enforce_rate_limit(
            self._session,
            scope="user-search",
            key=str(user_id),
            limit=PLAYER_SEARCH_HOURLY_LIMIT,
            window_seconds=3600,
            now=moment,
        )

        blocked_either_direction = exists().where(
            or_(
                (UserBlock.blocker_id == user_id) & (UserBlock.blocked_id == User.id),
                (UserBlock.blocker_id == User.id) & (UserBlock.blocked_id == user_id),
            )
        )
        statement = (
            select(User.id, User.tag, UserProfile.display_name)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(
                User.status == "active",
                User.id != user_id,
                ~blocked_either_direction,
            )
        )

        if "#" in term:
            tag = term.rsplit("#", 1)[1].strip()
            if not tag:
                raise InvalidPlayerSearch("tag vazia na consulta")
            statement = statement.where(User.tag == f"#{tag.upper()}")
        elif fullmatch(r"[0-9A-Fa-f]{8}(?:[0-9A-Fa-f]{2}){0,2}", term):
            statement = statement.where(User.tag == f"#{term.upper()}")
        else:
            # Nomes são canônicos em maiúsculas; elevar o termo em Python também
            # mantém a busca correta no SQLite dos testes, cujo lower/upper é ASCII.
            pattern = f"%{escape_like(term.upper())}%"
            statement = statement.where(UserProfile.display_name.ilike(pattern, escape="\\"))

        rows = self._session.execute(
            statement.order_by(UserProfile.display_name.asc(), User.id.asc()).limit(limit)
        ).all()
        relations = self._relations_for(user_id, [row.id for row in rows])
        return [
            PlayerSearchEntry(
                user_id=row.id,
                display_name=row.display_name,
                tag=row.tag,
                relation=relations.get(row.id, "none"),
            )
            for row in rows
        ]

    def list_friend_requests(
        self,
        user_id: uuid.UUID,
        *,
        direction: Literal["incoming", "outgoing", "all"] = "incoming",
        status: Literal["pending", "history"] = "pending",
    ) -> list[FriendRequestEntry]:
        if direction not in FRIEND_REQUEST_DIRECTIONS:
            raise ValueError("direção de pedidos inválida")
        if status not in FRIEND_REQUEST_FILTERS:
            raise ValueError("filtro de pedidos inválido")

        statement = select(Friendship).where(
            or_(
                Friendship.user_low_id == user_id,
                Friendship.user_high_id == user_id,
            )
        )
        if direction == "incoming":
            statement = statement.where(Friendship.requested_by != user_id)
        elif direction == "outgoing":
            statement = statement.where(Friendship.requested_by == user_id)
        if status == "pending":
            statement = statement.where(Friendship.status == "PENDING")
        else:
            statement = statement.where(Friendship.status != "PENDING")

        rows = list(
            self._session.scalars(
                statement.order_by(Friendship.created_at.desc(), Friendship.id.desc())
            )
        )
        result: list[FriendRequestEntry] = []
        labels = self._player_labels(
            [row.user_high_id if row.user_low_id == user_id else row.user_low_id for row in rows]
        )
        for row in rows:
            counterpart = row.user_high_id if row.user_low_id == user_id else row.user_low_id
            display_name, tag = labels.get(counterpart, (None, ""))
            result.append(
                FriendRequestEntry(
                    id=row.id,
                    counterpart_id=counterpart,
                    counterpart_name=display_name,
                    counterpart_tag=tag,
                    direction="outgoing" if row.requested_by == user_id else "incoming",
                    status=row.status,
                    created_at=row.created_at,
                    responded_at=row.responded_at,
                )
            )
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
        moment = ensure_utc(now or utcnow())
        existing = self._find_friendship(low, high, for_update=True)
        if existing is not None:
            return self._resume_friend_request(existing, actor_id, target_id, moment)

        self._enforce_friend_request_limit(actor_id, moment)
        try:
            friendship = self._insert_friendship(low, high, actor_id, moment)
        except IntegrityError:
            # Outra requisição criou o mesmo par entre a leitura e o INSERT.
            existing = self._find_friendship(low, high, for_update=True)
            if existing is None:
                raise
            return self._resume_friend_request(
                existing,
                actor_id,
                target_id,
                moment,
                enforce_limit=False,
            )
        self._notify_friend_request(friendship, actor_id, target_id, moment)
        return friendship

    def accept_friend_request(
        self,
        request_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> Friendship:
        friendship = self._session.get(Friendship, request_id, with_for_update=True)
        if (
            friendship is None
            or friendship.status != "PENDING"
            or user_id not in (friendship.user_low_id, friendship.user_high_id)
            or friendship.requested_by == user_id
        ):
            raise FriendshipNotFound("solicitação não encontrada")
        if self.is_blocked(friendship.user_low_id, friendship.user_high_id):
            raise BlockedRelationship("relação bloqueada")
        moment = ensure_utc(now or utcnow())
        friendship.status = "ACCEPTED"
        friendship.responded_at = moment
        friendship.updated_at = moment
        self._session.flush()
        self._notify(
            user_id=friendship.requested_by,
            kind="friend_accepted",
            title="Pedido de amizade aceito",
            body="Seu pedido de amizade foi aceito.",
            friendship=friendship,
            counterpart_id=user_id,
            moment=moment,
        )
        return friendship

    def decline_friend_request(
        self,
        request_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> Friendship:
        friendship = self._session.get(Friendship, request_id, with_for_update=True)
        if (
            friendship is None
            or friendship.status != "PENDING"
            or user_id not in (friendship.user_low_id, friendship.user_high_id)
            or friendship.requested_by == user_id
        ):
            raise FriendshipNotFound("solicitação não encontrada")
        moment = ensure_utc(now or utcnow())
        friendship.status = "DECLINED"
        friendship.responded_at = moment
        friendship.updated_at = moment
        self._session.flush()
        self._notify(
            user_id=friendship.requested_by,
            kind="friend_declined",
            title="Pedido de amizade recusado",
            body="Seu pedido de amizade foi recusado.",
            friendship=friendship,
            counterpart_id=user_id,
            moment=moment,
        )
        return friendship

    def cancel_friend_request(
        self,
        request_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> Friendship:
        friendship = self._session.get(Friendship, request_id, with_for_update=True)
        if (
            friendship is None
            or friendship.status != "PENDING"
            or user_id not in (friendship.user_low_id, friendship.user_high_id)
            or friendship.requested_by != user_id
        ):
            raise FriendshipNotFound("solicitação não encontrada")
        moment = ensure_utc(now or utcnow())
        friendship.status = "CANCELLED"
        friendship.responded_at = moment
        friendship.updated_at = moment
        self._session.flush()
        self._notify(
            user_id=friendship.user_low_id
            if friendship.user_high_id == user_id
            else friendship.user_high_id,
            kind="friend_cancelled",
            title="Pedido de amizade cancelado",
            body="Um pedido de amizade enviado a você foi cancelado.",
            friendship=friendship,
            counterpart_id=user_id,
            moment=moment,
        )
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

    def relation_with(self, actor_id: uuid.UUID, counterpart_id: uuid.UUID) -> PlayerRelation:
        """Relação social do ator com um jogador, em uma única consulta."""

        return self._relations_for(actor_id, [counterpart_id]).get(counterpart_id, "none")

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

    def _player_labels(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[str | None, str]]:
        """Nome e tag pública de cada usuário, em uma única consulta."""

        unique_ids = list(dict.fromkeys(user_ids))
        if not unique_ids:
            return {}
        rows = self._session.execute(
            select(User.id, User.tag, UserProfile.display_name)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(User.id.in_(unique_ids))
        ).all()
        return {row.id: (row.display_name, row.tag) for row in rows}

    def _relations_for(
        self, actor_id: uuid.UUID, counterpart_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, PlayerRelation]:
        """Relação do ator com cada resultado, em uma única consulta."""

        if not counterpart_ids:
            return {}
        rows = self._session.execute(
            select(
                Friendship.user_low_id,
                Friendship.user_high_id,
                Friendship.requested_by,
                Friendship.status,
            ).where(
                Friendship.status.in_(("ACCEPTED", "PENDING")),
                or_(
                    (Friendship.user_low_id == actor_id)
                    & Friendship.user_high_id.in_(counterpart_ids),
                    (Friendship.user_high_id == actor_id)
                    & Friendship.user_low_id.in_(counterpart_ids),
                ),
            )
        ).all()
        priority: dict[PlayerRelation, int] = {
            "none": 0,
            "incoming_request": 1,
            "outgoing_request": 1,
            "friend": 2,
        }
        relations: dict[uuid.UUID, PlayerRelation] = {}
        for low, high, requested_by, status in rows:
            other = high if low == actor_id else low
            if status == "ACCEPTED":
                relation: PlayerRelation = "friend"
            elif requested_by == actor_id:
                relation = "outgoing_request"
            else:
                relation = "incoming_request"
            current = relations.get(other, "none")
            if priority[relation] > priority[current]:
                relations[other] = relation
        return relations

    def _find_friendship(
        self,
        low: uuid.UUID,
        high: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> Friendship | None:
        statement = select(Friendship).where(
            Friendship.user_low_id == low,
            Friendship.user_high_id == high,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def _insert_friendship(
        self,
        low: uuid.UUID,
        high: uuid.UUID,
        actor_id: uuid.UUID,
        moment: datetime,
    ) -> Friendship:
        friendship = Friendship(
            user_low_id=low,
            user_high_id=high,
            requested_by=actor_id,
            status="PENDING",
            created_at=moment,
            updated_at=moment,
        )
        with self._session.begin_nested():
            self._session.add(friendship)
            self._session.flush()
        return friendship

    def _resume_friend_request(
        self,
        friendship: Friendship,
        actor_id: uuid.UUID,
        target_id: uuid.UUID,
        moment: datetime,
        *,
        enforce_limit: bool = True,
    ) -> Friendship:
        if friendship.status == "ACCEPTED":
            raise AlreadyFriends("já são amigos")
        if friendship.status == "PENDING":
            if friendship.requested_by == actor_id:
                # Reenvio do mesmo autor é idempotente: mesma linha, sem notificação nova.
                return friendship
            raise IncomingRequestExists(
                "existe solicitação pendente do outro usuário",
                friendship.id,
            )

        if enforce_limit:
            self._enforce_friend_request_limit(actor_id, moment)
        friendship.status = "PENDING"
        friendship.requested_by = actor_id
        # O pedido reaberto passa a valer como novo para listagem e ordenação.
        friendship.created_at = moment
        friendship.updated_at = moment
        friendship.responded_at = None
        self._session.flush()
        self._notify_friend_request(friendship, actor_id, target_id, moment)
        return friendship

    def _enforce_friend_request_limit(self, actor_id: uuid.UUID, moment: datetime) -> None:
        enforce_rate_limit(
            self._session,
            scope="friend-request",
            key=str(actor_id),
            limit=FRIEND_REQUEST_HOURLY_LIMIT,
            window_seconds=3600,
            now=moment,
        )

    def _notify_friend_request(
        self,
        friendship: Friendship,
        actor_id: uuid.UUID,
        target_id: uuid.UUID,
        moment: datetime,
    ) -> None:
        display_name, _tag = self._player_labels([actor_id]).get(actor_id, (None, ""))
        self._notify(
            user_id=target_id,
            kind="friend_request_received",
            title="Novo pedido de amizade",
            body=f"{display_name or 'Um jogador'} quer ser seu amigo.",
            friendship=friendship,
            counterpart_id=actor_id,
            moment=moment,
        )

    def _notify(
        self,
        *,
        user_id: uuid.UUID,
        kind: str,
        title: str,
        body: str,
        friendship: Friendship,
        counterpart_id: uuid.UUID,
        moment: datetime,
    ) -> None:
        counterpart_name, counterpart_tag = self._player_labels([counterpart_id]).get(
            counterpart_id, (None, "")
        )
        # A chave carrega o destinatário: NotificationService.create procura a
        # chave globalmente e não pode engolir a notificação de outro usuário.
        NotificationService(self._session).create(
            user_id=user_id,
            kind=kind,
            title=title,
            body=body,
            idempotency_key=f"{kind}:{user_id}:{friendship.id}:{moment.isoformat()}",
            data={
                "friendship_id": str(friendship.id),
                "counterpart_id": str(counterpart_id),
                "counterpart_name": counterpart_name,
                "counterpart_tag": counterpart_tag,
            },
            now=moment,
        )

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
