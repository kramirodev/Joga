# Fase 10 — Hardening e piloto (núcleo esportivo)

**Status:** 10A/10B (hardening backend local) concluídos em 2026-11-06; piloto real pendente de infraestrutura, provedores, orçamento e LGPD
**Branch:** `feat/10-hardening-piloto`

## Objetivo

Preparar o núcleo esportivo para um piloto controlado: documentar ameaças, reduzir superfície de abuso, melhorar observabilidade, validar backup/restauração, executar carga local e registrar limites operacionais. O piloto com usuários reais depende de infraestrutura, telefone e decisões de produto/LGPD.

## Escopo 10A (sem celular)

- Threat model atualizado do núcleo esportivo.
- Request ID, logs de acesso sem PII e headers de segurança básicos.
- Script de carga local reproduzível.
- Backup e restauração testados em PostgreSQL local.
- Revisão de autorização e idempotência existentes, com testes negativos adicionais quando necessário.
- Consolidação das políticas provisórias de retenção e dos limites de custo.
- Runbook de piloto, alertas e rollback.

## Fora do escopo imediato

- Testes em aparelho físico, App Store/Play Store e distribuição.
- SMS/mapas/push reais e respectivos custos.
- Revisão jurídica/LGPD definitiva.
- Redis/fan-out multi-processo e múltiplas instâncias.
- Painel administrativo, reservas, pagamentos e clãs.

## Entregáveis

### Observabilidade

- `X-Request-ID` em todas as respostas HTTP; eco do valor recebido quando válido.
- Log de acesso com método, rota, status, duração e request ID, sem query string, corpo, tokens ou telefone.
- Headers básicos: `X-Content-Type-Options`, `Referrer-Policy`, `Cache-Control: no-store` para respostas da API.
- Health live/ready já existentes; documentar uso em piloto.

### Carga

- `backend/scripts/load_test.py` com concorrência, número de requisições, endpoint, token opcional e percentis.
- Rodada local documentada com resultados e limitações.

### Backup e restauração

- Procedimento `pg_dump`/`pg_restore` no PostgreSQL local.
- Teste de restauração em banco temporário, validação de `alembic_version` e contagens mínimas.
- Registro no build-log e runbook.

### Segurança

- `docs/THREAT_MODEL.md` com ativos, atores, ameaças, controles e riscos residuais.
- Revisão de BOLA/autorização por recurso, sessão/WebSocket, OTP, chat, convites, rating e Outbox.
- Testes adicionais para headers, request ID e falhas de autorização quando houver lacuna.

### Piloto

- Checklist de go/no-go, limites de custo, alertas mínimos e rollback.
- Pendências explícitas: aparelho, provedores reais, LGPD e infraestrutura.

## Critérios de aceite 10A

- [x] Threat model registrado e revisado.
- [x] Request ID/logs/headers cobertos por testes.
- [x] Carga local executada e documentada.
- [x] Backup e restauração testados em banco temporário.
- [ ] Nenhuma vulnerabilidade crítica/alta conhecida em aberto sem bloqueio explícito — **parcial:** revisão manual feita; auditoria automatizada de CVE e pentest ainda pendentes.
- [ ] Limites de custo e checklist de piloto documentados — **parcial:** custo externo continua bloqueado; orçamento de piloto precisa de decisão.
- [x] Retenção provisória consolidada no runbook.

## Implementação 10A

- **Observabilidade:** `app/core/observability.py` com `X-Request-ID` seguro, log `joga.http` sem query string/corpo e headers básicos; testes em `test_observability.py`.
- **Carga:** `scripts/load_test.py`; 200 requisições em `/api/v1/health/live` com concorrência 20 → 0 falhas, p50 37,9 ms, p95 146,8 ms, p99 155,4 ms. 100 requisições em `/api/v1/sports` → 0 falhas, p50 41,2 ms, p95 79,2 ms.
- **Backup/restore:** `pg_dump` do banco local e `pg_restore` em `joga_restore_test`; versão `b4e8d1f6c752`, 13 usuários e 1 partida restaurados; banco temporário removido.
- **Segurança:** `docs/THREAT_MODEL.md` com ativos, ameaças, controles e riscos residuais.
- **Testes:** **287 passed, 23 skipped** sem PostgreSQL e **310 passed** com PostgreSQL; `ruff`, `ruff format`, `mypy` e `alembic check` passam.
- **Smoke Android 14:** moto g24; login, competitivo, chat, WebSocket ao vivo/reconnect, amizade e convite validados no aparelho. APK de debug exibiu aviso de compatibilidade do Android, mas executou.
- **Bloqueios para piloto real:** provedores de SMS/push/mapas, orçamento, LGPD/jurídico e infraestrutura de produção.
- **10B — limite de payload:** `JOGA_MAX_REQUEST_BODY_BYTES` (1 MB) retorna `413 payload_too_large`; testado.
- **10B — auditoria de dependências:** `pip-audit -r requirements.lock` sem vulnerabilidades conhecidas; `pnpm audit --prod` encontrou 2 moderadas transitivas em `glob`/`minimatch` via Expo CLI. Aceitas temporariamente como ferramenta de build; correção depende de atualização do Expo.
- **10B — carga autenticada:** 100 requisições em `/api/v1/matches`, concorrência 10, 0 falhas; p50 98,3 ms, p95 155,0 ms, p99 165,7 ms.

## Condição de parada

Encerrar 10A com evidências locais. Não iniciar piloto real, Fase 11 ou ações externas sem autorização específica.

## Limites de custo e checklist de piloto

- **Custo externo nesta fase:** zero. Nenhum SMS, push, mapa, hospedagem ou compra de crédito foi acionado.
- **Antes do piloto:** definir orçamento mensal máximo para SMS/OTP, mapas, hospedagem e armazenamento; registrar provedor e responsável.
- **Go/no-go:** restore testado; carga local aceitável; nenhuma vulnerabilidade crítica/alta aberta; alertas e responsável por incidentes definidos; LGPD/retenção revisadas; rollback documentado.
- **Rollback:** parar API/workers, restaurar backup validado, revogar segredos/tokens se houver suspeita e comunicar participantes.
- **Métricas mínimas:** erro 5xx, latência p95, fila/partidas presas, Outbox pendente, falhas de rating, conexões WebSocket e erros de push.
