"""Endpoints de health check: liveness sem dependências e readiness com banco."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.infrastructure.database.dependency import get_database
from app.infrastructure.database.engine import Database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    """Processo responde; não verifica dependências externas."""
    return {"status": "ok"}


@router.get("/ready")
def ready(database: Annotated[Database, Depends(get_database)]) -> dict[str, str]:
    """Verifica o PostgreSQL. Detalhes da falha não são expostos ao cliente."""
    try:
        database.check()
    except Exception:  # noqa: BLE001 - readiness deve falhar fechado para qualquer erro de conexão
        logger.exception("Falha na verificação de readiness do banco")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unavailable", "database": "unavailable"},
        ) from None
    return {"status": "ok", "database": "ok"}
