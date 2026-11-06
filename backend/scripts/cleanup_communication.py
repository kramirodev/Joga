"""Limpeza manual de mensagens, convites, Outbox e tokens de push.

Uso:
    python -m scripts.cleanup_communication
    python -m scripts.cleanup_communication --dry-run
    python -m scripts.cleanup_communication --message-days 730 --outbox-days 30
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.social.cleanup import (
    INVITE_RETENTION_DAYS,
    MESSAGE_RETENTION_DAYS,
    OUTBOX_RETENTION_DAYS,
    PUSH_TOKEN_RETENTION_DAYS,
    CommunicationCleanupResult,
    cleanup_communication,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message-days", type=int, default=MESSAGE_RETENTION_DAYS)
    parser.add_argument("--invite-days", type=int, default=INVITE_RETENTION_DAYS)
    parser.add_argument("--outbox-days", type=int, default=OUTBOX_RETENTION_DAYS)
    parser.add_argument(
        "--push-token-days",
        type=int,
        default=PUSH_TOKEN_RETENTION_DAYS,
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    engine = build_engine(get_settings())
    try:
        with Session(engine) as session:
            try:
                result = cleanup_communication(
                    session,
                    message_days=args.message_days,
                    invite_days=args.invite_days,
                    outbox_days=args.outbox_days,
                    push_token_days=args.push_token_days,
                )
            except ValueError as exc:
                session.rollback()
                print(f"argumento inválido: {exc}")
                return 2

            if args.dry_run:
                session.rollback()
                print(f"dry-run: {_format(result)}")
            else:
                session.commit()
                print(f"limpeza concluída: {_format(result)}")
    finally:
        engine.dispose()
    return 0


def _format(result: CommunicationCleanupResult) -> str:
    return (
        f"messages={result.messages} "
        f"invites={result.invites} "
        f"outbox_events={result.outbox_events} "
        f"push_tokens={result.push_tokens}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
