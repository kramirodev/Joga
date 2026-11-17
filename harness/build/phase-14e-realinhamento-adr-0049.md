# Fase 14E — Realinhamento da ADR 0049

**Status:** em andamento. Etapas 0–6 concluídas; 6b (vagas por passe/grátis/admin), 7 (inversão de leitura), 8 (conformidade) e 9 (aposentadoria) pendentes.
**Depende de:** 14, 14D congeladas e estabilização do repositório.
**Bloqueia:** 14B, 15, 19A e qualquer dinheiro real.
**Referência:** `docs/ADR/0049-modelo-tributario-da-intermediacao.md`, `docs/DECISOES_BACKEND_ADR_0049.md`, `docs/DATA_MODEL.md`.

## Objetivo

Fazer o código refletir a decisão vigente: crédito em reais como substância, ticket como unidade de exibição 1:1, preço em duas linhas, ledger de dupla entrada, CPF, NFS-e placeholder e custódia B→C.

## Escopo

- Saldo e ledger em centavos/reais como fonte da verdade.
- Ticket como unidade de exibição; saldo em reais não exibido como carteira.
- Persistir `venue_price_cents`, `fee_cents`, `fee_percent_applied`, `total_cents` por reserva.
- Integrar `LedgerService` em reserva, compra, passe, reembolso e repasse.
- Migrar lotes existentes pelo preço unitário pago; crédito comprado sem expiração.
- Passe com período mensal não acumulável e fora do escrow.
- CPF cifrado e NFS-e como intenção/documento por reserva.
- Remover o uso dos ledgers legados como fonte principal.
- Corrigir os P0 financeiros identificados na auditoria de 16/11 (T3 sem devolução, Pix + crédito, repasse após reembolso, `EXPIRED`, idempotência de compra).

## Fora do escopo

- Escolher fornecedor de escrow.
- Dinheiro real.
- Fixar alíquota, taxa final ou NFS-e operacional.
- Implementar UI nova fora do necessário para exibir preço/tickets.

## Plano

1. **Red:** testes que falham para saldo em reais, preço em duas linhas, ticket 1:1, ausência de expiração, devolução no T3 e bloqueio de cobrança dupla.
2. **Green:** migrations aditivas, serviços e ledger; migração de lotes idempotente.
3. **Refactor:** remover caminhos legados, sem manter dois saldos.
4. **Verify:** migrations do zero, `alembic check`, testes de concorrência e conciliação, revisão de dados.

## Critérios observáveis

- Nenhuma obrigação financeira fora do ledger em reais.
- Reserva guarda preço/taxa/percentual/total.
- Ticket exibido é 1:1 e o saldo em reais não é exibido.
- Preço do espaço, taxa e tabela de conversão aparecem antes da confirmação.
- NFS-e registrada por reserva.
- Crédito comprado não expira; passe tem período.
- T3 devolve crédito; Pix pago impede quitação por crédito.
- Reembolso bloqueia/reverte repasse.
- Migração de lotes idempotente e auditável.

## Comandos reais

```powershell
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy app
```

## Condição de parada

A fase termina quando os critérios acima estão verdes, a documentação está reconciliada e o usuário autoriza o commit/merge. Não iniciar 14B/15 automaticamente.
