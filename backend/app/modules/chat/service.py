"""Chat textual por lobby, persistido antes da entrega."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.chat.models import LobbyMessage
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.matchmaking.models import Lobby, LobbyParticipant
from app.modules.outbox.service import OutboxService

MAX_MESSAGE_LENGTH = 2000


class ChatAccessDenied(Exception):
    """Usuário não participa do lobby."""


class ChatClosed(Exception):
    """Lobby não aceita novas mensagens."""


class InvalidMessage(Exception):
    """Mensagem vazia ou acima do limite."""


class ChatService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def is_participant(self, lobby_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return (
            self._session.scalar(
                select(LobbyParticipant.id).where(
                    LobbyParticipant.lobby_id == lobby_id,
                    LobbyParticipant.user_id == user_id,
                )
            )
            is not None
        )

    def list_messages(
        self,
        lobby_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[LobbyMessage]:
        if not self.is_participant(lobby_id, user_id):
            raise ChatAccessDenied("acesso ao chat negado")
        if limit <= 0 or limit > 100:
            raise ValueError("limit inválido")
        statement = select(LobbyMessage).where(LobbyMessage.lobby_id == lobby_id)
        if before is not None:
            statement = statement.where(LobbyMessage.created_at < ensure_utc(before))
        rows = list(
            self._session.scalars(statement.order_by(LobbyMessage.created_at.desc()).limit(limit))
        )
        rows.reverse()
        return rows

    def send_message(
        self,
        lobby_id: uuid.UUID,
        user_id: uuid.UUID,
        body: str,
        *,
        now: datetime | None = None,
    ) -> LobbyMessage:
        if not self.is_participant(lobby_id, user_id):
            raise ChatAccessDenied("acesso ao chat negado")
        lobby = self._session.get(Lobby, lobby_id)
        if lobby is None or lobby.status != "scheduled":
            raise ChatClosed("lobby não aceita mensagens")
        if not body.strip():
            raise InvalidMessage("mensagem vazia")
        if len(body) > MAX_MESSAGE_LENGTH:
            raise InvalidMessage("mensagem acima do limite")

        moment = ensure_utc(now or utcnow())
        message = LobbyMessage(
            lobby_id=lobby_id,
            sender_id=user_id,
            body=body,
            created_at=moment,
        )
        self._session.add(message)
        self._session.flush()
        OutboxService(self._session).enqueue(
            event_type="lobby.message.created",
            aggregate_type="lobby",
            aggregate_id=lobby_id,
            payload={
                "message_id": str(message.id),
                "lobby_id": str(lobby_id),
                "sender_id": str(user_id),
                "body": body,
                "created_at": moment.isoformat(),
            },
            now=moment,
        )
        return message
