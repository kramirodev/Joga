"""Adaptador do Expo Push Service (Onda 1.8).

O Expo recebe a mensagem e entrega via FCM/APNs. O adaptador nunca registra o
access token, o token do dispositivo ou o corpo devolvido pelo provedor: para
a Outbox só sai um código interno estável.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.modules.push.service import (
    PushError,
    PushMessage,
    PushSender,
    PushTicket,
    build_webhook_push_sender,
)

logger = logging.getLogger("joga.notifications")

DEFAULT_EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
MAX_BATCH_SIZE = 100

# Apenas códigos conhecidos do Expo viram ``last_error``. Qualquer outro vira
# ``push_error`` para não persistir texto arbitrário do provedor.
SAFE_TICKET_ERRORS = frozenset(
    {
        "DeviceNotRegistered",
        "InvalidPushToken",
        "InvalidCredentials",
        "InvalidProviderPayload",
        "InvalidProviderToken",
        "MessageRateExceeded",
        "MessageTooBig",
        "MismatchSenderId",
    }
)


class ExpoPushSender:
    """Envia lotes de mensagens para ``/--/api/v2/push/send``."""

    def __init__(
        self,
        url: str,
        *,
        access_token: str | None = None,
        timeout_seconds: int = 10,
        client: httpx.Client | None = None,
        max_batch_size: int = MAX_BATCH_SIZE,
    ) -> None:
        if max_batch_size < 1:
            raise ValueError("max_batch_size deve ser positivo")
        self.url = url
        self._access_token = access_token or None
        self._max_batch_size = max_batch_size
        # ``trust_env=False``: o worker não deve herdar proxy/CA do ambiente do
        # host por acidente. O timeout evita bloqueio indefinido do ciclo.
        self._client = client or httpx.Client(timeout=timeout_seconds, trust_env=False)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def send_batch(self, messages: Sequence[PushMessage]) -> list[PushTicket]:
        tickets: list[PushTicket] = []
        for start in range(0, len(messages), self._max_batch_size):
            chunk = list(messages[start : start + self._max_batch_size])
            tickets.extend(self._send_chunk(chunk))
        return tickets

    def _send_chunk(self, messages: list[PushMessage]) -> list[PushTicket]:
        if not messages:
            return []
        try:
            response = self._client.post(
                self.url,
                json=[self._message_body(message) for message in messages],
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            raise PushError("push_unavailable") from exc
        if response.status_code >= 400:
            raise PushError(_http_error_code(response.status_code))
        try:
            body: Any = response.json()
        except ValueError as exc:
            raise PushError("push_invalid_response") from exc
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict):
            # A Expo devolve objeto quando a requisição tinha uma mensagem só.
            data = [data]
        if not isinstance(data, list) or len(data) != len(messages):
            raise PushError("push_invalid_response")
        return [_ticket(message.token, item) for message, item in zip(messages, data, strict=True)]

    def _message_body(self, message: PushMessage) -> dict[str, object]:
        body: dict[str, object] = {
            "to": message.token,
            "title": message.title,
            "body": message.body,
            "data": message.data,
            "sound": "default",
        }
        if message.channel_id:
            body["channelId"] = message.channel_id
        return body

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers


def _ticket(token: str, item: object) -> PushTicket:
    if not isinstance(item, dict):
        return PushTicket(token=token, ok=False, error="push_invalid_response")
    if item.get("status") == "ok":
        ticket_id = item.get("id")
        return PushTicket(
            token=token,
            ok=True,
            ticket_id=ticket_id if isinstance(ticket_id, str) else None,
        )
    details = item.get("details")
    code = details.get("error") if isinstance(details, dict) else None
    safe_code = code if isinstance(code, str) and code in SAFE_TICKET_ERRORS else "push_error"
    return PushTicket(token=token, ok=False, error=safe_code)


def _http_error_code(status_code: int) -> str:
    if status_code == 429:
        return "push_rate_limited"
    if status_code in {401, 403}:
        return "push_unauthorized"
    if status_code >= 500:
        return "push_unavailable"
    if status_code == 400:
        return "push_rejected"
    return f"push_http_{status_code}"


def build_expo_push_sender(settings: Settings | None = None) -> ExpoPushSender | None:
    """Cria o adaptador quando ``JOGA_EXPO_PUSH_URL`` está configurada."""
    resolved = settings or get_settings()
    if not resolved.expo_push_url:
        return None
    return ExpoPushSender(
        resolved.expo_push_url,
        access_token=resolved.expo_access_token_value,
        timeout_seconds=resolved.push_timeout_seconds,
    )


def build_push_sender(settings: Settings | None = None) -> PushSender | None:
    """Expo quando configurado; webhook legado como alternativa operacional."""
    sender = build_expo_push_sender(settings)
    if sender is not None:
        return sender
    return build_webhook_push_sender()


__all__ = [
    "DEFAULT_EXPO_PUSH_URL",
    "MAX_BATCH_SIZE",
    "SAFE_TICKET_ERRORS",
    "ExpoPushSender",
    "build_expo_push_sender",
    "build_push_sender",
]
