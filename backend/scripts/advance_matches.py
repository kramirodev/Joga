"""Avança estados das partidas por tempo e apura as rodadas de resultado.

Uso:
    python -m scripts.advance_matches
    python -m scripts.advance_matches --loop --interval 60
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.matches.service import MatchService
from app.modules.results.service import ResultsService

logger = logging.getLogger("joga.matches")


def run_once(session: Session) -> int:
    try:
        lifecycle = MatchService(session).advance()
        results = ResultsService(session).advance()
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("avanço de partidas falhou")
        return 1
    logger.info(
        "partidas: canceladas=%s iniciadas=%s confirmacoes_expiradas=%s suplentes=%s "
        "rodadas_abertas=%s rodadas_fechadas=%s finalizadas=%s disputadas=%s revisoes=%s",
        lifecycle.cancelled,
        lifecycle.started,
        lifecycle.confirmed_expired,
        lifecycle.substitutes_invited,
        results.rounds_opened,
        results.rounds_closed,
        results.finalized,
        results.disputed,
        results.reviews_opened,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()

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
                logger.info("worker de partidas encerrado")
    engine.dispose()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
