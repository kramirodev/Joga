"""Conteúdo dos templates transacionais (sem rede)."""

from __future__ import annotations

import pytest

from app.modules.email.models import EMAIL_KINDS
from app.modules.email.templates import SUBJECTS, InvalidTemplate, render


@pytest.mark.parametrize("kind", EMAIL_KINDS)
def test_every_template_has_fixed_subject_and_no_external_resource(kind: str) -> None:
    rendered = render(
        kind,
        code="123456",
        ttl_minutes=10,
        display_name="Jogador",
        occurred_at="18/11/2026 12:00 UTC",
        device_label="Android",
        deletion_label="solicitada",
    )
    assert rendered.subject == SUBJECTS[kind]
    assert "http://" not in rendered.text
    assert "https://" not in rendered.text
    assert "<img" not in rendered.html
    assert "<a " not in rendered.html
    assert "pixel" not in rendered.html.lower()
    assert "CPF" not in rendered.text
    assert "telefone" not in rendered.text.lower()


@pytest.mark.parametrize(
    "kind",
    [
        "email_verification",
        "email_login",
        "email_change_confirm",
        "password_reset",
    ],
)
def test_code_templates_show_only_code_and_validity(kind: str) -> None:
    rendered = render(kind, code="654321", ttl_minutes=10)
    assert "654321" in rendered.text
    assert "10 minutos" in rendered.text
    assert "654321" in rendered.html


def test_password_changed_notice_has_date_and_no_code() -> None:
    rendered = render("password_changed", occurred_at="19/11/2026 10:00 UTC")
    assert "19/11/2026 10:00 UTC" in rendered.text
    assert "senha" in rendered.text.lower()
    assert "@" not in rendered.text
    assert "http" not in rendered.text


def test_welcome_escapes_user_display_name_and_keeps_subject_fixed() -> None:
    rendered = render("welcome", display_name="<script>alert(1)</script>")
    assert "<script>" not in rendered.html
    assert "&lt;script&gt;" in rendered.html
    assert "<script>" not in rendered.subject
    assert rendered.subject == SUBJECTS["welcome"]


def test_change_notice_mentions_old_address_revocation_without_new_email() -> None:
    rendered = render(
        "email_change_notice",
        occurred_at="18/11/2026 12:00 UTC",
    )
    assert "18/11/2026 12:00 UTC" in rendered.text
    assert "não foi você" in rendered.text
    assert "@" not in rendered.text


def test_template_rejects_unknown_kind_and_invalid_code() -> None:
    with pytest.raises(InvalidTemplate):
        render("marketing")
    with pytest.raises(InvalidTemplate):
        render("email_login", code="12345", ttl_minutes=10)
    with pytest.raises(InvalidTemplate):
        render("email_login", code="123456", ttl_minutes=0)
