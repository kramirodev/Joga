# RUNBOOK — ambiente local do JOGA

Instruções reproduzíveis para subir o backend, o PostgreSQL/PostGIS local, rodar as verificações e abrir o aplicativo no Android. Reflete o que foi executado na Fase 2; não descreve ambientes que ainda não existem (staging, produção, iOS).

## 1. Pré-requisitos

| Ferramenta | Versão usada na validação | Observação |
|---|---|---|
| Python | 3.14.7 | `pyproject.toml` aceita `>=3.12,<3.15`; a CI usa 3.13 |
| Docker Desktop | Engine 29.6.2, Compose v5.3.1 | Necessário para o PostgreSQL/PostGIS local |
| Node.js | 24.22.1 | Em `.tools/nodejs/node-v24.22.1-win-x64` neste ambiente |
| pnpm | 11.25.0 | Via Corepack; o lockfile é `mobile/pnpm-lock.yaml` |
| Android SDK + adb | Platform-Tools 37.0.1 (ADB 1.0.41) | Somente para build/execução nativa; não é necessário para lint/tipos |
| Dispositivo Android | Moto G24, Android 14 | Depuração USB autorizada |

Nenhuma credencial real é necessária. Os valores padrão do Compose e do `.env.example` são locais e descartáveis.

## 2. Portas locais

| Serviço | Porta no host | Motivo |
|---|---|---|
| API | 8000 | Padrão local do Uvicorn |
| Metro/Expo | 8081 | Padrão do Expo |
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
```

Nova migração: `.venv\Scripts\python.exe -m alembic revision -m "descricao"` e revisão manual do arquivo. Toda alteração de schema passa por migração; não editar o banco manualmente. A migração baseline `af763231ef2f` é intencionalmente vazia; `3c9d51a7e2b4`, `d4a7f2c9e610` e `a7c3e9f2b415` criam identidade, access/recibo e desafios de passkey. `b8d2f4a6c910` cria catálogo, perfil, disponibilidade, região e locais, e semeia `futebol-5x5` e `volei-6x6`.

### Verificações do backend

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy app
.venv\Scripts\python.exe -m pytest
```

Resultado observado na Fase 2: Ruff sem achados, Mypy sem erros em 14 arquivos, 5 testes aprovados. Na Fase 3: Ruff e formatação sem achados, Mypy sem erros em 31 arquivos, 95 testes de unidade/API e 5 de integração PostgreSQL (100 com a variável definida). Na Fase 4: Ruff e formatação sem achados, Mypy sem erros em 36 arquivos, 112 testes sem PostgreSQL (119 com a variável definida, incluindo o teste PostGIS de raio/ordenação/paginação). Na Fase 5: Mypy sem erros em 41 arquivos, 145 testes sem PostgreSQL e 158 com a variável, incluindo concorrência real de dois workers e reexecução idempotente.

Testes de integração PostgreSQL (opcionais; exigem banco descartável e criam schemas isolados `identity_test` e `profile_test`):

```powershell
Set-Location C:\prog\joga\backend
$env:JOGA_TEST_DATABASE_URL = "postgresql+psycopg://joga:joga@127.0.0.1:5434/joga"
.venv\Scripts\python.exe -m pytest tests\test_identity_postgres.py tests\test_profile_postgres.py tests\test_matchmaking_postgres.py -v
```

Sem `JOGA_TEST_DATABASE_URL`, esses testes são ignorados; a CI define a variável e os executa após as migrações.

### Worker de matchmaking

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m scripts.run_matchmaking            # uma rodada
.venv\Scripts\python.exe -m scripts.run_matchmaking --loop --interval 15
```

Cada rodada expira entradas vencidas, seleciona entradas compatíveis com `FOR UPDATE SKIP LOCKED`, revalida dentro da transação e cria `lobbies` + `lobby_participants`. A versão da política fica em `matchmaking_runs.algorithm_version`. Redis não participa da formação.

### Limpeza de dados efêmeros

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m scripts.cleanup_identity `
  --challenge-days 1 --session-days 30 --event-days 90
```

Remove desafios OTP/passkey expirados, sessões antigas/revogadas e eventos de segurança acima da retenção. Não altera usuários, telefones nem credenciais. O agendamento em produção ainda é uma decisão operacional.

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

O projeto usa Expo `~58.0.22`, React Native `0.88.1`, React `19.3.0`, TypeScript `~6.0.3`, ESLint `9.39.5` e Prettier `3.9.10`. O pnpm usa `nodeLinker: hoisted` em `mobile/pnpm-workspace.yaml`; sem isso, o build Android no Windows falha por caminho longo (`build.ninja` dirty).

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

Conferir a ABI do aparelho com `adb shell getprop ro.product.cpu.abilist`. O APK de debug depende do Metro em `localhost:8081`; o `adb reverse` faz essa ponte.

## 6. CI

`.github/workflows/ci.yml` roda em push para `main`, `feat/**`, `fix/**`, `docs/**` e em pull requests:

- **backend:** Python 3.13, serviço `postgis/postgis:16-3.4` em 5432, instalação por `requirements.lock`, `ruff check`, `mypy app`, `alembic upgrade head`/`downgrade base`/`upgrade head` e `pytest`.
- **mobile:** Node 24, pnpm 11.25.0, `pnpm install --frozen-lockfile`, `lint`, `format:check`, `typecheck` e `expo install --check`.

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

## 8. Limites atuais

- Redis não está configurado; o `PLANS.md` permite mantê-lo desligado até existir uso real.
- Não há staging, produção, domínio, passkeys, iOS ou provedor de SMS.
- O PostgreSQL local é descartável e não contém dados reais.
