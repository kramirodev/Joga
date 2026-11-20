# ADR 0053 — Destino financeiro da quadra pública

- **Numeração:** esta ADR ocupa o número **0053** porque o **0052** foi ocupado
  pela ADR “Modo demo sem PSP e sem dinheiro real”, criada no mesmo dia. A
  numeração foi conferida em `docs/ADR/` antes da entrega.
- **Status:** Aprovado como direção em 2026-11-20. Implementação pendente na 14B
  (backend/PSP) e na 15B (painel). **Bloqueado para dinheiro real** até a 14B, a
  19A e os pareceres da ADR 0049.
- **Data:** 2026-11-20
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0049 (modelo tributário e ledger), ADR 0042 (ingresso e
  intermediação), ADR 0040 (repasse em `starts_at + 2h`), ADR 0039
  (cancelamento, substituição e ausência), ADR 0037 (reembolsos e conciliação),
  ADR 0048 (Mercado Pago centralizado), ADR 0021 (precificação),
  `docs/DECISOES_BACKEND_ADR_0049.md` §9.2, `docs/CONTRATO_RESERVAS_APP.md` §20,
  `harness/build-log.md` (2026-11-19, risco aberto do `payout_ready`) e
  `harness/build/phase-14b-mp-hardening.md`.
- **Substitui, no que conflitar:** a leitura de que toda reserva gera obrigação
  de repasse (ADR 0040, ADR 0042 §1.2 e ADR 0049 §2.2/§2.7/§7) **somente para a
  quadra pública operada pelo JOGA**. Não altera o modelo de intermediação das
  quadras de terceiros.

---

## 0. Natureza deste documento

Este documento não é parecer jurídico nem fiscal. Ele registra uma decisão de
modelagem para que contador, advogado e engenharia partam do mesmo fato: a
quadra pública é operada pelo JOGA, não por um estabelecimento terceiro. A
validação profissional continua na 19A; o que este documento faz é impedir que
o código trate a quadra pública como se houvesse um fornecedor a receber.

Marcação usada:

| Marca | Significa |
|---|---|
| **[F]** | Fato documentado no repositório ou no código |
| **[D]** | Decisão tomada neste documento |
| **[I]** | Interpretação contábil, fiscal ou jurídica — não vinculante |
| **[H]** | Hipótese que exige validação profissional antes de produzir efeito |

---

## 1. Contexto

### 1.1 O que existe hoje

A 14E e a entrega de quadras públicas criaram uma organização seed
`joga-publico` (`organizations.is_platform = true`) e marcaram suas quadras com
`organization_venues.is_public = true`. A quadra pública é reservável, tem preço
em faixa e aparece no discovery como “Quadra pública” / “Quadra da plataforma
JOGA”. **[F]**

Para permitir a reserva sem chave Pix/CNPJ, `payout_ready()` passou a devolver
`True` para qualquer organização com `is_platform = true`:

```python
def payout_ready(organization):
    if organization.is_platform:
        return True
    return bool(
        organization.payout_status == "active"
        and organization.pix_key
        and organization.legal_document
    )
```

**[F]** O efeito colateral é que a plataforma passou a satisfazer o portão
desenhado para fornecedores de terceiros.

### 1.2 O problema financeiro

Na confirmação de uma reserva, `post_booking_confirmed` credita
`venue_payable:<venue>` com o valor da quadra e `fee_revenue` com a taxa. Para a
quadra pública, o credor desse passivo é a própria `joga-publico`. Em seguida,
`FinancialService.ensure_release` cria uma `venue_release` para a organização da
plataforma, e `release_due` a libera em `starts_at + 2h`, lançando
`D venue_payable` / `C bank`. **[F]**

O resultado é uma obrigação com o próprio JOGA, um repasse para uma conta que
não existe e um crédito em `bank` que não corresponde a saída real de dinheiro.
No demo, `money_mode=simulated`; o PSP e o CPF/CNPJ ainda não estão
configurados. O build-log de 2026-11-19 registrou esse risco como aberto. **[F]**

### 1.3 O fato que decide

A quadra pública **não é um espaço de terceiro intermediado pelo JOGA**. O
próprio JOGA opera a quadra, define a disponibilidade e presta o serviço de uso
do espaço. Não há fornecedor a quem repassar o valor da quadra. **[F]/[D]**

Isso não é um detalhe operacional: muda a natureza da receita. Na quadra
privada, o valor do espaço é dinheiro de terceiro e a receita do JOGA é a
comissão (ADR 0049 §2.2). Na quadra pública, o valor inteiro pago pelo jogador é
receita do serviço próprio do JOGA, e não comissão de intermediação. **[I]**

### 1.4 Por que a decisão não pode ser adiada

Manter o desenho atual tem três efeitos mensuráveis:

1. o passivo `venue_payable:joga-publico` cresce sem credor real;
2. `venue_release` e o extrato do fornecedor mostram repasses que nunca
   aconteceram;
3. a conciliação entre ledger, PSP e banco nunca fecha para a quadra pública.

O demo pode operar assim por pouco tempo porque o dinheiro é simulado, mas cada
reserva nova aumenta o passivo fictício e o custo de correção. **[D]**

---

## 2. Decisão

### 2.1 Alternativa escolhida: A — receita da plataforma, sem repasse

**[D]** A quadra pública é tratada como **serviço próprio do JOGA**, não como
intermediação de espaço alheio. O valor pago pelo jogador é receita da
plataforma. Não existe `venue_payable` para a quadra pública, não existe
`venue_release` e não existe repasse para `joga-publico`.

A receita é registrada em conta própria, **separada da comissão de
intermediação**:

| Conta | Natureza | O que registra |
|---|---|---|
| `public_venue_deferred_revenue` | passivo | valor recebido/consumido por reserva pública ainda não prestada |
| `public_venue_revenue` | resultado | receita do serviço próprio da quadra pública, no momento da prestação |

O valor do espaço e a taxa continuam existindo como composição de preço na
reserva (`venue_price_cents`, `fee_cents`, `total_cents`), mas **não** são
tratados como comissão. O relatório financeiro da quadra pública soma os dois
como receita própria; o relatório de comissão do JOGA não os inclui. **[D]**

### 2.2 Reconhecimento

**[D]** A receita da quadra pública é reconhecida quando o serviço é prestado,
não na confirmação. O marco é o mesmo da ADR 0040: `starts_at + 2h`. Se a
reserva for concluída antes disso por evento inequívoco de prestação, o evento
de conclusão pode antecipar o reconhecimento; nunca se reconhece antes de o
espaço ter sido disponibilizado.

- Na confirmação: o valor consumido é **diferido** em
  `public_venue_deferred_revenue`.
- Na prestação: `D public_venue_deferred_revenue` / `C public_venue_revenue`.
- No cancelamento antes da prestação: o diferido é revertido e o jogador é
  reembolsado conforme a ADR 0039.
- No no-show depois do cutoff: a receita é reconhecida, porque o espaço foi
  disponibilizado; não há repasse.
- Na falha da plataforma ou da quadra pública: devolução integral, reversão do
  diferido ou da receita já reconhecida, sem repasse.

A regra vale para pagamento por crédito e por Pix. Para vaga financiada por
passe, a receita do passe já foi reconhecida na disponibilização mensal (ADR
0049 §2.6); a alocação para a quadra pública é uma **reclassificação** de
`pass_revenue` para `public_venue_deferred_revenue` e, depois, para
`public_venue_revenue`, sem criar receita nova. Para vaga grátis ou
administrativa, permanece a despesa promocional, sem receita de quadra pública.
**[D]**

### 2.3 Definição operacional de “quadra pública”

**[D]** Só entra neste fluxo a quadra que satisfaz **as duas** condições:

1. `organization.is_platform = true`; e
2. `organization_venue.is_public = true`, com operação efetivamente feita pelo
   JOGA.

Se uma quadra marcada como pública for, na realidade, operada por terceiro
(prefeitura, associação, concessionário ou parceiro), ela **não** pode usar este
fluxo. Deve ser reclassificada como quadra privada e voltar a exigir
`payout_ready` e repasse. A flag `is_public` não é autorização para dispensar
fornecedor. **[D]**

### 2.4 O que não muda

- A intermediação das quadras privadas continua exatamente como na ADR 0049:
  valor do espaço como passivo, comissão como receita, repasse em
  `starts_at + 2h`.
- O jogador continua comprando crédito, consumindo tickets e recebendo
  devolução em crédito, conforme ADR 0042/0049.
- A custódia continua no modelo B do protótipo, com a migração para C pendente
  de ADR própria.
- `money_mode=real` continua bloqueado até 14B/19A e pareceres.

---

## 3. Consequências

### 3.1 Consequências positivas

- O ledger deixa de criar um passivo sem credor.
- O extrato do fornecedor de `joga-publico` fica vazio por definição, e o painel
  não promete repasse.
- A quadra pública pode ser reservada sem chave Pix/CNPJ, sem que
  `payout_ready` minta sobre a existência de um destino de repasse.
- A conciliação da quadra pública passa a ter uma pergunta respondível: o
  diferido e a receita reconhecida batem com as reservas confirmadas,
  concluídas e reembolsadas.
- A receita própria fica separada da comissão, o que preserva a leitura correta
  da intermediação das quadras privadas.

### 3.2 Consequências negativas e custos

- O JOGA passa a ter **duas naturezas de receita**: comissão de intermediação e
  serviço próprio de quadra pública. Isso exige separação contábil, fiscal e de
  relatório; misturar as duas enfraquece a tese da ADR 0049.
- A quadra pública passa a exigir documento fiscal do próprio JOGA (NFS-e pelo
  uso do espaço), não do estabelecimento. Sem CNPJ/inscrição municipal da
  empresa operadora, não há operação com dinheiro real.
- O risco de chargeback da quadra pública é risco da plataforma. Não há
  fornecedor contra quem abrir receivable.
- A plataforma passa a responder, perante o jogador, como prestadora do serviço
  de uso do espaço, e não apenas como intermediária. Isso tem efeito
  consumerista e securitário que precisa ser revisto nos Termos.
- O código precisa de um ramo novo no ledger, no release, no extrato, na
  conciliação e no painel. Não é uma correção de uma linha.

### 3.3 Consequência de escopo

A ADR 0049 continua sendo a referência para quadras privadas. Esta ADR **não**
autoriza reconhecer o valor cheio de uma quadra privada como receita, **não**
autoriza dispensar CNPJ/Pix de fornecedor privado e **não** autoriza usar
`is_platform` como atalho de elegibilidade. **[D]**

---

## 4. Alternativas consideradas

### 4.1 B — retenção até haver conta/CNPJ da organização

**Descartada.** A retenção manteria `venue_payable:joga-publico` e a
`venue_release` pendente até a organização ter conta e CNPJ. Parece conservadora,
mas é incoerente:

- o credor e o devedor seriam a mesma pessoa jurídica;
- não há transferência real a fazer; pagar a si mesmo não é repasse;
- o passivo cresceria indefinidamente, sem evento que o extinga;
- a receita ficaria subdeclarada e o passivo superdeclarado;
- a conciliação continuaria sem contraparte externa;
- criar CNPJ para `joga-publico` não resolve a natureza da receita; apenas
  desloca o problema para uma transferência interna sem causa.

A falta de CNPJ é real, mas é um bloqueio de **operação com dinheiro real e
emissão fiscal**, não uma razão para manter um passivo fictício. **[D]**

### 4.2 C1 — tratar a quadra pública como quadra privada

**Não escolhida, mas é o caminho correto se o fato mudar.** Se a quadra pública
for operada por um terceiro, ela deve ser modelada como quadra privada: CNPJ,
chave Pix, `payout_ready`, `venue_payable`, `venue_release` e repasse. O que não
se pode é usar `is_public` para mascarar um fornecedor existente. **[D]**

### 4.3 C2 — quadra pública gratuita ou somente demonstração

**Não escolhida nesta fase.** O contrato de reservas diz que a quadra pública é
reservável com preço em faixa, e não há quadra gratuita. Se a 19A concluir que a
cobrança pelo uso de um bem público não é permitida sem concessão, a saída é
tornar a quadra pública gratuita/somente demonstração, sem receita e sem
repasse. Isso exigiria ADR própria e mudaria o produto. **[H]**

### 4.4 C3 — reconhecer o valor cheio como `fee_revenue`

**Descartada.** Chamar de “comissão” o valor de um serviço próprio confunde
relatório, base de cálculo e narrativa. A receita própria precisa de conta e
rótulo próprios. **[D]**

### 4.5 C4 — manter o desenho atual e apenas não liberar

**Descartada.** É a alternativa B com outro nome: o passivo e a release
continuam existindo, e o worker precisa de uma exceção permanente para não
liberá-los. Exceção permanente em fluxo financeiro é dívida técnica e risco de
regressão. **[D]**

---

## 5. Impacto no ledger

### 5.1 Contas

Novas contas singleton:

| Código | Tipo | Uso |
|---|---|---|
| `public_venue_deferred_revenue` | liability | valor de reserva pública confirmada e ainda não prestada |
| `public_venue_revenue` | revenue | receita própria da quadra pública na prestação |

Não criar `venue_payable:<public_venue>` nem `venue_receivable:<public_venue>`
para quadra pública. `fee_revenue` continua exclusivo da comissão de
intermediação. **[D]**

### 5.2 Lançamentos por evento

**Confirmação, pagamento por crédito:**

```text
D player_credit:<user>                  k × 310
C public_venue_deferred_revenue         k × 310
```

**Confirmação, pagamento por Pix:**

```text
D psp_clearing                          total
C public_venue_deferred_revenue         total
```

**Confirmação, vaga por passe:**

```text
D pass_revenue                          space_charge
C public_venue_deferred_revenue         space_charge
```

**Prestação (`starts_at + 2h` ou conclusão):**

```text
D public_venue_deferred_revenue         valor diferido
C public_venue_revenue                  valor diferido
```

**Reembolso antes da prestação:**

```text
D public_venue_deferred_revenue         valor diferido
C player_credit:<user> / psp_clearing   valor devolvido
```

**Reembolso depois da prestação (falha da plataforma/quadra):**

```text
D public_venue_revenue                  valor devolvido
C player_credit:<user> / psp_clearing   valor devolvido
```

**Chargeback depois da prestação:** mantém a receita e registra receivable
contra o jogador (`chargeback_receivable_player:<user>`), nunca contra a quadra.
O risco é da plataforma. **[D]**

### 5.3 Invariantes

- Nenhuma conta de jogador fica negativa.
- Todo lançamento fecha em zero (débitos = créditos).
- `public_venue_deferred_revenue` só é creditado por reserva pública confirmada
  e só é debitado por prestação, reembolso ou reclassificação.
- `public_venue_revenue` nunca recebe lançamento de reserva privada.
- Não existe `venue_payable` com owner `joga-publico` após a migração.
- Replay de confirmação, prestação ou reembolso não duplica lançamento; as
  chaves de idempotência continuam por evento (`booking:{id}:confirm`,
  `booking:{id}:refund`, `release:{id}`).

### 5.4 Migração dos dados existentes

**[D]** A correção é por **lançamento compensatório**, não por edição ou exclusão
de histórico:

1. Para cada `venue_payable:joga-publico` com saldo de reserva pública:
   - se o serviço ainda não foi prestado, reclassificar para
     `public_venue_deferred_revenue`;
   - se já foi prestado, reclassificar para `public_venue_revenue`.
2. Para cada `venue_release` da organização da plataforma:
   - `PENDING` → `REVERSED` com motivo `platform_own_service`, sem lançamento
     de banco;
   - `RELEASED` → compensating entry `D bank` / `C public_venue_revenue` (ou
     `public_venue_deferred_revenue`, conforme a prestação), porque o crédito em
     `bank` foi simulado e não houve saída real;
   - `FAILED`/`REVERSED` → manter, apenas auditar.
3. Registrar auditoria com ator de sistema, motivo e referência à reserva.
4. A migração é idempotente: repetir não duplica a compensação.

O histórico de `venue_releases` não é apagado; o status e a auditoria contam a
história. **[D]**

---

## 6. Impacto em reembolso, cancelamento, disputa e conciliação

### 6.1 Reembolso

- Antes da prestação: devolução integral conforme ADR 0039; o diferido é
  revertido. Não há `venue_receivable`.
- Depois da prestação, por falha da plataforma/quadra: a receita é estornada e o
  jogador é reembolsado; não há repasse a recuperar.
- Chargeback: receita permanece se o serviço foi prestado; o receivable é contra
  o jogador. Se o serviço não foi prestado, a receita/diferido é revertido e o
  receivable também é contra o jogador.
- Reembolso parcial continua fora do escopo até decisão própria.

### 6.2 Cancelamento

- Antes do cutoff: devolução integral, reversão do diferido, sem repasse.
- Depois do cutoff ou no-show: sem devolução, receita reconhecida, sem repasse.
- Cancelamento pela plataforma/quadra pública: devolução integral, reversão do
  diferido/receita, registro de incidente e auditoria.
- Substituição:
  - pública → privada: a reserva pública é revertida e a privada segue o fluxo
    normal de `venue_payable`/release;
  - privada → pública: o `venue_payable` da privada é revertido e a pública usa
    o fluxo de receita própria.
  Nunca criar repasse para a plataforma no meio da substituição.

### 6.3 Disputa

- A `FinancialDispute` é uma contestação **de fornecedor** sobre `venue_release`.
  Não se aplica à quadra pública, porque não há release.
- `open_dispute` deve recusar organização da plataforma com erro claro
  (`dispute_not_applicable`), ou encaminhar para atendimento/chargeback, não
  para o fluxo financeiro do fornecedor.
- Disputa legada de `joga-publico` não libera valor; é encerrada com motivo
  `platform_own_service` e auditoria.
- O painel do fornecedor não mostra “contestar repasse” para quadra pública.

### 6.4 Conciliação

- `venue_releases` e o extrato do fornecedor excluem a organização da
  plataforma.
- A conciliação da quadra pública compara:
  - reservas públicas confirmadas;
  - saldo de `public_venue_deferred_revenue`;
  - receita reconhecida em `public_venue_revenue`;
  - reembolsos e chargebacks do período.
- O relatório de comissão não soma `fee_cents` de quadra pública.
- O reconciliador deve falhar se encontrar `venue_release` para `is_platform` ou
  `venue_payable:joga-publico`.
- O extrato do fornecedor de `joga-publico`, se consultado, devolve lista vazia
  com explicação “quadra operada pela plataforma”; não devolve repasse fictício.

---

## 7. O que muda em `payout_ready`, painel financeiro e ambiente/PSP

### 7.1 `payout_ready`

**[D]** `payout_ready` volta a significar “existe destino verificado de repasse
de terceiro” e, portanto, devolve **`False`** para `is_platform`.

Para não bloquear a reserva, entra um predicado separado:

```python
def booking_ready(organization):
    return organization.status == "active" and (
        organization.is_platform or payout_ready(organization)
    )
```

- Criação de reserva e seleção de candidatos usam `booking_ready`.
- Liberação, recebíveis, extrato e contestação usam `payout_ready`.
- `OrganizationView.payout_ready` da plataforma passa a ser `False`.
- Expor `is_platform` (ou `payout_applicable=false`) na visão administrativa para
  o painel esconder o fluxo de repasse.
- Nenhum caminho pode usar `is_platform` para autorizar `create_payout`.

### 7.2 Painel financeiro

- Para `joga-publico`, a aba “Financeiro” de fornecedor não mostra repasses,
  recebíveis, contestação, comprovante ou comissão. Mostra, se necessário, uma
  visão interna de **receita de quadra pública**: confirmações, diferido,
  reconhecido, reembolsos, chargebacks e período.
- A visão interna é de administração da plataforma, não de operador de
  organização. Operador de organização não vê receita da plataforma.
- O detalhe da reserva pública não exibe `release_status`,
  `receipt_reference` nem `dispute_deadline`; exibe o preço congelado, o
  diferido/reconhecido e o documento fiscal do JOGA.
- O relatório de comissão continua separando `venue_price_cents` de
  `joga_fee_cents` apenas para quadras privadas. Para a pública, o rótulo é
  “Receita de quadra pública”, sem “taxa de intermediação”.
- O recibo do app para quadra pública mostra uma linha de serviço próprio
  (“Uso da quadra — JOGA”) e não promete repasse a estabelecimento.

### 7.3 Ambiente e PSP

- `joga-publico` continua sem chave Pix e sem CNPJ de repasse. **Não** criar
  chave/CNPJ fictício para satisfazer `payout_ready`.
- O CNPJ da empresa operadora é identidade fiscal da plataforma, não chave de
  repasse da organização. Ele é necessário para NFS-e e dinheiro real, e
  pertence à 19A/14B.
- `money_mode=simulated` continua o padrão. A receita pública é simulada; nada
  aqui autoriza `money_mode=real`.
- Nenhuma chamada `create_payout` para a quadra pública. O valor permanece na
  conta da plataforma no PSP, como receita própria; não há split nem recebedor
  de marketplace.
- Se o PSP exigir um “recebedor” para a quadra pública, isso é sinal de que o
  desenho está errado: não há terceiro a receber.
- Não criar flag que reative o repasse para a plataforma. A proteção é o ramo
  por `is_platform` mais a checagem de conciliação.

---

## 8. Testes que a 14B precisa implementar

### 8.1 Elegibilidade e autorização

- `payout_ready(platform_org) is False`.
- `booking_ready(platform_org) is True` com organização ativa.
- Organização privada sem Pix/CNPJ continua bloqueada para reserva paga.
- `booking_ready` não aceita organização inativa.
- Nenhum endpoint permite `create_payout` para `is_platform`.
- `open_dispute` para reserva pública é recusado com `dispute_not_applicable`
  (ou rota de atendimento documentada).

### 8.2 Ledger de confirmação e prestação

- Confirmação de reserva pública por crédito:
  - não cria `venue_payable`;
  - credita `public_venue_deferred_revenue` pelo valor consumido;
  - não credita `fee_revenue`.
- Confirmação por Pix: mesmo comportamento, com débito em `psp_clearing`.
- Confirmação por passe: reclassifica `pass_revenue` para
  `public_venue_deferred_revenue`, sem receita nova.
- Vaga grátis/admin: mantém `promo_expense`, sem receita pública.
- Prestação em `starts_at + 2h`: debita o diferido e credita
  `public_venue_revenue`.
- Prestação repetida (replay) não duplica receita.
- Reserva privada continua com `venue_payable` + `fee_revenue`; teste de não
  regressão.
- Somatório de débitos e créditos é zero em todos os eventos.
- Nenhum saldo de jogador fica negativo.

### 8.3 Reembolso e cancelamento

- Reembolso antes da prestação reverte o diferido e devolve crédito/Pix.
- Reembolso depois da prestação estorna `public_venue_revenue` e devolve
  crédito/Pix.
- Cancelamento antes do cutoff: devolução integral e diferido zerado.
- No-show depois do cutoff: receita reconhecida, sem devolução, sem release.
- Cancelamento pela plataforma/quadra: devolução integral, receita/diferido
  revertido, auditoria.
- Substituição pública → privada e privada → pública sem `venue_payable` para a
  plataforma.
- Chargeback depois da prestação: receita permanece, receivable contra o
  jogador, sem `venue_receivable`.
- Chargeback antes da prestação: diferido revertido, receivable contra o
  jogador.

### 8.4 Release, disputa e conciliação

- `ensure_release` não cria `venue_release` para reserva pública.
- `release_due` ignora organização da plataforma.
- Release legada `PENDING` é revertida com motivo `platform_own_service` e sem
  lançamento em `bank`.
- Release legada `RELEASED` recebe compensating entry e auditoria.
- `FinancialDispute` não é aberta para reserva pública.
- Extrato do fornecedor de `joga-publico` é vazio.
- Relatório de comissão não inclui `fee_cents` de quadra pública.
- Reconciliador falha se encontrar `venue_release`/`venue_payable` da
  plataforma.
- Reconciliador fecha `deferred + revenue + refunds` com as reservas públicas.
- Migração/backfill é idempotente e não apaga histórico.

### 8.5 Painel e contrato

- Painel esconde repasses/contestação para `joga-publico`.
- Painel mostra receita própria no escopo administrativo correto.
- Detalhe da reserva pública não expõe `release_status`/`receipt_reference`.
- Recibo do app não mostra “taxa de intermediação” para quadra pública.
- `OrganizationView` da plataforma devolve `payout_ready=false` e o painel lida
  com isso sem quebrar.
- `money_mode=real` continua recusando boot sem aprovação legal, mesmo com
  reserva pública.

---

## 9. Riscos fiscais, jurídicos e operacionais

### 9.1 Riscos fiscais

- **Natureza da receita [H].** Tratar o valor cheio como receita própria muda a
  base de cálculo. Na quadra privada, a base é a comissão; na pública, é o valor
  do serviço. O contador precisa confirmar o enquadramento (ISS, Simples/Lucro
  Presumido, IBS/CBS) e o item municipal aplicável.
- **NFS-e [H].** O JOGA precisa emitir documento fiscal pelo uso da quadra
  pública. Sem CNPJ/inscrição municipal da empresa operadora, a operação com
  dinheiro real fica bloqueada. `joga-publico` não é emissor fiscal.
- **Separação de contas [D].** Misturar receita própria e comissão no mesmo
  relatório enfraquece a tese da ADR 0049 e produz base de cálculo errada. As
  contas `public_venue_revenue` e `fee_revenue` não se compensam.
- **Split payment [H].** Se o IBS/CBS segregar tributo na liquidação, a receita
  própria precisa estar documentalmente separada desde a origem. A ADR 0049
  §6.4 continua aplicável.
- **Preço [H].** A tabela 2D e o piso de margem foram calibrados para
  intermediação. Na quadra pública, o valor cheio é receita, mas também há custo
  de operação, manutenção e disponibilidade. A margem da quadra pública não foi
  calculada nesta ADR; precisa de modelo próprio.

### 9.2 Riscos jurídicos

- **Titularidade do espaço [H].** Se a quadra pública é bem público, o JOGA pode
  precisar de concessão, permissão ou autorização para explorá-la
  comercialmente. Esta ADR não decide isso e não autoriza cobrança sem base
  legal.
- **Responsabilidade [H].** Como prestador do serviço de uso do espaço, o JOGA
  pode responder por disponibilidade, conservação, segurança e danos de forma
  diferente da intermediação. Os Termos e o seguro precisam de revisão na 19A.
- **Consumidor [D].** O jogador deve saber que a quadra é operada pelo JOGA. O
  app e o recibo não podem sugerir um estabelecimento terceiro que não existe.
- **Direito de arrependimento [H].** A devolução em dinheiro nos 7 dias do CDC
  continua aplicável à compra de crédito; a quadra pública não pode criar uma
  restrição nova.
- **Chargeback [D].** O risco é da plataforma; não há fornecedor para cobrar.
  Isso precisa estar no contrato e no runbook.

### 9.3 Riscos operacionais

- **Passivo fictício residual.** A migração precisa rodar antes de qualquer
  relatório de repasse; caso contrário, o painel continua mostrando valores
  antigos.
- **Worker de release.** `release_due` não pode liberar release legada da
  plataforma; a checagem precisa ser por `is_platform`, não por nome.
- **Duplicidade de receita.** Passe e quadra pública podem reconhecer a mesma
  moeda duas vezes se a reclassificação for implementada como receita nova. O
  teste de reclassificação é obrigatório.
- **Documento fiscal.** Reserva pública sem NFS-e do JOGA não pode ser
  considerada concluída em modo real; o bloqueio de repasse por documento
  fiscal (ADR 0049 §9.4) precisa de equivalente para a receita própria.
- **Painel.** A aba de fornecedor não pode exibir “repasse pendente” para a
  plataforma; isso gera cobrança interna sem sentido.

---

## 10. Fora do escopo

- Escolher PSP, escrow ou conta vinculada.
- Definir alíquota, regime tributário ou item de ISS da quadra pública.
- Definir se a quadra pública será gratuita, subsidiada ou comercial.
- Obter concessão/permissão para explorar bem público.
- Definir preço, margem ou capacity da quadra pública.
- Implementar NFS-e operacional.
- Definir política de reembolso parcial, MED ou chargeback real.
- Alterar a ADR 0049 para quadras privadas.
- Criar CNPJ, conta ou chave Pix para `joga-publico`.
- Autorizar `money_mode=real`.

---

## 11. Critérios de revisão

- Parecer da 19A concluir que a quadra pública não pode ser tratada como serviço
  próprio.
- A quadra pública passar a ser operada por terceiro.
- O JOGA passar a pagar aluguel, concessão ou contrapartida pelo espaço.
- Entrada em vigor de regra municipal que proíba cobrança pelo uso.
- Migração para custódia C.
- Qualquer alteração que permita saque, transferência ou expiração de saldo.
- Ativação de `money_mode=real`.

---

## 12. Resumo da decisão

| Pergunta | Resposta |
|---|---|
| A quadra pública gera repasse? | **Não.** |
| O valor pago é receita de quem? | **Do JOGA, como serviço próprio.** |
| É comissão de intermediação? | **Não.** Conta e relatório separados. |
| Quando a receita é reconhecida? | **Na prestação** (`starts_at + 2h`/conclusão), com diferimento na confirmação. |
| `payout_ready` da plataforma? | **`False`.** |
| Como a reserva é liberada? | Por `booking_ready`, que aceita `is_platform`. |
| Existe `venue_release` para a plataforma? | **Não.** Legadas são revertidas/compensadas com auditoria. |
| Existe disputa de fornecedor? | **Não.** Vai para atendimento/chargeback. |
| O que muda no PSP? | Nada no fluxo de recebimento; nenhum `create_payout` para a plataforma. |
| O que falta para dinheiro real? | 14B, 19A, CNPJ/NFS-e, pareceres e autorização explícita. |
