"""Executa o worker de matchmaking uma vez ou em loop.

Uso:
    python -m scripts.run_matchmaking
    python -m scripts.run_matchmaking --loop --interval 15
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.matchmaking.service import MatchmakingService

logger = logging.getLogger("joga.matchmaking")


def build_service(session: Session) -> MatchmakingService:
    settings = get_settings()
    return MatchmakingService(
        session,
        algorithm_version=settings.matchmaking_algorithm_version,
        max_radius_km=settings.matchmaking_max_radius_km,
        search_days=settings.matchmaking_search_days,
        slot_minutes=settings.matchmaking_slot_minutes,
        min_lead_minutes=settings.matchmaking_min_lead_minutes,
        queue_ttl_hours=settings.matchmaking_queue_ttl_hours,
        default_timezone=settings.default_timezone,
    )


def run_once(session: Session) -> int:
    service = build_service(session)
    try:
        result = service.run_once()
        session.commit()
    except Exception:
        session.commit()
        logger.exception("rodada de matchmaking falhou")
        return 1
    logger.info(
        "rodada concluída: lobbies=%s expiradas=%s versao=%s",
        result.lobbies_formed,
        result.entries_expired,
        get_settings().matchmaking_algorithm_version,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=15)
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
                logger.info("worker encerrado")
    engine.dispose()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
