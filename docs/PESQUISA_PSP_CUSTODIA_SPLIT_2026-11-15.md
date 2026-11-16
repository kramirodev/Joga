# Pesquisa — PSPs, subadquirentes e BaaS para marketplace de reservas

**Pergunta:** quais provedores brasileiros atendem aos cinco requisitos eliminatórios
(saldo de terceiros por pagador, N liberações futuras, quadra como *merchant of record*,
recebedor só com dados bancários, estorno por evento)?

**Data da consulta:** 15/11/2026 (todas as citações abaixo foram lidas nesta data).
**Escopo:** documentação oficial de API, páginas de preço, rodapé legal dos provedores e
dados abertos do Banco Central. Marketing sem documentação foi tratado como "não verificado".

> **Nota de reescopo (mesma data).** O pedido foi reduzido a **dois essenciais**: (i) o dinheiro
> da quadra não pode ser da JOGA em nenhum intervalo; (ii) uma conta de terceiro, em instituição
> autorizada, com titular ≠ JOGA, que paga a quadra por instrução no evento. As seções 1 a 10
> continuam válidas como levantamento dos cinco requisitos originais, mas **a decisão passa a ser
> lida pela seção 11**, que responde só aos dois essenciais.

---

## 1. Veredito

**Nenhum dos provedores analisados atende aos cinco requisitos com documentação pública.**

E isso não é acidente de mercado: três pares de requisitos são estruturalmente incompatíveis
entre si no arranjo brasileiro (seção 3). O resultado útil não é uma lista de "quem atende",
é saber **qual requisito cada um quebra** e **qual desenho cobre os cinco**.

| # | Requisito | Situação no mercado |
|---|---|---|
| 1 | Saldo de terceiros **individualizado por pagador**, fora do balanço, com segregação patrimonial | Nenhum adquirente oferece. Só existe como conta de pagamento de titularidade do jogador (BaaS) ou escrow/agente fiduciário |
| 2 | Uma captura → **N liberações futuras** com recebedor definido depois | Só o Stripe (cobranças e transferências separadas). No Brasil, nenhum split nativo faz isso |
| 3 | Quadra como **merchant of record** (NF-e e chargeback) | Só Zoop (`on_behalf_of` + `liable`) e Stripe (`on_behalf_of` + `losses_collector`) documentam isso explicitamente |
| 4 | Recebedor **só com dados bancários**, sem conta no PSP | Nenhum provedor com split. Iugu, Asaas e Efí proíbem explicitamente; Pagar.me e Zoop exigem credenciamento com KYC |
| 5 | **Estorno/retenção por evento** | Amplamente disponível, com ressalvas de granularidade |

**Os dois candidatos mais prováveis** (por motivos diferentes): **Zoop** (melhor aderência ao
requisito 3, o mais difícil de replicar) e **Stripe** (único com requisito 2 de verdade).
A combinação que cobriria os cinco é uma **arquitetura em duas camadas** (seção 7), não um
provedor único.

---

## 2. Enquadramento normativo (o que muda a leitura dos requisitos)

- **Lei 12.865/2013** define instituição de pagamento como a pessoa jurídica que, aderindo a
  arranjos, tenha como atividade "gerir conta de pagamento", "executar ou facilitar a instrução
  de pagamento", "credenciar a aceitação de instrumento de pagamento" ou "converter moeda física
  ou escritural em moeda eletrônica". Texto oficial:
  <https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12865.htm> (consulta 15/11/2026).
- **Resolução BCB 150/2021** disciplina a autorização e o funcionamento das instituições de
  pagamento (sucede a Circular 3.681/2013). Página oficial de normativos:
  <https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20BCB&numero=150>
  (consulta 15/11/2026 — o site do BCB é uma SPA e não entrega o texto por requisição direta;
  o texto consolidado deve ser obtido no próprio portal ou no DOU).
- **Resolução BCB 80/2021** disciplina os arranjos de pagamento (instituidor, participantes,
  regras). Mesma observação de acesso:
  <https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20BCB&numero=80>.
- **Regulamento Pix**: portal oficial <https://www.bcb.gov.br/estabilidadefinanceira/pix>
  (consulta 15/11/2026).
- **Pix não tem split nativo.** O Pix identifica **um** recebedor por transação (chave Pix). Não
  existe primitiva de múltiplos recebedores no regulamento. Todo "split Pix" é implementação do
  participante: a Efí descreve o próprio produto de split, a Celcoin tem "Split - Recebimento de
  Pix", a Zoop tem regras de divisão por transação. Isso importa porque significa que o split é
  **contratual e operacional**, não uma garantia do arranjo — cada provedor pode impor as
  restrições que quiser (e impõe: só contas próprias, limite de 20 contas, etc.).
- **Cuidado com homônimo:** "split payment" também é o nome do mecanismo de recolhimento de
  IBS/CBS da reforma tributária (manual publicado pelo CGIBS em set/2026:
  <https://cgibs.gov.br/upload/arquivos/202609/24101007-split-payment-manual-de-operacoes-v1-0-1.pdf>,
  consulta 15/11/2026). É outra coisa e **não foi analisado em profundidade aqui**; entra como
  risco/oportunidade da base tributária, a validar com tributarista.

### 2.1 Duas leituras do requisito 1 (e por que isso decide a resposta)

**(A) Leitura literal** — conta de pagamento de titularidade do **jogador**, saldo individualizado,
fora do balanço da plataforma, com segregação patrimonial.

**(B) Leitura funcional** — o dinheiro fica em conta de terceiro (recebedor) na instituição,
individualizado por transação, e nunca no caixa da plataforma.

A leitura (A) colide com o "sem saque" do próprio modelo: se o saldo é conta de pagamento do
jogador, o titular tende a ter direito de movimentá-lo; bloquear saque por decisão da plataforma
é exatamente o que a regulamentação de contas de pagamento tenta impedir. Ou seja, **"conta de
pagamento em nome do jogador" + "intransferível e sem saque" é uma contradição** que precisa de
parecer, não de PSP.

A leitura (B) é a que o mercado entrega — mas ela só resolve o balanço da plataforma se **100%
do valor da quadra for para a quadra na captura**, e aí não sobra nada para "liberar depois"
(requisito 2). É a tensão da seção 3.1.

---

## 3. As três tensões que impedem um provedor único

### 3.1 Requisito 1 × requisito 2 — alguém precisa custodiar no intervalo

Para liberar em N parcelas futuras, alguém guarda o dinheiro entre a captura e a liberação:

- se **a plataforma** controla a liberação, o saldo está na conta/balanço dela (ativo, ou
  passivo com o jogador como credor) → falha o requisito 1 e reabre a base tributária;
- se **o jogador** é o titular, ele pode sacar → falha o "sem saque" e o crédito deixa de ser
  pré-pago;
- se **a quadra** é a titular desde a captura, a plataforma não pode programar liberação → falha
  o requisito 2.

Só o **escrow/agente fiduciário** (ou conta de garantia bancária) resolve os três ao mesmo tempo:
o dinheiro não é da plataforma, não é sacável pelo jogador e é liberado por instrução conforme
condição contratual.

### 3.2 Requisito 3 × requisito 4 — MoR no cartão exige credenciamento

Ser *merchant of record* no arranjo de cartão significa ser o estabelecimento credenciado: passa
por KYC, aceita o regulamento da bandeira e responde pelo chargeback. Nenhum provedor credencia
um recebedor "só com dados bancários". Quem aceita recebedor só com dados bancários (Pix/TED out)
não o coloca como MoR — a plataforma fica como contratante e o chargeback sobra para ela.

### 3.3 Requisito 1 "por pagador" não é produto de adquirência

Adquirência individualiza por **recebedor** (seller/recebedor/subconta), não por pagador. Conta
por pagador é produto de *wallet* (BaaS) ou de escrow. Nenhum dos PSPs de split oferece isso.

---

## 4. Fichas por candidato

> Convenção: ✅ atende · 🟡 atende parcialmente · ❌ não atende · ❓ indeterminado/não público.

### 4.1 Stripe — "Separate charges and transfers" (Connect)

- **Produto exato:** Stripe Connect, tipo de cobrança *Separate charges and transfers*
  (`PaymentIntent` na plataforma + `Transfer` com `source_transaction`, `transfer_group`,
  `on_behalf_of`).
- **Status BCB:** "Stripe Brasil Soluções de Pagamento Ltda. — Instituição de Pagamento,
  CNPJ 22.121.209/0001-46 … opera na modalidade de credenciadora" (rodapé de
  <https://stripe.com/br>, consulta 15/11/2026). Número do ato de autorização: **não público de
  forma consolidada — confirmar no contrato/DOU**.
- **1. Saldo por pagador — ❌ (no Brasil).** A segregação existe, mas é *private preview* e não
  está disponível no Brasil: *"Funds segregation lets you allocate funds from separate charges and
  transfers to a holding state on your platform account before transferring them to connected
  accounts. Funds in this state don't appear in your platform balance, and you can only transfer
  them to a connected account."* E a lista de disponibilidade é: *"BE CH DE DK ES FR GB NL SE US"*
  — **Brasil fora**. Além disso, a própria doc veta a combinação com MoR: *"Don't use the
  `on_behalf_of` parameter when creating the PaymentIntent."*
  Fonte: <https://docs.stripe.com/connect/funds-segregation> (consulta 15/11/2026).
  Sem a segregação, o dinheiro fica no saldo da plataforma: *"Your account balance is debited for
  the cost of the Stripe fees, refunds, and chargebacks."*
- **2. N liberações futuras — ✅.** *"Create separate charges and transfers to transfer funds from
  one payment to multiple connected accounts, or when a specific user isn't known at the time of
  the payment. The charge on your platform account is decoupled from the transfers to your
  connected accounts."* E: *"You don't need to transfer the full payment amount in a single
  transfer or to a single connected account. You can split allocated funds across multiple
  transfers, as long as the total doesn't exceed the original payment amount."*
  Disponível no Brasil: a lista de regiões inclui *"Brazil"*. Não há agendador nativo — a
  plataforma dispara cada transferência quando quiser (cron próprio).
  Fonte: <https://docs.stripe.com/connect/separate-charges-and-transfers> (consulta 15/11/2026).
- **3. Quadra como MoR — 🟡/❓.** A matriz oficial de MoR permite exatamente isso: *"Connected
  account | … | Separate charges and transfers | With `on_behalf_of`"*, e o MoR é definido como
  *"the entity that the customer understands they're buying from … responsible for the transaction
  and for providing customer recourse in scenarios such as refunds and disputes"*. O chargeback
  pode ser alocado à conta conectada via `losses_collector: "stripe"` nas contas v2.
  **Ressalva:** não localizei confirmação pública de que `on_behalf_of` esteja habilitado para
  contas brasileiras → tratar como **não público — confirmar por conta Stripe/account manager**.
  Fontes: <https://docs.stripe.com/connect/merchant-of-record>,
  <https://docs.stripe.com/connect/accounts-v2> (consulta 15/11/2026).
- **4. Recebedor só com dados bancários — ❌.** Exige conta conectada com KYC (documento, data de
  nascimento, endereço, dados bancários de mesma titularidade). Não é "só dados bancários".
- **5. Estorno por evento — ✅.** Reembolso parcial por cobrança e reversão de transferência
  individual (`transfer reversals`), sem afetar as demais transferências da mesma cobrança.
- **Custo:** 3,99% + R$ 0,39 por transação no cartão; 1,19% no Pix
  (<https://stripe.com/br/pricing>, consulta 15/11/2026). Tarifa de transferência/payout e
  mensalidade do Connect: **não público — confirmar com comercial**. Saldo retido: não remunera.
- **Limitações:** segregação indisponível no BR e em preview; `on_behalf_of` × segregação são
  mutuamente exclusivos; sem agendamento nativo; KYC obrigatório do recebedor.
- **Links:** doc de API acima; central de ajuda <https://support.stripe.com>; termos
  <https://stripe.com/br/legal>; status regulatório no rodapé de <https://stripe.com/br>.

### 4.2 Zoop — "Split de Pagamentos" + "Conta Gráfica"

- **Produto exato:** Zoop Payments (API v1/v2.8) — `POST /v1/marketplaces/{id}/transactions` com
  `split_rules` (a priori) e `POST …/transactions/{id}/split_rules` (a posteriori); conta gráfica
  do seller; `on_behalf_of`.
- **Status BCB:** **não localizado** no catálogo de dados abertos do BCB nem declaração de
  entidade/CNPJ no site → **não público — confirmar por contrato de adesão e lista oficial de IPs
  do BCB**. (O site apenas afirma atender "às exigências regulatórias do Banco Central".)
- **1. Saldo por pagador — 🟡.** Há conta individualizada por **recebedor**, mantida na Zoop e não
  na plataforma: *"Todos os sellers credenciados ao Marketplace e aprovados, terão sua conta
  gráfica criada automaticamente, onde ficarão todos os valores transacionados, gerando saldo em
  conta"*, com *"current_blocked_balance: Saldo bloqueado para liquidação"*. Não é conta por
  **pagador** — é por seller. Segregação patrimonial depende do status de IP da Zoop (não
  confirmado).
  Fontes: <https://docs.zoop.co/docs/saldo-em-conta>,
  <https://docs.zoop.co/docs/conta-grafica-zoop> (consulta 15/11/2026).
- **2. N liberações futuras — 🟡.** Permite definir o recebedor **depois** da captura, mas só até
  a primeira liquidação: *"Suporte a configuração de regras de divisão no momento da criação da
  transação (a priori), ou então após a transação (a posteriori), até a data anterior a primeira
  liquidação do recebível."* Não é "N liberações ao longo do tempo"; é "N regras antes do primeiro
  pagamento".
  Fonte: <https://docs.zoop.co/docs/split-de-pagamentos> (consulta 15/11/2026).
- **3. Quadra como MoR — ✅ (o melhor da lista).** Os exemplos oficiais usam
  `"on_behalf_of": "{{seller_id}}"`, e o campo `liable` resolve o chargeback no recebedor:
  *"liable: define se o recebedor arca com prejuízo em caso de chargeback ou não. 1 ou (true)
  arca; 0 ou (false) não arca."* É a única documentação brasileira que trata explicitamente as
  duas metades do requisito 3 (MoR e chargeback).
  Fontes: <https://docs.zoop.co/docs/split-rules>,
  <https://docs.zoop.co/reference/post_v1-marketplaces-marketplace-id-transactions-transaction-id-split-rules-1>
  (consulta 15/11/2026).
- **4. Recebedor só com dados bancários — ❌.** Exige credenciamento com KYC: *"será necessário
  informar os dados cadastrais, documentos de identificação (Documento e Selfie) e dados
  bancários tokenizados de mesma titularidade"*, após o que *"automaticamente será criada uma
  conta Zoop"*.
  Fonte: <https://docs.zoop.co/docs/credenciamento> (consulta 15/11/2026).
- **5. Estorno por evento — ✅ (com ressalva).** Estorno total ou parcial por transação
  (*"retornando um valor total ou parcial de uma cobrança"*) e remoção de regra de split
  individual. A ressalva é a mesma do requisito 2: o que já liquidou não se desfaz por split.
  Fonte: <https://docs.zoop.co/docs/estornando-transacoes> (consulta 15/11/2026).
- **Custo:** **não público — confirmar com comercial** (MDR e tarifa de split/transferência são
  negociados; não há tabela pública). Saldo retido: não remunera.
- **Limitações:** recebedor precisa de credenciamento e conta bancária de mesma titularidade;
  split a posteriori só antes da primeira liquidação; conta gráfica é do seller, não do pagador.
- **Links:** <https://docs.zoop.co>, <https://ajuda.zoop.com.br>, termos em
  <https://www.zoop.com.br>.

### 4.3 Pagar.me / Stone — "Split" + "Recebedores"

- **Produto exato:** Pagar.me API v5 — `POST /core/v5/orders` com `payments[].split`
  (`type`, `amount`/`percentage`, `recipient_id`); `POST /recipients` com
  `register_information` + `default_bank_account` + `transfer_settings`.
- **Status BCB:** opera sob **Stone Instituição de Pagamento S.A.**, CNPJ 16.501.555/0001-57,
  *"Instituição de pagamento autorizada pelo Banco Central do Brasil, nas modalidades de
  credenciadora e emissora de moeda eletrônica"* (rodapé de <https://www.pagar.me>, consulta
  15/11/2026). Não é IP própria da marca Pagar.me.
- **1. Saldo por pagador — 🟡.** Saldo individualizado por **recebedor**: *"Um `recipient` é um
  recebedor … Dentro do ambiente Pagar.me é atribuído um saldo a esse recebedor"*. A plataforma é
  a loja (EC) e o valor transita pelo saldo dela antes de liquidar → **não fica fora do balanço
  da plataforma**.
  Fonte: <https://docs.pagar.me/docs/recebedores-2> (consulta 15/11/2026).
- **2. N liberações futuras — ❌.** O split é definido na criação do pedido, com `recipient_id`
  conhecido: *"Utilizando a funcionalidade de Split, você pode criar um pedido que terá mais de
  um recebedor."* Há agendamento de **saque** do recebedor (diário/semanal/mensal), mas não de
  liberação por reserva:
  *"Ao ativar o saque automático para um recebedor, o Pagar.me efetua transferências de acordo com
  a periodicidade configurada (diariamente, semanalmente ou mensalmente)"*.
  Fonte: <https://docs.pagar.me/docs/pedidos-com-split> (consulta 15/11/2026).
- **3. Quadra como MoR — ❌.** No modelo de marketplace da Pagar.me a plataforma é a loja/EC e os
  demais são recebedores; não há parâmetro equivalente a `on_behalf_of` para deslocar o MoR, nem
  alocação explícita de chargeback por recebedor na documentação pública.
- **4. Recebedor só com dados bancários — 🟡.** Não exige login nem conta operada pela quadra:
  cria-se o `recipient` com `default_bank_account` + `register_information` (CPF/CNPJ, endereço,
  KYC). É "cadastro com dados bancários e KYC", não "apenas dados bancários".
  Fonte: <https://docs.pagar.me/reference/criar-recebedor-1> (consulta 15/11/2026).
- **5. Estorno por evento — 🟡.** Estorno por transação/pedido existe; a reversão do split
  acompanha o estorno do pedido. Se uma cobrança cobrir N reservas, o estorno é do pedido inteiro.
- **Custo:** tabela em <https://www.pagar.me/precos>, mas o split está restrito a
  *"clientes PSP"* — **"Esta funcionalidade está disponível apenas para clientes PSP"** — o que
  implica contrato de facilitador e MDR negociado. Valores: **não público — confirmar com
  comercial**.
- **Limitações:** split só para cliente PSP; recebedor precisa de KYC; plataforma é a EC.
- **Links:** <https://docs.pagar.me>, <https://docs.pagar.me/docs/pedidos-com-split>,
  <https://ajuda.pagar.me>.

### 4.4 Mercado Pago — "Split de Pagamentos 1:1" / `marketplace_fee`

- **Produto exato:** Split de Pagamentos (checkout com `marketplace`), comissão via
  `marketplace_fee` e access token por vendedor (OAuth).
- **Status BCB:** **Mercado Pago IP Ltda.** — consta no catálogo de dados abertos do BCB como
  `SFN - MERCADO PAGO IP LTDA.` (consulta 15/11/2026 via API CKAN
  `dadosabertos.bcb.gov.br/api/3/action/package_search`). Número do ato: não público de forma
  consolidada — confirmar no DOU/contrato.
- **1. Saldo por pagador — 🟡.** Saldo por vendedor (conta MP). A plataforma não custodia, mas a
  conta é do vendedor, não do pagador.
- **2. N liberações futuras — ❌.** Split na captura; existe liberação programada (`money_release`)
  como **uma** data por pagamento, não N liberações com recebedor definido depois.
- **3. Quadra como MoR — 🟡.** A comissão do marketplace é destacada e o vendedor recebe o
  líquido: *"Ambos os checkouts realizam automaticamente a divisão dos valores entre o vendedor e
  o marketplace por meio do split de pagamentos"* e *"A comissão do Mercado Pago é descontada do
  valor recebido pelo vendedor."* Mas não há parâmetro público de MoR/chargeback por recebedor.
  Fonte:
  <https://www.mercadopago.com.br/developers/pt/docs/split-payments/split-1-1/integration-configuration/integrate-marketplace>
  (consulta 15/11/2026).
- **4. Recebedor só com dados bancários — ❌.** Exige conta MP e autorização OAuth: *"utilizando
  um access token para cada vendedor, obtido através de OAuth"*.
- **5. Estorno por evento — 🟡.** Estorno por pagamento; o `marketplace_fee` é devolvido conforme
  regra do split.
- **Custo:** tabela em <https://www.mercadopago.com.br/costs>; **não público para split
  negociado — confirmar com comercial**.
- **Limitações:** conta MP obrigatória para o recebedor; sem MoR explícito; liberação programada
  única.

### 4.5 iugu — "Split de Pagamentos" (Conta Mestre + Subcontas)

- **Status BCB:** *"iugu Instituição de Pagamento S/A. CNPJ: 15.111.975/0001-64"* (rodapé de
  <https://www.iugu.com>, consulta 15/11/2026).
- **1. 🟡** saldo por subconta (recebedor), não por pagador.
- **2. ❌** split definido na fatura; *"a conta criadora da fatura divida e transfira os valores
  automaticamente assim que o pagamento for realizado"*.
- **3. 🟡** a subconta é o destino; sem MoR/chargeback explícito.
- **4. ❌ — o mais explícito do mercado:** *"É possível realizar o split para contas não iugu?
  Não. Hoje, a divisão de valores é realizada apenas entre contas iugu (mestre e sub)."*
- **5. 🟡** reembolso por fatura (`POST /v1/invoices/{id}/refund`) e estorno; reversão de split
  acompanha a fatura.
- **Custo:** **não público — confirmar com comercial** (plano Marketplace).
- **Links:** <https://dev.iugu.com/docs/split-de-pagamentos>,
  <https://dev.iugu.com/docs/criar-verificar-e-configurar-subconta>.

### 4.6 Asaas — "Split de pagamento" (subcontas)

- **Status BCB:** **ASAAS IP S.A.** — `SFN - ASAAS IP S.A.` no catálogo de dados abertos do BCB
  (consulta 15/11/2026).
- **1. 🟡** saldo por subconta/wallet, não por pagador.
- **2. ❌** split na criação da cobrança, com `walletId` conhecido.
- **3. 🟡** sem MoR explícito; o recebedor é uma conta Asaas.
- **4. ❌ — explícito:** *"cada recebedor deve possuir uma conta Asaas"*.
- **5. 🟡** *"Quando uma cobrança com Split é estornada, os repasses relacionados também são
  estornados."* — funciona por evento **se** cada reserva for uma cobrança.
- **Custo:** <https://www.asaas.com/precos> (consulta 15/11/2026; página bloqueou leitura
  automatizada — **confirmar valores no site/contrato**).
- **Links:** <https://docs.asaas.com/docs/split-de-pagamentos>,
  <https://docs.asaas.com/docs/criacao-de-subcontas>.

### 4.7 Efí — "Split de pagamento Pix"

- **Status BCB:** *"Efí S.A. CNPJ 09.089.356/0001-18 — Efí, Instituição de Pagamento"* (rodapé de
  <https://sejaefi.com.br>, consulta 15/11/2026).
- **1. 🟡** repasses para contas Efí; sem conta por pagador.
- **2. ❌** split configurado por cobrança/`txid` antes do recebimento.
- **3. 🟡** sem MoR/chargeback explícito (e é Pix, sem chargeback de cartão).
- **4. ❌ — explícito:** *"O Split de pagamento Pix só pode ser realizado entre contas Efí, com
  limite máximo de 20 contas para o repasse."*
- **5. 🟡** devolução Pix por `txid` (inclusive parcial), com efeito sobre o split conforme
  configuração.
- **Custo:** **não público — confirmar com comercial** (tarifas por transação Pix).
- **Links:** <https://dev.efipay.com.br/docs/api-pix/split-de-pagamento-pix/>,
  <https://sejaefi.com.br>.

### 4.8 Nota — Celcoin (BaaS), o candidato "camada de custódia"

- **Status BCB:** **CELCOIN IP S.A.** — `SFN - CELCOIN IP S.A.` no catálogo de dados abertos
  (consulta 15/11/2026).
- **O que oferece (nav da doc, consulta 15/11/2026):** "Gestão de Contas" (abertura/encerramento,
  saldo, extrato), **"Agendador de Transação Pix — Agendar uma transação Pix / Cancelar um Pix
  agendado"** e **"Split - Recebimento de Pix"**.
- **Por que entra:** é o único perfil que ataca os requisitos **2** (agendamento de N Pix futuros
  de valor variável) e **4** (Pix para qualquer banco, por chave/dados) de forma nativa.
- **O que não resolve:** requisito **3** (não é adquirente/MoR; não há `on_behalf_of` documentado)
  e requisito **1** na leitura literal (a conta é do titular cadastrado — a definir se jogador ou
  quadra; e "saldo bloqueado" para conta de terceiro é terreno jurídico sensível).
- **Custo:** **não público — confirmar com comercial**.
- **Link:** <https://developers.celcoin.com.br/docs>.

---

## 5. Tabela comparativa

| Candidato | 1. Saldo por pagador | 2. N liberações | 3. Quadra MoR | 4. Recebedor só banco | 5. Estorno por evento | Status BCB | Custo público |
|---|:--:|:--:|:--:|:--:|:--:|---|---|
| **Stripe Connect** | ❌ (segregação fora do BR) | ✅ | 🟡/❓ | ❌ | ✅ | IP/credenciadora (rodapé) | 3,99% + R$0,39; Pix 1,19% |
| **Zoop** | 🟡 (por seller) | 🟡 (só até 1ª liquidação) | ✅ (`on_behalf_of` + `liable`) | ❌ (KYC + selfie) | ✅ | não confirmado | sob consulta |
| **Pagar.me/Stone** | 🟡 (por seller, passa pela plataforma) | ❌ | ❌ | 🟡 | 🟡 | Stone IP (credenciadora) | sob consulta |
| **Mercado Pago** | 🟡 | ❌ | 🟡 | ❌ (OAuth) | 🟡 | Mercado Pago IP Ltda. | sob consulta |
| **iugu** | 🟡 | ❌ | 🟡 | ❌ (só contas iugu) | 🟡 | iugu IP S/A | sob consulta |
| **Asaas** | 🟡 | ❌ | 🟡 | ❌ (conta Asaas) | 🟡 | Asaas IP S.A. | sob consulta |
| **Efí** | 🟡 | ❌ | 🟡 | ❌ (só contas Efí) | 🟡 | Efí S.A. IP | sob consulta |
| **Celcoin** (BaaS) | 🟡/❓ | ✅ (Pix agendado) | ❌ | ✅ | ✅ | Celcoin IP S.A. | sob consulta |

**Nenhuma coluna tem cinco ✅ em uma linha.** O requisito 4 é o mais violado (7 de 8 ❌ ou 🟡),
seguido do 2 (6 de 8 ❌).

---

## 6. Os dois candidatos mais prováveis

### 6.1 Zoop — melhor aderência ao requisito 3

**Por quê:** é o único produto brasileiro cuja documentação pública desloca o MoR para o
recebedor (`on_behalf_of`) **e** aloca o chargeback no recebedor (`liable`). Isso é o coração
do requisito 3 e o que protege a plataforma de ser a "vendedora" para fins de cartão e de
estorno. Também é o único com conta gráfica de recebedor pronta (sem conta bancária própria
obrigatória para operar o dia a dia).

**Onde quebra:** requisito 4 (KYC + selfie + conta de mesma titularidade) e requisito 2 (split
só até a primeira liquidação).

**Próximo passo de validação (Zoop):**
1. Pedir por escrito ao comercial/ jurídico: (a) status de IP e número do ato de autorização;
   (b) se `on_behalf_of` pode ser usado junto com conta gráfica e qual o efeito no comprovante/
   extrato do portador; (c) teto de `liable` e como o chargeback é debitado do seller sem
   alcançar a plataforma.
2. Teste em sandbox: captura única, `split_rules` a posteriori em 3 momentos antes da 1ª
   liquidação, estorno parcial de 1 reserva e verificação de que os demais recebíveis não mudam.
3. Perguntar o que acontece com split já liquidado quando há estorno parcial (é o caso que
   derruba o requisito 5 na prática).

### 6.2 Stripe Connect — melhor aderência ao requisito 2

**Por quê:** é o único que separa **de verdade** a captura da transferência: N transferências
parciais por cobrança, recebedor escolhido no momento da transferência ("or when a specific user
isn't known at the time of the payment"), com MoR configurável e reversão individual de
transferência. É o desenho que o requisito 2 pede, palavra por palavra.

**Onde quebra:** requisito 1 no Brasil (segregação é preview e não cobre BR; e é incompatível com
`on_behalf_of`) e requisito 4 (conta conectada com KYC).

**Próximo passo de validação (Stripe):**
1. Confirmar com o account manager: (a) `on_behalf_of` habilitado para contas brasileiras;
   (b) previsão/requisitos para liberar *funds segregation* no BR; (c) se existe alternativa de
   custódia segregada para BR (conta de garantia/escrow) no contrato.
2. Teste em sandbox: 1 `PaymentIntent` + 3 `Transfer` parciais com `source_transaction`,
   `transfer_group` por reserva, e `TransferReversal` de uma delas.
3. Modelar o pior caso: se a segregação continuar indisponível no BR, o saldo fica no balanço da
   plataforma — e o requisito 1 morre. Decidir antes de integrar.

---

## 7. Arquitetura em duas camadas (a única que cobre os cinco)

Como nenhum provedor cobre os cinco, o desenho viável separa **adquirência/MoR** de
**custódia/liberação**:

```
Jogador ──cartão/Pix──► [Camada A: adquirente com MoR = quadra]
                              │  captura; comissão da plataforma sai no split
                              ▼
                        [Camada B: custódia segregada]
                        conta de garantia / escrow (agente fiduciário ou IP)
                              │  N liberações programadas, por reserva
                              ▼
                        conta bancária da quadra (dados bancários)
```

- **Camada A (MoR e chargeback):** Zoop (`on_behalf_of` + `liable`) ou Stripe
  (`on_behalf_of` + `losses_collector`). A plataforma entra só como recebedor de taxa.
- **Camada B (custódia e liberação):** conta de garantia/escrow com agente fiduciário ou IP
  (Celcoin/Zoop conta gráfica) que (i) não é conta da plataforma, (ii) é individualizada por
  reserva, (iii) libera por instrução em N parcelas.
- **Requisito 4** é atendido na ponta da Camada B (Pix/TED para qualquer banco por dados
  bancários), não na Camada A — que sempre exigirá KYC do recebedor.
- **Requisito 1 na leitura literal** (conta em nome do jogador) continua sem produto pronto:
  exigiria conta de pagamento do jogador (BaaS) com o problema do saque, ou escrow com o jogador
  como beneficiário. **Recomendação:** adotar a leitura funcional (saldo de terceiro segregado,
  individualizado por reserva) e registrar a decisão em ADR, porque a leitura literal conflita
  com "intransferível e sem saque".

**O que validar juridicamente antes de contratar:**
1. Escrow/conta de garantia: quem é o titular, quem é o beneficiário, o que acontece na
   insolvência da plataforma e da quadra.
2. Se a plataforma, ao instruir liberação, pratica "gestão de conta de pagamento" (Lei 12.865 +
   Res. BCB 150/2021) sem autorização.
3. Se o arranjo desenhado pela plataforma configura "arranjo de pagamento" (Res. BCB 80/2021)
   sujeito a autorização.
4. Base tributária: comissão x receita bruta, no regime de competência e na transição IBS/CBS.

---

## 8. Conflito com as decisões já registradas no JOGA

Este levantamento **contradiz** parte do que está aprovado no repositório — registro explícito,
conforme `AGENTS.md` §1:

- **ADR 0042 §1.4** exige "conta segregada", mas **§5.7** admite: *"A provisão de 100% do passivo
  é política interna de liquidez, não segregação jurídica. Em insolvência, o portador do ingresso
  é credor quiroquistário."* O requisito 1 do pedido é exatamente o que falta ali.
- **ADR 0042 §2.7** diz que a intransferibilidade é o que mantém o ingresso como crédito de
  serviço e **não** conta de pagamento. O requisito 1, na leitura literal ("conta de pagamento em
  nome do jogador"), desfaz esse guardrail.
- **ADR 0048** (aprovada em 15/11/2026) determina custódia centralizada no Mercado Pago, *"Não há
  split, recebedor automático nem promessa de repasse automático"*, e lista como critério de
  revisão *"Exigência regulatória, de custódia ou de split pelo modelo de negócio"*. **Este
  levantamento aciona esse critério.**
- **ADR 0021/0034** apontam Pagar.me Flex como produção; a doc atual mostra split **restrito a
  "clientes PSP"** e sem MoR por recebedor — a premissa precisa ser revalidada.

**Decisão pendente (não tomada aqui):** manter custódia centralizada (simples, mas com o
problema de balanço/quirografia) ou migrar para o desenho em duas camadas (mais caro e mais
lento, mas alinhado ao objetivo de base tributária na comissão).

---

## 9. O que não é público (confirmar por qual canal)

| Informação | Onde confirmar |
|---|---|
| Número do ato de autorização de cada IP | Contrato de adesão do provedor + DOU; lista oficial de IPs do BCB |
| Status regulatório da Zoop (IP própria? opera via terceiro?) | Contrato de adesão Zoop + BCB |
| `on_behalf_of` habilitado para contas Stripe no Brasil | Account manager Stripe |
| Disponibilidade de *funds segregation* no Brasil | Account manager Stripe |
| MDR, tarifa de split, tarifa de transferência, mensalidade | Comercial de cada provedor |
| Se o saldo retido rende (e para quem) | Contrato de adesão |
| Teto/limite de `liable` e tratamento de chargeback já liquidado | Jurídico Zoop |
| Efeito do estorno parcial sobre recebíveis já liquidados | Sandbox + contrato |
| Tratamento de escrow/conta de garantia por agente fiduciário | Vórtx, Oliveira Trust, BTG/Itaú (escrow) — **não verificado nesta pesquisa** |

---

## 10. Limitações desta pesquisa

- O portal do BCB é uma SPA e não entrega o texto das resoluções por requisição direta; as
  resoluções foram citadas por identificação e link oficial, **sem transcrição literal de
  artigos**. Confirmar a redação vigente antes de usar em parecer.
- O catálogo de dados abertos do BCB (`dadosabertos.bcb.gov.br`) cobre parte das instituições;
  **ausência no catálogo não prova ausência de autorização**.
- Preços: apenas Stripe tem tabela pública legível; os demais são negociados.
- Não foram testadas APIs em sandbox; todas as conclusões vêm de documentação.
- O "split payment" da reforma tributária (CGIBS) não foi analisado.
- Data de referência de todas as leituras: **15/11/2026**. Documentação de PSP muda com frequência.

---

## 11. Reescopo de 15/11/2026 — resposta apenas aos dois essenciais

**Pergunta vigente:** (i) o dinheiro da quadra não pode ser da JOGA em nenhum intervalo entre a
compra do ingresso e a partida; (ii) uma conta de terceiro, em instituição autorizada, cujo
titular não é a JOGA, que paga a quadra por instrução no evento. Todo o resto da lista original
passa a ser indiferente.

### 11.1 O que "titular ≠ JOGA" elimina de saída

Produtos em que a conta é do **contratante** (ou do recebedor credenciado) não servem, mesmo que
tenham split, agendamento ou bloqueio:

| Produto | Por que falha | Evidência |
|---|---|---|
| **Locker Account (Fits)** | é conta **vinculada a uma conta regular do próprio cliente**, com dados bancários fornecidos pelo cliente | "Every Locker account is linked to a regular account" · "The BU provides the bank, branch, account and digit of the Locker account" — <https://dev.fits.com.br/docs/onboarding-locker-account.md> (consulta 15/11/2026) |
| **Subcontas iugu / Asaas / Efí / Zoop / Pagar.me** | titular é a plataforma ou o recebedor credenciado, e o crédito é **imediato** — não há "pagar no evento" | seção 4 desta pesquisa |
| **Saldo de plataforma (Stripe sem segregação, Pagar.me)** | o dinheiro fica no saldo/balanço da plataforma | seção 4.1 |
| **Mercado Pago centralizado (ADR 0048)** | a captura cai na **conta MP da JOGA**; o dinheiro da quadra é, no intervalo, um passivo da JOGA | ADR 0048 + §5.7 da ADR 0042 |

Sobra **uma única classe** capaz de atender aos dois essenciais: **conta de escrow / conta
vinculada cujo titular é a própria instituição ou uma estrutura fiduciária (agente de garantia)**,
operada por procuração pela JOGA e liberada por instrução no evento. É o que existe de fato no
mercado brasileiro, e não é produto de adquirência.

### 11.2 Fits — "Conta Escrow" (1º candidato)

- **Instituição:** "O FITS INSTITUIÇÃO DE PAGAMENTO S.A., inscrita no CNPJ/MF sob nº
  13.203.354/0001-85 … é instituição de pagamento autorizada pelo Banco Central do Brasil, na
  forma da Lei nº 12.865/2013" — rodapé de <https://www.fitbank.com.br/escrow> (consulta
  15/11/2026). **Número do ato de autorização: não público — confirmar no contrato e no Unicad.**
- **O que a página promete, literalmente:**
  - "Custódia que move o dinheiro como o contrato determina."
  - "Abra rápido e libere sob as regras da operação: **split, lastro, agente de garantia** e trilha
    auditável em cada liquidação."
  - "**Conta Escrow** — … Abra e assine a conta online, opere via app ou Internet banking e
    **parametrize procuradores automaticamente**."
  - "**Desembolso** — … Libere desembolso com liquidação imediata e split com parametrização de
    lastro."
  - "**Agente de garantia** — Dê ao agente de garantia prova do fluxo sem pedir relatório a
    ninguém. Configure perfis de visualização e autorização."
  - Versão EN: "set **attorneys** automatically" / "Give the **collateral agent** proof of the
    flow … Configure viewing and authorization profiles" (<https://fits.com.br/en/escrow>).
- **Por que isso importa para os dois essenciais:** "procuradores" e "agente de garantia com
  perfis de autorização" são exatamente os dois mecanismos necessários — **titular** (quem é dono
  da conta) separado de **quem instrui** (JOGA, por procuração). Se o contrato titularizar a conta
  no agente de garantia/estrutura, o essencial (i) está atendido por construção.
- **O que a documentação pública NÃO tem:** não existe endpoint de escrow em
  <https://dev.fits.com.br>. O que existe é conta de pagamento (`NewAccountCompany`), **Locker**
  (subconta do cliente — não serve, ver 11.1), Pix/TED/PixOut, **Future Posting** (agendamento) e
  **Payment Order**. Ou seja: **a titularidade da Conta Escrow é comercial/contratual, não
  documentada** — é o ponto a fechar antes de qualquer integração.
- **Encaixe operacional:** cobrança por boleto/Pix/TED na própria conta (sem adquirente), extrato e
  conciliação por API, desembolso Pix/TED para a quadra por dados bancários (sem conta na Fits) e
  agendamento para o repasse de `starts_at + 2h` (ADR 0040). Não há cartão de crédito nesse
  desenho.
- **Custo:** **não público — confirmar com comercial@fits.com.br** (tarifa de abertura, mensalidade,
  tarifa por Pix/TED de desembolso, tarifa por conta escrow).

### 11.3 Oliveira Trust — "Conta Vinculada" (2º candidato)

- **Instituição:** "a Oliveira Trust Distribuidora de Títulos e Valores Mobiliários S.A. (CNPJ nº
  36.113.876/0001-91), é instituição devidamente autorizada a funcionar pelo Banco Central do
  Brasil (BACEN) … atuando na prestação de serviços especializados, tais como: Agente Fiduciário,
  Administração Fiduciária, Gestão de Recursos de Terceiros, Custódia, Escrituração, **Conta
  Vinculada**, dentre outros" — rodapé de
  <https://www.oliveiratrust.com.br/servicos/conta-vinculada> (consulta 15/11/2026).
- **O que a página diz, literalmente:** "Esta inovação introduz uma **conta de pagamento, dedicada
  às operações financeiras estruturadas**, facilitando o acompanhamento de fluxos financeiros e
  permitindo a **retenção de recursos para assegurar o cumprimento das obrigações de cada
  operação**."
- **Serviço irmão:** "Atuamos como **Agente de Garantias**, Agente Administrativo ou Trustee …
  Monitoramos contratos de garantia … e centralizamos a comunicação"
  (<https://www.oliveiratrust.com.br/servicos/agente-garantias>).
- **Por que é o encaixe mais próximo do pedido:** é a única das duas em que a instituição **já é**
  a fiduciária da operação — o desenho natural é a conta vinculada da operação (titular = estrutura
  fiduciária/OT), com a JOGA apenas ordenando desembolsos conforme contrato. O essencial (i) não
  depende de invenção contratual; depende de adesão a um produto que existe para isso.
- **O que não é público:** contrato, taxa de adesão, taxa por operação, existência de API/portal
  para instrução automática, e se o produto aceita operações de **varejo** (milhares de reservas de
  R$ 30–80) — o material comercial é de mercado de capitais. **Confirmar com o comercial da OT.**
- **Risco principal:** custo fixo e operação desenhada para tickets altos. Mesmo atendendo aos dois
  essenciais, pode ser inviável em ticket de reserva.

### 11.4 Mercado Pago — o caminho barato, mas condicionado

O único jeito de manter o MP (ADR 0048) sem o dinheiro passar pela JOGA é o **recebedor ser a
quadra** (split/OAuth) com **liberação programada** — nesse caso quem custodia no intervalo é o
MP e quem paga a quadra na data é o MP, não a JOGA.

- **O que está documentado:** o Split 1:1 do MP "is designed to provide Payment Service Provider
  (PSP) services to sellers in marketplace models" e "splits payments between your company and each
  participant in a transaction"
  (<https://www.mercadopago.com.br/developers/en/docs/split-payments/split-1-1/overview.md>,
  consulta 15/11/2026). **A mesma página não documenta liberação futura/retida** — o texto fala de
  divisão, não de prazo.
- **Portanto:** atende (i) com folga; atende (ii) **somente se** existir liberação programada por
  reserva no contrato da conta da quadra. Isso é **não público — confirmar com o gerente de contas
  do MP**, com uma pergunta fechada: *"é possível definir a data de liberação de cada pagamento
  para `starts_at + 2h`, sem o valor transitar pela conta do marketplace?"*
- **Custo:** MDR do MP, sem tarifa adicional de custódia (a confirmar).

### 11.5 Quadro de decisão

| Opção | (i) dinheiro nunca é da JOGA | (ii) terceiro paga a quadra no evento | O que falta |
|---|:--:|:--:|---|
| **Fits Conta Escrow** | ✅ se o titular for o agente de garantia/estrutura | ✅ desembolso por instrução + Future Posting | confirmar titularidade, procuradores e preço |
| **Oliveira Trust Conta Vinculada** | ✅ por desenho (conta da operação, retenção) | ✅ por contrato, desembolso pela OT | confirmar API/portal, taxa e viabilidade em ticket baixo |
| **MP com recebedor = quadra + liberação** | ✅ | 🟡 só com liberação programada | confirmar liberação por pagamento |
| **MP centralizado (ADR 0048 atual)** | ❌ | ❌ | mudaria a decisão, não o fornecedor |

### 11.6 Script único de validação (enviar aos dois)

1. Quem é o **titular** da conta escrow/vinculada no contrato: a JOGA, a instituição ou o agente de
   garantia? (pedir minuta)
2. A JOGA pode ser apenas **procuradora/ordenadora**, com poderes limitados a instruir desembolso
   para o beneficiário definido no contrato?
3. A **liberação por evento** pode ser disparada por **API/webhook** (ex.: `POST` de desembolso em
   `starts_at + 2h`)? Qual o SLA de liquidação Pix?
4. O beneficiário (quadra) pode receber **só com dados bancários**, sem abrir conta na instituição?
5. O que acontece na **insolvência da JOGA**: os recursos ficam fora da massa? (pedir cláusula)
6. **Estorno** antes da liberação: a JOGA ordena, ou o jogador tem direito de sacar? (tem que ser a
   JOGA, por contrato)
7. **Preço**: abertura, mensalidade, tarifa por desembolso, tarifa de manutenção da conta escrow.
8. Existe **conta escrow por reserva** ou uma conta por quadra/operação? Qual o custo de cada
   arranjo?

### 11.7 Limites desta seção

- Nenhuma das duas instituições publica a **titularidade** da conta escrow. A conclusão "atende" é
  condicional à resposta do item 1 do script.
- Não foi possível verificar `swap.com.br`, `quitech.com` e `hash.com.br` (DNS/TLS indisponíveis
  neste ambiente); podem existir outros provedores de escrow não cobertos.
- O número do ato de autorização das duas instituições deve ser conferido no **Unicad/BCB**, não só
  no rodapé do site.
- Conflito registrado: esta seção **não** altera a ADR 0042 nem a ADR 0048. Se a decisão for
  adotar escrow de terceiro, é preciso **ADR nova** revogando o §5.7 da 0042 e o modelo centralizado
  da 0048.
