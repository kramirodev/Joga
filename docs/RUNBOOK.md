# RUNBOOK — ambiente local do JOGA

Instruções reproduzíveis para subir o backend, o PostgreSQL/PostGIS local, rodar as verificações e abrir o aplicativo no Android. Reflete o que foi executado nas Fases 1–6; não descreve ambientes que ainda não existem (staging, produção, iOS).

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

`alembic check` compara os modelos com o banco e deve retornar “No new upgrade operations detected”. A CI executa essa verificação depois de reaplicar as migrações.

Nova migração: `.venv\Scripts\python.exe -m alembic revision -m "descricao"` e revisão manual do arquivo. Toda alteração de schema passa por migração; não editar o banco manualmente. A migração baseline `af763231ef2f` é intencionalmente vazia; `3c9d51a7e2b4`, `d4a7f2c9e610` e `a7c3e9f2b415` criam identidade, access/recibo e desafios de passkey; `b8d2f4a6c910` cria catálogo, perfil, disponibilidade, região e locais (com seeds `futebol-5x5` e `volei-6x6`); `c5e1a7d3f208` cria fila, lobbies, participantes e rodadas; `d7f2b9c4e615` cria partidas, participantes e transições; `e1a4c7d9b230` cria resultados, disputas, capitão e idempotência; `f2b5d8e1a7c3` cria contadores de rate limiting.

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

Nesta fase o WebSocket entrega apenas conexões do processo atual. Para reiniciar após queda, o cliente busca o histórico pela API; Redis e fan-out multi-processo ficam para hardening/escala.

### Limpeza de comunicação (Fase 9)

A retenção provisória está no `docs/ADR/0027-retencao-provisoria-comunicacao.md`. Comece pelo `--dry-run`:

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m scripts.cleanup_communication --dry-run
.venv\Scripts\python.exe -m scripts.cleanup_communication
```

Padrões: mensagens de lobby 730 dias; convites encerrados 90 dias; eventos de Outbox entregues/falhos 30 dias; tokens de push revogados 90 dias. Eventos `PENDING`, convites pendentes/aceitos e tokens ativos são preservados.

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

O painel **Competitivo** (Fase 8C) usa `GET /api/v1/ratings/me` e `GET /api/v1/rankings`. Ele mostra divisão, progresso, posição e top do formato; não exibe MMR bruto nem Trust Factor.

O painel **Comunicação** (Fase 9B/9C) usa `GET /api/v1/matches`, chat por lobby, amigos e convites. Ele abre um WebSocket autenticado para o lobby selecionado e reconcilia o histórico pela API após reconexão.

O painel **Reservas** (Fase 13B) usa `GET /api/v1/bookings`, confirmação de participante e pagamento simulado local. A criação da reserva ainda depende do lobby/quadra; não há seletor de quadra no mobile nesta rodada.

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

O painel cobre organizações, membros/papéis, estabelecimentos e auditoria. A Fase 12A acrescentou quadras/espaços, modalidades, agenda semanal, preços, bloqueios, reservas externas e fotos de quadra com revisão. A Fase 13A acrescentou reservas, holds e T1/T2/T3 no backend e uma aba de reservas no painel. Reservas no mobile, pagamentos reais, KYC, clãs, moderação e publicidade não estão implementados.

### Reservas e temporizadores (Fase 13A)

- Endpoints: `POST/GET /api/v1/bookings`, `GET /api/v1/bookings/{id}`, confirmação de participante, substituição, cancelamento e pagamento simulado; no painel, `GET /api/v1/organizations/{org}/bookings` e ações de aceite/recusa/conclusão.
- T1 começa na criação; T2 começa quando todas as vagas confirmam; T3 começa no aceite com hold ativo. Os prazos são independentes e controlados pelo backend.
- T2 usa tempo corrido nesta fase; horário comercial e feriados ficam pendentes.
- O pagamento é simulado apenas em ambiente `local`/`test`/`development`/`ci`; nenhum PSP real é acionado.
- Worker de expiração:

```bash
cd backend
.venv/bin/python -m scripts.advance_bookings
.venv/bin/python -m scripts.advance_bookings --loop --interval 60
```

- O worker libera holds vencidos, expira T1/T2 e cancela T3 sem pagamento completo. Reexecutar é seguro.

### Pagamentos no protótipo/beta (ADR 0034)

- **Protótipo/beta fechado:** Mercado Pago Checkout Transparente com Pix e custódia centralizada de teste. O valor fica na conta do JOGA; o ledger registra a obrigação e o repasse ao estabelecimento é simulado ou manual após `COMPLETED`.
- **Não é escrow** nem garantia de reembolso de produção. Dinheiro real no beta exige CNPJ/MEI, contrato e revisão jurídica; CPF fica restrito a sandbox.
- **Produção:** Pagar.me Flex, com retenção/split e liberação controlada (ADR 0021).
- Nenhuma credencial real de PSP deve ser configurada sem autorização.

#### Fase 14A — Mercado Pago Orders API

- O adaptador padrão é `simulator` (`JOGA_PSP_PROVIDER=simulator`), sem rede e sem credenciais.
- Para sandbox, configure no `backend/.env` (não versionado):

```env
JOGA_PSP_PROVIDER=mercadopago
JOGA_MERCADO_PAGO_ACCESS_TOKEN=TEST-...
JOGA_MERCADO_PAGO_PAYER_EMAIL=seu-email-de-teste@testuser.com
JOGA_MERCADO_PAGO_WEBHOOK_SECRET=...
JOGA_MERCADO_PAGO_NOTIFICATION_URL=https://seu-dominio/api/v1/payments/mercadopago/webhook
```

> A Orders API atual **não aceita** `notification_url` no payload da ordem. Configure a URL de webhook no painel do Mercado Pago; a variável acima serve como referência operacional.

- Rotas: webhook público em `POST /api/v1/payments/mercadopago/webhook`, sincronização em `POST /api/v1/bookings/{booking}/payments/{payment}/sync` e reabertura em `POST /api/v1/organizations/{org}/bookings/{booking}/payments/open`.
- O webhook valida HMAC quando o segredo está configurado e consulta a ordem no PSP antes de mudar o estado.
- O QR Code/copia-e-cola aparece no mobile para o próprio participante; a organização vê apenas o status.
- Nenhum pagamento real deve ser feito no protótipo/beta.

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
| `401 invalid_token` após ~10 min | access token vence e o app ainda não renova sozinho | entrar novamente; melhoria prevista para o hardening |
| Log da API cheio de `GET /health 404` | o app consulta `/health` em vez de `/api/v1/health/live` | pendência de hardening registrada no build log |
| Expo Go não abre o app | módulo nativo `passkey-proof` e `expo-secure-store` | usar development build (`expo run:android` ou APK de debug) |

## 8. Limites atuais

- Redis não está configurado; o `PLANS.md` permite mantê-lo desligado até existir uso real.
- Não há staging, produção, domínio, passkeys, iOS ou provedor de SMS.
- O PostgreSQL local é descartável e não contém dados reais.
- O app mobile cobre identidade e perfil/descoberta; ainda não tem tela de fila/partida.
- Passkey criada em um aparelho não é transferida automaticamente; no aparelho novo, entre por OTP e cadastre uma nova.
- Fases 5, 6, 7 e 8 estão implementadas no backend e no mobile; a Fase 9 está em implementação (9A backend). O worker precisa estar rodando para formar partidas, avançar estados, apurar rodadas e aplicar MMR.
- Reservas de quadras, pagamentos Pix, split, KYC de recebedor, interface financeira, clãs, moderação e publicidade **não estão implementados**. Não configurar PSP, chaves de produção ou credenciais reais sem autorização explícita.
- Resultados, disputas, segunda rodada e revisão humana da Fase 7 estão implementados no backend, sem MMR e sem painel administrativo. A CLI de revisão exige `JOGA_REVIEW_OPERATORS` configurado; os POSTs de resultado têm rate limit por usuário (`JOGA_RESULTS_RATE_LIMIT_PER_MINUTE`, padrão 30). A retenção provisória está no ADR 0024 e é aplicada manualmente por `scripts.cleanup_results.py`; a política definitiva depende da revisão LGPD das Fases 10/19.
- O modelo de dados atual não contém tabelas de agenda, reserva, cobrança, ledger, reembolso ou liberação; elas pertencem às Fases 12–15.

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
