"""Limpeza manual de desafios, sessões e eventos antigos.

Uso:
    python -m scripts.cleanup_identity
    python -m scripts.cleanup_identity --challenge-days 1 --session-days 30 --event-days 90
"""

from __future__ import annotations

import argparse

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.identity.cleanup import cleanup_identity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--challenge-days", type=int, default=1)
    parser.add_argument("--session-days", type=int, default=30)
    parser.add_argument("--event-days", type=int, default=90)
    args = parser.parse_args()

    engine = build_engine(get_settings())
    with Session(engine) as session:
        result = cleanup_identity(
            session,
            challenge_retention_days=args.challenge_days,
            session_retention_days=args.session_days,
            event_retention_days=args.event_days,
        )
        session.commit()

    engine.dispose()
    print(
        "limpeza concluída: "
        f"phone_challenges={result.phone_challenges} "
        f"passkey_challenges={result.passkey_challenges} "
        f"sessions={result.sessions} "
        f"security_events={result.security_events}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
