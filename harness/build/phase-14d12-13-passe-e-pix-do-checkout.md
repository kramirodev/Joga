# Fase 14D.12 + 14D.13 — Passe como assinatura e Pix no checkout

**Status:** implementado no backend em 2026-11-13.
**Depende de:** 14D.3 (carteira), 14D.4 (pacotes), 14D.8 (trilha), 14A (PSP e webhook).
**Não inclui:** UI, assinatura recorrente, Inter PJ, split e repasse.

## Problema

O passe existia apenas como bloqueio: `claim_level` recusava qualquer nível da
trilha paga com `pass_required`, sem modelo de assinatura. A compra de pacote
também não cobrava nada: `POST /me/tickets/purchases/{id}/confirm` só funcionava
em ambiente local e creditava ingressos sem PSP.

## Decisão

1. **Assinatura sem recorrência automática.** O jogador paga um Pix por
   trimestre; não há cobrança automática, token de cartão nem renovação.
2. **Quatro planos fixos** (ADR 0043 §2): 10, 20, 30 e 50 ingressos por mês, a
   R$ 3,25 por ingresso. O trimestre custa R$ 97,50, R$ 195,00, R$ 292,50 e
   R$ 487,50. O preço fica gravado na assinatura no momento da compra.
3. **Entrega mensal, não retroativa.** A primeira franquia cai na ativação; as
   seguintes vencem a cada mês, com chave de idempotência
   `pass:{subscription_id}:{month_index}`. Mês anterior à compra não é pago.
4. **Vigência de três meses a partir do pagamento.** A assinatura não é
   amarrada à virada do trimestre civil: quem compra no meio do trimestre
   recebe três franquias mensais e mantém a trilha paga enquanto estiver
   vigente. Essa é uma decisão de implementação; o produto ainda pode preferir
   vender apenas no início da temporada.
5. **A trilha paga consulta a assinatura vigente.** `claim_level` recebe
   `has_pass`; a API calcula com `has_active_pass`. Sem assinatura, continua
   `403 pass_required`.
6. **Uma única tabela de cobrança para compras.** `purchase_payments` cobre
   pacote (`ticket_pack`) e passe (`pass`), com referência polimórfica por
   `kind` + `reference_id`. O fluxo de ingresso não usa `booking_payments`,
   porque não há reserva, participante nem repasse.
7. **Webhook é a autoridade.** O pagamento só credita ingressos ou ativa o
   passe quando o PSP confirma. `POST /sync` repete a consulta server-to-server;
   replay de webhook não duplica efeito.
8. **Valor e referência externa são conferidos.** Divergência de valor ou de
   `kind:reference` é recusada e não liquida a compra.

## Superfície

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/v1/me/pass/plans` | Quatro planos e preços |
| GET | `/api/v1/me/pass` | Assinatura vigente ou última tentativa, franquias e próxima entrega |
| POST | `/api/v1/me/pass/subscriptions` | Cria assinatura pendente e abre Pix do trimestre |
| GET | `/api/v1/me/pass/subscriptions/{id}` | Detalhe privado |
| POST | `/api/v1/me/pass/subscriptions/{id}/sync` | Consulta o PSP e ativa se pago |
| POST | `/api/v1/me/pass/subscriptions/{id}/confirm` | Ativa sem PSP, só em ambiente local |
| DELETE | `/api/v1/me/pass/subscriptions/{id}` | Cancela assinatura ainda pendente |
| POST | `/api/v1/me/tickets/purchases` | Cria compra e abre Pix do pacote |
| POST | `/api/v1/me/tickets/purchases/{id}/sync` | Consulta o PSP e credita se pago |

## Modelo

- `pass_subscriptions`: plano, franquia mensal, valor do trimestre, status
  (`pending`, `active`, `expired`, `cancelled`), início, fim e pagamento.
- `pass_deliveries`: uma linha por mês (1..3), com `unique(subscription_id, month_index)`.
- `purchase_payments`: cobrança Pix de compra, com `unique(kind, reference_id)`
  e `unique(provider, provider_order_id)`.

Migração `e4a1c9d7b203`, aplicada em upgrade → downgrade → upgrade; `alembic check` limpo.

## Rotina

`python -m scripts.deliver_pass_months` entrega franquias vencidas e expira
assinaturas. Aceita `--loop --interval`. Não há worker interno no MVP.

## Testes

- `tests/test_pass.py`: escada de planos, compra → Pix → ativação, entrega
  mensal idempotente, expiração, bloqueio e liberação da trilha paga,
  isolamento entre jogadores.
- `tests/test_ticket_pix.py`: compra não credita antes do pagamento, status pago
  credita uma vez, divergência de valor recusada, webhook com replay e `/sync`.

## Pendente

1. Definir se o passe pode ser vendido no meio da temporada e se há pro-rata.
2. Reembolso de passe e de pacote (hoje só existe reembolso de reserva).
3. Conciliação do `purchase_payments` com o extrato do PSP.
4. Recibo/comprovante do passe.
5. Contrato do Mercado Pago em produção (o Inter PJ fica para a 1.0).
