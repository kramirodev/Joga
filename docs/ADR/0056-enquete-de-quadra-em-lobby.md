# ADR 0056 — Enquete de escolha de quadra em lobby

- **Status:** Aprovado em 2026-11-20 como decisão de produto. **Design a
  implementar**; nenhuma parte desta ADR está implementada.
- **Data:** 2026-11-20
- **Decisores:** responsável pelo produto e equipe técnica.
- **Numeração:** esta ADR ocupa o número **0056**. A numeração foi conferida em
  `docs/ADR/`: 0052 = payout da quadra pública, 0053 = modo demo sem PSP, 0054 =
  cache e rate limit do catálogo público, 0055 = quadra pública gratuita; **0056
  estava livre**.
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §8.1–§8.3, ADR
  0049 (crédito, ticket e preço), ADR 0043 (passe e temporada), ADR 0042
  (ingresso e intermediação), ADR 0055 (quadra pública gratuita), ADR 0039
  (cancelamento e substituição) e `PLANS.md`.
- **Substitui, no que conflitar:** a restrição da seção 8.3 do documento
  conceitual de que a votação existe apenas em lobbies abertos originados pelo
  matchmaking.

---

## 1. Contexto

### 1.1 O que a documentação diz hoje

A seção 8.3 do documento conceitual afirma que “a votação de troca de quadra
será uma funcionalidade dos lobbies abertos originados pelo matchmaking” e que
“não existirá votação de troca de arena em lobbies fechados ou em lobbies
criados manualmente”. O restante da seção descreve uma votação binária sobre uma
proposta de troca de quadra, com quórum de 50% dos elegíveis e mais de 50% dos
votos válidos favoráveis. **[F]**

### 1.2 O problema

O lobby manual é o principal caminho para um grupo fechado organizar uma partida.
Hoje, sem votação, a escolha da quadra fica com o dono do lobby ou com quem
criou o grupo. Isso concentra uma decisão que afeta o bolso de todos os
participantes — porque a quadra privada é paga com tickets — e não tem
contrapeso quando o dono escolhe uma categoria que os demais não conseguem
pagar.

Além disso, a votação por quadra específica (como está descrita hoje) exige que
alguém já tenha escolhido uma quadra antes de votar. Isso não resolve o problema
real: o grupo precisa decidir primeiro **quanto quer gastar** e **quem escolhe a
quadra**, e só depois a quadra concreta. **[D]**

### 1.3 A decisão

O dono do produto decidiu estender a votação ao lobby manual, com a **categoria
de quadra** como unidade, com janela curta controlada pelo servidor e com uma
segunda decisão sobre **quem escolhe a quadra**. A gratuidade da quadra pública
(ADR 0055) entra como categoria de custo zero. **[D]**

---

## 2. Decisão

### 2.1 Onde a enquete existe

**[D]** A enquete existe em:

- lobby originado pelo matchmaking; e
- **lobby manual**, inclusive fechado ou por convite, com pelo menos dois
  participantes ativos.

A enquete não é aberta automaticamente em todo lobby. Ela é uma ação disponível
aos participantes, inclusive quando já existe reserva confirmada; nesse caso, a
aprovação não cancela a reserva automaticamente (§2.8). Uma vez aberta, a
decisão deixa de ser unilateral do dono do lobby.

> **Divergência registrada:** a seção 8.3 atual restringe a votação a lobbies
> abertos originados pelo matchmaking e exclui lobbies manuais e fechados. Esta
> ADR revoga essa exclusão para o lobby manual. O motivo é que o problema — dono
> escolhendo categoria que os outros não podem pagar — existe justamente em
> grupos fechados. Lobbies por convite continuam sem participação de estranhos,
> mas com a mesma enquete entre os membros.

### 2.2 Unidade da votação: categoria de quadra

**[D]** A votação é sobre **categoria**, não sobre quadra específica. Categoria é
a faixa de preço já existente na tabela 2D (`band_code`), resolvida para o
formato do lobby. A cédula mostra, para cada categoria:

- o nome/rótulo da categoria;
- o preço por jogador e a quantidade de tickets por vaga (`tickets_per_seat`);
- a quadra pública como **“Pública — grátis”**, com custo zero.

A cédula não promete quadra disponível: a disponibilidade é verificada depois do
resultado. A quadra concreta só é escolhida na etapa seguinte (§2.5).

### 2.3 Quem pode votar

**[D]** O jogador só pode votar em categoria que **consegue pagar**. A
verificação é do servidor, comparando o saldo de tickets do jogador com o custo
por vaga da categoria para o formato do lobby.

- O servidor calcula a elegibilidade; o cliente nunca envia “posso pagar” nem
  “meu saldo”.
- Categorias acima do saldo aparecem desabilitadas, com motivo (“faltam N
  ingressos”). O voto nelas é recusado.
- A quadra pública é elegível para todos, porque custa zero.
- Os votos declarados são visíveis aos demais participantes, como na seção 8.3.
  O saldo, a capacidade de pagamento e o motivo individual de inelegibilidade não
  são expostos; o que se mostra é apenas o voto declarado.

**Nota de compatibilidade com a ADR 0049:** a substância de valor é o crédito em
reais e o ticket é a unidade de exibição/consumo. O servidor deve calcular a
elegibilidade sobre a mesma fonte autoritativa que produz o saldo exibido como
tickets, e não sobre um número enviado pelo app. A ADR 0049 continua sendo a
referência; esta ADR só define a regra de produto da enquete. **[D]**

### 2.4 Janela de votação

**[D]** A janela é de **10 minutos**, controlada pelo servidor:

- começa quando a enquete é aberta;
- termina no horário do servidor, mesmo que o app esteja offline ou o relógio do
  aparelho esteja errado;
- não pode ser estendida pelo dono do lobby nem por votação;
- voto depois do encerramento é recusado;
- o resultado é apurado no servidor, não no cliente;
- encerrada a janela, a enquete não reabre sozinha; abrir outra é uma nova
  rodada.

### 2.5 O que a votação decide

**[D]** A cédula tem duas decisões:

1. **Categoria:** qual faixa de preço o grupo quer.
2. **Quem escolhe:** “o sistema decide” ou “os usuários decidem”.

- **Sistema decide:** o servidor busca uma quadra concreta na categoria
  vencedora, no horário e na duração do lobby.
- **Usuários decidem:** os participantes escolhem a quadra concreta dentro da
  categoria vencedora, pagando com tickets. A escolha acontece em etapa curta
  controlada pelo servidor; a primeira confirmação válida vence, e ninguém pode
  escolher fora da categoria vencedora.

Quando a categoria vencedora é a pública gratuita, “usuários decidem” não envolve
pagamento: os participantes escolhem a quadra pública concreta sem consumir
ticket. A exigência de tickets da §2.3 vale para categoria **privada**. **[D]**

### 2.6 Quórum, maioria e empate

Mantém-se o desenho da seção 8.3: **quórum mínimo de 50% dos elegíveis** e
**mais de 50% dos votos válidos** para a opção vencedora. As particularidades:

- O quórum é calculado sobre os participantes ativos no momento da abertura e
  congelado para a rodada.
- Para a pergunta de categoria, o denominador de elegíveis é o conjunto de
  jogadores que consegue pagar **pelo menos uma** categoria (ou a pública). Quem
  não pode pagar nenhuma categoria não participa dessa pergunta; incluí-lo no
  denominador tornaria o quórum inalcançável.
- Para a pergunta “quem escolhe”, o denominador é o conjunto de participantes
  ativos, porque a decisão não depende de saldo.
- Empate na pergunta “quem escolhe” resolve para **“o sistema decide”**, que é a
  opção sem gasto adicional e sem escolha unilateral.
- Empate ou ausência de maioria estrita na pergunta de categoria **não escolhe
  categoria**: a rodada termina sem mudança e mantém a quadra/horário atual.
  Não há segunda rodada automática nesta fase.

> **Divergência registrada:** a seção 8.3 foi escrita para uma votação binária
> (“favorável/contrário”) e não define o que fazer quando há três ou mais
> categorias e nenhuma atinge maioria estrita. Esta ADR resolve o caso por
> “sem decisão”, preservando o estado atual, em vez de inventar desempate por
> pluralidade. Uma segunda rodada entre as duas mais votadas fica como evolução
> possível, não implementada.

### 2.7 Falta de quadra na categoria/horário

**[D]** Se o sistema não encontrar quadra na categoria e no horário vencedores:

- não falha silenciosamente nem escolhe outra categoria;
- **sugere o horário livre mais próximo** na mesma categoria, com a diferença
  de horário explícita;
- a sugestão precisa de confirmação dos participantes antes de virar reserva;
- se não houver horário livre dentro do horizonte máximo definido na
  implementação, a rodada termina sem reserva, com motivo estável, e a
  quadra/horário atual permanece.

A sugestão não é reserva automática e não pode cobrar valor diferente do valor
da categoria vencedora. Se o horário mais próximo for em outra categoria, a
enquete precisa ser refeita; não se troca a categoria por conta própria. **[D]**

### 2.8 Uma votação ativa por lobby

**[D]** Cada lobby tem **uma enquete ativa por vez**. Abrir outra enquanto a
primeira está aberta é recusado. Uma reserva já confirmada não é cancelada
automaticamente pela aprovação da enquete: o sistema apresenta os efeitos de
cancelamento e reembolso antes de qualquer mudança, como já diz a seção 8.3.
**[D]**

### 2.9 Transparência e notificações

- Os votos declarados são visíveis aos participantes, como na seção 8.3.
- Saldo, capacidade de pagamento e motivo individual de inelegibilidade não são
  visíveis a terceiros.
- O chat do lobby recebe mensagens automáticas de abertura, lembrete e
  resultado, conforme §8.2 do documento conceitual.
- A notificação de encerramento não exige o app aberto.

---

## 3. Alternativas consideradas

### 3.1 Somente o matchmaking decide

**Descartada.** Manteria a escolha da quadra fora do alcance de lobbies manuais,
que são o caso em que o grupo mais precisa de regra explícita. Também não resolve
a categoria: o matchmaking escolheria por disponibilidade, não por quanto o grupo
pode pagar.

### 3.2 Dono do lobby decide

**Descartada.** É o estado atual e o problema que a decisão quer corrigir. O dono
pode escolher categoria acima do saldo dos demais e transformar a partida em
constrangimento ou exclusão. A enquete não retira a função organizadora do dono;
retira apenas a decisão unilateral de custo e local.

### 3.3 Sem votação; cada jogador reserva a própria vaga

**Descartada.** Fragmenta a reserva, cria corrida por vagas e não decide a
quadra do grupo. Também não produz a informação de “quem escolhe”.

### 3.4 Votar em quadra específica, como na seção 8.3

**Descartada como unidade principal.** Exige uma quadra pré-escolhida e não
expressa a restrição de bolso. A quadra específica continua existindo, mas na
etapa de execução, depois da categoria e do modo.

---

## 4. Consequências

### 4.1 Dependência do sistema de tickets

A enquete depende de:

- tabela 2D por faixa e formato, com `tickets_per_seat` vigente;
- saldo de tickets confiável e calculado no servidor;
- registro de consumo de tickets na confirmação da reserva;
- tratamento de reserva já paga, cancelamento e reembolso (ADR 0039).

Nesta fase, **a compra de tickets está desligada por flag** (`503
ticket_purchase_disabled`, ADR 0053). Os saldos existentes continuam válidos,
mas não há reposição. Na prática, muitas categorias podem ficar inelegíveis para
parte dos jogadores, e a enquete precisa lidar com isso sem quebrar: mostrar a
categoria desabilitada, permitir a pública gratuita e encerrar sem decisão
quando não houver categoria elegível para ninguém.

### 4.2 Dependência da quadra pública gratuita

A categoria pública só pode aparecer como custo zero se a ADR 0055 estiver
implementada no backend e no app. Antes disso, a cédula não deve prometer
gratuidade. A implementação das duas frentes precisa ser coordenada.

### 4.3 Efeitos no produto

- O dono do lobby perde a decisão unilateral de categoria e de modo quando a
  enquete é aberta.
- A escolha fica mais lenta: até 10 minutos de votação mais a busca/etapa de
  escolha. Isso precisa caber na antecedência da partida e não pode consumir o
  cutoff de cancelamento.
- A reserva pode não acontecer. O produto precisa comunicar “sem quadra
  disponível” e sugerir horário, não simular sucesso.
- A transparência dos votos aumenta a responsabilidade, mas pode gerar pressão
  social; a mitigação é não expor saldo nem motivo individual.
- O painel passa a precisar de leitura de enquetes para suporte e auditoria
  (a implementar). Não há poder de operador para “decidir a enquete” no lugar dos
  jogadores.

### 4.4 Efeitos técnicos

- Novos endpoints de abrir enquete, votar, consultar estado e executar resultado,
  todos com autorização por participação no lobby (a implementar).
- Temporizador e apuração no servidor, não no app; relógio do cliente não é
  fonte de verdade.
- Uma constraint/garantia de “uma enquete ativa por lobby” no banco, não só na
  aplicação.
- Idempotência na abertura, no voto e na execução do resultado.
- Consulta de disponibilidade por categoria e horário, com sugestão de horário
  mais próximo.
- Auditoria de abertura, votos, resultado e execução.

---

## 5. O que não será implementado agora

- Endpoints, schemas e migration de enquete.
- Tela de enquete no app, chat, push e lembretes.
- Temporizador de 10 minutos e expiração automática.
- Cálculo de elegibilidade por saldo no servidor.
- Categoria pública gratuita na cédula (depende da ADR 0055).
- Busca de quadra por categoria, etapa de escolha pelos usuários e sugestão de
  horário mais próximo.
- Segunda rodada, desempate por pluralidade ou votação ponderada.
- Penalidade por no-show ou limite de enquetes por jogador.
- Painel de auditoria e suporte da enquete.

Nada acima deve ser tratado como pronto por esta ADR.

---

## 6. Gatilhos de revisão

- Reativação da compra de tickets.
- Mudança na tabela 2D, nas faixas ou no valor de calibração.
- Implementação da quadra pública gratuita (ADR 0055) e revisão da cédula.
- Aumento de lobbies sem categoria elegível.
- Reclamação de pressão social ou exposição de voto.
- Necessidade de segunda rodada por ausência de maioria.
- Mudança na janela de 10 minutos ou no cutoff de cancelamento.
- Incidente de abuso, voto duplicado ou resultado executado duas vezes.
- Entrada em operação com dinheiro real.

---

## 7. Resumo da decisão

| Pergunta | Resposta |
|---|---|
| Onde há enquete? | Lobby do matchmaking e **lobby manual**, inclusive fechado/por convite. |
| Unidade do voto? | **Categoria de quadra** (faixa de preço), não quadra específica. |
| Quem vota? | Quem consegue pagar a categoria; verificação no servidor. |
| Quanto dura? | **10 minutos**, controlados pelo servidor, sem extensão. |
| O que decide? | Categoria **e** quem escolhe a quadra (“sistema” ou “usuários”). |
| Sem quadra no horário? | Sugere o horário livre mais próximo, com confirmação. |
| Quadra pública? | **Grátis**; não consome ticket. |
| Quórum/maioria? | 50% dos elegíveis + mais de 50% dos votos válidos, com as ressalvas da §2.6. |
| Quantas por lobby? | **Uma ativa por vez.** |
| Está implementado? | **Não.** Design a implementar. |
