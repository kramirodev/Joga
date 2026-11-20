# ADR 0053 — Modo demo sem PSP e sem dinheiro real

- **Status:** Aprovado em 2026-11-20.
- **Data:** 2026-11-20
- **Relaciona:** ADR 0034 (Mercado Pago no protótipo e beta fechado), ADR 0048
  (Mercado Pago como PSP do protótipo com jogadores reais), ADR 0049 (modelo
  tributário), ADR 0051 (versão mínima do app), `AGENTS.md` §3/§4/§5,
  `docs/DEPLOY_DEMO.md` e `docs/RUNBOOK.md`.
- **Numeração:** a ADR 0052 é a do payout da quadra pública; esta decisão ocupa
  o número 0053.

## Contexto

O ambiente de demonstração era configurado como `development`, um ambiente
local. Isso liberava a simulação de pagamento por qualquer combinação de flags
e permitia que o webhook do Mercado Pago aceitasse eventos sem assinatura
quando o segredo não estava configurado. Ao mesmo tempo, um boot em
`production` exigia credenciais reais do Mercado Pago, que o demo não deve ter.

O demo precisa continuar demonstrando reserva e passe com pagamento simulado,
mas com as guardas de um ambiente compartilhado: sem PSP real, sem aceitar
webhook sem assinatura e sem possibilidade de dinheiro real.

## Decisão

### 1. Classificação de ambientes

`app/core/environments.py` centraliza a classificação:

- `LOCAL_ENVIRONMENTS = {"local", "test", "development", "ci"}`;
- `DEMO_ENVIRONMENTS = {"demo"}`;
- `is_production()` é tudo que não é local nem demo, inclusive `staging`.

As cinco cópias da lista de ambientes locais (`config.py`, `payments.py`,
`passes.py`, `tickets.py` e `bookings/service.py`) passam a usar os helpers.
Local e produção mantêm o comportamento anterior.

### 2. Perfil de configuração do demo

Com `JOGA_ENVIRONMENT=demo`, o boot falha se:

- `JOGA_PSP_PROVIDER` não for `simulator`;
- `JOGA_MONEY_MODE` não for `simulated`;
- `JOGA_TICKET_PURCHASE_ENABLED` não for `false`;
- `JOGA_PHONE_HASH_SECRET` ou `JOGA_TOKEN_HASH_SECRET` estiverem no valor
  padrão de desenvolvimento;
- `JOGA_DEV_FIXED_OTP` estiver definido.

O demo continua exigindo `JOGA_CPF_KEY` + `JOGA_CPF_KEY_ID`, porque a proteção
de dados pessoais não depende do financeiro. `JOGA_MERCADO_PAGO_ACCESS_TOKEN`,
`JOGA_MERCADO_PAGO_WEBHOOK_SECRET` e `JOGA_MERCADO_PAGO_NOTIFICATION_URL` não
são exigidos. O adaptador de PSP construído é sempre o simulador; nenhuma
chamada de rede ao Mercado Pago é feita.

### 3. O que fica permitido

- `POST /api/v1/bookings/{id}/payments/simulate`: somente para participante
  ativo do próprio booking, como em local. O pagamento é registrado como
  simulado e mantém o ledger consistente.
- `POST /api/v1/me/pass/subscriptions/{id}/confirm`: somente para o dono da
  assinatura. Produção continua respondendo `403 confirmation_requires_psp`.
- `GET /api/v1/app-config` expõe `demo_mode: true` para os clientes exibirem
  o rótulo de demonstração.

### 4. O que fica bloqueado

- `POST /api/v1/payments/mercadopago/webhook` responde
  `404 webhook_disabled` em demo, antes de ler o corpo, verificar assinatura ou
  gravar `psp_webhook_events`. Nenhum evento é persistido.
- PSP real (`psp_provider=mercadopago`) e `money_mode=real` são recusados no
  boot.
- Compra de tickets permanece desligada; a flag existente responde
  `503 ticket_purchase_disabled`.
- Não há repasse, custódia, NFS-e, Pix ou qualquer movimentação de dinheiro
  real no demo.

### 5. Dados e operação

- Os dados do demo são descartáveis e não devem ser tratados como registro
  contábil, fiscal ou de identidade.
- É proibido usar credenciais reais do Mercado Pago, chaves Pix de produção,
  dados pessoais reais ou dinheiro real no demo.
- O checklist de variáveis para o agente de infra está em
  `docs/RUNBOOK.md` e `backend/.env.example`.

## Consequências

- O demo deixa de depender de `development` e passa a ter guardas explícitas.
- Um deploy de demo com configuração incompleta falha no boot em vez de
  degradar silenciosamente.
- O webhook fica indisponível no demo; reservas e passes usam apenas a
  simulação do próprio recurso.
- Clientes podem distinguir demonstração de produção por um campo aditivo, sem
  quebrar contratos existentes.
- A migração dos workflows de deploy para `JOGA_ENVIRONMENT=demo` é
  responsabilidade do agente de infraestrutura.

## Alternativas consideradas

- **Manter o demo como `development`:** simples, mas mantinha a simulação
  aberta e o webhook sem assinatura aceitável.
- **Usar `production` com PSP sandbox:** exigiria credenciais e chamadas de
  rede ao Mercado Pago, além de risco de confundir sandbox com dinheiro real.
- **Criar um PSP falso separado:** adicionaria complexidade sem ganho; o
  simulador existente já cobre o fluxo e o adaptador é selecionado pela
  configuração.
