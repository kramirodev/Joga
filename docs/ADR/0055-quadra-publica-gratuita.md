# ADR 0055 — Quadra pública gratuita

- **Status:** Aprovado em 2026-11-20. Decisão de produto fechada; **design a
  implementar** no backend, no painel e no app. Substitui a decisão A da ADR
  0052 (receita própria da quadra pública).
- **Data:** 2026-11-20
- **Decisores:** responsável pelo produto e equipe técnica.
- **Numeração:** esta ADR ocupa o número **0055**. A numeração foi conferida em
  `docs/ADR/`: 0052 = payout da quadra pública, 0053 = modo demo sem PSP, 0054 =
  cache e rate limit do catálogo público; **0055 estava livre**.
- **Relaciona:** ADR 0052 (payout da quadra pública, **superada por esta ADR**),
  ADR 0049 (modelo tributário e ledger), ADR 0042 (ingresso e intermediação),
  ADR 0040 (repasse em `starts_at + 2h`), ADR 0039 (cancelamento, substituição e
  ausência), ADR 0037 (reembolsos e conciliação), ADR 0021 (precificação),
  `docs/CONTRATO_RESERVAS_APP.md` §0 e §20,
  `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §8.3 e `PLANS.md`.
- **Substitui, no que conflitar:** a decisão A da ADR 0052 e todo o desenho de
  receita de quadra pública (`public_venue_deferred_revenue`,
  `public_venue_revenue`, reconhecimento em `starts_at + 2h`). Permanecem
  válidos, da ADR 0052, a recusa de repasse para a organização da plataforma, o
  `payout_ready = False` para `is_platform` e a proibição de `venue_release`
  para `joga-publico`.

---

## 1. Contexto

### 1.1 O que existe hoje

A organização seed `joga-publico` (`organizations.is_platform = true`) tem
quadras marcadas com `organization_venues.is_public = true`. Essas quadras são
reserváveis e precificadas como qualquer quadra privada: o espaço tem
`venue_spaces.price_cents`, a reserva congela `venue_price_cents`, `fee_cents` e
`total_cents`, e o app mostra valor do espaço, taxa e contagem de tickets.
**[F]**

O contrato de reservas ainda afirma, na seção 20, que “a quadra pública é
reservável nesta etapa, com preço em faixa; não há quadra gratuita”. **[F]**

### 1.2 O desenho financeiro que seria herdado

A ADR 0052 aprovou, para a quadra pública, um serviço próprio do JOGA com
receita da plataforma: o valor pago seria diferido em
`public_venue_deferred_revenue`, reconhecido em `public_venue_revenue` no marco
`starts_at + 2h` e nunca repassado a `joga-publico`. Não haveria
`venue_payable`, `venue_release` nem `create_payout` para a plataforma. **[D]**

Esse desenho **não chegou a ser implementado**; o que existe no código é a
cobrança comum por faixa, com o mesmo caminho de ledger de uma quadra privada,
salvo o portão de repasse. **[F]**

### 1.3 O fato que decide

O dono do produto decidiu que **não se cobra por bem público**. A quadra pública
é gratuita, sempre, em qualquer modalidade, horário ou formato. A decisão é de
produto e não depende do parecer da 19A; a 19A deixa de precisar autorizar
cobrança pelo uso do espaço, porque não haverá cobrança. **[D]**

A ADR 0052 já previa esse caminho na alternativa C2 (“quadra pública gratuita ou
somente demonstração”), condicionado ao parecer jurídico. A condição muda: a
gratuidade passa a ser a decisão principal, e a cobrança fica rejeitada. **[D]**

---

## 2. Decisão

### 2.1 Regra

**[D]** A quadra pública é **gratuita**:

- não tem valor de espaço;
- não tem taxa de intermediação;
- não gera receita de quadra pública;
- não gera `venue_payable`, `venue_release`, repasse ou receivable de quadra;
- não consome ticket nem passe;
- não abre etapa de pagamento.

“Gratuita” é propriedade da quadra pública, não uma promoção temporária nem um
desconto de 100%. Não existe preço “zerado por enquanto” que possa ser reativado
por configuração: reativar cobrança exige nova ADR. **[D]**

### 2.2 Definição operacional

Continua valendo a definição da ADR 0052 §2.3: só é quadra pública a que satisfaz
**as duas** condições:

1. `organization.is_platform = true`; e
2. `organization_venue.is_public = true`, com operação efetivamente feita pelo
   JOGA.

Se a quadra for operada por terceiro (prefeitura, associação, concessionário ou
parceiro), ela não é pública para este efeito: deve ser modelada como quadra
privada, com preço, taxa, `payout_ready` e repasse. A flag `is_public` não
autoriza tratar um fornecedor existente como gratuito. **[D]**

### 2.3 O que não muda

- A intermediação de quadras privadas continua na ADR 0049: valor do espaço como
  passivo, comissão como receita, repasse em `starts_at + 2h`.
- O jogador continua comprando crédito, consumindo tickets e recebendo devolução
  em crédito nas quadras privadas.
- `money_mode=real` continua bloqueado até 14B, 19A e pareceres.
- A quadra pública continua reservável, com disponibilidade, agenda, bloqueios e
  regras de presença iguais às demais.

---

## 3. Consequências no ledger

### 3.1 Contas que deixam de ser usadas

| Conta | Situação após esta ADR |
|---|---|
| `public_venue_deferred_revenue` | **Não é criada nem usada.** Não há valor a diferir. |
| `public_venue_revenue` | **Não é criada nem usada.** Não há receita de quadra pública. |
| `venue_payable:<public_venue>` | **Nunca** para quadra pública. |
| `venue_release` / `bank` | **Nunca** para quadra pública. |
| `fee_revenue` | Continua exclusivo da comissão de quadra **privada**. |
| `pass_revenue` | Não é reclassificado para quadra pública. |
| `promo_expense` | Não é usado para vaga pública gratuita; o custo operacional da quadra é despesa da plataforma, fora do ledger por reserva. |

**[D]** A reserva pública gratuita **não gera lançamento financeiro em nenhum
evento** — criação, confirmação, conclusão, cancelamento ou ausência. O que
existe é o evento de domínio da reserva e o registro de auditoria append-only
(ator, origem, motivo quando houver, data). Auditoria não é lançamento
contábil. **[D]**

### 3.2 Composição de preço da reserva

A reserva pública deve nascer com:

| Campo | Valor |
|---|---|
| `venue_price_cents` | `0` |
| `fee_cents` | `0` |
| `fee_percent_applied` | `0` |
| `total_cents` | `0` |
| `tickets_per_seat` | `0` |
| `band_code` | `null` |
| `pricing_version` | identificador próprio da gratuidade, a definir na implementação |
| `settled_with` | valor próprio de gratuidade, a definir na implementação |

**[D]** A reserva pública não é “faixa com preço zero”: ela não pertence a faixa
nenhuma. O `band_code` nulo evita que relatórios de faixa, comissão ou tabela 2D
somem uma reserva que nunca teve preço. **[D]**

Os campos continuam existindo para compatibilidade do contrato e para que
nenhum consumidor precise tratar `null` onde hoje espera inteiro; o valor zero é
a representação da gratuidade. **[D]**

### 3.3 Invariantes

- Nenhuma conta de jogador é debitada ou creditada por reserva pública.
- Nenhum lançamento é criado, e todo lançamento existente continua fechando em
  zero.
- Não existe `venue_payable`, `venue_release` ou `venue_receivable` com owner
  `joga-publico`.
- `public_venue_deferred_revenue` e `public_venue_revenue`, se já existirem em
  algum ambiente, devem ter saldo zerado por migração; não podem receber
  lançamento novo.
- Replay de criação, confirmação, conclusão ou cancelamento não cria lançamento
  nem duplica evento; a idempotência continua por reserva e por evento.
- O reconciliador deve falhar se encontrar lançamento financeiro de quadra
  pública.

### 3.4 Reembolso e cancelamento

- **Antes do início:** não há valor a devolver. O cancelamento libera a vaga e
  registra evento e auditoria. Nenhum estorno é lançado.
- **Cancelamento pela plataforma ou pela quadra:** mesma regra; não há
  reembolso porque não houve pagamento. Registrar incidente e auditoria.
- **Substituição:** o substituto também não paga. A vaga gratuita não vira vaga
  paga no meio do fluxo.
- **Reserva histórica paga:** se existir reserva de quadra pública criada antes
  da entrada em vigor desta ADR, ela preserva o preço congelado e segue a
  política de cancelamento da ADR 0039. Não se reescreve o passado nem se
  “converte” a reserva em gratuita. **[D]**
- **Reembolso parcial** continua fora do escopo.

### 3.5 No-show

- Não há devolução, porque não há pagamento.
- Não há receita a reconhecer, porque não há receita.
- A vaga não é reembolsada nem convertida em crédito; eventual liberação para
  outro jogador depende da janela de tolerância definida na implementação.
- A consequência de confiabilidade (Trust Factor, ADR 0041) é **proposta**, não
  decisão desta ADR: um no-show em vaga gratuita pode gerar evento de
  confiabilidade e limite de reservas gratuitas ativas. A implementação fica
  pendente de decisão própria. **[D]**

### 3.6 Concorrência de vaga

A gratuidade aumenta a disputa pela mesma vaga. A reserva gratuita **não pode**
relaxar o controle de concorrência:

- a escolha de horário continua transacional, com bloqueio no PostgreSQL e
  constraint de exclusão por espaço e intervalo;
- duas confirmações simultâneas para o mesmo horário não podem ambas vencer;
- a gratuidade não cria uma janela longa de “reserva sem compromisso” que
  imobilize a vaga: a implementação deve encurtar ou eliminar a etapa de
  pagamento (T2) para a reserva pública gratuita;
- a reserva gratuita continua sujeita a rate limit e a limite de reservas ativas
  por jogador, como mitigação de abuso (proposta na §7).

**[D]** A implementação deve tratar a reserva gratuita como operação de domínio
normal, com as mesmas constraints da reserva paga, e não como um caminho
“administrativo” que dispensa validação.

---

## 4. Consequências no contrato e nas interfaces

### 4.1 Contrato de reservas

- `GET /discovery/bookable-venues` e o detalhe da quadra passam a devolver
  `min_price_cents: 0` para quadra pública e um campo aditivo de gratuidade
  (por exemplo `is_free: true`), **a implementar**.
- `venue_spaces.price_cents` e `venue_availability.price_cents` de quadra
  pública devem ser `0`. Publicar quadra pública com preço maior que zero deve
  ser recusado, **a implementar**, com erro estável próprio.
- A ativação/publicação de quadra pública não exige faixa de preço; a exigência
  de `pricing_not_configured` vale para quadra privada.
- A criação de reserva em quadra pública aceita ausência de faixa e não abre
  cobrança. Não há `insufficient_tickets` para vaga pública.
- A reserva gratuita não exige chave Pix, CNPJ de repasse nem `payout_ready`;
  a organização da plataforma continua inelegível a repasse e continua sujeita
  à checagem de organização ativa já definida na ADR 0052.
- O recibo da reserva pública não mostra valor, taxa, faixa, contagem de tickets
  nem promessa de repasse. Mostra “Grátis” e a identificação de que a quadra é
  operada pelo JOGA.
- A NFS-e de valor zero e o tratamento fiscal da gratuidade ficam pendentes de
  validação contábil; não são afirmação desta ADR. **[H]**

### 4.2 Painel

- A quadra pública aparece com rótulo **“Gratuita”**, sem faixa, sem preço e sem
  taxa.
- A aba financeira de `joga-publico` não mostra repasse, recebível, contestação,
  receita de quadra, diferido ou reconhecimento. Se necessário, mostra apenas
  contagem de reservas e ocupação.
- A visão administrativa não oferece edição de preço para espaço público; a
  tentativa deve ser recusada e auditada.
- Relatórios de comissão e de faixa ignoram reservas públicas; relatórios de
  ocupação as incluem.
- O extrato de fornecedor de `joga-publico` continua vazio, agora por dois
  motivos: não há repasse e não há receita.

### 4.3 App

- O app exibe **“Grátis”** na vitrine, no detalhe, no resumo e no recibo.
- Não há tela de pagamento, escolha de tickets ou cobrança Pix para vaga
  pública.
- O fluxo de confirmação não pede compra de ingresso e não bloqueia por saldo.
- O detalhe deixa claro que a quadra é pública e operada pelo JOGA, para não
  sugerir estabelecimento terceiro.
- O app não deve inferir gratuidade apenas por `min_price_cents == 0`; deve usar
  o campo de gratuidade ou `is_public` mais a regra do servidor, para não tratar
  erro de preço como cortesia.

---

## 5. Consequências no passe e no ticket

- Vaga pública gratuita **não consome ticket**, não consome franquia de passe e
  não gera `pass_revenue` nem reclassificação.
- O passe continua valendo para quadras privadas, conforme ADR 0043/0049.
- Se o jogador tiver passe ativo, a reserva pública não “gasta” a franquia
  mensal nem reduz o saldo exibido.
- A compra de tickets continua desligada por flag nesta fase (ADR 0053); a
  gratuidade da quadra pública reduz a dependência desse fluxo, mas não o
  reativa.
- O limite de reservas gratuitas ativas por jogador, se adotado, é regra de
  abuso e não de consumo de passe; não pode ser implementado como “cobrança
  disfarçada”.

---

## 6. Alternativas consideradas

### 6.1 Cobrar pelo uso (decisão A da ADR 0052)

**Rejeitada pelo dono.** Cobrar por bem público levanta questão de base legal,
concessão ou autorização, e o produto não quer depender disso para operar. Mesmo
com receita própria separada da comissão, o desenho continua vulnerável a
questionamento sobre a titularidade do espaço e sobre a natureza do serviço.
**[D]**

### 6.2 Modelo híbrido (grátis em horário ocioso, pago no horário de pico)

**Descartada.** Um bem público gratuito em um horário e pago em outro é difícil
de explicar ao jogador e de defender juridicamente. Também cria incentivo para
marcar todo horário como “pico” e reabre a discussão de preço que esta ADR
encerra. **[D]**

### 6.3 Gratuita somente no modo demonstração

**Descartada.** A gratuidade não é um recurso de demo; é a regra do produto. Se
fosse só demonstração, o ambiente real herdaria a cobrança e a ADR 0052 voltaria
a valer por omissão, exatamente o que se quer evitar. **[D]**

### 6.4 Reserva pública paga com receita revertida em manutenção

**Descartada.** Reverter valor para manutenção não muda a natureza da cobrança:
continua havendo preço pelo uso do bem público, com a mesma necessidade de base
legal. **[D]**

---

## 7. Riscos e mitigações propostas

| Risco | Efeito | Mitigação proposta (não decidida nesta ADR) |
|---|---|---|
| Custo operacional sem receita | Manutenção, limpeza, iluminação e conservação sem contrapartida direta | Orçamento próprio da plataforma; medição de ocupação por quadra; revisão de portfólio |
| Uso abusivo e no-show | Vaga gratuita reservada e não usada, prejudicando quem queria jogar | Evento de confiabilidade, limite de reservas gratuitas ativas e cutoff de cancelamento; decidir em ADR própria |
| Robôs e reservas em massa | Esgotamento da agenda por poucos jogadores | Rate limit por conta e por região, verificação de telefone já existente, limite por janela |
| Concentração em horário de pico | Disputa e insatisfação | Fila de espera e sugestão de horário alternativo; sem cobrança dinâmica |
| Falta de receita distorce relatório | Confundir quadra pública com quadra privada | Separação de relatórios; `band_code` nulo; reconciliador que recusa lançamento financeiro público |
| Percepção de “serviço de segunda classe” | Jogador achar que grátis significa pior | Comunicação de que a quadra é operada pelo JOGA; mesma regra de presença e cancelamento |

**[D]** Nenhuma mitigação acima está implementada por esta ADR. Elas entram como
proposta para a fase de implementação e para decisão posterior.

---

## 8. Migração e dados existentes

Plano **a implementar**; nada abaixo foi executado.

1. **Espaços e janelas públicas:** passar `venue_spaces.price_cents` e
   `venue_availability.price_cents` para `0`, com auditoria e motivo. Não apagar
   espaços, janelas nem histórico. **[D]**
2. **Reservas públicas já criadas:** preservar preço congelado; não recalcular,
   não reembolsar em massa e não reescrever ledger. Elas contam como histórico.
3. **Contas `public_venue_deferred_revenue` / `public_venue_revenue`:** se
   existirem com saldo, zerar por lançamento compensatório, com ator de sistema,
   motivo e referência; nunca por deleção de histórico. **[D]**
4. **`venue_release` de `joga-publico`:** se houver, reverter `PENDING` e
   compensar `RELEASED` conforme ADR 0052 §5.4, mantendo a auditoria.
5. **Idempotência:** repetir a migração não duplica compensação nem altera
   reserva já migrada.

---

## 9. Fora do escopo

- Definir limite, penalidade ou bloqueio por no-show.
- Definir NFS-e, ISS ou tratamento fiscal de serviço gratuito.
- Definir política de fila, sorteio ou prioridade de vaga gratuita.
- Definir se a quadra pública terá manutenção terceirizada ou contrapartida.
- Alterar o fluxo de quadras privadas.
- Reativar compra de tickets, passe ou `money_mode=real`.
- Implementar endpoints, telas, painel ou migração.

---

## 10. Critérios de revisão

- Decisão de cobrar pelo uso da quadra pública, com base legal e ADR própria.
- A quadra pública passar a ser operada por terceiro.
- O JOGA passar a pagar aluguel, concessão ou contrapartida pelo espaço.
- Necessidade de conter abuso que os limites propostos não resolvam.
- Mudança na natureza do bem público ou na legislação aplicável.
- Entrada em operação com dinheiro real.
- Qualquer proposta de “preço simbólico” ou taxa de manutenção: reabre esta ADR.

---

## 11. Resumo da decisão

| Pergunta | Resposta |
|---|---|
| A quadra pública tem preço? | **Não. É gratuita.** |
| Gera receita? | **Não.** |
| Gera `venue_payable`/`venue_release`? | **Não.** |
| Gera lançamento no ledger? | **Não.** Só evento de domínio e auditoria. |
| Consome ticket ou passe? | **Não.** |
| Reembolso? | **Não se aplica**; não há valor pago. |
| No-show? | **Sem efeito financeiro**; penalidade é proposta futura. |
| E a ADR 0052? | **Superada** quanto à receita própria; permanece o “sem repasse”. |
| O que falta implementar? | Backend (preço zero, ledger sem lançamento, migração), painel (“Gratuita”, sem financeiro) e app (“Grátis”, sem pagamento). |
