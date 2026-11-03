# Modelo de dados — JOGA

Documento incremental. Nesta etapa cobre apenas o subconjunto de **identidade** da Fase 3; as demais entidades serão adicionadas nas fases correspondentes.

## Convenções

- Chaves internas em `UUID`; telefone nunca é chave primária.
- Datas de evento em `timestamptz` (UTC no backend).
- Nomes de constraints seguem a convenção de `app/infrastructure/database/base.py`.
- Migrações Alembic revisáveis; nenhuma alteração manual de schema.
- Dados sensíveis não são persistidos em claro: telefone, IP e OTP usam HMAC-SHA256 com segredo de ambiente.

## `users`

Identidade central e estado da conta.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `status` | varchar(20) | `pending`, `active`, `suspended`, `deleted` |
| `created_at` | timestamptz | default `now()` |
| `updated_at` | timestamptz | default `now()` |

## `user_phones`

Telefone verificado. Nesta iteração guarda apenas o hash de busca.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK `users.id`, cascade |
| `phone_hash` | varchar(64) | HMAC do telefone E.164 |
| `is_primary` | boolean | contato principal |
| `verified_at` | timestamptz | quando verificado |
| `released_at` | timestamptz | libera o hash para reutilização |
| `created_at` | timestamptz | default `now()` |

Constraint: índice único parcial `uq_user_phones_active_hash` em `phone_hash` quando `released_at IS NULL`. Na troca de telefone, o vínculo antigo recebe `released_at` e o novo é gravado verificado; a troca revoga todas as sessões (ADR 0016).

## `phone_challenges`

Desafio OTP de uso único.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK e vínculo do HMAC do OTP |
| `phone_hash` | varchar(64) | hash do telefone |
| `user_id` | UUID | FK opcional `users.id` |
| `purpose` | varchar(20) | `registration`, `login`, `phone_change`, `recovery` |
| `code_hash` | varchar(64) | HMAC do OTP |
| `attempts` | integer | tentativas consumidas |
| `max_attempts` | integer | limite por desafio |
| `request_ip_hash` | varchar(64) | hash do IP, nunca o IP |
| `expires_at` | timestamptz | expiração |
| `consumed_at` | timestamptz | uso único da verificação |
| `receipt_used_at` | timestamptz | consumo do recibo pelo cadastro/login |
| `created_at` | timestamptz | default `now()` |

Índices: `ix_phone_challenges_phone_created` (`phone_hash`, `created_at`).

O `id` do desafio consumido (`consumed_at` preenchido) funciona como recibo de verificação de curta duração; a expiração do recibo é calculada a partir de `consumed_at` + política (`JOGA_OTP_RECEIPT_TTL_SECONDS`, padrão 600 s). O recibo não é sessão (ADR 0015).

## `devices`

Dispositivo vinculado ao usuário.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK `users.id`, cascade |
| `platform` | varchar(20) | `android`, `ios`, `web`, `unknown` |
| `name` | varchar(80) | rótulo opcional |
| `created_at` | timestamptz | default `now()` |
| `last_seen_at` | timestamptz | opcional |
| `revoked_at` | timestamptz | opcional |

## `passkey_challenges`

Desafio WebAuthn de uso único para registro ou autenticação.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK opcional `users.id` (registro/autenticação específica) |
| `challenge` | varchar(128) | nonce público, único |
| `purpose` | varchar(20) | `registration` ou `authentication` |
| `expires_at` | timestamptz | expiração curta |
| `consumed_at` | timestamptz | uso único |
| `request_ip_hash` | varchar(64) | hash do IP |
| `created_at` | timestamptz | default `now()` |

O desafio é um nonce público enviado ao cliente; não é segredo, mas nunca deve ir para logs. O limite de criação por IP/hora é aplicado no serviço.

## `passkey_credentials`

Credencial pública de passkey; não guarda chave privada.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK `users.id`, cascade |
| `device_id` | UUID | FK opcional `devices.id`, `SET NULL` |
| `credential_id` | text | único |
| `public_key` | bytea | chave pública |
| `sign_count` | bigint | contador de assinatura |
| `transports` | json | transportes informados |
| `name` | varchar(80) | rótulo opcional |
| `created_at` | timestamptz | default `now()` |
| `last_used_at` | timestamptz | opcional |
| `revoked_at` | timestamptz | revogação individual |

## `sessions`

Sessão com refresh opaco armazenado apenas como hash.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK `users.id`, cascade |
| `device_id` | UUID | FK opcional `devices.id`, `SET NULL` |
| `family_id` | UUID | família de rotação |
| `access_token_hash` | varchar(64) | HMAC do access token, único |
| `access_expires_at` | timestamptz | expiração curta do access |
| `refresh_token_hash` | varchar(64) | HMAC do refresh, único |
| `created_at` | timestamptz | default `now()` |
| `last_used_at` | timestamptz | opcional |
| `expires_at` | timestamptz | expiração absoluta |
| `idle_expires_at` | timestamptz | expiração por inatividade |
| `revoked_at` | timestamptz | opcional |
| `revoked_reason` | varchar(40) | opcional |
| `replaced_by_session_id` | UUID | rotação |

Índices: `ix_sessions_user_revoked` (`user_id`, `revoked_at`).

Access e refresh são valores opacos; o banco guarda apenas HMAC. A rotação cria uma nova linha na mesma família e marca a anterior como `rotated`/`replaced_by_session_id`. Reutilização de um refresh já rotacionado revoga toda a família. O cadastro/login consome `phone_challenges.receipt_used_at` antes de criar a sessão.

## `security_events`

Evento de autenticação ou abuso, sem PII em claro.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK opcional `users.id`, `SET NULL` |
| `event_type` | varchar(50) | tipo do evento |
| `ip_hash` | varchar(64) | hash do IP |
| `metadata` | json | detalhes não sensíveis |
| `created_at` | timestamptz | default `now()` |

Usado pelos endpoints de OTP para registrar solicitação, verificação, falha e bloqueio, sem telefone, OTP ou IP em claro.

## `audit_logs`

Trilha append-only de ações sensíveis, com ator, recurso, motivo e data.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `actor_user_id` | UUID | FK opcional `users.id`, `SET NULL` |
| `action` | varchar(80) | ação |
| `resource_type` | varchar(50) | tipo do recurso |
| `resource_id` | varchar(100) | identificador do recurso |
| `reason` | text | justificativa |
| `metadata` | json | detalhes não sensíveis |
| `created_at` | timestamptz | default `now()` |

## Pendências deste modelo

- Armazenamento cifrado do telefone para contato futuro (recuperação/notificações): decidir cifra e gestão de chaves antes do bloco de recuperação.
- Estratégia de rotação do segredo de HMAC e versionamento dos hashes.
- Política de retenção e agendamento da limpeza em produção (o script existe).
- Rate limit de tentativas de verificação por IP, além do limite de criação por telefone/IP.
- Vínculo de dispositivo com atestação; hoje há nome/plataforma e revogação por sessões.
- Recuperação assistida quando o usuário perde todas as passkeys e o telefone.
- Índices adicionais para consultas de sessões e eventos após os fluxos reais.
- Migração de dados existentes não se aplica: o banco ainda não tem dados de produção.

## Referência

- Migração: `backend/migrations/versions/3c9d51a7e2b4_identity_foundation.py` e `d4a7f2c9e610_add_session_access_and_receipt.py`
- Modelos: `backend/app/modules/identity/models.py`
- Decisões: ADR 0012, ADR 0013, ADR 0014 e ADR 0015.
