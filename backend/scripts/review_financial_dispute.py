"""Decide uma contestação financeira por operador autorizado (Fase 15).

Uso:
    python -m scripts.review_financial_dispute \
        --dispute-id <uuid> --operator operador-1 \
        --decision ACCEPTED --reason "Justificativa auditável"
"""

from __future__ import annotations

import argparse
import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.payments.financial import (
    DisputeNotFound,
    DisputeStateError,
    FinancialService,
    OperatorNotAuthorized,
)

logger = logging.getLogger("joga.financial")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dispute-id", required=True, type=uuid.UUID)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--decision", required=True, choices=["ACCEPTED", "REJECTED"])
    parser.add_argument("--reason", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= len(args.reason) <= 500:
        parser.error("--reason deve ter entre 1 e 500 caracteres")

    logging.basicConfig(level=get_settings().log_level)
    settings = get_settings()
    if args.operator not in settings.review_operator_ids:
        logger.error("operador não autorizado: %s", args.operator)
        return 3

    engine = build_engine(settings)
    with Session(engine) as session:
        service = FinancialService(session)
        try:
            dispute = service.decide_dispute(
                args.dispute_id,
                operator=args.operator,
                decision=args.decision,
                reason=args.reason,
            )
        except (DisputeNotFound, DisputeStateError):
            session.rollback()
            logger.error("contestação inexistente ou não está aberta")
            engine.dispose()
            return 4
        except OperatorNotAuthorized:
            session.rollback()
            logger.error("operador não autorizado")
            engine.dispose()
            return 3

        if args.dry_run:
            session.rollback()
            logger.info(
                "dry-run: contestação %s seria %s por %s",
                dispute.id,
                args.decision,
                args.operator,
            )
        else:
            session.commit()
            logger.info(
                "contestação %s decidida como %s por %s",
                dispute.id,
                args.decision,
                args.operator,
            )
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
