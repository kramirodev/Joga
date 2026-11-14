"""Reativa contas com suspensão temporária vencida (Fase 17B).

Uso:
    python -m scripts.reactivate_suspensions
    python -m scripts.reactivate_suspensions --loop --interval 300
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import User

logger = logging.getLogger("joga.moderation")


def run_once(session: Session) -> int:
    moment = ensure_utc(utcnow())
    users = list(
        session.scalars(
            select(User).where(
                User.status == "suspended",
                User.suspended_until.is_not(None),
                User.suspended_until <= moment,
            )
        ).all()
    )
    for user in users:
        user.status = "active"
        user.suspended_until = None
        user.updated_at = moment
    session.commit()
    logger.info("moderação: contas_reativadas=%s", len(users))
    return len(users)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval deve ser positivo")

    logging.basicConfig(level=get_settings().log_level)
    engine = build_engine(get_settings())
    exit_code = 0
    with Session(engine) as session:
        if not args.loop:
            run_once(session)
        else:
            try:
                while True:
                    run_once(session)
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                logger.info("reativação de suspensões encerrada")
    engine.dispose()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
