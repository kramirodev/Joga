"""Aplica MMR às partidas ranqueadas finalizadas.

Uso:
    python -m scripts.apply_ratings
    python -m scripts.apply_ratings --loop --interval 60
"""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.ratings.service import RatingNotApplicable, RatingService

logger = logging.getLogger("joga.ratings")


@dataclass(frozen=True)
class BatchResult:
    matches: int
    applied: int
    skipped: int
    failed: int


def run_once(engine, *, limit: int = 100) -> BatchResult:  # noqa: ANN001
    with Session(engine) as session:
        match_ids = RatingService(session).pending_match_ids(limit=limit)

    applied = skipped = failed = 0
    for match_id in match_ids:
        with Session(engine) as session:
            try:
                result = RatingService(session).apply_match(match_id)
                session.commit()
                applied += result.applied
            except RatingNotApplicable:
                session.rollback()
                skipped += 1
            except Exception:
                session.rollback()
                failed += 1
                logger.exception("aplicação de rating falhou: match=%s", match_id)

    logger.info(
        "ratings: partidas=%s aplicados=%s ignorados=%s falhas=%s",
        len(match_ids),
        applied,
        skipped,
        failed,
    )
    return BatchResult(
        matches=len(match_ids),
        applied=applied,
        skipped=skipped,
        failed=failed,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    if args.interval <= 0:
        parser.error("--interval deve ser positivo")
    if args.limit <= 0:
        parser.error("--limit deve ser positivo")

    logging.basicConfig(level=logging.INFO)
    engine = build_engine(get_settings())
    try:
        while True:
            result = run_once(engine, limit=args.limit)
            if not args.loop:
                return 0 if result.failed == 0 else 1
            time.sleep(args.interval)
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
