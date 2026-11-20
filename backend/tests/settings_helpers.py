"""Fábricas de ``Settings`` para testes de ambiente."""

from __future__ import annotations

from pydantic import SecretStr

from app.core.config import Settings
from tests.compliance_helpers import cpf_key_kwargs


def demo_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "demo",
        "phone_hash_secret": "demo-phone-hash-secret",
        "token_hash_secret": "demo-token-hash-secret",
        "psp_provider": "simulator",
        "money_mode": "simulated",
        "ticket_purchase_enabled": False,
        "web_cookie_secure": True,
        **cpf_key_kwargs(),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "phone_hash_secret": "production-phone-hash-secret",
        "token_hash_secret": "production-token-hash-secret",
        "psp_provider": "mercadopago",
        "mercado_pago_access_token": SecretStr("mp-access-token"),
        "mercado_pago_webhook_secret": SecretStr("mp-webhook-secret"),
        "mercado_pago_notification_url": "https://api.joga.example/payments/mercadopago/webhook",
        "web_cookie_secure": True,
        **cpf_key_kwargs(),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)
