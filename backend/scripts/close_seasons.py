"""Fecha temporadas vencidas e abre a do trimestre seguinte (Fase 14D.14).

Uso:
    python -m scripts.close_seasons
    python -m scripts.close_seasons --loop --interval 3600
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.clans.service import snapshot_season
from app.modules.season.models import Season
from app.modules.season.service import close_expired_season

logger = logging.getLogger("joga.season")


def run_once(session: Session) -> int:
    closed = 0
    try:
        while close_expired_season(session) is not None:
            closed += 1
        for season_id in session.scalars(select(Season.id).where(Season.status == "closed")):
            snapshot_season(session, season_id)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("fechamento de temporada falhou")
        return 1
    logger.info("temporada: fechadas=%s", closed)
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
                logger.info("worker de temporada encerrado")
    engine.dispose()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
