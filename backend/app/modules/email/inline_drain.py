"""Drenagem da Outbox de e-mail no processo da API.

O Render free não mantém worker dedicado e o cron do GitHub Actions é
best-effort. Com ``JOGA_EMAIL_INLINE_DRAIN_ENABLED=true`` a API drena a Outbox
enquanto estiver acordada, usando o mesmo advisory lock do worker agendado para
não duplicar envio. O workflow continua existindo como caminho de reserva.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Self

from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.infrastructure.database.dependency import get_engine, get_session_factory
from app.modules.email.dispatcher import DeliveryReport, dispatch_email_deliveries
from app.modules.email.drain_lock import email_drain_lock
from app.modules.email.models import EmailDelivery
from app.modules.email.sender import EmailSender, build_email_sender
from app.modules.identity.clock import ensure_utc, utcnow

logger = logging.getLogger("joga.email")

TASK_NAME = "joga-email-inline-drain"
MIN_INTERVAL_SECONDS = 10
MAX_INTERVAL_SECONDS = 300


def percentile(values: list[float], fraction: float) -> float:
    """Percentil por interpolação linear; evita depender de função do dialeto."""
    if not values:
        raise ValueError("percentil exige ao menos uma amostra")
    if not 0 <= fraction <= 1:
        raise ValueError("fraction deve estar entre 0 e 1")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def delivery_latency_percentiles(
    session: Session,
    *,
    day_start: datetime,
) -> tuple[int, float, float]:
    """Latência (segundos) entre a criação do evento e o envio aceito, no dia."""
    rows = session.execute(
        select(EmailDelivery.created_at, EmailDelivery.sent_at).where(
            EmailDelivery.sent_at.is_not(None),
            EmailDelivery.sent_at >= day_start,
        )
    ).all()
    latencies = [
        max(0.0, (ensure_utc(sent) - ensure_utc(created)).total_seconds())
        for created, sent in rows
        if sent is not None
    ]
    if not latencies:
        return 0, 0.0, 0.0
    return len(latencies), percentile(latencies, 0.50), percentile(latencies, 0.95)


class InlineEmailDrain:
    """Task asyncio que drena a Outbox em intervalos regulares."""

    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: sessionmaker[Session],
        engine: Engine,
        sender_factory: Callable[[Settings], EmailSender | None] = build_email_sender,
        lock: Callable[[Engine | Connection], AbstractContextManager[bool]] = email_drain_lock,
        now: Callable[[], datetime] = utcnow,
        interval_seconds: int | None = None,
    ) -> None:
        interval = (
            settings.email_inline_drain_interval_seconds
            if interval_seconds is None
            else interval_seconds
        )
        if not MIN_INTERVAL_SECONDS <= interval <= MAX_INTERVAL_SECONDS:
            raise ValueError(
                "intervalo da drenagem inline deve ficar entre "
                f"{MIN_INTERVAL_SECONDS} e {MAX_INTERVAL_SECONDS} segundos"
            )
        self._settings = settings
        self._session_factory = session_factory
        self._engine = engine
        self._sender_factory = sender_factory
        self._lock = lock
        self._now = now
        self._interval = interval
        self._task: asyncio.Task[None] | None = None
        self._sender_unavailable = False

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(
            settings,
            session_factory=get_session_factory(),
            engine=get_engine(),
        )

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def run_cycle(self) -> DeliveryReport | None:
        """Executa um ciclo bloqueante; chamar fora do event loop."""
        if self._sender_unavailable:
            return None
        sender = self._sender_factory(self._settings)
        if sender is None:
            self._sender_unavailable = True
            logger.warning("e-mail: drenagem inline sem provedor configurado; ciclos desativados")
            return None
        try:
            with self._lock(self._engine) as acquired:
                if not acquired:
                    logger.info("e-mail: ciclo inline ignorado; outro drenador ativo")
                    return None
                started = time.perf_counter()
                try:
                    with self._session_factory() as session:
                        try:
                            report = dispatch_email_deliveries(
                                session,
                                sender,
                                max_attempts=self._settings.email_max_delivery_attempts,
                                bounce_threshold=self._settings.email_bounce_threshold,
                                now=self._now(),
                            )
                            session.commit()
                        except Exception:
                            session.rollback()
                            logger.exception(
                                "e-mail: ciclo inline falhou; Outbox preservada para o "
                                "próximo ciclo"
                            )
                            return None
                        self._log_latency(session)
                finally:
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    logger.debug("e-mail: ciclo inline em %.0f ms", elapsed_ms)
        finally:
            sender.close()
        return report

    async def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.create_task(self._run(), name=TASK_NAME)

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        logger.info("e-mail: drenagem inline encerrada")

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self.run_cycle)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("e-mail: ciclo inline falhou; nova tentativa no próximo intervalo")
            await asyncio.sleep(self._interval)

    def _log_latency(self, session: Session) -> None:
        day_start = self._now().replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            samples, p50, p95 = delivery_latency_percentiles(session, day_start=day_start)
        except Exception:
            logger.warning("e-mail: falha ao calcular a latência diária", exc_info=True)
            return
        if samples:
            logger.info(
                "e-mail: latência diária p50=%.1fs p95=%.1fs amostras=%s",
                p50,
                p95,
                samples,
            )


__all__ = [
    "InlineEmailDrain",
    "delivery_latency_percentiles",
    "percentile",
]
