# ADR 0036 — Hipótese de provisão de fraude baseada no Trust Factor

- **Status:** Proposta registrada em 2026-11-07; **não aprovada** e não implementada.
- **Data:** 2026-11-07
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §14, §17 e §26; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §11.2 e §15; ADR 0025 (Trust Factor); ADR 0034 (Mercado Pago no beta).

## Contexto

Foi proposta uma provisão de fraude (`p_t`) dinâmica por partida, calculada a partir da **mediana do Trust Factor** dos participantes. A intuição é que a mediana resistiria a um único perfil ruim e permitiria que grupos confiáveis pagassem menos, enquanto grupos sem histórico ou com histórico ruim pagariam mais.

A ideia é coerente como hipótese, mas exige separar risco esportivo de risco financeiro antes de qualquer cobrança.

## Hipótese

```text
p_t = fator(mediana(Trust Factor dos participantes)) * p_t_base
```

Faixa ilustrativa: 0,05% para grupos de alta confiança e até 0,5% para grupos de baixa confiança, sempre com piso e teto.

## Decisão atual

1. A hipótese fica **registrada, mas não aprovada**.
2. O modelo atual continua usando `p_t = 0,2%` fixo, conforme ADR 0021.
3. Nenhum código, preço ou cobrança será alterado nesta fase.
4. Trust Factor continua sendo confiabilidade operacional esportiva, não score de risco de pagamento.
5. Qualquer experimento será feito em **modo sombra**, sem cobrar diferente do jogador.

## Por que não aplicar agora

- **Trust Factor ainda não está operacional:** começa neutro em 100, fica oculto e os deltas completos pertencem à Fase 17.
- **Mede coisa diferente:** comparecimento e conduta esportiva não predizem MED, chargeback ou conta tomada.
- **Mediana é manipulável por grupo:** resiste a um outlier, não a uma comunidade coordenada, contas infladas ou partidas combinadas.
- **Conta nova paga mais:** sem histórico, o grupo cai na faixa conservadora, o que penaliza adoção.
- **Incentivo perverso:** se o preço depende da reputação, passa a valer a pena farmar Trust Factor.
- **Impacto financeiro pequeno:** em `V = R$ 180`, `0,2%` é R$ 0,36 e `0,05%` é R$ 0,09; a diferença é R$ 0,27 por reserva.
- **Risco jurídico e de transparência:** preço variável por reputação exige base legal, explicação clara e revisão de consumidor/LGPD.
- **Complexidade de preço:** o valor é congelado na abertura da cobrança e precisa ser versionado e auditável; calcular por partida adiciona margem de erro e disputa.

## Plano de avaliação futura

1. Coletar, no piloto, Trust Factor, MED, chargebacks, estornos sem saldo, valor da reserva, idade da conta e histórico de pagamento.
2. Calcular a mediana de Trust Factor e um score de risco de pagamento em paralelo, **sem cobrar diferente**.
3. Comparar o score com eventos reais de fraude/MED em janela mínima de 90 dias.
4. Se houver poder preditivo, criar um score de risco **separado** do Trust Factor esportivo.
5. Aplicar apenas com piso/teto, sem penalizar conta nova, com explicação e revisão jurídica.
6. Versionar o cálculo e congelar o valor na abertura da cobrança.

## Consequências

- O beta mantém preço previsível e `p_t` fixo.
- A hipótese fica documentada para a Fase 15/17 sem comprometer a cobrança atual.
- O JOGA evita usar reputação esportiva como proxy de fraude financeira sem evidência.
- Se a hipótese for rejeitada pelos dados, o modelo fixo continua válido.

## Critérios para revisão

- Dados suficientes de MED/chargeback no piloto.
- Trust Factor implementado e com deltas contestáveis.
- Revisão jurídica de preço baseado em reputação.
- Evidência de que o ganho de risco compensa a complexidade operacional.
