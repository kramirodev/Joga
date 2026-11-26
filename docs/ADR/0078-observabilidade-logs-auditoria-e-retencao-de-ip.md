# 0078 — Observabilidade: logs operacionais, auditoria e retenção de IP

- **Status:** aceito
- **Data:** 2026-11-25
- **Fase:** 1 (backend) do sistema de logs, observabilidade e auditoria
- **Relacionados:** SEC-002 (IP real atrás de Render + Cloudflare), SEC-003 (step-up do admin, **não implementado**), ADR 0047 (painel de moderação/operadores), ADR 0066 (admin de plataforma)

## Contexto

O produto já tinha duas trilhas duráveis e append-only:

- `audit_logs` — ações administrativas e sensíveis, com ator, ação, recurso, motivo e detalhes;
- `security_events` — autenticação e abuso, em geral sem PII em claro e apenas com hash de IP.

Também existia log de acesso estruturado em stdout (`joga.http`), com `request_id`, mas sem
persistência consultável. Isso impedia investigar um incidente por usuário, IP, endpoint ou
`request_id`, e não havia classificação consistente por nível/categoria, retenção explícita nem
proteção contra vazamento de segredos em mensagens.

O painel web (Fase 2) precisa de uma API de consulta. Captura de erro do app mobile é Fase 3 e
não faz parte desta decisão.

## Decisão

### 1. Uma tabela operacional e duas trilhas canônicas

- `log_events` guarda eventos operacionais: HTTP, aplicação, jobs e clientes.
- `security_events` continua sendo a trilha canônica de segurança; `audit_logs` continua sendo a
  trilha canônica de auditoria. **Não existe segunda trilha de auditoria**: os endpoints
  administrativos leem as três fontes, e `log_events` não recebe cópias de eventos de segurança ou
  auditoria.
- As duas trilhas canônicas foram estendidas de forma aditiva com `ip`, `ip_hash`, `request_id`,
  `endpoint`, `user_agent` e `result`. A migração é anulável e não faz backfill obrigatório.
- `audit_logs` recebeu um gatilho PostgreSQL que rejeita `UPDATE` e `DELETE`. A única exceção é
  a integridade referencial: `ON DELETE SET NULL` pode anular `actor_user_id` e/ou
  `organization_id` (sem tocar em nenhuma outra coluna). Correções de conteúdo continuam sendo
  novos eventos compensatórios.

### 2. Categorias, níveis e campos

Categorias de `log_events`: `http`, `app`, `security`, `audit`, `job`, `client`. Nesta fase o
serviço grava `http`, `app` e `job`; `security` e `audit` são categorias reservadas para consulta
das trilhas canônicas pelo mesmo contrato. `client` fica reservado à Fase 3.

Níveis: `debug`, `info`, `warn`, `error`, `fatal`.

Campos: `id`, `occurred_at` (UTC), `level`, `category`, `module`, `request_id`, `correlation_id`,
`user_id` (FK opcional), `ip` (até 45 caracteres, IPv4/IPv6), `ip_hash`, `user_agent` (512),
`endpoint` (template da rota; sem query string), `status`, `duration_ms`, `message` (2 KB),
`error_code`, `stack` (16 KB, sanitizado) e `metadata` JSONB (8 KB).

Índices: BRIN em `occurred_at`; btree em `(level, occurred_at)`, `(category, occurred_at)`,
`request_id`, `(user_id, occurred_at)`, `(ip_hash, occurred_at)` e `(status, occurred_at)`.
Paginação por cursor `(occurred_at, id)`.

### 3. Redação obrigatória

Antes de qualquer persistência:

- chaves que contenham `password`, `senha`, `token`, `access_token`, `refresh_token`,
  `authorization`, `cookie`, `set-cookie`, `otp`, `code`, `cpf`, `card`, `cvv`, `pix`, `secret` ou
  `api_key` viram `[redacted]` (exceto chaves explicitamente já mascaradas, como `cpf_masked`);
- texto livre tem `Bearer …`, JWT, e-mail (`p***@dominio`), CPF e telefone mascarados;
- corpo de requisição e de resposta **nunca** é gravado por padrão;
- limites: metadata 8 KB, mensagem 2 KB, user-agent 512, stack 16 KB.

### 4. Escrita, amostragem e fallback

- Eventos operacionais usam fila `asyncio` limitada (`JOGA_LOG_ASYNC_QUEUE_SIZE`, padrão
  10.000), lote de 100 a cada 1 s e flush no shutdown.
- Se a fila enche ou o banco falha, o evento sanitizado vai para stdout
  (`log_events_fallback`) e os contadores `dropped`/`failed_batches` aumentam. A requisição HTTP
  nunca falha por causa do log.
- Amostragem apenas de 2xx bem-sucedidos (`JOGA_LOG_HTTP_SUCCESS_SAMPLE_RATE`, padrão 10%).
  4xx, 5xx, requisições lentas (> 1 s) e erros são **sempre** gravados.
- Segurança e auditoria são síncronas, transacionais e **nunca amostradas**.

### 5. IP completo × hash

- `ip_hash` (HMAC com `JOGA_PHONE_HASH_SECRET`) é a chave de correlação estável.
- `ip` completo é necessário para investigação de abuso e só é exposto a `platform_admin`.
- Listagens e exportações mascaram o IP (`203.0.113.•`) por padrão. O detalhe do evento e a
  consulta por IP retornam o valor completo. Exportação com `full_ip=true` é possível e auditada.
- O IP real vem exclusivamente de `request.client.host`, resolvido pelo Caddy (SEC-002):
  `trusted_proxies static private_ranges`, `client_ip_headers CF-Connecting-IP`,
  `X-Forwarded-For` reescrito e uvicorn com `--forwarded-allow-ips 127.0.0.1`. Headers
  `X-Forwarded-For`, `CF-Connecting-IP` e `True-Client-IP` enviados pelo cliente são ignorados.
- Retenção do IP em claro: 30 dias em `log_events` e 180 dias em `security_events`; depois disso,
  resta apenas o hash enquanto a trilha existir. `audit_logs` não é purgado por padrão. Em
  particular, o IP **consultado** em uma investigação fica registrado nos filtros do evento de
  auditoria (`observability.query`/`observability.export`), e o IP de origem do administrador fica
  nas colunas `ip`/`ip_hash` de `audit_logs`; ambos seguem a retenção da auditoria, por decisão
  administrativa, e o acesso continua restrito ao admin de plataforma.

### 6. Papéis e permissões

A separação nesta fase é garantida pela dependência `require_platform_admin` (allowlist
`JOGA_PLATFORM_ADMINS`) e por testes negativos. O papel de moderação **não** é promovido a
administrador de plataforma; ser `ADMIN` em `moderation_operators` também não concede
observabilidade.

| Papel | Moderação (denúncias, conteúdo, ações) | Observabilidade (logs, IP, stack, auditoria, exportação) | Gestão de usuários administrativos |
| --- | --- | --- | --- |
| **Jogador** | não | não | não |
| **Moderador** (`ModerationOperator.role = MODERATOR`) | sim: fila de denúncias, conteúdo denunciado e ações de moderação (ocultar mensagem, advertir, suspender conforme o fluxo atual) | **não** | não |
| **Operador/organizador** (`OWNER`/`ADMIN` da organização) | não, salvo fluxo próprio da organização | **não** | não |
| **Admin de plataforma** (`JOGA_PLATFORM_ADMINS`) | sim, por definição (ADR 0066) | sim: único papel com IP completo, stack, auditoria e exportação | sim (rotas `/admin/users`) |

- Operador/organizador acessa apenas dados da própria organização/quadras; não vê logs, IP ou
  auditoria de plataforma.
- O admin de plataforma é o único que acessa `/api/v1/admin/observability/*`; toda consulta e
  exportação é auditada com filtros e quantidade.
- **O step-up do admin (SEC-003) ainda não existe.** Quando existir, será exigido nas ações
  destrutivas e no acesso a IP/logs. Até lá, a proteção é: allowlist de `platform_admin`, rate
  limit, mascaramento de IP em listas e auditoria obrigatória.
- **Pendência de modelo:** o sistema atual distingue moderação (`moderation_operators`,
  `MODERATOR`/`ADMIN`, e `JOGA_MODERATION_ADMIN_USER_IDS`) de administração de plataforma
  (`JOGA_PLATFORM_ADMINS`), mas não possui um RBAC dedicado e unificado. A fila proposta é criar
  esse RBAC (papéis e permissões explícitos) antes de ampliar o painel; nesta fase o teste
  negativo usa `ModerationOperator(role="MODERATOR")`, o papel disponível mais próximo, e exige
  `403` em todas as rotas de observabilidade.

### 7. Permissões, auditoria de consulta e step-up

- Todos os endpoints `/api/v1/admin/observability/*` exigem a mesma dependência de
  `platform_admin` que protege `/admin/*`. Operador de organização, mesmo `OWNER`, **não** acessa.
- Limite de 60 consultas/minuto por administrador; o contador vive em `rate_limit_counters`.
- **O step-up do admin (SEC-003) ainda não existe.** Por isso, nesta fase:

  - o acesso é exclusivo do admin de plataforma;
  - **toda** consulta gera `observability.query` e **toda** exportação gera
    `observability.export` em `audit_logs`, com filtros (incluindo IP/usuário), quantidade e
    indicação de truncamento;
  - a Fase 2 deve exibir esses eventos e pode adicionar reautenticação quando SEC-003 existir.

### 8. Retenção e operação

- `log_events`: `JOGA_LOG_RETENTION_DAYS` (30).
- `security_events`: `JOGA_LOG_SECURITY_RETENTION_DAYS` (180).
- `audit_logs`: sem expiração automática; retenção é decisão administrativa separada.
- `scripts/purge_observability.py` remove apenas as duas primeiras faixas, aceita `--dry-run` e
  registra o job em `log_events`.
- O painel deve considerar a retenção do Render/Supabase: o expurgo local não substitui a
  política de retenção de backup do provedor.

## Consequências

- Consultas administrativas ficam mais caras (três fontes para atividade por usuário), mas sem
  duplicar trilhas nem arriscar divergência entre auditoria e segurança.
- A tabela operacional cresce rápido; BRIN + retenção de 30 dias + amostragem mantêm o custo
  controlado.
- O IP completo é dado pessoal de acesso restrito; a consulta é auditada e a listagem é mascarada.
- A amostragem de 2xx reduz volume, mas séries estatísticas de sucesso são aproximadas; erros e
  eventos de segurança são completos.
- Cada 401/403/429 gera um evento de segurança síncrono; um flood de credenciais inválidas amplia
  a escrita. O rate limiting da borda/API continua sendo o controle primário.

## Fora do escopo (fases seguintes)

- **Fase 2:** painel web consumindo os endpoints, visualização de stack/exportação, alertas
  automáticos, step-up (SEC-003).
- **Fase 3:** captura de erro e telemetria do app mobile (`client`).
- Alertas automáticos, correlação distribuída completa, Kafka/Celery, Redis como autoridade e
  retenção gerenciada pelo provedor.
