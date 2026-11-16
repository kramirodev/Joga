"""Reprocessa webhooks do PSP que falharam (MP-05).

Uso:
    python -m scripts.retry_webhooks
    python -m scripts.retry_webhooks --limit 50 --dry-run

O evento bruto é persistido antes do processamento. Falhas ficam com
``last_error`` e ``next_attempt_at``; este worker só pega eventos ainda não
processados cujo próximo horário já venceu. Não altera valores manualmente:
o status é sempre reconsultado no PSP.
"""

from __future__ import annotations

import argparse
import logging

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.identity.clock import utcnow
from app.modules.payments.adapter import PspAdapter, build_psp_adapter
from app.modules.payments.models import PspWebhookEvent
from app.modules.payments.service import PaymentService

logger = logging.getLogger("joga.webhooks")


def pending_events(session: Session, *, limit: int) -> list[PspWebhookEvent]:
    moment = utcnow()
    return list(
        session.scalars(
            select(PspWebhookEvent)
            .where(
                PspWebhookEvent.processed_at.is_(None),
                or_(
                    PspWebhookEvent.next_attempt_at.is_(None),
                    PspWebhookEvent.next_attempt_at <= moment,
                ),
            )
            .order_by(PspWebhookEvent.created_at)
            .limit(limit)
        ).all()
    )


def retry_pending(
    session: Session,
    adapter: PspAdapter,
    *,
    limit: int = 50,
    dry_run: bool = False,
) -> list[str]:
    events = pending_events(session, limit=limit)
    if dry_run:
        return [str(event.id) for event in events]

    service = PaymentService(session, adapter)
    results: list[str] = []
    for event in events:
        event_id = event.id
        try:
            service.process_webhook(event)
            session.commit()
            results.append(f"{event_id}:processed")
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            failed = session.get(PspWebhookEvent, event_id)
            if failed is None:
                results.append(f"{event_id}:missing")
                continue
            service.fail_webhook(failed, type(exc).__name__)
            session.commit()
            results.append(f"{event_id}:failed")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=get_settings().log_level)
    engine = build_engine(get_settings())
    adapter = build_psp_adapter()
    try:
        with Session(engine) as session:
            results = retry_pending(
                session,
                adapter,
                limit=args.limit,
                dry_run=args.dry_run,
            )
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()
        engine.dispose()

    for item in results:
        print(item)
    if not results:
        print("nenhum webhook pendente")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
