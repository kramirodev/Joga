"""Entrega notificações pendentes uma vez (cron/manual) ou em loop.

Uso:
    python -m scripts.dispatch_notifications
    python -m scripts.dispatch_notifications --loop --interval 30

Para operação contínua prefira ``python -m workers.notification_dispatch``.
Sem ``JOGA_EXPO_PUSH_URL`` (ou webhook legado), o script não altera a Outbox.
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.notifications.dispatch import dispatch_notifications
from app.modules.push.expo import build_push_sender
from app.modules.realtime.notifications import publish_notification_event_sync

logger = logging.getLogger("joga.notifications")


def run_once(session: Session) -> int:
    settings = get_settings()
    sender = build_push_sender(settings)
    if sender is None:
        logger.warning("nenhum provedor de push configurado; Outbox preservada")
        return 0
    try:
        report = dispatch_notifications(
            session,
            sender,
            publisher=publish_notification_event_sync,
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("entrega de notificações falhou")
        return 1
    finally:
        sender.close()
    logger.info(
        "notificações: eventos=%s entregues=%s sem_token=%s falhas=%s",
        report.processed,
        report.delivered,
        report.no_tokens,
        report.failed,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval deve ser positivo")

    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
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
                logger.info("dispatcher de notificações encerrado")
    engine.dispose()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
