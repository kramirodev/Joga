"""Abertura do ledger no cutover (ADR 0049 §11.7).

Uso:
    python -m scripts.ledger_opening --dry-run
    python -m scripts.ledger_opening --apply

O padrão é `--dry-run`. O relatório lista usuários, lotes e centavos. `--apply`
grava `opening:{user}` de forma idempotente.
"""

from __future__ import annotations

import argparse
import json
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.ledger.opening import open_ledger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=get_settings().log_level)
    engine = build_engine(get_settings())
    with Session(engine) as session:
        report = open_ledger(session, dry_run=not args.apply)
        if args.apply:
            session.commit()
        else:
            session.rollback()
    engine.dispose()

    payload = {
        "dry_run": not args.apply,
        "total_cents": report.total_cents,
        "created": report.created,
        "users": [
            {"user_id": str(line.user_id), "cents": line.cents, "lots": line.lots}
            for line in report.lines
        ],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"{'DRY-RUN' if not args.apply else 'APLICADO'}: "
            f"{len(report.lines)} usuários, {report.total_cents} centavos, "
            f"{report.created} contas abertas"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
