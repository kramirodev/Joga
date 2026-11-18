# ADR 0049 — Modelo tributário do ingresso: intermediação em conta alheia

- **Status:** Aprovado como direção em 2026-11-15. **Bloqueado para produção com
  dinheiro real** até os pareceres da seção 10.
- **Data:** 2026-11-15
- **Decisores:** responsável pelo produto. Pendente de homologação por contador e
  advogado tributarista.
- **Relaciona:** ADR 0021 (precificação), ADR 0039 (cancelamento e ausência),
  ADR 0040 (repasse), ADR 0042 (ingresso e natureza da intermediação),
  ADR 0043 (passe trimestral), ADR 0048 (Mercado Pago no protótipo),
  `docs/PESQUISA_PSP_CUSTODIA_SPLIT_2026-11-15.md`,
  `docs/JURIDICO_PENDENCIAS.md`.
- **Substitui, no que conflitar:** ADR 0042 §1.2, §2.2, §2.6, §3 (tabela 2D como
  preço) e §5.7; ADR 0042 §2.1 (unidade de conta); ADR 0048 §5 (centralização do
  valor na conta da JOGA), **condicionado** à decisão de custódia da seção 2.8.

---

## 0. Natureza deste documento

Este documento **não é parecer jurídico nem parecer fiscal**. Ele registra uma
decisão de modelagem e o raciocínio que a sustenta, para que contador e advogado
possam validá-la ou derrubá-la com base em texto legal, e para que produto e
engenharia não implementem nada incoerente com ela.

Marcação usada em todo o texto:

| Marca | Significa |
|---|---|
| **[F]** | Fato documentado no repositório ou em fonte oficial citada |
| **[D]** | Decisão tomada neste documento |
| **[I]** | Interpretação jurídica ou contábil — **não vinculante**, sujeita a revisão |
| **[H]** | Hipótese que **exige validação profissional** antes de produzir efeito |

Regra de leitura: nada marcado **[I]** ou **[H]** pode ser tratado como
conclusão. Se a única coisa que sobrar de um parágrafo for uma dessas marcas, o
parágrafo é uma pergunta, não uma resposta.

---

## 1. Contexto

O fluxo comercial do JOGA é: o jogador compra crédito antes de existir partida;
semanas depois entra em uma partida; nesse momento uma quadra parceira é
reservada e o valor é dividido entre quadra e plataforma.

A ADR 0042 fixou a natureza de **intermediação** e a base de cálculo na
**comissão**, mas deixou três furos que este documento fecha:

1. **Devedor do saldo.** A §1.2 declara que o saldo é "obrigação do JOGA com o
   jogador". Isso é adiantamento — dinheiro da JOGA —, não custódia de terceiro.
   A §1.4 exige "conta segregada", mas a §5.7 admite que a provisão de 100% é
   "política interna de liquidez, **não segregação jurídica**", e que em
   insolvência o portador é credor quiroquistário. **[F]**
2. **Preço.** A tabela 2D produz margem efetiva variável entre 10,2% e 22,6%
   conforme o preço da quadra (§3.5). Margem que varia com o custo do insumo é
   comportamento de revenda, não de agência. **[I]**
3. **Unidade de conta.** A §2.2 exige que o jogador "veja apenas ingressos". Um
   crédito que não é expresso em reais é mais difícil de conciliar e mais fácil
   de ser lido como produto próprio. **[I]**

A ADR 0048 agravou o item 1 ao determinar que o Mercado Pago **centraliza o
valor** na conta da JOGA, com repasse manual e sem split. No intervalo entre a
compra e a partida, o dinheiro da quadra é, tecnicamente, um passivo da JOGA.
**[F]**

A pesquisa de 15/11/2026 conclui três coisas que restringem o desenho: **[F]**

- Nenhum PSP/adquirente brasileiro entrega saldo individualizado **por pagador**
  com segregação patrimonial. O que existe é saldo por **recebedor**.
- "Conta de pagamento em nome do jogador" + "intransferível e sem saque" é uma
  **contradição**: o titular de conta de pagamento tende a ter direito de
  movimentar o saldo.
- A única classe que mantém o dinheiro fora do balanço da plataforma **e** sem
  saque pelo jogador é **conta de escrow / conta vinculada com titular ≠ JOGA**,
  operada por procuração.

### 1.1 Correção em relação à recomendação anterior

Em conversa, a recomendação foi "caminho B: dinheiro na JOGA, em conta vinculada
no PSP, separada do caixa operacional". A pesquisa de 15/11/2026 mostra que essa
formulação é **insuficiente**: conta no nome da JOGA, ainda que em PSP, continua
sendo dinheiro da JOGA — a separação é operacional, não patrimonial. **[F]**

Portanto a taxonomia correta tem **três** modelos, não dois:

| Modelo | Quem é titular do dinheiro no intervalo | Saque pelo jogador | Segregação real | Custo/atrito |
|---|---|:--:|:--:|---|
| **A** — conta de pagamento do jogador (BaaS) | jogador | sim, por natureza | sim | KYC por usuário, custo por conta, contradiz "sem saque" |
| **B** — conta da JOGA (PSP ou banco) | JOGA | não | **não** | baixo; mantém float; pior defesa fiscal |
| **C** — escrow / conta vinculada, titular ≠ JOGA | instituição ou agente de garantia | não | sim | contrato, custo fixo, integração |

**[D] Decisão:** o alvo é **C**. O protótipo pode operar em **B** enquanto C não
estiver contratado, assumindo explicitamente que, em B, a tese de conta alheia é
**mais fraca** e depende inteiramente de contrato, mandato e cadeia de notas.

**A está descartada:** não porque seja impossível, mas porque (i) contradiz o
guardrail de intransferibilidade e ausência de saque que a própria ADR 0042 §2.7
identifica como o que separa crédito de serviço de conta de pagamento, e (ii)
implica KYC e custo por usuário incompatíveis com o estágio. **[D]/[I]**

---

## 2. Decisão

### 2.1 Natureza da relação

**[D]** O JOGA atua como **intermediador por mandato**, em nome e por conta do
jogador, na contratação do espaço esportivo. Não adquire o espaço, não subcontrata
e não revende.

### 2.2 Base de cálculo

**[D]** A base de cálculo dos tributos sobre a receita é a **comissão de
intermediação**. O valor destinado à quadra não é receita do JOGA em nenhum
momento: nem na compra do crédito, nem na confirmação da reserva, nem no repasse.

### 2.3 Unidade de conta

**[D]** O saldo passa a ser expresso **em reais**. A unidade "ingresso" deixa de
ser unidade de conta; ela é a **unidade de consumo** da tabela 2D (§13) e não tem
efeito jurídico, contábil ou fiscal. O valor em reais é sempre visível antes da
confirmação. **Não há conversão 1:1 entre ticket e real:** a tabela 2D mapeia o
valor da quadra e o formato para uma quantidade de tickets, e o ledger lança o
valor em reais.

O limite que o jogador define para o matchmaking é expresso em **créditos**, não
em reais digitados. Como o saldo é expresso em reais, o limite é monetário por
construção, sem exigir que o jogador informe um valor em dinheiro.

Isso contraria a ADR 0042 §2.2 e a substitui.

### 2.4 Preço

**[D]** A expressão de custo da ADR 0021 (`c·V + C_k + C_c·μ·S + p_t·V`) **continua
existindo como cálculo interno** de piso e calibração. O que o jogador vê são duas
linhas, ambas em reais:

```
Uso do espaço — Estabelecimento ....... R$ 150,00
Taxa de intermediação JOGA ............ R$  18,00
```

Regras associadas:

1. Percentual **uniforme** para todas as quadras. Percentual negociado por arena
   é indício de atacado/revenda. **[I]**
2. Percentual divulgado nos Termos, não na tela. **[D]**
3. Custo de PSP, provisão de cancelamento e "fator de risco" **nunca** aparecem
   como linha na fatura, na nota ou nos Termos. São custo interno da comissão.
   Expor "fator de risco" é confessar que a plataforma assume o risco da operação
   — exatamente o que define conta própria. **[I]**
4. O valor exibido é a soma exata da expressão interna, sem arredondamento
   criativo. **[D]**

### 2.5 Crédito

**[D]** O crédito comprado:

- **não expira**;
- **não é transferível**, revendível ou permutável;
- **não é sacável**;
- **não gera rendimento** para o jogador nem para o JOGA;
- **não gera breakage**: saldo não usado jamais é reconhecido como receita.

O §5.8 da ADR 0042 já decidia que o float não é receita e que ingresso não usado
não é resultado. Este documento mantém a decisão e acrescenta a razão: reconhecer
saldo não usado como receita é, além de tudo, cláusula potencialmente abusiva
(CDC art. 51) e enriquecimento sem causa (CC art. 884). **[I]**

### 2.6 Passe trimestral — tratamento distinto

**[D]** O passe **não é crédito**. É **assinatura de franquia mensal**: o objeto
é a disponibilização de uma cota mensal de partidas, não a venda de saldo.

Consequência fiscal: a receita do passe é reconhecida **no mês**, pela
disponibilização da franquia, independentemente de o jogador usá-la. Não há
breakage porque não há crédito; há serviço prestado. **[I]**

Consequência consumerista: a franquia não acumulada precisa estar descrita de
forma inequívoca como **assinatura com cota mensal**, sob pena de ser lida como
venda de crédito com confisco. **[H]**

Por isso o passe fica **fora** do fluxo de escrow: não há valor de terceiro a
custodiar.

### 2.7 Cadeia documental

**[D]** Em cada partida:

| Documento | Emitente | Tomador | Valor |
|---|---|---|---|
| NFS-e de locação/uso do espaço | estabelecimento | **jogador** (CPF informado na reserva) | preço do espaço |
| NFS-e de intermediação | JOGA | jogador | comissão |

O JOGA **nunca** recebe nota do estabelecimento pelo espaço. Receber essa nota é
o ato que materializa compra e revenda. **[I]**

### 2.8 Custódia

**[D]** Requisito: o dinheiro destinado à quadra **não pode ser da JOGA em nenhum
intervalo** entre a compra e a partida.

Duas fases, declaradas:

- **Fase protótipo (B):** conta separada do caixa operacional, ledger por jogador,
  reconhecimento como passivo. Aceito com risco fiscal declarado.
- **Fase comercial (C):** escrow / conta vinculada com titular ≠ JOGA, JOGA como
  procuradora com poderes limitados a instruir desembolso ao estabelecimento
  definido na reserva.

A escolha do fornecedor de C **não é decidida aqui** — exige ADR própria, com as
respostas do script de validação da §11.6 da pesquisa de PSP.

---

## 3. Por que isso é intermediação

Esta seção é o núcleo do documento. Ela é escrita para ser lida por quem vai
**contestar** o modelo, não para quem quer concordar com ele.

A lei não define intermediação por vocabulário. Define por **posição econômica**.
O teste decisivo está na LC 123/2006, art. 3º, §1º, que define receita bruta como
"o produto da venda de bens e serviços nas operações de **conta própria**, o preço
dos serviços prestados e **o resultado nas operações em conta alheia**". **[F]**

Ou seja: a lei já prevê duas coisas diferentes. Em conta própria, tributa-se o
valor cheio. Em conta alheia, tributa-se **o resultado** — a comissão. A pergunta
"posso tributar só a comissão?" é, na prática, "esta operação é conta alheia?".

Conta alheia não é declaração de vontade. É um conjunto de fatos verificáveis. A
seguir, os sete testes, na ordem em que um fiscal os aplicaria.

### 3.1 Teste 1 — Natureza da obrigação assumida

**O que se verifica:** o JOGA se obriga a *prestar o uso de um espaço* ou a
*aproximar as partes e executar o pagamento*?

**Como o modelo responde:** o objeto do contrato com o jogador é a intermediação
e a execução de pagamento. O objeto do contrato com a quadra é o repasse do valor
do espaço. O JOGA não promete o espaço: promete contratá-lo em nome do jogador.

**O que sustenta:** a descrição do objeto nos dois contratos, a nota fiscal
(§2.7) e o fato de o JOGA não ter estoque, não ter disponibilidade própria e não
poder realocar a reserva para outra quadra sem nova autorização.

**O que quebra:** cláusula do tipo "o JOGA garante a realização da partida em
qualquer quadra disponível". Isso é promessa de resultado sobre bem alheio —
obrigação de quem vende, não de quem intermedeia. **[I]**

### 3.2 Teste 2 — Titularidade do dinheiro no intervalo

**O que se verifica:** entre o pagamento e a prestação, de quem é o dinheiro?

**Como o modelo responde:** em C, o dinheiro está em conta de terceiro; o JOGA é
ordenador. Em B, o dinheiro está na JOGA como passivo — e aqui a resposta é
**pior**, sem eufemismo.

**O que sustenta:** extrato da conta de escrow, contrato de custódia, procuração
com poderes limitados, e a trilha de que a JOGA nunca teve livre disposição.

**O que quebra:** usar o saldo como capital de giro, investir o float, pagar
despesa própria com o saldo, ou prometer ao jogador que "o dinheiro está
guardado" quando ele está no caixa da empresa. **[I]**

Este é o teste mais frágil do modelo em B. Em C ele passa por construção.

### 3.3 Teste 3 — Quem contrata o espaço

**O que se verifica:** quem é o contratante perante o estabelecimento?

**Como o modelo responde:** o jogador, por meio de **mandato** (CC art. 653).
O JOGA recebe poderes para, em nome do jogador, reservar, pagar e cancelar. Nos
termos do CC art. 116, a manifestação de vontade do representante, nos limites dos
poderes, produz efeitos **em relação ao representado**. **[F]**

**Por que o matchmaking não destrói isso:** mandatário pode escolher. O mandato
não exige que o mandante escolha pessoalmente a quadra; exige que a escolha seja
**em nome e por conta dele, dentro dos limites conferidos**. O modelo reforça os
limites com três mecanismos de produto: **[D]**

1. **Teto por partida, em créditos** — o jogador define o máximo de créditos que o
   matchmaking pode consumir. Como o crédito é expresso em reais na razão 1:1
   (§2.3), o teto é monetário por construção: não se pede ao jogador que digite
   um valor em reais, e ainda assim existe limite em dinheiro registrado.
2. **Lobby criado por usuário** — a partida nasce do jogador, não da plataforma.
3. **Votação para trocar a quadra** — a substituição é decisão dos participantes,
   com direito de recusa e devolução integral a quem discordar.

**Limite objetivo do mandato — regra de não absorção [D]:** independentemente do
teto do jogador, o mandato é limitado por uma regra verificável e não discricionária:

> O JOGA não contrata espaço cujo custo por jogador exceda o valor dos créditos
> consumidos naquela partida.

Se o custo exceder, a partida **não fecha**: o jogador é convidado a ampliar o
teto, mudar de faixa ou ampliar região/horário (ADR 0042 §6.5). A plataforma nunca
cobre a diferença com receita própria.

Essa regra é o que substitui o "teto em reais" e é mais forte que ele: não depende
de o jogador acertar um número, é determinística, auditável e demonstrável a
partir do ledger.

**O que sustenta:** a cláusula de mandato, o registro do teto aceito em créditos, a
reserva sair **no nome do jogador** no estabelecimento, e o histórico de que a
plataforma não decide sozinha.

**O que quebra:** reserva em nome do JOGA ("JOGA reservou"); contratar quadra mais
cara que o crédito arrecadado para "não frustrar o jogador"; ou qualquer lançamento
que cubra a diferença com receita da plataforma. Absorver diferença é assumir risco
de preço — que é precisamente o comportamento de dono. **[I]**

### 3.4 Teste 4 — Quem fixa o preço do espaço

**O que se verifica:** o preço do espaço é definido pelo estabelecimento ou pela
plataforma?

**Como o modelo responde:** pelo estabelecimento. A plataforma aplica percentual
uniforme sobre um preço que não negocia.

**O que sustenta:** tabela de preços da quadra no painel, histórico de reajuste
com autor e data (ADR 0042 §9.7), percentual uniforme, ausência de desconto por
volume na compra de horários.

**O que quebra:** negociar preço por arena; comprar blocos de horário com desconto
e revender; garantir "preço fechado" ao jogador independentemente do custo;
praticar preço diferente do praticado na portaria. Qualquer um desses transforma
a comissão em margem de revenda. **[I]**

### 3.5 Teste 5 — Quem assume o risco

**O que se verifica:** quem perde dinheiro se o espaço custar mais, se a quadra
não prestar, se houver chargeback, se ninguém aparecer?

**Como o modelo responde:**

| Risco | Quem assume | Instrumento |
|---|---|---|
| Preço do espaço subir | jogador (novo teto) | confirmação individual acima do teto |
| Quadra não prestar | quadra, perante o jogador | NFS-e da quadra ao jogador; devolução integral |
| No-show do jogador | jogador, conforme ADR 0039 | política de cancelamento |
| Chargeback | decisão pendente | contrato e política de MED |
| Ocupação da partida não completar | jogador / regra de partida | ADR 0039 |

**O que sustenta:** nenhum risco de resultado sobre o espaço estar alocado na
plataforma. A plataforma ganha a comissão **mesmo quando a partida é cancelada
com devolução**? Não — e isso é bom: se a comissão sobrevivesse ao cancelamento
sem serviço prestado, seria receita de risco, não de agência. **[I]**

**O que quebra:** cláusula de "garantia de realização", seguro oferecido pela
plataforma sem repasse, ou absorção de prejuízo da quadra para preservar o
jogador.

### 3.6 Teste 6 — Cadeia documental

**O que se verifica:** quem emite nota para quem.

**Como o modelo responde:** quadra → jogador; JOGA → jogador. Ver §2.7.

**O que sustenta:** as duas notas, com CPF do jogador na nota da quadra, e a
inexistência de nota da quadra contra o JOGA.

**O que quebra:** quadra emitindo contra o JOGA "porque é mais simples"; JOGA
emitindo nota do valor cheio; ou ausência de nota da quadra. A última é o risco
mais provável na prática, porque parte das arenas é informal ou não está
habilitada a emitir NFS-e no município. **[H]**

### 3.7 Teste 7 — Funções de pagamento exercidas

**O que se verifica:** a plataforma exerce atividade de instituição de pagamento
(Lei 12.865/2013; Res. BCB 150/2021 e 80/2021)?

**Como o modelo responde:** não, desde que não haja (i) conta de pagamento de
titularidade do jogador, (ii) saque, (iii) transferência entre usuários, (iv)
concessão de crédito, (v) emissão de moeda eletrônica.

**O que sustenta:** a intransferibilidade, a ausência de saque, a ausência de P2P
e o crédito ser vinculado a consumo.

**O que quebra:** permitir saque, transferência, "presente" de saldo, ou saldo
que sobreviva ao encerramento da conta do jogador em dinheiro. **[I]**

### 3.8 Síntese dos sete testes

| Teste | Situação em C | Situação em B |
|---|---|---|
| 1. Natureza da obrigação | passa | passa |
| 2. Titularidade do dinheiro | **passa por construção** | **frágil** |
| 3. Quem contrata | passa, com mandato e limites | passa, com mandato e limites |
| 4. Quem fixa o preço | passa, se não negociar | passa, se não negociar |
| 5. Quem assume o risco | passa | passa |
| 6. Cadeia documental | passa, se a quadra emitir | idem |
| 7. Funções de pagamento | passa | passa |

**Conclusão [I]:** em C, o modelo é sustentável nos sete testes. Em B, seis de
sete — e o que falha é justamente o mais visível para o fiscal. A diferença entre
"tributo sobre a comissão" e "tributo sobre o valor cheio" mora no teste 2.

---

## 4. Vetores de descaracterização

Lista do que transforma intermediação em revenda, em ordem de probabilidade. Cada
item é um veto operacional, não uma recomendação de estilo.

| # | Vetor | Por que descaracteriza | Mitigação |
|---|---|---|---|
| 1 | Absorver diferença de preço da quadra | assume risco de preço | regra de não absorção + confirmação individual |
| 2 | Negociar preço/volume por arena | posição de atacadista | percentual uniforme; preço vem da quadra |
| 3 | Receber nota da quadra pelo espaço | compra e revenda documentadas | nota sempre contra o jogador |
| 4 | Garantir a realização da partida | obrigação de resultado sobre bem alheio | obrigação é de meio: contratar em nome do jogador |
| 5 | Usar o saldo como capital de giro | dinheiro deixa de ser de terceiro | escrow (C) |
| 6 | Reter saldo não usado como receita | confisco + receita sem serviço | sem expiração, sem breakage |
| 7 | Prometer "preço fechado" ao jogador | preço próprio | preço do espaço sempre visível e destacado |
| 8 | Emitir nota do valor cheio | receita bruta declarada | nota só da comissão |
| 9 | Permitir saque/transferência | vira conta de pagamento | bloqueio técnico, não só contratual |
| 10 | Pagar a quadra antes da confirmação da reserva | antecipa compra | desembolso só no evento (ADR 0040) |

---

## 5. Fato gerador e momento

**[D]** Três eventos, três tratamentos:

| Evento | Contabilmente | Tributariamente | Documento |
|---|---|---|---|
| Compra do crédito | entra dinheiro, nasce obrigação (ou ativo de terceiro) | **nada** | recibo/comprovante |
| Confirmação da reserva | parte vira receita da comissão; parte vira obrigação com a quadra | **fato gerador da comissão** | NFS-e da comissão |
| Partida realizada / repasse | baixa da obrigação com a quadra | nada novo | comprovante de repasse |

**Por que a compra não é fato gerador [I]:** porque na compra não há serviço
prestado nem preço de serviço definido — há disponibilização de saldo. O serviço
do JOGA (intermediar) só existe quando há partida e quadra determinadas.

**Ressalva importante [H]:** no Simples Nacional a apuração é essencialmente de
**caixa**. A tese de que a compra não gera receita **não** se apoia em competência
— apoia-se em **natureza** (o dinheiro não é receita do JOGA). Se a autoridade
entender que o dinheiro é da JOGA, ele é receita no recebimento, e não em 2027.
Essa distinção precisa estar clara no parecer: **não é diferimento, é
não-incidência por natureza**. Confundir as duas coisas é o erro mais comum nesse
tipo de modelo. **[I]**

**Estornos e devoluções:** devolução de crédito não é receita negativa; é
reversão de passivo. Devolução após confirmação de reserva cancela a comissão
correspondente. **[I]**

---

## 6. Regime tributário

### 6.1 Simples Nacional

**[H]** Enquadramento esperado: serviço de intermediação, com receita bruta
composta apenas pela comissão.

- **Anexo V** (alíquota inicial de 15,5%) é o enquadramento provável para
  intermediação de serviços. **[H]**
- **Anexo III** (inicial de 6%) só se o **Fator R** for ≥ 28%, isto é, folha de
  salários + pró-labore ≥ 28% da receita bruta dos 12 meses anteriores. **[H]**
- **Conflito registrado [F]:** a ADR 0042 §5.2 usa "imposto de 6% sobre a comissão"
  no cálculo do piso de 10%. Se o enquadramento real for Anexo V, a alíquota
  efetiva sobe e **o piso de 10% pode não se sustentar**. O piso precisa ser
  recalculado com a alíquota real antes de qualquer decisão de preço.

### 6.2 ISS

**[H]** Serviço de agenciamento/intermediação, item 10 da lista anexa à
LC 116/2003. O subitem e a alíquota dependem do município do estabelecimento
prestador. A retenção pelo tomador também é municipal e varia. Confirmar com
contador, por município de operação.

**Ponto de atenção [I]:** se a nota da comissão for emitida contra o **jogador**
(pessoa física), a retenção normalmente não ocorre; se for contra a **quadra**
(pessoa jurídica), a retenção pode ser exigida pelo município do tomador. A
escolha de quem paga a taxa tem efeito operacional relevante.

### 6.3 Lucro Presumido (alternativa)

**[H]** Se a receita anual tornar o Simples inviável ou proibitivo:

- IRPJ/CSLL sobre base presumida (percentual de presunção aplicável a serviços);
- PIS/COFINS no regime cumulativo ou não cumulativo, conforme o caso;
- ISS municipal.

Ponto relevante: **no Lucro Presumido o custo da quadra também não reduz a base**
(a presunção incide sobre a receita bruta). Só no **Lucro Real** o custo entraria
como despesa dedutível. **[H]**

### 6.4 Reforma Tributária (LC 214/2025)

**[H]** Três efeitos a modelar:

1. **Transição** de CBS/IBS ao longo de vários anos, com alíquota-teste antes da
   vigência plena. Tratar "2027" como data única é simplificação perigosa.
2. **Split payment** do IBS/CBS: o tributo tende a ser segregado no momento da
   liquidação financeira. Isso **dificulta** a tese de repasse intocável se o
   fluxo não estiver documentalmente separado desde o início.
3. **Base de cálculo**: a discussão sobre o que é receita própria ganha uma
   segunda camada (ISS municipal + IBS estadual + CBS federal), e o desenho de
   escrow passa a ser vantagem, não custo.

### 6.5 Obrigações acessórias

**[H]** Emissão de NFS-e (padrão nacional), declarações do Simples ou do regime
escolhido, e conciliação entre PSP, ledger e extrato. Nenhuma delas existe hoje
no backend.

---

## 7. Contabilidade

**[D]** Estrutura mínima de contas:

| Conta | Natureza | O que registra |
|---|---|---|
| PSP em trânsito | ativo | recebido no PSP, ainda não liquidado |
| Bancos | ativo | conta da JOGA |
| Créditos de jogadores a liberar | passivo | saldo pré-pago ainda não aplicado |
| Obrigação com estabelecimentos | passivo | valor da quadra reconhecido na reserva, até o repasse |
| Receita de intermediação | resultado | comissão reconhecida na confirmação da reserva |
| Passe a apropriar | passivo | trimestre pago com mês ainda não disponibilizado |
| Receita de passe | resultado | franquia mensal disponibilizada |
| Imposto a recolher | passivo | apuração explícita, nunca calculada por alíquota no código |
| Despesa de imposto | resultado | contrapartida da apuração |
| Recebíveis (jogador / quadra) | ativo | valores a receber por reversão de crédito ou de repasse |
| Despesa de PSP | resultado | tarifa do PSP |
| Incobrável | despesa | baixa aprovada e auditada |
| Capital de abertura | patrimônio | contrapartida do cutover do ledger |

A lista completa, com códigos estáveis e as dezoito regras de lançamento, está em
`docs/DECISOES_BACKEND_ADR_0049.md` §9.2. Esta tabela é a versão normativa do
conceito; aquela é a versão executável.

**Lançamentos por evento (C):**

1. **Compra do crédito:** D PSP em trânsito — C créditos de jogadores a liberar.
2. **Confirmação da reserva:** D créditos de jogadores — C obrigação com
   estabelecimentos (valor da quadra) + C receita de intermediação (taxa).
   É aqui que a intermediação se completa: a quadra está contratada em nome do
   jogador e paga.
3. **Repasse:** D obrigação com estabelecimentos — C bancos.
4. **Devolução integral:** D obrigação com estabelecimentos + D receita de
   intermediação — C créditos de jogadores (ou C bancos/PSP em trânsito, se a
   devolução for em dinheiro). A receita é estornada, nunca editada.
5. **Venda de passe:** D PSP em trânsito — C passe a apropriar. No mês
   disponibilizado: D passe a apropriar — C receita de passe.
6. **Apuração de imposto:** D despesa de imposto — C imposto a recolher.

**Proibições contábeis [D]:**

- Reconhecer a venda de pacote como receita.
- Reconhecer saldo não usado como receita (breakage).
- Reconhecer a comissão antes da confirmação da reserva (ou seja, em
  `HOLD_CONFIRMED` ou `PAYMENT_PENDING`).
- Reconhecer a receita do passe antes da disponibilização do mês correspondente.
- Lançar rendimento de float como receita operacional.
- Compensar comissão com valor de quadra na mesma conta de resultado.

**Detalhamento executável [D]:** schema, sinais, plano de contas completo e as
dezoito regras de lançamento estão em
`docs/DECISOES_BACKEND_ADR_0049.md` §9.2. Dois pontos que complementam esta seção:

- O saldo do jogador (`player_credit`) nunca fica negativo. O que não couber nele
  vira receivable explícito contra o jogador, não passivo negativo.
- Imposto só entra no ledger por lançamento explícito de apuração. O código nunca
  calcula imposto a partir de alíquota.

---

## 8. Cláusulas obrigatórias nos Termos de Uso

Cada cláusula abaixo tem uma razão fiscal ou consumerista. Nenhuma é estilo.

### C1 — Objeto e natureza da relação

> O JOGA é plataforma de intermediação. Sua atividade é aproximar jogadores e
> estabelecimentos esportivos e executar, em nome do jogador, a contratação e o
> pagamento do espaço. O JOGA não é proprietário, locador, organizador do evento
> esportivo nem prestador do serviço de uso do espaço.

**Razão:** fixa a natureza antes de qualquer outra cláusula. É a primeira coisa
que um fiscal lê.

### C2 — Mandato

> O jogador constitui o JOGA seu mandatário para, em seu nome e por sua conta,
> contratar o espaço esportivo da partida confirmada e praticar os atos
> necessários à reserva, ao pagamento, ao cancelamento e à devolução.

**Razão:** CC art. 653. Sem mandato, o contratante é o JOGA.

### C3 — Limites do mandato

> O mandato é limitado pelo teto de créditos definido pelo jogador para cada
> partida e pela regra de não absorção: o JOGA não contrata espaço cujo custo por
> jogador exceda o valor dos créditos consumidos naquela partida. Ultrapassar
> qualquer desses limites exige confirmação individual do jogador.

**Razão:** poder limitado é o que distingue mandato de carta branca. O limite não
precisa ser digitado em reais: como o crédito é expresso em reais na razão 1:1,
um teto em créditos é um teto monetário. Excesso de mandato gera responsabilidade
do mandatário e aproxima a operação de conta própria.

### C4 — Não aquisição e não revenda

> O JOGA não adquire, não subcontrata e não revende o uso do espaço. O contrato de
> uso do espaço é celebrado entre o jogador e o estabelecimento.

**Razão:** é a negativa expressa do fato que caracterizaria revenda.

### C5 — Preço e composição

> O valor da partida é composto por (i) preço do espaço, definido pelo
> estabelecimento, e (ii) taxa de intermediação do JOGA, correspondente a
> [X]% do preço do espaço. Os dois valores são exibidos separadamente antes da
> confirmação.

**Razão:** transparência (CDC arts. 30 e 31) e separação entre preço alheio e
preço próprio.

### C6 — Natureza do saldo

> O saldo é crédito de consumo, expresso em reais, vinculado ao uso na plataforma.
> Não é conta de pagamento, não é moeda eletrônica, não rende, não é transferível,
> não é sacável e não pode ser cedido a terceiros.

**Razão:** afasta a incidência do regime de instituições de pagamento e sustenta
o teste 7.

### C7 — Inexistência de expiração

> O saldo comprado não expira. A franquia mensal do passe não se acumula e não se
> converte em saldo.

**Razão:** evita confisco e evita a leitura de breakage como receita. A segunda
frase separa assinatura de crédito.

### C8 — Direito de arrependimento

> O jogador pode desistir da compra no prazo de 7 dias, com devolução integral em
> dinheiro, pelo mesmo meio de pagamento. Passado esse prazo, o saldo não é
> convertível em dinheiro enquanto a conta estiver ativa; permanece disponível para
> uso e é devolvido em dinheiro no encerramento da conta, na forma da cláusula C13.

**Razão:** CDC art. 49. Devolução em crédito não satisfaz o direito. A segunda frase
existe para que a restrição seja **escrita**, e não descoberta pelo jogador: saldo
que não se converte em dinheiro é o que separa crédito de conta de pagamento
(vetor 9), mas restrição não declarada não é oponível. **[H]** A redação exata
depende de J5 e J6.

### C9 — Cancelamento, substituição, ausência e votação

> Regras de cancelamento, substituição de espaço, ausência e votação entre
> participantes, incluindo o direito de recusa com devolução integral ao
> participante que discordar da substituição.

**Razão:** a votação só é compatível com mandato se houver direito de saída;
sem ele, o dissidente é obrigado a contrato que não autorizou.

### C10 — Responsabilidade

> O serviço de uso do espaço é prestado pelo estabelecimento, que responde por
> sua qualidade, disponibilidade e adequação. O JOGA responde pela intermediação,
> pela cobrança, pela devolução e pelo tratamento de dados.

**Razão:** delimita o dever de meio. Não elimina a responsabilidade solidária
quando houver falha na cadeia de consumo — apenas não a assume preventivamente.

### C11 — Documentos fiscais

> O estabelecimento emite documento fiscal contra o jogador pelo valor do espaço.
> O JOGA emite documento fiscal contra o jogador pelo valor da taxa de
> intermediação.

**Razão:** torna a cadeia documental uma obrigação contratual, e não uma
consequência esperada.

### C12 — Custódia e insolvência (redação obrigatoriamente honesta)

> Os valores destinados ao espaço são mantidos em [conta de escrow / conta
> separada], sem livre disposição pelo JOGA. [Se em B: O saldo constitui crédito
> do jogador contra o JOGA, na forma da legislação aplicável.]

**Razão:** prometer segregação que não existe é representação enganosa
(CDC art. 37) e, em insolvência, gera litígio sobre promessa não cumprida. A
redação deve refletir o modelo efetivamente contratado, não o desejado.

### C13 — Suspensão e encerramento

> Hipóteses de suspensão, prazo, contraditório e recurso. No encerramento da conta,
> o saldo de crédito comprado é devolvido em dinheiro, pelo mesmo meio de
> pagamento, no prazo de [prazo] dias, e nunca convertido em crédito, transferido
> ou confiscado. A franquia mensal do passe já disponibilizada não é reembolsada;
> as mensalidades ainda não disponibilizadas são devolvidas proporcionalmente.
> Saldo originado de gratuidade (XP, promoção, cortesia) não é convertível em
> dinheiro.

**Razão:** a auditoria já apontou ausência de política de suspensão permanente. O
saldo não pode ser confiscado no encerramento; a regra precisa estar escrita. A
última frase separa dinheiro de liberalidade: o que o jogador pagou volta; o que
recebeu de graça não vira saque, o que também fecha a porta para lavagem de
crédito promocional. **[H]** O prazo e a obrigatoriedade da devolução em dinheiro
dependem de J6/J7.

### C14 — Atendimento, foro e lei aplicável

> Canal de atendimento, prazo de resposta, foro do domicílio do consumidor e
> legislação brasileira.

**Razão:** Decreto 7.962/2013 e CDC.

---

## 9. Cláusulas obrigatórias no contrato com o estabelecimento

A tese fiscal não vive só nos Termos do jogador. Ela depende do fornecedor:

1. **Obrigação de emitir documento fiscal contra o jogador**, com o CPF
   informado na reserva, no prazo legal.
2. **Preço informado é o preço final ao jogador** — vedação de cobrança por fora.
3. **Vedação de emissão de nota contra o JOGA** pelo uso do espaço.
4. **Teto de preço por faixa** e aviso prévio de reajuste (ADR 0042 §9).
5. **Repasse** em `starts_at + 2h` (ADR 0040), condicionado à realização.
6. **Cancelamento e pausa**: devolução integral, sem repasse (ADR 0039).
7. **Chargeback e MED**: quem suporta, como se bloqueia o repasse, como se cobra,
   **e autorização expressa de compensar no repasse seguinte** devolução paga à
   quadra e depois revertida, no prazo de 90 dias.
8. **KYC e titularidade da conta de recebimento**: triple-check, com registro.
9. **Autorização de tratamento de dados** do estabelecimento e dos contatos.
10. **Retenção do repasse por falta de documento fiscal**: o JOGA pode reter o
    repasse da quadra enquanto houver reserva sem NFS-e emitida contra o jogador
    após o prazo de tolerância, com liberação mediante emissão ou decisão
    fundamentada. Sem esta cláusula, a retenção do §9.4 de
    `docs/DECISOES_BACKEND_ADR_0049.md` é inexigível.

**Razão:** o item 1 é o mais crítico. Sem documento fiscal da quadra contra o
jogador, a cadeia do §2.7 não existe e o teste 6 falha na prática, ainda que a
cláusula exista no papel. **[H]**

---

## 10. Pendências bloqueantes

**Correção de escopo (2026-11-16).** A redação anterior — "nenhuma linha de código
antes dos pareceres" — era ampla demais. O que os pareceres bloqueiam é a
**operação com dinheiro real** e qualquer código que **codifique a conclusão
jurídica**. Código invariante ao resultado pode e deve avançar. A separação em
três faixas está em `docs/DECISOES_BACKEND_ADR_0049.md`:

- **Faixa 1 (pode agora):** código cujo comportamento não muda qualquer que seja
  a conclusão fiscal ou jurídica.
- **Faixa 2 (pode com parâmetro):** código cujo comportamento depende de um valor
  que ainda não se conhece — o valor é configuração, nunca constante.
- **Faixa 3 (não pode):** código que presume a conclusão (ex.: alíquota fixa,
  reconhecer a compra como receita, absorver diferença de preço).

Nenhuma linha de código deve ser escrita para esse modelo antes de:

| # | Pendência | Quem resolve | Bloqueia |
|---|---|---|---|
| 1 | Parecer fiscal: natureza da receita, base de cálculo, ISS, retenção, IBS/CBS | contador + tributarista | tudo |
| 2 | Parecer jurídico: mandato, custódia, insolvência, CDC | advogado | contrato e Termos |
| 3 | Alíquota real do Simples e recálculo do piso de 10% | contador | precificação |
| 4 | Escolha do fornecedor de escrow e confirmação de titularidade | comercial + jurídico | fase C |
| 5 | Confirmação de que as quadras parceiras emitem NFS-e contra o jogador | operação | teste 6 |
| 6 | Política de expiração/reenvio de saldo em encerramento de conta | jurídico | C13 |
| 7 | Efeito do split payment do IBS/CBS sobre o fluxo | tributarista | §6.4 |

---

## 11. Consequências

- O saldo passa a ser expresso em reais; a unidade "ingresso" perde efeito de
  conta.
- A tabela 2D deixa de ser preço e vira, no máximo, calibração interna.
- O preço exibido passa a ter duas linhas: espaço e taxa.
- A comissão passa a ser percentual uniforme, com piso mínimo por transação.
- O passe é assinatura de franquia mensal, fora do fluxo de escrow.
- A tese fiscal passa a depender de três provas: mandato, titularidade do dinheiro
  e cadeia de notas.
- **Em B, o modelo é operável, mas a defesa fiscal é declaradamente mais fraca.**
  Migrar para C é condição para escala comercial.

### 11.1 O que este documento não decide

- PSP ou fornecedor de escrow.
- Percentual final da taxa (depende da alíquota real).
- Política de expiração do passe além do que já está na ADR 0043.
- Tratamento de MED/chargeback.
- Se o JOGA cobra a taxa do jogador ou da quadra.

---

## 12. Critérios de revisão

- Parecer fiscal que conclua que a receita é o valor cheio → revisar o modelo
  inteiro, não apenas o preço.
- Migração de B para C.
- Entrada em vigor plena de CBS/IBS.
- Exigência de autorização como instituição de pagamento por autoridade
  competente.
- Qualquer alteração que permita saque, transferência ou expiração de saldo.

---

## 13. Adendo 2026-11-16 — tabela 2D como unidade de consumo

**Status:** decisão de produto para a Fase 14E. Corrige a §2.3 e esclarece a §11.
Não altera a natureza da intermediação nem o ledger em reais.

### 13.1 Decisão

O ticket é a **unidade de consumo**, não uma conversão do real. A quantidade de
tickets de uma vaga vem da **tabela 2D** (faixa de preço da quadra × formato),
como na ADR 0042 §3.2. O preço em reais (valor da quadra + taxa) continua
congelado por reserva e é o que o ledger lança. **Não há conversão de ticket em
real no consumo:** a tabela é a autoridade de tickets; o ledger é a autoridade
monetária.

### 13.2 Formatos padrão

Existem três formatos padrão:

- **5x5 (futebol):** 10 jogadores.
- **6x6 (vôlei):** 12 jogadores.
- **3x3 (futevôlei):** 6 jogadores.

4x4 e menores são **contingência** (falta de jogador ou substituição), não
catálogo padrão. Quando ocorrerem, a contagem é derivada por
`k = ceil((V + taxa) / (n × 3,10))`, sem célula fixa. O 3x3 deixou de ser
contingência: é o futevôlei.

### 13.3 Tabela padrão (ingressos por jogador)

| Faixa | Valor da quadra | 5x5 (10) | 6x6 (12) | 3x3 (6) |
|---|---:|---:|---:|---:|
| Econômica dia | até R$ 120 | 5 | 4 | 8 |
| Econômica noite | R$ 121–150 | 6 | 5 | 10 |
| Padrão dia | R$ 151–180 | 7 | 6 | 12 |
| Padrão noite | R$ 181–220 | 9 | 8 | 15 |
| Coberta | R$ 221–260 | 11 | 9 | 17 |
| Premium | R$ 261–300 | 12 | 10 | 20 |

Correções em relação à tabela da ADR 0042: **Coberta 5x5 10 → 11**, **Padrão
noite 6x6 7 → 8**, **Padrão noite 3x3 14 → 15** e **Premium 3x3 19 → 20**. As
outras células não mudam. O calibre é o menor preço de ticket (R$ 3,10, pacote
grande).

### 13.4 Fechamento da conta

Premissas: taxa de 20% sobre a quadra, alíquota de 15,5% (Anexo V) sobre a taxa,
PSP de 0,99% sobre a quadra, custo fixo/infraestrutura de R$ 4,00 por partida,
provisão de cancelamento de R$ 0,20 por jogador e provisão de cauda de 0,2% sobre
a quadra.

**5x5 (10 jogadores)**

| Faixa | Quadra | Taxa | Imposto | PSP | Provisão | Infra | Cauda | Sobra | Margem |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Econômica dia | 120,00 | 24,00 | 3,72 | 1,19 | 2,00 | 4,00 | 0,24 | 12,85 | 10,71% |
| Econômica noite | 150,00 | 30,00 | 4,65 | 1,48 | 2,00 | 4,00 | 0,30 | 17,57 | 11,71% |
| Padrão dia | 180,00 | 36,00 | 5,58 | 1,78 | 2,00 | 4,00 | 0,36 | 22,28 | 12,38% |
| Padrão noite | 220,00 | 44,00 | 6,82 | 2,18 | 2,00 | 4,00 | 0,44 | 28,56 | 12,98% |
| Coberta | 260,00 | 52,00 | 8,06 | 2,57 | 2,00 | 4,00 | 0,52 | 34,85 | 13,40% |
| Premium | 300,00 | 60,00 | 9,30 | 2,97 | 2,00 | 4,00 | 0,60 | 41,13 | 13,71% |

**6x6 (12 jogadores)**

| Faixa | Quadra | Taxa | Imposto | PSP | Provisão | Infra | Cauda | Sobra | Margem |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Econômica dia | 120,00 | 24,00 | 3,72 | 1,19 | 2,40 | 4,00 | 0,24 | 12,45 | 10,38% |
| Econômica noite | 150,00 | 30,00 | 4,65 | 1,48 | 2,40 | 4,00 | 0,30 | 17,17 | 11,45% |
| Padrão dia | 180,00 | 36,00 | 5,58 | 1,78 | 2,40 | 4,00 | 0,36 | 21,88 | 12,16% |
| Padrão noite | 220,00 | 44,00 | 6,82 | 2,18 | 2,40 | 4,00 | 0,44 | 28,16 | 12,80% |
| Coberta | 260,00 | 52,00 | 8,06 | 2,57 | 2,40 | 4,00 | 0,52 | 34,45 | 13,25% |
| Premium | 300,00 | 60,00 | 9,30 | 2,97 | 2,40 | 4,00 | 0,60 | 40,73 | 13,58% |

**3x3 (6 jogadores)**

| Faixa | Quadra | Taxa | Imposto | PSP | Provisão | Infra | Cauda | Sobra | Margem |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Econômica dia | 120,00 | 24,00 | 3,72 | 1,19 | 1,20 | 4,00 | 0,24 | 13,65 | 11,38% |
| Econômica noite | 150,00 | 30,00 | 4,65 | 1,48 | 1,20 | 4,00 | 0,30 | 18,37 | 12,25% |
| Padrão dia | 180,00 | 36,00 | 5,58 | 1,78 | 1,20 | 4,00 | 0,36 | 23,08 | 12,82% |
| Padrão noite | 220,00 | 44,00 | 6,82 | 2,18 | 1,20 | 4,00 | 0,44 | 29,36 | 13,35% |
| Coberta | 260,00 | 52,00 | 8,06 | 2,57 | 1,20 | 4,00 | 0,52 | 35,65 | 13,71% |
| Premium | 300,00 | 60,00 | 9,30 | 2,97 | 1,20 | 4,00 | 0,60 | 41,93 | 13,98% |

Todas as margens ficam acima do piso de 10%. A sobra é o que resta depois de
imposto, PSP, provisão, infraestrutura e cauda; não é lucro líquido final.

### 13.5 Contagem e cobertura

| Faixa | 5x5/jogador | k 5x5 | 6x6/jogador | k 6x6 | 3x3/jogador | k 3x3 |
|---|---:|---:|---:|---:|---:|---:|
| Econômica dia | 15,50 | 5 | 12,40 | 4 | 24,80 | 8 |
| Econômica noite | 18,60 | 6 | 15,50 | 5 | 31,00 | 10 |
| Padrão dia | 21,70 | 7 | 18,60 | 6 | 37,20 | 12 |
| Padrão noite | 27,90 | 9 | 24,80 | 8 | 46,50 | 15 |
| Coberta | 34,10 | 11 | 27,90 | 9 | 52,70 | 17 |
| Premium | 37,20 | 12 | 31,00 | 10 | 62,00 | 20 |

O valor por jogador é `k × 3,10`; o total da partida é esse valor vezes o número
de jogadores (10 no 5x5, 12 no 6x6, 6 no 3x3). Em todas as células,
`k × 3,10 ≥ valor da quadra + 20%`. A diferença entre o total de tickets e a
quadra é o **valor do JOGA** (§13.9).

### 13.6 Risco de cancelamento

O fator de risco da ADR 0021 é `S = 1 + z√(φ/μ)`. Com `q = 20%`, `μ = 4`,
`z = 1,645` e `φ = 1`, `S = 1,8225`. Com `C_c = R$ 0,47`, a provisão plena é
`C_c·μ·S = R$ 3,43` por partida.

A decisão vigente usa **R$ 0,20 por jogador** (R$ 2,00 no 5x5 e R$ 2,40 no 6x6),
abaixo da provisão plena. É uma redução deliberada de risco: com R$ 3,43, a faixa
de R$ 120 cai para ~9,5% nos dois formatos, abaixo do piso de 10%. Se a operação
confirmar o custo pleno, a taxa da faixa de R$ 120 precisa subir para ~20,6% ou a
faixa não é oferecida. A provisão é provisão, não seguro.

Sensibilidade de imposto: com 6% em vez de 15,5%, a sobra sobe e a margem da faixa
de R$ 120 vai a ~12,6% no 5x5. A alíquota permanece pendente de parecer (§10).

### 13.7 Ledger, invariante e migração

- **Consumo:** `settle_with_tickets` baixa `tickets_per_seat` tickets (tabela) e
  o ledger debita `tickets_per_seat × 310` (o valor do ticket), não
  `contribution_cents`.
- **Ledger (regra 4, caminho por tickets):**
  D `player_credit` `k × 310`; C `venue_payable` `venue_price_cents`;
  C `fee_revenue` `(k × 310) − venue_price_cents`.
- **Caminho por Pix:** D `psp_clearing` `contribution_cents`; C `venue_payable`
  `space_charge_cents`; C `fee_revenue` `fee_charge_cents` (20% da quadra).
- **Dois saldos independentes:** tickets (lots) e centavos (`player_credit`). O
  jogador precisa dos dois; o excedente de caixa (preço do pacote acima de 3,10)
  fica como crédito (passivo).
- **Invariante:** por evento, não por valor. Compra sobe caixa e tickets;
  quitação baixa `k × 310` e `k` tickets; a soma quadra + JOGA = `k × 310`;
  nenhum saldo negativo. O invariante `ledger == remaining × preço pago` não vale.
- **Compra:** D `psp_clearing` `N × P`; C `player_credit` `N × P`; lote sobe N
  tickets. O ticket vale 3,10 no consumo; o que exceder 3,10 é preço do pacote e
  fica como crédito.
- **Migração:** abertura monetária `Σ remaining × unit_price_cents`, contra
  `opening_equity`, idempotente; lotes de passe/grátis/admin ficam em tickets.

### 13.8 O que este adendo altera

- **§2.3:** sai a conversão 1:1; o ticket é a unidade de consumo da tabela 2D.
- **§11:** a tabela 2D não é preço; é a unidade de consumo e exibição. O preço
  jurídico continua sendo o valor da quadra + taxa.
- **§4.1/§8:** confirmam 20% de taxa, piso de R$ 8,00 e provisão de R$ 0,20 por
  jogador; a provisão plena exigiria ~20,6% na faixa de R$ 120.
- **Formatos:** 5x5, 6x6 e 3x3 (futevôlei) no catálogo padrão; 4x4 e menores são
  contingência.
- **Pendências:** alíquota, PSP definitivo, custódia C e pareceres da §10.

### 13.9 Valor do JOGA na confirmação

Quando o participante confirma e usa os créditos, o valor gasto em tickets é
`k × 3,10`. A notificação e o recibo mostram duas linhas:

- **Valor da quadra:** `space_charge_cents` (soma exata = `venue_price_cents`).
- **Valor do JOGA:** `k × 3,10 − space_charge_cents` (o restante).

As duas linhas somam `k × 3,10`. O valor do JOGA é o **restante**, não um
percentual fixo. A taxa de 20% é o piso de referência; o arredondamento para cima
do número inteiro de tickets faz o restante ficar entre 20,56% e 35,27% da
quadra, conforme a faixa e o formato. O backend deve persistir os dois valores
por participante e devolvê-los na confirmação e no recibo.

Exemplo, R$ 120 no 5x5: 5 tickets × 3,10 = R$ 15,50 por jogador; 10 jogadores =
R$ 155,00. Quadra R$ 120,00; JOGA R$ 35,00 (29,17%). No 6x6: 4 × 3,10 = R$ 12,40;
12 jogadores = R$ 148,80; JOGA R$ 28,80 (24,00%).
