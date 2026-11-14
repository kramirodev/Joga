"""Redige o contexto de denúncias antigas (Fase 17B, retenção provisória).

Uso:
    python -m scripts.cleanup_moderation
    python -m scripts.cleanup_moderation --dry-run
    python -m scripts.cleanup_moderation --days 180
"""

from __future__ import annotations

import argparse
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.identity.clock import utcnow
from app.modules.moderation.models import ModerationReport


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    days = args.days or get_settings().moderation_retention_days
    if days <= 0:
        parser.error("--days deve ser positivo")

    cutoff = utcnow() - timedelta(days=days)
    engine = build_engine(get_settings())
    try:
        with Session(engine) as session:
            rows = list(
                session.scalars(
                    select(ModerationReport).where(
                        ModerationReport.created_at < cutoff,
                        ModerationReport.description != "[redacted]",
                    )
                ).all()
            )
            for row in rows:
                row.description = "[redacted]"
                row.context = []
                row.classifier_signals = None
            if args.dry_run:
                session.rollback()
                print(f"dry-run: denúncias_redigidas={len(rows)}")
            else:
                session.commit()
                print(f"limpeza concluída: denúncias_redigidas={len(rows)}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
