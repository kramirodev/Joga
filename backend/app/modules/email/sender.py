"""Provedores de e-mail transacional (Brevo, Resend e fake de teste).

O adaptador nunca registra corpo, código ou endereço em log. Mensagens de erro
do provedor não são propagadas: apenas um código interno estável é exposto ao
log de entrega.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

import httpx

from app.modules.email.addresses import normalize_email

if TYPE_CHECKING:  # pragma: no cover - apenas tipagem
    from app.core.config import Settings

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
RESEND_ENDPOINT = "https://api.resend.com/emails"


@dataclass(frozen=True)
class EmailMessage:
    """Mensagem já renderizada.

    ``code`` existe apenas para o adaptador de teste recuperar o código sem
    analisar o corpo; os provedores reais ignoram esse campo.
    """

    to: str
    subject: str
    text: str
    html: str
    kind: str
    code: str | None = field(default=None, repr=False)


class EmailSenderError(Exception):
    """Falha de entrega classificada; nunca contém corpo do provedor."""

    def __init__(self, code: str, *, permanent: bool) -> None:
        super().__init__(code)
        self.code = code
        self.permanent = permanent


class EmailSender(Protocol):
    """Contrato mínimo de entrega de um e-mail já renderizado."""

    @property
    def provider(self) -> str: ...

    def send(self, message: EmailMessage) -> str | None: ...

    def close(self) -> None: ...


class FakeSender:
    """Adaptador de teste; não abre socket e guarda mensagens em memória."""

    def __init__(
        self,
        *,
        failures: list[tuple[str, bool]] | None = None,
    ) -> None:
        self._failures = list(failures or [])
        self.sent: list[EmailMessage] = []
        self.attempts: list[EmailMessage] = []

    @property
    def provider(self) -> str:
        return "fake"

    def send(self, message: EmailMessage) -> str | None:
        self.attempts.append(message)
        if self._failures:
            code, permanent = self._failures.pop(0)
            raise EmailSenderError(code, permanent=permanent)
        self.sent.append(message)
        return f"fake-{len(self.sent)}"

    def close(self) -> None:
        return None

    def last_message(self) -> EmailMessage | None:
        return self.sent[-1] if self.sent else None


class _HttpSender:
    """Base comum para provedores HTTP, com um único POST por tentativa."""

    provider = "http"

    def __init__(
        self,
        *,
        api_key: str,
        from_email: str,
        from_name: str,
        reply_to: str | None = None,
        timeout_seconds: float = 10,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key de e-mail não pode ser vazio")
        self._api_key = api_key
        self._from_email = from_email
        self._from_name = from_name
        self._reply_to = reply_to or None
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def send(self, message: EmailMessage) -> str | None:
        try:
            response = self._client.post(
                self._endpoint(),
                headers=self._headers(),
                json=self._payload(message),
            )
        except httpx.TimeoutException as error:
            raise EmailSenderError("timeout", permanent=False) from error
        except httpx.HTTPError as error:
            raise EmailSenderError("transport_error", permanent=False) from error

        if not response.is_success:
            raise _classify(response.status_code)
        try:
            payload = response.json()
        except ValueError:
            return None
        return _message_id(payload)

    def _endpoint(self) -> str:
        raise NotImplementedError

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    def _payload(self, message: EmailMessage) -> dict[str, object]:
        raise NotImplementedError


class BrevoSender(_HttpSender):
    """Brevo (ex-Sendinblue) é o provedor padrão do beta."""

    provider = "brevo"

    def __init__(
        self,
        *,
        api_key: str,
        from_email: str,
        from_name: str,
        reply_to: str | None = None,
        timeout_seconds: float = 10,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            timeout_seconds=timeout_seconds,
            client=client,
        )

    def _endpoint(self) -> str:
        return BREVO_ENDPOINT

    def _headers(self) -> dict[str, str]:
        return {"api-key": self._api_key, "accept": "application/json"}

    def _payload(self, message: EmailMessage) -> dict[str, object]:
        payload: dict[str, object] = {
            "sender": {"email": self._from_email, "name": self._from_name},
            "to": [{"email": message.to}],
            "subject": message.subject,
            "htmlContent": message.html,
            "textContent": message.text,
        }
        if self._reply_to:
            payload["replyTo"] = {"email": self._reply_to}
        return payload


class ResendSender(_HttpSender):
    """Resend exige domínio verificado; alternativa ao Brevo."""

    provider = "resend"

    def __init__(
        self,
        *,
        api_key: str,
        from_email: str,
        from_name: str,
        reply_to: str | None = None,
        timeout_seconds: float = 10,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            timeout_seconds=timeout_seconds,
            client=client,
        )

    def _endpoint(self) -> str:
        return RESEND_ENDPOINT

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _payload(self, message: EmailMessage) -> dict[str, object]:
        payload: dict[str, object] = {
            "from": f"{self._from_name} <{self._from_email}>",
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
        }
        if self._reply_to:
            payload["reply_to"] = self._reply_to
        return payload


def _classify(status_code: int) -> EmailSenderError:
    if status_code == 429:
        return EmailSenderError("provider_rate_limited", permanent=False)
    if status_code == 401 or status_code == 403:
        return EmailSenderError("provider_auth_failed", permanent=True)
    if 400 <= status_code < 500:
        return EmailSenderError("provider_rejected", permanent=True)
    return EmailSenderError("provider_unavailable", permanent=False)


def _message_id(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("messageId", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value[:120]
    return None


def build_email_sender(settings: Settings) -> EmailSender | None:
    """Constrói o provedor configurado; ``None`` desabilita o envio."""
    provider = settings.email_provider
    if provider == "none":
        return None
    if provider == "fake":
        return FakeSender()

    api_key = (
        settings.email_api_key.get_secret_value().strip()
        if settings.email_api_key is not None
        else ""
    )
    from_email = normalize_email((settings.email_from or "").strip())
    reply_to = (
        normalize_email(settings.email_reply_to)
        if settings.email_reply_to and settings.email_reply_to.strip()
        else None
    )
    timeout_seconds = float(settings.email_timeout_seconds)
    if provider == "brevo":
        return BrevoSender(
            api_key=api_key,
            from_email=from_email,
            from_name=settings.email_from_name,
            reply_to=reply_to,
            timeout_seconds=timeout_seconds,
        )
    return ResendSender(
        api_key=api_key,
        from_email=from_email,
        from_name=settings.email_from_name,
        reply_to=reply_to,
        timeout_seconds=timeout_seconds,
    )


__all__ = [
    "BREVO_ENDPOINT",
    "RESEND_ENDPOINT",
    "BrevoSender",
    "EmailMessage",
    "EmailSender",
    "EmailSenderError",
    "FakeSender",
    "ResendSender",
    "build_email_sender",
]
