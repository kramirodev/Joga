"""Entrega mensal do passe e expiração de assinaturas (Fase 14D.12).

Uso:
    python -m scripts.deliver_pass_months
    python -m scripts.deliver_pass_months --loop --interval 3600
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.passes.service import deliver_all_due

logger = logging.getLogger("joga.passes")


def run_once(session: Session) -> int:
    try:
        delivered = deliver_all_due(session)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("entrega do passe falhou")
        return 1
    logger.info("passe: franquias_entregues=%s", delivered)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=3600)
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
                logger.info("worker do passe encerrado")
    engine.dispose()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
