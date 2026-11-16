"""Tradução de status do PSP para o vocabulário interno."""

from __future__ import annotations

INTERNAL_PAID = {"processed", "approved", "paid"}
INTERNAL_REFUNDED = {"refunded", "charged_back"}
INTERNAL_FAILED = {"failed", "canceled", "cancelled"}
INTERNAL_EXPIRED = {"expired"}


def map_provider_status(status: str) -> str:
    normalized = status.lower()
    if normalized in INTERNAL_PAID:
        return "PAID"
    if normalized in INTERNAL_REFUNDED:
        return "REFUNDED"
    if normalized in INTERNAL_FAILED:
        return "FAILED"
    if normalized in INTERNAL_EXPIRED:
        return "EXPIRED"
    return "PENDING"
