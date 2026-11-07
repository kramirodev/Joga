# Fase 14 — Pagamentos Pix e reembolsos

**Status:** 14A (Mercado Pago sandbox, Pix, webhook e ledger) implementada e validada localmente em 2026-11-07; 14B (Pagar.me produção, split/retenção e reembolso real) pendente.
**Branch:** `feat/14-pagamentos-pix`

## Fontes e contexto

- `AGENTS.md`
- `GOALS.md`
- `PLANS.md` Fase 14
- `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §12 e §17
- `docs/JOGA_DOCUMENTACAO_TECNICA.md` §15
- ADR 0021 (Pagar.me em produção)
- ADR 0034 (Mercado Pago no protótipo/beta)
- Fases 13A/13B (reservas e T3)

## Objetivo

Implementar a cobrança Pix por participante no protótipo/beta usando Mercado Pago Checkout Transparente (Orders API), com webhook autenticado, idempotência, ledger interno e conciliação básica, sem dinheiro real e sem split automático. Produção com Pagar.me fica para a 14B.

## Escopo 14A — Mercado Pago sandbox

- Adaptador de PSP desacoplado do domínio (`PspAdapter`), com implementações `simulator` e `mercadopago`.
- Criação de uma ordem Pix por participante, vinculada à reserva, vaga e versão da cobrança.
- `X-Idempotency-Key` em todas as chamadas de criação.
- Persistência de `provider_order_id`, `provider_payment_id`, QR Code, copia-e-cola, ticket URL, expiração e status bruto.
- Webhook público do Mercado Pago com validação de assinatura quando o segredo estiver configurado.
- Idempotência de webhook por `provider_event_id` e por transição de pagamento.
- Sincronização manual do status de um pagamento.
- Ledger interno append-only: cobrança criada, pagamento confirmado e reembolso simulado.
- Confirmação da reserva somente quando todas as vagas ativas estiverem pagas.
- Adaptador simulado para testes locais e CI.
- Exibição do QR Code/copia-e-cola no mobile e status financeiro no painel.

## Fora do escopo da 14A

- Dinheiro real, credenciais reais, produção.
- Split, retenção, liberação e custódia de produção.
- Reembolso real e MED.
- KYC do recebedor e onboarding de estabelecimentos no PSP.
- Pagar.me, cartão, boleto ou assinaturas.
- Interface financeira completa e conciliação periódica (Fase 15).

## Pré-requisitos e dependências

- Fases 13A/13B integradas ou autorização para empilhar a 14A.
- Conta Mercado Pago de teste e credenciais sandbox para teste manual; CI usa simulador.
- Definição de que o beta não movimenta dinheiro real.
- E-mail do pagador: a API do Mercado Pago exige `payer.email`. No sandbox, usar e-mail de teste configurável; em produção, coletar e-mail real ou definir identidade de pagamento.

## Arquivos/componentes esperados

- `backend/app/modules/payments/adapter.py` — contrato e adaptadores.
- `backend/app/modules/payments/models.py` — eventos, webhooks e ledger.
- `backend/app/modules/payments/service.py` — abertura de cobranças, webhook, sync e ledger.
- `backend/app/api/v1/payments.py` — webhook e sincronização.
- Ajustes em `bookings/models.py` e `bookings/service.py`.
- Migração Alembic revisável.
- Testes de adaptador, serviço, API, webhook e idempotência.
- Ajustes no painel web e no mobile para exibir Pix.

## Riscos e decisões pendentes

- **Alto:** webhook forjado ou replay. Assinatura, idempotência e consulta server-to-server.
- **Alto:** confirmação de reserva sem pagamento real. Só confirmar por status `PAID` do PSP/simulador.
- **Alto:** exposição de QR Code ou dados financeiros a outro participante. Filtrar por participante/organização.
- **Médio:** Mercado Pago exige e-mail do pagador; o cadastro atual é por telefone.
- **Médio:** Orders API pode mudar; adaptador e testes de contrato reduzem acoplamento.
- **Médio:** sem split/retenção, o beta é custódia centralizada de teste.
- **Pendente:** PSP de produção, reembolso, conciliação, KYC e credenciais.

## Plano de verificação

- **Red:** testes falhando para webhook inválido, replay, pagamento parcial, valor divergente, acesso cruzado e PSP indisponível.
- **Green:** implementar adaptador simulado/sandbox, persistência e confirmação condicionada.
- **Refactor:** separar contrato, mapeamento de status e ledger.
- **Verify:** pytest, Postgres, ruff, mypy, alembic, web e mobile.

## Comandos reais de validação

```bash
cd backend
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy app
.venv/bin/python -m pytest
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic check

cd ../web
pnpm lint && pnpm format:check && pnpm typecheck && pnpm test && pnpm build

cd ../mobile
pnpm exec tsc --noEmit && pnpm exec eslint . && pnpm exec prettier --check .
```

## Critérios de aceite

- [x] Cada vaga ativa tem uma cobrança Pix vinculada à reserva e à versão.
- [x] Criação de cobrança é idempotente e não duplica ordem.
- [x] Webhook inválido é rejeitado; replay não duplica pagamento nem ledger.
- [x] Reserva só confirma com todas as vagas ativas pagas.
- [x] Valor e referência externa são conferidos contra o banco.
- [x] Participante só vê o próprio QR/cobrança; organização vê apenas as próprias reservas.
- [x] Ledger registra cobrança, confirmação e reembolso simulado.
- [x] Adaptador simulado funciona sem rede e sem credenciais.
- [x] Nenhum dinheiro real, split ou provedor de produção é acionado.
- [x] Migração reversível e `alembic check` limpo.

## Evidências exigidas

- Saída de testes backend, Postgres, ruff, mypy e alembic.
- Testes de adaptador com HTTP simulado.
- Saída de web/mobile.
- Revisão do diff e `git diff --check`.
- Atualização de `harness/build-log.md`.

## Evidências da 14A (2026-11-07)

- Adaptador `simulator` e `mercadopago` (Orders API) com testes HTTP simulados.
- Cobrança Pix por vaga, QR Code, copia-e-cola, ticket URL e expiração persistidos.
- Webhook com validação HMAC, idempotência por evento e consulta server-to-server.
- Ledger `CHARGE_CREATED`, `PAYMENT_CONFIRMED` e `VENUE_RELEASE`; reembolso simulado.
- Reserva confirma somente com todas as vagas ativas pagas.
- Backend: **364 passed** com `JOGA_TEST_DATABASE_URL`; ruff, formatação e mypy verdes.
- Painel web e mobile com testes/verificações verdes; QR Code exibido no mobile.
- Nenhuma credencial real, dinheiro real ou split de produção foi acionado.
- **Sandbox real:** credencial de teste validada em `/users/me` e ordem Pix criada com status `action_required`, QR Code e ticket URL. Nenhum pagamento foi realizado.

## Aprovação e condição de parada

14A autorizada em 2026-11-07. 14B depende de contrato/credenciais do Pagar.me e autorização específica. Não iniciar a Fase 15 automaticamente.
