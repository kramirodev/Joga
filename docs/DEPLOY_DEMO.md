# Deploy de demonstração (Render + Supabase)

**Status:** planejado. Os artefatos de container ainda **não existem** no repositório
(ver §3). Este documento é a checklist de execução, não o registro de um deploy feito.

**Data:** 2026-11-18

## 1. O que é e o que não é

É um ambiente de **demonstração privada**, com dinheiro simulado, para validar o
app do jogador e o painel antes do beta fechado.

Não é produção. Continuam bloqueados por decisão (ADR 0049 e pareceres):
dinheiro real, PSP real, NFS-e, escrow/modelo C, KYC/MED e SMS real.

## 2. Arquitetura obrigatória: uma origem

O painel usa `API_BASE="/api/v1"` e `credentials: "same-origin"`
(`web/src/lib/api.ts:50,183`), e a API usa cookies `SameSite=Strict`. Painel e API
em domínios diferentes **quebram o login**.

| Camada | Escolha | Motivo |
|---|---|---|
| API + painel | Um único container no Render (Caddy serve `/srv/web` e faz proxy de `/api/*` para o uvicorn) | Mesma origem, sem CORS |
| Banco | Supabase free (Postgres + PostGIS) | PostGIS pronto, sem cartão |
| E-mail | Brevo free (300/dia) | Unico free tier que envia para qualquer destinatário sem domínio verificado |
| Worker | GitHub Actions agendado | Render free não mantém worker |
| Redis | Nenhum | O código não usa |

Não adicionar CORS. Se optar por Vercel para o painel, é obrigatório um `rewrite`
de `/api/*` para o Render e o teste de cookie/CSRF; a opção de um container é mais
simples e menos frágil.

## 3. Artefatos pendentes

| Artefato | Estado | Observação |
|---|---|---|
| `Dockerfile` (multi-stage: web build + runtime Python + Caddy) | **Pendente** | Nenhum Dockerfile no repo |
| `deploy/Caddyfile` | **Pendente** | Basic auth, `/api/*` proxy, fallback do SPA |
| `deploy/start.sh` | **Pendente** | `alembic upgrade head`, uvicorn em background, `caddy run` |
| `.dockerignore` | **Pendente** | Excluir `.git`, `node_modules`, `.venv`, `mobile`, `telas` |
| `render.yaml` | **Pendente** | `plan: free`, health check `/api/v1/health/ready` |
| `backend/scripts/seed_demo.py` | **Pendente** | Sem seed, o painel abre vazio |
| `.github/workflows/email-worker.yml` | Existe, **não commitado** | Precisa de correção de ambiente (§7) |
| `.github/workflows/email-cleanup.yml` | Existe, **não commitado** | Idem |

## 4. Contas e chaves

| Conta | O que pegar | Vai para | Custo |
|---|---|---|---|
| Supabase | Connection string do **Session pooler** | `JOGA_DATABASE_URL` | Free (500 MB) |
| Render | Nada obrigatório | — | Free (750 h/mês) |
| Brevo | API key `xkeysib-...` e remetente verificado | `JOGA_EMAIL_API_KEY`, `JOGA_EMAIL_FROM` | Free (300/dia) |
| GitHub | Secrets do repositório (§7) | Workflows | Free |
| UptimeRobot ou cron-job.org | URL de ping | — | Free |

### Supabase: o que pegar e o que **não** pegar

- **Pegue** `Settings → Database → Connection string`. Use o **Session pooler**
  (porta 5432, host `aws-0-<região>.pooler.supabase.com`, usuário
  `postgres.<ref>`).
- **Não use** as chaves `anon` e `service_role` de `Settings → API`. Elas são do
  SDK/PostgREST; o JOGA fala Postgres direto.
- **Não use** o Transaction pooler (6543) para migração.
- Habilite a extensão antes das migrações:

```sql
create extension if not exists postgis;
```

### Por que Session pooler e não conexão direta

O host `db.<ref>.supabase.co` é IPv6-only na maioria dos projetos. O Render free
e os runners do GitHub Actions não têm saída IPv6 confiável. O Session pooler é
IPv4 e mantém compatibilidade com migração.

## 5. Variáveis de ambiente (perfil beta)

Nomes e valores do demo. Tudo marcado como **segredo** vai no dashboard, nunca no Git.

```text
JOGA_ENVIRONMENT=development          # obrigatório para liberar o simulador
JOGA_DATABASE_URL=<segredo>           # Session pooler + ?sslmode=require
JOGA_PHONE_HASH_SECRET=<segredo>
JOGA_TOKEN_HASH_SECRET=<segredo>
JOGA_CPF_KEY=<segredo base64 32 bytes>
JOGA_CPF_KEY_ID=<id>
JOGA_AUTH_EMAIL_ENABLED=true
JOGA_AUTH_PHONE_ENABLED=false
JOGA_ALLOW_EMAIL_REGISTRATION=true
JOGA_ALLOW_PHONE_REGISTRATION=false
JOGA_PHONE_REQUIRED_FOR_BOOKING=false
JOGA_SIGNUP_MODE=open
JOGA_EMAIL_PROVIDER=brevo
JOGA_EMAIL_API_KEY=<segredo>
JOGA_EMAIL_FROM=<remetente verificado no Brevo>
JOGA_EMAIL_FROM_NAME=JOGA
JOGA_EMAIL_DAILY_BUDGET=250
JOGA_WEB_COOKIE_SECURE=true           # HTTPS no Render
JOGA_PSP_PROVIDER=simulator
JOGA_MONEY_MODE=simulated
JOGA_FISCAL_MODE=disabled
JOGA_CUSTODY_MODEL=B
JOGA_WEBAUTHN_RP_ID=<host do Render, sem https>
JOGA_WEBAUTHN_ORIGIN_WEB=https://<host do Render>
DEMO_BASIC_AUTH_HASH=<segredo bcrypt>
```

`JOGA_ENVIRONMENT=development` é deliberado: fora de
`local/test/development/ci` o boot exige Mercado Pago com token e webhook
(`backend/app/core/config.py`). Por isso o demo é `development` e o acesso precisa
ficar atrás de basic auth.

## 6. Banco: migração e cuidados

O `backend/.env` aponta para o Postgres **local** de propósito. Para migrar o
remoto, use a variável inline na sessão — não edite o `.env`:

```powershell
cd backend
$env:JOGA_DATABASE_URL="postgresql+psycopg://postgres.<ref>:<senha>@aws-0-<região>.pooler.supabase.com:5432/postgres?sslmode=require"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
Remove-Item Env:JOGA_DATABASE_URL
```

Regras:

- Nunca executar `alembic downgrade base` contra o Supabase. É drop de schema.
- `alembic check` precisa dizer "No new upgrade operations detected".
- O banco local pode estar em revisão órfã; para recriar:

```powershell
docker compose -f infra/compose.yaml down -v
docker compose -f infra/compose.yaml up -d
```

## 7. Worker de e-mail — bloqueio conhecido

O código enfileira o e-mail e responde `202`; sem worker, o código **não chega**.

Os workflows agendados existem, mas como estão hoje **falham no demo**:

```yaml
JOGA_ENVIRONMENT: production
JOGA_PSP_PROVIDER: mercadopago
JOGA_MERCADO_PAGO_ACCESS_TOKEN: ${{ secrets... }}
```

Em `production`, o boot exige Mercado Pago com token, webhook e URL HTTPS. Sem
credenciais reais (que estão bloqueadas), o job morre antes de drenar a Outbox.

Correção necessária, feita pelo agente de backend:

- usar `JOGA_ENVIRONMENT=development` e `JOGA_PSP_PROVIDER=simulator` no demo, ou
  parametrizar por `vars.JOGA_ENVIRONMENT` / `vars.JOGA_PSP_PROVIDER`; e
- remover os segredos de Mercado Pago dos jobs do demo.

Outras limitações do agendador:

- Workflows agendados só rodam a partir do **branch padrão** (`main`). Nada roda
  enquanto os arquivos estiverem fora dele.
- O cron do GitHub é best-effort: atraso típico de 5 a 15 minutos.
- Agendamentos são desativados após ~60 dias sem atividade no repositório.
- Os runners não têm IPv6: use o Session pooler (§4).

Alternativa sem GitHub Actions: um ping externo (cron-job.org) para um endpoint
interno autenticado de drenagem. Esse endpoint **não existe** hoje.

## 8. Passo a passo

1. Criar o projeto no Supabase; habilitar PostGIS; copiar a URL do Session pooler.
2. Rodar `alembic upgrade head` e `alembic check` no remoto (§6).
3. Criar o seed de demonstração (organização, quadra, operador, jogador).
4. Construir a imagem e testar localmente:

```powershell
docker build -t joga-demo .
docker run --rm -p 8080:8080 --env-file .env.demo.local joga-demo
```

5. Criar o web service no Render (Docker, `plan: free`, health check
   `/api/v1/health/ready`), configurar as variáveis de §5.
6. Confirmar `Live` e os health checks.
7. Configurar os secrets do GitHub e corrigir o ambiente dos workflows (§7).
8. Rodar o smoke test (§9).
9. Configurar o ping do UptimeRobot para evitar o sleep do Render.

## 9. Smoke test

| Verificação | Esperado |
|---|---|
| `GET /api/v1/health/live` | 200 |
| `GET /api/v1/health/ready` | 200 |
| `GET /` sem basic auth | 401 |
| Login do painel por e-mail + senha | 200 e organização demo visível |
| `POST /auth/email/code` (`purpose=registration` ou `password_reset`) | 202 genérico |
| Código chega no e-mail | sim, em até ~5 min |
| `GET /auth/emails` | só a credencial da própria conta |
| `PUT /me/email` | altera só o e-mail do pagador |
| `PATCH /me/account/email` | exige código no endereço novo |
| `GET /discovery/bookable-venues` | quadra demo |
| Carteira | `source=ledger`; indisponibilidade retorna 503 sem zerar |
| Nenhuma tela | saldo em reais como carteira |

## 10. Limitações do free tier

- Render: dorme após ~15 min; primeiro acesso leva 30–60 s. 512 MB de RAM.
- Supabase: pausa após ~7 dias sem uso.
- Brevo: 300 e-mails/dia, compartilhados entre código, boas-vindas e avisos.
- `JOGA_MEDIA_ROOT` é disco efêmero: fotos de quadra somem no redeploy. Storage
  de objetos fica para depois.
- Sem backup automático confiável.
- Sem observabilidade além de log.

## 11. Segredos: rotação

Duas credenciais já circularam em texto puro durante a preparação. Rotacionar
antes de abrir o beta para terceiros:

- **Brevo**: `SMTP & API → API Keys` → revogar e gerar nova.
- **Supabase**: `Settings → Database → Reset database password` e atualizar
  `JOGA_DATABASE_URL` no Render e nos secrets do GitHub.

Nunca commitar `.env`. O `.gitignore` cobre `backend/.env`, `backend/.env.*` e
mantém `backend/.env.example` versionado.

## 12. O que falta para produção (não é este documento)

Pareceres fiscal e jurídico, PSP real homologado, NFS-e, escrow, domínio próprio
com SPF/DKIM/DMARC, backups, observabilidade, worker dedicado, storage de objetos
e revisão de segurança (§ADR 0049 e `docs/PENDENCIAS.md`).
