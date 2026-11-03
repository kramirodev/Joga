"""Adaptador de SMS. Nenhum provedor real é contatado nesta fase."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.modules.identity.clock import ensure_utc, utcnow


@dataclass(frozen=True)
class SmsMessage:
    """Mensagem registrada pelo adaptador simulado.

    O código fica fora do `repr` para reduzir o risco de vazamento em logs.
    """

    phone: str
    code: str = field(repr=False)
    purpose: str
    sent_at: datetime


class SmsSender(Protocol):
    """Contrato mínimo para envio de OTP."""

    def send_otp(self, *, phone: str, code: str, purpose: str) -> None: ...


class RecordingSmsSender:
    """Adaptador de desenvolvimento/teste; não entrega SMS real.

    Guarda as mensagens apenas em memória para permitir testes. Não usar em
    produção: o código deveria ir para o provedor autorizado, nunca para logs.
    """

    def __init__(self) -> None:
        self.messages: list[SmsMessage] = []

    def send_otp(self, *, phone: str, code: str, purpose: str) -> None:
        self.messages.append(
            SmsMessage(phone=phone, code=code, purpose=purpose, sent_at=ensure_utc(utcnow()))
        )

    def last_message(self) -> SmsMessage | None:
        return self.messages[-1] if self.messages else None
