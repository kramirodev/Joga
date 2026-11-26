"""Serviço central de logging, segurança e auditoria (ADR 0078).

Uma única API evita que cada módulo invente o próprio formato:

* ``log_event`` — evento operacional (HTTP, app, job, cliente).
* ``log_security`` — delega à trilha canônica ``security_events`` (síncrono).
* ``log_audit`` — delega à trilha canônica ``audit_logs`` (síncrono).
* ``log_exception`` — erro com stack sanitizado, nunca devolvido ao cliente.
* ``log_job`` — início/fim/falha de job ou worker.

Eventos operacionais são enfileirados e gravados em lote. Se o banco falhar,
o evento sanitizado vai para stdout e o contador de perda aumenta; a requisição
nunca falha por causa do log. Segurança e auditoria nunca são amostrados.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core import request_context
from app.core.config import Settings
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.events import record_security_event
from app.modules.observability.models import LOG_CATEGORIES, LOG_LEVELS, LogEvent
from app.modules.observability.redaction import (
    sanitize_details,
    sanitize_message,
    sanitize_stack,
    sanitize_user_agent,
)

logger = logging.getLogger("joga.observability")

FLUSH_INTERVAL_SECONDS = 1.0
BATCH_SIZE = 100
SLOW_REQUEST_MS = 1_000
DROP_FALLBACK_LEVEL = logging.ERROR

_dispatcher_var: ContextVar[LogDispatcher | None] = ContextVar("joga_log_dispatcher", default=None)


@dataclass(slots=True)
class LogEntry:
    """Evento já sanitizado, pronto para a fila ou para o banco."""

    level: str
    category: str
    message: str | None = None
    occurred_at: datetime = field(default_factory=utcnow)
    module: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    user_id: uuid.UUID | None = None
    ip: str | None = None
    ip_hash: str | None = None
    user_agent: str | None = None
    endpoint: str | None = None
    status: int | None = None
    duration_ms: int | None = None
    error_code: str | None = None
    stack: str | None = None
    details: dict[str, Any] | None = None

    def to_model(self) -> LogEvent:
        return LogEvent(
            occurred_at=self.occurred_at,
            level=self.level,
            category=self.category,
            module=self.module,
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            user_id=self.user_id,
            ip=self.ip,
            ip_hash=self.ip_hash,
            user_agent=self.user_agent,
            endpoint=self.endpoint,
            status=self.status,
            duration_ms=self.duration_ms,
            message=self.message,
            error_code=self.error_code,
            stack=self.stack,
            details=self.details,
        )

    def as_stdout(self) -> str:
        payload = {
            "level": self.level,
            "category": self.category,
            "module": self.module,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "user_id": str(self.user_id) if self.user_id else None,
            "endpoint": self.endpoint,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "error_code": self.error_code,
            "message": self.message,
        }
        return json.dumps(payload, ensure_ascii=False, default=str)


def build_entry(
    *,
    level: str,
    category: str,
    message: str | None,
    module: str | None = None,
    occurred_at: datetime | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
    user_id: uuid.UUID | None = None,
    ip: str | None = None,
    ip_hash: str | None = None,
    user_agent: str | None = None,
    endpoint: str | None = None,
    status: int | None = None,
    duration_ms: int | None = None,
    error_code: str | None = None,
    stack: str | None = None,
    details: dict[str, Any] | None = None,
    use_request_context: bool = True,
) -> LogEntry:
    """Normaliza, redige e completa um evento com o contexto corrente."""
    if level not in LOG_LEVELS:
        level = "info"
    if category not in LOG_CATEGORIES:
        category = "app"
    if use_request_context:
        request_id = request_id or request_context.current_request_id()
        user_id = user_id or request_context.current_user_id()
        ip = ip or request_context.current_ip()
        ip_hash = ip_hash or request_context.current_ip_hash()
        user_agent = user_agent or request_context.current_user_agent()
        endpoint = endpoint or request_context.current_endpoint()
    return LogEntry(
        level=level,
        category=category,
        message=sanitize_message(message),
        occurred_at=ensure_utc(occurred_at or utcnow()),
        module=module[:80] if module else None,
        request_id=request_id[:64] if request_id else None,
        correlation_id=correlation_id[:64] if correlation_id else None,
        user_id=user_id,
        ip=ip[:45] if ip else None,
        ip_hash=ip_hash[:64] if ip_hash else None,
        user_agent=sanitize_user_agent(user_agent),
        endpoint=endpoint[:255] if endpoint else None,
        status=status,
        duration_ms=duration_ms,
        error_code=error_code[:80] if error_code else None,
        stack=sanitize_stack(stack),
        details=sanitize_details(details),
    )


def format_stack(exc: BaseException) -> str | None:
    """Formata a pilha do erro; o chamador decide se persiste."""
    import traceback

    try:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    except Exception:  # noqa: BLE001 - a stack nunca pode derrubar o log
        return None


class LogDispatcher:
    """Fila limitada em ``asyncio`` com lote, fallback e contadores."""

    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: sessionmaker[Session] | Callable[[], Session] | None,
        sink: Callable[[list[LogEntry]], None] | None = None,
        flush_interval_seconds: float = FLUSH_INTERVAL_SECONDS,
        batch_size: int = BATCH_SIZE,
    ) -> None:
        self.settings = settings
        self._session_factory = session_factory
        self._sink = sink
        self._flush_interval = flush_interval_seconds
        self._batch_size = batch_size
        self._queue: asyncio.Queue[LogEntry] = asyncio.Queue(maxsize=settings.log_async_queue_size)
        self._task: asyncio.Task[None] | None = None
        self.written = 0
        self.dropped = 0
        self.failed_batches = 0

    # -- ciclo de vida -------------------------------------------------
    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        pending = self._drain()
        if pending:
            await self._write_batch_async(pending)

    # -- entrada --------------------------------------------------------
    def submit(self, entry: LogEntry) -> None:
        if not self.settings.observability_enabled:
            return
        try:
            self._queue.put_nowait(entry)
        except asyncio.QueueFull:
            self.dropped += 1
            self._fallback(entry, reason="queue_full")

    def submit_sync(self, entry: LogEntry) -> None:
        """Grava imediatamente (scripts/workers sem loop asyncio)."""
        if not self.settings.observability_enabled:
            return
        try:
            self._write_batch([entry])
        except Exception as exc:  # noqa: BLE001 - log nunca derruba o chamador
            self.failed_batches += 1
            logger.error("falha ao gravar evento operacional error_type=%s", type(exc).__name__)
            self._fallback(entry, reason="database_error")

    async def flush(self) -> None:
        pending = self._drain()
        while pending:
            await self._write_batch_async(pending)
            pending = self._drain()

    # -- segurança/auditoria -------------------------------------------
    def write_security_now(
        self,
        event_type: str,
        *,
        user_id: uuid.UUID | None = None,
        ip: str | None = None,
        ip_hash: str | None = None,
        request_id: str | None = None,
        endpoint: str | None = None,
        user_agent: str | None = None,
        result: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Grava evento de segurança de forma síncrona, com fallback stdout."""
        if self._session_factory is None:
            self._fallback(
                LogEntry(level="warn", category="security", message=event_type, details=details),
                reason="no_database",
            )
            return
        try:
            with self._session_factory() as session:
                record_security_event(
                    session,
                    event_type,
                    user_id=user_id,
                    ip=ip,
                    ip_hash=ip_hash,
                    request_id=request_id,
                    endpoint=endpoint,
                    user_agent=user_agent,
                    result=result,
                    details=details,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001 - log nunca derruba a requisição
            self.failed_batches += 1
            logger.error(
                "falha ao gravar evento de segurança %s error_type=%s",
                event_type,
                type(exc).__name__,
            )
            self._fallback(
                LogEntry(level="warn", category="security", message=event_type, details=details),
                reason="database_error",
            )

    # -- interno --------------------------------------------------------
    async def _run(self) -> None:
        while True:
            try:
                first = await asyncio.wait_for(self._queue.get(), timeout=self._flush_interval)
            except TimeoutError:
                continue
            batch = [first]
            while len(batch) < self._batch_size:
                try:
                    batch.append(self._queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            await self._write_batch_async(batch)

    def _drain(self) -> list[LogEntry]:
        batch: list[LogEntry] = []
        while True:
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                return batch

    async def _write_batch_async(self, batch: list[LogEntry]) -> None:
        if not batch:
            return
        try:
            await asyncio.to_thread(self._write_batch, batch)
        except Exception as exc:  # noqa: BLE001
            self.failed_batches += 1
            logger.error(
                "falha ao persistir lote de log_events (%s eventos) error_type=%s",
                len(batch),
                type(exc).__name__,
            )
            for entry in batch:
                self._fallback(entry, reason="database_error")

    def _write_batch(self, batch: list[LogEntry]) -> None:
        if self._sink is not None:
            self._sink(batch)
            self.written += len(batch)
            return
        if self._session_factory is None:
            for entry in batch:
                self._fallback(entry, reason="no_database")
            return
        with self._session_factory() as session:
            session.add_all(entry.to_model() for entry in batch)
            session.commit()
        self.written += len(batch)

    def _fallback(self, entry: LogEntry, *, reason: str) -> None:
        try:
            logger.log(
                DROP_FALLBACK_LEVEL,
                "log_events_fallback reason=%s event=%s",
                reason,
                entry.as_stdout(),
            )
        except Exception:  # noqa: BLE001
            pass


def set_dispatcher(dispatcher: LogDispatcher | None) -> Any:
    """Associa o dispatcher ao contexto atual; devolve o token de reset."""
    return _dispatcher_var.set(dispatcher)


def reset_dispatcher(token: Any) -> None:
    _dispatcher_var.reset(token)


def current_dispatcher() -> LogDispatcher | None:
    return _dispatcher_var.get()


# -- API pública ---------------------------------------------------------
def _resolve_dispatcher() -> LogDispatcher | None:
    return current_dispatcher()


def log_event(
    level: str,
    category: str,
    message: str | None = None,
    *,
    session: Session | None = None,
    module: str | None = None,
    details: dict[str, Any] | None = None,
    error_code: str | None = None,
    stack: str | None = None,
    **kwargs: Any,
) -> None:
    """Registra um evento operacional; nunca levanta por falha de log."""
    entry = build_entry(
        level=level,
        category=category,
        message=message,
        module=module,
        details=details,
        error_code=error_code,
        stack=stack,
        **kwargs,
    )
    dispatcher = _resolve_dispatcher()
    if dispatcher is not None:
        dispatcher.submit(entry)
        return
    if session is not None:
        session.add(entry.to_model())
        return
    logger.info("log_event %s", entry.as_stdout())


def log_exception(
    exc: BaseException | None = None,
    *,
    level: str = "error",
    category: str = "app",
    module: str | None = None,
    message: str | None = None,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
    include_stack: bool | None = None,
    session: Session | None = None,
    **kwargs: Any,
) -> None:
    """Registra uma exceção com stack sanitizado.

    A pilha nunca entra na resposta HTTP: o chamador devolve apenas um código
    estável. ``include_stack`` obedece ``JOGA_LOG_STACKTRACES`` por padrão.
    """
    settings = getattr(_resolve_dispatcher(), "settings", None)
    allowed = settings.log_stacktraces if settings is not None else True
    if include_stack is not None:
        allowed = include_stack
    resolved_message = message
    if resolved_message is None and exc is not None:
        resolved_message = f"{type(exc).__name__}: {exc}"
    log_event(
        level,
        category,
        resolved_message,
        session=session,
        module=module,
        error_code=error_code or (type(exc).__name__ if exc is not None else None),
        stack=format_stack(exc) if (exc is not None and allowed) else None,
        details=details,
        **kwargs,
    )


def log_job(
    session: Session | None,
    *,
    job: str,
    status: str,
    message: str | None = None,
    duration_ms: int | None = None,
    details: dict[str, Any] | None = None,
    error: BaseException | None = None,
) -> None:
    """Registra início/fim/falha de um job.

    Com sessão, grava na transação corrente (o chamador commita). Sem sessão,
    usa o dispatcher corrente. Falhas sempre viram ``error`` com stack.
    """
    level = "error" if status == "failed" or error is not None else "info"
    if status == "started":
        level = "info"
    resolved_details = dict(details or {})
    resolved_details.setdefault("status", status)
    dispatcher = _resolve_dispatcher()
    include_stack = True
    if dispatcher is not None:
        include_stack = dispatcher.settings.log_stacktraces
    log_event(
        level,
        "job",
        message or f"job {job} {status}",
        session=session,
        module=job,
        duration_ms=duration_ms,
        error_code=type(error).__name__ if error is not None else None,
        stack=format_stack(error) if (error is not None and include_stack) else None,
        details=resolved_details,
    )


def log_security(session: Session, event_type: str, **kwargs: Any) -> None:
    """Atalho explícito para a trilha canônica de segurança (síncrona)."""
    record_security_event(session, event_type, **kwargs)


def log_audit(session: Session, **kwargs: Any) -> None:
    """Atalho explícito para a trilha canônica de auditoria (síncrona)."""
    from app.modules.identity.audit import record_audit

    record_audit(session, **kwargs)


__all__ = [
    "BATCH_SIZE",
    "FLUSH_INTERVAL_SECONDS",
    "SLOW_REQUEST_MS",
    "LogDispatcher",
    "LogEntry",
    "build_entry",
    "current_dispatcher",
    "format_stack",
    "log_audit",
    "log_event",
    "log_exception",
    "log_job",
    "log_security",
    "reset_dispatcher",
    "set_dispatcher",
]
