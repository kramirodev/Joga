"""Dependência FastAPI para o adaptador de PSP."""

from __future__ import annotations

from collections.abc import Iterator

from app.modules.payments.adapter import PspAdapter, build_psp_adapter


def get_psp_adapter() -> Iterator[PspAdapter]:
    adapter = build_psp_adapter()
    try:
        yield adapter
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()
