# Fase 14D.2 — Fornecedor e chave de repasse

**Status:** implementado localmente em 2026-11-12.
**Branch:** `main`

## Fontes e contexto

- `PLANS.md` Fase 14D (fatia 2)
- ADR 0042 §1 (o estabelecimento é fornecedor, não recebedor de marketplace)
- ADR 0040 (repasse em `starts_at + 2h`)
- Fase 12A (quadras e estabelecimentos)

## Objetivo

Saber **para onde pagar**. O ingresso é pré-pago e o JOGA precisa repassar à quadra;
sem destino de repasse validado, reserva paga não pode abrir.

## Decisões desta fatia

| Tema | Decisão | Motivo |
|---|---|---|
| Titularidade | CNPJ do estabelecimento, com dígitos verificadores | O repasse vai para o próprio CNPJ; chave de terceiro é recusada na validação |
| Chave Pix | Tipos `cnpj`, `email`, `phone` e `random` | Cobre as quatro formas do Pix |
| Estado | `payout_status` em `pending`, `active` ou `blocked` | `active` só depois de definir CNPJ e chave válidos |
| Ativação | Automática ao definir CNPJ e chave | O KYC real é contratual, não desta fatia |
| Exibição | Chave **mascarada** na API | Evita vazar chave Pix em resposta e em log |
| Autorização | `financial:manage` | Operador não altera destino de dinheiro |

## Implementação

- `organizations`: `legal_document`, `pix_key_type`, `pix_key`, `payout_status` e `payout_verified_at`.
- `OrganizationService.set_payout` — normaliza, valida e audita (`organization.payout_updated`).
- `normalize_cnpj`, `normalize_pix_key`, `mask_pix_key`, `payout_ready`.
- `PUT /api/v1/organizations/{id}/payout`.
- `OrganizationView` passa a expor `payout_ready`, `payout_status`, `pix_key_type` e `pix_key_masked`.
- Migração `c2d3e4f50618` com as duas constraints de coerência.

## Testes

`tests/test_payout.py`:

- CNPJ válido + e-mail ativa o repasse e devolve chave mascarada.
- CNPJ formatado (`11.222.333/0001-81`) é aceito.
- CNPJ com dígito errado retorna `422 invalid_input`.
- E-mail inválido é rejeitado.
- `OPERATOR` recebe `403 forbidden`.
- Organização nova nasce `pending` e sem chave.

Suíte completa, `ruff`, `mypy --strict` e `alembic check` verdes; migração testada em
upgrade, downgrade e novo upgrade.

## Limitações conhecidas

1. **Ativação automática.** Não há verificação de titularidade junto ao banco. No piloto, a
   conferência é manual; KYC real entra com o contrato do PSP.
2. **Sem evento de expiração.** Trocar de chave sobrescreve a anterior sem histórico próprio;
   o rastro fica na auditoria, não em tabela dedicada.
3. **O portão ainda não é chamado.** `payout_ready` é exposto, mas a abertura de reserva paga
   só vai consultá-lo na fatia 14D.3/14D.4.
4. **Sem contrato com teto por faixa.** O teto hoje é o da própria faixa de preço; a cláusula
   contratual com aviso de 30 dias continua pendente.

## Próxima fatia

**14D.3 — Confirmação sem cobrança:** T3 passa a ser janela de confirmação e o ingresso é
consumido na confirmação, sem cobrança por participante.
