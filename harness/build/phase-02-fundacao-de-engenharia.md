# Fase 02 — Fundação de engenharia

**Status:** Complete — backend mínimo com health checks, PostgreSQL/PostGIS local, migração baseline reversível, verificações automatizadas e CI verde nos dois projetos em 2026-11-02
**Branch:** `feat/02-fundacao-engenharia`
**Decisão de sequenciamento:** `docs/ADR/0010-inicio-fase-2-com-pendencias-da-fase-1.md` (Fase 1 permanece `In progress` por pendências externas)

## Fontes e contexto

- `AGENTS.md`
- `GOALS.md`
- `PLANS.md` (fonte normativa das fases, seção Fase 2)
- `docs/JOGA_DOCUMENTACAO_TECNICA.md`, especialmente §3.2, §4 (estrutura), §20 (observabilidade) e §23.5 (qualidade)
- `docs/RUNBOOK.md`
- `harness/build-log.md`
- `harness/build/phase-01-prova-tecnica-mobile-nativa.md`

## Objetivo

Criar a base de engenharia verificável do JOGA — estrutura de pastas, configuração explícita, PostgreSQL/PostGIS local, migração inicial vazia, API mínima com health checks, verificações de lint/formatação/tipos/testes e CI — sem implementar funcionalidade de produto.

## Escopo

- Estrutura `mobile/`, `backend/`, `infra/`, `docs/`, `harness/` e `.github/`.
- Backend Python + FastAPI em monólito modular, com camadas separadas (`api`, `core`, `infrastructure`, `modules`).
- Configuração por ambiente com prefixo `JOGA_`, sem segredo versionado.
- PostgreSQL + PostGIS local em container, com extensão habilitada.
- Alembic com migração baseline vazia, aplicável e reversível em banco descartável.
- Health check de liveness (sem dependências) e readiness (verifica o banco).
- Versões fixadas: `backend/requirements.lock` e `mobile/pnpm-lock.yaml`.
- Lint, formatação, type check e testes mínimos nos dois projetos.
- CI em GitHub Actions para backend e mobile.
- Instruções locais reproduzíveis em `docs/RUNBOOK.md`.

## Fora do escopo

- Funcionalidades de produto: identidade, perfil, filas, partidas, resultados, rating, moderação, comércio.
- Tabelas de domínio, autenticação real, passkeys, SMS, WebSocket e workers ativos.
- Redis (permitido desligado até existir uso real), Kafka, Kubernetes ou microserviços.
- Painel web, site público, domínio, deploy, staging ou produção.
- Alterar a estratégia mobile aprovada no ADR 0009.
- Resolver as pendências externas da Fase 1.

## Pré-requisitos e dependências

- Fase 0 concluída.
- Decisão de iniciar a Fase 2 com a Fase 1 em andamento (ADR 0010).
- Docker Desktop disponível para o banco local.
- Acesso ao registry Python e npm/pnpm para instalar dependências fixadas.

## Arquivos/componentes criados

- `backend/pyproject.toml`, `backend/requirements.lock`, `backend/.env.example`, `backend/alembic.ini`
- `backend/app/main.py`, `backend/app/api/v1/health.py`, `backend/app/api/v1/router.py`
- `backend/app/core/config.py`, `backend/app/core/logging.py`
- `backend/app/infrastructure/database/engine.py`, `backend/app/infrastructure/database/dependency.py`
- `backend/migrations/env.py`, `backend/migrations/versions/af763231ef2f_initial_empty_baseline.py`
- `backend/tests/conftest.py`, `backend/tests/test_health.py`, `backend/tests/test_config.py`
- `infra/compose.yaml`, `infra/postgres/init/001-extensions.sql`
- `.github/workflows/ci.yml`
- `mobile/eslint.config.js`, `mobile/.prettierrc`, `mobile/.prettierignore` e scripts em `mobile/package.json`
- `docs/RUNBOOK.md`

## Decisões técnicas registradas

1. **Python 3.12+ com venv e lock completo.** `pyproject.toml` declara dependências e ferramentas; `requirements.lock` contém todas as versões resolvidas. A CI usa Python 3.13; o ambiente local validado usa 3.14.7.
2. **SQLAlchemy síncrono com psycopg 3.** Suficiente para a fundação e para o monólito modular; assincronismo não traz benefício comprovado nesta fase.
3. **Porta local 5434.** A máquina já tem PostgreSQL 18 em 5432 e outro projeto ocupa 5433; o Compose aceita `POSTGRES_PORT` e a URL é configurada por `JOGA_DATABASE_URL`.
4. **PostGIS por script de inicialização do container.** A migração baseline permanece vazia; extensão é infraestrutura, não schema de domínio.
5. **ESLint 9.39.5 fixado.** ESLint 10 quebra `eslint-plugin-react` 7.37.5 (`contextOrFilename.getFilename is not a function`); a configuração usa `eslint-config-expo` 58.0.4 em flat config.
6. **pnpm com `nodeLinker: hoisted`.** Mantido do ADR 0009 para evitar o limite de caminho do Windows no build Android.
7. **Readiness falha fechado.** Qualquer erro de conexão retorna 503 com mensagem genérica; detalhes ficam no log, sem expor host, usuário ou senha.

## Riscos e decisões pendentes

- **CI observada em execução.** O workflow rodou no GitHub Actions para o commit `3e6c692`: job `Backend (lint, tipos, migrações, testes)` e job `Mobile (lint, formatação, tipos)` concluíram com `success` (run [41475001880](https://github.com/kramirodev/Joga/actions/runs/41475001880)).
- **Versão de Python diferente entre local e CI.** Local 3.14.7, CI 3.13. O `requirements.lock` foi conferido para 3.13 por `pip install --dry-run --python-version 3.13` e a CI instalou o lock com sucesso; a diferença está coberta.
- **Android SDK ausente no ambiente atual.** A execução do app foi validada via Expo Go na rede local. O build nativo com `expo run:android` foi comprovado na Fase 1, mas não foi repetido nesta fase por falta de SDK; não confundir as duas evidências.
- **Volume do PostgreSQL preservado.** A migração foi aplicada, revertida e reaplicada no container atual; o teste em banco realmente vazio depende de `down -v`, não executado para não perder o estado local.
- **Redis desligado.** Permitido pelo `PLANS.md`; será introduzido quando existir uso real.
- **Sem Dockerfile do backend.** A documentação técnica prevê o arquivo; a containerização da API não é necessária para o aceite da Fase 2 e fica para quando houver deploy.
- **Aviso do Starlette.** `TestClient` avisa que `httpx` está obsoleto em favor de `httpx2`; os 5 testes passam. Não foi alterada dependência sem necessidade demonstrada.

## Plano Red / Green / Refactor / Verify

- **Red:** registrar ausência de estrutura, configuração, banco e CI antes da fase.
- **Green:** criar o menor backend executável, o Compose com PostGIS e a migração vazia; adicionar testes de health e configuração.
- **Refactor:** separar rotas finas de infraestrutura, remover duplicação de configuração e fixar ferramentas.
- **Verify:** lint, formatação, tipos, testes, migração em banco real, health ao vivo, falha de readiness, execução do app e revisão do diff/segredos.

## Comandos reais de validação

Backend (ambiente `backend/`, venv local):

- `python -m venv backend\.venv`
- `backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock` (também validado em venv descartável: FastAPI 0.162.0, SQLAlchemy 2.1.6, Alembic 1.20.1, psycopg 3.3.6)
- `backend\.venv\Scripts\python.exe -m ruff check .`
- `backend\.venv\Scripts\python.exe -m ruff format --check .`
- `backend\.venv\Scripts\python.exe -m mypy app`
- `backend\.venv\Scripts\python.exe -m pytest`
- `backend\.venv\Scripts\python.exe -m alembic upgrade head`
- `backend\.venv\Scripts\python.exe -m alembic current`
- `backend\.venv\Scripts\python.exe -m alembic downgrade base`
- `backend\.venv\Scripts\python.exe -m alembic upgrade head`
- `backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`

Infra:

- `docker compose -f infra/compose.yaml up -d --force-recreate`
- `docker inspect --format '{{.State.Health.Status}}' joga-postgres-1`
- `docker exec joga-postgres-1 psql -U joga -d joga -tAc "SELECT extname FROM pg_extension WHERE extname='postgis'"`
- `curl.exe -s -i http://127.0.0.1:8001/api/v1/health/ready` (processo apontando para porta fechada, para provar 503)

Mobile (Node em `.tools/nodejs`):

- `pnpm install --frozen-lockfile`
- `pnpm run lint`
- `pnpm run format:check`
- `pnpm run typecheck`
- `pnpm exec expo install --check`
- `pnpm exec expo start --lan --port 8081`
- `adb shell am start -a android.intent.action.VIEW -d "exp://192.168.0.107:8081" host.exp.exponent`
- `adb shell uiautomator dump` + captura de tela no Moto G24 (`0087722228`)

## Resultados observados

- **Backend:** Ruff sem achados, `ruff format --check` sem alterações, Mypy sem erros em 14 arquivos, Pytest com 5 testes aprovados.
- **Lock reproduzível:** `pip install -r requirements.lock` em venv descartável instalou todas as versões fixadas; importações confirmaram FastAPI 0.162.0, SQLAlchemy 2.1.6, Alembic 1.20.1 e psycopg 3.3.6. A resolução para Python 3.13 também foi conferida com `pip install --dry-run --python-version 3.13 --only-binary=:all:` (exit 0).
- **Banco:** container `joga-postgres-1` (`postgis/postgis:16-3.4`) saudável em 8 s, extensão `postgis` presente; `alembic upgrade head` aplicou `af763231ef2f`, `downgrade base` removeu, `upgrade head` reaplicou e `current` confirmou `af763231ef2f (head)`.
- **API:** `GET /api/v1/health/live` → `200 {"status":"ok"}`; `GET /api/v1/health/ready` → `200 {"status":"ok","database":"ok"}` com o banco real; com o banco inacessível, `ready` → `503 {"detail":{"status":"unavailable","database":"unavailable"}}` e `live` continuou `200`.
- **Mobile:** lint, formatação, `tsc --noEmit` e `expo install --check` passaram; app abriu no Moto G24 via Expo Go pela rede local e renderizou a tela de prova sem erro de JS no logcat.
- **Segurança:** nenhuma credencial real; `.env` fica fora do Git; readiness não expõe detalhes de conexão.
- **CI:** run [41475001880](https://github.com/kramirodev/Joga/actions/runs/41475001880) concluída com `success`; backend e mobile verdes, incluindo aplicação e reversão da migração no serviço PostGIS da CI.

## Critérios de aceite

- [x] Estrutura `mobile/`, `backend/`, `infra/`, `docs/`, `harness/` e `.github/` com versões fixadas. — Venv + `requirements.lock`; pnpm lock preservado; scripts de verificação.
- [x] App abre em dispositivo/emulador. — Moto G24 (`0087722228`) via Expo Go em 2026-11-02; build nativo já comprovado na Fase 1.
- [x] API sobe. — Uvicorn em `127.0.0.1:8000`, endpoints de health respondendo.
- [x] Health check verifica dependências corretamente. — `live` independente; `ready` consulta o banco e falha fechado com 503 sem vazar detalhes.
- [x] Migração inicial vazia aplica em banco descartável. — PostgreSQL/PostGIS em container; upgrade/downgrade/upgrade confirmados.
- [x] CI valida os dois projetos. — Run [41475001880](https://github.com/kramirodev/Joga/actions/runs/41475001880): `Backend (lint, tipos, migrações, testes)` e `Mobile (lint, formatação, tipos)` concluídos com `success`.
- [x] Instruções locais reproduzíveis. — `docs/RUNBOOK.md`.
- [x] Lint, formatação, tipos e testes mínimos passam localmente. — Comandos e resultados registrados acima.
- [x] `git diff --check` e revisão de segredos no diff.

## Observações pós-conclusão

A Fase 2 atende a todos os critérios de `PLANS.md`. Os itens abaixo não bloqueiam a conclusão e ficam para as próximas fases ou para hardening.

1. **Repetir o build nativo Android no ambiente atual.** Exige Android SDK/Platform-Tools instalados; não foi possível nesta sessão. A abertura do app foi validada via Expo Go e o build nativo já foi comprovado na Fase 1.
2. **Decidir quando adicionar Dockerfile do backend.** Fora do escopo imediato; depende de deploy.
3. **Configurar Dependabot e auditoria automatizada de dependências.** Lockfiles estão fixados; a automação mencionada na documentação técnica pode entrar no hardening.
4. **Redis continua desligado.** Só deve ser introduzido quando existir uso real, conforme `PLANS.md`.
