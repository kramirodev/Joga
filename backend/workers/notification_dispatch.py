"""Worker de entrega de notificações: Outbox -> Expo Push + WebSocket.

Rodar como processo separado:

    python -m workers.notification_dispatch

O intervalo vem de ``JOGA_NOTIFICATION_DISPATCH_INTERVAL_SECONDS``. Sem
``JOGA_EXPO_PUSH_URL`` o worker não altera a Outbox: não há entrega fingida.
"""

from __future__ import annotations

import logging
import signal
import threading
from collections.abc import Callable
from datetime import datetime
from types import FrameType

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_engine, get_session_factory
from app.modules.identity.clock import utcnow
from app.modules.notifications.dispatch import (
    DEFAULT_RETRY_SECONDS,
    DispatchReport,
    NotificationPublisher,
    dispatch_notifications,
)
from app.modules.push.expo import build_expo_push_sender
from app.modules.push.service import PushSender
from app.modules.realtime.notifications import publish_notification_event_sync

logger = logging.getLogger("joga.notifications")

SenderFactory = Callable[[Settings], PushSender | None]


class NotificationDispatchWorker:
    """Loop de drenagem; cada ciclo abre e fecha uma sessão curta."""

    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: sessionmaker[Session],
        sender_factory: SenderFactory = build_expo_push_sender,
        publisher: NotificationPublisher | None = publish_notification_event_sync,
        stop_event: threading.Event | None = None,
        interval_seconds: int | None = None,
        retry_in_seconds: int = DEFAULT_RETRY_SECONDS,
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        interval = (
            settings.notification_dispatch_interval_seconds
            if interval_seconds is None
            else interval_seconds
        )
        if interval < 1:
            raise ValueError("intervalo do dispatcher deve ser de ao menos 1 segundo")
        self._settings = settings
        self._session_factory = session_factory
        self._sender_factory = sender_factory
        self._publisher = publisher
        self._stop = stop_event or threading.Event()
        self._interval = interval
        self._retry_in_seconds = max(0, retry_in_seconds)
        self._now = now
        self._sender_unavailable = False

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        stop_event: threading.Event | None = None,
    ) -> NotificationDispatchWorker:
        return cls(
            settings,
            session_factory=get_session_factory(),
            stop_event=stop_event,
        )

    def run_cycle(self) -> DispatchReport | None:
        """Executa um ciclo bloqueante; chamar fora do event loop."""
        if self._sender_unavailable:
            return None
        sender = self._sender_factory(self._settings)
        if sender is None:
            self._sender_unavailable = True
            logger.warning("push: nenhum provedor configurado; ciclos desativados até reiniciar")
            return None
        report: DispatchReport
        try:
            with self._session_factory() as session:
                try:
                    report = dispatch_notifications(
                        session,
                        sender,
                        publisher=self._publisher,
                        retry_in_seconds=self._retry_in_seconds,
                        now=self._now(),
                    )
                    session.commit()
                except Exception:
                    session.rollback()
                    logger.exception("push: ciclo falhou; Outbox preservada")
                    return None
        finally:
            sender.close()
        logger.info(
            "push: eventos=%s entregues=%s sem_token=%s ignorados=%s "
            "falhas=%s revogados=%s tempo_real=%s",
            report.processed,
            report.delivered,
            report.no_tokens,
            report.skipped,
            report.failed,
            report.revoked,
            report.published,
        )
        return report

    def run(self, *, max_cycles: int | None = None) -> None:
        """Loop com parada graciosa; ``max_cycles`` existe para testes."""
        if max_cycles is not None and max_cycles < 1:
            raise ValueError("max_cycles deve ser positivo")
        cycles = 0
        while not self._stop.is_set():
            try:
                self.run_cycle()
            except Exception:
                logger.exception("push: ciclo inesperado falhou; nova tentativa no próximo")
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            if self._stop.wait(self._interval):
                break
        logger.info("push: worker encerrado")


def _install_stop_handlers(stop: threading.Event) -> None:
    def _handle(signum: int, _frame: FrameType | None) -> None:
        logger.info("push: sinal %s recebido; encerrando após o ciclo atual", signum)
        stop.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)


def main() -> int:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    stop = threading.Event()
    _install_stop_handlers(stop)
    try:
        NotificationDispatchWorker.from_settings(settings, stop_event=stop).run()
    finally:
        get_engine().dispose()
    return 0


__all__ = ["NotificationDispatchWorker", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
