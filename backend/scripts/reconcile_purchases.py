"""Concilia compras de pacote/passe com o PSP (Fase 14D.16).

Uso:
    python -m scripts.reconcile_purchases
    python -m scripts.reconcile_purchases --json

Saída diferente de zero indica divergência que exige investigação. O script
não altera saldo, ingresso ou status de compra.
"""

from __future__ import annotations

import argparse
import json
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.payments.adapter import build_psp_adapter
from app.modules.payments.purchase_reconciliation import reconcile_purchases

logger = logging.getLogger("joga.purchases")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=get_settings().log_level)
    engine = build_engine(get_settings())
    adapter = build_psp_adapter()
    try:
        with Session(engine) as session:
            issues = reconcile_purchases(session, adapter)
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()
        engine.dispose()

    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    elif issues:
        for issue in issues:
            print(json.dumps(issue, ensure_ascii=False))
    else:
        print("Conciliação de compras sem divergências.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
