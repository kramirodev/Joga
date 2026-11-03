# Modelo de dados — JOGA

Documento incremental. Cobre o subconjunto de **identidade** (Fase 3) e de **perfil, disponibilidade, região e locais** (Fase 4); as demais entidades serão adicionadas nas fases correspondentes.

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

## `sports`

Catálogo de modalidades.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `slug` | varchar(40) | único |
| `name` | varchar(80) | nome exibido |
| `active` | boolean | default `true` |
| `created_at` | timestamptz | default `now()` |

Seeds: `futebol` e `volei`.

## `sport_formats`

Configuração versionada do formato esportivo. Constraints garantem `total_participants = team_size * 2` e `duration_minutes = play_minutes + break_minutes`.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `sport_id` | UUID | FK `sports.id`, cascade |
| `slug` | varchar(40) | único com `version` |
| `name` | varchar(80) | nome exibido |
| `team_size` | integer | > 0 |
| `total_participants` | integer | = 2 × `team_size` |
| `play_minutes` | integer | > 0 |
| `break_minutes` | integer | >= 0 |
| `duration_minutes` | integer | = `play_minutes` + `break_minutes` |
| `version` | integer | default `1` |
| `active` | boolean | default `true` |
| `created_at` | timestamptz | default `now()` |

Seeds ativos: `futebol-5x5` (5 por equipe, 10 participantes, 50 + 10 = 60 min) e `volei-6x6` (6 por equipe, 12 participantes, 60 + 0 = 60 min).

## `user_profiles`

Dados básicos do jogador. Público: nome de exibição e bio.

| Coluna | Tipo | Regra |
|---|---|---|
| `user_id` | UUID | PK e FK `users.id`, cascade |
| `display_name` | varchar(60) | opcional |
| `bio` | varchar(280) | opcional |
| `created_at` | timestamptz | default `now()` |
| `updated_at` | timestamptz | default `now()` |

## `user_sport_profiles`

Nível autodeclarado e preferência de quadra por formato.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK `users.id`, cascade |
| `format_id` | UUID | FK `sport_formats.id`, cascade |
| `level` | varchar(20) | `beginner`, `intermediate`, `advanced` |
| `court_preference` | varchar(20) | `PUBLIC_ONLY`, `PRIVATE_ONLY`, `ANY` (default) |
| `created_at` | timestamptz | default `now()` |
| `updated_at` | timestamptz | default `now()` |

Constraint única `(user_id, format_id)`; a substituição do conjunto é transacional (apaga e regrava na mesma transação).

## `availabilities`

Janelas semanais recorrentes de disponibilidade.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK `users.id`, cascade |
| `weekday` | smallint | 1 a 7 |
| `start_time` | time | < `end_time` |
| `end_time` | time | > `start_time` |
| `timezone` | varchar(64) | IANA, padrão `America/Sao_Paulo` |
| `created_at` | timestamptz | default `now()` |

Índice `(user_id, weekday)`. Um mesmo dia pode ter **várias faixas** (por exemplo, sábado às 14h, 18h e 20h) e dias diferentes podem ter quantidades e horários distintos. Sobreposição no mesmo dia é rejeitada pelo serviço, não pelo banco.

## `user_regions`

Centro **aproximado** de busca. Guarda apenas o ponto arredondado (duas casas decimais), nunca a coordenada residencial exata, e nenhum histórico de deslocamento.

| Coluna | Tipo | Regra |
|---|---|---|
| `user_id` | UUID | PK e FK `users.id`, cascade |
| `source` | varchar(10) | `gps` ou `cep` |
| `cep` | varchar(8) | obrigatório quando `source = 'cep'` |
| `city` | varchar(120) | obrigatório quando `source = 'cep'` |
| `state` | varchar(2) | obrigatório quando `source = 'cep'` |
| `radius_km` | integer | 1 a 200 |
| `center_lat` | double | -90 a 90, arredondado |
| `center_lng` | double | -180 a 180, arredondado |
| `updated_at` | timestamptz | default `now()` |

Usar GPS substitui a região anterior e limpa `cep`/`city`/`state`; não há acúmulo de pontos.

## `venues`

Local esportivo descoberto. Catálogo **vazio** nesta fase; cadastro público pertence às Fases 11/14.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `name` | varchar(120) | nome do local |
| `kind` | varchar(20) | `public` ou `private` |
| `city` | varchar(120) | município |
| `state` | varchar(2) | UF |
| `cep` | varchar(8) | opcional |
| `address` | varchar(200) | opcional |
| `lat` | double | -90 a 90 |
| `lng` | double | -180 a 180 |
| `active` | boolean | default `true` |
| `created_at` | timestamptz | default `now()` |

Índices: `ix_venues_city_state` (`city`, `state`) e `ix_venues_location_gist`, índice GiST sobre `ST_SetSRID(ST_MakePoint(lng, lat), 4326)` criado apenas no PostgreSQL. A busca usa `ST_DWithin` sobre `geography` com raio em metros, ordenada por `ST_Distance`.

Quadras (`venue_spaces`), vínculo esporte–quadra (`venue_sports`), agenda (`venue_availability`) e reservas (`bookings`) **não** existem nesta fase.

## `queue_entries`

Entrada persistente na fila. O usuário mantém no máximo uma entrada ativa por formato e modo.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK `users.id`, cascade |
| `format_id` | UUID | FK `sport_formats.id`, cascade |
| `mode` | varchar(10) | `casual` ou `ranked` |
| `court_preference` | varchar(20) | preferência efetiva da entrada |
| `level` | varchar(20) | nível no momento da entrada |
| `status` | varchar(20) | `waiting`, `matched`, `cancelled`, `expired` |
| `center_lat` / `center_lng` | double | centro aproximado copiado de `user_regions` |
| `radius_km` | integer | 1 a 200 |
| `lobby_id` | UUID | FK `lobbies.id`, `SET NULL` |
| `created_at` / `updated_at` | timestamptz | default `now()` |
| `matched_at` | timestamptz | opcional |
| `expires_at` | timestamptz | TTL da entrada (24 h por padrão) |

Índice `ix_queue_entries_waiting` (`format_id`, `mode`, `status`, `created_at`) e índice único parcial `uq_queue_entries_active` em (`user_id`, `format_id`, `mode`) quando `status = 'waiting'` — impede duplicidade ativa, inclusive sob concorrência.

## `lobbies`

Agrupamento formado pelo matchmaking, com horário concreto.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `format_id` | UUID | FK `sport_formats.id`, `RESTRICT` |
| `format_version` | integer | versão do formato aplicada |
| `origin` | varchar(20) | `matchmaking` ou `manual` |
| `mode` | varchar(10) | `casual` ou `ranked` |
| `status` | varchar(20) | `scheduled`, `cancelled`, `completed` |
| `court_preference` | varchar(20) | interseção efetiva das preferências |
| `scheduled_start_at` / `scheduled_end_at` | timestamptz | horário concreto; fim > início |
| `duration_minutes` | integer | copiada do formato |
| `center_lat` / `center_lng` | double | média geográfica dos centros aproximados |
| `radius_km` | integer | menor raio informado, limitado a 30 km |
| `venue_id` | UUID | FK `venues.id`, `SET NULL`; nulo nesta fase |
| `algorithm_version` | varchar(40) | ex. `level_v1` |
| `created_at` | timestamptz | default `now()` |

## `lobby_participants`

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `lobby_id` | UUID | FK `lobbies.id`, cascade |
| `user_id` | UUID | FK `users.id`, cascade |
| `queue_entry_id` | UUID | FK `queue_entries.id`, `SET NULL`, único |
| `team` | smallint | 1 ou 2 |
| `level` | varchar(20) | nível usado no balanceamento |
| `created_at` | timestamptz | default `now()` |

Únicos: `(lobby_id, user_id)` e `queue_entry_id`.

## `matchmaking_runs`

Trilha de cada rodada do worker.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `status` | varchar(20) | `running`, `completed`, `failed` |
| `algorithm_version` | varchar(40) | política aplicada |
| `entries_expired` | integer | >= 0 |
| `lobbies_formed` | integer | >= 0 |
| `started_at` | timestamptz | default `now()` |
| `finished_at` | timestamptz | opcional |

## `matches`

Partida criada a partir de um lobby, com estado controlado pelo servidor.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `lobby_id` | UUID | FK `lobbies.id`, cascade, único |
| `state` | varchar(24) | `PENDING_CONFIRMATION`, `READY`, `IN_PROGRESS`, `RESULT_PENDING`, `FINALIZED`, `DISPUTED`, `VOIDED`, `CANCELLED`, `EXPIRED` |
| `scheduled_start_at` / `scheduled_end_at` | timestamptz | cópia do lobby; fim > início |
| `confirmation_deadline` | timestamptz | `min(formado + 24 h, início − 45 min)` |
| `check_in_opens_at` | timestamptz | início − 60 min |
| `check_in_deadline` | timestamptz | início − 30 min |
| `substitution_deadline` | timestamptz | início − 15 min |
| `cancelled_reason` | varchar(40) | `declined`, `confirmation_deadline`, `no_substitute`, `missing_check_in` |
| `started_at` | timestamptz | quando entrou em `IN_PROGRESS` |
| `created_at` / `updated_at` | timestamptz | default `now()` |

Constraints garantem a ordem dos prazos e que tudo acontece antes do início. A fase 6 só alcança `PENDING_CONFIRMATION → READY → IN_PROGRESS`, com saídas `CANCELLED`/`EXPIRED`.

## `match_participants`

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `match_id` | UUID | FK `matches.id`, cascade |
| `user_id` | UUID | FK `users.id`, cascade; único com `match_id` |
| `team` | smallint | 1 ou 2 |
| `level` | varchar(20) | nível usado no balanceamento |
| `status` | varchar(20) | `invited`, `confirmed`, `declined`, `checked_in`, `no_show` |
| `is_substitute` | boolean | suplente convidado após ausência |
| `queue_entry_id` | UUID | FK `queue_entries.id`, `SET NULL` |
| `invited_at` | timestamptz | default `now()` |
| `confirmed_at` / `checked_in_at` | timestamptz | opcionais |
| `updated_at` | timestamptz | default `now()` |

Índice `(match_id, status)`. Suplente entra na vaga do ausente mantendo o time, e o ausente fica `no_show` sem contar como ativo.

## `match_state_transitions`

Trilha append-only das transições, com ator e motivo.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `match_id` | UUID | FK `matches.id`, cascade |
| `from_state` | varchar(24) | nulo na criação |
| `to_state` | varchar(24) | obrigatório |
| `actor_user_id` | UUID | FK opcional `users.id`, `SET NULL` |
| `reason` | text | motivo auditável |
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
- Catálogo de locais vazio: quadras, vínculo esporte–quadra, agenda e reservas pertencem às Fases 11/14.
- Penalidades por no-show (banimento temporário e reputação) ficam para as Fases 8/17; a Fase 6 só registra `no_show`.
- Capitães adiados: dependem de Trust Factor, MMR e histórico de partidas.
- Geocoding de CEP depende do BrasilAPI (gratuito, sem SLA); cache é por processo e some no restart.
- Disponibilidade não trata feriados, exceções pontuais nem conversão de fuso por usuário.

## Referência

- Migração: `backend/migrations/versions/3c9d51a7e2b4_identity_foundation.py`, `d4a7f2c9e610_add_session_access_and_receipt.py` e `b8d2f4a6c910_add_profile_and_discovery.py`
- Modelos: `backend/app/modules/identity/models.py` e `backend/app/modules/profile/models.py`
- Decisões: ADR 0012, ADR 0013, ADR 0014, ADR 0015 e ADR 0019.
