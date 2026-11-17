"""Reconciliação do crédito em centavos (ADR 0049 §11.6).

Uso:
    python -m scripts.reconcile_ledger
    python -m scripts.reconcile_ledger --json

Saída diferente de zero indica divergência. O script não corrige nada. As
vagas de passe/grátis/admin aparecem como excluídas (Etapa 6b).
"""

from __future__ import annotations

import argparse
import json
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.ledger.reconciliation import reconcile_credit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=get_settings().log_level)
    engine = build_engine(get_settings())
    with Session(engine) as session:
        report = reconcile_credit(session)
    engine.dispose()

    payload = {
        "clean": report.clean,
        "checked_users": report.checked_users,
        "mismatches": [
            {
                "user_id": str(item.user_id),
                "ledger_cents": item.ledger_cents,
                "lots_cents": item.lots_cents,
                "difference": item.difference,
            }
            for item in report.mismatches
        ],
        "excluded_seats": [
            {
                "booking_id": str(item.booking_id),
                "participant_id": str(item.participant_id),
                "user_id": str(item.user_id),
                "source": item.source,
                "contribution_cents": item.contribution_cents,
            }
            for item in report.excluded_seats
        ],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif report.clean:
        print(
            f"Reconciliação limpa: {report.checked_users} usuários; "
            f"{len(report.excluded_seats)} vagas excluídas (Etapa 6b)."
        )
    else:
        for item in report.mismatches:
            print(
                f"divergência user={item.user_id} "
                f"ledger={item.ledger_cents} lotes={item.lots_cents} "
                f"diferença={item.difference}"
            )
    return 0 if report.clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
