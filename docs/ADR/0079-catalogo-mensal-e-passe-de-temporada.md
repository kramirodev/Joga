# ADR 0079 — Catálogo mensal 20/40/70 e passe de temporada separado

- **Status:** Proposto. Decisão financeira e de produto de 2026-11-28 registrada;
  pendente de parecer jurídico (reembolso × CDC) e fiscal (6% × 15,5%) antes de
  ser Aceito. **Nada foi implementado** em backend, app ou painel.
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

### 2. Cartão somente 1x, com o cliente absorvendo a taxa

1. **Não existe 3x nem 6x.** O cartão é cobrado em **uma parcela**.
2. O cliente absorve a taxa: `P_cartão = P_pix ÷ (1 − 5,49%)`, arredondado para
   cima. A taxa é 4,99% de MDR + 0,5% de provisão de chargeback; o acréscimo
   efetivo sobre o Pix é de 5,81%. Sem a provisão de 0,5%, os preços seriam
   R$ 3,58 / 3,37 / 3,27.
3. A apresentação correta é **“Pix R$ X; cartão R$ Y”** — dois preços de tabela,
   não uma taxa adicionada depois.
4. **Registro de conflito (6x × 1x).** O responsável pelo produto pediu
   parcelamento em **6x**. O parecer financeiro de 28/11 mostrou que o 6x sem
   juros exige preço dedicado e que o gross-up do Adendo A só preservaria a
   margem com preço percebido pior; a decisão registrada é **1x**. Enquanto não
   houver revisão financeira explícita, **1x prevalece** e o app não pode exibir
   parcela.

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
2. Preço: **R$ 42,50/temporada** no Pix (**R$ 44,97** no cartão 1x), equivalente
   a ~R$ 14,17/mês.
3. O passe **não tem tickets pagos**. Ele libera trilha, cosméticos,
   estatísticas avançadas, lobby privado, busca por CEP e os tickets grátis da
   trilha (ADR 0043 §5, §7 e §10 permanecem).
4. **Tickets:** free 6 por temporada; passe **+6**, total **12 por temporada**.
   Os grátis **expiram no fim da temporada** e não acumulam.
5. **Margem:** com 12 tickets e imposto de 15,5%, a margem fica em
   **12,3%–12,9%** (Pix/cartão); no cenário incremental de 6 tickets,
   45,7%–57,7%. A R$ 37,50 (equivalente ao antigo R$ 12,50/mês) a margem cai para
   3,4%–3,5% no cenário conservador; por isso o preço é R$ 42,50.
6. **Ressalva de faixa.** A R$ 42,50, o piso de 10% só se sustenta se os tickets
   grátis forem usados na faixa de referência (R$ 2,50/ticket) ou se houver
   restrição de faixa. No premium (R$ 2,68/ticket), a margem cai para **7,5%**
   (cartão, 15,5%) / 7,8% (Pix, 15,5%). Duas saídas: **restringir os tickets
   grátis às faixas elegíveis** (Econômica e Padrão dia, como o crédito de
   estreia da ADR 0042 §7) ou **subir o passe para R$ 49,90**. A escolha é
   pendência (§Pendências), e o passe fica **aprovado com ressalva** até ela.
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

### 6. Reembolso proporcional ao não usado

1. **Assinatura mensal:**
   `reembolso = tickets_não_usados × P_pago × (1 − s)`, onde `P_pago` é o preço
   por ticket efetivamente recebido e `s` o custo do meio (0,99% Pix; 4,99%
   cartão 1x; 5,49% com chargeback). O que foi consumido é cobrado pelo preço do
   plano; o mês pago não volta.
2. **Sem uso e dentro de 7 dias:** reembolso do valor líquido da taxa; se o PSP
   devolver a taxa, reembolso cheio.
3. **Passe:**
   `reembolso = (meses_não_usados ÷ 3) × 42,50 − (tickets_grátis_resgatados × 2,50) − taxa_do_meio`.
   Resultado negativo significa **sem reembolso**. Exemplo: 1 mês usado e 6
   tickets resgatados → R$ 13,33 menos a taxa; 12 tickets resgatados →
   reembolso zero.
4. **Conflito com CDC art. 49 e ADR 0070 §8.1.** A regra vigente garante
   reembolso **integral em 7 dias**, sem desconto de tickets usados. A regra
   proporcional é **proposta financeira**, não regra vigente: exige emenda à ADR
   0070 e parecer jurídico. **O app e o painel não podem prometer a regra
   proporcional antes disso**; até a decisão, prevalece o texto da ADR 0070 §8.

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

1. Esta ADR é **Proposto**. Código, contrato e preço só mudam depois de Aceito,
   com parecer jurídico (reembolso) e fiscal (alíquota/base) anexados.
2. Até lá, o catálogo em produção continua o da ADR 0070 e o app não exibe
   20/40/70 nem o passe separado.

## Conflitos registrados

| # | Conflito | Onde | Situação |
|---|---|---|---|
| 1 | **CDC art. 49 × reembolso proporcional.** CDC e ADR 0070 §8.1 garantem reembolso integral em 7 dias; a decisão de 28/11 propõe proporcional ao não usado, com desconto de tickets resgatados. | ADR 0070 §8.1; CDC art. 49; §6 desta ADR | **Aberto — prevalece a regra vigente** até parecer jurídico e emenda. Não prometer no app. |
| 2 | **6x × 1x.** O dono pediu 6x; o parecer chegou a modelar 6x com gross-up (Adendo A) e 6x com juros (modelo B); a decisão de 28/11 fixou **somente 1x**. | §2; parecer §3, §4 e §12 | **Fechado por decisão financeira em 1x**, revisável apenas com nova análise. |
| 3 | **Fiscal 6% × 15,5% e base de cálculo.** 6% sobre a comissão é a conta; Anexo V (15,5%) é o stress. Se a base for a receita cheia, o plano de 70 fica em 2,4% e o passe no premium em 7,5%. | ADR 0049; §8 | **Aberto — pendente de parecer fiscal.** Precificação do 70 e do passe depende disso. |
| 4 | **Numeração de ADR.** O parecer manda formalizar em “0075”, que já é Supabase; 0076/0077 são lacunas; existem dois arquivos 0070 (assinatura e pedido de entrada em clã). | `docs/ADR/` | **Aberto — esta ADR usa 0079.** Renumeração/desambiguação do 0070 fica para rodada própria; nenhum arquivo é renumerado aqui. |
| 5 | **Mecânica dos 12 tickets do passe.** A ADR 0043 §2.1 dá 2 tickets a cada 5 níveis (teto 12); a decisão de 28/11 fala em “6 grátis + 6 do passe”. | ADR 0043 §2.1; §4, item 4 desta ADR | **Aberto — decidir se os 6 extras são fixos ou distribuídos por nível.** |
| 6 | **Passe a R$ 42,50 no premium.** O preço fecha na referência, mas cai a 7,5% no 4x4 premium com 15,5%. | §4, item 6; parecer §6 | **Aberto — restringir faixa ou subir para R$ 49,90.** |
| 7 | **Bundle 20 + passe.** O cliente que pagava R$ 204/temporada passa a pagar R$ 246,50 (+20,8%). | §4; parecer §7 | **Risco comercial registrado**, não conflito documental. |

## Consequências

### Positivas

- Catálogo cai de 7 SKUs para **3 planos + 1 passe**, com uma duração só.
- O 6x sai do produto e com ele o principal consumidor de margem.
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
| 7 | Reembolso proporcional × CDC | Alta | Insegurança jurídica e reclamação | Não prometer no app; parecer + emenda à ADR 0070 |
| 8 | NFS-e ausente | Alta | Autuação e imposto acumulado | Provisionar; emitir mensalmente quando formalizado |
| 9 | Canibalização do 20 pelo passe | Média | Mix pior, margem blended menor | Vender o passe pelo benefício, não como ticket |

### Critérios de aceite (quando Aceito)

1. O catálogo ativo tem **exatamente** 3 planos mensais e 1 passe; nenhum SKU
   trimestral/semestral é vendável.
2. O checkout oferece **Pix e cartão 1x**; qualquer requisição com parcela > 1 é
   rejeitada pelo backend (não apenas escondida no app).
3. O preço do cartão é calculado por **gross-up versionado**, nunca digitado no
   app; mudança de taxa exige nova versão de preço, não edição do histórico.
4. Assinatura e passe são **entitlements distintos**: um não libera o outro.
5. Recorrência com consentimento, 3 tentativas e suspensão do mês seguinte;
   passe cobrado uma vez.
6. Reembolso implementado **somente** na regra jurídica aprovada; enquanto o
   conflito do CDC existir, o fluxo é o da ADR 0070 §8.
7. Repasse à quadra em `starts_at + 2h` pelo valor cheio, comprovado por teste.
8. Chargeback suspende franquia e novas compras, sem clawback da quadra.
9. Migração do legado honra lotes `purchase` sem validade e ciclos já pagos.
10. Testes de idempotência da cobrança, autorização negativa, repetição de
    webhook, falha de PSP e concorrência na concessão de franquia.

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
- Preço de cartão por gross-up versionado; taxa e provisão parametrizadas.
- Reembolso conforme a regra jurídica vigente; cálculo do passe isolado.
- Repasse e chargeback conforme §7; nenhum desconto no repasse da quadra.
- Migração/limpeza de planos e convivência com lotes `purchase` legados.

### App mobile

- Trocar “trimestre” por “mês” na tela de assinatura.
- Exibir 20/40/70 com dois preços (Pix e cartão 1x); **sem 3x/6x**.
- Separar visualmente o **passe de temporada** da assinatura de tickets.
- Mostrar 6 grátis do free e +6 do passe, com aviso de expiração no fim da
  temporada.
- Consentimento de recorrência, cancelamento, falha de pagamento e a regra de
  reembolso vigente.

### Painel/site

- Catálogo de 3 planos + passe, com preço por meio de pagamento.
- Margem por plano, passe, uso (`u`) e faixa; provisão de chargeback.
- Receita diferida do passe (1/3 por mês) e receita mensal da assinatura.
- Conciliação de recorrência, falhas, estornos e chargebacks.
- Sem promessa de split/repasse automático.

### Testes

- Catálogo: 3 planos, 1 passe, nenhum SKU antigo vendável.
- Parcela > 1 rejeitada no servidor.
- Gross-up: tabela de preço por versão; arredondamento para cima.
- Recorrência: 3 tentativas, suspensão do mês seguinte, cancelamento.
- Passe: cobrança única, expiração dos tickets, pro-rata opcional.
- Reembolso: regra vigente + casos-limite do passe (resultado negativo).
- Repasse cheio e chargeback sem clawback.
- Autorização negativa, idempotência e repetição de webhook.

## Documentos a atualizar (fora do escopo desta rodada)

1. `docs/ADR/0070-assinatura-com-franquia-mensal-expiravel.md` — status:
   substituído parcialmente por esta ADR (catálogo, durações, parcelamento e
   passe embutido); §8.1 permanece vigente até o parecer jurídico.
2. `docs/ADR/0043-temporada-trimestral-passe-e-customizacao.md` — atualizado
   nesta rodada apenas no status.
3. `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` — catálogo, passe, reembolso.
4. `docs/JOGA_DOCUMENTACAO_TECNICA.md` — entitlements, contratos e cobrança.
5. `docs/CONTRATO_RESERVAS_APP.md` — preço por meio de pagamento e recusa de
   parcela.
6. `PLANS.md` e `PENDENCIAS.md` — fases de implementação e pendências
   jurídico/fiscais.

## Pendências

| # | Pendência | Gravidade | Depende de |
|---|---|---|---|
| 1 | Parecer jurídico sobre reembolso proporcional × CDC art. 49 | **P0** | Jurídico |
| 2 | Parecer fiscal: 6% sobre comissão × 15,5% e base de cálculo | **P0** | Contador/advogado tributarista |
| 3 | Restringir faixa dos tickets grátis do passe ou subir para R$ 49,90 | **P0** | Produto + financeiro |
| 4 | Contrato do MP: recorrência, card-on-file e 1x | **P0** | Contrato/painel MP |
| 5 | Mecânica dos 12 tickets do passe (fixos × por nível) | P1 | Produto |
| 6 | Pro-rata da venda do passe no meio da temporada | P1 | Produto |
| 7 | Confirmar que a base legada está vazia e regra de migração | P1 | Dados |
| 8 | Desambiguação da numeração 0070 e uso das lacunas 0076/0077 | P2 | Documentação |
| 9 | NFS-e/recibo do passe e da assinatura | P2 | ADR 0068 + fiscal |
