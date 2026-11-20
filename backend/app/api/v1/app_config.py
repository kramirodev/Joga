"""Contrato público de configuração de versão do cliente (ADR 0051)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.client_version import update_required_for
from app.core.config import Settings, get_settings
from app.core.environments import is_demo

router = APIRouter(prefix="/app-config", tags=["app-config"])


def get_app_settings(request: Request) -> Settings:
    """Usa as configurações resolvidas no boot, inclusive em testes."""
    resolved = getattr(request.app.state, "settings", None)
    if isinstance(resolved, Settings):
        return resolved
    return get_settings()


class AppConfigView(BaseModel):
    min_supported_version: str
    latest_version: str
    update_url: str | None
    version_gate_enabled: bool
    update_required: bool
    demo_mode: bool


@router.get("", response_model=AppConfigView)
def read_app_config(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AppConfigView:
    """Configuração aberta: o app consulta antes do login para se atualizar."""
    return AppConfigView(
        min_supported_version=settings.min_app_version,
        latest_version=settings.latest_app_version,
        update_url=settings.app_update_url,
        version_gate_enabled=settings.app_version_gate_enabled,
        update_required=update_required_for(request, settings),
        demo_mode=is_demo(settings.environment),
    )


__all__ = ["get_app_settings", "router"]
