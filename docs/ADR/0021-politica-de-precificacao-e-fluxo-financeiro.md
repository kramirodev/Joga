# ADR 0021 — Política de precificação e fluxo financeiro das reservas

- **Status:** Aprovado pelo responsável do produto em 2026-11-05.
- **Data:** 2026-11-05
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §12, §14, §16, §17, §18, §19 e §26; `GOALS.md`; `PLANS.md` Fases 12–15; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §13–§16.

## Contexto

A versão 3.0 do documento conceitual adotou `TAXA_JOGA = 1,8 × (CUSTOS + LUCRO_ALVO)`, com piso de custos e teto de 15% a 20% do valor da quadra. A versão 3.1 reposicionou o coeficiente como hipótese inicial, mas manteve piso, preço variável e teto.

A revisão mostrou quatro problemas naquele desenho:

1. O coeficiente 1,8 incidia sobre custos determinísticos e sobre uma provisão aleatória ao mesmo tempo, misturando naturezas diferentes.
2. O piso e o teto podiam se contradizer sem que a operação fosse declarada inviável.
3. O teto de 15%–20% não tinha derivação econômica e podia esconder custo real.
4. A fonte de financiamento dos cancelamentos não estava explícita: parte da margem parecia pagar o mesmo risco duas vezes.

Ao mesmo tempo, a análise do fluxo de pagamentos concluiu que o JOGA precisa operar com várias cobranças Pix individuais por reserva, split por cobrança, saldo por recebedor e liberação controlada. O custo por cancelamento e a possibilidade de a quadra sacar antes da confirmação alteram diretamente o preço.

## Decisão

### 1. Fórmula aprovada

A taxa de serviço do JOGA por reserva concluída passa a ser:

```text
TAXA = c·V + C_k + C_c·μ·S + p_t·V

μ = (1 − q) / q
S = 1 + z·√(φ / μ)
```

| Termo | Significado |
|---|---|
| `c·V` | Comissão comercial sobre o valor da quadra. Cobre custo fixo da operação (produto, suporte, KYC, interface financeira do recebedor) e lucro-alvo. |
| `C_k` | Custo variável de uma reserva **concluída**: tarifas do PSP por cobrança, split, transferência, conciliação e operação variável. |
| `C_c` | Custo de uma reserva **cancelada**: tarifas não recuperáveis, devolução e atendimento. Nunca inclui o valor principal devolvido. |
| `μ` | Cancelamentos esperados por reserva concluída. |
| `S` | Fator de segurança estatístico para o número de cancelamentos. |
| `p_t·V` | Provisão de cauda: MED, estorno sem saldo, disputa após liberação e outros eventos raros. |

`q` é a taxa de conclusão: reservas pagas que efetivamente se confirmam e se realizam, divididas pelas tentativas de reserva paga abertas no período.

Parâmetros iniciais:

| Parâmetro | Valor inicial | Natureza |
|---|---|---|
| `q` | Medido por janela móvel de 90 dias | Dado operacional; não é premissa fixa |
| `c` | 10% | Hipótese comercial a validar no piloto |
| `z` | 1,645 | 95% de confiança |
| `φ` | 1,0 | Poisson; aumentar se cancelamentos forem correlacionados (chuva, feriado) |
| `p_t` | 0,2% | Provisão inicial de cauda |
| `C_k`, `C_c` | Medidos por PSP e operação | Substituir hipóteses por contrato e dados reais |

### 2. Interpretação correta do 1,8

Com `q = 20%`, `μ = 4` e `φ = 1`:

```text
S = 1 + 1,645/√4 = 1,82
μ·S = 7,29
```

O coeficiente 1,8 é, na prática, o fator de segurança de 95% para a variância dos cancelamentos no cenário de 80% de cancelamento. Ele **não** é markup sobre o custo total e **não** deve ser aplicado a `C_k` nem à soma `CUSTOS + LUCRO_ALVO`.

A leitura aprovada é:

- `1,8` incide apenas sobre a provisão de cancelamento (`C_c·μ`), por meio de `S`.
- `C_k` é custo determinístico e entra uma única vez.
- Cancelamentos não entram em `C_k` para evitar dupla contagem.
- A comissão `c·V` é a fonte principal de financiamento dos cancelamentos; o fator `S` protege contra a variância, não substitui a comissão.

### 3. Base de cálculo e ponto fixo

As tarifas percentuais do PSP incidem sobre o valor total pago (`V + TAXA`), não apenas sobre o valor da quadra. O cálculo deve ser resolvido como ponto fixo:

```text
S_total = V + TAXA
C_k = a_k + p·S_total + τ
C_c = a_c + p·S_total·(m/k)
TAXA = c·V + C_k + C_c·μ·S + p_t·V
```

Onde `a_k` é o custo fixo por reserva concluída, `p` é a tarifa percentual por cobrança, `τ` é a tarifa de transferência/liberação, `a_c` é o custo fixo por cancelamento e `m/k` é a quantidade média de cobranças pagas antes do cancelamento.

O valor exibido ao jogador é congelado quando a cobrança é aberta. Recalibrações valem apenas para reservas futuras.

### 4. Substituição do teto por elegibilidade mínima

O teto `α` de 15%–20% é removido. Ele não tinha derivação econômica e podia transformar reservas necessárias em prejuízo.

Em seu lugar, o JOGA adota uma **regra de elegibilidade**:

- Se a taxa calculada ultrapassar o limite operacional aceito para a faixa (referência inicial: 25% do valor da quadra), a reserva paga não é oferecida.
- Se o valor da quadra for baixo demais para diluir os custos fixos, o estabelecimento é orientado a renegociar o preço da quadra ou a operar apenas com reserva sem pagamento integrado.
- A decisão é registrada com o valor calculado, a faixa e o motivo. Não é um desconto silencioso nem um subsídio.

Com `q = 20%`, a referência de R$ 100 de valor mínimo mantém a taxa abaixo de 25%. Esse número é ilustrativo e será recalibrado com os custos reais.

### 5. Calibração e governança

- `q` é medido por modalidade e faixa de preço, com janela móvel e amortecimento. Não usar `q` por quadra sem amostra suficiente, para evitar seleção adversa.
- A taxa não varia em tempo real. A variação por ciclo é limitada a ±10% e precisa ser registrada.
- A taxa de uma reserva não muda depois que o pagamento foi aberto.
- Aumentos e reduções exigem justificativa econômica, simulação e versionamento.
- `C_k`, `C_c`, `τ` e `p_t` são revisados quando o contrato do PSP ou o comportamento observado mudar.

### 6. Decisão de PSP

O **Pagar.me Flex** é a primeira opção, condicionada a confirmação contratual e comercial. A documentação pública sustenta:

- várias cobranças no mesmo `order`;
- Pix com split;
- split por valor fixo ou percentual;
- saldo por recebedor;
- `POST /transfers` com `recipient_id` e `Idempotency-Key`;
- `transfer_enabled=false` para desativar transferência automática.

O **Inter** é a alternativa centralizada: o valor fica na conta do JOGA, a quadra não saca sozinha e o reembolso é operacionalmente mais simples. Em troca, aumenta a exposição jurídica e regulatória de custódia de recursos de terceiros e exige parecer específico.

Ficam excluídos como primeira opção os PSPs com tarifa fixa alta por Pix, porque o fluxo tem muitas cobranças individuais: Asaas (R$ 1,99 por Pix), AbacatePay (R$ 0,80 por Pix) e OpenPix (0,80% com mínimo de R$ 0,50).

### 7. Condições de liberação e KYC

- A quadra só recebe a liberação depois que **tudo estiver confirmado**, inclusive a realização da partida.
- Deve existir liberação automática após `N` horas da partida, com janela de disputa anterior. `N` permanece pendente.
- Um estabelecimento com `recipient` em credenciamento **não pode** originar reserva paga. O KYC é um portão de elegibilidade, não uma etapa posterior.
- A interface financeira do recebedor é escopo obrigatório quando houver split: extrato por reserva e cobrança, agenda de recebíveis, comprovantes, contratos e canal de contestação (Res. 264/349).
- Se a quadra puder sacar o saldo por conta própria, a retenção deixa de ser técnica e passa a ser apenas contratual; nesse caso, `p_t` sobe e a política de cancelamento após confirmação precisa ser revista.

## Consequências

- A fórmula passa a ter quatro parâmetros auditáveis (`c`, `z`, `φ`, `p_t`) e três custos medidos (`C_k`, `C_c`, `τ`), em vez de um coeficiente arbitrário.
- O 1,8 deixa de ser margem e passa a ser provisão estatística; a comissão passa a ser a fonte explícita do custo de cancelamento.
- O piso e o teto deixam de existir como mecanismos concorrentes. A proteção contra prejuízo passa a ser a regra de elegibilidade e a negociação do PSP.
- O preço pode ficar acima de 20% em quadras baratas ou em cenários de baixa conclusão; nesses casos, a reserva paga não é oferecida em vez de ser subsidiada.
- A interface financeira do estabelecimento e o KYC entram no custo fixo coberto pela comissão, não em `C_k`.
- A escolha final do PSP não altera a fórmula, apenas os parâmetros e o risco de cauda.

## Pendências

1. Medir `q`, `C_k`, `C_c`, `τ` e `p_t` no piloto.
2. Confirmar com o Pagar.me: elegibilidade como cliente PSP no Flex, tarifa Pix negociada, tarifa de split/transferência, saque autônomo com `transfer_enabled=false`, comportamento do estorno Pix V5 com split, responsabilidade por MED e retenção de novos recebedores.
3. Definir `N` da liberação automática e a janela de disputa.
4. Definir a política de cancelamento após a reserva confirmada.
5. Revisar juridicamente o modelo de split e, se aplicável, a custódia centralizada no Inter.
6. Definir o limite operacional de elegibilidade por faixa de preço.
