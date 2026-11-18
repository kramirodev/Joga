"""Entrega e-mails transacionais pendentes da Outbox.

Uso:
    python -m scripts.deliver_emails --once
    python -m scripts.deliver_emails --loop --interval 30

O modo ``--once`` é o usado pelo workflow agendado (sem depender de worker).
Sem provedor configurado, o script não altera a Outbox.
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.email.dispatcher import DeliveryReport, dispatch_email_deliveries
from app.modules.email.sender import EmailSender, build_email_sender

logger = logging.getLogger("joga.email")


def run_once_with_sender(
    session: Session,
    sender: EmailSender,
    *,
    max_attempts: int,
    bounce_threshold: int,
    now: datetime | None = None,
) -> DeliveryReport:
    """Drena a Outbox com um sender explícito; usado no workflow e em teste."""
    report = dispatch_email_deliveries(
        session,
        sender,
        max_attempts=max_attempts,
        bounce_threshold=bounce_threshold,
        now=now,
    )
    session.commit()
    return report


def run_once(session: Session) -> int:
    settings = get_settings()
    sender = build_email_sender(settings)
    if sender is None:
        logger.warning("JOGA_EMAIL_PROVIDER=none; Outbox de e-mail preservada")
        return 0
    try:
        report = run_once_with_sender(
            session,
            sender,
            max_attempts=settings.email_max_delivery_attempts,
            bounce_threshold=settings.email_bounce_threshold,
        )
    except Exception:
        session.rollback()
        logger.exception("entrega de e-mail falhou")
        return 1
    finally:
        sender.close()
    logger.info(
        "e-mail: enviados=%s falhos=%s bounced=%s ignorados=%s",
        report.sent,
        report.failed,
        report.bounced,
        report.skipped,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="drena uma vez e encerra (modo do workflow agendado)",
    )
    mode.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval deve ser positivo")

    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    engine = build_engine(settings)
    exit_code = 0
    with Session(engine) as session:
        if not args.loop:
            exit_code = run_once(session)
        else:
            try:
                while True:
                    run_once(session)
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                logger.info("dispatcher de e-mail encerrado")
    engine.dispose()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
