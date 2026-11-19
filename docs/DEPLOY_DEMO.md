# Deploy de demonstração (Render + Supabase)

**Status:** ambiente de demonstração **no ar** no Render free + Supabase. A URL
real não é versionada (repositório público); consulte o dashboard do Render.
Worker de e-mail validado; a Outbox remota está DISPATCHED e as entregas
`password_reset`/`security_alert` estão `sent`.

**Data:** 2026-11-18

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
| Worker | GitHub Actions agendado | Render free não mantém worker |
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
JOGA_ENVIRONMENT=development
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
JOGA_SIGNUP_MODE=closed                # decisão do demo: cadastro fechado
JOGA_EMAIL_PROVIDER=brevo
JOGA_EMAIL_API_KEY                     # segredo
JOGA_EMAIL_FROM=kramirodev@gmail.com
JOGA_EMAIL_FROM_NAME=JOGA
JOGA_EMAIL_DAILY_BUDGET=250
JOGA_WEB_COOKIE_SECURE=true            # HTTPS no Render
JOGA_PSP_PROVIDER=simulator
JOGA_MONEY_MODE=simulated
JOGA_FISCAL_MODE=disabled
JOGA_CUSTODY_MODEL=B
JOGA_WEBAUTHN_RP_ID=<host do Render, sem https>
JOGA_WEBAUTHN_ORIGIN_WEB=https://<host do Render>
JOGA_MEDIA_ROOT=/app/backend/var/media
DEMO_BASIC_AUTH_HASH                   # segredo: hash bcrypt do Caddy
```

`JOGA_ENVIRONMENT=development` é deliberado: fora de
`local/test/development/ci` o boot exige Mercado Pago com token e webhook
(`backend/app/core/config.py`). Por isso o demo é `development` e o acesso fica
atrás de basic auth.

### Cadastro fechado

`JOGA_SIGNUP_MODE=closed` impede que qualquer pessoa crie conta e consuma a cota
de 300 e-mails/dia. As contas de teste entram pelo seed. Para liberar
autoatendimento, troque para `open` sabendo do risco.

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
| Variáveis | 26, nomes conferidos na API; valores secretos só no Render |
| Deploy | HEAD, status **live** (deploy manual; auto-deploy não disparou) |
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

**Estado (2026-11-18):** os três secrets estão configurados. O workflow
`Email worker (Outbox)` foi executado com sucesso (run `44408140879`); a Outbox
remota ficou DISPATCHED e as entregas `password_reset`/`security_alert` estão
`sent`, com `attempts=1` e `provider_message_id`. Um reset real para
`kramirodev+teste@gmail.com` também foi enviado e ficou `sent`.

Depois do merge na `main`, em Actions → "Email worker (Outbox)" → *Run
workflow* (`workflow_dispatch`), conferir no log `enviados` > 0 e, no banco,
`email_deliveries.status = 'sent'`.

Lembretes: o cron do GitHub é best-effort (5–15 min), só roda no branch padrão e
é desativado após ~60 dias sem atividade.

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

### Ambiente público (Render + Supabase)

| Verificação | Resultado |
|---|---|
| `GET /api/v1/health/live` sem credencial | 200 `{"status":"ok"}` |
| `GET /api/v1/health/ready` sem credencial | 200 `{"status":"ok","database":"ok"}` |
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
| Passkey Android | `assetlinks.json` publicado em `web/public`; falta o redeploy e validar no APK |

O `web/public/.well-known/assetlinks.json` declara `com.anonymous.joga` e o
SHA-256 do keystore de debug (`FA:C6:…:3B:9C`). O Caddy serve esse caminho sem
basic auth; a validação local retornou 200 sem credencial, com `/` ainda 401 e o
fallback do SPA 200. O login por senha continua independente de passkey.

## 12. Limitações do free tier

- Render: dorme após ~15 min; primeiro acesso leva 30–60 s; 512 MB de RAM;
  750 h/mês.
- Supabase: pausa após ~7 dias sem uso.
- Brevo: 300 e-mails/dia, compartilhados entre código, boas-vindas e avisos.
- `JOGA_MEDIA_ROOT` é disco efêmero: fotos de quadra somem no redeploy.
- Sem backup automático confiável.
- Sem observabilidade além de log.
- O cron do GitHub é best-effort e desativado após ~60 dias sem atividade.

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

Nunca commitar `.env`. O `.gitignore` cobre `backend/.env`, `backend/.env.*` e
mantém `backend/.env.example` versionado.

## 14. O que falta para produção (não é este documento)

Pareceres fiscal e jurídico, PSP real homologado, NFS-e, escrow, domínio próprio
com SPF/DKIM/DMARC, backups, observabilidade, worker dedicado, storage de objetos
e revisão de segurança (ADR 0049 e `docs/PENDENCIAS.md`).
