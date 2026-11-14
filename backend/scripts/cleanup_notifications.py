"""Limpeza manual de notificações antigas.

Uso:
    python -m scripts.cleanup_notifications
    python -m scripts.cleanup_notifications --dry-run
    python -m scripts.cleanup_notifications --days 180
"""

from __future__ import annotations

import argparse
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.identity.clock import utcnow
from app.modules.notifications.models import Notification

DEFAULT_RETENTION_DAYS = 180


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=DEFAULT_RETENTION_DAYS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.days <= 0:
        parser.error("--days deve ser positivo")

    cutoff = utcnow() - timedelta(days=args.days)
    engine = build_engine(get_settings())
    try:
        with Session(engine) as session:
            count = session.scalar(delete(Notification).where(Notification.created_at < cutoff))
            if args.dry_run:
                session.rollback()
                print(f"dry-run: notificações={count}")
            else:
                session.commit()
                print(f"limpeza concluída: notificações={count}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
