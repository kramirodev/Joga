"""Revisão humana de denúncias (Fase 17A).

Uso:
    python -m scripts.review_moderation --list
    python -m scripts.review_moderation --decide <id> --decision DISMISS \
        --reason "..." --operator op1
    python -m scripts.review_moderation --decide <id> --decision RESTRICT_RANKED \
        --days 7 --reason "..." --operator op1
    python -m scripts.review_moderation --appeals
    python -m scripts.review_moderation --appeal <id> --decision ACCEPTED \
        --reason "..." --operator op1
"""

from __future__ import annotations

import argparse
import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.moderation.models import ModerationAppeal, ModerationReport
from app.modules.moderation.service import ModerationService

logger = logging.getLogger("joga.moderation")


def _print_report(report: ModerationReport) -> None:
    print(
        json.dumps(
            {
                "id": str(report.id),
                "category": report.category,
                "severity": report.severity,
                "priority": report.priority,
                "status": report.status,
                "description": report.description,
                "context_count": len(report.context or []),
                "created_at": report.created_at.isoformat(),
            },
            ensure_ascii=False,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--decide", type=uuid.UUID)
    parser.add_argument("--decision", choices=("DISMISS", "WARN", "RESTRICT_RANKED"))
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--reason")
    parser.add_argument("--operator")
    parser.add_argument("--appeals", action="store_true")
    parser.add_argument("--appeal", type=uuid.UUID)
    parser.add_argument("--appeal-decision", choices=("ACCEPTED", "REJECTED"))
    args = parser.parse_args()

    logging.basicConfig(level=get_settings().log_level)
    engine = build_engine(get_settings())
    try:
        with Session(engine) as session:
            service = ModerationService(session)
            if args.list:
                for report in service.queue(status_filter="OPEN"):
                    _print_report(report)
                return 0
            if args.appeals:
                rows = session.scalars(
                    select(ModerationAppeal)
                    .where(ModerationAppeal.status == "OPEN")
                    .order_by(ModerationAppeal.created_at)
                ).all()
                for appeal in rows:
                    print(
                        json.dumps(
                            {
                                "id": str(appeal.id),
                                "action_id": str(appeal.action_id),
                                "user_id": str(appeal.user_id),
                                "reason": appeal.reason,
                                "created_at": appeal.created_at.isoformat(),
                            },
                            ensure_ascii=False,
                        )
                    )
                return 0
            if args.decide:
                if not args.decision or not args.reason or not args.operator:
                    parser.error("--decision, --reason e --operator são obrigatórios")
                report, action = service.review(
                    args.decide,
                    operator=args.operator,
                    decision=args.decision,
                    reason=args.reason,
                    days=args.days,
                )
                session.commit()
                print(
                    json.dumps(
                        {
                            "report_id": str(report.id),
                            "status": report.status,
                            "action_id": str(action.id) if action is not None else None,
                        }
                    )
                )
                return 0
            if args.appeal:
                if not args.appeal_decision or not args.reason or not args.operator:
                    parser.error("--appeal-decision, --reason e --operator são obrigatórios")
                appeal = service.review_appeal(
                    args.appeal,
                    operator=args.operator,
                    decision=args.appeal_decision,
                    reason=args.reason,
                )
                session.commit()
                print(json.dumps({"appeal_id": str(appeal.id), "status": appeal.status}))
                return 0
            parser.print_help()
            return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
