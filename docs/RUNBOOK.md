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

O readiness não devolve detalhes da falha de conexão; o erro completo fica no log do processo.

### Configuração

Lida do ambiente com prefixo `JOGA_` (e de `backend/.env`, não versionado). Ver `backend/.env.example`.

| Variável | Padrão local |
|---|---|
| `JOGA_ENVIRONMENT` | `local` |
| `JOGA_DATABASE_URL` | `postgresql+psycopg://joga:joga@127.0.0.1:5434/joga` |
| `JOGA_DATABASE_CONNECT_TIMEOUT_SECONDS` | `3` |
| `JOGA_LOG_LEVEL` | `INFO` |

Nunca versionar `.env`, credenciais reais ou segredos. `.env.example` só contém placeholders.

### Migrações

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic downgrade base
.venv\Scripts\python.exe -m alembic upgrade head
```

Nova migração: `.venv\Scripts\python.exe -m alembic revision -m "descricao"` e revisão manual do arquivo. Toda alteração de schema passa por migração; não editar o banco manualmente. A migração baseline `af763231ef2f` é intencionalmente vazia.

### Verificações do backend

```powershell
Set-Location C:\prog\joga\backend
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy app
.venv\Scripts\python.exe -m pytest
```

Resultado observado na Fase 2: Ruff sem achados, Mypy sem erros em 14 arquivos, 5 testes aprovados.

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

Sem Android SDK, a via disponível é Expo Go pela rede local:

```powershell
Set-Location C:\prog\joga\mobile
pnpm exec expo start --lan
adb shell am start -a android.intent.action.VIEW -d "exp://<ip-do-host>:8081" host.exp.exponent
```

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
