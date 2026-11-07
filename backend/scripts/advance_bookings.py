"""Expira temporizadores de reservas e libera bloqueios vencidos.

Uso:
    python -m scripts.advance_bookings
    python -m scripts.advance_bookings --loop --interval 60
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.bookings.service import BookingService

logger = logging.getLogger("joga.bookings")


def run_once(session: Session) -> int:
    try:
        expired = BookingService(session).expire_due()
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("expiração de reservas falhou")
        return 1
    logger.info("reservas: temporizadores_expirados=%s", expired)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
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
                logger.info("worker de reservas encerrado")
    engine.dispose()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
