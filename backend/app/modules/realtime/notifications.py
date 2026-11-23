"""Publicação de notificações no WebSocket local.

O registro de conexões vive no processo da API. O worker de push é outro
processo: ``manager.publish_user`` entrega apenas às conexões do próprio
processo e devolve 0. O histórico continua disponível em
``GET /me/notifications``; o app deve reconciliar ao reconectar. Um barramento
(Redis/fan-out) é o próximo passo documentado, não um canal inventado aqui.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from app.modules.realtime.manager import manager

logger = logging.getLogger("joga.notifications")

NOTIFICATION_EVENT = "notification.created"


def notification_event_payload(
    *,
    notification_id: object,
    kind: str,
    title: str,
    body: str,
    data: dict[str, str],
) -> dict[str, Any]:
    """Monta o contrato enviado ao app pelo WebSocket."""
    return {
        "type": NOTIFICATION_EVENT,
        "notification_id": None if notification_id is None else str(notification_id),
        "kind": kind,
        "title": title,
        "body": body,
        "data": data,
    }


async def publish_notification_event(
    user_id: uuid.UUID,
    payload: dict[str, Any],
) -> int:
    """Entrega best-effort no processo atual; nunca levanta erro de socket.

    ``ConnectionManager.publish_user`` já isola falhas por conexão. Esta função
    é o ponto testável para o caminho assíncrono (API embutida/no processo).
    """
    return await manager.publish_user(user_id, payload)


def publish_notification_event_sync(
    user_id: uuid.UUID,
    payload: dict[str, Any],
) -> int:
    """Adapta a publicação para código síncrono (worker e scripts).

    Só entrega se as conexões estiverem no mesmo processo e o loop for
    utilizável. Falha de entrega em tempo real nunca interrompe a Outbox: o
    retorno é a quantidade entregue (0 quando não há conexão acessível).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        # Dentro de um loop, ``asyncio.run`` falharia; o chamador async deve usar
        # ``publish_notification_event`` diretamente.
        return 0
    try:
        return asyncio.run(publish_notification_event(user_id, payload))
    except Exception:
        # Processo separado/troca de loop: o manager local não é o da API.
        logger.debug(
            "notificações: entrega em tempo real indisponível neste processo",
            exc_info=True,
        )
        return 0


__all__ = [
    "NOTIFICATION_EVENT",
    "notification_event_payload",
    "publish_notification_event",
    "publish_notification_event_sync",
]
