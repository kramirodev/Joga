"""Concilia pagamentos, reembolsos, liberações e ledger (Fase 15).

Uso:
    python -m scripts.reconcile_financials
    python -m scripts.reconcile_financials --organization-id <uuid>
    python -m scripts.reconcile_financials --json

Saída diferente de zero indica divergência que exige investigação. O script
não altera saldos nem corrige registros.
"""

from __future__ import annotations

import argparse
import json
import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.payments.reconciliation import reconcile

logger = logging.getLogger("joga.financial")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization-id", type=uuid.UUID)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=get_settings().log_level)
    engine = build_engine(get_settings())
    with Session(engine) as session:
        issues = reconcile(session, organization_id=args.organization_id)
    engine.dispose()

    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    elif issues:
        for issue in issues:
            print(json.dumps(issue, ensure_ascii=False))
    else:
        print("Conciliação sem divergências.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
