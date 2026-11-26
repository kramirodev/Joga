"""Purga eventos operacionais e de segurança vencidos (ADR 0078).

Uso:
    python -m scripts.purge_observability
    python -m scripts.purge_observability --dry-run

``log_events`` usa ``JOGA_LOG_RETENTION_DAYS`` (30 por padrão) e
``security_events`` usa ``JOGA_LOG_SECURITY_RETENTION_DAYS`` (180 por padrão).
``audit_logs`` **nunca** é apagado por este script: a trilha de auditoria é
append-only e a retenção é decisão administrativa separada.
"""

from __future__ import annotations

import argparse
import logging
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.identity.clock import utcnow
from app.modules.identity.models import SecurityEvent
from app.modules.observability.models import LogEvent
from app.modules.observability.service import log_job

logger = logging.getLogger("joga.observability")


def purge(
    session: Session,
    *,
    log_retention_days: int,
    security_retention_days: int,
    dry_run: bool = False,
    now=None,
) -> tuple[int, int]:
    """Remove eventos fora da retenção; devolve (log_events, security_events)."""
    moment = now or utcnow()
    log_cutoff = moment - timedelta(days=log_retention_days)
    security_cutoff = moment - timedelta(days=security_retention_days)

    log_count = int(
        session.scalar(
            select(func.count()).select_from(LogEvent).where(LogEvent.occurred_at < log_cutoff)
        )
        or 0
    )
    security_count = int(
        session.scalar(
            select(func.count())
            .select_from(SecurityEvent)
            .where(SecurityEvent.created_at < security_cutoff)
        )
        or 0
    )
    if dry_run:
        return log_count, security_count

    if log_count:
        session.execute(
            delete(LogEvent)
            .where(LogEvent.occurred_at < log_cutoff)
            .execution_options(synchronize_session=False)
        )
    if security_count:
        session.execute(
            delete(SecurityEvent)
            .where(SecurityEvent.created_at < security_cutoff)
            .execution_options(synchronize_session=False)
        )
    session.commit()
    log_job(
        session,
        job="observability.purge",
        status="finished",
        message="purga de observabilidade concluída",
        details={
            "log_events_deleted": log_count,
            "security_events_deleted": security_count,
            "log_retention_days": log_retention_days,
            "security_retention_days": security_retention_days,
        },
    )
    session.commit()
    return log_count, security_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    engine = build_engine(settings)
    with Session(engine) as session:
        log_count, security_count = purge(
            session,
            log_retention_days=settings.log_retention_days,
            security_retention_days=settings.log_security_retention_days,
            dry_run=args.dry_run,
        )
    suffix = " (dry-run)" if args.dry_run else ""
    logger.info(
        "observabilidade: log_events=%s security_events=%s%s",
        log_count,
        security_count,
        suffix,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
