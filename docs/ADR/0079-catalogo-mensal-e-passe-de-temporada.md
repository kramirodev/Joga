# ADR 0079 — Catálogo mensal 20/40/70 e passe de temporada separado

- **Status:** **Aprovado como direção com ajustes (2026-11-28); jurídico/fiscal
  pendentes; implementação faseada.** Catálogo, preço e parcelamento do passe
  estão decididos; o parecer jurídico (reembolso × CDC) e o fiscal (6% × 15,5%)
  continuam pendentes e não bloqueiam o início faseado. **Nada foi implementado**
  em backend, app ou painel.
- **Data:** 2026-11-28
- **Decisores:** responsável pelo produto (decisão) e parecer financeiro
  (`docs/PARECER_FINANCEIRO_ASSINATURA_2026-11-28.md`).
- **Substitui parcialmente:** **ADR 0070** (catálogo de 7 SKUs, durações
  trimestral/semestral, passe embutido, 6x) e **ADR 0043 §2** (passe trimestral
  pago, tamanhos 10/20/30/50, preço único de R$ 3,25).
- **Relaciona:** ADR 0042 (ingresso, tabela 2D e piso de 10%), ADR 0040 (repasse
  em `starts_at + 2h`), ADR 0049 (unidade de conta, base tributária e custódia),
  ADR 0068 (NFS-e), ADR 0075 (Supabase; ocupa o número sugerido no parecer).
- **Fontes:** `docs/DECISAO_CATALOGO_MENSAL_E_PASSE_2026-11-28.md` (registro da
  decisão) e `docs/PARECER_FINANCEIRO_ASSINATURA_2026-11-28.md` (custos, margens
  e riscos).

> **Nota de numeração.** Esta ADR usa **0079**. O parecer sugeria “ADR 0075”, mas
> 0075 já é `0075-endurecimento-supabase-public-schema.md`. 0076 e 0077 são
> lacunas livres em `origin/main` e ficam preservadas como lacuna; 0078 é
> observabilidade. Além disso, existem **dois arquivos 0070** no acervo
> (`0070-assinatura-com-franquia-mensal-expiravel.md` e
> `0070-pedido-de-entrada-em-cla.md`) — colisão de numeração a resolver em rodada
> própria, sem renumerar nenhum dos dois agora.

## Contexto

A ADR 0070 substituiu os pacotes avulsos da ADR 0042 e o passe da ADR 0043 por um
único produto de assinatura com sete SKUs: mensal 20/40/60, trimestral 20/40/60 e
um semestral 40, com franquia mensal expirável, passe embutido na assinatura e
parcelamento em até 6x no semestral. A ADR 0043, por sua vez, definiu temporada
trimestral, passe pago a R$ 3,25 por ingresso e franquia de ingressos entregue mês
a mês.

Três problemas apareceram na análise financeira de 2026-11-28:

1. **Complexidade de catálogo sem ganho de margem.** Sete SKUs, três durações e
   escada de preço por volume *e* por duração não se traduzem em margem: o
   semestral de 40 fica exatamente no piso (10,5% no pior caso) e o desconto
   máximo sobre o pacote grande histórico é de 3,2%.
2. **Parcelamento sem juros destrói o piso.** No 6x sem juros (13,91%), o
   semestral de 40 fica em **−5,0%** no pior caso; no cartão 1x a 4,99% ele fica
   em 15,6%. O parcelamento é a variável que mais consome margem.
3. **Passe embutido esconde o preço real.** A assinatura vendia tickets *e*
   temporada no mesmo valor, o que impedia precificar a temporada pelo que ela
   custa (tickets grátis) e impedia comparar planos.

A decisão de 28/11 resolve os três simplificando o catálogo e separando os dois
produtos. As premissas de custo continuam as do parecer: quadra R$ 2,50/ticket na
célula de referência (5x5 econômica noturna, 6 tickets/jogador), custo
fixo/cancelamento de R$ 0,1667/ticket, custódia 0,4%, Pix 0,99%, cartão 1x 4,99%
e provisão de chargeback de 0,5%.

Em 28/11/2026 o dono ajustou duas decisões sobre a mesma direção: (a) o **passe**
pode ser pago em **até 3x** no cartão, mantendo a **assinatura em 1x** e o **6x
fora**; (b) o **reembolso proporcional ao não usado entra no app** por decisão do
dono, com o conflito com o CDC art. 49 e a ADR 0070 §8.1 registrado e o risco
jurídico aceito de forma consciente — sem parecer que aprove a regra.

## Decisão

### 1. Catálogo: três planos mensais

1. Existem **somente três planos**, todos **mensais** e de **assinatura de
   tickets**: 20, 40 e 70 tickets por mês.
2. **Trimestral e semestral deixam de existir** como catálogo. Não há venda
   nova de ciclo de 3 ou 6 meses.
3. O preço do Pix é o **preço-base**; o cartão é preço de tabela obtido por
   gross-up (§2). Não há preço “escondido” nem taxa acrescentada no checkout.

| Plano | Tickets/mês | Pix/ticket | Pix/mês | Margem Pix* | Margem receita* | Cartão 1x/ticket | Cartão/mês | Margem cartão* |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 20 | R$ 3,40 | R$ 68,00 | 25,3% | 18,6% | R$ 3,60 | R$ 72,00 | 26,2% |
| 40 | 40 | R$ 3,20 | R$ 128,00 | 17,9% | 14,0% | R$ 3,39 | R$ 135,60 | 18,8% |
| 70 | 70 | R$ 3,10 | R$ 217,00 | 14,2% | 11,4% | R$ 3,29 | R$ 230,30 | 15,3% |

\* Margem sobre a quadra consumida no pior caso (`u = 1`), com piso de 10%
(ADR 0042 §5.4) e alvo de 12%; “receita” é a margem sobre a receita do plano.

4. **Comunicação de partidas precisa ser conservadora.** Na faixa de 6–7
   tickets/partida, os planos dão **cerca de 3, 6 e 10 partidas/mês**. No cenário
   econômico, **até 4, 8 e 14**; no premium (12 tickets/partida), **a partir de
   2, 3 e 6**. É proibido prometer “10 partidas” no plano de 70 para o público
   premium.
5. **O plano de 70 fica em R$ 3,10, não em R$ 3,00.** A R$ 3,00 ele cai para
   7,8%–9,7% em células padrão (6x6 econômica dia/noite, 5x5 padrão dia). A
   R$ 3,10 todas as células padrão ficam ≥ 11,5% e o 4x4 premium em 10,2%.
6. O piso absoluto de R$ 3,00 da ADR 0070 §1 continua valendo como regra geral,
   mas o catálogo não usa o piso: usa R$ 3,10 no plano de maior volume.

### 2. Cartão: assinatura somente 1x; passe em até 3x

1. **Assinatura mensal: somente 1x.** Não existe 3x nem 6x para os planos de
   tickets.
2. **Passe de temporada: até 3x.** O parcelamento existe **apenas no passe**,
   **sem 6x**. O cliente absorve a taxa e os juros; o Pix continua sendo o
   preço-base.
3. Gross-up: `P_cartão(n) = P_pix ÷ (1 − s_n − 0,5%)`, arredondado para cima,
   com `s_1x = 4,99%` (MDR) e `s_3x = 9,05%` (MDR + parcelamento, tabela pública
   do MP). Acréscimo efetivo sobre o Pix: **5,81% no 1x** e **10,56% no 3x**.
   - assinatura 1x: R$ 3,60 / 3,39 / 3,29 por ticket;
   - passe 1x: **R$ 44,97**; passe 3x: **R$ 46,99** (3× de R$ 15,66, com o
     centavo restante na última parcela).
4. A apresentação correta é **“Pix R$ X; cartão 1x R$ Y”** para a assinatura e
   **“Pix R$ 42,50; cartão 1x R$ 44,97; cartão 3x R$ 46,99”** para o passe — dois
   ou três preços de tabela, nunca uma taxa lançada depois.
5. **Registro de conflito (6x × 1x × 3x).** O dono pediu 6x; o parecer mostrou
   que o 6x sem juros exige preço dedicado e piora o preço percebido. A decisão
   de 28/11 fechou em **1x para a assinatura** e, no ajuste do mesmo dia, em
   **3x somente para o passe**. **6x permanece fora**; qualquer reabertura exige
   nova análise financeira.
6. **Implementação do 3x.** A tabela acima é o **modelo A** (taxa embutida no
   preço; a JOGA paga o parcelamento e o recupera no gross-up). O **modelo B**
   (1x + juros do emissor, com a JOGA pagando só o MDR) é alternativa válida e
   mantém o custo com o cliente — a escolha depende do contrato do MP
   (§Pendências). Em qualquer modelo, **o cliente paga**; a JOGA não absorve
   parcelamento. Se a taxa real de 3x for maior que 9,05%, a tabela é refeita: o
   gross-up preserva a margem, mas o preço sobe.

### 3. Recorrência e cobrança

1. A assinatura de tickets é **recorrente no cartão**, com consentimento
   explícito. No Pix, a renovação continua **manual** (Pix Automático fora do
   MVP, ADR 0042 §8.5).
2. **Cobrança mensal única.** Assinatura e passe comprados juntos geram **uma
   cobrança no primeiro mês**; nos meses seguintes, cobra-se só a assinatura.
3. **Três tentativas em 24h** (5 min, 1h, 24h). Se todas falharem, suspende-se a
   franquia do **mês seguinte**, nunca a do mês já pago.
4. **Cancelamento** vale para o mês seguinte; o mês pago não é reembolsado
   (ressalvado o direito de arrependimento, §6).
5. A tabela pública do Mercado Pago é referência, **não contrato**: a taxa de
   recorrência/card-on-file pode diferir dos 4,99% e precisa ser confirmada antes
   de ligar a recorrência.

### 4. Passe de temporada: produto separado

1. O passe é **benefício de temporada**, não assinatura de tickets, e é
   **cobrança única** por temporada de 3 meses.
2. Preço: **R$ 42,50/temporada** no Pix, **R$ 44,97** no cartão 1x e
   **R$ 46,99** no cartão 3x (até 3x, §2), equivalente a ~R$ 14,17/mês no Pix. O
   parcelamento é do passe, não da assinatura.
3. O passe **não tem tickets pagos**. Ele libera trilha, cosméticos,
   estatísticas avançadas, lobby privado, busca por CEP e os tickets grátis da
   trilha (ADR 0043 §5, §7 e §10 permanecem).
4. **Tickets:** free 6 por temporada; passe **+6**, total **12 por temporada**.
   Os grátis **expiram no fim da temporada** e não acumulam.
5. **Margem:** com 12 tickets e imposto de 15,5%, a margem fica em
   **12,3%–12,9%** (Pix/cartão); no cenário incremental de 6 tickets,
   45,7%–57,7%. A R$ 37,50 (equivalente ao antigo R$ 12,50/mês) a margem cai para
   3,4%–3,5% no cenário conservador; por isso o preço é R$ 42,50. O **3x**, por
   ser gross-up, mantém a margem do 1x (a taxa de parcelamento é pass-through).
6. **Ressalva de faixa.** A R$ 42,50, o piso de 10% só se sustenta se os tickets
   grátis forem usados na faixa de referência (R$ 2,50/ticket) ou se houver
   restrição de faixa. No premium (R$ 2,68/ticket), a margem cai para **7,5%**
   (cartão, 15,5%) / 7,8% (Pix, 15,5%). Duas saídas: **restringir os tickets
   grátis às faixas elegíveis** (Econômica e Padrão dia, como o crédito de
   estreia da ADR 0042 §7) ou **subir o passe para R$ 49,90**. A escolha é
   pendência (§Pendências); até ela, a direção está aprovada, mas **a condição de
   preço do passe no premium fica aberta**.
7. **Venda no meio da temporada:** pro-rata por mês restante, com cap
   proporcional de tickets, ou não vender após o início. Recomendação do
   parecer: pro-rata.
8. O passe **não interrompe** a temporada já paga ao ser cancelado; os meses
   restantes entram no cálculo de reembolso (§6).

### 5. Franquia, consumo e expiração

1. A franquia da assinatura é **mensal** e **não acumula**: o não usado expira no
   fim do mês (ADR 0070 §4 permanece).
2. Os tickets grátis da temporada (free e passe) **expiram no fim da temporada** e
   são franquia, não crédito comprado.
3. Crédito comprado antes desta ADR continua **sem validade** (ADR 0049); os dois
   regimes coexistem enquanto houver saldo legado.
4. Ticket de assinatura e ticket grátis continuam **pessoais e intransferíveis**.
5. Ordem de consumo e devolução por reserva cancelada seguem a ADR 0070 §5.

### 6. Reembolso proporcional ao não usado (decisão do dono)

1. **Assinatura mensal:**
   `reembolso = tickets_não_usados × P_pago × (1 − s)`, onde `P_pago` é o preço
   por ticket efetivamente recebido e `s` o custo do meio pago pela JOGA (0,99%
   Pix; 4,99% cartão 1x; 9,05% cartão 3x do passe). A provisão de 0,5% de
   chargeback **não** entra no `s`: fica retida como reserva de risco (§7). O que
   foi consumido é cobrado pelo preço do plano; o mês pago não volta.
2. **Sem uso e dentro de 7 dias:** reembolso do valor líquido da taxa; se o PSP
   devolver a taxa, reembolso cheio.
3. **Passe:**
   `reembolso = (meses_não_usados ÷ 3) × 42,50 − (tickets_grátis_resgatados × 2,50) − taxa_do_meio`.
   Resultado negativo significa **sem reembolso**. Exemplo: 1 mês usado e 6
   tickets resgatados → R$ 13,33 menos a taxa; 12 tickets resgatados →
   reembolso zero.
4. **Decisão do dono: a regra proporcional entra no app.** Mesmo com o conflito
   com o **CDC art. 49** e a **ADR 0070 §8.1**, o dono decidiu que o app e o
   painel passam a exibir e aplicar a regra proporcional ao não usado. **Isto não
   é aprovação jurídica:** o parecer jurídico segue pendente e pode exigir
   mudança. O risco é **consciente e aceito** pelo dono e fica registrado nesta
   ADR; a regra é implementada de forma reversível (flag e texto versionado).
5. Mitigação mínima enquanto o jurídico não fecha: texto e consentimento
   explícitos no checkout, Termos de Uso e tela de cancelamento alinhados,
   atendimento com trilha de auditoria, provisão para reclamações e disposição
   para reverter a regra se o parecer contrário vier.
6. `s` no reembolso do passe pago em 3x é **9,05%** (custo real do meio); a
   provisão de 0,5% de chargeback não entra no cálculo (§7).

### 7. Repasse à quadra e chargeback

1. A quadra recebe **o valor cheio**, em `starts_at + 2h`, **sem descontar** MDR,
   recorrência ou chargeback (ADR 0040 permanece).
2. **Chargeback/MED é risco da JOGA.** A JOGA absorve, cria receivable contra o
   jogador, suspende a franquia restante e bloqueia novas compras — **não faz
   clawback da quadra** e não bloqueia saldo já existente.
3. Provisão de **0,5%–1,0%** da receita de cartão. O passe de R$ 42,50 é ticket
   baixo: um chargeback custa quase uma temporada; a cobrança combinada no
   primeiro mês dilui o risco.
4. Não há promessa de split ou repasse automático no piloto.

### 8. Fiscal e reconhecimento de receita

1. A conta usa **6% sobre a comissão**. O cenário de **15,5% (Anexo V)** é o teste
   de stress — a ADR 0049 já registra o conflito [F] entre 6% e 15,5%.
2. Sensibilidade (Pix): a 15,5% sobre a comissão, os planos ficam em 21,9% /
   15,2% / 11,9%. A 15,5% **sobre a receita cheia**, caem para 12,4% / 5,7% /
   **2,4%**. Se essa base for confirmada, o plano de 70 precisa subir para
   ~R$ 3,33 ou a base de cálculo precisa ser a comissão.
3. **NFS-e/recibo ficam fora do caminho crítico por ora**, mas o imposto continua
   sendo custo e passivo: provisionar tributo e risco de autuação. A ausência de
   NFS-e **não aumenta a margem**.
4. **Reconhecimento:** a assinatura é receita do mês, na disponibilização da
   franquia; não usado não gera receita de breakage. O passe é receita diferida,
   reconhecida **1/3 por mês**.
5. O parecer fiscal (6% × 15,5% e base de cálculo) é **condição para escalar**,
   não para o piloto.

### 9. Migração do legado

1. **Base legada sem expiração** (lotes `purchase`) é honrada integralmente; não
   é convertida em franquia.
2. Assinaturas ativas nos planos antigos (10/20/30/50 a R$ 3,25; mensal 20/40/60;
   trimestral 20/40/60; semestral 40) são **honradas até o fim do ciclo pago** e
   migram na renovação para o catálogo novo, com comunicação prévia.
3. Não há reembolso retroativo nem reajuste retroativo na migração.
4. A confirmação de que a base legada está vazia é pré-requisito para desligar o
   catálogo antigo (pendência do parecer).

### 10. Vigência

1. Esta ADR está **aprovada como direção com ajustes (2026-11-28)**, com
   **implementação faseada**. Catálogo, preço e parcelamento do passe estão
   decididos; o jurídico (reembolso) e o fiscal (alíquota/base) seguem pendentes.
2. **Faseamento:** (a) backend do catálogo, entitlements e preço de tabela por
   meio e parcelamento; (b) app com 20/40/70, passe separado e 3x do passe;
   (c) reembolso proporcional no app e no painel, com texto de risco e Termos;
   (d) recorrência no cartão só com o contrato do MP confirmado.
3. Enquanto a fase (a) não entra em produção, o catálogo vigente continua o da
   ADR 0070.
4. O parecer fiscal é condição para **escalar**, não para o piloto. O parecer
   jurídico é condição para **consolidar** a regra de reembolso — que já entra no
   app por decisão do dono, com o risco registrado em §6 e nos conflitos.

## Conflitos registrados

| # | Conflito | Onde | Situação |
|---|---|---|---|
| 1 | **CDC art. 49 × reembolso proporcional (decisão do dono).** CDC e ADR 0070 §8.1 preveem reembolso integral em 7 dias; a regra proporcional ao não usado vai para o app por decisão do dono, sem parecer que a aprove. | ADR 0070 §8.1; CDC art. 49; §6 desta ADR | **Decisão do dono em 2026-11-28, com risco jurídico registrado e aceito.** Jurídico pendente; a regra entra no app com texto/consentimento e é reversível. **Não é aprovação jurídica.** |
| 2 | **6x × 1x × 3x.** O dono pediu 6x; o parecer modelou 6x com gross-up e 6x com juros; a decisão fixou 1x na assinatura e, no ajuste de 28/11, **3x somente no passe**. | §2; parecer §3, §4 e §12 | **Fechado: 6x fora; 3x só no passe; assinatura em 1x.** Reabertura exige análise financeira nova. |
| 3 | **Fiscal 6% × 15,5% e base de cálculo.** 6% sobre a comissão é a conta; Anexo V (15,5%) é o stress. Se a base for a receita cheia, o plano de 70 fica em 2,4% e o passe no premium em 7,5%. | ADR 0049; §8 | **Aberto — pendente de parecer fiscal.** Precificação do 70 e do passe depende disso. |
| 4 | **Numeração de ADR.** O parecer manda formalizar em “0075”, que já é Supabase; 0076/0077 são lacunas; existem dois arquivos 0070 (assinatura e pedido de entrada em clã). | `docs/ADR/` | **Aberto — esta ADR usa 0079.** Renumeração/desambiguação do 0070 fica para rodada própria; nenhum arquivo é renumerado aqui. |
| 5 | **Mecânica dos 12 tickets do passe.** A ADR 0043 §2.1 dá 2 tickets a cada 5 níveis (teto 12); a decisão de 28/11 fala em “6 grátis + 6 do passe”. | ADR 0043 §2.1; §4, item 4 desta ADR | **Aberto — decidir se os 6 extras são fixos ou distribuídos por nível.** |
| 6 | **Passe a R$ 42,50 no premium.** O preço fecha na referência, mas cai a 7,5% no 4x4 premium com 15,5%. | §4, item 6; parecer §6 | **Aberto — restringir faixa ou subir para R$ 49,90.** |
| 7 | **Bundle 20 + passe.** O cliente que pagava R$ 204/temporada passa a pagar R$ 246,50 (+20,8%). | §4; parecer §7 | **Risco comercial registrado**, não conflito documental. |

## Consequências

### Positivas

- Catálogo cai de 7 SKUs para **3 planos + 1 passe**, com uma duração só.
- O 6x sai do produto e com ele o principal consumidor de margem; o **3x fica
  restrito ao passe**.
- A temporada passa a ter preço próprio e deixa de esconder o custo dos tickets
  grátis.
- O repasse à quadra continua cheio e simples: sem MDR, sem chargeback, sem
  clawback.
- O pior caso de margem é positivo no catálogo **na célula de referência**.

### Negativas e riscos

| # | Risco | Gravidade | Impacto | Mitigação |
|---|---|---|---|---|
| 1 | Tickets grátis do passe no premium | Alta | Margem do passe cai para 7,5% | Restringir às faixas elegíveis ou subir para R$ 49,90 |
| 2 | 15,5% na receita cheia | Alta | Plano de 70 a 2,4%; passe no premium a 7,5% (15,5% sobre a comissão) | Parecer fiscal; reprecificar o 70 para ~R$ 3,33 se confirmar |
| 3 | 20 + passe +20,8% | Média-alta | Queda de conversão do plano de entrada | Bundle, comunicação de valor, teste A/B |
| 4 | Recorrência no cartão | Média | Falha de cobrança, churn, chargeback | 3 tentativas, suspender o mês seguinte, consentimento claro |
| 5 | Contrato do MP | Média | Taxa de recorrência/card-on-file diferente de 4,99% | Extrair do painel/contrato antes de ligar |
| 6 | Chargeback em ticket baixo | Média | Um chargeback do passe consome quase a temporada | Provisão 0,5%–1,0%; cobrança combinada no 1º mês |
| 7 | Reembolso proporcional × CDC | Alta | Ação judicial/reclamação; a regra não é juridicamente aprovada | **Risco aceito pelo dono**; texto/consentimento, Termos, atendimento auditável, provisão e revisão se o parecer contrário vier |
| 8 | NFS-e ausente | Alta | Autuação e imposto acumulado | Provisionar; emitir mensalmente quando formalizado |
| 9 | Canibalização do 20 pelo passe | Média | Mix pior, margem blended menor | Vender o passe pelo benefício, não como ticket |
| 10 | 3x do passe | Média | Taxa real > 9,05%, regra do MP, preço percebido e chargeback de maior valor | Gross-up versionado, feature flag, confirmar contrato e limitar a 3x e ao passe |
| 11 | Parcelamento induz compra por impulso | Baixa | Aumento de arrependimento e de reembolso proporcional | 3x só no passe, texto claro e monitorar cancelamentos |

### Critérios de aceite (implementação faseada)

1. O catálogo ativo tem **exatamente** 3 planos mensais e 1 passe; nenhum SKU
   trimestral/semestral é vendável.
2. O checkout oferece **Pix e cartão 1x** na assinatura e **Pix, 1x e 3x** no
   passe; o backend rejeita parcela > 1 na assinatura, > 3 no passe e **6x em
   qualquer produto** (não apenas esconde no app).
3. O preço do cartão é calculado por **gross-up versionado**, nunca digitado no
   app; mudança de taxa exige nova versão de preço, não edição do histórico.
4. Assinatura e passe são **entitlements distintos**: um não libera o outro.
5. Recorrência com consentimento, 3 tentativas e suspensão do mês seguinte;
   passe cobrado uma vez.
6. Reembolso proporcional ao não usado implementado no app e no painel
   **conforme decisão do dono**, com texto, consentimento e risco visível;
   **jurídico pendente** e a regra é reversível por configuração.
7. Repasse à quadra em `starts_at + 2h` pelo valor cheio, comprovado por teste.
8. Chargeback suspende franquia e novas compras, sem clawback da quadra.
9. Migração do legado honra lotes `purchase` sem validade e ciclos já pagos.
10. Testes de idempotência da cobrança, autorização negativa, repetição de
    webhook, falha de PSP e concorrência na concessão de franquia.
11. Preço de tabela do passe (1x e 3x) versionado e calculado pelo servidor;
    nenhum preço de parcela é digitado no app.

## Impacto de implementação (não implementado)

### Backend

- Catálogo de 3 planos mensais + 1 passe de temporada; desativar trimestral,
  semestral e os planos 10/20/30/50.
- `PASS_MONTHS` deixa de ser 3 para a assinatura (1 mês); a temporada de 3 meses
  fica no passe.
- `amount_cents` da assinatura passa a ser valor **mensal**; remover
  `quarter_cents` ou renomear para `price_cents`/`duration_months`.
- Entitlements separados: assinatura → tickets; passe → trilha, cosméticos,
  estatísticas, lobby, CEP e tickets grátis.
- Cobrança recorrente de cartão para assinatura; cobrança única para passe.
  **Assinatura só 1x; passe aceita 1x e 3x; 6x rejeitado no servidor para todos
  os produtos.**
- Preço de cartão por gross-up versionado, **por meio e por parcelamento**
  (1x/3x); taxa de parcelamento e provisão de chargeback parametrizadas.
- Reembolso proporcional ao não usado **conforme decisão do dono**, atrás de
  flag de configuração e com trilha de auditoria; `s` do 3x = 9,05% e o passe
  pago em 3x usa esse custo no cálculo.
- Repasse e chargeback conforme §7; nenhum desconto no repasse da quadra.
- Migração/limpeza de planos e convivência com lotes `purchase` legados.

### App mobile

- Trocar “trimestre” por “mês” na tela de assinatura.
- Exibir 20/40/70 com **Pix e cartão 1x**; a assinatura **não** mostra 3x/6x.
- No **passe**, exibir Pix, **cartão 1x e cartão 3x** (R$ 42,50 / 44,97 / 46,99);
  o 3x é exclusivo do passe.
- Separar visualmente o **passe de temporada** da assinatura de tickets.
- Mostrar 6 grátis do free e +6 do passe, com aviso de expiração no fim da
  temporada.
- Consentimento de recorrência, cancelamento, falha de pagamento e **texto
  explícito do reembolso proporcional ao não usado** (sem apresentá-lo como
  garantia legal).

### Painel/site

- Catálogo de 3 planos + passe, com preço por meio de pagamento.
- Margem por plano, passe, uso (`u`) e faixa; provisão de chargeback.
- Receita diferida do passe (1/3 por mês) e receita mensal da assinatura.
- Conciliação de recorrência, falhas, estornos, **3x do passe** e chargebacks.
- Reembolso proporcional com cálculo auditável e relatório de impacto (CDC).
- Sem promessa de split/repasse automático.

### Testes

- Catálogo: 3 planos, 1 passe, nenhum SKU antigo vendável.
- Parcela > 1 rejeitada na assinatura, > 3 no passe e **6x rejeitado em tudo**.
- Gross-up: tabela de preço por versão e por parcelamento; arredondamento para
  cima e 3x de R$ 46,99 no passe.
- Recorrência: 3 tentativas, suspensão do mês seguinte, cancelamento.
- Passe: cobrança única, expiração dos tickets, pro-rata opcional.
- Reembolso: **regra proporcional do dono**, casos-limite do passe (resultado
  negativo), `s` do 3x e reversão por flag.
- Repasse cheio e chargeback sem clawback.
- Autorização negativa, idempotência e repetição de webhook.

## Documentos a atualizar (fora do escopo desta rodada)

1. `docs/ADR/0070-assinatura-com-franquia-mensal-expiravel.md` — status:
   substituído parcialmente por esta ADR (catálogo, durações, parcelamento e
   passe embutido). **§8.1 (reembolso) precisa de emenda:** por decisão do dono,
   o app passa a aplicar a regra proporcional desta ADR, com o risco registrado.
2. `docs/ADR/0043-temporada-trimestral-passe-e-customizacao.md` — atualizado
   nesta rodada apenas no status.
3. `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` — catálogo, passe, reembolso.
4. `docs/JOGA_DOCUMENTACAO_TECNICA.md` — entitlements, contratos e cobrança.
5. `docs/CONTRATO_RESERVAS_APP.md` — preço por meio e parcelamento (1x/3x do
   passe) e recusa de parcela.
6. `PLANS.md` e `PENDENCIAS.md` — fases de implementação e pendências
   jurídico/fiscais.

## Pendências

| # | Pendência | Gravidade | Depende de |
|---|---|---|---|
| 1 | Parecer jurídico sobre reembolso proporcional × CDC art. 49 | **P0, não bloqueia o app** | Jurídico |
| 2 | Parecer fiscal: 6% sobre comissão × 15,5% e base de cálculo | **P0** | Contador/advogado tributarista |
| 3 | Restringir faixa dos tickets grátis do passe ou subir para R$ 49,90 | **P0** | Produto + financeiro |
| 4 | Contrato do MP: recorrência/card-on-file, 1x, **taxa real do 3x** e escolha do modelo A/B | **P0** | Contrato/painel MP |
| 5 | Mecânica dos 12 tickets do passe (fixos × por nível) | P1 | Produto |
| 6 | Pro-rata da venda do passe no meio da temporada | P1 | Produto |
| 7 | Confirmar que a base legada está vazia e regra de migração | P1 | Dados |
| 8 | Desambiguação da numeração 0070 e uso das lacunas 0076/0077 | P2 | Documentação |
| 9 | NFS-e/recibo do passe e da assinatura | P2 | ADR 0068 + fiscal |
| 10 | Termos de Uso, checkout e política de reembolso alinhados à decisão do dono | **P0** | Jurídico + produto |
