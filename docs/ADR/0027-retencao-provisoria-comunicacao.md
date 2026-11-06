# ADR 0027 — Retenção provisória de comunicação e Outbox

- **Status:** Aprovado provisoriamente em 2026-11-06 para desenvolvimento e piloto; sujeito à revisão LGPD das Fases 10 e 19.
- **Data:** 2026-11-06
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0026; `docs/DATA_MODEL.md`; `docs/RUNBOOK.md`; `harness/build/phase-09-comunicacao-tempo-real.md`.

## Contexto

A Fase 9 passou a armazenar mensagens de lobby, convites, eventos de Outbox e tokens de push. Sem uma política operacional, esses dados cresceriam indefinidamente. A retenção definitiva continua sendo uma decisão de LGPD das Fases 10/19.

## Decisão

| Dado | Retenção provisória | Referência |
|---|---:|---|
| `lobby_messages` | 730 dias | `created_at` |
| `lobby_invites` | 90 dias | `responded_at` ou `created_at` para `DECLINED`/`EXPIRED`/`CANCELLED` |
| `outbox_events` | 30 dias | `dispatched_at` ou `created_at` para `DISPATCHED`/`FAILED` |
| `device_push_tokens` | 90 dias após revogação | `revoked_at` |

Regras:

- eventos `PENDING` da Outbox nunca são removidos pela limpeza;
- convites `PENDING` ou `ACCEPTED` não são removidos;
- tokens ativos não são removidos;
- a execução é manual, por CLI, com `--dry-run`;
- não há agendamento automático nesta fase.

## Implementação

- `backend/app/modules/social/cleanup.py`: regra e contagem por categoria.
- `backend/scripts/cleanup_communication.py`: CLI com prazos configuráveis e `--dry-run`.
- A limpeza é uma exceção controlada à retenção append-only, removendo apenas registros fora do prazo.

## Consequências

- Mensagens, convites, eventos e tokens passam a ter ciclo de vida explícito.
- A política é provisória e pode ser ajustada sem alterar o schema.
- A revisão LGPD das Fases 10/19 pode substituir este ADR por uma política definitiva.

## O que este ADR não decide

- Retenção definitiva, base legal ou processo de eliminação em produção.
- Agendamento, monitoramento ou alerta da limpeza.
- Remoção de eventos `PENDING` ou dados ainda necessários para entrega.
