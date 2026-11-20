# RUNBOOK — ambiente local do JOGA

Instruções reproduzíveis para subir o backend, o PostgreSQL/PostGIS local, rodar as verificações e abrir o aplicativo no Android. Reflete o ambiente local das Fases 0–17; não descreve staging, produção ou iOS. A ADR 0049 é a referência para crédito, preço e custódia; dinheiro real permanece bloqueado até os pareceres.

## 1. Pré-requisitos

| Ferramenta | Versão usada na validação | Observação |
|---|---|---|
| Python | 3.14.7 | `pyproject.toml` aceita `>=3.12,<3.15`; a CI usa 3.13 |
| Docker Desktop | Engine 29.6.2, Compose v5.3.1 | Necessário para o PostgreSQL/PostGIS local |
| Node.js | 24.22.1 | Em `.tools/nodejs/node-v24.22.1-win-x64` neste ambiente |
| pnpm | 11.25.0 | Via Corepack; o lockfile é `mobile/pnpm-lock.yaml` |
| JDK | Temurin 17.0.20.1 | Em `.tools/temurin-17/jdk-17.0.20.1+1` neste ambiente; necessário só para o APK |
| Android SDK + adb | Platform-Tools 37.0.1 (ADB 1.0.41) | Em `.tools/android-sdk`; necessário só para build/aparelho |
| Dispositivo Android | Moto G24, Android 14 (arm64) e Moto G7 Play, Android 10 (arm32) | Depuração USB autorizada |

Nenhuma credencial real é necessária. Os valores padrão do Compose e do `.env.example` são locais e descartáveis.

`.tools/` (Node, JDK, Android SDK, platform-tools) é local desta máquina e **não** está no Git. Em outro computador, instale as versões equivalentes e ajuste os caminhos nos comandos abaixo.

## 2. Portas locais

| Serviço | Porta no host | Motivo |
|---|---|---|
| API | 8000 | Padrão local do Uvicorn |
| Metro/Expo | 8081 | Padrão do Expo |
| Painel web (Vite) | 5173 | Padrão local do Vite; faz proxy de `/api` para 8000 |
| PostgreSQL/PostGIS | **5434** | 5432 já é usada pelo PostgreSQL 18 da máquina; 5433 é usada por outro projeto (`matchmaking-engine-db-1`) |

Se outra porta estiver ocupada, defina `POSTGRES_PORT` no ambiente **e** ajuste `JOGA_DATABASE_URL` para a mesma porta. O Compose não altera a URL da aplicação automaticamente.

## 3. PostgreSQL/PostGIS local

```powershell
Set-Location C:\prog\joga
docker compose -f infra/compose.yaml up -d
docker compose -f infra/compose.yaml ps
```

O container se chama `joga-postgres-1`, usa `postgis/postgis:16-3.4` e executa `infra/postgres/init/001-extensions.sql`, que habilita a extensão `postgis`. O healthcheck precisa ficar `healthy` antes de rodar migrações.

Verificação rápida:

```powershell
docker exec joga-postgres-1 psql -U joga -d joga -tAc "SELECT extname FROM pg_extension WHERE extname='postgis'"
```

Recriar o container para aplicar mudanças de porta: `docker compose -f infra/compose.yaml up -d --force-recreate`. O volume `joga_postgres-data` preserva dados entre recriações; remova-o apenas quando quiser um banco descartável de verdade (`docker compose -f infra/compose.yaml down -v`).

## 4. Backend

Criar o ambiente e instalar as versões fixadas:

```powershell
Set-Location C:\prog\joga
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
```

Rodar a API:

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Endpoints:

| Rota | Esperado |
|---|---|
| `GET /api/v1/health/live` | `200 {"status":"ok"}` sem tocar no banco |
| `GET /api/v1/health/ready` | `200 {"status":"ok","database":"ok"}` com o banco respondendo |
| `GET /api/v1/health/ready` (banco fora) | `503 {"detail":{"status":"unavailable","database":"unavailable"}}` |
| `GET /api/docs` | OpenAPI/Swagger local |

Endpoints de identidade (Fase 3):

| Rota | Esperado |
|---|---|
| `POST /api/v1/auth/phone/challenges` | `202` com `challenge_id`, `expires_at` e `resend_after_seconds` |
| `POST /api/v1/auth/phone/challenges/{id}/verify` | `200` com recibo (`challenge_id`, `purpose`, `verified_at`, `receipt_expires_at`) |
| `POST /api/v1/auth/registration` | `201` com tokens e usuário; consome recibo de registro |
| `POST /api/v1/auth/login` | `200` com tokens; consome recibo de login |
| `POST /api/v1/auth/refresh` | `200` com novos tokens; rotaciona o refresh |
| `GET /api/v1/auth/me` | `200` com usuário da sessão (`Authorization: Bearer`) |
| `POST /api/v1/auth/logout` | `204`; revoga a sessão atual |
| `POST /api/v1/auth/logout-all` | `204`; revoga todas as sessões |
| `POST /api/v1/auth/phone-change/challenges` | `202`; envia OTP ao novo telefone (autenticado) |
| `POST /api/v1/auth/phone-change` | `204`; troca o telefone e revoga todas as sessões |
| `POST /api/v1/auth/passkeys/registration/options` | `200`; opções WebAuthn para adicionar passkey (autenticado) |
| `POST /api/v1/auth/passkeys/registration/verify` | `201`; verifica atestação e grava credencial |
| `POST /api/v1/auth/passkeys/authentication/options` | `200`; opções de login por passkey (público) |
| `POST /api/v1/auth/passkeys/authentication/verify` | `200`; verifica asserção e emite sessão |
| `GET /api/v1/auth/passkeys` | `200`; credenciais ativas |
| `DELETE /api/v1/auth/passkeys/{credential_id}` | `204`; revoga credencial |
| `GET /api/v1/auth/devices` | `200`; dispositivos ativos |
| `DELETE /api/v1/auth/devices/{id}` | `204`; revoga dispositivo e sessões dele |
| Telefone igual ao atual | `400 {"detail":{"code":"phone_unchanged"}}` |
| Telefone de outra conta | `409 {"detail":{"code":"phone_already_registered"}}` |
| Recibo inválido/expirado/usado | `400 {"detail":{"code":"invalid_receipt"}}` |
| Telefone já cadastrado | `409 {"detail":{"code":"phone_already_registered"}}` |
| Conta inexistente no login | `404 {"detail":{"code":"account_not_found"}}` |
| Access/refresh inválido | `401 {"detail":{"code":"invalid_token"}}` ou `invalid_refresh_token` |
| Desafio inválido/expirado/bloqueado | `400 {"detail":{"code":"invalid_code_or_challenge"}}` |
| Telefone fora de E.164 | `400 {"detail":{"code":"invalid_phone"}}` |
| Limite de reenvio/hora/IP | `429 {"detail":{"code":"rate_limited"}}` com `Retry-After` |

Exemplo local (o código não é exposto pela API; em desenvolvimento ele fica no adaptador simulado em memória):

```powershell
$body = @{ phone = "+5511999999999"; purpose = "registration" } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/auth/phone/challenges `
  -ContentType "application/json" -Body $body
```

A resposta não revela se o telefone já possui conta. O recibo de verificação é de uso único e curto (ADR 0015) e é consumido pelos endpoints de registro/login; as sessões usam access/refresh opacos rotativos (ADR 0013).

O readiness não devolve detalhes da falha de conexão; o erro completo fica no log do processo.

### Configuração

Lida do ambiente com prefixo `JOGA_` (e de `backend/.env`, não versionado). Ver `backend/.env.example`.

| Variável | Padrão local |
|---|---|
| `JOGA_ENVIRONMENT` | `local` |
| `JOGA_DATABASE_URL` | `postgresql+psycopg://joga:joga@127.0.0.1:5434/joga` |
| `JOGA_DATABASE_CONNECT_TIMEOUT_SECONDS` | `3` |
| `JOGA_LOG_LEVEL` | `INFO` |
| `JOGA_PHONE_HASH_SECRET` | placeholder local; obrigatório fora de `local`/`test`/`development`/`ci` |
| `JOGA_OTP_TTL_SECONDS` | `300` |
| `JOGA_OTP_MAX_ATTEMPTS` | `5` |
| `JOGA_OTP_RESEND_COOLDOWN_SECONDS` | `60` |
| `JOGA_OTP_MAX_PER_HOUR` | `5` |
| `JOGA_OTP_MAX_PER_IP_PER_HOUR` | `20` |
| `JOGA_OTP_RECEIPT_TTL_SECONDS` | `600` |
| `JOGA_TOKEN_HASH_SECRET` | placeholder local; obrigatório fora de `local`/`test`/`development`/`ci` |
| `JOGA_ACCESS_TOKEN_TTL_SECONDS` | `600` |
| `JOGA_REFRESH_ABSOLUTE_TTL_DAYS` | `30` |
| `JOGA_REFRESH_IDLE_TTL_DAYS` | `7` |
| `JOGA_WEBAUTHN_RP_ID` | `joga-passkeys.vercel.app` |
| `JOGA_WEBAUTHN_RP_NAME` | `JOGA` |
| `JOGA_WEBAUTHN_ORIGIN_ANDROID` | `android:apk-key-hash:...` do certificado de debug |
| `JOGA_WEBAUTHN_ORIGIN_WEB` | `https://joga-passkeys.vercel.app` |
| `JOGA_PASSKEY_CHALLENGE_TTL_SECONDS` | `300` |
| `JOGA_PASSKEY_MAX_PER_IP_PER_HOUR` | `30` |
| `JOGA_DEV_FIXED_OTP` | vazio; apenas local, para testes manuais |
| `JOGA_CEP_API_BASE_URL` | `https://brasilapi.com.br/api/cep/v2` |
| `JOGA_CEP_TIMEOUT_SECONDS` | `5` |
| `JOGA_GEO_TIMEOUT_SECONDS` | `3` |
| `JOGA_GEO_CACHE_TTL_DAYS` | `30` |
| `JOGA_GEO_RATE_LIMIT_PER_MINUTE` | `30` |
| `JOGA_GEO_PROVIDER_VERSION` | `brasilapi_v1` |
| `JOGA_DISCOVERY_MAX_RADIUS_KM` | `100` |
| `JOGA_DISCOVERY_DEFAULT_RADIUS_KM` | `10` |
| `JOGA_DISCOVERY_PAGE_SIZE` | `20` |
| `JOGA_LOCATION_ROUND_DECIMALS` | `2` |
| `JOGA_DEFAULT_TIMEZONE` | `America/Sao_Paulo` |
| `JOGA_MATCHMAKING_ALGORITHM_VERSION` | `level_v1` |
| `JOGA_MATCHMAKING_QUEUE_TTL_HOURS` | `24` |
| `JOGA_MATCHMAKING_SEARCH_DAYS` | `7` |
| `JOGA_MATCHMAKING_SLOT_MINUTES` | `30` |
| `JOGA_MATCHMAKING_MIN_LEAD_MINUTES` | `120` |
| `JOGA_MATCHMAKING_MAX_RADIUS_KM` | `30` |
| `JOGA_RELEASE_DELAY_HOURS` | `2`; repasse 2 h após o início da partida (ADR 0040) |
| `JOGA_BOOKING_T2_MAX_MINUTES` | `60`; teto da resposta da quadra (ADR 0039) |
| `JOGA_CANCELLATION_CUTOFF_HOURS` | `6`; cutoff proposto na ADR 0039 |
| `JOGA_SUBSTITUTION_WINDOW_PERCENT` | `25`; janela T4 proporcional ao tempo restante |
| `JOGA_SUBSTITUTION_WINDOW_MIN_MINUTES` | `30`; piso da janela T4 |
| `JOGA_SUBSTITUTION_WINDOW_MAX_HOURS` | `12`; teto da janela T4 |
| `JOGA_LATE_SUBSTITUTION_WINDOW_MINUTES` | `15`; janela de substituto em no-show |
| `JOGA_PRESENCE_OPEN_LEAD_MINUTES` | `60`; abertura do pré-check-in/presença |
| `JOGA_PRESENCE_CLOSE_LEAD_MINUTES` | `30`; fechamento e no-show automático |
| `JOGA_PRESENCE_RADIUS_M` | `200`; raio do geofence |
| `JOGA_PRESENCE_MAX_ACCURACY_M` | `100`; precisão máxima aceita no GPS |
| `JOGA_REVIEW_OPERATORS` | vazio; operadores autorizados a decidir contestações financeiras |
| `JOGA_CPF_KEY` | vazio; 32 bytes em base64; obrigatório fora de `local`/`test`/`development`/`ci` |
| `JOGA_CPF_KEY_ID` | vazio; id curto da chave vigente (ex.: `local-v1`) |
| `JOGA_CPF_PREVIOUS_KEYS` | `{}`; JSON `{"<id>": "<base64>"}` apenas para leitura durante rotação |

Nunca versionar `.env`, credenciais reais ou segredos. `.env.example` só contém placeholders.

### Migrações

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic downgrade base
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
```

`alembic check` compara os modelos com o banco e deve retornar “No new upgrade operations detected”. A CI executa essa verificação depois de reaplicar as migrações. A migração `c15a1b2c3d4e` cria `venue_releases` e `financial_disputes` e faz backfill das liberações simuladas da 14C.

Nova migração: `.venv\Scripts\python.exe -m alembic revision -m "descricao"` e revisão manual do arquivo. Toda alteração de schema passa por migração; não editar o banco manualmente. A migração baseline `af763231ef2f` é intencionalmente vazia; `3c9d51a7e2b4`, `d4a7f2c9e610` e `a7c3e9f2b415` criam identidade, access/recibo e desafios de passkey; `b8d2f4a6c910` cria catálogo, perfil, disponibilidade, região e locais (com seeds `futebol-5x5` e `volei-6x6`); `c5e1a7d3f208` cria fila, lobbies, participantes e rodadas; `d7f2b9c4e615` cria partidas, participantes e transições; `e1a4c7d9b230` cria resultados, disputas, capitão e idempotência; `f2b5d8e1a7c3` cria contadores de rate limiting.

### Reparo do catálogo visual em bancos antigos

A revisão `a0b1c2d3e4f5` passou a apontar para `z9c0d1e2f3a4`. Um banco que
aplicou `a0b1c2d3e4f5` **antes** de `z9c0d1e2f3a4` existir avança para
`b1c2d3e4f5a6` sem criar os objetos de `z9`: o Alembic não reaplica uma revisão
ancestral retroativamente. O sintoma é `500` em `/api/v1/catalog/sports`,
`/api/v1/catalog/visual` e `/api/v1/sports`, com `alembic_version` em
`b1c2d3e4f5a6`.

A revisão de reparo `c1d2e3f4a5b6` roda depois de `b1c2d3e4f5a6` e é aditiva e
idempotente: cria somente o que falta (colunas, constraints, índices, tabelas e
seeds de `z9`) e não apaga dados. Em banco novo ela não altera nada. O downgrade
é intencionalmente no-op; não use `alembic downgrade` como rollback desse
reparo.

Diagnóstico somente de leitura (o resultado deve ser `t` para tudo depois do
reparo):

```sql
SELECT version_num FROM alembic_version;
SELECT to_regclass('visual_catalog_items') IS NOT NULL AS tem_catalogo,
       to_regclass('user_visual_identity') IS NOT NULL AS tem_identidade,
       to_regclass('user_visual_unlocks') IS NOT NULL AS tem_unlocks;
SELECT count(*) AS colunas_z9
FROM information_schema.columns
WHERE table_schema = current_schema()
  AND ((table_name = 'sports' AND column_name IN ('icon_key', 'sort_order'))
    OR (table_name = 'sport_formats'
        AND column_name IN ('players_per_team', 'period_count', 'score_model', 'positions')));
SELECT count(*) AS itens_catalogo FROM visual_catalog_items;
SELECT count(*) AS seed_futevolei FROM sports WHERE slug = 'futevolei';
```

Procedimento no demo (requer autorização explícita para o deploy):

1. Faça um backup recuperável do banco (snapshot do Supabase ou `pg_dump`)
   antes de qualquer alteração.
2. Faça o deploy do commit que contém `c1d2e3f4a5b6`. O `deploy/start.sh` roda
   `alembic upgrade head` com três tentativas no boot.
3. Confirme a cabeça e o schema:

   ```powershell
   Set-Location C:\prog\joga\backend
   $env:JOGA_DATABASE_URL = "postgresql+psycopg://<usuario>:<senha>@<host>:5432/postgres?sslmode=require"
   .venv\Scripts\python.exe -m alembic current
   .venv\Scripts\python.exe -m alembic check
   ```

   `current` deve mostrar `c1d2e3f4a5b6 (head)` e `check` deve retornar
   “No new upgrade operations detected”.

4. Verifique os endpoints públicos: `/api/v1/health/ready`,
   `/api/v1/catalog/sports`, `/api/v1/catalog/visual` e `/api/v1/sports` devem
   responder `200`.
5. Repita o `upgrade head` ou rode o deploy novamente para confirmar que o
   reparo é repetível; não deve haver erro nem duplicação de seeds.

Reprodução local em PostgreSQL descartável:

```powershell
Set-Location C:\prog\joga\backend
$env:JOGA_TEST_DATABASE_URL = "postgresql+psycopg://joga:joga@127.0.0.1:5434/joga"
.venv\Scripts\python.exe -m pytest -q -o addopts="" tests\test_catalog_migration.py
```

O teste `test_repair_migration_heals_legacy_database` recria o estado antigo
(schema em `b1c2d3e4f5a6` sem `z9`), aplica o reparo, valida `alembic check`, os
três endpoints `200`, o downgrade no-op e a reexecução sobre schema parcial.

### Verificações do backend

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy app
.venv\Scripts\python.exe -m pytest
```

Resultado observado na Fase 2: Ruff sem achados, Mypy sem erros em 14 arquivos, 5 testes aprovados. Na Fase 3: Ruff e formatação sem achados, Mypy sem erros em 31 arquivos, 95 testes de unidade/API e 5 de integração PostgreSQL (100 com a variável definida). Na Fase 4: Ruff e formatação sem achados, Mypy sem erros em 36 arquivos, 112 testes sem PostgreSQL (119 com a variável definida, incluindo o teste PostGIS de raio/ordenação/paginação). Na Fase 5: Mypy sem erros em 41 arquivos, 145 testes sem PostgreSQL e 158 com a variável, incluindo concorrência real de dois workers e reexecução idempotente. Na Fase 6: Mypy sem erros em 45 arquivos, 161 testes sem PostgreSQL e 175 com a variável, incluindo 10 confirmações concorrentes que geram uma única transição para `READY`. Na Fase 7: 224 testes sem PostgreSQL e 245 com a variável, incluindo concorrência de votos, confirmações de capitão, fechamento de rodada, abertura única da segunda rodada, decisão humana, rate limit e retenção; migração aplicada, revertida e reaplicada no PostgreSQL local.

Testes de integração PostgreSQL (opcionais; exigem banco descartável e criam schemas isolados `identity_test`, `profile_test`, `matchmaking_test`, `matches_test` e `results_test`):

```powershell
Set-Location C:\prog\joga\backend
$env:JOGA_TEST_DATABASE_URL = "postgresql+psycopg://joga:joga@127.0.0.1:5434/joga"
.venv\Scripts\python.exe -m pytest tests\test_identity_postgres.py tests\test_profile_postgres.py tests\test_matchmaking_postgres.py tests\test_matches_postgres.py tests\test_results_postgres.py -v
```

Sem `JOGA_TEST_DATABASE_URL`, esses testes são ignorados; a CI define a variável e os executa após as migrações.

### Worker de matchmaking

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m scripts.run_matchmaking            # uma rodada
.venv\Scripts\python.exe -m scripts.run_matchmaking --loop --interval 15
```

Cada rodada expira entradas vencidas, seleciona entradas compatíveis com `FOR UPDATE SKIP LOCKED`, revalida dentro da transação e cria `lobbies` + `lobby_participants`. A versão da política fica em `matchmaking_runs.algorithm_version`. Redis não participa da formação.

### Worker de partidas

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m scripts.advance_matches
.venv\Scripts\python.exe -m scripts.advance_matches --loop --interval 60
```

Avança o ciclo por tempo: dissolve partidas sem confirmação completa, marca ausentes no fechamento do check-in, convida suplentes, inicia partidas às quais todos fizeram check-in, cancela quando não há suplente, abre a rodada 1 de resultado, fecha rodadas vencidas, abre a segunda rodada e encaminha casos inconclusivos à revisão humana. Reexecutar é seguro (idempotente).

### Worker de rating (Fase 8)

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m scripts.apply_ratings
.venv\Scripts\python.exe -m scripts.apply_ratings --loop --interval 60
```

Aplica MMR às partidas `ranked` em `FINALIZED` que ainda não têm eventos para a versão `glicko2_team_v1`. A constraint única por partida/usuário/versão torna a reexecução idempotente. Partidas casuais, disputadas, anuladas ou não finalizadas não recebem rating. A fila ranqueada usa `mmr_v1`; os endpoints de leitura são `GET /api/v1/ratings/me` e `GET /api/v1/rankings`.

Simulação antes de liberar ranking público:

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m scripts.simulate_ratings --players 60 --matches 3000 --seed 7
```

### Limpeza de dados efêmeros

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m scripts.cleanup_identity `
  --challenge-days 1 --session-days 30 --event-days 90
```

Remove desafios OTP/passkey expirados, sessões antigas/revogadas e eventos de segurança acima da retenção. Não altera usuários, telefones nem credenciais. O agendamento em produção ainda é uma decisão operacional.

### Limpeza de resultados (Fase 7)

A retenção provisória está no `docs/ADR/0024-retencao-provisoria-resultados.md`. Comece sempre pelo `--dry-run`:

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m scripts.cleanup_results --dry-run
.venv\Scripts\python.exe -m scripts.cleanup_results
```

Padrões: contadores de rate limit 24 h; evidências 365 dias após o encerramento da disputa; relatos, confirmações, decisões, revisões e análises 730 dias após o encerramento da partida. Partidas em andamento, em disputa ou com revisão pendente são preservadas. Os prazos podem ser ajustados por `--rate-limit-hours`, `--evidence-days`, `--report-days` e `--decision-days`.

### Comunicação e WebSocket (Fase 9A)

- `GET /api/v1/lobbies/{lobby_id}/messages` lista o histórico paginado.
- `POST /api/v1/lobbies/{lobby_id}/messages` envia texto; exige `Idempotency-Key`.
- `GET /api/v1/ws` abre o WebSocket autenticado por `Authorization: Bearer <token>`. O cliente envia `{"type":"subscribe","lobby_id":"..."}`.
- `GET/POST /api/v1/friends`, `/api/v1/blocks`, `/api/v1/lobbies/{id}/invites` e `/api/v1/lobby-invites` cobrem amigos, bloqueios e convites.
- `PUT /api/v1/push-tokens` registra token; o envio real depende de provedor autorizado.
- `GET /api/v1/me/notifications`, `/unread-count`, `/{id}/read` e `/read-all` formam a central persistida; push é apenas transporte.

Nesta fase o WebSocket entrega apenas conexões do processo atual. Para reiniciar após queda, o cliente busca o histórico pela API; Redis e fan-out multi-processo ficam para hardening/escala.

### Limpeza de comunicação (Fase 9)

A retenção provisória está no `docs/ADR/0027-retencao-provisoria-comunicacao.md`. Comece pelo `--dry-run`:

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m scripts.cleanup_communication --dry-run
.venv\Scripts\python.exe -m scripts.cleanup_communication
```

Padrões: mensagens de lobby 730 dias; convites encerrados 90 dias; eventos de Outbox entregues/falhos 30 dias; tokens de push revogados 90 dias. Eventos `PENDING`, convites pendentes/aceitos e tokens ativos são preservados.

Notificações têm retenção provisória de 180 dias:

```powershell
.venv\Scripts\python.exe -m scripts.cleanup_notifications --dry-run
```

## 4.1 Observabilidade, carga e backup

Todas as respostas HTTP incluem `X-Request-ID` (eco de um valor seguro do cliente ou um ID novo). Os logs `joga.http` registram método, rota, status, duração e request ID, sem query string, corpo, tokens ou telefone.

Carga local:

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m scripts.load_test --requests 200 --concurrency 20
.venv\Scripts\python.exe -m scripts.load_test --path /api/v1/sports --requests 100 --concurrency 10
```

Backup e restauração local:

```bash
docker exec joga-postgres-1 pg_dump -U joga -d joga -Fc > /tmp/joga_backup.dump
docker exec joga-postgres-1 psql -U joga -d postgres -c "CREATE DATABASE joga_restore_test"
docker exec -i joga-postgres-1 pg_restore -U joga -d joga_restore_test < /tmp/joga_backup.dump
docker exec joga-postgres-1 psql -U joga -d joga_restore_test -tAc "SELECT version_num FROM alembic_version"
```

Depois de validar, remova o banco temporário e o arquivo de dump. Produção exige storage externo, criptografia, retenção e teste de restore documentado.

### E-mail transacional (beta por e-mail)

Perfil beta (ADR 0050): login é **e-mail + senha**; telefone fica
desabilitado por flag. O código de 6 dígitos serve apenas para verificar o
e-mail no cadastro, trocar o e-mail e redefinir a senha. O `.env` local não
deve ser versionado.

```dotenv
JOGA_EMAIL_PROVIDER=brevo
JOGA_EMAIL_API_KEY=<secret>
JOGA_EMAIL_FROM=<remetente verificado no Brevo>
JOGA_EMAIL_DAILY_BUDGET=250
```

Validar o boot (falha em vez de degradar):

```powershell
.venv\Scripts\python.exe -c "from app.core.config import get_settings; get_settings()"
```

Entregar a fila (a API nunca espera o provedor):

```powershell
# Execução agendada (uma passada; é o modo usado pelo GitHub Actions)
.venv\Scripts\python.exe -m scripts.deliver_emails --once

# Desenvolvimento local contínuo
.venv\Scripts\python.exe -m scripts.deliver_emails --loop --interval 30
```

**Sem worker no Render free.** O serviço web dorme e não mantém `--loop`.
A entrega é feita por workflows agendados fora do web service:

- `.github/workflows/email-worker.yml`: `*/5 * * * *` (a cada 5 min) chama
  `python -m scripts.deliver_emails --once`;
- `.github/workflows/email-cleanup.yml`: `17 3 * * *` (1x/dia) chama
  `python -m scripts.cleanup_email --outbox-hours 1 --delivery-days 90`.

**Perfil do demo (`JOGA_ENVIRONMENT=demo`).** O demo não tem PSP real. O boot
exige as guardas abaixo e falha se qualquer uma estiver fora do esperado:

```text
JOGA_ENVIRONMENT=demo
JOGA_PSP_PROVIDER=simulator
JOGA_MONEY_MODE=simulated
JOGA_TICKET_PURCHASE_ENABLED=false
JOGA_PHONE_HASH_SECRET=<segredo próprio do demo>
JOGA_TOKEN_HASH_SECRET=<segredo próprio do demo>
JOGA_CPF_KEY=<32 bytes em base64>
JOGA_CPF_KEY_ID=k1
```

Não é preciso definir `JOGA_MERCADO_PAGO_ACCESS_TOKEN`,
`JOGA_MERCADO_PAGO_WEBHOOK_SECRET` nem `JOGA_MERCADO_PAGO_NOTIFICATION_URL`.
O webhook do Mercado Pago responde `404 webhook_disabled` e não grava evento.
`JOGA_DEV_FIXED_OTP` é recusado. Compra de tickets continua desligada. Ver
`docs/ADR/0053-modo-demo-sem-psp.md`.

O serviço web do demo já roda em `JOGA_ENVIRONMENT=demo` desde 2026-11-20
(deploy `6a89c79`); o passo a passo da troca, as variáveis exigidas e o rollback
estão em `docs/DEPLOY_DEMO.md` §5.1. Os workflows de e-mail
(`.github/workflows/email-worker.yml` e `email-cleanup.yml`) ainda usam
`JOGA_ENVIRONMENT=development` por padrão: eles só drenam a Outbox e não
aplicam as guardas do modo demo. Para um ambiente com PSP real, defina as
repository variables `JOGA_ENVIRONMENT=production` e
`JOGA_PSP_PROVIDER=mercadopago` e configure os secrets do PSP (ver abaixo).

Secrets do worker: `JOGA_DATABASE_URL`, `JOGA_EMAIL_API_KEY` e
`JOGA_EMAIL_FROM` (opcional `JOGA_EMAIL_REPLY_TO`). O cleanup precisa apenas de
`JOGA_DATABASE_URL`. Nenhum job de demo usa `JOGA_MERCADO_PAGO_*`. Para um
ambiente `production`, além das vars do PSP, adicione ao workflow os secrets
`JOGA_PHONE_HASH_SECRET` e `JOGA_TOKEN_HASH_SECRET` (o boot de produção recusa
os valores padrão).

**Supabase e IPv4.** Com `JOGA_DATABASE_URL` no Supabase, use a URL do
**Session pooler** (IPv4), no formato
`postgresql+psycopg://postgres.<project-ref>:<senha>@aws-0-<region>.pooler.supabase.com:5432/postgres`.
O host direto do Supabase é IPv6 e não é alcançável pelo runner do GitHub nem
pelo Render free. A URL precisa começar com `postgresql+psycopg://`.

**Quando o workflow passa a existir.** O arquivo só é registrado no GitHub
depois do merge no branch padrão (`main`). Antes disso, `workflow_dispatch` não
aparece na aba Actions e o cron não roda. Depois do merge, o cron é
best-effort: na prática, 5–15 min (pode atrasar mais em pico). Dispare
manualmente em **Actions → Email worker → Run workflow** para validar.

`POST /auth/email/code` responde `202` quando o desafio e a entrega foram
enfileirados; o código chega em condições normais dentro desse intervalo. O
GitHub desativa schedules após 60 dias sem atividade no repositório; reative o
workflow ou dispare manualmente.

Conferir atraso da Outbox e estado das entregas (PostgreSQL):

```sql
SELECT status, count(*), min(created_at), max(created_at)
FROM outbox_events
WHERE event_type = 'email.delivery_requested'
GROUP BY status;

SELECT status, count(*), min(created_at)
FROM email_deliveries
WHERE created_at >= now() - interval '1 day'
GROUP BY status;
```

Atraso da fila (evento mais antigo ainda pendente/falho):

```sql
SELECT min(created_at) AS oldest_pending,
       now() - min(created_at) AS queue_delay
FROM outbox_events
WHERE event_type = 'email.delivery_requested'
  AND status IN ('PENDING', 'FAILED');
```

Aceite do `workflow_dispatch` no demo:

1. Dispare **Actions → Email worker → Run workflow**.
2. O log termina com `enviados=1` (ou mais) e exit code 0.
3. Confirme no banco:

```sql
SELECT id, kind, status, attempts, provider_message_id, last_error_code
FROM email_deliveries
ORDER BY created_at DESC
LIMIT 5;

SELECT status, count(*)
FROM outbox_events
WHERE event_type = 'email.delivery_requested'
GROUP BY status;
```

O aceite é `email_deliveries.status = 'sent'` com `provider_message_id`
preenchido e o evento correspondente `DISPATCHED` na Outbox. Se ficar
`FAILED`, o `last_error_code` indica o motivo (sem corpo do provedor).

Operação:

- Login: `POST /auth/email/login` com e-mail + senha. Não existe login por
  código. O rate limit é 10/15 min por e-mail e 30/15 min por IP; ajuste com
  `JOGA_EMAIL_LOGIN_MAX_PER_EMAIL`/`JOGA_EMAIL_LOGIN_MAX_PER_IP`.
- Senha: Argon2id com 64 MiB, 3 iterações e paralelismo 4. O banco guarda
  apenas a string PHC; nunca logue senha/hash. A política é mínimo 10, máximo
  128, com bloqueio de senhas comuns e do próprio e-mail.
- Cadastro: o código verifica o e-mail; a senha é definida no `register`.
  Recuperação: `purpose=password_reset` → `verify` →
  `POST /auth/email/password/reset` (revoga todas as sessões e envia aviso).
- Troca autenticada: `POST /me/password` (revoga as outras sessões).
- `email_deliveries` é o log de entrega; não contém corpo, código, senha nem
  endereço.
- A Outbox guarda o destinatário e o código apenas até o despacho. Agende a
  limpeza para reduzir a retenção do payload:
  `python -m scripts.cleanup_email --outbox-hours 1 --delivery-days 90`.
- Consumo em 80% do orçamento gera `email.budget_warning`; em 100% o envio novo
  é bloqueado com `email.budget_exhausted` e a resposta pública continua
  genérica (`202`). Verifique a fila e a cota do provedor.
- Falha transitória vai para a fila com backoff. Falha permanente
  (`provider_rejected`) marca a credencial como não entregável após
  `JOGA_EMAIL_BOUNCE_THRESHOLD`; o jogador precisa de passkey/suporte.
- `JOGA_SIGNUP_MODE=closed` é o kill switch imediato de cadastro, sem deploy.
- `JOGA_TICKET_PURCHASE_ENABLED=false` (padrão) bloqueia criação, sincronização e confirmação de compra de ingressos com `503 ticket_purchase_disabled`; carteira, extrato e lotes continuam legíveis. Ver `docs/TELAS_DESATIVADAS.md`.
- Para voltar ao telefone no lançamento, troque as flags (e-mail continua
  ligado como secundário):
  `JOGA_AUTH_PHONE_ENABLED=true`, `JOGA_ALLOW_PHONE_REGISTRATION=true`,
  `JOGA_PHONE_REQUIRED_FOR_BOOKING=true`.
- Testes nunca usam o provedor real: `JOGA_EMAIL_PROVIDER=fake` e o fixture
  hermético de `tests/conftest.py` ignora o `.env` do desenvolvedor.


## 5. Mobile

```powershell
$env:PATH = "C:\prog\joga\.tools\nodejs\node-v24.22.1-win-x64;$env:PATH"
Set-Location C:\prog\joga\mobile
pnpm install --frozen-lockfile
pnpm run lint
pnpm run format:check
pnpm run typecheck
pnpm exec expo install --check
```

O projeto usa Expo `~58.0.23`, React Native `0.88.1`, React `19.3.0`, TypeScript `~6.0.3`, ESLint `9.39.5` e Prettier `3.9.10`. O pnpm usa `nodeLinker: hoisted` em `mobile/pnpm-workspace.yaml`; sem isso, o build Android no Windows falha por caminho longo (`build.ninja` dirty).

O painel **Competitivo** (Fase 8C) usa `GET /api/v1/ratings/me` e `GET /api/v1/rankings`. Ele mostra divisão, progresso, posição e top do formato; não exibe MMR bruto nem Trust Factor. A ADR 0045 mantém essa leitura: "MMR" nas estatísticas é divisão/progresso, e as estatísticas do passe usam projeções sobre `rating_events` sem expor o número.

O painel **Comunicação** (Fase 9B/9C) usa `GET /api/v1/matches`, chat por lobby, amigos e convites. Ele abre um WebSocket autenticado para o lobby selecionado e reconcilia o histórico pela API após reconexão.

O painel **Reservas** (Fase 13B) usa `GET /api/v1/bookings`, confirmação de participante e pagamento simulado local. A vitrine e a criação de reserva estão prontas no backend (Fase 13C); o app ainda precisa ligar as telas a `/api/v1/discovery/bookable-venues` e `POST /api/v1/bookings`.

### Abrir no aparelho

O fluxo de identidade/passkey exige **development build** (Credential Manager, `expo-secure-store` e o módulo local não funcionam no Expo Go). O app usa `http://127.0.0.1:8000/api/v1`; faça a ponte das portas 8081 (Metro) e 8000 (API):

```powershell
Set-Location C:\prog\joga\mobile
pnpm exec expo start --dev-client --localhost --port 8081
adb reverse tcp:8081 tcp:8081
adb reverse tcp:8000 tcp:8000
```

Para testar o OTP manualmente sem provedor real, suba a API com um código fixo **apenas em ambiente local**:

```powershell
$env:JOGA_DEV_FIXED_OTP = "123456"
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

`JOGA_DEV_FIXED_OTP` é rejeitado fora de `local`/`test`/`development`; nunca usar em ambiente compartilhado.

Com Android SDK configurado, o build de desenvolvimento é:

```powershell
pnpm exec expo run:android --device <serial>
```

`android/` e `ios/` são gerados por `expo prebuild` e não são versionados (ADR 0009).

Em aparelhos 32 bits (`armeabi-v7a`, como o moto g(7) play com Android 10), compile a ABI do aparelho e instale o APK de debug:

```powershell
Set-Location C:\prog\joga\mobile\android
$env:JAVA_HOME = "C:\prog\joga\.tools\temurin-17\jdk-17.0.20.1+1"
$env:ANDROID_HOME = "C:\prog\joga\.tools\android-sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:GRADLE_USER_HOME = "$env:TEMP\joga-gradle-home"
.\gradlew.bat assembleDebug -PreactNativeArchitectures=armeabi-v7a --console=plain
adb install -r app\build\outputs\apk\debug\app-debug.apk
adb reverse tcp:8081 tcp:8081
adb reverse tcp:8000 tcp:8000
```

Para um aparelho **arm64** (como o moto g24, Android 14), troque a ABI. O `node` precisa estar no `PATH` do Gradle, e `android/local.properties` deve apontar para o SDK:

```powershell
Set-Location C:\prog\joga\mobile\android
"sdk.dir=C\:\\prog\\joga\\.tools\\android-sdk" | Set-Content local.properties -Encoding ASCII
$env:JAVA_HOME = "C:\prog\joga\.tools\temurin-17\jdk-17.0.20.1+1"
$env:ANDROID_HOME = "C:\prog\joga\.tools\android-sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:PATH = "C:\prog\joga\.tools\nodejs\node-v24.22.1-win-x64;$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:PATH"
.\gradlew.bat assembleDebug -PreactNativeArchitectures=arm64-v8a --console=plain
adb install -r app\build\outputs\apk\debug\app-debug.apk
adb reverse tcp:8081 tcp:8081
adb reverse tcp:8000 tcp:8000
```

Conferir a ABI do aparelho com `adb shell getprop ro.product.cpu.abilist`. O APK de debug depende do Metro em `localhost:8081`; o `adb reverse` faz essa ponte. O APK não é versionado e precisa ser gerado de novo em cada máquina.

Para o procedimento de build no Windows com raiz curta, MAX_PATH/Ninja, `arm64-v8a` e `EXPO_PUBLIC_API_URL`, consulte `docs/BUILD_ANDROID.md`. Para a compra de ingressos desativada, consulte `docs/TELAS_DESATIVADAS.md`.

## 5.1 Painel web (Fase 11B)

O painel **JOGA y GESTÃO** fica em `web/` e usa React + TypeScript + Vite. Ele consome a mesma API do aplicativo; não há banco ou autenticação separados.

```powershell
Set-Location C:\prog\joga\web
pnpm install --frozen-lockfile
pnpm run lint
pnpm run format:check
pnpm run typecheck
pnpm run build
pnpm run dev
```

Abra `http://localhost:5173` com a API em `http://127.0.0.1:8000` e as migrações aplicadas. O Vite faz proxy de `/api` para o backend local.

Para testar o login sem SMS real, defina `JOGA_DEV_FIXED_OTP` no ambiente do backend. O refresh token fica em cookie `HttpOnly` com `Path=/api/v1/auth/web`; o access token fica em memória. Refresh e logout exigem `X-CSRF-Token` de duplo envio. Em produção, use HTTPS, `JOGA_WEB_COOKIE_SECURE=true` e painel/API no mesmo site.

O painel cobre organizações, membros/papéis, estabelecimentos e auditoria. A Fase 12A acrescentou quadras/espaços, modalidades, agenda semanal, preços, bloqueios, reservas externas e fotos de quadra com revisão. A Fase 13A acrescentou reservas, holds e T1/T2/T3 no backend e uma aba de reservas no painel; a 13C acrescentou a vitrine reservável e a criação ponta a ponta; a 13D alinhou o painel ao fornecedor com payout, cobertura, reajuste, cancelamento, reembolso e presença; a 13E acrescentou T2 em horário comercial e dispatcher. A Fase 15 acrescentou a aba Financeiro com extrato, repasses, liberação simulada e contestação. A Fase 17A acrescentou denúncias, triagem determinística, moderação por CLI e recursos; a 17C acrescentou o painel de moderação e a central interna. Pagamentos reais, escrow, NFS-e, classificador de IA e publicidade não estão implementados.

### Reservas e temporizadores (Fase 13A)

- Endpoints: `POST/GET /api/v1/bookings`, `GET /api/v1/bookings/{id}`, confirmação de participante, substituição, cancelamento e pagamento simulado; no painel, `GET /api/v1/organizations/{org}/bookings` e ações de aceite/recusa/conclusão.
- T1 começa na criação; T2 começa quando todas as vagas confirmam; T3 começa no aceite com hold ativo. Os prazos são independentes e controlados pelo backend.
- T2 usa horário comercial com expediente, feriados e fechamentos (13E); validar casos de borda.
- O pagamento é simulado em `local`/`test`/`development`/`ci` e no ambiente `demo` (ADR 0053); no demo, somente para participante ativo do próprio booking. Nenhum PSP real é acionado.
- Worker de expiração:

```bash
cd backend
.venv/bin/python -m scripts.advance_bookings
.venv/bin/python -m scripts.advance_bookings --loop --interval 60
```

- O worker libera holds vencidos, expira T1/T2 e cancela T3 sem pagamento completo. Também reembolsa reservas terminais com cobranças pagas; a exceção de desistência pós-confirmação segue a política consolidada da ADR 0039. Reexecutar é seguro.
- **ADR 0039 — fatia 1:** fila de substitutos, cancelamento individual após `CONFIRMED`, T4/T5, expiração e exclusão de reembolso de quem desistiu.
- Endpoints: `POST/DELETE/GET /api/v1/lobbies/{lobby}/substitutes`, `POST /api/v1/bookings/{booking}/participant-cancellations`, `GET /api/v1/bookings/{booking}/substitutions`, `POST /api/v1/bookings/{booking}/substitutions/{substitution}/assign`, `.../accept`, `.../decline` e `POST /api/v1/bookings/{booking}/participants/{user}/no-show`.
- Ao abrir uma vaga, o sistema chama automaticamente o primeiro substituto `STANDBY` (`CALLED`, timeout de 5 min). O substituto aceita ou recusa; se recusar/expirar, chama o próximo. A atribuição manual continua disponível.
- A atribuição antes do cutoff cria uma cobrança para o substituto. Quando ele paga, a vaga é marcada `FILLED` e o substituído é reembolsado. Se não pagar até T4, a atribuição expira.
- No no-show após o cutoff, a vaga nasce `paid_seat=True`: o substituto ocupa a vaga já paga (`WAIVED`/`covered_by_payment_id`), sem nova cobrança e sem reembolso ao ausente. Sem substituto, a vaga expira, mas a reserva continua `CONFIRMED`.
- Presença: `POST /bookings/{id}/pre-check-in`, `POST /bookings/{id}/presence` e `GET /bookings/{id}/presence`. O estabelecimento deve informar `latitude`/`longitude` no cadastro. GPS só marca `PRESENT` dentro de `JOGA_PRESENCE_RADIUS_M`/`JOGA_PRESENCE_MAX_ACCURACY_M`; caso contrário fica `UNVERIFIED` e exige confirmação do estabelecimento (`VENUE`). Não existe confirmação por capitão.
- O worker `advance_bookings` fecha presença em T-30m, marca ausentes como `NO_SHOW` e cria vaga paga para cada um. Também calcula a formação recomendada: par = dois times; ímpar = `NxN + 1 rodízio`; abaixo de 4 presentes = sem quórum. O campo `formation_note` é apenas recomendação, sem cronômetro controlado pelo JOGA.
- O worker `advance_bookings` expira T4: cancela o lobby/reserva, libera o hold e reembolsa os demais pagantes, sem reembolsar quem desistiu.
- Trust Factor interno (ADR 0041): no-show −30, cancelamento após confirmação −7, cancelamento antes do pagamento −2, recuperação não linear ao concluir partida e restrição ranqueada de 7/30 dias. O score não é exposto.
- Ainda pendente: UI de presença/fila e UI de suporte para revisar restrições; a integração completa com o ciclo da partida continua parcial.
- A organização consulta o resumo em `GET /api/v1/organizations/{org}/financial/summary` e o extrato em `GET /api/v1/organizations/{org}/bookings/{booking}/financial`.
- Reembolso manual: `POST /api/v1/organizations/{org}/bookings/{booking}/refund` com motivo. No beta, o adaptador simulado processa o estorno.

### Pagamentos no protótipo (ADR 0048)

- **Protótipo com jogadores reais:** Mercado Pago Orders API com Pix e custódia centralizada. O valor fica na conta do JOGA; o ledger registra a obrigação e o repasse ao estabelecimento é manual/registrado no ledger (ADR 0040).
- **Não é escrow** nem garantia de reembolso de produção. Dinheiro real exige CNPJ/MEI, contrato e revisão jurídica.
- **Inter/Pagar.me ficam para o futuro** e não são dependência do protótipo.
- Nenhuma credencial real de PSP deve ser configurada sem autorização.

#### Fase 14A — Mercado Pago Orders API

- O adaptador padrão é `simulator` (`JOGA_PSP_PROVIDER=simulator`), sem rede e sem credenciais.
- Fora de local/teste, o startup exige provider `mercadopago`, token, segredo e URL HTTPS:
- Para sandbox, configure no `backend/.env` (não versionado):

```env
JOGA_PSP_PROVIDER=mercadopago
JOGA_MERCADO_PAGO_ACCESS_TOKEN=TEST-...
JOGA_MERCADO_PAGO_WEBHOOK_SECRET=...
JOGA_MERCADO_PAGO_NOTIFICATION_URL=https://seu-dominio/api/v1/payments/mercadopago/webhook
```

> O e-mail do pagador vem de `users.email` (`GET/PUT /api/v1/me/email`); não existe e-mail global de cobrança. Sem e-mail, a abertura responde `422 payer_email_required`.

> A Orders API atual **não aceita** `notification_url` no payload da ordem. Configure a URL de webhook no painel do Mercado Pago; a variável acima serve como referência operacional.

- Rotas: webhook público em `POST /api/v1/payments/mercadopago/webhook`, sincronização em `POST /api/v1/bookings/{booking}/payments/{payment}/sync` e reabertura em `POST /api/v1/organizations/{org}/bookings/{booking}/payments/open`.
- O webhook valida HMAC, persiste o evento bruto antes de processar e consulta a ordem no PSP antes de mudar o estado. Falha transitória responde 5xx, guarda `last_error` e agenda `next_attempt_at` com backoff.
- Reprocessamento manual: `python -m scripts.retry_webhooks --limit 50` (use `--dry-run` para listar sem processar).
- O QR Code/copia-e-cola aparece no mobile para o próprio participante; a organização vê apenas o status.
- Valide a Orders API com credenciais reais antes do go-live; os testes automatizados usam HTTP simulado.

### Interface financeira e conciliação (Fase 15)

> **Decisões de 17/11/2026.** A 15A está entregue no backend e a 15B depende do
> painel. O repasse é em `starts_at + 2h` (ADR 0040,
> `JOGA_RELEASE_DELAY_HOURS=2`); a contestação tem **72 h** persistidas
> (`JOGA_DISPUTE_WINDOW_HOURS=72`). Custódia B com Inter PJ; escrow/modelo C
> fica para a fase comercial. MED bloqueia repasse e cria receivable sem
> clawback da quadra (fluxo real na 14B). Não existe reembolso parcial.
>
> A política de cancelamento/substituição/presença é a **ADR 0039**, complementada
> pela decisão de 17/11/2026: antes do cutoff, devolução integral e sem repasse;
> depois do cutoff/no-show, sem devolução, quadra integral e repasse; quadra que
> cancela devolve tudo e não recebe; disputa aberta congela o repasse. O Trust
> Factor está na ADR 0041; UI de presença/suporte ainda não existe.

- Três relógios distintos: pagamento (T3), contestação (72 h) e repasse (`starts_at + 2h`).
- Resumo: `GET /api/v1/organizations/{org}/financial/summary` inclui `pending_release_cents`, `disputed_cents`, `venue_price_cents` e `joga_fee_cents`.
- Recebíveis: `GET /api/v1/organizations/{org}/financial/receivables?status=PENDING`, com `receipt_reference`, `dispute_deadline` e o preço em duas linhas.
- Extrato: `GET /api/v1/organizations/{org}/financial/statement`; comissão: `GET .../financial/commission`.
- Contestações: `GET/POST /api/v1/organizations/{org}/financial/disputes`, `GET .../{dispute_id}` e `POST .../{dispute_id}/decision`.
- A reserva `CONFIRMED` ou `COMPLETED` ganha liberação com `eligible_at = starts_at + JOGA_RELEASE_DELAY_HOURS` (padrão 2 h, ADR 0040) e snapshot de 72 h. Contestações `OPEN` suspendem a liberação.
- Worker de liberação (reexecutável):

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m scripts.release_payments
.venv\Scripts\python.exe -m scripts.release_payments --loop --interval 60
```

- Decisão interna de contestação: endpoint com `financial:manage` + `JOGA_REVIEW_OPERATORS` ou CLI operacional:

```powershell
$env:JOGA_REVIEW_OPERATORS = "operador-1"
.venv\Scripts\python.exe -m scripts.review_financial_dispute `
  --dispute-id <uuid> --operator operador-1 `
  --decision ACCEPTED --reason "Justificativa auditável"
```

- Conciliação interna (relata divergências, não corrige saldo):

```powershell
.venv\Scripts\python.exe -m scripts.reconcile_financials
.venv\Scripts\python.exe -m scripts.reconcile_financials --organization-id <uuid> --json
```

- Crédito e tickets (14E): abertura e reconciliação do ledger. A abertura é
  idempotente e deve rodar antes de ligar a leitura:

```powershell
# dry-run com relatório por usuário
.venv\Scripts\python.exe -m scripts.ledger_opening
# aplica opening:{user} = Σ remaining × unit_price_cents contra opening_equity
.venv\Scripts\python.exe -m scripts.ledger_opening --apply
# health check: exit 1 e contador de divergência de tickets, caixa e 6b
.venv\Scripts\python.exe -m scripts.reconcile_ledger --json
```

- Leitura do saldo: exclusivamente lotes + ledger. O saldo é a soma dos
  tickets dos lotes comprados + passe/grátis/admin utilizáveis, com validação
  do caixa `player_credit` (compras pagas + abertura − Σ k×310 das reservas
  confirmadas). Conta ausente, caixa divergente ou saldo negativo responde
  `503 balance_unavailable`; não há flag nem fallback.
- `ticket_balances` é **view** sobre `ticket_lots` (migração `t4e5f6a7b8c9`);
  não é mais escrita. O lock de carteira é a linha de `users`.
- O extrato financeiro do fornecedor é projetado de `ledger_transactions` +
  `ledger_entries` (`u5f6a7b8c9d0`); `booking_ledger_entries` não existe mais.
  `CHARGE_CREATED` deixou de existir, `PAYMENT_CONFIRMED` representa a parte da
  quadra e `booking_payment_id` vem nulo no extrato.
- O painel mostra a aba **Financeiro** para `OWNER`, `ADMIN` e `OPERATOR`; apenas `OWNER`/`ADMIN` abrem contestação. A decisão exige `financial:manage` **e** usuário em `JOGA_REVIEW_OPERATORS`; o fornecedor não decide a própria contestação.
- Contestações só são aceitas com liberação `PENDING` e antes do snapshot `dispute_deadline` (72 h). O comprovante real será `bank:<e2e_id>` + PDF privado; `simulated:<release_id>` só em teste. A NFS-e é exibida de `fiscal_documents` (`pending_manual`).
- O relatório `GET /organizations/{id}/financial/commission` separa `venue_price_cents` (fornecedor) de `joga_fee_cents` (JOGA). `block_for_chargeback` bloqueia/reverte a liberação sem tocar saldo; MED real é 14B.
- Nenhum repasse real é feito: o ledger e a liberação são simulados como proposta técnica. Split, MED, chargeback, comprovantes, NFS-e e a política de repasse continuam pendentes; a 14E integrou o ledger em reais.

### CPF, termos e intenção fiscal (Fase 14E-E)

- **CPF:** `PUT /api/v1/me/cpf` grava o CPF cifrado; `GET` devolve só
  `cpf_present` e `cpf_masked` (`***.***.***-25`); `DELETE` anonimiza o perfil e
  preserva o snapshot fiscal já emitido. Nenhuma rota devolve o número em claro.
- **Chave:** `JOGA_CPF_KEY` (32 bytes em base64) + `JOGA_CPF_KEY_ID`. Fora de
  `local`/`test`/`development`/`ci`, o boot falha sem chave; o placeholder de 32
  bytes zero é recusado. A chave nunca entra no banco, no Git, no bundle nem em log.
- **Rotação:** gere a chave nova, publique como `JOGA_CPF_KEY` com um
  `JOGA_CPF_KEY_ID` novo e mova a antiga para `JOGA_CPF_PREVIOUS_KEYS`. A leitura
  usa o `cpf_key_id` gravado na linha. Não remova a chave antiga antes de
  recifrar os registros ativos; a recifragem em lote ainda não é automatizada.
- **Diagnóstico:** `GET /api/v1/me/cpf` e os eventos de auditoria
  `user.cpf_updated`/`user.cpf_deleted` (apenas `cpf_present`). Não registre o
  CPF, o CPF cifrado nem a chave em log, ticket ou captura de tela.
- **Termos:** `GET /api/v1/legal/terms/current` devolve `null` enquanto não há
  versão `approved`; `POST /api/v1/legal/terms/accept` só aceita versão aprovada.
  Com versão aprovada, a compra de pacote passa a exigir `terms_version_id`;
  sem versão aprovada, o fluxo atual continua sem aceite.
- **Intenção fiscal:** com `JOGA_FISCAL_MODE=placeholder`, a confirmação da
  reserva grava `fiscal_documents` (`pending_manual`, valor = preço do espaço) e
  um `fiscal_document_takers` por jogador com a cota e o CPF cifrado. Nenhuma
  chamada externa é feita; não há emissor, município nem alíquota definidos.
- **Reembolso parcial:** o schema aceita `refund_type=PARTIAL`, mas nenhum fluxo
  cria parcial nesta etapa; o serviço continua criando um único `FULL` por
  cobrança.
- **Retenção e base legal:** ver `docs/PRIVACIDADE_CPF_E_RETENCAO.md`.

### Quadras, agenda e fotos (Fase 12A)

- A rota do painel é `/organizations/{org}/venues/{venue}`; a lista de estabelecimentos tem o atalho “Quadras e fotos”.
- Endpoints principais: `/api/v1/organizations/{org}/venues/{venue}/spaces`, `.../spaces/{space}/availability`, `.../spaces/{space}/blackouts` e `.../photos`.
- Fotos são validadas e reencodadas em JPEG, têm EXIF removido e ficam em storage privado. O padrão local é `JOGA_MEDIA_ROOT=var/media`, relativo ao diretório `backend/`; não há serving estático.
- A foto nasce `PENDING`; `OWNER`/`ADMIN` aprova ou rejeita com motivo. `OPERATOR` pode enviar e remover, mas não revisar. A revisão independente fica para a Fase 17.
- O serving usa `GET .../photos/{photo}/content` com autenticação e `Cache-Control: no-store`. Fotos não são públicas.
- Em produção, defina storage de objetos, criptografia, backup, retenção e limpeza de órfãos; o diretório local não é adequado para múltiplas instâncias.

## 6. CI

`.github/workflows/ci.yml` roda em push para `main`, `feat/**`, `fix/**`, `docs/**` e em pull requests:

- **backend:** Python 3.13, serviço `postgis/postgis:16-3.4` em 5432, instalação por `requirements.lock`, `ruff check`, `mypy app`, `alembic upgrade head`/`downgrade base`/`upgrade head` e `pytest`.
- **mobile:** Node 24, pnpm 11.25.0, `pnpm install --frozen-lockfile`, `lint`, `format:check`, `typecheck` e `expo install --check`.
- **web:** Node 24, pnpm 11.25.0, `pnpm install --frozen-lockfile`, `lint`, `format:check`, `typecheck` e `build`.

A CI foi observada em execução no commit `3e6c692`: backend e mobile concluíram com `success` (run [41475001880](https://github.com/kramirodev/Joga/actions/runs/41475001880)). Para repetir, faça push de uma branch coberta pelos gatilhos ou abra um pull request.

## 7. Problemas conhecidos

| Sintoma | Causa provável | Ação |
|---|---|---|
| `Bind for 0.0.0.0:5434 failed: port is already allocated` | outra instância usando a porta | escolher outra porta e ajustar `JOGA_DATABASE_URL` |
| `ready` retorna 503 | banco parado, URL/porta errada ou migração não aplicada | `docker compose ps`, conferir `.env`, `alembic upgrade head` |
| `password authentication failed` | credenciais divergentes do volume existente | usar os valores padrão `joga/joga` ou recriar o volume de teste |
| Build Android falha com `build.ninja still dirty` | pnpm com layout isolado e caminhos longos no Windows | confirmar `nodeLinker: hoisted` e caminho curto do repositório |
| `expo install --check` falha | dependência fora da faixa esperada pelo SDK | `pnpm exec expo install <pacote>` e revisar o lockfile |
| `adb reverse` indisponível | adb antigo (1.0.31) | usar Platform-Tools recente ou Expo Go via `--lan` |
| App não carrega o bundle | Metro parado ou `adb reverse` ausente | subir Metro em 8081 e repetir `adb reverse tcp:8081 tcp:8081` |
| `401 invalid_token` após ~10 min | access token vence; o app tenta renovar pelo refresh | se o refresh falhar, entrar novamente; investigar revogação/suspensão |
| Log da API cheio de `GET /health 404` | cliente antigo consulta `/health` em vez de `/api/v1/health/live` | corrigir o cliente; o backend expõe `/api/v1/health/ready` |
| Expo Go não abre o app | módulo nativo `passkey-proof` e `expo-secure-store` | usar development build (`expo run:android` ou APK de debug) |

### Troca de ambiente no Render não aplica sozinha

**Sintoma:** mudei `JOGA_ENVIRONMENT` (ou outra variável) no Render e o serviço
continuou com o comportamento antigo.

**Diagnóstico:** o Render **não reinicia nem refaz o deploy** quando só a
variável muda. O processo em execução segue com o ambiente carregado no boot
anterior. Além disso, com `JOGA_ENVIRONMENT=demo` o boot **falha** se faltar
`JOGA_CPF_KEY`/`JOGA_CPF_KEY_ID`, se `JOGA_PHONE_HASH_SECRET` ou
`JOGA_TOKEN_HASH_SECRET` estiverem no valor padrão, se
`JOGA_PSP_PROVIDER`/`JOGA_MONEY_MODE`/`JOGA_TICKET_PURCHASE_ENABLED` estiverem
fora do esperado ou se `JOGA_DEV_FIXED_OTP` estiver definido; nesse caso o
deploy não fica `live` e a revisão antiga continua servindo.

**Ação e validação:** dispare *Manual Deploy → Deploy latest commit*, confira o
log de boot e valide `GET /api/v1/health/ready` (200) e
`GET /api/v1/app-config` (`demo_mode: true`). A ordem completa e o rollback
estão em `docs/DEPLOY_DEMO.md` §5.1.

## 8. Limites atuais

- Redis não está configurado; o `PLANS.md` permite mantê-lo desligado até existir uso real.
- Não há staging, produção, domínio, passkeys de produção, iOS ou provedor de SMS.
- O PostgreSQL local é descartável e não contém dados reais.
- O app mobile cobre identidade, perfil/descoberta, fila/partidas, reservas, carteira, temporada, clãs e moderação; passkey WebAuthn, push e WebSocket ainda não estão integrados no app.
- Passkey criada em um aparelho não é transferida automaticamente; no aparelho novo, entre por OTP e cadastre uma nova.
- Fases 5–9 estão implementadas no backend; a Fase 9 tem chat HTTP, mas o app ainda não tem cliente WebSocket. A Fase 10 está em hardening local; o piloto real depende de SMS, passkey, push, backup/restore e LGPD.
- As Fases 11–17 têm implementação local parcial ou completa; parte da 13C–13E, 14D.10–16, 16 e 17 está na branch de trabalho, sem merge. A 14D/15 estão congeladas até a 14E (ADR 0049).
- O ledger de dupla entrada existe, mas não está integrado aos fluxos; a receita, a taxa e o repasse ainda usam registros legados. Não configurar PSP, chaves de produção ou credenciais reais sem autorização explícita.
- Resultados, disputas, segunda rodada e revisão humana estão implementados no backend. A CLI de revisão exige `JOGA_REVIEW_OPERATORS`; a retenção provisória está no ADR 0024 e é aplicada por `scripts.cleanup_results.py`.
- O modelo de dados atual contém agenda, reservas, cobranças, ledgers, reembolsos, repasses, crédito, temporada, clãs e moderação; consulte `docs/DATA_MODEL.md`.

### 8.1 Workers operacionais

Além de `run_matchmaking`, `advance_matches` e `apply_ratings`, o ambiente local usa:

```powershell
.venv\Scripts\python.exe -m scripts.advance_bookings --loop --interval 30
.venv\Scripts\python.exe -m scripts.release_payments --loop --interval 300
.venv\Scripts\python.exe -m scripts.retry_webhooks --loop --interval 60
.venv\Scripts\python.exe -m scripts.dispatch_notifications --loop --interval 30
.venv\Scripts\python.exe -m scripts.close_seasons --loop --interval 3600
.venv\Scripts\python.exe -m scripts.deliver_pass_months --loop --interval 3600
.venv\Scripts\python.exe -m scripts.reactivate_suspensions --loop --interval 300
```

Não há supervisor único; em produção, esses processos precisam de agendamento, health check e alertas. `scripts.reconcile_financials.py` e `scripts.reconcile_purchases.py` são operações de conciliação, não workers contínuos.

## 8.1 Revisão humana de resultado (Fase 7)

A revisão humana só existe por CLI interna; não há endpoint público de moderação. Configure os operadores autorizados no ambiente do backend, em lista separada por vírgula:

```bash
export JOGA_REVIEW_OPERATORS="operador-1,operador-2"
```

Com a revisão `PENDING`, execute a partir de `backend/`:

```bash
.venv/bin/python -m scripts.review_match_result \
  --match-id <uuid> \
  --operator operador-1 \
  --reason "Justificativa auditável" \
  --decision FINALIZE \
  --outcome TEAM_1
```

- `--decision`: `FINALIZE`, `VOID` ou `REQUEST_MORE_INFO`.
- `--outcome` é obrigatório apenas em `FINALIZE` e precisa ser permitido pelo formato.
- `--reason` é obrigatório (1–500 caracteres).
- `--dry-run` valida sem gravar.
- Exit codes: 0 sucesso; 2 argumento inválido; 3 operador não autorizado; 4 revisão não encontrada/não pendente; 5 transição inválida.
- A decisão grava `match_result_decisions` com `origin = HUMAN`, operador, motivo e timestamp.

O worker `advance_matches.py` abre a rodada 1 em `scheduled_end_at`, fecha no prazo de 10 minutos, abre a rodada 2 por 5 minutos quando aplicável e encaminha os casos restantes à revisão. A API rejeita votos após o prazo mesmo que o worker esteja atrasado.

## 8.2 Moderação de denúncias (Fases 17A–17C)

A revisão é interna e pode ser feita pelo painel web separado em `/moderation` ou
pela CLI de contingência. O painel não é público e não se mistura ao JOGA y GESTÃO.

```bash
export JOGA_MODERATION_ADMIN_USER_IDS="<uuid-admin-1>,<uuid-admin-2>"
export JOGA_MODERATION_OPERATORS="operador-1,operador-2"   # compatibilidade com 17A
export JOGA_MODERATION_MAX_REPORTS_PER_DAY=5
```

1. Defina ao menos um UUID de conta em `JOGA_MODERATION_ADMIN_USER_IDS` e reinicie a API.
2. Entre no painel com essa conta e abra `/moderation`.
3. Cadastre os demais moderadores pelo bloco “Moderadores”. `MODERATOR` opera a
   fila; `ADMIN` também altera papéis.
4. A fila ordena por prioridade e atualiza a cada 30 segundos. Cada nova denúncia
   gera uma notificação persistida `moderation_report`; cada recurso gera
   `moderation_appeal`; a decisão do recurso gera `moderation_appeal_result`
   para o jogador.
5. A decisão exige justificativa e registra auditoria. Medidas: `DISMISS`,
   `WARN`, `RESTRICT_RANKED` e `SUSPEND_TEMP` (1–30 dias).

Conta suspensa:

- O refresh mobile rotaciona a sessão e responde `200` com `user.status = "suspended"`; o app preserva a sessão e renova o access token durante toda a suspensão.
- `GET /moderation/actions/me`, `GET /moderation/appeals/me` e
  `POST /moderation/actions/{id}/appeal` aceitam a sessão suspensa para ver e
  contestar a própria medida.
- Todas as outras rotas continuam exigindo conta ativa.
- O refresh web do painel continua respondendo `401 account_suspended`.

Notificações:

- `moderation_report` e `moderation_appeal` usam o canal interno `moderation`;
  não aparecem em `GET /me/notifications` nem geram push no app do jogador.
- O painel lê o canal interno em `GET /moderation/notifications`,
  `GET /moderation/notifications/unread-count`,
  `POST /moderation/notifications/{id}/read` e
  `POST /moderation/notifications/read-all`. Todos exigem operador ativo.
- `moderation_appeal_result` usa o canal `player`.

CLI de contingência:

```bash
.venv/bin/python -m scripts.review_moderation --list
.venv/bin/python -m scripts.review_moderation \
  --decide <report-id> --decision WARN \
  --reason "Aviso formal" --operator operador-1
.venv/bin/python -m scripts.review_moderation \
  --decide <report-id> --decision RESTRICT_RANKED --days 7 \
  --reason "Restrição ranqueada" --operator operador-1
.venv/bin/python -m scripts.review_moderation --appeals
.venv/bin/python -m scripts.review_moderation \
  --appeal <appeal-id> --decision ACCEPTED \
  --reason "Recurso procedente" --operator operador-2
```

A triagem é determinística (`rules_v1`) por categoria, reincidência e contexto; não há IA paga nem envio de texto a terceiros.

Suspensão temporária (1–30 dias) e recurso:

```bash
.venv/bin/python -m scripts.review_moderation \
  --decide <report-id> --decision SUSPEND_TEMP --days 3 \
  --reason "Ameaça grave" --operator operador-1
```

Reativação e retenção:

```bash
.venv/bin/python -m scripts.reactivate_suspensions
.venv/bin/python -m scripts.cleanup_moderation --dry-run
.venv/bin/python -m scripts.cleanup_moderation
```

Os POSTs de relato, confirmação e evidência aplicam rate limit por usuário em janela fixa de 60 segundos. O limite padrão é 30 requisições e pode ser ajustado em `JOGA_RESULTS_RATE_LIMIT_PER_MINUTE`; o excesso retorna `429 {"detail":{"code":"rate_limited"}}` com `Retry-After`.

## 9. Retomada em outro computador

Estado versionado no GitHub: `main` contém as Fases 0–6 (backend + docs). Nada essencial fica só na máquina antiga, exceto ferramentas e artefatos listados no fim desta seção.

1. **Clonar e conferir**
   ```powershell
   git clone https://github.com/kramirodev/Joga.git
   Set-Location Joga
   git log --oneline -1     # esperado: 8bdc049 (Fase 6)
   ```
2. **Instalar ferramentas** (não versionadas): Python 3.12–3.14, Docker Desktop, Node 24 + pnpm 11.25, JDK 17 e Android SDK/platform-tools se for gerar APK.
3. **Banco**
   ```powershell
   docker compose -f infra/compose.yaml up -d
   docker exec joga-postgres-1 pg_isready -U joga -d joga
   ```
4. **Backend**
   ```powershell
   python -m venv backend\.venv
   backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
   Set-Location backend
   .venv\Scripts\python.exe -m alembic upgrade head
   .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
   Para testes manuais com OTP fixo, suba com `JOGA_DEV_FIXED_OTP=123456` e `JOGA_ENVIRONMENT=local` (nunca fora de ambiente local). `.env` não é versionado; copie de `.env.example` só se precisar mudar algo.
5. **Verificações**
   ```powershell
   .venv\Scripts\python.exe -m ruff check .
   .venv\Scripts\python.exe -m ruff format --check .
   .venv\Scripts\python.exe -m mypy app
   .venv\Scripts\python.exe -m pytest
   ```
6. **Mobile**
   ```powershell
   Set-Location C:\prog\joga\mobile
   pnpm install --frozen-lockfile
   pnpm exec expo prebuild --platform android --no-install
   ```
   Depois siga “Abrir no aparelho” com a ABI do novo celular.
7. **Workers** (terminais separados, opcional)
   ```powershell
   python -m scripts.run_matchmaking --loop --interval 15
   python -m scripts.advance_matches --loop --interval 60
   ```
8. **Dados**: não há seed de usuários. Crie uma conta pelo fluxo OTP local; o catálogo esportivo vem da migração.

**Não está no Git** (precisa existir na máquina nova): `.env`, `backend/.venv`, `mobile/node_modules`, `mobile/android` e `mobile/ios` (gerados por prebuild), `android/local.properties`, o APK de debug e a pasta `.tools/` com Node/JDK/SDK.

**Troca de celular**: confira a ABI (`adb shell getprop ro.product.cpu.abilist`), gere o APK para ela, autorize a depuração USB, faça `adb reverse` das portas 8000 e 8081 e entre novamente (a sessão anterior fica no aparelho antigo). Passkeys são por aparelho; cadastre uma nova no aparelho novo.
