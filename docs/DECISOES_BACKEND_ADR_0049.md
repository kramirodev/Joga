# Decisões para desbloquear o backend — ADR 0049

**Data:** 2026-11-16
**Origem:** lista de pendências levantada pelo agente de backend contra a ADR 0049.
**Objetivo:** responder o que é decisão de produto/arquitetura e isolar o que
depende de terceiro, para que o backend saiba exatamente o que pode construir.

Legenda de status:

| Marca | Significa |
|---|---|
| **[R]** | Resolvido aqui. Implementável agora. |
| **[P]** | Parametrizado. Implementável agora, com o valor em configuração — **nunca constante no código**. |
| **[B]** | Bloqueado. Depende de terceiro. Não implementar. |

---

## 0. Correção do portão de código

A ADR 0049 §10 dizia "nenhuma linha de código antes dos pareceres". **Era amplo
demais e está corrigido.** O que os pareceres bloqueiam é a **operação com
dinheiro real** e o código que **codifica a conclusão jurídica**.

Três faixas:

**Faixa 1 — pode agora.** Código cujo comportamento é idêntico qualquer que seja a
resposta do fiscal ou do advogado. Ex.: guardar CPF, separar valor da quadra da
comissão no ledger, registrar o teto aceito, impedir saque.

**Faixa 2 — pode com parâmetro.** Código cujo comportamento depende de um valor
desconhecido. Ex.: alíquota de imposto, percentual da taxa, prazo de repasse. O
valor vai para configuração; o código não presume.

**Faixa 3 — não pode.** Código que presume a conclusão. Ex.: reconhecer a compra
como receita, absorver diferença de preço, fixar alíquota, expirar crédito.

Regra de ouro: **se a dúvida é "quanto", é parâmetro; se a dúvida é "o que é", é
bloqueio.** Nenhum item desta lista é bloqueio por "quanto".

---

## 1. Bloqueantes da seção 10

| # | Item | Status | Decisão / o que fazer |
|---|---|---|---|
| 1 | Parecer fiscal | **[B]** | Nada a implementar. O código não depende do texto do parecer, apenas dos valores. |
| 2 | Parecer jurídico | **[B]** | Termos e contrato são conteúdo, não código. O backend não espera. |
| 3 | Alíquota real e piso | **[P]** | Alíquota é configuração versionada por competência (§9.6). Piso é configuração (§4.1). |
| 4 | Escolha de escrow | **[B]** | Não escolher fornecedor agora. Não criar abstração preventiva (§3.4). |
| 5 | NFS-e das quadras | **[B]** para emitir / **[R]** para preparar | Guardar CPF e registrar o documento fiscal da quadra por reserva. Ver §3.8. |
| 6 | Saldo no encerramento | **[R]** política / **[B]** texto legal | Política: nunca confiscar; devolver em dinheiro. Redação final depende do advogado. |
| 7 | Split payment IBS/CBS | **[P]** | Nenhuma mudança de código agora. A cadeia de notas do §3.8 já é o pré-requisito. |

---

## 2. Decisões em aberto da seção 11.1

| Item | Status | Decisão |
|---|---|---|
| PSP / fornecedor de escrow | **[B]** | Manter Mercado Pago no protótipo. Não integrar PSP novo. |
| Percentual final da taxa | **[P]** | Parâmetro `fee_percent`. Valor provisório: **20%**. Ver §4.1 — decisão sua. |
| Expiração do passe | **[R]** | Franquia mensal não acumula e não converte em saldo. Nada além da ADR 0043. |
| MED/chargeback | **[R]** regra / **[B]** contrato | Chargeback bloqueia o repasse, gera receivable contra a quadra e **não toca o saldo do jogador**. |
| Quem paga a taxa | **[R]** | **O jogador**, em linha separada. Ver §4.2. |

---

## 3. Conflitos com o que está implementado

Esta é a parte que o backend precisa. Nove decisões.

### 3.1 Unidade: ingressos → reais  **[R]**

O ledger passa a ser a fonte da verdade em **centavos (inteiro)**. `ticket_lots`
permanece como **registro de origem** do que foi comprado — a identidade do lote é
imutável (`source`, `original_amount`, `unit_price_cents`, `created_at`), mas
`remaining` é projeção de saldo, não verdade. Detalhe em §9.1.

Migração dos saldos existentes: **cada lote converte pelo preço unitário que o
jogador efetivamente pagou naquele lote** — 3,70 / 3,40 / 3,20 / 3,10 —, nunca por
um preço único.

```
saldo_cents = Σ (lote.remaining × lote.unit_price_cents)
```

Razão: converter tudo por R$ 3,10 tiraria valor de quem pagou R$ 3,70. Arredondar
a favor do jogador quando houver fração de centavo.

**Não fazer:** manter dois saldos em paralelo, ou converter por média.

### 3.2 Expiração  **[R]**

- **Crédito comprado:** `expires_at = null`, sempre. Migrar para `null` toda
  expiração futura pendente. Expiração já consumida no passado não é revertida.
- **Franquia de passe:** continua com período (`2026-11`), mas **não é
  `expires_at`** — é `period`. São conceitos diferentes e não devem compartilhar
  coluna.
- **Nenhum job de expiração de crédito.** O job de fechamento de período do passe
  permanece.

### 3.3 Preço em duas linhas  **[R]**

Persistir por reserva, congelado:

| Campo | Conteúdo |
|---|---|
| `venue_price_cents` | preço do espaço informado pelo estabelecimento |
| `fee_cents` | comissão calculada no momento da reserva |
| `fee_percent_applied` | percentual usado, para auditoria — **snapshot**, não referência viva |
| `total_cents` | soma |

`fee_cents = round(venue_price_cents × fee_percent)`, com piso `fee_min_cents`.

**Invariante (§3.6):** o valor cobrado pela linha "espaço" é **exatamente**
`venue_price_cents`. Não existe tabela intermediando o preço da quadra.

### 3.4 Custódia  **[R]** e **[B]**

- **[B]** escolher escrow.
- **[R]** o ledger **não pode presumir** que o dinheiro recebido é receita. Modelo
  de dupla entrada com o plano de contas da **§9.2**. A ADR 0049 §7 lista as contas
  conceituais; a §9.2 lista as **quatorze** necessárias para operar de verdade,
  incluindo PSP em trânsito, receita diferida, receivable de chargeback e
  incobrável.
- **Não criar `CustodyAdapter` agora.** Não há duas implementações concretas; a
  abstração nasceria sem necessidade. O que protege a migração é o ledger não
  codificar a hipótese, não uma interface.

### 3.5 Passe  **[R]**

O passe concede **cota mensal**, não ingressos.

- `pass_period_quota` não existe como tabela nova: a cota do passe é um lote
  `ticket_lots` com `source='pass'` e `period='YYYY-MM'`, conforme §9.1. Criar uma
  segunda estrutura para a mesma coisa duplicaria a fonte de verdade.
- Ordem de consumo: **primeiro a cota do passe, depois a cortesia, depois o
  crédito comprado** — ordem completa em §9.1.
- Cota não usada **não vira crédito** e não é receita de breakage; a receita do
  passe é do mês, pela disponibilização (ADR 0049 §2.6).

### 3.6 Regra de não absorção  **[R]**

Não é regra de negócio: é **invariante de dados**.

```
SUM(space_charge_cents por reserva) == venue_price_cents
```

Com o preço em duas linhas, a absorção é estruturalmente impossível — a linha
"espaço" é o preço da quadra, não uma tabela. O que a regra proíbe é o desvio:
desconto na linha "espaço" sem que a quadra o tenha concedido por contrato.

Implementar como constraint/checagem no fechamento da reserva + teste negativo.
**Nenhuma coluna de absorção ou de desconto.** Se a quadra aceitar cobrar menos por
um horário, isso é preço novo — cotação versionada com autor e data (§9.11), não um
abatimento na linha do espaço. Sem exceção: assento vago significa reserva não
confirmada no preço antigo, não plataforma cobrindo a diferença (§9.10).

### 3.7 Teto por partida  **[R]**

Persistir por participação na partida:

| Campo | Conteúdo |
|---|---|
| `max_credits_cents` | teto aceito pelo jogador no momento em que entra na partida |
| `accepted_at` | quando aceitou |
| `terms_version` | versão dos Termos vigente no aceite |

O matchmaking **não oferece** partida cujo custo por jogador exceda o teto. Se
nada couber, oferecer as saídas da ADR 0042 §6.5 (aumentar teto, ampliar
região/horário, fila).

### 3.8 CPF e documento fiscal  **[R]**

- Coletar CPF no perfil, **obrigatório antes da primeira reserva confirmada**.
- Armazenar **cifrado** (não hash — precisa ser lido para a nota), com finalidade
  declarada e acesso auditado.
- Registrar por reserva: `fiscal_document` com tipo, número, emitente (CNPJ da
  quadra), tomador (CPF do jogador), valor e data de emissão.
- O backend **não emite** NFS-e. Ele **armazena o que a quadra emitiu** e sinaliza
  reserva sem documento após o prazo.

**Isto é Faixa 1 e pode começar hoje**, mesmo sem o parecer. É o pré-requisito do
teste 6 e o item que mais quebra na prática.

### 3.9 Comissão no cancelamento  **[R]**

O ledger precisa separar, por reserva, `venue_amount_cents` e `fee_amount_cents`
desde o início. Hoje não separa. Sem isso, não existe reversão correta.

Regra: cancelamento com devolução integral reverte **os dois** na mesma
proporção. A comissão nunca sobrevive a uma devolução integral — sobreviver seria
cobrar por uma intermediação que foi desfeita.

---

## 4. Decisões de política

### 4.1 Taxa e piso  **[P]** — precisa do seu ok

A taxa é parâmetro. Mas o **valor** depende de uma decisão que é sua, não do
contador: qual margem líquida o produto precisa.

Com a pilha de custos da ADR 0042 (`s = 0,99%`, `K = R$ 10,00` por partida com 10
jogadores):

| Espaço | Taxa p/ margem de 10%, t=6% | Taxa p/ margem de 10%, t=15,5% |
|---:|---:|---:|
| R$ 120 | 20,8% | 23,1% |
| R$ 150 | 19,0% | 21,1% |
| R$ 200 | 17,2% | 19,2% |
| R$ 300 | 15,4% | 17,2% |

Três leituras:

1. **O piso de 10% e uma taxa abaixo de ~18% são incompatíveis.** Não é questão
   de arredondar: é a pilha de custos.
2. **Se o enquadramento for Anexo V, o piso de 10% exige taxa acima de 21%** em
   quadras baratas. Comercialmente insustentável.
3. **A provisão de cancelamento de R$ 0,60 por jogador custa R$ 6,00 por partida**
   — 4% de uma quadra de R$ 150. É o maior item depois do imposto.

**Decisão tomada [D]:** `fee_percent = 20%`, `fee_min_cents = 800`, provisórios e
em configuração. A provisão de cancelamento cai de R$ 0,60 para **R$ 0,20 por
jogador** — R$ 2,00 por partida em vez de R$ 6,00.

Efeito com 20% e provisão de R$ 0,20/jogador (Anexo V, 15,5%):

| Espaço | Taxa | Sobra | Margem |
|---:|---:|---:|---:|
| R$ 120 | 24,00 | 12,85 | **10,7%** |
| R$ 150 | 30,00 | 17,57 | **11,7%** |
| R$ 200 | 40,00 | 25,42 | **12,7%** |
| R$ 300 | 60,00 | 41,14 | **13,7%** |

O piso de 10% passa a valer a partir de **~R$ 105**. Não é preciso subir a taxa
para 21–23%.

**Risco aceito com essa decisão:** a provisão de R$ 0,20 é menor que o custo real
de um reembolso, de um atendimento e de um reprocessamento de fila. Ela é
provisão, não seguro. Se o parecer ou a operação mostrarem que R$ 0,20 não cobre,
o caminho não é compensar com receita de float: é rever a taxa, com número.

### 4.2 Quem paga a taxa  **[R]**

**O jogador**, em linha separada.

Razão: preserva a igualdade entre o preço da quadra na plataforma e o preço na
portaria — que é o que prova ausência de markup (ADR 0049 §3.4). Cobrar da quadra
obrigaria a quadra a subir o preço para repassar, reintroduzindo a diferença.

### 4.3 Passe  **[R]**

Sem acúmulo, sem conversão em saldo, sem reembolso após a disponibilização do mês
(sujeito a J6 do termo de referência).

### 4.4 Encerramento de conta e devolução de saldo  **[R]** política

Cinco situações, cinco regras — e elas não são a mesma coisa:

| Situação | Crédito comprado | Franquia de passe | Gratuidade (XP/cortesia) |
|---|---|---|---|
| Arrependimento em 7 dias (CDC art. 49) | devolução **em dinheiro**, integral, inclusive parte já consumida | devolução em dinheiro do trimestre, descontado o mês já disponibilizado **[H]** | não reembolsável |
| **Depois de 7 dias, conta ativa** | **não há devolução em dinheiro** | meses **não disponibilizados** devolvidos se o passe for cancelado; mês disponibilizado não | não reembolsável |
| Encerramento de conta | devolução **em dinheiro**, pelo mesmo meio | mensalidades **não disponibilizadas** devolvidas; mês disponibilizado não | não reembolsável |
| Cancelamento de reserva | volta como crédito, salvo devolução integral em dinheiro | não se aplica | volta como ingresso |
| Expiração | **não existe** | fim do período do mês, sem conversão | conforme a concessão |

**Por que não há reembolso de pacote depois de 7 dias.** É decisão, não omissão:

- **Crédito não é depósito.** Se o jogador pode converter saldo em dinheiro a
  qualquer momento, o crédito passa a funcionar como conta de pagamento — que é o
  vetor 9 da ADR 0049 §4 e a pergunta J5 do termo de referência. A licitude do
  modelo depende de o saldo ser meio de uso, não de saque.
- **A exceção é o encerramento.** Ao encerrar a conta, o saldo comprado é devolvido
  em dinheiro (C13). A diferença não é capricho: encerrar é terminar a relação; sacar
  é usar a plataforma como conta.
- **A janela de 7 dias é do CDC** e cobre o arrependimento da compra, inclusive se
  parte do crédito já foi usada. Depois dela, o crédito é para jogar.
- **Isso precisa estar escrito nos Termos**, com a mesma clareza: "saldo é para uso
  na plataforma; devolução em dinheiro em 7 dias ou no encerramento da conta". Sem
  essa frase, a restrição não é oponível.

Regras que o código precisa respeitar:

- **Crédito comprado nunca vira ingresso nem passe; ingresso gratuito nunca vira
  crédito.** Converter um no outro é criar ou destruir valor.
- **O passe não é saldo.** A franquia do mês disponibilizado é consumida e acaba;
  não acumula, não vira crédito e não é reembolsável. O trimestre pago e ainda não
  disponibilizado é devolvido proporcionalmente.
- **Gratuidade não é saque.** Saldo de XP, promoção ou cortesia não é convertível
  em dinheiro; se o jogador encerrar a conta, ele simplesmente se extingue. Sem
  isso, promoção vira canal de saque.
- Prazo de devolução em configuração (`JOGA_CREDIT_REFUND_DAYS`, provisório **30**).
  Se o jogador não responder ao contato documentado, o valor fica em passivo em
  aberto — nunca é apropriado como receita.

**[H]** A obrigatoriedade da devolução em dinheiro e o prazo dependem de J6/J7. A
política acima é a conservadora: é lícita nos dois cenários e não precisa ser
reescrita se o parecer confirmar.

---

## 5. O que continua bloqueado — e como destravar com placeholder

Nenhum destes cinco pode **funcionar de verdade** sem terceiro. Todos podem ser
**estruturados** agora, atrás de uma flag única, sem mover dinheiro e sem chamada
externa. Regra: com `JOGA_MONEY_MODE=simulated`, o sistema se comporta exatamente
como hoje. **Este é o único nome de flag.** `JOGA_REAL_MONEY_ENABLED` não existe e
não deve ser implementado (§9.8).

### 5.1 NFS-e  **[P]**

`JOGA_FISCAL_MODE = disabled | placeholder | provider`

- `disabled` (padrão): nada acontece.
- `placeholder`: grava a intenção, não emite. Cria `fiscal_documents` com
  `status = pending_manual`, `provider_ref = null`.
- `provider`: falha no boot com mensagem clara enquanto não houver integração.

Tabela `fiscal_documents`: `booking_id`, `issuer_cnpj` (quadra), `taker_user_id`,
`amount_cents`, `number`, `issued_at`, `status`, `provider_ref`, `created_at`.

**O CPF não é copiado para esta tabela em texto claro.** Enquanto o perfil não
tiver o campo cifrado (§9.3), a tabela guarda apenas `taker_user_id`. Quando o CPF
existir, o snapshot cifrado entra na mesma transação da emissão, em coluna própria
— nunca em claro, nunca em log.

Aceite: nenhuma chamada HTTP para emissor; reserva sem documento após o prazo
aparece em relatório; CPF cifrado nunca em log.

### 5.2 Dinheiro real no novo modelo  **[P]**

`JOGA_MONEY_MODE = simulated | real`

- `simulated` (padrão): mantém o caminho atual do Mercado Pago e do ledger
  simulado.
- `real`: recusa o boot sem `JOGA_LEGAL_APPROVAL_REF` preenchido (string que
  referencia o parecer fiscal e jurídico aprovados).

Aceite: `real` sem a referência → erro de startup, nunca degradação silenciosa
para simulado (mesma lógica da ADR 0048 §3).

### 5.3 Escrow  **[P]**

`JOGA_CUSTODY_MODEL = B | C`

- `B` (padrão): conta da JOGA, ledger com passivo.
- `C`: **não implementado**. Selecionar falha no boot com `custody_model_not_implemented`.

Não criar `CustodyAdapter`. Um enum no ledger por movimento basta para provar
qual modelo vigorava em cada data. Abstração sem segunda implementação real é
custo sem retorno.

### 5.4 Termos de Uso  **[P]**

Tabela `terms_versions`: `version`, `content`, `status = draft | approved`,
`published_at`, `legal_review_ref`.

- Semear as cláusulas C1–C14 da ADR 0049 §8 como `draft`.
- Aceite só pode apontar para versão `approved`. `draft` é rejeitada pelo backend.
- `terms_version` já é gravado no teto por partida (§3.7) — os dois se conectam.

Aceite: nenhum aceite gravado contra versão `draft`; texto publicado é imutável
(nova versão, nunca edição).

### 5.5 Alíquota e taxa  **[P]**

`JOGA_TAX_RATE_BPS` (ex.: `1550`), `JOGA_FEE_PERCENT_BPS` (ex.: `2000`),
`JOGA_FEE_MIN_CENTS` (ex.: `800`).

A alíquota **nunca** entra no ledger: ela só aparece em relatório de margem. A
taxa entra no ledger apenas como `fee_cents` já calculado e congelado (§3.3).

**`JOGA_TAX_RATE_BPS` é apenas valor local.** Ele não serve para relatório
histórico: a alíquota efetiva do Simples muda com a receita e o ISS varia por
município. Relatório de margem usa `tax_rate_versions` por competência (§9.6) e
**falha** se não houver versão cadastrada — não cai em silêncio para o env.

Aceite: mudar a alíquota no ambiente não altera nenhum lançamento histórico;
mudar a taxa não altera reservas já criadas.

---

## 5.6 O que continua bloqueado de verdade

Curto e sem rodeio:

- Emitir nota fiscal de verdade.
- Mover dinheiro real no novo modelo.
- Operar custódia em C.
- Publicar Termos de Uso.
- Fixar alíquota e piso final.

Os cinco acima são **estrutura**, não operação. A operação continua bloqueada.

---

## 6. As três decisões — tomadas

Foram as únicas que dependiam do dono do produto, não do contador. Estão fechadas
em §8:

1. **Taxa de 20%**, piso de R$ 8,00, em configuração.
2. **Piso de margem de 10%**, atingido cortando a provisão de cancelamento para
   R$ 0,20 por jogador.
3. **Quem paga a taxa: o jogador**, em linha separada.

---

## 7. Ordem de implementação sugerida

```
Faixa 1 (hoje, sem parecer):
  CPF + registro de documento fiscal (§3.8)
  ledger em centavos com venue/fee separados (§3.1, §3.9)
  invariante de não absorção (§3.6)
  teto por partida (§3.7)
  remoção de expiração do crédito (§3.2)

Faixa 2 (hoje, com parâmetro):
  fee_percent / fee_min (§4.1)
  alíquota e piso como configuração (§1.3)
  prazo de repasse e de devolução (config)

Faixa 3 (depois dos pareceres):
  ligar dinheiro real no novo modelo
  emitir NFS-e
  publicar Termos
  migrar para escrow
```

---

## 8. Decisões aceitas — resumo

| Decisão | Valor | Status |
|---|---|---|
| Taxa de intermediação | **20%** (`fee_percent_bps = 2000`) | **[P]** provisório |
| Piso da taxa | **R$ 8,00** (`fee_min_cents = 800`) | **[P]** |
| Provisão de cancelamento | **R$ 0,20 por jogador** (`JOGA_CANCELLATION_PROVISION_CENTS = 20`) | **[P]** |
| Quem paga a taxa | **o jogador**, em linha separada | **[R]** |
| Custódia | **B** agora (`JOGA_CUSTODY_MODEL=B`), **C** como alvo | **[R]** / **[B]** |
| Piso de margem | **10%** (passa a valer a partir de ~R$ 105 com a provisão nova) | **[D]** |
| Migração de saldo | lote a lote, pelo preço pago; gratuito e passe não viram dinheiro | **[R]** |
| Ledger | dupla entrada, partidas por transação, `booking_payments` não é ledger | **[R]** |

O piso de R$ 8,00 é decorativo a 20%: ele só morde em quadra abaixo de R$ 40. Fica
em configuração porque é barato mantê-lo e evita taxa de centavos.

---

## 9. Especificação dos pontos que o backend levantou

Esta seção responde, um por um, os dez itens que o backend disse não conseguir
implementar sem especificação. Cada resposta tem: a decisão, o esquema mínimo e a
regra de aceite. Nada aqui depende de parecer, exceto onde marcado **[B]**.

### 9.1 Migração de saldos e passes ativos  **[R]**

**Pergunta do backend:** o que fazer com ingressos gratuitos de XP/passe, com
passes que já entregaram ingressos, com reservas antigas e com o rollback.

**Decisão: só dinheiro pago vira crédito em centavos. Todo o resto continua
ingresso, na unidade original.**

Isso não é detalhe de migração; é o que impede criar dinheiro do nada. Um ingresso
de XP ou de franquia de passe nunca foi pago por unidade — ele não tem preço, e
atribuir um seria reconhecer passivo que não existe.

Quatro classes de lote, quatro tratamentos:

| `ticket_lots.source` | Vira crédito? | Tratamento |
|---|---|---|
| `purchase` | **Sim** | `remaining × unit_price_cents` do lote |
| `refund` | **Sim, se rastreável** | preço do lote que originou o consumo; se ambíguo, maior preço entre os candidatos |
| `pass` | **Não** | continua ingresso de franquia, com `period` |
| `free_level`, `admin` | **Não** | continua ingresso, com a validade que já tiver |

**`legacy_balance` não é `source`.** No código atual, o saldo anterior aos lotes vira
um lote `source='admin'` com `ref_type='legacy_balance'` (`_legacy_lot` em
`tickets/service.py`). Portanto ele cai na linha `admin`: **não** é convertido, e é
identificado por `ref_type = 'legacy_balance'`, não por um `source` novo. Não criar
valor novo no `CHECK` de `source` para isso.

Efeito colateral aceito: quem tem saldo anterior aos lotes mantém os ingressos e
**não** ganha crédito sacável. É a leitura conservadora — não se inventa preço para
saldo de origem desconhecida — e a comunicação desse caso no encerramento de conta
precisa ser escrita em linguagem clara, sem letra miúda.

**De onde vem `unit_price_cents`.** `ticket_lots` não tem essa coluna hoje, e o
preço do `ticket_packs` pode ter mudado. A fonte correta é o que o jogador pagou:

```
ticket_lots.ref_type = 'purchase' AND ref_id = ticket_purchases.id
unit_price_cents = ticket_purchases.amount_cents / ticket_purchases.tickets
```

A divisão é inteira e exata por construção (`ticket_purchases.amount_cents` veio de
`pack.amount_cents = tickets × unit_price_cents` no momento da compra). Se não for
exata, **abortar a migração** — não arredondar.

**Lote `refund`.** O reembolso devolve um ingresso que já tinha sido consumido.
O preço vem do consumo revertido:

```
ticket_lots(refund) → ticket_lot_consumptions(ref_type, ref_id)
                    → ticket_lots(consumido) → ticket_purchases
```

Se houver mais de um preço entre os consumos revertidos, usa-se o **maior** — a
favor do jogador, como já decidido em §3.1. Se não houver rastro algum, o lote
**não** é convertido: fica como ingresso com `migration_note = 'untraced_refund'`
e vai para revisão humana. Perder valor em silêncio é pior que atrasar um caso.

**Regra de teto, para a migração não criar dinheiro.** Antes de gravar, rodar em
modo `dry-run` e verificar, por usuário:

```
crédito_convertido_cents ≤ Σ ticket_purchases.amount_cents (status = 'paid')
```

Se qualquer usuário violar, **abortar tudo**. Não corrigir automaticamente, não
"ajustar para caber": a violação significa que o rastro está errado e precisa de
gente. A migração produz um relatório por usuário (lotes de origem, preço usado,
total convertido, total pago) que fica arquivado.

**Passe ativo que já entregou ingressos.** Não muda nada no que já foi entregue.

- `pass_subscriptions` e `pass_deliveries` ficam como estão.
- Os lotes `source='pass'` **mantêm o comportamento de franquia**: continuam
  válidos até o fim do período em que foram entregues e não acumulam. O jogador
  recebeu sob essa regra; mudá-la retroativamente seria alterar o contrato dele.
- A remoção de expiração do §3.2 vale **só** para crédito comprado.
- Entrega futura grava `period` (`'YYYY-MM'`) e **não** grava `expires_at`. São
  conceitos diferentes e não devem compartilhar coluna.

Consequência para o código: `_active_lots` passa a selecionar

```
(source = 'pass' AND period = período_atual AND remaining > 0)
OR (source IN ('purchase','refund') AND expires_at IS NULL AND remaining > 0)
OR (source IN ('free_level','admin')
    AND (expires_at IS NULL OR expires_at > now()) AND remaining > 0)
```

`free_level` e `admin` **não podem sair da seleção**. Se a query ficar só com
`pass`, `purchase` e `refund`, todo ingresso gratuito e administrativo some do saldo
do jogador no primeiro consumo — e o sintoma é o usuário reclamando que perdeu
ingressos, sem erro no log. Estes dois continuam com a regra de validade que já
têm: expiram se tiverem `expires_at`, não expiram se não tiverem.

**Backfill de `period` antes de trocar a query.** Todo lote `pass` existente tem
`expires_at` e não tem `period`. A migração preenche
`period = to_char(expires_at, 'YYYY-MM')` em todos eles **antes** de a nova query
entrar em produção. Sem esse backfill, a primeira consulta com `period =
período_atual` não acha nenhum lote de passe e a franquia do mês corrente
desaparece do saldo.

O job `expire_due` acompanha: encerra lote de passe por **`period` vencido**, não
por `expires_at`. Se ficar como está, lote de passe sem `expires_at` nunca expira e
a franquia vira crédito de fato — exatamente o que a §3.2 proíbe. Este é o ponto
onde a migração silenciosamente erra se o job não for revisto junto.

**"Histórico imutável" e `remaining`.** A §3.1 chamou `ticket_lots` de histórico
imutável, mas `remaining` é decrementado hoje. As duas coisas não cabem na mesma
coluna. Decisão:

- Imutáveis: `source`, `original_amount`, `unit_price_cents`, `created_at`,
  `ref_type`, `ref_id`. Nunca mudam.
- **Projeção, não verdade:** `remaining` é saldo projetado, atualizado no consumo,
  e reconstruível por `original_amount − Σ ticket_lot_consumptions.amount`.
- A verdade do consumo é `ticket_lot_consumptions`, append-only.
- Um job de reconciliação compara `remaining` com a soma das consumições e falha
  alto se divergir.

Isso preserva a propriedade que importa (nada é apagado, tudo é reconstruível) sem
fingir que `remaining` é imutável. A §3.1 fica lida assim: o **registro de origem**
do lote é imutável; o saldo dele é projeção.

**Dois saldos durante a migração.** `ticket_balances` (ingressos) e
`credit_balances` (centavos) coexistem no cutover, e ninguém pode ler os dois por
conta própria. Regra de fase:

| Fase | Fonte de leitura | Escrita |
|---|---|---|
| 0 — hoje | `ticket_balances` | `ticket_balances` |
| 1 — migração | **`get_balances(user)`** — único ponto de leitura | ambos |
| 2 — após 1 ciclo | `get_balances(user)` | `credit_balances`; `ticket_balances` só recebe `free_level`/`admin`/`pass` |
| 3 — aposentadoria | `get_balances(user)` | `credit_balances` + lotes; `ticket_balances` vira **view** sobre os lotes |

`get_balances(user)` devolve `{credit_cents, free_tickets, pass_quota_remaining}`.
Nenhum endpoint, tela ou relatório consulta as tabelas de saldo diretamente. A
tabela `ticket_balances` só é aposentada quando a fase 3 estiver implementada e
testada; até lá, ela continua sendo escrita para os ingressos não convertidos.

**Ordem de consumo.** Falta dizer onde entram `free_level` e `admin`. A ordem passa
a ser, e isso **muda** o `SOURCE_PRIORITY` atual:

```
pass → free_level → admin → purchase → refund
```

Razão: consumir primeiro o que expira e o que não pode ser sacado preserva o saldo
sacável do jogador. O código atual coloca `admin` por último e `purchase` antes de
`free_level`; com a ADR 0049, isso faria o jogador gastar o dinheiro devolvível
antes da cortesia e chegar ao encerramento da conta com saldo não reembolsável.
Dentro da mesma classe: `expires_at` mais próximo primeiro, depois `created_at`.
É uma mudança de comportamento e exige teste próprio — não é refactor silencioso.

**Reservas antigas.** Sim, recebem preço em duas linhas, mas **sem inventar
comissão**:

| Campo | Retrofill |
|---|---|
| `venue_price_cents` | `= bookings.price_cents` |
| `fee_cents` | `= 0` |
| `fee_percent_applied` | `= 0` |
| `pricing_version` | `= 'legacy_v0'` |
| `space_charge_cents` (participante) | `= contribution_cents` se a divisão fechar exata; senão `NULL` + `legacy_v0` |

Reserva antiga não teve taxa. Dizer que teve, mesmo com valor zero em outro campo,
contamina relatório de margem e a prova de que não havia markup. Relatório
histórico **exclui** `legacy_v0`, e diz que exclui.

**Rollback.** A migração é reversível porque não destrói a origem:

- `ticket_lots`, `ticket_ledger`, `ticket_balances` **não são apagados** nesta
  migração.
- `ticket_lots` ganha `unit_price_cents` (snapshot), `converted_at`,
  `converted_cents`, `migration_note`.
- `credit_entries` ganha `converted_lot_id` (FK para o lote de origem).
- Rollback = zerar `credit_balances`, apagar `credit_entries where source =
  'migration'`, recalcular `ticket_balances` a partir dos lotes. Os lotes nunca
  saíram do lugar, então o estado anterior é reconstruível por inteiro.
- As colunas antigas (`tickets`, `ticket_balances`) só são removidas em migração
  **posterior**, depois de um ciclo completo, e com ADR aprovada. Não no mesmo dia.

**Não fazer:** tratar os dois saldos como verdades independentes (a verdade é uma
só, exposta por `get_balances`); converter por média; converter gratuito para
completar centavos.

### 9.2 Ledger de dupla entrada  **[R]**

**Pergunta do backend:** "três contas" não é schema.

Correto. Segue o schema mínimo, com sinais, idempotência, concorrência e cutover.

**Princípio:** `booking_payments` continua sendo o registro **do PSP** (ids do
provedor, status, QR, expiração). Ele **não é** o ledger. O ledger é append-only e
não conhece PSP.

```sql
ledger_accounts (
  id            uuid primary key,
  code          varchar(60) not null unique,   -- 'psp_clearing', 'player_credit:<uuid>'
  kind          varchar(12) not null,          -- asset|liability|revenue|expense|equity
  owner_kind    varchar(10) null,              -- user|venue|joga
  owner_id      uuid null,
  custody_model char(1) not null default 'B',  -- prova qual modelo vigorava
  created_at    timestamptz not null,
  check (kind in ('asset','liability','revenue','expense','equity')),
  check ((owner_kind is null) = (owner_id is null))
)

ledger_transactions (
  id                      uuid primary key,
  kind                    varchar(40) not null,
  ref_type                varchar(20) not null,
  ref_id                  uuid not null,
  idempotency_key         varchar(120) not null unique,
  occurred_at             timestamptz not null,
  custody_model           char(1) not null,
  reverses_transaction_id uuid null references ledger_transactions(id),
  created_at              timestamptz not null
)

ledger_entries (
  id             uuid primary key,
  transaction_id uuid not null references ledger_transactions(id),
  account_id     uuid not null references ledger_accounts(id),
  direction      char(1) not null,             -- 'D' | 'C'
  amount_cents   bigint not null,
  created_at     timestamptz not null,
  check (direction in ('D','C')),
  check (amount_cents > 0),
  unique (transaction_id, account_id, direction)
)
```

**Sinais.** O valor é sempre positivo; o sinal é a `direction`. Nunca gravar
número negativo. Saldo natural:

```
ativo/despesa:  Σ D − Σ C
passivo/receita: Σ C − Σ D
```

Uma view `v_ledger_balances` normaliza isso para "saldo natural", e é a única coisa
que telas e relatórios leem.

`unique (transaction_id, account_id, direction)` significa **uma partida por conta
e por direção em cada transação**. Se um evento precisar de duas partidas na mesma
conta, são duas transações — não uma transação com duas linhas iguais.

**Balanceamento.** Por transação: `Σ amount_cents(D) = Σ amount_cents(C)`.

- Verificação no serviço, antes do `flush`.
- Trigger `DEFERRABLE INITIALLY DEFERRED` no PostgreSQL, para pegar o que escapar
  do serviço — vale no `COMMIT`, então permite inserir partida a partida.
- Job noturno `ledger_integrity_check`: transação desbalanceada é incidente, não
  aviso.

Testes rodam em SQLite, onde o trigger não existe. Por isso a verificação de
serviço é obrigatória e tem teste próprio; o trigger é a segunda linha.

**Idempotência.** `idempotency_key` única por transação, no formato
`<kind>:<ref_id>` (ex.: `booking_confirmed:<booking_id>`). Repetir devolve a
transação existente. `IntegrityError` na chave → buscar e devolver, nunca propagar
como erro para o cliente.

**Concorrência.** Entradas são imutáveis; não há `UPDATE` em `ledger_entries`.
Saldos projetados (`credit_balances`, `venue_payable_balances`) são atualizados sob
`SELECT ... FOR UPDATE` na linha do dono, na mesma transação contábil. A ordem de
lock é fixa (por `account_id` crescente) para não gerar deadlock.

**Plano de contas** (código fixo, criado por migração):

| `code` | `kind` | O que é |
|---|---|---|
| `psp_clearing` | asset | recebido no PSP, ainda não liquidado |
| `bank` | asset | conta da JOGA |
| `player_credit:<user>` | liability | crédito pré-pago não consumido |
| `venue_payable:<venue>` | liability | valor da quadra a repassar |
| `fee_revenue` | revenue | comissão reconhecida na confirmação da reserva |
| `pass_deferred_revenue` | liability | trimestre do passe pago, mês não disponibilizado |
| `pass_revenue` | revenue | franquia mensal disponibilizada |
| `chargeback_receivable_player:<user>` | asset | jogador deve compra de crédito revertida |
| `venue_receivable:<venue>` | asset | quadra deve devolução paga a ela |
| `tax_payable` | liability | imposto apurado por lançamento explícito |
| `tax_expense` | expense | contrapartida da apuração |
| `psp_fee_expense` | expense | tarifa do PSP |
| `writeoff_expense` | expense | incobrável, com aprovação |
| `opening_equity` | equity | contrapartida da abertura do ledger no cutover |

**Regras de lançamento.** Esta é a parte que o backend precisa copiar:

| # | Evento | Débito | Crédito |
|---|---|---|---|
| 1 | Compra de crédito (R$ 100) | `psp_clearing` 10000 | `player_credit:u` 10000 |
| 2 | Liquidação do PSP | `bank` 10000 | `psp_clearing` 10000 |
| 3 | Tarifa do PSP | `psp_fee_expense` | `bank` |
| 4 | Reserva confirmada (quadra 15000 + taxa 3000) | `player_credit:u` 18000 | `venue_payable:v` 15000 + `fee_revenue` 3000 |
| 5 | Repasse à quadra | `venue_payable:v` 15000 | `bank` 15000 |
| 6 | Devolução integral antes do repasse | `venue_payable:v` 15000 + `fee_revenue` 3000 | `player_credit:u` 18000 |
| 7 | Devolução integral depois do repasse | `venue_receivable:v` 15000 + `fee_revenue` 3000 | `player_credit:u` 18000 |
| 8 | Chargeback da compra de crédito (saldo suficiente) | `player_credit:u` | `psp_clearing` |
| 9 | Chargeback da compra de crédito (saldo insuficiente) | `player_credit:u` (até zerar) + `chargeback_receivable_player:u` (resto) | `psp_clearing` |
| 10 | Venda de passe (trimestre) | `psp_clearing` | `pass_deferred_revenue` |
| 11 | Mês do passe disponibilizado | `pass_deferred_revenue` | `pass_revenue` |
| 12 | Imposto apurado | `tax_expense` | `tax_payable` |
| 13 | Incobrável (aprovação + auditoria) | `writeoff_expense` | `chargeback_receivable_*` |
| 14 | Abertura do ledger no cutover | conforme saldo devedor | `opening_equity` |
| 15 | Devolução em dinheiro de crédito não usado | `player_credit:u` | `psp_clearing` (ou `bank`) |
| 16 | Devolução em dinheiro de reserva não repassada | `venue_payable:v` + `fee_revenue` | `psp_clearing` (ou `bank`) |
| 17 | Devolução em dinheiro de reserva já repassada | `venue_receivable:v` + `fee_revenue` | `psp_clearing` (ou `bank`) |
| 18 | Devolução de passe não disponibilizado | `pass_deferred_revenue` | `psp_clearing` (ou `bank`) |

**Devolução em dinheiro: as regras que faltavam.** A §4.4 promete devolução em
dinheiro em dois casos — arrependimento de 7 dias e encerramento de conta — e sem
os eventos 15 a 18 a política não fechava contabilmente.

- **Nunca em duas etapas.** Devolver em crédito e depois "sacar" o crédito é
  proibido: cria justamente o caminho de saque que a ADR 0049 veta, e deixa rastro
  de conta de pagamento. A devolução em dinheiro sai direto de `player_credit` para
  `psp_clearing`/`bank`.
- **Nunca devolve mais do que existe.** `amount_cents ≤ saldo de player_credit`.
  Se a devolução pedida exceder, o excedente não existe — é erro de cálculo, não
  receivable.
- **Proporcional, sempre.** Devolução de reserva reverte `venue_payable` e
  `fee_revenue` na mesma proporção. Nunca se devolve taxa sozinha nem quadra
  sozinha: isso seria reescrever o preço depois do fato.
- **Depois do repasse, muda a conta.** Se a quadra já recebeu, o débito vai em
  `venue_receivable:v` (regra 17), não em `venue_payable` — que já está zerada.
- **Idempotência por pedido, não por valor:** `credit_refund:<refund_request_id>`.
  Duas devoluções legítimas do mesmo jogador são duas transações.
- **Estorno no PSP x transferência:** se o dinheiro volta pelo mesmo meio (Pix), o
  crédito é em `psp_clearing` e a liquidação segue o fluxo normal; se sai por
  transferência, é `bank`. O ledger registra os dois igualmente; a diferença é só a
  conta de caixa.

Cinco consequências que valem destacar:

- **A comissão vira receita na confirmação da reserva**, não na realização da
  partida. A confirmação é o momento em que a intermediação se completa: a quadra
  está contratada em nome do jogador e paga. Fazer a receita depender de a partida
  acontecer transformaria o JOGA em garantidor do serviço da quadra — que é
  exatamente o vetor 4 de descaracterização.
- **Cancelamento e devolução usam estorno**: débito em `fee_revenue`, nunca `UPDATE`
  e nunca exclusão. Se o estorno cai em competência diferente, ele aparece como
  redução de receita naquela competência, e o relatório mostra as duas.
- **A taxa nunca é calculada a partir de `tax_rate_bps`.** Imposto entra só pelo
  evento 12, com valor informado por quem apura. Se o código calcular imposto, ele
  está inventando alíquota.
- **O passe é o único diferimento real.** O trimestre é pago de uma vez e o mês é
  disponibilizado depois; por isso `pass_deferred_revenue`. Não confundir com a
  comissão: o passe é receita própria do JOGA, a comissão é receita de
  intermediação.
- **`player_credit` nunca fica negativo.** O que sobra vira receivable do jogador.
  Passivo negativo é dívida disfarçada; receivable é dívida explícita.

**Evento canônico da receita.** A receita nasce na transição da reserva para
`CONFIRMED` com o pagamento de **todas as participações ativas** confirmado. Esse é
o ponto exato em que a intermediação se completa — a quadra está contratada em nome
do jogador e paga.

O que **não** dispara lançamento contábil:

- `COMPLETED` — serve para fechar a partida, o rating e o histórico. Não é evento
  contábil. Se disparasse, a receita dependeria de a partida acontecer e o JOGA
  viraria garantidor do serviço da quadra (vetor 4).
- `presence_status` / check-in — serve para Trust Factor e disputa, não para receita.
- Reserva cancelada antes de `CONFIRMED` — nunca gera lançamento.
- Cancelamento depois de `CONFIRMED` — gera estorno (regras 6 e 7), nunca edição.

**Cutover.** O ledger nasce vazio na data de corte. Uma única transação
`kind='opening_balance'` lança o crédito migrado (§9.1) contra `opening_equity`.
Reservas anteriores ao corte **não** são relançadas — elas não tinham taxa e
relançar inventaria obrigação e receita.

**Aceite:** 100 transações aleatórias → `Σ D = Σ C` em todas; replay de qualquer
transação não duplica; `v_ledger_balances` de `player_credit` bate com
`credit_balances`; nenhum endpoint escreve em `ledger_entries` com `UPDATE`.

### 9.3 CPF: chave, acesso e LGPD  **[R]** para o desenho, **[B]** para a base legal

**Decisão: cifrar com AES-256-GCM, chave fora do banco, acesso por dois caminhos
auditados, retenção amarrada à obrigação fiscal.**

Colunas em `user_profiles`:

```sql
cpf_ciphertext   bytea       null,   -- nonce(12) || ciphertext || tag(16)
cpf_key_id       varchar(20) null,
cpf_last2        char(2)     null,   -- exibição mascarada
cpf_updated_at   timestamptz null
```

**Chave.**

- `JOGA_CPF_KEY` (32 bytes, base64) e `JOGA_CPF_KEY_ID`; nenhuma das duas no banco,
  no Git, no bundle ou em log.
- AAD = `user_id` em bytes. Copiar o ciphertext de um usuário para outro não
  decifra.
- Em produção, o boot **falha** se a chave faltar ou for igual ao placeholder
  documentado. Mesma lógica do §5.2: nunca degradar em silêncio.
- Rotação: subir `key_id` novo em `JOGA_CPF_PREVIOUS_KEYS` (mapa id→chave),
  rodar job de re-cifra em lotes, remover a chave antiga depois de 100%. Sem
  downtime e sem reescrever a chave no banco.

**Quem acessa.** Exatamente dois caminhos, ambos com registro em `audit_logs`
(ator, finalidade, `booking_id`, instante):

1. tela fiscal da quadra, para as reservas **daquela** quadra;
2. provedor de NFS-e, quando existir.

Jogador vê `cpf_present: bool` e `cpf_masked: "***.***.***-12"`. Suporte não vê
CPF por padrão; ver exige papel específico e fica auditado. CPF nunca entra em log
de aplicação, mensagem de erro, evento de analytics ou payload de webhook.

**Retenção.** Enquanto a conta existir. Pedido de exclusão anonimiza o perfil
(nome, e-mail, telefone, CPF), mas **preserva o documento fiscal** — número,
valor, data e o CPF do tomador cifrado no próprio registro fiscal — pelo prazo
legal aplicável. Sem isso a exclusão destrói prova que a lei manda guardar.

**Base legal.** Execução de contrato + obrigação legal fiscal. **Não** consentimento:
consentimento é revogável, e nota fiscal não. **[H]** A confirmação dessa base e do
prazo de guarda é do advogado/tributarista (P11 e J11 do termo de referência).

### 9.4 NFS-e ausente bloqueia o repasse?  **[R]** — sim

**Decisão: sim, bloqueia o repasse da quadra, com prazo de tolerância e override
auditado.**

- `JOGA_PAYOUT_REQUIRES_FISCAL_DOCUMENT = true` (padrão no modo `placeholder`).
- Documento `issued` ou `not_required` → valor liberado.
- `pending_manual` há mais de `JOGA_FISCAL_DOCUMENT_GRACE_DAYS` (padrão **5**) →
  **o repasse daquela quadra é retido por inteiro**, não só a linha da reserva.
  Bloqueio parcial é inaplicável na operação e não prova nada.
- Ao reter: alerta para a quadra, alerta interno, e a reserva entra no relatório
  "sem nota".
- Override manual: papel específico, justificativa obrigatória, validade de uma
  execução, registro em `audit_logs`. Sem override silencioso por env.
- Reincidência sistemática é quebra de contrato, tratada comercialmente — não é
  caso para o código decidir sozinho.

Razão: o teste 6 da ADR 0049 só vale se a cadeia for verificável. Se a nota pode
faltar e o dinheiro sai igual, a cadeia é declaração de intenção.

**[B] sem a cláusula contratual, a retenção é inexigível.** O contrato com o
estabelecimento precisa autorizar expressamente a retenção do repasse enquanto
houver reserva sem NFS-e contra o jogador (ADR 0049 §9, item 10). Enquanto a
cláusula não existir, a implementação pode existir atrás de flag, mas não pode ser
ligada em produção com quadra real.

### 9.5 Chargeback × repasse já pago  **[R]**

**Primeiro, a distinção que resolve o problema:** o chargeback só existe sobre
**compra de crédito** (ou de passe), nunca sobre reserva. Reserva é paga com
crédito, e crédito é saldo, não cobrança nova. Logo **não existe clawback de
quadra por fraude de jogador**.

Consequências:

- Chargeback de compra de crédito → eventos 9/10 do §9.2. A quadra não é afetada.
  O crédito é removido; o que faltar vira receivable do jogador.
- Jogador com receivable: **bloqueado de comprar crédito**, não de jogar com saldo
  existente, e **nunca suspenso automaticamente**. Suspensão automática por dívida
  é decisão jurídica que não tomamos.
- Devolução de reserva **depois** de a quadra já ter recebido → evento 11:
  `venue_receivable`. Cobrança: compensação no próximo repasse; se não houver
  repasse em `JOGA_VENUE_RECEIVABLE_OFFSET_DAYS` (padrão **90**), fatura com
  vencimento em 10 dias; 30 dias em atraso → bloqueio de **novas reservas** naquela
  quadra; write-off só com aprovação administrativa, motivo e auditoria.
- Quadra que discorda: contestação formal em 10 dias, com o comprovante da reserva
  e o documento fiscal. Enquanto contestada, o receivable fica em aberto e **não**
  vira despesa. Não há cobrança automática durante a contestação.

**[B]** A cláusula de compensação e o prazo de 90 dias precisam estar no contrato
com o estabelecimento (ADR 0049 §9). Sem cláusula, a compensação não é oponível.

### 9.6 Alíquota versionada por competência  **[P]**

`JOGA_TAX_RATE_BPS` sozinho **não serve** para relatório histórico: a alíquota
efetiva do Simples muda com a receita e o ISS varia por município.

```sql
tax_rate_versions (
  id                 uuid primary key,
  competencia        char(7)  not null,   -- 'YYYY-MM'
  regime             varchar(20) not null,-- 'simples'
  annex              varchar(4)  null,    -- 'III','V'
  municipality_ibge  char(7)   null,
  iss_rate_bps       int       null,      -- retenção do tomador PJ
  effective_rate_bps int       not null,  -- alíquota aplicada ao relatório
  source_ref         varchar(200) not null, -- de onde veio o número
  approved_by        varchar(120) null,
  created_at         timestamptz not null,
  unique (competencia, regime, annex, municipality_ibge)
)
```

- Relatório de margem resolve a versão pela **competência do evento de receita**,
  não pela data do relatório.
- Sem versão cadastrada para a competência: **o relatório falha**, com mensagem
  clara. Não cai para env, não usa a última conhecida, não estima.
- `JOGA_TAX_RATE_BPS` fica apenas para ambiente local e teste.
- Quem preenche é o contador, por competência, antes do fechamento. Não é código.

### 9.7 Aceite dos Termos  **[R]**

`terms_version` no teto por partida não é consentimento: é o registro de qual texto
estava vigente. Falta o aceite com prova.

```sql
terms_acceptances (
  id                uuid primary key,
  user_id           uuid not null references users(id),
  terms_version_id  uuid not null references terms_versions(id),
  context           varchar(20) not null,  -- signup|credit_purchase|pass_purchase|booking_ceiling
  accepted_at       timestamptz not null,
  ip_hash           char(64) not null,     -- hash, nunca IP cru
  user_agent_hash   char(64) null,
  terms_hash        char(64) not null,     -- sha256 do content aceito
  unique (user_id, terms_version_id, context)
)
```

- `terms_hash` prova **o que** foi mostrado mesmo que o texto mude; `ip_hash` usa o
  segredo de hash já existente (`JOGA_PHONE_HASH_SECRET`), nunca IP em claro.
- Obrigatório em: **cadastro** (bloqueia qualquer reserva), **cada compra de
  crédito** (é onde nasce a relação contratual) e **teto por partida** (§3.7).
- Aceite só contra `terms_versions.status = 'approved'`; `draft` é recusada.
- O teto referencia `terms_acceptance_id`, não só a string da versão.
- Sem aceite → operação recusada com `terms_not_accepted`.
- Exportação de prova por usuário (versão, hash, instante, hash de IP) para
  contestação. **[B]** O valor probatório é do advogado; o dado tem de existir.

### 9.8 Nome único da flag  **[R]**

`JOGA_MONEY_MODE = simulated | real`. **Só.** Toda menção a
`JOGA_REAL_MONEY_ENABLED` foi removida. O backend não deve criar alias, variável
depreciada nem leitura dupla: dois nomes para a mesma decisão é como se descobre,
em produção, que metade do sistema está num modo e metade no outro.

### 9.9 Referência do parecer como evidência  **[R]**

String solta não prova nada. Três valores, todos obrigatórios com
`JOGA_MONEY_MODE=real`:

| Variável | Formato | Exemplo |
|---|---|---|
| `JOGA_LEGAL_APPROVAL_REF` | identificador do documento | `parecer-fiscal-juridico-2026-11` |
| `JOGA_LEGAL_APPROVAL_SHA256` | 64 hex do PDF | `9f2c…` |
| `JOGA_LEGAL_APPROVAL_DATE` | `YYYY-MM-DD` | `2026-11-30` |

Boot falha se faltar qualquer um, se o hash não for 64 hex, ou se a data estiver no
futuro. O PDF fica em armazenamento privado e imutável, endereçado pelo hash. Assim
"existe parecer" vira "existe este parecer, nesta versão, nesta data", que é o que
se consegue mostrar depois.

### 9.10 Arredondamento e rateio  **[R]**

**Taxa.**

```
fee_cents = round_half_up(venue_price_cents × fee_percent_bps / 10000)
fee_cents = max(fee_cents, fee_min_cents)
fee_cents = min(fee_cents, venue_price_cents)
```

`round_half_up`, não banker's rounding: 0,5 centavo sobe. O teto em
`venue_price_cents` impede taxa maior que a quadra em configuração errada.

**Rateio por participante.** Não se arredonda a cota; divide-se o inteiro.

```
base = total // n
rem  = total %  n
assentos 1..rem pagam base + 1
assentos rem+1..n pagam base
```

Rateio da linha espaço usa `venue_price_cents`; rateio da taxa usa `fee_cents`.
Cada participante fica com
`contribution_cents = space_charge_cents + fee_charge_cents`.

**Quem absorve a fração de centavo: ninguém.** Não sobra fração — a divisão inteira
distribui o resto por ordem de assento. O problema de "centavo perdido" só existe
quem arredonda cada cota isoladamente.

**Exemplo — quadra R$ 150, 20%, 9 jogadores:**

```
fee   = round(15000 × 0,20) = 3000
total = 18000

espaço: 15000 // 9 = 1666, resto 6 → 6 × 1667 + 3 × 1666 = 10002 + 4998 = 15000 ✓
taxa:    3000 // 9 =  333, resto 3 → 3 ×  334 + 6 ×  333 =  1002 + 1998 =  3000 ✓
contribuição: 3 jogadores 2001, 3 jogadores 2000, 3 jogadores 1999 = 18000 ✓
```

**Assento vago, e por que absorção não existe.** `SUM(space_charge_cents) =
venue_price_cents` vale **sem exceção**. Não existe `joga_absorption_cents`, nem
"absorção explícita com aprovação". A versão anterior deste documento permitia, e
estava errada: a ADR 0049 §3.3 e o vetor 1 da §4 proíbem a plataforma de cobrir
diferença de preço, porque cobrir diferença é assumir risco de preço — o
comportamento de dono, não de intermediário. Absorção com aprovação continua sendo
absorção; o carimbo não muda a natureza.

Consequências operacionais, sem saída pela tangente:

- **Reserva só confirma quando as cotas fecham o preço da quadra.** Com assento
  vago, ela não confirma naquele preço. O jogador recebe as saídas da ADR 0042
  §6.5: aumentar o teto, mudar de faixa, ampliar região/horário, ou esperar.
- **Se a quadra aceitar cobrar menos por aquele horário**, isso é **preço novo**,
  não desconto: grava-se cotação versionada com autor e data (§9.11) e o rateio é
  recalculado sobre o novo `venue_price_cents`. Não existe coluna de desconto.
- **Cancelamento depois de confirmada não mexe na linha do espaço.** As cotas
  continuam somando o preço da quadra; a devolução é transação separada (regras 6 e
  7 do §9.2) e o buraco é coberto pela provisão de cancelamento, que é despesa — não
  é abatimento do preço da quadra.
- **Se um dia for inevitável**, a decisão exige emenda à ADR 0049 com justificativa
  jurídica, e a emenda vem **antes** do código. Não se cria a coluna "por
  precaução".

O que a regra proíbe, no fim, é a diferença que aparece no relatório e ninguém sabe
explicar. A forma de garantir isso não é permitir a coluna com aprovação: é não
ter a coluna.

**Aceite:** propriedade `Σ cotas = total` testada com `n` de 1 a 30 e valores de
1 a 100000 centavos; nenhuma cota negativa; nenhuma cota zero quando `total ≥ n`.

### 9.11 Assento vago: o fluxo operacional  **[R]**

**Primeiro, o fato que muda a pergunta.** O rateio é feito sobre os participantes
**confirmados**, não sobre a capacidade da quadra. Com 9 confirmados numa quadra de
R$ 150, cada um paga R$ 16,67 e a soma continua sendo R$ 150,00. Assento vago, por
si só, **não** gera buraco.

O buraco só existe quando a cota de alguém **passa do teto** que ela aceitou. Ex.:
quadra de R$ 150 com 6 confirmados → R$ 25,00 por pessoa; quem aceitou teto de
R$ 20,00 não pode ser cobrado. Aí a reserva **não confirma** naquele preço.

Cinco saídas, nesta ordem:

| # | Saída | Quem decide | Efeito |
|---|---|---|---|
| 1 | Entra mais jogador | fila/substituição | cota volta para dentro do teto |
| 2 | O jogador aumenta o próprio teto | **jogador**, com novo aceite | cota passa a caber |
| 3 | A quadra baixa o preço daquele horário | **quadra** | cota cai |
| 4 | Outro horário / outra faixa / outra região | jogador | nova partida |
| 5 | A reserva não acontece | automático | devolução integral |

**Quem altera `venue_price_cents`: só a quadra.** A plataforma nunca edita preço,
nem "para destravar". Se a JOGA pudesse baixar o preço para a partida fechar, ela
estaria fixando preço — vetor 2 e teste 4 da ADR 0049. A JOGA pode **pedir** um novo
preço; quem publica é o estabelecimento.

**Registro do preço novo.** Não é `UPDATE` em `bookings`. É cotação versionada:

```sql
booking_price_quotes (
  id                uuid primary key,
  booking_id        uuid not null references bookings(id),
  version           int  not null,
  venue_price_cents int  not null,
  author_user_id    uuid not null references users(id),  -- operador da quadra
  author_role       varchar(20) not null,                 -- 'venue'
  reason            varchar(200) not null,
  created_at        timestamptz not null,
  expires_at        timestamptz null,
  unique (booking_id, version),
  check (venue_price_cents > 0)
)
```

`bookings.price_quote_id` aponta para a cotação vigente. A cotação anterior fica no
histórico — nada é apagado. Preço de reserva confirmada é **congelado**: cotação
nova não altera reserva antiga, e reajuste de tabela da quadra vale só para reservas
futuras (ADR 0042 §9.7).

**Prazo.** Cotação só é aceita enquanto a reserva está em `HOLD_CONFIRMED`,
`PAYMENT_PENDING` ou `SUBSTITUTING`. Depois de `CONFIRMED`, não há cotação
retroativa. `expires_at` (padrão 2 horas, configurável) evita cotação eterna.

**Quem precisa reaceitar.** A regra é sobre o valor **individual**, não o total:

- **Cota diminui** (quadra baixou o preço): **não** precisa reaceitar — pagar menos
  está dentro do que já foi aceito. Em `HOLD_CONFIRMED` não houve débito de crédito:
  o que diminui é o valor reservado, e não há o que devolver. Se por algum motivo já
  houve débito, a diferença volta como crédito; em dinheiro só na janela de 7 dias
  ou no encerramento da conta (§4.4, regra 15 do §9.2).
- **Cota aumenta**: exige **novo aceite explícito** daquele participante, com novo
  `max_credits_cents` e `terms_acceptance_id`. Quem não reaceitar dentro do prazo
  sai com devolução integral, sem penalidade.
- **Cota aumenta acima do teto e o jogador não reaceita**: a reserva volta para o
  estado anterior; não se cobra "quase confirmado".

**Sequência canônica.** Para o backend não inventar ordem:

1. calcular o rateio sobre os confirmados;
2. se todas as cotas couberem nos tetos → confirma;
3. se alguma não couber → abrir a lista de saídas (§tabela);
4. quadra publica cotação → recalcular rateio;
5. se as cotas diminuíram → confirmar, notificar, devolver diferença;
6. se as cotas aumentaram → colher reaceite; quem não reaceitar sai com devolução;
7. confirmar só quando `Σ space_charge_cents = venue_price_cents` da cotação vigente.

**Aceite:** não existe caminho de código que altere `venue_price_cents` sem
`author_role = 'venue'`; reserva confirmada não muda de preço; toda mudança de preço
pré-confirmação gera cotação nova, nunca `UPDATE` no valor antigo; soma das cotas
bate com a cotação em todos os estados.

---

## 10. Mensagem ao agente de backend

Você pediu dez especificações e disse que não começaria sem elas. Elas estão na
§9. Leia nesta ordem: **9.10 → 9.11 → 9.2 → 9.1 → 9.3 → 9.7 → 9.4 → 9.5 → 9.6
→ 9.8 → 9.9**. Arredondamento, cotação de preço e ledger primeiro porque todo o
resto depende deles.

**Correções desta revisão.** As dezesseis inconsistências apontadas foram fechadas
assim — se você já tinha começado por alguma delas, releia:

| # | Era | Fica |
|---|---|---|
| 1 | absorção explícita permitida | **proibida**, sem coluna; assento vago = reserva não confirma |
| 2 | receita na confirmação em um lugar, diferida em outro | **receita na confirmação**, um lugar só (ADR §7 e §9.2) |
| 3 | plano de contas sem `tax_expense`, passe e abertura | 14 contas, incluindo as três |
| 4 | `_active_lots` sem `free_level`/`admin` | query completa na §9.1, `admin` e `free_level` nunca saem |
| 5 | lote "imutável" com `remaining` mutável | `remaining` é projeção; verdade é `ticket_lot_consumptions` |
| 6 | dois saldos sem regra de leitura | `get_balances(user)` é o único ponto; tabela de fases na §9.1 |
| 7 | `legacy_balance` como `source` | é `ref_type` de lote `source='admin'`; nenhum `source` novo |
| 8 | ordem de consumo sem `free_level`/`admin` | `pass → free_level → admin → purchase → refund` (muda o código) |
| 9 | "partida realizada ou presença" como evento | evento é a transição para `CONFIRMED`; `COMPLETED` não é contábil |
| 10 | devolução de pacote/passe ausente | §4.4 e cláusula C13 da ADR, quatro situações distintas |
| 11 | retenção de repasse sem base contratual | cláusula 10 do contrato com a quadra (ADR §9) |
| 12 | arquivos não versionados | bloqueado: exige autorização explícita de commit |
| 13 | devolução em dinheiro sem lançamento | regras 15 a 18 da §9.2 |
| 14 | assento vago sem fluxo operacional | §9.11: cotação da quadra, autor, prazo e reaceite |
| 15 | pacote depois de 7 dias indefinido | **não há devolução em dinheiro**, exceto encerramento (§4.4) |
| 16 | `test_mark_issued_and_failed` falhando | corrigido: suíte com **12 testes, 12 passam** |

Dois pontos da tabela **mudam comportamento existente** e não são refactor:
o item 4/8 (ordem de consumo em `SOURCE_PRIORITY`) e o item 6 (leitura de saldo).
Os dois exigem teste próprio e um teste de migração de dados.

**O que está liberado agora (não espere parecer):**

1. `money.py` com `compute_fee_cents` e `allocate_cents`, e os testes de
   propriedade da §9.10. É função pura, sem banco, sem flag. Comece por ela.
2. `ledger_accounts` / `ledger_transactions` / `ledger_entries` com a verificação
   de balanceamento no serviço e o trigger diferido no Postgres (§9.2).
3. Migração de lotes da §9.1, **em modo dry-run primeiro**, com o relatório por
   usuário e o aborto por teto de crédito.
4. `terms_acceptances` com `ip_hash` e `terms_hash` (§9.7).
5. `tax_rate_versions` (§9.6) — tabela e resolução por competência, sem cálculo.
6. As três variáveis do §9.9 e o endurecimento do validador de boot.
7. `booking_price_quotes` e o fluxo de assento vago da §9.11 — só a quadra
   publica preço; a plataforma nunca edita.
8. As regras 15 a 18 do §9.2 (devolução em dinheiro), sem as quais a §4.4 não
   fecha.

**O que não fazer, mesmo que pareça simples:**

- Não criar `CustodyAdapter`. Não há segunda implementação.
- Não calcular imposto a partir de `tax_rate_bps`.
- Não converter ingresso gratuito, de XP ou de passe em centavos.
- Não relançar reserva anterior ao corte no ledger.
- Não criar alias de `JOGA_MONEY_MODE`.
- Não fazer clawback de quadra por chargeback de jogador (§9.5).
- Não criar coluna de absorção nem de desconto na linha do espaço (§9.10).
- Não tratar `COMPLETED` como evento contábil (§9.2).

**Versionamento.** Os documentos desta rodada estão **untracked** no Git. Não
commitei porque a instrução do repositório só permite commit com autorização
explícita, e ela não foi dada para esta entrega. Se a implementação vai começar a
partir deles, versione antes: documento não versionado não é fonte da verdade, é
rascunho compartilhado.

**Estado do código que já existe.** Os placeholders de fiscal e termos estão
implementados (`app/modules/fiscal/`, `app/modules/legal/`, migração
`i2e3f4a5b6c7`, flags em `config.py`). A suíte
`tests/test_fiscal_legal_placeholders.py` roda **12 testes, 12 passam** —
a falha anterior era só a chamada de `mark_issued`/`mark_failed` sem `db_session`,
já corrigida.

O que **não** existe e continua sendo seu: ledger, migração de saldos,
`booking_price_quotes`, `terms_acceptances`, `tax_rate_versions` e as regras 15 a
18.

**O que eu ainda devo a você, e não é código:** o parecer fiscal (P1–P11) e o
jurídico (J1–J11), em `docs/TERMO_DE_REFERENCIA_PARECERES.md`. Enquanto eles não
existirem, `JOGA_MONEY_MODE=real` não sobe, e isso é intencional.

**O que continua bloqueado de verdade:** emitir NFS-e, mover dinheiro real,
operar custódia C, publicar Termos, fixar alíquota.
