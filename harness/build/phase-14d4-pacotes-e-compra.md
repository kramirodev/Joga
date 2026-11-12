# Fase 14D.4 — Pacotes e compra de ingressos

**Status:** implementado localmente em 2026-11-12.
**Branch:** `main`

## Fontes e contexto

- `PLANS.md` Fase 14D
- ADR 0042 §3 (escada de preço) e §2 (ingresso pré-pago)
- Fase 14D.3 (carteira e ledger)

## Objetivo

Transformar a escada de preço em produto: o jogador vê os pacotes com o preço unitário
decrescente, cria a intenção de compra e recebe os ingressos na carteira.

## Decisões desta fatia

| Tema | Decisão | Motivo |
|---|---|---|
| Catálogo | `ticket_packs` com `code`, `tickets` e `unit_price_cents` | A escada muda por decisão comercial, não por código |
| Escada semeada | 3 @ R$ 3,70 · 10 @ R$ 3,40 · 30 @ R$ 3,20 · 50 @ R$ 3,10 | ADR 0042 §3 item 7 |
| Compra | `ticket_purchases` com valor congelado | O preço da compra não muda depois de criada |
| Confirmação | Endpoint **só em ambiente local** | Dinheiro real depende da 14B e do Inter |
| Crédito | `grant` com chave `purchase:{id}` | Confirmar duas vezes não credita duas vezes |

## Implementação

- `ticket_packs` e `ticket_purchases` em `app/modules/tickets/models.py`.
- `seed_default_packs`, `list_packs`, `get_pack`, `create_purchase` e `confirm_purchase` no serviço.
- `GET /api/v1/me/tickets/packs`, `POST /api/v1/me/tickets/purchases`,
  `GET /api/v1/me/tickets/purchases/{id}` e `POST .../confirm`.
- Migração `e4f5061a2838`.

## Testes

`tests/test_ticket_purchases.py`:

- escada devolvida em ordem crescente de tamanho e decrescente de preço unitário;
- compra de pacote cria intenção com valor congelado;
- confirmação credita a carteira;
- confirmação repetida não credita duas vezes;
- pacote inexistente retorna 404;
- compra de outro jogador retorna 404.

Suíte completa, `ruff`, `mypy --strict` e `alembic check` verdes; migração testada em
upgrade, downgrade e novo upgrade.

## Limitações conhecidas

1. **Não há cobrança Pix.** A compra fica `pending` e a confirmação só existe em ambiente
   local. Ligar ao PSP é a 14B.
2. **Não há cancelamento de compra.** `cancelled` está no schema, sem fluxo.
3. **O consumo ainda não existe.** A carteira credita, mas a reserva não debita — é a
   próxima fatia e depende de uma decisão de produto: **de quem é o saldo debitado**.

## Próxima fatia

**14D.5 — Consumo na confirmação.** Precisa decidir se o débito é do saldo de **cada
participante** ou do saldo do **criador da reserva**.
