"""Normalização de motivo das escritas administrativas."""

from __future__ import annotations

from fastapi import HTTPException, status


def clean_reason(reason: str | None) -> str:
    """Remove espaços das pontas e exige motivo não vazio.

    O contrato expõe ``reason_required`` para corpo ausente/em branco; o
    limite de tamanho já é validado pelo schema Pydantic.
    """

    cleaned = (reason or "").strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "reason_required"},
        )
    return cleaned


__all__ = ["clean_reason"]
