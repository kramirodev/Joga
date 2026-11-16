# Fase 14B — Hardening do Mercado Pago

**Status:** não iniciada.
**Depende de:** 14E, contrato e credenciais reais, revisão jurídica/fiscal.
**Bloqueia:** 15 e 19B.

## Objetivo

Validar e endurecer o Mercado Pago como PSP do protótipo, sem prometer dinheiro real antes dos pareceres.

## Escopo

- Validação com credenciais reais e URL HTTPS pública.
- Reembolso real e reembolso parcial.
- MED/chargeback: bloqueio de repasse, receivable contra o fornecedor e registro no ledger.
- Conciliação externa entre PSP, ledger e extrato.
- Retry/replay de webhook com hash do corpo e rollback.
- Métricas e alertas de pagamento.
- Runbook operacional.

## Fora do escopo

- Escolher escrow/conta vinculada.
- Ativar dinheiro real sem parecer.
- Implementar NFS-e operacional.
- Split.

## Critérios observáveis

- Pagamento, reembolso e repasse conciliam com o extrato do PSP.
- Replay não duplica e corpo divergente é rejeitado.
- MED/chargeback bloqueia repasse e não toca o saldo do jogador.
- Reembolso parcial funciona e é idempotente.
- Alertas e runbook existem.
- Nenhuma operação exige intervenção manual não auditada.

## Condição de parada

A fase termina com evidências de sandbox/live controlado, conciliação reproduzível e autorização explícita para o próximo passo.
