"""Libera valores vencidos ao estabelecimento (Fase 15).

Uso:
    python -m scripts.release_payments
    python -m scripts.release_payments --loop --interval 60
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.payments.financial import FinancialService

logger = logging.getLogger("joga.financial")


def run_once(session: Session) -> int:
    service = FinancialService(session)
    try:
        created = service.ensure_missing_releases()
        released = service.release_due()
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("liberação financeira falhou")
        return 1
    logger.info("financeiro: liberacoes_criadas=%s liberacoes=%s", created, released)
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
                logger.info("worker financeiro encerrado")
    engine.dispose()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
