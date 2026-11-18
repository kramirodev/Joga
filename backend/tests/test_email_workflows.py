"""Perfil seguro dos workflows de e-mail (demo sem PSP real)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _read(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_email_worker_uses_demo_profile_without_mercadopago_secrets() -> None:
    text = _read("email-worker.yml")

    assert "JOGA_ENVIRONMENT: ${{ vars.JOGA_ENVIRONMENT || 'development' }}" in text
    assert "JOGA_PSP_PROVIDER: ${{ vars.JOGA_PSP_PROVIDER || 'simulator' }}" in text
    assert "JOGA_MERCADO_PAGO" not in text
    assert "python -m scripts.deliver_emails --once" in text
    assert 'cron: "*/5 * * * *"' in text
    assert "workflow_dispatch:" in text


def test_email_cleanup_uses_demo_profile_without_mercadopago_secrets() -> None:
    text = _read("email-cleanup.yml")

    assert "JOGA_ENVIRONMENT: ${{ vars.JOGA_ENVIRONMENT || 'development' }}" in text
    assert "JOGA_PSP_PROVIDER: ${{ vars.JOGA_PSP_PROVIDER || 'simulator' }}" in text
    assert "JOGA_MERCADO_PAGO" not in text
    assert "python -m scripts.cleanup_email --outbox-hours 1 --delivery-days 90" in text
    assert 'cron: "17 3 * * *"' in text
    assert "workflow_dispatch:" in text
