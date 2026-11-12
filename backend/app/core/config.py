"""Configuração da API, lida de variáveis de ambiente com prefixo JOGA_."""

from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PHONE_HASH_SECRET = "local-development-only-change-me"
DEFAULT_TOKEN_HASH_SECRET = "local-token-development-only-change-me"
LOCAL_ENVIRONMENTS = {"local", "test", "development", "ci"}


class Settings(BaseSettings):
    """Configuração explícita; nenhum segredo real tem valor padrão versionado."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="JOGA_",
        extra="ignore",
    )

    environment: str = "local"
    database_url: str = "postgresql+psycopg://joga:joga@127.0.0.1:5434/joga"
    database_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    max_request_body_bytes: int = Field(default=1_000_000, ge=1024, le=10_000_000)
    log_level: str = "INFO"

    # Segredo de hash de telefone/OTP/IP. O valor padrão só vale para
    # desenvolvimento e testes; ambientes reais precisam definir JOGA_PHONE_HASH_SECRET.
    phone_hash_secret: SecretStr = SecretStr(DEFAULT_PHONE_HASH_SECRET)
    otp_ttl_seconds: int = Field(default=300, ge=60, le=900)
    otp_max_attempts: int = Field(default=5, ge=1, le=10)
    otp_resend_cooldown_seconds: int = Field(default=60, ge=0, le=300)
    otp_max_per_hour: int = Field(default=5, ge=1, le=20)
    otp_max_per_ip_per_hour: int = Field(default=20, ge=1, le=200)
    otp_receipt_ttl_seconds: int = Field(default=600, ge=60, le=1800)

    # Segredo de hash de access/refresh tokens. O padrão só vale para
    # desenvolvimento e testes; ambientes reais precisam definir JOGA_TOKEN_HASH_SECRET.
    token_hash_secret: SecretStr = SecretStr(DEFAULT_TOKEN_HASH_SECRET)
    access_token_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    refresh_absolute_ttl_days: int = Field(default=30, ge=1, le=365)
    refresh_idle_ttl_days: int = Field(default=7, ge=1, le=90)

    # Painel web: refresh em cookie HttpOnly e CSRF em cookie legível.
    # Em produção, JOGA_WEB_COOKIE_SECURE deve ser true (HTTPS).
    web_cookie_secure: bool = False

    # WebAuthn/passkeys. A origem Android é derivada do certificado de debug da
    # prova; um build de release exige atualizar este valor e o assetlinks.
    webauthn_rp_id: str = Field(default="joga-passkeys.vercel.app", min_length=1)
    webauthn_rp_name: str = Field(default="JOGA", min_length=1)
    webauthn_origin_android: str = Field(
        default=("android:apk-key-hash:-sYXRdwJA3hvue3mKpYrOZ9zSPC7b4mbgzJmdZEDO5w"),
        min_length=1,
    )
    webauthn_origin_web: str = Field(
        default="https://joga-passkeys.vercel.app",
        min_length=1,
    )
    passkey_challenge_ttl_seconds: int = Field(default=300, ge=60, le=600)
    passkey_max_per_ip_per_hour: int = Field(default=30, ge=1, le=300)

    # Perfil e descoberta (Fase 4).
    cep_api_base_url: str = Field(
        default="https://brasilapi.com.br/api/cep/v2",
        min_length=1,
    )
    cep_timeout_seconds: int = Field(default=5, ge=1, le=15)
    discovery_max_radius_km: int = Field(default=100, ge=1, le=200)
    discovery_default_radius_km: int = Field(default=10, ge=1, le=100)
    discovery_page_size: int = Field(default=20, ge=1, le=50)
    location_round_decimals: int = Field(default=2, ge=1, le=3)
    default_timezone: str = Field(default="America/Sao_Paulo", min_length=1)

    # Matchmaking (Fase 5).
    matchmaking_algorithm_version: str = Field(default="level_v1", min_length=1, max_length=40)
    matchmaking_queue_ttl_hours: int = Field(default=24, ge=1, le=168)
    matchmaking_search_days: int = Field(default=7, ge=1, le=30)
    matchmaking_slot_minutes: int = Field(default=30, ge=5, le=60)
    matchmaking_min_lead_minutes: int = Field(default=120, ge=0, le=1440)
    matchmaking_max_radius_km: int = Field(default=30, ge=1, le=200)

    # Fotos de quadra (Fase 12A). O storage local é privado e não é servido
    # estaticamente; produção exige decisão de storage de objetos.
    media_root: str = Field(default="var/media", min_length=1, max_length=500)
    venue_photo_max_bytes: int = Field(default=5_000_000, ge=1024, le=20_000_000)
    venue_photo_max_pixels: int = Field(default=40_000_000, ge=10_000, le=100_000_000)
    venue_photo_max_dimension: int = Field(default=4000, ge=200, le=10_000)
    venue_photo_min_dimension: int = Field(default=200, ge=1, le=2000)
    venue_photo_output_max_dimension: int = Field(default=2000, ge=200, le=4000)

    # Reservas e temporizadores (Fase 13A). T2 opera em tempo corrido nesta
    # fase; horário comercial fica pendente de implementação.
    booking_t1_minutes: int = Field(default=60, ge=5, le=240)
    booking_t2_minutes: int = Field(default=30, ge=5, le=240)
    booking_t2_max_minutes: int = Field(default=60, ge=30, le=60)
    booking_t3_minutes: int = Field(default=60, ge=10, le=240)
    booking_payment_buffer_minutes: int = Field(default=10, ge=0, le=30)

    # Cancelamento e substituição (ADR 0039). O cutoff e a janela são
    # propostas iniciais; não são regra financeira aprovada.
    cancellation_cutoff_hours: int = Field(default=6, ge=1, le=168)
    substitution_window_percent: int = Field(default=25, ge=1, le=100)
    substitution_window_min_minutes: int = Field(default=30, ge=5, le=240)
    substitution_window_max_hours: int = Field(default=12, ge=1, le=72)
    late_substitution_window_minutes: int = Field(default=15, ge=5, le=30)
    substitution_call_timeout_minutes: int = Field(default=5, ge=2, le=15)
    presence_open_lead_minutes: int = Field(default=60, ge=5, le=240)
    presence_close_lead_minutes: int = Field(default=30, ge=5, le=120)
    presence_radius_m: int = Field(default=200, ge=50, le=1000)
    presence_max_accuracy_m: int = Field(default=100, ge=10, le=500)

    # PSP (Fase 14A). O simulador é o padrão local/CI; o Mercado Pago exige
    # credenciais sandbox e nunca deve ser usado com dinheiro real neste estágio.
    psp_provider: str = Field(default="simulator", pattern="^(simulator|mercadopago)$")
    mercado_pago_access_token: SecretStr | None = None
    mercado_pago_webhook_secret: SecretStr | None = None
    mercado_pago_base_url: str = Field(
        default="https://api.mercadopago.com",
        min_length=1,
        max_length=200,
    )
    mercado_pago_payer_email: str = Field(
        default="test_user_br@testuser.com",
        min_length=3,
        max_length=120,
    )
    mercado_pago_notification_url: str | None = Field(default=None, max_length=500)
    psp_timeout_seconds: int = Field(default=10, ge=1, le=60)

    # Liberação ao estabelecimento: no horário da partida (ADR 0039). O atraso
    # opcional existe apenas para operação; o padrão é zero.
    release_delay_hours: int = Field(default=2, ge=0, le=720)

    # Revisão humana de resultados (Fase 7). Lista separada por vírgula; vazia
    # significa que nenhum operador está autorizado.
    review_operators: str = ""

    # Limite de POSTs de resultado por usuário em uma janela de 60 segundos.
    results_rate_limit_per_minute: int = Field(default=30, ge=1, le=600)

    @property
    def review_operator_ids(self) -> frozenset[str]:
        return frozenset(item.strip() for item in self.review_operators.split(",") if item.strip())

    # Apenas para desenvolvimento local: fixa o OTP para facilitar testes no app.
    # Nunca usar em ambiente compartilhado/produção.
    dev_fixed_otp: str | None = Field(default=None, pattern=r"^\d{6}$")

    @property
    def webauthn_origins(self) -> list[str]:
        return [self.webauthn_origin_android, self.webauthn_origin_web]

    @model_validator(mode="after")
    def reject_default_secret_outside_local(self) -> Self:
        if self.psp_provider == "mercadopago" and self.mercado_pago_access_token is None:
            raise ValueError("JOGA_MERCADO_PAGO_ACCESS_TOKEN é obrigatório com psp=mercadopago")
        if self.environment.lower() in LOCAL_ENVIRONMENTS:
            return self
        secrets = {
            "JOGA_PHONE_HASH_SECRET": (
                self.phone_hash_secret.get_secret_value(),
                DEFAULT_PHONE_HASH_SECRET,
            ),
            "JOGA_TOKEN_HASH_SECRET": (
                self.token_hash_secret.get_secret_value(),
                DEFAULT_TOKEN_HASH_SECRET,
            ),
        }
        for name, (value, default) in secrets.items():
            if value == default:
                raise ValueError(f"{name} deve ser definido fora do ambiente local")
        if self.dev_fixed_otp is not None:
            raise ValueError("JOGA_DEV_FIXED_OTP só pode ser usado em ambiente local")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
