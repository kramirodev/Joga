# Deploy de demonstração (Render + Supabase)

**Status:** ambiente de demonstração **no ar** no Render free + Supabase. A URL
real não é versionada (repositório público); consulte o dashboard do Render.
Cadastro **aberto** desde 2026-11-19. A Outbox é drenada **no processo da API**
(task inline a cada 30 s) e o workflow do GitHub fica como reserva; a Outbox
remota está DISPATCHED e as entregas `password_reset`/`security_alert` estão
`sent`. Desde 2026-11-20 o serviço roda em **`JOGA_ENVIRONMENT=demo`** (ADR
0053): documentação interativa desabilitada, webhook do Mercado Pago desligado e
compra de tickets bloqueada (seção 5.1).

**Data:** 2026-11-20 (última atualização)

## 1. O que é e o que não é

É um ambiente de **demonstração privada**, com dinheiro simulado, para validar o
app do jogador e o painel antes do beta fechado.

Não é produção. Continuam bloqueados por decisão (ADR 0049 e pareceres):
dinheiro real, PSP real, NFS-e, escrow/modelo C, KYC/MED e SMS real.

## 2. Arquitetura obrigatória: uma origem

O painel usa `API_BASE="/api/v1"` e `credentials: "same-origin"`
(`web/src/lib/api.ts`), e a API usa cookies `SameSite=Strict`. Painel e API em
domínios diferentes **quebram o login**.

| Camada | Escolha | Motivo |
|---|---|---|
| API + painel | Um único container no Render (Caddy serve `/srv/web` e faz proxy de `/api/*` para o uvicorn) | Mesma origem, sem CORS |
| Banco | Supabase free (Postgres + PostGIS) | PostGIS pronto, sem cartão |
| E-mail | Brevo free (300/dia) | Envia para qualquer destinatário sem domínio verificado |
| Worker | Task inline na API + GitHub Actions agendado (reserva) | Render free não mantém worker dedicado; o cron do GitHub é *best-effort* |
| Redis | Nenhum | O código não usa |

Não adicionar CORS.

### Roteamento no Caddy

| Caminho | Destino | Basic auth |
|---|---|---|
| `/api/*` (inclui `/api/v1/health/live` e `/ready`) | `127.0.0.1:8000` | **não** (app mobile e monitores não enviam credencial HTTP) |
| `/.well-known/assetlinks.json` | `/srv/web/.well-known/assetlinks.json` | **não** (Digital Asset Links do Android; expõe só este arquivo) |
| `/` e assets do SPA | `/srv/web` com fallback `index.html` | **sim** |

## 3. Artefatos

| Artefato | Estado | Observação |
|---|---|---|
| `Dockerfile` (raiz) | **Pronto** | Multi-stage: Node 22 + pnpm 9.15.4; Python 3.12 + `requirements.lock`; Caddy oficial >= 2.8 validado no build |
| `deploy/Caddyfile` | **Pronto** | `handle /api/*` sem basic auth; SPA com `basic_auth`; `try_files` |
| `deploy/start.sh` | **Pronto** | `alembic upgrade head` com 3 tentativas; uvicorn em loopback; `exec caddy run` |
| `.dockerignore` | **Pronto** | Exclui `.git`, `node_modules`, `.venv`, `__pycache__`, `web/dist`, `mobile`, `telas`, `backend/var`, `.env*`, `dist` |
| `render.yaml` | **Pronto** | Web service Docker, `plan: free`, health check `/api/v1/health/ready` |
| `backend/scripts/seed_demo.py` | **Pronto** | Idempotente; usa `pricing.service`, `EmailAccountService`, `OrganizationService` e `VenueService` |
| `.github/workflows/email-worker.yml` | **Já existia** | `development` + `simulator`; roda no branch padrão |
| `.github/workflows/email-cleanup.yml` | **Já existia** | Limpeza diária |

## 4. Contas e chaves necessárias

| Conta | O que pegar | Vai para | Custo |
|---|---|---|---|
| Supabase | URL do **Session pooler** + senha do banco + região | `JOGA_DATABASE_URL` | Free (500 MB) |
| Render | Acesso ao dashboard/API | Deploy do serviço | Free (750 h/mês) |
| Brevo | API key e remetente verificado | `JOGA_EMAIL_API_KEY`, `JOGA_EMAIL_FROM` | Free (300/dia) |
| GitHub | Permissão para secrets e workflow_dispatch | Workflows | Free |
| UptimeRobot | Monitor HTTP(S) | Ping do health | Free |

### Supabase: o que pegar e o que **não** pegar

- **Pegue** `Settings → Database → Connection string`. Use o **Session pooler**
  (porta 5432, host `aws-0-<região>.pooler.supabase.com`, usuário
  `postgres.<ref>`).
- **Não use** as chaves `anon` e `service_role` de `Settings → API`. O JOGA fala
  Postgres direto.
- **Não use** o Transaction pooler (6543) para migração.
- Habilite a extensão antes das migrações:

```sql
create extension if not exists postgis;
```

### Por que Session pooler e não conexão direta

O host `db.<ref>.supabase.co` é IPv6-only na maioria dos projetos. O Render free
e os runners do GitHub Actions não têm saída IPv6 confiável. O Session pooler é
IPv4 e mantém compatibilidade com migração.

## 5. Variáveis de ambiente (nomes, sem valores)

Tudo marcado como **segredo** vai no dashboard, nunca no Git.

```text
JOGA_ENVIRONMENT=demo                  # desde 2026-11-20; ver seção 5.1
JOGA_DATABASE_URL                      # segredo: Session pooler + ?sslmode=require
JOGA_PHONE_HASH_SECRET                 # segredo
JOGA_TOKEN_HASH_SECRET                 # segredo
JOGA_CPF_KEY                           # segredo: base64 de 32 bytes
JOGA_CPF_KEY_ID=k1
JOGA_AUTH_EMAIL_ENABLED=true
JOGA_AUTH_PHONE_ENABLED=false
JOGA_ALLOW_EMAIL_REGISTRATION=true
JOGA_ALLOW_PHONE_REGISTRATION=false
JOGA_PHONE_REQUIRED_FOR_BOOKING=false
JOGA_SIGNUP_MODE=open                  # demo desde 2026-11-19 (kill switch)
JOGA_SIGNUP_MAX_PER_IP_PER_DAY=20
JOGA_EMAIL_PROVIDER=brevo
JOGA_EMAIL_API_KEY                     # segredo
JOGA_EMAIL_FROM=kramirodev@gmail.com
JOGA_EMAIL_FROM_NAME=JOGA
JOGA_EMAIL_DAILY_BUDGET=250
JOGA_EMAIL_MAX_PER_ADDRESS_PER_HOUR=5
JOGA_EMAIL_MAX_PER_IP_PER_HOUR=50
JOGA_EMAIL_INLINE_DRAIN_ENABLED=true   # drenagem no processo da API
JOGA_EMAIL_INLINE_DRAIN_INTERVAL_SECONDS=30
JOGA_WEB_COOKIE_SECURE=true            # HTTPS no Render
JOGA_PSP_PROVIDER=simulator
JOGA_MONEY_MODE=simulated
JOGA_FISCAL_MODE=disabled
JOGA_CUSTODY_MODEL=B
JOGA_TICKET_PURCHASE_ENABLED=false     # obrigatório false em demo (ADR 0053)
JOGA_PLATFORM_ADMINS=9f556105-a328-4a6a-bc8d-6276c6b3f1ba
                                       # operador@demo.joga.test; uuid já listado na seção 7
JOGA_WEBAUTHN_RP_ID=<host do Render, sem https>
JOGA_WEBAUTHN_ORIGIN_WEB=https://<host do Render>
JOGA_APP_VERSION_GATE_ENABLED=true
JOGA_MIN_APP_VERSION=1.0.1
JOGA_LATEST_APP_VERSION=1.0.1
# JOGA_APP_UPDATE_URL=https://...   # opcional; quando existir, use HTTPS
JOGA_MEDIA_ROOT=/app/backend/var/media
DEMO_BASIC_AUTH_HASH                   # segredo: hash bcrypt do Caddy
```

`JOGA_ENVIRONMENT=demo` **não** exige Mercado Pago: o boot aceita o perfil sem
`JOGA_MERCADO_PAGO_*` e constrói sempre o PSP simulador. Ele **exige** as guardas
descritas na seção 5.1; qualquer desvio falha no boot em vez de degradar.

### Risco encerrado: `development` até o modo demo (2026-11-20)

**Estado anterior (até 2026-11-20):** o demo rodou em
`JOGA_ENVIRONMENT=development`, um ambiente local. Nesse perfil, a simulação de
pagamento de reserva, a confirmação de passe sem PSP e o webhook sem assinatura
continuavam aceitos pelo código. O risco era aceito porque o valor era simulado
(`JOGA_MONEY_MODE=simulated`), não havia PSP nem checkout do passe, o demo era
privado e a correção definitiva (modo demo explícito) estava decidida.

**Estado atual:** as guardas do modo demo estão aplicadas desde 2026-11-20
(seção 5.1), conforme o ADR 0053. Webhook responde `404 webhook_disabled`, compra
de tickets responde `503 ticket_purchase_disabled`, a documentação interativa
(`/api/docs`, `/api/openapi.json`, `/redoc`) responde 404 e o app recebe
`demo_mode: true` em `/api/v1/app-config`.

**Gatilhos de revisão:** qualquer dinheiro real, PSP real ou dado de usuário
real exige voltar a este documento e revisar as guardas antes de expor o
ambiente.

### Cadastro aberto e kill switch

O demo está com `JOGA_SIGNUP_MODE=open` desde 2026-11-19 para validar o
autoatendimento pelo app. A cota de e-mail é protegida pelo orçamento
(`JOGA_EMAIL_DAILY_BUDGET=250`), pelos limites por IP/endereço e pelo teto de
cadastros por IP.

Emergência (sem deploy): troque `JOGA_SIGNUP_MODE=closed` no dashboard do
Render; a mudança reinicia o serviço e o endpoint
`POST /api/v1/auth/email/code` (`registration`) volta a responder
`403 signup_closed`. O `render.yaml` é a fonte para recriar o ambiente e só
muda por commit; mantenha dashboard e arquivo alinhados.

### Drenagem inline da Outbox

O Render free dorme e não mantém worker. O cron do GitHub é *best-effort*: em
2026-11-19 houve **1** execução agendada em 4h15, o que não sustenta o aceite de
15 min. Por isso a API drena a Outbox sozinha:

- `JOGA_EMAIL_INLINE_DRAIN_ENABLED=true` sobe uma task asyncio no lifespan do
  FastAPI; cada ciclo chama `dispatch_email_deliveries` fora do event loop.
- `JOGA_EMAIL_INLINE_DRAIN_INTERVAL_SECONDS=30` (mínimo 10, máximo 300; valor
  fora da faixa falha no boot).
- O ciclo usa `pg_try_advisory_lock` (`backend/app/modules/email/drain_lock.py`,
  chave `4_426_433_101`). API e workflow usam o **mesmo** lock, então nunca há
  envio duplo; se o lock estiver ocupado, o ciclo é ignorado e tenta de novo.
- Falha do provedor não derruba a API: o ciclo loga, a entrega volta para a
  fila com backoff e o próximo ciclo tenta outra vez. Shutdown cancela a task.
- `email_deliveries.sent_at` guarda o aceite do provedor; a latência
  (`sent_at - created_at`) é logada por mensagem (`latencia_ms`) e resumida por
  ciclo em p50/p95 do dia (UTC).
- **Aceite do demo:** p95 ≤ 60 s com o serviço acordado. Até 15 min vale apenas
  no caminho de reserva (workflow do GitHub), quando a API estiver dormindo.
- O workflow `Email worker (Outbox)` continua ativo como reserva; ele não é mais
  o caminho principal.

**Cota do Brevo (monitoramento).** O orçamento é 250/dia, abaixo da cota free
de 300. Em 80% (200 e-mails) o backend grava `email.budget_warning`; em 100%
bloqueia envio novo com `email.budget_exhausted` e mantém a resposta pública
`202`. Acompanhamento por SQL (sem PII):

```sql
SELECT count(*) FILTER (WHERE created_at >= date_trunc('day', now())) AS hoje,
       count(*) FILTER (WHERE created_at >= now() - interval '24 hours') AS ultimas_24h
FROM email_deliveries
WHERE status = 'sent';
```

### Hash do basic auth

O usuário é fixo `demo`; o que varia é a senha. Gerar dentro da imagem (a senha
não é versionada):

```bash
docker run --rm joga-demo caddy hash-password --plaintext '<senha-do-demo>'
```

No Render, cole o hash em `DEMO_BASIC_AUTH_HASH` (secret). O Caddyfile lê a
variável em tempo de execução; sem ela, o Caddy falha fechado. A diretiva
`basic_auth` do Caddy exige o par `<usuário> <hash>` — por isso o Caddyfile tem
`demo {$DEMO_BASIC_AUTH_HASH}` e não apenas o hash.

### Rate limit do basic auth: risco aceito (2026-11-20)

O `basic_auth` do Caddy **não tem rate limit** e não será adicionado nesta fase.
**Decisão:** manter senha forte e aceitar o risco; não usar Cloudflare (não há
domínio próprio) nem plugin/xcaddy (custo desproporcional). A imagem, o
`Dockerfile` e o `Caddyfile` não mudam por causa disso.

**Por que o risco é aceito:**

- o basic auth protege apenas o SPA estático em `/`; `/api/*` fica fora e tem
  autenticação, autorização e rate limit próprios no backend;
- o demo é privado, não indexado e não contém dado financeiro real;
- a senha é aleatória, com 24+ caracteres, e o hash bcrypt fica somente no
  Render;
- o pior caso é tentativa de força bruta contra uma senha longa, sem acesso
  direto a dados além do próprio SPA.

**Gatilhos de revisão:** domínio próprio; demo público ou longevo; painel
passando a servir dado fora da API; aumento anormal de respostas 401 no Caddy;
incidente de acesso ao painel. Nesses casos, reavaliar Cloudflare/proxy com
rate limit ou autenticação mais forte.

**Rotação:** gerar a senha com CSPRNG (24+ caracteres) e o hash com
`caddy hash-password` (bcrypt custo 14); aplicar o hash em
`DEMO_BASIC_AUTH_HASH` no Render, reiniciar e testar `GET /` sem credencial
(401) e com `demo:<senha>` (200). Em 2026-11-20 foi gerada uma credencial nova e
mantida fora do Git; o hash **não foi aplicado** porque não houve autorização
para alterar variáveis de ambiente. A aplicação fica para a janela do modo demo.

### Gate de versão do app mobile

O app 1.0.1 envia `X-Client: mobile`, `X-App-Version`, `X-Build-Number` e
`X-Platform` em REST e WebSocket. O painel envia `X-Client: web`. Com
`JOGA_APP_VERSION_GATE_ENABLED=true`, mobile abaixo de `JOGA_MIN_APP_VERSION`
recebe **426 `app_update_required`** (WebSocket fecha com 4403). Health,
`/api/v1/app-config` e o painel ficam isentos. Sem `X-Client`, User-Agent
OkHttp/CFNetwork/Expo é tratado como mobile antigo; curl e navegador continuam
liberados.

O gate não é fronteira de segurança: headers podem ser falsificados. Ele existe
para impedir que binários antigos continuem consumindo a API; autorização e rate
limit permanecem no servidor. Ver ADR 0051.

**Estado no demo (2026-11-19):** gate ativo com 29 variáveis; mobile 1.0.0
recebe 426, mobile 1.0.1 passa, painel e curl continuam liberados.

## 5.1 Troca para o ambiente demo (2026-11-20)

**Executado em 2026-11-20:** o serviço `joga-demo` passou de
`JOGA_ENVIRONMENT=development` para `demo` no deploy de `6a89c79` (`main`). O
deploy terminou **live** e o ambiente passou a responder com as guardas
server-side do ADR 0053.

O procedimento abaixo é a ordem reproduzível. O ponto crítico é que mudar
variável no Render **não reinicia o processo**: sem o deploy do passo 3, o
serviço continua rodando com o ambiente antigo.

### Ordem obrigatória

1. **Deploy do código.** Publique o `main` que contém o modo demo e aguarde o
   status **live**. Aplicar `JOGA_ENVIRONMENT=demo` antes de a imagem ter o
   perfil demo faz o boot cair no ramo de produção, que exige
   `JOGA_PSP_PROVIDER=mercadopago` e credenciais do Mercado Pago; o deploy
   falha.
2. **Aplicar as variáveis** no dashboard/API do Render (tabela abaixo).
3. **Disparar um deploy** (*Manual Deploy → Deploy latest commit*) para
   reiniciar o serviço e reler o ambiente. A mudança de variável sozinha não
   reinicia nada.
4. **Validar** com os comandos de "Validação" antes de liberar o demo.

### Variáveis aplicadas nesta troca

| Variável | Valor | Observação |
|---|---|---|
| `JOGA_ENVIRONMENT` | `demo` | muda a classificação de ambiente; ver ADR 0053 |
| `JOGA_TICKET_PURCHASE_ENABLED` | `false` | o boot demo recusa `true` |
| `JOGA_PLATFORM_ADMINS` | `9f556105-a328-4a6a-bc8d-6276c6b3f1ba` | operador `operador@demo.joga.test` (UUID já listado na seção 7) |

### Perfil exigido pelo boot demo

Além das variáveis já existentes no serviço, o boot com `JOGA_ENVIRONMENT=demo`
valida este conjunto (nomes apenas; segredos ficam no Render):

```text
JOGA_ENVIRONMENT=demo
JOGA_PSP_PROVIDER=simulator            # obrigatório
JOGA_MONEY_MODE=simulated              # obrigatório
JOGA_TICKET_PURCHASE_ENABLED=false     # obrigatório
JOGA_PHONE_HASH_SECRET                 # segredo próprio do demo, nunca o default
JOGA_TOKEN_HASH_SECRET                 # segredo próprio do demo, nunca o default
JOGA_CPF_KEY                           # segredo: 32 bytes em base64
JOGA_CPF_KEY_ID                        # identificador da chave já configurada
JOGA_PLATFORM_ADMINS                   # operador do seed, para /admin/venues
```

Não são exigidos `JOGA_MERCADO_PAGO_ACCESS_TOKEN`,
`JOGA_MERCADO_PAGO_WEBHOOK_SECRET` nem `JOGA_MERCADO_PAGO_NOTIFICATION_URL`.
`JOGA_DEV_FIXED_OTP` é recusado no boot demo. Faltando CPF, segredo de hash ou
qualquer flag acima, o boot falha e o deploy não fica `live`.

### Validação

A URL real não é versionada; pegue o host no dashboard do Render.

```bash
export BASE_URL="https://<url-do-demo>"

curl -s -o /dev/null -w 'ready=%{http_code}\n' "$BASE_URL/api/v1/health/ready"
curl -s -o /dev/null -w 'docs=%{http_code}\n' "$BASE_URL/api/docs"
curl -s -o /dev/null -w 'openapi=%{http_code}\n' "$BASE_URL/api/openapi.json"
curl -s -o /dev/null -w 'redoc=%{http_code}\n' "$BASE_URL/redoc"
curl -s -o /dev/null -w 'webhook=%{http_code}\n' -X POST "$BASE_URL/api/v1/payments/mercadopago/webhook"
curl -s -o /dev/null -w 'tickets=%{http_code}\n' -X POST "$BASE_URL/api/v1/me/tickets/purchases" -H 'Content-Type: application/json' -d '{}'
curl -s -o /dev/null -w 'admin_venues=%{http_code}\n' "$BASE_URL/api/v1/admin/venues"
curl -s -o /dev/null -w 'catalog=%{http_code}\n' "$BASE_URL/api/v1/catalog/visual"
curl -s "$BASE_URL/api/v1/app-config"
curl -sI "$BASE_URL/api/v1/health/ready"
```

Resultado observado após a troca:

| Verificação | Resultado |
|---|---|
| `GET /api/v1/health/ready` | 200 |
| `GET /api/docs`, `GET /api/openapi.json`, `GET /redoc` | 404 (documentação desabilitada em demo) |
| `POST /api/v1/payments/mercadopago/webhook` | 404 `webhook_disabled`, antes de ler o corpo |
| `POST /api/v1/me/tickets/purchases` | 503 `ticket_purchase_disabled` |
| `GET /api/v1/admin/venues` sem sessão | 401 |
| `GET /api/v1/catalog/visual` | 200 |
| `GET /api/v1/app-config` | 200 com `demo_mode: true` |

Headers conferidos na borda (Caddy): `Strict-Transport-Security`,
`Content-Security-Policy`, `X-Frame-Options: DENY`, `Permissions-Policy`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` e
`Cache-Control: no-store`.

### Rollback

O rollback é voltar ao perfil anterior, ciente de que isso **reabre** os caminhos
que o modo demo fecha:

1. no dashboard/API do Render, definir `JOGA_ENVIRONMENT=development`
   (mantenha `JOGA_PSP_PROVIDER=simulator` e `JOGA_MONEY_MODE=simulated`);
2. disparar um deploy para reiniciar o serviço;
3. validar `/api/docs` (volta a responder), o webhook (volta a aceitar evento
   sem assinatura) e o `/api/v1/app-config` (`demo_mode` volta a `false`).

O rollback reabre a documentação interativa e o webhook sem assinatura, e
devolve a simulação de pagamento sem as guardas do modo demo. Use apenas como
emergência, registre o motivo e reverta assim que possível.

### `render.yaml` está defasado

O blueprint versionado ainda declara `JOGA_ENVIRONMENT=development` e não contém
`JOGA_TICKET_PURCHASE_ENABLED` nem `JOGA_PLATFORM_ADMINS`; o serviço em execução
foi alterado pelo dashboard/API. **Não edite o `render.yaml` sem ordem
explícita.** Se o Blueprint for sincronizado ou o serviço recriado a partir dele,
atualize essas três entradas antes — do contrário o demo volta para
`development` e reabre docs e webhook.

## 6. Banco: migração e cuidados

O `backend/.env` aponta para o Postgres **local** de propósito. Para migrar o
remoto, use a variável inline na sessão — não edite o `.env`:

```powershell
cd backend
$env:JOGA_DATABASE_URL="postgresql+psycopg://postgres.<ref>:<senha>@aws-1-<região>.pooler.supabase.com:5432/postgres?sslmode=require"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
Remove-Item Env:JOGA_DATABASE_URL
```

Regras:

- Nunca executar `alembic downgrade` contra o Supabase. É drop de schema.
- `alembic check` precisa dizer "No new upgrade operations detected".
- Head esperado: `y8b9c0d1e2f3`.

**Estado remoto (2026-11-18):** projeto `cdleiwxqmlawaaadsxhe`, região
`us-east-2`; PostGIS `3.3.7` habilitado em `public`; migrações aplicadas até
`y8b9c0d1e2f3` pelo Session pooler
`aws-1-us-east-2.pooler.supabase.com:5432`. `alembic current` e `alembic check`
limpos.

## 7. Seed de demonstração

```powershell
cd backend
$env:JOGA_DATABASE_URL="postgresql+psycopg://..."
$env:JOGA_DEMO_SEED_PASSWORD="<senha-forte>"
.venv\Scripts\python.exe -m scripts.seed_demo
Remove-Item Env:JOGA_DATABASE_URL, Env:JOGA_DEMO_SEED_PASSWORD
```

O script é idempotente: na segunda execução reaproveita usuários, organização,
estabelecimento e quadra, e só cria janelas de agenda que faltam. A senha vem
somente de `JOGA_DEMO_SEED_PASSWORD`; o hash é Argon2id produzido pelo
`PasswordService`.

Dados criados:

| Item | Valor |
|---|---|
| Operador | `operador@demo.joga.test` (OWNER da organização) |
| Jogador | `jogador@demo.joga.test` |
| Organização | `Arena Demo` (CNPJ fictício `11222333000181`) |
| Estabelecimento | `Arena Demo Centro`, São Paulo/SP |
| Quadra | `Quadra 1` |
| Agenda | Todos os dias, 06:00–22:00, R$ 120,00, slot de 60 min |
| Faixas | Tabela 2D padrão via `pricing.service` |

### IDs do seed remoto

O seed foi executado duas vezes no Supabase. A segunda execução preservou os
mesmos IDs e criou 0 janelas de agenda:

| Item | ID |
|---|---|
| Operador | `9f556105-a328-4a6a-bc8d-6276c6b3f1ba` |
| Jogador | `7767af50-d2e0-4cc5-b095-8d2e96210432` |
| Organização | `ad5dc6fb-1029-432e-aa1a-b6fa87e21c6a` |
| Estabelecimento | `52c7a0db-684b-46b7-9512-b29664e68eff` |
| Quadra | `14ee4dc5-1cd3-4c38-988f-dc1877ac2356` |

## 8. Render (executado)

O web service foi criado pela API do Render, somente para o demo:

| Item | Valor |
|---|---|
| Serviço | `joga-demo` (`srv-dbv1gmek1f9s73b4m4rg`) |
| Runtime | Docker, contexto na raiz, `./Dockerfile` |
| Plano | `free` (sem cartão, sem upgrade, sem trial) |
| Região | `ohio` (mesma região AWS do Supabase, `us-east-2`) |
| Health check | `/api/v1/health/ready` |
| Variáveis | 34, com `JOGA_ENVIRONMENT` agora `demo`; somam-se `JOGA_TICKET_PURCHASE_ENABLED=false` e `JOGA_PLATFORM_ADMINS` (seção 5.1); valores secretos só no Render |
| Deploy | `bed5e96` **live** em 2026-11-19 (disparado pela API); `6a89c79` **live** em 2026-11-20, já em `JOGA_ENVIRONMENT=demo` |
| URL | `<url-do-demo>` (intencionalmente não versionada) |

O build Docker foi executado pelo Render a partir do HEAD; o container subiu, as
migrações rodaram no boot e o health check ficou 200. O
`Dockerfile`/`deploy/start.sh` não foram testados localmente porque Docker não
está instalado neste host, mas o build remoto validou o caminho. O auto-deploy
não disparou nos primeiros minutos após o push; o deploy do HEAD foi disparado
pela API do Render.

**Basic auth do painel:** usuário `demo`; a senha está em
`DEMO_BASIC_AUTH_PASSWORD` no `.env.deploy` (arquivo ignorado pelo Git). O hash
bcrypt correspondente está em `DEMO_BASIC_AUTH_HASH` no Render.

Observação: `render.yaml` usa `sync: false` para `JOGA_WEBAUTHN_ORIGIN_WEB`; o
host real foi definido no serviço criado pela API. Se o Blueprint for usado no
futuro, preencha essa variável com `https://<url-do-demo>`.

## 9. GitHub (worker de e-mail)

Secrets do repositório:

- `JOGA_DATABASE_URL` (Session pooler)
- `JOGA_EMAIL_API_KEY`
- `JOGA_EMAIL_FROM`

**Estado (2026-11-19):** os três secrets estão configurados e o workflow segue
`active` na `main`. O caminho principal passou a ser a drenagem inline da API
(seção 5); o workflow é a reserva. O cron do GitHub não é confiável para o
aceite: em 2026-11-19 houve **1** execução agendada (run `44437055423`, 01:27Z)
em 4h15 de janela, e uma entrega ficou presa por 28 min até um
`workflow_dispatch` manual (run `44467343379`) drenar a Outbox.

Conferência manual (reserva), em Actions → "Email worker (Outbox)" → *Run
workflow*: o log termina com `enviados` > 0 e, no banco,
`email_deliveries.status = 'sent'` com `provider_message_id`.

Lembretes: o cron só roda no branch padrão e é desativado após ~60 dias sem
atividade no repositório.

## 10. UptimeRobot

Monitor HTTP(s) criado em `<url-do-demo>/api/v1/health/live`, intervalo de 5
minutos, alerta no contato de e-mail já existente na conta. Sem basic auth (o
health é aberto). Isso também reduz o sleep do Render.

| Item | Valor |
|---|---|
| Monitor | `804728291` |
| Tipo | HTTP(s) |
| Intervalo | 300 s |
| Contato | `9051684` (e-mail, ativo) |
| Método | GET (`http_method=2`) |
| Status | **up (2)** |

O monitor padrão da UptimeRobot enviava HEAD e recebia 405 do health; o método
foi ajustado para GET no monitor existente, sem criar duplicata nem apagar
monitores.

## 11. Smoke test

### Ambiente público (Render + Supabase) — baseline 2026-11-18

| Verificação | Resultado |
|---|---|
| `GET /api/v1/health/live` sem credencial | 200 `{"status":"ok"}` |
| `GET /api/v1/health/ready` sem credencial | 200 `{"status":"ok","database":"ok"}` |
| `GET /api/v1/app-config` | 200 com `min_supported_version=1.0.1` |
| Mobile 1.0.0 / sem headers | 426 `app_update_required` |
| Mobile 1.0.1 | login 200; headers `X-Client`/`X-App-Version` |
| `X-Client: web` | login 200 |
| `GET /` sem basic auth | 401 |
| `GET /` com `demo:<senha>` | 200, SPA carrega; assets JS/CSS 200 |
| Login do painel (`/auth/web/email/login`) | 200; organização `Arena Demo` visível |
| `GET /organizations` com sessão do painel | 200, papel `OWNER` |
| Cookies do painel | `joga_web_refresh` HttpOnly/Secure/SameSite=strict; `joga_web_csrf` Secure/SameSite=strict |
| `POST /auth/email/login` com senha errada | 401 `invalid_credentials` |
| Login do jogador | 200, access + refresh emitidos |
| `GET /auth/emails` | 200, apenas `jogador@demo.joga.test` |
| `GET /discovery/bookable-venues` | 200, `Arena Demo Centro` |
| `GET /me/tickets` | 200, `source=ledger`, saldo 0 |
| `PUT /me/email` | 200, altera só o pagador |
| `GET /auth/emails` após o PUT | continua apenas `jogador@demo.joga.test` |
| `POST /auth/email/code` (`registration`) | 403 `signup_closed` |
| `POST /auth/email/code` (`password_reset`) | 202; worker drenou a Outbox |
| Worker `email-worker` | run `44408140879` success; `email_deliveries` `sent` com `provider_message_id` |
| Reset real (`kramirodev+teste@gmail.com`) | `sent` com `provider_message_id` |

O `SameSite=strict` é o valor emitido pelo Starlette; equivale semanticamente a
`SameSite=Strict`. Nenhum cookie, CSP ou CORS foi alterado.

### Cadastro aberto e drenagem inline (2026-11-19)

| Verificação | Resultado |
|---|---|
| Variáveis no Render | `JOGA_SIGNUP_MODE=open`, `JOGA_AUTH_EMAIL_ENABLED=true`, `JOGA_EMAIL_PROVIDER=brevo`, `JOGA_EMAIL_DAILY_BUDGET=250`, `JOGA_SIGNUP_MAX_PER_IP_PER_DAY=20`, `JOGA_EMAIL_MAX_PER_IP_PER_HOUR=50`, `JOGA_EMAIL_MAX_PER_ADDRESS_PER_HOUR=5`, `JOGA_EMAIL_INLINE_DRAIN_ENABLED=true`, intervalo 30 s |
| Sonda de cadastro (`registration` com domínio descartável) | 400 `email_domain_not_allowed` — o gate `signup_closed` passou, sem enviar e-mail |
| Antes da mudança | 403 `signup_closed` (mesma sonda) |
| Workflow `Email worker (Outbox)` | `active` na `main`; secrets `JOGA_DATABASE_URL`, `JOGA_EMAIL_API_KEY`, `JOGA_EMAIL_FROM` presentes |
| Execuções agendadas | 1 em 4h15 (run `44437055423`, 01:27Z) — cron não sustenta o aceite |
| Entrega presa | `security_alert` pendente 28 min; `workflow_dispatch` `44467343379` drenou e marcou `sent` com `provider_message_id`; Outbox em 0 pendentes |
| Latência p50/p95 do dia | coletada por `email_deliveries.sent_at`; sem tráfego real de cadastro depois do deploy |

O `render.yaml` local e o da `main` não contêm a URL pública; a origem WebAuthn
segue `sync: false` no dashboard.

### Modo demo (2026-11-20)

A troca para `JOGA_ENVIRONMENT=demo` foi validada no deploy `6a89c79`: health
`ready` 200; `/api/docs`, `/api/openapi.json` e `/redoc` 404; webhook 404
`webhook_disabled`; compra de tickets 503; `/api/v1/admin/venues` anônimo 401;
`/api/v1/catalog/visual` 200; `/api/v1/app-config` com `demo_mode: true`; e
headers de segurança na borda (`Strict-Transport-Security`,
`Content-Security-Policy`, `X-Frame-Options: DENY`, `Permissions-Policy`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
`Cache-Control: no-store`). Comandos e tabela completa na seção 5.1.

### Executado localmente (API + Postgres local, sem Caddy)

| Verificação | Resultado |
|---|---|
| `GET /api/v1/health/live` | 200 `{"status":"ok"}` |
| `GET /api/v1/health/ready` | 200 `{"status":"ok","database":"ok"}` |
| `POST /auth/email/login` com senha errada | 401 `invalid_credentials` |
| Login do jogador (e-mail + senha) | 200, access + refresh emitidos |
| `GET /auth/emails` | 200, apenas `jogador@demo.joga.test` |
| `GET /discovery/bookable-venues` | 200, `Arena Demo Centro` |
| `GET /me/tickets` | 200, `source=ledger`, saldo 0 |
| `PUT /me/email` | 200, altera só o pagador |
| `GET /auth/emails` após o PUT | continua apenas `jogador@demo.joga.test` |
| `POST /auth/email/code` (`registration`) | 403 `signup_closed` |
| Login do painel (`/auth/web/email/login`) | 200; cookies `joga_web_refresh` (HttpOnly) e `joga_web_csrf`, ambos `SameSite=Strict`, `Path=/` |
| `GET /organizations` com sessão do painel | 200, `Arena Demo`, papel `OWNER` |
| `POST /auth/email/code` (`password_reset`) | 202 com `challenge_id` |
| Worker `scripts.deliver_emails --once` com sender fake | `enviados=2`; `email_deliveries.status='sent'` |

### Caddy validado com o binário oficial (SPA stub, porta 8090)

O Caddyfile real foi executado com o Caddy 2.11.9 oficial para Windows,
substituindo apenas o `root` por um diretório temporário com um `index.html`
stub. O restante (proxy, basic auth, fallback) é o mesmo do container:

| Verificação | Resultado |
|---|---|
| `GET /api/v1/health/live` sem basic auth | 200 |
| `GET /api/v1/health/ready` sem basic auth | 200 |
| `GET /` sem basic auth | 401 |
| `GET /` com `demo:<senha>` | 200, corpo do SPA |
| `GET /painel/rota` com basic auth | 200, fallback para `index.html` |
| `caddy validate --config deploy/Caddyfile --adapter caddyfile` | `Valid configuration` |

### Pendente

| Verificação | Motivo |
|---|---|
| `docker build` local | Docker/Node ausentes neste host; o build remoto do Render ficou **live** |
| Confirmação de chegada do e-mail real | Brevo aceitou (`sent` com `provider_message_id`); depende da caixa `kramirodev+teste@gmail.com` |
| Reset completo (código → nova senha) | depende do código recebido na caixa real |
| Passkey Android | `/.well-known/assetlinks.json` servido e 200 sem basic auth; falta validar a cerimônia no APK 1.0.1 |

O `web/public/.well-known/assetlinks.json` declara `com.anonymous.joga` e o
SHA-256 do keystore de debug (`FA:C6:…:3B:9C`). O Caddy serve esse caminho sem
basic auth; a validação local retornou 200 sem credencial, com `/` ainda 401 e o
fallback do SPA 200. O login por senha continua independente de passkey.

### Assinatura de debug do APK/AAB: risco aceito (2026-11-20)

O APK/AAB de demonstração é assinado com o certificado de debug do Android
(`CN=Android Debug`, SHA-256 `FA:C6:…:3B:9C`), o mesmo do
`web/public/.well-known/assetlinks.json`. A chave de debug não tem custódia
adequada, é compartilhada por qualquer instalação Android e não é aceita por
loja. **Serve apenas para demo por sideload; nunca para publicação.**

A correção fica fora do escopo desta fase. Registro completo, limite e gatilhos
de revisão em `docs/THREAT_MODEL.md` ("Riscos aceitos da auditoria de
2026-11-20", item A). Antes de qualquer publicação em loja: gerar chave de
release com custódia fora do repositório, assinar com ela e reemitir o
`assetlinks.json`.

## 12. Limitações do free tier

- Render: dorme após ~15 min; primeiro acesso leva 30–60 s; 512 MB de RAM;
  750 h/mês.
- Supabase: pausa após ~7 dias sem uso.
- Brevo: 300 e-mails/dia, compartilhados entre código, boas-vindas e avisos.
- `JOGA_MEDIA_ROOT` é disco efêmero: fotos de quadra somem no redeploy.
- Sem backup automático confiável.
- Sem observabilidade além de log.
- O cron do GitHub é best-effort e desativado após ~60 dias sem atividade; por
  isso a entrega do demo depende da drenagem inline enquanto a API está
  acordada (p95 ≤ 60 s). Com o serviço dormindo, o pior caso é o caminho de
  reserva (até 15 min).

## 13. Como revogar / encerrar o demo

1. **Render:** Dashboard → serviço → *Suspend* ou *Delete*. Não há recurso pago.
2. **Supabase:** `Settings → Database → Reset database password`; depois
   atualizar `JOGA_DATABASE_URL` no Render e nos secrets do GitHub. Para
   encerrar, pausar/remover o projeto.
3. **Brevo:** `SMTP & API → API Keys` → revogar a chave usada.
4. **GitHub:** Settings → Secrets and variables → Actions → remover
   `JOGA_DATABASE_URL`, `JOGA_EMAIL_API_KEY`, `JOGA_EMAIL_FROM`.
5. **UptimeRobot:** remover o monitor.
6. **Basic auth:** trocar `DEMO_BASIC_AUTH_HASH` por um hash novo e reiniciar.
7. **Contas do seed:** são contas de demonstração. Ao encerrar, remova o serviço
   e rotacione a senha do banco; não há admin de usuários no painel.

Nunca commitar `.env`. O `.gitignore` da raiz cobre `.env` e `.env.*` em
qualquer diretório (inclusive `mobile/` e `web/`), com exceção de
`.env.example`, que continua versionado (`backend/.env.example`,
`mobile/.env.example`).

## 14. O que falta para produção (não é este documento)

Pareceres fiscal e jurídico, PSP real homologado, NFS-e, escrow, domínio próprio
com SPF/DKIM/DMARC, backups, observabilidade, worker dedicado, storage de objetos
e revisão de segurança (ADR 0049 e `docs/PENDENCIAS.md`).
