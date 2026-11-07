# ADR 0034 — Mercado Pago no protótipo e beta fechado

- **Status:** Aprovado para protótipo e beta fechado em 2026-11-07. Não é a decisão de PSP de produção.
- **Data:** 2026-11-07
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `docs/ADR/0021-politica-de-precificacao-e-fluxo-financeiro.md`; `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §12; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §15; `PLANS.md` Fase 14.

## Contexto

O JOGA ainda está em protótipo e beta fechado. Nessa etapa, o objetivo é validar a jornada de pagamento Pix, o fluxo de reserva e a conciliação sem assumir o custo e a complexidade de uma operação financeira de produção. O custo de manter um CNPJ/MEI ativo (cerca de R$ 80 por mês) é relevante para o momento, mas não é uma mensalidade do PSP.

O Mercado Pago oferece Checkout Transparente com Pix, cobrança percentual por transação e sem grande aporte inicial. A decisão de produção do ADR 0021 continua sendo o Pagar.me Flex, com split e liberação controlada. É necessário separar claramente as duas fases para não tratar a custódia de teste como modelo definitivo.

## Decisão

1. No **protótipo e beta fechado**, o PSP será o **Mercado Pago Checkout Transparente**, exclusivamente com **Pix** nesta etapa.
2. O protótipo não movimenta dinheiro real. O beta usa valores simbólicos/de teste e ambiente controlado; qualquer cobrança real exige MEI/CNPJ ativo, revisão contábil/jurídica e autorização específica.
3. No beta, o valor fica centralizado na conta Mercado Pago do JOGA, com registro no ledger interno por reserva, participante e vaga. Não há split automático para o estabelecimento nesta fase.
4. O repasse ao estabelecimento é **simulado ou manual** e só ocorre depois que a partida for declarada como acontecida (`COMPLETED`). Não chamar esse fluxo de escrow, custódia definitiva ou garantia de produção.
5. O domínio de pagamentos deve usar um **adaptador de PSP** com modos distintos:
   - `mercadopago_beta`: custódia centralizada de teste, Pix, ledger interno e repasse após `COMPLETED`;
   - `pagarme_production`: split/retenção e liberação controlada, conforme ADR 0021.
6. O backend não deve assumir que o PSP de beta oferece split, retenção ou reembolso integral. O ledger e a máquina de estados continuam sendo a fonte interna de direitos e obrigações.
7. Produção continua com **Pagar.me Flex** para prender o valor e liberar após a partida, condicionada a contrato e validação. O Mercado Pago não substitui essa decisão.
8. O beta com dinheiro real só pode operar com MEI/CNPJ ativo, contrato com o estabelecimento, política de cancelamento/reembolso e revisão jurídica. CPF pessoal fica restrito a protótipo/sandbox.
9. Antes de qualquer beta com valor real, validar no Mercado Pago: Pix, webhooks autenticados, idempotência, reembolso, conciliação, tarifas e limites.

## Alternativas consideradas

### A. Pagar.me desde o protótipo

Alinhado à produção, mas exige contrato, onboarding e configuração mais pesada antes de validar a jornada. Fica para produção.

### B. Mercado Pago com split desde já

Aproxima o beta da produção, mas o split 1:1 credita o vendedor e o reembolso depende do saldo dele; isso não é necessário para testar a jornada e adiciona risco operacional. Não adotado no beta.

### C. Mercado Pago com custódia centralizada de teste (adotada)

Permite testar Pix, reserva, ledger e repasse após a partida com baixo custo e sem prometer o modelo de produção. Exige deixar claro que é custódia de teste.

### D. Operar com CPF pessoal em produção

Reduz custo imediato, mas mistura patrimônio pessoal, receita, tributos e responsabilidade civil. Rejeitada para dinheiro real.

## Consequências

- O beta consegue validar a jornada Pix sem o custo de uma operação financeira completa.
- O JOGA precisa manter um adaptador de PSP e um ledger que não dependam do Mercado Pago.
- A custódia centralizada de teste não deve ser apresentada como garantia de retenção ou reembolso de produção.
- A migração para Pagar.me exigirá novo adaptador, contrato, testes de split/retenção e revisão jurídica.
- Qualquer beta com dinheiro real aumenta a exigência de CNPJ/MEI, contratos, nota fiscal e conformidade.

## Critérios para revisão

- Início de beta com dinheiro real.
- Definição de MEI/CNPJ e revisão contábil/jurídica.
- Validação técnica do Mercado Pago para Pix, reembolso e conciliação.
- Contratação do Pagar.me e validação de retenção/liberação.
- Volume, risco de fraude, MED ou exigência regulatória que torne a custódia centralizada inviável.
