"""Remove payload efêmero de e-mail já despachado e log de entrega antigo.

Uso:
    python -m scripts.cleanup_email
    python -m scripts.cleanup_email --outbox-hours 1 --delivery-days 90
"""

from __future__ import annotations

import argparse

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.email.dispatcher import (
    purge_dispatched_email_events,
    purge_email_deliveries,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outbox-hours", type=int, default=1)
    parser.add_argument("--delivery-days", type=int, default=90)
    args = parser.parse_args()
    if args.outbox_hours < 0:
        parser.error("--outbox-hours não pode ser negativo")
    if args.delivery_days <= 0:
        parser.error("--delivery-days deve ser positivo")

    engine = build_engine(get_settings())
    with Session(engine) as session:
        events = purge_dispatched_email_events(session, older_than_hours=args.outbox_hours)
        deliveries = purge_email_deliveries(session, retention_days=args.delivery_days)
        session.commit()
    engine.dispose()
    print(f"limpeza de e-mail concluída: outbox={events} deliveries={deliveries}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
