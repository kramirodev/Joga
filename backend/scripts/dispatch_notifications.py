"""Entrega notificações pendentes via webhook de push.

Uso:
    python -m scripts.dispatch_notifications
    python -m scripts.dispatch_notifications --loop --interval 30

Sem ``JOGA_PUSH_WEBHOOK_URL``, o script não altera a Outbox.
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.notifications.dispatch import dispatch_notifications
from app.modules.push.service import build_webhook_push_sender

logger = logging.getLogger("joga.notifications")


def run_once(session: Session) -> int:
    sender = build_webhook_push_sender()
    if sender is None:
        logger.warning("JOGA_PUSH_WEBHOOK_URL não configurado; Outbox preservada")
        return 0
    try:
        delivered = dispatch_notifications(session, sender)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("entrega de notificações falhou")
        return 1
    finally:
        sender.close()
    logger.info("notificações: entregues=%s", delivered)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval deve ser positivo")

    logging.basicConfig(level=get_settings().log_level)
    engine = build_engine(get_settings())
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
                logger.info("dispatcher de notificações encerrado")
    engine.dispose()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
