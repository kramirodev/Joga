# ADR 0024 — Retenção provisória dos dados de resultado da Fase 7

- **Status:** Aprovado provisoriamente em 2026-11-06 para desenvolvimento e piloto; sujeito à revisão LGPD das Fases 10 e 19.
- **Data:** 2026-11-06
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `PLANS.md` Fase 7; `docs/ADR/0023-fase-7-resultados-e-disputas.md`; `docs/DATA_MODEL.md`; `docs/RUNBOOK.md`; `harness/build/phase-07-resultados-e-disputas.md`.

## Contexto

A Fase 7 passou a armazenar relatos, confirmações de capitão, evidências textuais, análises internas, revisões, decisões humanas e contadores de rate limiting. Os documentos de produto mantêm a política definitiva de retenção como pendência de LGPD, a ser fechada nas Fases 10 e 19.

Sem um prazo operacional, os dados cresceriam indefinidamente e a evidência textual — que pode conter dado pessoal — ficaria guardada sem finalidade delimitada. Este ADR fixa uma política **provisória**, configurável e sem agendamento automático, para permitir desenvolvimento e piloto controlado.

## Decisão

| Dado | Retenção provisória | Referência de tempo |
|---|---:|---|
| `rate_limit_counters` | 24 horas | `window_start` |
| `match_dispute_evidence` | 12 meses | `match_disputes.closed_at` |
| `match_result_reports` | 24 meses | encerramento da partida (`finalized_at` ou `updated_at`) |
| `match_result_captain_confirmations` | 24 meses | encerramento da partida |
| `match_result_decisions` | 24 meses | `resolved_at` da revisão ou `created_at` |
| `match_result_reviews` | 24 meses | `resolved_at` da revisão ou `created_at` |
| `match_result_analyses` | 24 meses | encerramento da partida |
| `matches` e `match_result_rounds` | mantidos | histórico competitivo; fora desta limpeza |

Regras de segurança:

- só são removidos dados de partidas `FINALIZED` ou `VOIDED`;
- partidas `IN_PROGRESS`, `RESULT_PENDING` ou `DISPUTED` são preservadas;
- revisões só são removidas quando `RESOLVED` ou `CANCELLED`;
- decisões são removidas antes das revisões, respeitando as FKs;
- a limpeza é manual, por CLI, com `--dry-run`;
- a execução não é agendada automaticamente nesta fase.

## Implementação

- `backend/app/modules/results/cleanup.py`: regra de limpeza e contagem por categoria.
- `backend/scripts/cleanup_results.py`: CLI com `--report-days`, `--evidence-days`, `--decision-days`, `--rate-limit-hours` e `--dry-run`.
- A limpeza é uma exceção controlada à regra append-only: ela remove apenas registros fora do prazo aprovado, nunca altera o conteúdo de registros mantidos.

## Consequências

- Os dados de resultado passam a ter ciclo de vida explícito.
- A política continua provisória: os valores podem ser ajustados por revisão de produto/LGPD sem alterar o schema.
- A CLI deve ser executada com cautela em ambientes compartilhados e sempre começar por `--dry-run`.
- A revisão LGPD das Fases 10/19 pode substituir este ADR por uma política definitiva, incluindo base legal, prazos e processo de eliminação.

## O que este ADR não decide

- Não define a política definitiva de retenção para produção.
- Não define a base legal de cada tratamento.
- Não define agendamento, monitoramento ou alerta da limpeza.
- Não autoriza apagar dados de partidas em andamento ou de revisões pendentes.
