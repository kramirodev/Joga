"""Carteira de ingressos do jogador (ADR 0042 §2)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.tickets.service import get_balance, list_entries

router = APIRouter(prefix="/me/tickets", tags=["tickets"])


class TicketEntryView(BaseModel):
    id: UUID
    amount: int
    source: str
    ref_type: str | None
    ref_id: UUID | None
    created_at: datetime


class TicketWalletView(BaseModel):
    balance: int
    entries: list[TicketEntryView]


@router.get("", response_model=TicketWalletView)
def read_wallet(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> TicketWalletView:
    """Saldo e últimos movimentos. O saldo nunca é editável pelo cliente."""

    entries = list_entries(session, current.user_id, limit=limit)
    return TicketWalletView(
        balance=get_balance(session, current.user_id),
        entries=[
            TicketEntryView(
                id=item.id,
                amount=item.amount,
                source=item.source,
                ref_type=item.ref_type,
                ref_id=item.ref_id,
                created_at=item.created_at,
            )
            for item in entries
        ],
    )
