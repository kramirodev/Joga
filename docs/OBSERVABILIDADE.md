# Observabilidade — guia operacional (Fase 1)

Referência de decisão: `docs/ADR/0078-observabilidade-logs-auditoria-e-retencao-de-ip.md`.
Esta fase entrega backend; o painel é Fase 2 e a telemetria do app é Fase 3.

## Visão geral

| Trilha | Tabela | Conteúdo | Quem lê |
| --- | --- | --- | --- |
| Operacional | `log_events` | HTTP, aplicação, jobs e (Fase 3) cliente | `platform_admin` |
| Segurança | `security_events` | 401/403/429, login/OTP/passkey, sessão | `platform_admin` |
| Auditoria | `audit_logs` | Ações administrativas e consultas/exportações | `platform_admin` |

`log_events` **não** duplica segurança/auditoria. As consultas administrativas leem as três fontes
quando faz sentido (atividade por usuário).

## Como adicionar um evento

Use o serviço central em `app/modules/observability/service.py`:

```python
from app.modules.observability.service import log_event, log_exception, log_job, log_security

# Evento de aplicação (assíncrono, sanitizado, sem PII)
log_event(
    "warn",
    "app",
    "pagamento conciliado com divergência",
    module="payments.reconcile",
    details={"charge_id": str(charge_id), "delta_cents": 100},
)

# Erro com stack sanitizado (nunca devolvido ao cliente)
try:
    ...
except Exception as exc:
    log_exception(exc, category="app", module="payments.reconcile")

# Job/worker: grava na transação corrente e o chamador commita
log_job(session, job="email.delivery", status="finished", duration_ms=120, details={"sent": 4})

# Segurança/auditoria: trilhas canônicas, síncronas e não amostradas
log_security(session, "otp.verification_failed", user_id=user.id)
```

Regras:

- não passe corpo de requisição/resposta, senha, token, cookie, OTP, CPF ou e-mail;
- `metadata` é limitado a 8 KB e `message` a 2 KB;
- o serviço redige chaves sensíveis e mascara PII mesmo que o chamador erre;
- jobs de longa duração devem registrar `started` e `finished`/`failed` (e-mail, notificações,
  resultados/ratings, temporada);
- o worker de push registra um evento por ciclo (`finished`/`failed`) para não inflar a trilha.

## Níveis e categorias

- Níveis: `debug`, `info`, `warn`, `error`, `fatal`.
- Categorias: `http`, `app`, `security`, `audit`, `job`, `client`.
- HTTP: 2xx amostrado (`JOGA_LOG_HTTP_SUCCESS_SAMPLE_RATE`, padrão 10%); 4xx, 5xx, lentas
  (> 1 s) e exceções sempre gravados.
- 401/403/429 também geram `security_events` (`http.unauthorized`, `http.forbidden`,
  `http.rate_limited`) com IP, hash, `request_id` e endpoint.
- O log de acesso completo continua em stdout (`joga.http`); o banco guarda o recorte acima.
- Health checks (`/api/v1/health/live` e `/ready`) não são persistidos.

## Variáveis de ambiente

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `JOGA_OBSERVABILITY_ENABLED` | `true` | Liga a persistência em `log_events`; stdout continua independente |
| `JOGA_LOG_LEVEL` | `INFO` | Nível do logging Python; valor inválido falha o boot |
| `JOGA_LOG_HTTP_SUCCESS_SAMPLE_RATE` | `0.1` | Amostragem de 2xx; fora de `[0, 1]` falha o boot |
| `JOGA_LOG_RETENTION_DAYS` | `30` | Retenção de `log_events` (1–730) |
| `JOGA_LOG_SECURITY_RETENTION_DAYS` | `180` | Retenção de `security_events` (30–3650) |
| `JOGA_LOG_ASYNC_QUEUE_SIZE` | `10000` | Tamanho da fila assíncrona (100–100000) |
| `JOGA_LOG_STACKTRACES` | `true` | Persiste stack sanitizado de erros |
| `JOGA_LOG_MAX_EXPORT_ROWS` | `20000` | Teto de linhas por exportação (100–100000) |

`JOGA_LOG_LEVEL` aceita `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL`. Os limites são
validados no boot; não há degradação silenciosa.

## Proxy confiável e IP real

O IP completo só é registrado se for um IP válido em `request.client.host`, que é resolvido na
borda (SEC-002):

- Caddy usa `trusted_proxies static private_ranges` + `trusted_proxies_strict`;
- a fonte é `CF-Connecting-IP`, definido pelo Cloudflare;
- o Caddy reescreve `X-Forwarded-For` com um único IP e remove `CF-Connecting-IP`/`True-Client-IP`;
- uvicorn roda com `--proxy-headers --forwarded-allow-ips 127.0.0.1`.

Nunca amplie `trusted_proxies` para faixas públicas nem leia `X-Forwarded-For` do cliente como
verdade. Se o peer imediato não for privado, o IP cai para o peer do Render: o hash continua
funcionando, mas deixa de distinguir clientes.

## Papéis e permissões

| Papel | O que pode consultar |
| --- | --- |
| Jogador | nada de logs, auditoria ou IP |
| Moderador (`MODERATOR`) | fila de denúncias, conteúdo denunciado e ações de moderação; **nada** em `/admin/observability/*` |
| Operador/organizador (`OWNER`/`ADMIN` da organização) | apenas dados da própria organização/quadras; **nada** de logs, IP ou auditoria |
| Admin de plataforma (`JOGA_PLATFORM_ADMINS`) | tudo em `/admin/observability/*`: logs, IP completo, stack, auditoria e exportação |

O papel de moderação não implica administração de plataforma, e `ADMIN` em
`moderation_operators` **não** libera observabilidade. A única dependência que autoriza as rotas
abaixo é a de `platform_admin`. Toda consulta/exportação é auditada. O step-up (SEC-003) ainda
não existe; quando entrar, será exigido no acesso a IP/logs e nas ações destrutivas. O modelo
atual não tem RBAC unificado — a pendência e a fila estão no ADR 0078, §6.

## Endpoints administrativos

Prefixo: `/api/v1/admin/observability`. Todos exigem `platform_admin` (allowlist
`JOGA_PLATFORM_ADMINS`) e são limitados a 60 consultas/minuto por administrador.

### `GET /summary?window=24h|7d`

Retorna contagens da janela atual e da anterior (mesmo tamanho):

```json
{
  "window": "24h",
  "current": {
    "from_at": "...", "to_at": "...", "total_events": 1234,
    "by_level": [{"level": "error", "count": 3}],
    "by_category": [{"category": "http", "count": 1000}],
    "http": {"requests": 1000, "status_4xx": 40, "status_5xx": 3,
             "slow_requests": 7, "avg_duration_ms": 42.5},
    "auth": {"unauthorized": 10, "forbidden": 1, "rate_limited": 2, "failed_logins": 4},
    "jobs": {"started": 12, "finished": 11, "failed": 1},
    "audit_events": 20, "security_events": 15,
    "suspicious_users": [{"user_id": "...", "events": 8, "security_events": 2,
                          "last_seen_at": "..."}]
  },
  "previous": { "...": "mesmo formato" }
}
```

“Usuários suspeitos” = usuários com eventos `warn/error/fatal` ou falhas de segurança na janela,
ordenados por volume e recência (top 10).

### `GET /events`

Filtros (todos opcionais): `from`, `to` (ISO 8601), `level`, `category`, `user_id`, `ip`,
`endpoint`, `status`, `request_id`, `correlation_id`, `q`, `cursor`, `limit` (1–100, padrão 50).

- Sem `category`, lê `log_events` (trilha operacional).
- `category=security` lê `security_events`; `category=audit` lê `audit_logs`.
- Filtros que não existem na trilha canônica (ex.: `status`) resultam em conjunto vazio; `level`
  em segurança/auditoria é derivado de `result`.
- `q` busca em mensagem/endpoint/error_code (operacional) ou tipo/ação/motivo (canônicas), com
  limite de 100 caracteres.
- IP aparece mascarado (`203.0.113.•`).

```json
{"events": [{"id": "...", "occurred_at": "...", "level": "info", "category": "http",
             "source": "log_events", "module": "http", "request_id": "...",
             "correlation_id": "...", "user_id": null, "ip": "203.0.113.•",
             "ip_masked": true, "user_agent": "...", "endpoint": "/api/v1/x",
             "status": 200, "duration_ms": 42, "message": "GET /api/v1/x 200",
             "error_code": null, "details": {"method": "GET", "slow": false}}],
 "next_cursor": "..."}
```

### `GET /events/{id}`

Detalhe com **IP completo** e `stack` (quando houver). Procura em `log_events`,
`security_events` e `audit_logs`; `source` informa a origem. `404 event_not_found` se não existir.

### `GET /users/{user_id}/activity?from=&to=&category=&cursor=&limit=`

Une `log_events` (user_id), `security_events` (user_id) e `audit_logs` (actor_user_id), mais
recentes primeiro, com cursor. IP mascarado.

```json
{"user_id": "...", "events": ["mesmo formato de EventView"], "next_cursor": null}
```

### `GET /ips/{ip}`

Aceita IPv4/IPv6. Retorna o IP **completo**, hash, primeira/última ocorrência, totais, número de
falhas de login, usuários associados (até 20) e até 100 eventos recentes (IP completo).

```json
{"ip": "203.0.113.10", "ip_hash": "...", "first_seen_at": "...", "last_seen_at": "...",
 "total_events": 10, "security_events": 2, "failed_logins": 1,
 "users": [{"user_id": "...", "events": 8, "last_seen_at": "..."}],
 "events": ["..."]}
```

### `GET /export?format=csv|json`

Aceita os mesmos filtros de `/events`, mais `full_ip` (padrão `false`). Teto:
`JOGA_LOG_MAX_EXPORT_ROWS`. Resposta em streaming com:

- `Content-Disposition: attachment`;
- `X-Export-Rows`: linhas efetivamente exportadas;
- `X-Export-Truncated`: `true` quando o total excede o teto.

CSV tem cabeçalho `id,occurred_at,level,category,source,module,request_id,correlation_id,user_id,ip,user_agent,endpoint,status,duration_ms,message,error_code`.
JSON é um array de objetos no formato de `EventView`. IP mascarado por padrão.

### Auditoria das consultas

Toda consulta gera `observability.query`; toda exportação gera `observability.export`. O evento
contém `filters` (datas em ISO, UUID em texto), `count`, `has_ip_filter`, `has_user_filter` e, na
exportação, `format`, `full_ip`, `truncated` e `max_rows`. O IP de origem da consulta também é
gravado no próprio `audit_logs` (`ip`, `ip_hash`, `request_id`, `endpoint`, `user_agent`).

## Como investigar

1. **Um erro específico do cliente**: peça o `X-Request-ID` da resposta e consulte
   `GET /events?request_id=...`. O mesmo ID aparece em `security_events` e `audit_logs`.
2. **Um usuário**: `GET /users/{uuid}/activity`, refinando por `category` e período. Falhas de
   login aparecem como `security`.
3. **Um IP abusivo**: `GET /ips/{ip}` mostra usuários, falhas de login e eventos recentes. A
   consulta fica auditada com `has_ip_filter=true`.
4. **Pico de 5xx**: `GET /summary?window=24h` e depois
   `GET /events?level=error&category=http&status=500`.
5. **Job falhando**: `GET /events?category=job&level=error`; detalhe mostra `stack`.
6. **Exportação para análise**: use `format=csv` com filtros; confirme `X-Export-Truncated`.

## Retenção e expurgo

```bash
python -m scripts.purge_observability --dry-run
python -m scripts.purge_observability
```

- `log_events`: `JOGA_LOG_RETENTION_DAYS` (30).
- `security_events`: `JOGA_LOG_SECURITY_RETENTION_DAYS` (180).
- `audit_logs`: **não** é apagado; o gatilho `trg_audit_logs_append_only` bloqueia
  `UPDATE`/`DELETE`. Exceção única: `ON DELETE SET NULL` de `actor_user_id`/`organization_id`
  quando o usuário ou a organização é removido fisicamente; nenhuma outra coluna muda e o evento
  permanece.
- O script registra um evento `job` com as contagens.

## Limitações desta fase

- **Step-up do admin (SEC-003) não existe.** O acesso é exclusivo do `platform_admin` e toda
  consulta/exportação é auditada. A Fase 2 deve considerar reautenticação quando SEC-003 entrar.
- Sem alerta automático, sem detecção de anomalia e sem correlação distribuída (apenas
  `request_id`/`correlation_id`).
- A amostragem de 2xx torna métricas de sucesso aproximadas.
- O teto de exportação e a retenção são locais; backups e retenção do Render/Supabase seguem
  política separada.
- `log_events` pode perder eventos se a fila encher ou o banco cair; nesse caso há fallback em
  stdout e contador de perda. Segurança/auditoria não são amostradas, mas também caem para stdout
  se o banco estiver indisponível.
- A captura de erro do app mobile (`client`) é Fase 3.
- Cada 401/403/429 vira um evento de segurança. Um flood de tokens inválidos pode gerar volume de
  escrita; o controle primário é o rate limiting da borda/API. Monitore o crescimento de
  `security_events` e ajuste limites antes de abrir tráfego hostil.
