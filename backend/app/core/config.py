"""Configuração da API, lida de variáveis de ambiente com prefixo JOGA_."""

import base64
import binascii
from datetime import date
from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.environments import is_demo, is_local
from app.core.versioning import parse_version

DEFAULT_PHONE_HASH_SECRET = "local-development-only-change-me"
DEFAULT_TOKEN_HASH_SECRET = "local-token-development-only-change-me"

# Hosts sempre aceitos no header Host. ``testserver`` é o host padrão do
# TestClient; os demais cobrem desenvolvimento local e sondas de loopback.
# O host público do Render é acrescentado por ``RENDER_EXTERNAL_HOSTNAME``.
DEFAULT_TRUSTED_HOSTS = ("localhost", "127.0.0.1", "testserver")

# Cotas diárias dos planos usados pelo beta. O orçamento configurado precisa
# ficar abaixo da cota para não esgotá-la sem margem operacional.
EMAIL_PROVIDER_QUOTAS = {
    "brevo": 300,
    "resend": 3_000,
    "fake": 10_000,
    "none": 10_000,
}


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

    # Allowlist do header Host (TrustedHostMiddleware). Lista extra separada por
    # vírgula, sem esquema, porta ou curinga. RENDER_EXTERNAL_HOSTNAME, quando
    # presente, entra na allowlist porque o Render é a origem pública do demo.
    trusted_hosts: str = ""
    render_external_hostname: str | None = Field(
        default=None,
        validation_alias="RENDER_EXTERNAL_HOSTNAME",
        max_length=253,
    )

    # Gate de versão do app mobile (ADR 0051). Desativado no desenvolvimento
    # local/testes; o demo/produção pode ativá-lo sem alterar o código.
    app_version_gate_enabled: bool = False
    min_app_version: str = Field(default="1.0.1", pattern=r"^\d{1,5}\.\d{1,5}\.\d{1,5}$")
    latest_app_version: str = Field(default="1.0.1", pattern=r"^\d{1,5}\.\d{1,5}\.\d{1,5}$")
    app_update_url: str | None = Field(default=None, max_length=500)

    # Segredo de hash de telefone/OTP/IP. O valor padrão só vale para
    # desenvolvimento e testes; ambientes reais precisam definir JOGA_PHONE_HASH_SECRET.
    phone_hash_secret: SecretStr = SecretStr(DEFAULT_PHONE_HASH_SECRET)
    otp_ttl_seconds: int = Field(default=300, ge=60, le=900)
    otp_max_attempts: int = Field(default=5, ge=1, le=10)
    otp_resend_cooldown_seconds: int = Field(default=60, ge=0, le=300)
    otp_max_per_hour: int = Field(default=5, ge=1, le=20)
    otp_max_per_ip_per_hour: int = Field(default=20, ge=1, le=200)
    otp_receipt_ttl_seconds: int = Field(default=600, ge=60, le=1800)

    # Fase de autenticação (ADR 0050). O padrão do código preserva o caminho de
    # telefone já existente; o perfil beta é aplicado por variável de ambiente
    # em `.env.example`. Nunca habilitar e-mail sem provedor configurado.
    auth_email_enabled: bool = False
    auth_phone_enabled: bool = True
    allow_email_registration: bool = True
    allow_phone_registration: bool = True
    phone_required_for_booking: bool = False
    signup_mode: str = Field(default="open", pattern="^(open|closed)$")

    # E-mail transacional (ADR 0050). Nenhum segredo tem valor padrão.
    email_provider: str = Field(default="none", pattern="^(brevo|resend|none|fake)$")
    email_api_key: SecretStr | None = None
    email_from: str | None = Field(default=None, max_length=254)
    email_from_name: str = Field(default="JOGA", min_length=1, max_length=80)
    email_reply_to: str | None = Field(default=None, max_length=254)
    email_timeout_seconds: int = Field(default=10, ge=1, le=60)
    email_daily_budget: int = Field(default=250, ge=1, le=10_000)
    email_code_ttl_seconds: int = Field(default=600, ge=60, le=1800)
    email_max_per_address_per_hour: int = Field(default=5, ge=1, le=20)
    email_max_per_ip_per_hour: int = Field(default=50, ge=1, le=200)
    email_resend_cooldown_seconds: int = Field(default=60, ge=0, le=300)
    # Beta: rede móvel/CGNAT compartilha IP. O limite por endereço continua
    # separado; a evolução para limite por dispositivo está em PENDENCIAS.
    signup_max_per_ip_per_day: int = Field(default=20, ge=1, le=100)
    # Lista adicional, separada por vírgula. A lista embutida cobre provedores
    # descartáveis conhecidos e não depende de serviço pago.
    email_disposable_domains: str = ""
    email_max_delivery_attempts: int = Field(default=5, ge=1, le=20)
    email_bounce_threshold: int = Field(default=3, ge=1, le=20)
    email_change_cooldown_hours: int = Field(default=24, ge=1, le=168)
    # Login por senha (ADR 0050). Janela fixa de 15 min.
    email_login_max_per_email: int = Field(default=10, ge=1, le=100)
    email_login_max_per_ip: int = Field(default=30, ge=1, le=300)
    # Drenagem da Outbox dentro do processo da API. O Render free não mantém
    # worker e o cron do GitHub é best-effort; ligada no demo, desligada por
    # padrão (inclusive em teste). O workflow agendado continua como reserva.
    email_inline_drain_enabled: bool = False
    email_inline_drain_interval_seconds: int = Field(default=30, ge=10, le=300)

    # Segredo de hash de access/refresh tokens. O padrão só vale para
    # desenvolvimento e testes; ambientes reais precisam definir JOGA_TOKEN_HASH_SECRET.
    token_hash_secret: SecretStr = SecretStr(DEFAULT_TOKEN_HASH_SECRET)
    access_token_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    # App mobile de uso esporádico (ADR 0059): 30 dias de inatividade e 180
    # dias de vida absoluta da família de refresh. O access continua curto e
    # o refresh rotativo/revogável cobre a sessão de longo prazo.
    refresh_absolute_ttl_days: int = Field(default=180, ge=1, le=365)
    refresh_idle_ttl_days: int = Field(default=30, ge=1, le=90)
    # Corrida legítima: duas chamadas concorrentes com o mesmo refresh. Dentro
    # desta janela, o token imediatamente anterior não revoga a família e a
    # resposta é 401 refresh_retry_required. 0 desliga a tolerância.
    refresh_reuse_grace_seconds: int = Field(default=30, ge=0, le=300)

    # Painel web: refresh em cookie HttpOnly e CSRF em cookie legível.
    # Fora do ambiente local, JOGA_WEB_COOKIE_SECURE deve ser true: o boot
    # falha se o cookie de sessão puder trafegar sem Secure.
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
    # Verificação de CNPJ de organizações (ADR 0062). A consulta é síncrona no
    # cadastro e falha fechada; cache curto evita repetição em retries do app.
    cnpj_api_base_url: str = Field(
        default="https://brasilapi.com.br/api/cnpj/v1",
        min_length=1,
    )
    cnpj_timeout_seconds: int = Field(default=5, ge=1, le=15)
    cnpj_lookup_attempts: int = Field(default=2, ge=1, le=3)
    cnpj_cache_ttl_seconds: int = Field(default=300, ge=0, le=3600)
    organization_cnpj_recheck_days: int = Field(default=7, ge=1, le=30)
    organization_cnpj_retry_hours: int = Field(default=6, ge=1, le=48)
    geo_timeout_seconds: int = Field(default=3, ge=1, le=15)
    geo_cache_ttl_days: int = Field(default=30, ge=1, le=365)
    geo_rate_limit_per_minute: int = Field(default=30, ge=1, le=600)
    geo_provider_version: str = Field(default="brasilapi_v1", min_length=1, max_length=40)
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

    # PSP. O simulador é o padrão local/CI. Fora do ambiente local, o Mercado
    # Pago é obrigatório com credenciais de produção; não há fallback silencioso
    # para simulador nem e-mail de pagador fixo.
    psp_provider: str = Field(default="simulator", pattern="^(simulator|mercadopago)$")
    mercado_pago_access_token: SecretStr | None = None
    mercado_pago_webhook_secret: SecretStr | None = None
    mercado_pago_base_url: str = Field(
        default="https://api.mercadopago.com",
        min_length=1,
        max_length=200,
    )
    # O e-mail do pagador vem do usuário (`users.email`); não existe e-mail
    # global fixo para cobrança.
    mercado_pago_notification_url: str | None = Field(default=None, max_length=500)
    psp_timeout_seconds: int = Field(default=10, ge=1, le=60)

    # Modelo tributário e custódia (ADR 0049). Nada aqui liga operação real por
    # acidente: `real` exige referência do parecer, e os modos sem implementação
    # falham no boot em vez de degradar em silêncio.
    money_mode: str = Field(default="simulated", pattern="^(simulated|real)$")
    legal_approval_ref: str | None = Field(default=None, max_length=120)
    legal_approval_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    legal_approval_date: date | None = None
    fiscal_mode: str = Field(default="disabled", pattern="^(disabled|placeholder|provider)$")
    custody_model: str = Field(default="B", pattern="^(B|C)$")
    # Taxa de intermediação (ADR 0049 §2.4) e alíquota usada apenas em relatório
    # de margem. Nenhum lançamento histórico depende da alíquota.
    tax_rate_bps: int = Field(default=1550, ge=0, le=10_000)
    fee_percent_bps: int = Field(default=2_000, ge=0, le=10_000)
    fee_min_cents: int = Field(default=800, ge=0)
    cancellation_provision_cents: int = Field(default=20, ge=0)
    payout_requires_fiscal_document: bool = True
    fiscal_document_grace_days: int = Field(default=5, ge=0, le=60)
    venue_receivable_offset_days: int = Field(default=90, ge=1, le=365)
    credit_refund_days: int = Field(default=30, ge=1, le=180)
    # CPF cifrado (ADR 0049 §9.3). A chave de 32 bytes fica fora do banco; o
    # ``cpf_key_id`` acompanha o ciphertext e as chaves anteriores são usadas
    # apenas para leitura durante a rotação.
    cpf_key: SecretStr | None = None
    cpf_key_id: str | None = Field(default=None, max_length=20)
    cpf_previous_keys: dict[str, SecretStr] = Field(default_factory=dict)

    # Push: transporte externo. O webhook é um adaptador operacional; a
    # central de notificações continua sendo a fonte de verdade.
    push_webhook_url: str | None = Field(default=None, max_length=500)
    push_timeout_seconds: int = Field(default=5, ge=1, le=30)

    # Liberação ao estabelecimento: no horário da partida (ADR 0039). O atraso
    # opcional existe apenas para operação; o padrão é zero.
    release_delay_hours: int = Field(default=2, ge=0, le=720)

    # Janela técnica de contestação, contada a partir de ``eligible_at``.
    # Decisão de 17/11/2026: 72 h, persistida como snapshot na liberação e na
    # contestação. O valor é configurável, mas o snapshot não é recalculado.
    dispute_window_hours: int = Field(default=72, ge=1, le=720)

    # Revisão humana de resultados (Fase 7). Lista separada por vírgula; vazia
    # significa que nenhum operador está autorizado.
    review_operators: str = ""

    # Administração de plataforma (catálogo de esportes e usuários). Allowlist
    # de user IDs separada por vírgula; vazia significa que ninguém é admin.
    platform_admins: str = ""

    # Compra de tickets. Desligada por padrão: o app exibe carteira e pacotes,
    # mas abrir compra exige decisão operacional explícita.
    ticket_purchase_enabled: bool = False

    # Organização da plataforma que possui as quadras públicas. Não aparece em
    # listagens de estabelecimentos e é operada por platform_admin sem vínculo.
    platform_org_slug: str = Field(default="joga-publico", min_length=2, max_length=60)

    # Limite de POSTs de resultado por usuário em uma janela de 60 segundos.
    results_rate_limit_per_minute: int = Field(default=30, ge=1, le=600)

    @property
    def review_operator_ids(self) -> frozenset[str]:
        return frozenset(item.strip() for item in self.review_operators.split(",") if item.strip())

    @property
    def platform_admin_ids(self) -> frozenset[str]:
        return frozenset(item.strip() for item in self.platform_admins.split(",") if item.strip())

    @property
    def email_disposable_domain_set(self) -> frozenset[str]:
        return frozenset(
            item.strip().lower().rstrip(".")
            for item in self.email_disposable_domains.split(",")
            if item.strip()
        )

    @property
    def email_provider_quota(self) -> int | None:
        """Cota diária do plano do provedor usado no boot."""
        if self.email_provider in {"brevo", "resend"}:
            return EMAIL_PROVIDER_QUOTAS[self.email_provider]
        return None

    @property
    def trusted_host_list(self) -> list[str]:
        """Allowlist efetiva do header Host, sem duplicatas e em minúsculas."""
        hosts = list(DEFAULT_TRUSTED_HOSTS)
        external_hostname = (self.render_external_hostname or "").strip().lower()
        if external_hostname:
            hosts.append(external_hostname)
        for item in self.trusted_hosts.split(","):
            candidate = item.strip().lower()
            if candidate and candidate not in hosts:
                hosts.append(candidate)
        return hosts

    # Moderação (Fase 17A). Operadores são nomes internos, não usuários do app.
    moderation_operators: str = ""
    moderation_admin_user_ids: str = ""
    moderation_max_reports_per_day: int = Field(default=5, ge=1, le=50)
    moderation_false_report_threshold: int = Field(default=3, ge=1, le=20)
    moderation_false_report_cooldown_days: int = Field(default=7, ge=1, le=90)
    moderation_retention_days: int = Field(default=180, ge=30, le=3650)

    @property
    def moderation_operator_ids(self) -> frozenset[str]:
        return frozenset(
            item.strip() for item in self.moderation_operators.split(",") if item.strip()
        )

    @property
    def moderation_admin_ids(self) -> frozenset[str]:
        return frozenset(
            item.strip() for item in self.moderation_admin_user_ids.split(",") if item.strip()
        )

    # Apenas para desenvolvimento local: fixa o OTP para facilitar testes no app.
    # Nunca usar em ambiente compartilhado/produção.
    dev_fixed_otp: str | None = Field(default=None, pattern=r"^\d{6}$")

    @field_validator("dev_fixed_otp", mode="before")
    @classmethod
    def blank_dev_fixed_otp_is_disabled(cls, value: object) -> object:
        """Permite ``JOGA_DEV_FIXED_OTP=`` no ambiente sem quebrar o boot."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("trusted_hosts", "render_external_hostname")
    @classmethod
    def validate_trusted_host(cls, value: str | None) -> str | None:
        """Recusa curinga, esquema, porta ou caminho na allowlist de Host."""
        if value is None:
            return None
        for item in value.split(","):
            entry = item.strip()
            if not entry:
                continue
            if "*" in entry:
                raise ValueError("allowlist de Host nao aceita curinga")
            if any(marker in entry for marker in ("://", "/", ":", " ")):
                raise ValueError(
                    "allowlist de Host aceita apenas nomes de host, sem esquema, porta ou caminho"
                )
        return value

    @property
    def webauthn_origins(self) -> list[str]:
        return [self.webauthn_origin_android, self.webauthn_origin_web]

    @model_validator(mode="after")
    def validate_app_version_policy(self) -> Self:
        """Garante semver coerente e URL de atualização HTTPS (ADR 0051)."""
        minimum = parse_version(self.min_app_version)
        latest = parse_version(self.latest_app_version)
        if minimum is None or latest is None:
            raise ValueError("JOGA_MIN_APP_VERSION/JOGA_LATEST_APP_VERSION devem ser semver")
        if minimum > latest:
            raise ValueError("JOGA_MIN_APP_VERSION nao pode ser maior que JOGA_LATEST_APP_VERSION")
        if self.app_update_url and not self.app_update_url.strip().startswith("https://"):
            raise ValueError("JOGA_APP_UPDATE_URL deve usar https")
        return self

    @model_validator(mode="after")
    def validate_environment_profile(self) -> Self:
        token = (
            self.mercado_pago_access_token.get_secret_value().strip()
            if self.mercado_pago_access_token is not None
            else ""
        )
        if self.psp_provider == "mercadopago" and not token:
            raise ValueError("JOGA_MERCADO_PAGO_ACCESS_TOKEN é obrigatório com psp=mercadopago")
        if is_local(self.environment):
            return self
        if is_demo(self.environment):
            if self.psp_provider != "simulator":
                raise ValueError("JOGA_PSP_PROVIDER=simulator é obrigatório no ambiente demo")
            if self.money_mode != "simulated":
                raise ValueError("JOGA_MONEY_MODE=simulated é obrigatório no ambiente demo")
            if self.ticket_purchase_enabled:
                raise ValueError(
                    "JOGA_TICKET_PURCHASE_ENABLED=false é obrigatório no ambiente demo"
                )
            if self.dev_fixed_otp is not None:
                raise ValueError("JOGA_DEV_FIXED_OTP não pode ser usado no ambiente demo")
            self._require_non_default_hash_secrets()
            return self
        if self.dev_fixed_otp is not None:
            raise ValueError("JOGA_DEV_FIXED_OTP só pode ser usado em ambiente local")
        if self.psp_provider != "mercadopago":
            raise ValueError("JOGA_PSP_PROVIDER=mercadopago é obrigatório fora do ambiente local")
        webhook_secret = (
            self.mercado_pago_webhook_secret.get_secret_value().strip()
            if self.mercado_pago_webhook_secret is not None
            else ""
        )
        if not webhook_secret:
            raise ValueError(
                "JOGA_MERCADO_PAGO_WEBHOOK_SECRET é obrigatório fora do ambiente local"
            )
        notification_url = (self.mercado_pago_notification_url or "").strip()
        if not notification_url.startswith("https://"):
            raise ValueError(
                "JOGA_MERCADO_PAGO_NOTIFICATION_URL deve ser uma URL HTTPS pública "
                "fora do ambiente local"
            )
        self._require_non_default_hash_secrets()
        return self

    def _require_non_default_hash_secrets(self) -> None:
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

    @model_validator(mode="after")
    def validate_web_cookie_secure(self) -> Self:
        """Recusa boot com cookie de sessão sem ``Secure`` fora do local.

        Em local/teste o painel roda em HTTP e o cookie sem ``Secure`` é
        aceitável. Fora disso, depender de alguém lembrar da variável é frágil:
        o boot falha em vez de emitir um refresh token interceptável.
        """
        if not is_local(self.environment) and not self.web_cookie_secure:
            raise ValueError("JOGA_WEB_COOKIE_SECURE=true é obrigatório fora do ambiente local")
        return self

    @model_validator(mode="after")
    def validate_cpf_key(self) -> Self:
        """Valida a chave de CPF e exige que exista fora do ambiente local.

        O CPF não pode ser cifrado sem chave, e degradar para texto claro é
        inaceitável. O placeholder de 32 bytes zero é recusado sempre.
        """
        materials: list[tuple[str, str]] = []
        if self.cpf_key is not None:
            if not (self.cpf_key_id or "").strip():
                raise ValueError("JOGA_CPF_KEY_ID é obrigatório quando JOGA_CPF_KEY existe")
            materials.append((self.cpf_key.get_secret_value(), "JOGA_CPF_KEY"))
        for key_id, key in self.cpf_previous_keys.items():
            if not key_id.strip():
                raise ValueError("JOGA_CPF_PREVIOUS_KEYS exige ids de chave não vazios")
            materials.append((key.get_secret_value(), f"JOGA_CPF_PREVIOUS_KEYS[{key_id}]"))
        for value, name in materials:
            try:
                raw = base64.b64decode(value.strip(), validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError(f"{name} deve ser base64 válido") from exc
            if len(raw) != 32:
                raise ValueError(f"{name} deve ter 32 bytes")
            if raw == b"\x00" * 32:
                raise ValueError(f"{name} não pode ser o placeholder de desenvolvimento")
        if not is_local(self.environment) and self.cpf_key is None:
            raise ValueError("JOGA_CPF_KEY é obrigatório fora do ambiente local")
        return self

    @model_validator(mode="after")
    def validate_auth_phase_flags(self) -> Self:
        """Falha no boot em combinações de credencial inválidas (ADR 0050)."""
        local = is_local(self.environment)

        if not (self.auth_email_enabled or self.auth_phone_enabled):
            raise ValueError("pelo menos uma credencial deve estar habilitada")

        if not self.auth_phone_enabled:
            if self.allow_phone_registration:
                raise ValueError("JOGA_ALLOW_PHONE_REGISTRATION exige JOGA_AUTH_PHONE_ENABLED=true")
            if self.phone_required_for_booking:
                raise ValueError(
                    "JOGA_PHONE_REQUIRED_FOR_BOOKING exige JOGA_AUTH_PHONE_ENABLED=true"
                )

        if self.email_provider == "fake" and not local:
            raise ValueError("JOGA_EMAIL_PROVIDER=fake só pode ser usado em ambiente local")

        if self.email_provider != "none":
            api_key = (
                self.email_api_key.get_secret_value().strip()
                if self.email_api_key is not None
                else ""
            )
            if not api_key:
                raise ValueError("JOGA_EMAIL_API_KEY é obrigatório com provedor de e-mail")
            if not (self.email_from or "").strip():
                raise ValueError("JOGA_EMAIL_FROM é obrigatório com provedor de e-mail")
            if not (self.email_from_name or "").strip():
                raise ValueError("JOGA_EMAIL_FROM_NAME é obrigatório com provedor de e-mail")

        if self.auth_email_enabled and self.email_provider == "none":
            raise ValueError(
                "JOGA_AUTH_EMAIL_ENABLED=true exige JOGA_EMAIL_PROVIDER diferente de none"
            )

        from app.modules.email.addresses import InvalidEmail, normalize_email

        for name, value in (
            ("JOGA_EMAIL_FROM", self.email_from),
            ("JOGA_EMAIL_REPLY_TO", self.email_reply_to),
        ):
            if value is None or not value.strip():
                continue
            try:
                normalize_email(value)
            except InvalidEmail as error:
                raise ValueError(f"{name} inválido: {error}") from error

        quota = self.email_provider_quota
        if quota is not None and self.email_daily_budget >= quota:
            raise ValueError(
                f"JOGA_EMAIL_DAILY_BUDGET deve ser menor que a cota do plano "
                f"({quota}/dia para {self.email_provider})"
            )

        return self

    @model_validator(mode="after")
    def reject_unimplemented_financial_modes(self) -> Self:
        """Falha cedo nos modos que ainda dependem de terceiro (ADR 0049 §5)."""
        if self.money_mode == "real":
            if not (self.legal_approval_ref or "").strip():
                raise ValueError(
                    "JOGA_MONEY_MODE=real exige JOGA_LEGAL_APPROVAL_REF com a referência do "
                    "parecer fiscal e jurídico aprovados"
                )
            if self.legal_approval_sha256 is None:
                raise ValueError(
                    "JOGA_MONEY_MODE=real exige JOGA_LEGAL_APPROVAL_SHA256 do PDF do parecer"
                )
            if self.legal_approval_date is None:
                raise ValueError("JOGA_MONEY_MODE=real exige JOGA_LEGAL_APPROVAL_DATE do parecer")
            if self.legal_approval_date > date.today():
                raise ValueError("JOGA_LEGAL_APPROVAL_DATE não pode estar no futuro")
        if self.custody_model == "C":
            raise ValueError(
                "JOGA_CUSTODY_MODEL=C não está implementado: exige conta de escrow com "
                "titular diferente do JOGA"
            )
        if self.fiscal_mode == "provider":
            raise ValueError(
                "JOGA_FISCAL_MODE=provider não está implementado: falta integração de NFS-e"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
