# ADR 0075 — Endurecimento do schema `public` no Supabase (RLS, grants e Data API)

- **Status:** Aceito e aplicado no demo em 2026-11-24 (deploy
  `dep-dc30mce1egvs73832rk0`); migração `e2f3a4b5c6d7` executada no boot.
- **Data:** 2026-11-24
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** migração `e2f3a4b5c6d7` (revisa `d9e0f1a2b3c4`);
  `backend/scripts/audit_db_security.py`;
  `backend/tests/test_db_security_hardening.py`; `docs/THREAT_MODEL.md`;
  `docs/DEPLOY_DEMO.md` §4 e §11; `docs/RUNBOOK.md` §10.

## Contexto

Em 2026-11-24 o Supabase Security Advisor passou a reportar
`rls_disabled_in_public` no projeto do demo. Uma auditoria **somente de leitura**
confirmou o seguinte estado:

- 120 tabelas em `public` estavam sem Row Level Security (RLS): 118 tabelas de
  dados do app + `alembic_version` (controle de migração), ambas donas de
  `postgres`, + `spatial_ref_sys` (PostGIS, dona `supabase_admin`). A auditoria
  conta 118 tabelas de dados porque exclui `alembic_version` e objetos de
  extensão.
- `anon` e `authenticated` não tinham `SELECT`, `INSERT`, `UPDATE` nem `DELETE`
  nas tabelas do app, mas mantinham `TRUNCATE` — um privilégio destrutivo que
  não deveria existir para papéis que o app não usa.
- `anon` tinha DML completo em `spatial_ref_sys`, tabela do PostGIS cujo dono é
  `supabase_admin`.
- O schema `public` concedia `USAGE` a `PUBLIC`, `anon` e `authenticated`, e as
  default privileges continuavam concedendo `ALL` em objetos novos.
- O JOGA **não usa Data API, chave `anon` nem `service_role`**. O app fala
  Postgres direto pelo **Session pooler**, com o usuário `postgres.<ref>`, que
  resolve para o papel `postgres` com `BYPASSRLS`. Migrações, workers e API usam
  o mesmo caminho.

A chave `anon` é pública por desenho e não é segredo. O risco não é "alguém
descobrir a chave": é qualquer caminho que aceite essa chave (Data API,
PostgREST, integrações futuras) alcançar tabelas sem RLS e com grants amplos.
Como o projeto é demo e usa dados de usuários reais desde o SEC-001, o alerta
não pode ser tratado como ruído.

## Decisão

A correção é uma migração Alembic revisável, idempotente e restrita aos objetos
do app. Ela:

1. **Revoga `USAGE` e `CREATE` no schema `public`** de `PUBLIC`, `anon` e
   `authenticated`.
2. **Revoga `ALL`** em todas as tabelas, views, materialized views, foreign
   tables, sequences e funções do app desses mesmos papéis.
3. **Habilita RLS em todas as tabelas do app**, sem criar policies e sem
   `FORCE ROW LEVEL SECURITY` (o owner precisa continuar lendo e gravando).
4. Aplica **`security_invoker = true`** nas views do app, para que elas respeitem
   as permissões e a RLS de quem consulta, e não as do dono da view.
5. **Revoga as default privileges** que concedem `ALL` em tabelas, sequences e
   funções futuras a `anon`/`authenticated` (e a `PUBLIC`), para que a próxima
   `CREATE TABLE` não reabra o buraco. Vale para o papel que executa a migração;
   as default privileges de `supabase_admin` não são alteráveis por ele e ficam
   contidas pela falta de `USAGE` no schema.
6. **Não altera** objetos de `supabase_admin` — em especial `spatial_ref_sys` e
   as funções do PostGIS. A tabela fica inalcançável por `anon` porque o schema
   deixa de ter `USAGE`, sem precisar mexer em objeto de extensão.
7. **Preserva `postgres` e `service_role`.** O app continua funcionando pelo
   papel owner com `BYPASSRLS`; `service_role` não é usado pelo JOGA e fica
   intacta.
8. **Desliga a Data API, o Storage e o Auth do Supabase no dashboard**, que não
   são usados pelo produto. Essa etapa é operacional, não versionada, e deve ser
   registrada como evidência à parte.

### Por que RLS sem policies não quebra o app

RLS sem policy nega todas as linhas para papéis sujeitos a RLS. O papel
`postgres` do Supabase tem `BYPASSRLS`, então a API, os workers e as migrações
continuam lendo e gravando normalmente. `service_role` também tem `BYPASSRLS`.
O efeito prático é: qualquer acesso futuro por `anon`/`authenticated` encontra
schema sem `USAGE`, tabela sem grant e RLS fechada — três barreiras
independentes, sem depender de uma policy correta.

## O que NÃO fazer

- **Não reconceder** `USAGE`/`CREATE` no schema `public`, nem `SELECT`/`INSERT`/
  `UPDATE`/`DELETE`/`TRUNCATE` a `anon` ou `authenticated` "para resolver" um
  erro. Se um cliente legítimo precisar de acesso, isso exige ADR, policies
  explícitas e testes negativos.
- **Não criar policy permissiva** (`USING (true)`) para silenciar o advisor. Isso
  reabre a exposição e é pior que o estado anterior, porque parece controlado.
- **Não habilitar Data API/PostgREST**, expor a chave `anon` no app ou criar
  integração que dependa dela sem uma ADR específica.
- **Não desabilitar RLS** em tabela alguma para "destravar" consulta. O caminho
  correto é usar o papel owner/BYPASSRLS ou adicionar policy justificada.
- **Não revogar** privilégios de `postgres`, `service_role`, `supabase_admin` ou
  dos objetos de extensão. `spatial_ref_sys` não é tabela do app.
- **Não aplicar SQL manual** no SQL Editor do Supabase como correção
  permanente. A fonte é a migração; o dashboard só executa e registra.
- **Não rodar `alembic downgrade`** contra o Supabase. O downgrade desta
  migração é intencionalmente no-op: reabrir o schema exige uma decisão
  explícita de segurança e uma migração nova, revisada e justificada.

## Dependência do role owner/BYPASSRLS

O desenho depende de o app continuar conectando como `postgres.<ref>` no Session
pooler, papel owner com `BYPASSRLS`. Consequências:

- trocar `JOGA_DATABASE_URL` para um papel sem `BYPASSRLS` e sem policies faz
  todas as consultas do app retornarem vazio ou falharem — é uma parada total,
  não uma degradação;
- um papel de aplicação dedicado, se adotado no futuro, precisa de policies
  explícitas por tabela **ou** de desenho equivalente aprovado em ADR;
- workers e migrações herdam o mesmo requisito, porque usam a mesma URL;
- o Session pooler é obrigatório por IPv4; o formato do usuário é
  `postgres.<project-ref>` e não deve ser trocado por um usuário de Data API.

## Consequências

- As tabelas de dados do app ficam cobertas por RLS; `spatial_ref_sys` segue
  sem RLS por ser objeto de extensão (`supabase_admin`) e fica inalcançável por
  `anon`/`authenticated` pela falta de `USAGE`.
- Nenhum cliente PostgREST/Data API consegue operar no schema `public`; hoje não
  existe cliente assim, então não há quebra funcional esperada.
- `spatial_ref_sys` continua pertencendo ao PostGIS, mas sem `USAGE` no schema
  não é alcançável por `anon`/`authenticated`.
- O schema fica "fechado por padrão": novos objetos só ganham acesso se alguém
  conceder explicitamente, o que é o comportamento desejado.
- A migração habilita RLS em 119 tabelas donas de `postgres` (118 de dados do
  app + `alembic_version`) e pode adquirir locks curtos de DDL; aplicar em
  janela de baixo tráfego. Mudanças futuras que alterem dados exigem
  snapshot/backup recuperável; esta migração é somente de catálogo.
- O dashboard do Supabase continua fora do controle de versão. Se a Data API for
  religada por engano, o schema fechado ainda bloqueia o acesso, mas a recomendação
  é desligá-la e registrar a decisão.

## Operação e reteste

Pré-condições: autorização explícita e janela de reinício combinada. Mudanças
que alterem dados exigem snapshot/backup recuperável. **Esta rodada não teve
snapshot dedicado** (limite operacional do Supabase free): a migração é somente
de catálogo e foi validada em transação revertida no Supabase real antes do
deploy (ver Resultado).

1. **Antes:** rodar a auditoria read-only e guardar a saída sem PII/segredos.
   O baseline esperado é o descrito no Contexto (118 tabelas de dados do app +
   `alembic_version` + `spatial_ref_sys`, 120 no total, sem RLS e com grants
   amplos).
2. **Aplicar:** deploy do commit que contém a migração. O `deploy/start.sh` roda
   `alembic upgrade head` no boot; confirmar `alembic current` na cabeça e
   `alembic check` sem operações pendentes. **Executado em 2026-11-24** (deploy
   manual `dep-dc30mce1egvs73832rk0`, `live`; commits `65bc9b2` da borda e
   `0db2a49` do backend na `main`).
3. **Auditar depois:** executar o script read-only
   `python -m scripts.audit_db_security` (saída JSON; exit 0 limpo, 1 para
   violação e 2 para erro de conexão) ou as consultas de
   `docs/RUNBOOK.md` §10.1. Baseline esperado:
   - 0 tabelas de dados do app com `relrowsecurity = false`;
   - `has_schema_privilege('anon', 'public', 'USAGE'|'CREATE') = false` e o mesmo
     para `authenticated`;
   - 0 entradas de ACL diretas para `anon`/`authenticated` em tabelas/views,
     sequences e funções/procedures do app (o script cobre os três grupos); as
     consultas de `docs/RUNBOOK.md` §10.1 ficam como conferência manual;
   - 0 views do app sem `security_invoker` (o script reporta como warning);
   - nenhuma default privilege para `anon`/`authenticated` em `public`.
4. **Smoke do app:** health, login do jogador e do operador, catálogo,
   carteira/passe, endpoints administrativos, painel com basic auth e
   `assetlinks.json`, conforme a tabela abaixo. Sem isso, a migração não está
   validada.
5. **Advisor:** recarregar o Security Advisor do Supabase. O alerta pode levar
   alguns minutos para refletir o catálogo; se persistir, conferir se o objeto
   apontado é de extensão (`supabase_admin`), não do app.
6. **Dashboard:** desligar Data API, Storage e Auth; registrar data, responsável
   e evidência (captura sem credencial). Não copiar URL com senha para ticket.
   **Pendente em 2026-11-24:** não foram desligados nem verificados.
7. **Registro:** anexar a saída da auditoria e o resultado do smoke ao PR/ADR.

### Resultado da aplicação (2026-11-24)

- **Migração no boot:** log `Running upgrade d9e0f1a2b3c4 -> e2f3a4b5c6d7`.
- **Sem snapshot dedicado:** não houve backup/snapshot antes do deploy — limite
  operacional do Supabase free. A migração altera somente catálogo (ACL, RLS,
  default privileges e `security_invoker`), não dados. Antes do deploy, os 5 DO
  blocks foram executados numa transação revertida no Supabase real (dry-run) e
  o rollback foi confirmado; o deploy aplicou a migração no boot e o app/smoke
  ficaram verdes. **Limitação registrada, não recomendação:** mudanças futuras
  que alterem dados exigem snapshot.
- **Auditoria:** `audit_db_security` exit 0, `ok=true`, `violations=[]`,
  `warnings=[]`; 118/118 tabelas de dados do app com RLS, 0 sem RLS; 119/120
  tabelas em `public` com RLS (a 120ª é `spatial_ref_sys`, dona
  `supabase_admin`/PostGIS, ainda sem RLS); 2 funções do app e 0 sequences;
  nenhuma default privilege para `anon`/`authenticated`/`PUBLIC`.
- **Acesso negado:** `SET ROLE anon`/`authenticated` em `public.users`,
  `public.spatial_ref_sys` e `public.ticket_balances` retornou
  `permission denied for schema public`.
- **Smoke:** `/health/live` e `/health/ready` 200; `/app-config` 200 com
  `demo_mode=true`; login de jogador e operador 200; `/auth/me`,
  `/me/profile`, `/catalog/sports`, `/me/tickets`, `/me/pass` e `/admin/users`
  200; painel com basic auth 200 e CSP presente; `/.well-known/assetlinks.json`
  200 JSON. Logs do Render sem 5xx após o boot (os 502 de health check durante o
  boot foram transitórios, antes de o uvicorn subir).
- **Pendência:** Data API, Storage e Auth do Supabase não foram desligados nem
  verificados no dashboard.

## Riscos residuais e gatilhos de revisão

- **Residual operacional:** Data API, Storage e Auth continuam existindo até
  serem desligados no dashboard. Enquanto isso, o schema fechado é o controle
  efetivo; a chave `anon` não deve ser distribuída.
- **Residual de extensão:** `spatial_ref_sys` é gerenciada por `supabase_admin`;
  o JOGA não a altera. Se uma migração futura precisar de extensão em `public`,
  revisar grants e `USAGE` antes.
- **Gatilhos:** novo alerta de RLS/grants; criação de tabela/view fora da
  migração; adoção de Data API, PostgREST ou chave `anon`; troca do papel de
  conexão do app; atualização do Supabase que altere default privileges;
  incidente de acesso ou `TRUNCATE` inesperado.
- Em qualquer gatilho: rodar a auditoria, comparar com o baseline e corrigir por
  migração. Reconceder acesso exige ADR, policy explícita e teste negativo.
