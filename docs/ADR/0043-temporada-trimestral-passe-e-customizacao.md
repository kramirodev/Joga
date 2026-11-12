# ADR 0043 — Temporada trimestral, passe, trilha e customização

- **Status:** Aprovado como direção de produto; não implementado.
- **Data:** 2026-11-11
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0025 (MMR, rankings e cosméticos), ADR 0029 (sem fotos de pessoas), ADR 0042 (ingresso e passe), ADR 0044 (clãs no MVP).

## Contexto

A ADR 0042 definiu o ingresso, a tabela 2D e o passe como benefício de quantidade fixa com reset mensal. Faltava definir três coisas: a duração da temporada, o que o passe entrega além de ingressos e o que a customização pode e não pode monetizar.

Um mês é curto demais para uma temporada: o jogador casual não percebe progresso e a trilha vira decoração. E o passe mensal, somado a uma temporada mensal, criava dois calendários que precisavam coincidir artificialmente.

Ao mesmo tempo, era preciso resolver uma tensão: a ADR 0042 §10 dizia que customização não é monetária, mas o passe precisa de valor além de ingressos. Sem uma regra clara, o produto escorrega para pay-to-progress.

## Decisão

### 1. Temporada trimestral

1. Uma temporada tem **3 meses**; quatro por ano.
2. O reset é trimestral e coincide com o ciclo do passe. **Um único calendário.**
3. Badge de temporada é emitido no fechamento; não volta.

### 2. Passe trimestral com franquia mensal

1. **Não existe passe mensal.** Um plano, uma cadência, um reset.
2. Cobrança **única por trimestre**; a franquia de ingressos é **entregue mês a mês**.
3. Tamanhos por mês: **10, 20, 30 e 50** ingressos. No trimestre: 30, 60, 90 e 150. Preço: **R$ 3,25 por ingresso**.

| Plano | Ingressos/mês | Preço/mês | Trimestre | Margem/trimestre |
|---|---:|---:|---:|---:|
| Jogador | 10 | R$ 32,50 | R$ 97,50 | R$ 14,78 |
| Craque | 20 | R$ 65,00 | R$ 195,00 | R$ 29,56 |
| Time | 30 | R$ 97,50 | R$ 292,50 | R$ 44,34 |
| Elenco | 50 | R$ 162,50 | R$ 487,50 | R$ 73,90 |

4. A entrega mensal é deliberada e não deve ser trocada por entrega adiantada:
   - entrega adiantada recria o "passe como banco", que a ADR 0042 eliminou;
   - a franquia mensal cria **três momentos de engajamento** em vez de um;
   - reduz o passivo e o saldo carregado num produto ainda em validação.
5. A cobrança trimestral resolve por construção a arbitragem de "assinar, cancelar e ficar com o saldo": o trimestre pago entrega o trimestre.
6. **O passe não tem desconto por ingresso.** Seu preço é R$ 3,25 — acima do pacote grande (R$ 3,10). O valor percebido é compensado fora do dinheiro real: franquia mensal, ingressos grátis por nível e Temporada. Vender o passe abaixo do pacote grande derruba a margem das faixas caras e ainda destrói a âncora de preço.
7. A renovação é por Pix por ciclo no MVP. Pix Automático continua fora do MVP.
8. **O passe inclui lobby privado:** fechar a partida para o grupo sem depender de clã.

### 2.1 Ingressos grátis por nível

1. **Free:** 1 ingresso a cada 5 níveis (5, 10, 15, 20, 25, 30). Teto de **6 por temporada**.
2. **Passe:** 2 ingressos a cada 5 níveis. Teto de **12 por temporada**.
3. Expiram no fim da temporada. São franquia, não ingresso comprado, e não acumulam.
4. Não dão XP, não substituem a trilha e não podem ser convertidos em dinheiro.
5. **Custo do programa:** 3,3% da receita no free e 6,7% no passe, porque a progressão é proporcional ao volume jogado (1 nível ≈ 1 partida, 6 ingressos por partida). Por isso o passe custa R$ 3,25: com R$ 3,10 a margem não absorveria os 6,7%.
6. Depois do programa, o piso líquido de 10% da ADR 0042 continua respeitado — no topo da faixa de R$ 150, a margem cai de 14,1% para 10,1%.


### 3. Trilha e XP

1. **30 níveis por temporada**, com 150 XP por nível.
2. **O XP é idêntico para todos.** Não existe bônus de XP para assinante, nem compra de XP, nem aceleração paga. A assinatura muda o que se desbloqueia, nunca a velocidade.
3. Fontes iniciais de XP: partida 100, vitória +40, missão 40, quadra nova 50.
4. **Sem moeda secundária.** Só XP.
5. Calibração inicial: o jogador casual deve terminar a temporada entre os níveis 10 e 12; o assinante ativo deve conseguir fechar a trilha. Os números são ponto de partida e serão reajustados com dados do piloto.

### 4. Missões e streak

1. Três missões por semana, fixas: jogar 1 partida; jogar em uma quadra nova; fazer check-in até o horário de início.
2. As missões premiam exatamente os comportamentos que o produto precisa: frequência, descoberta e redução de no-show.
3. **Streak é sequência de vitórias com validade semanal.** Empate ou derrota zeram a sequência; **semana sem partida concluída também zera**. Persiste entre temporadas enquanto o jogador continua jogando. `best_wins` é recorde e nunca diminui. Streak não dá XP e não dá vantagem.
4. **Nível da temporada:** bronze (1–9), prata (10–19) e ouro (20–30) pelo nível alcançado na temporada. **Reseta na virada.** Não acumula e não depende de meses consecutivos. **É sempre visível para todos, inclusive free** — aparece no perfil e na escalação.
5. **Jogador que entra no meio da temporada começa no nível 1**, sem crédito proporcional. Não se recompensa quem não jogou. O que se faz é manter a curva barata nos primeiros níveis, para que o ingressante tardio ainda tenha progresso visível nas primeiras partidas.

### 5. Customização: três estados

Todo item cosmético existe em exatamente um destes estados:

| Estado | Regra | Exemplos |
|---|---|---|
| **Livre** | Disponível desde o cadastro | Bases do avatar, traços de identidade, 3 temas (incluindo alto contraste), 1 moldura, 1 celebração, parte dos acessórios, **escudo de clã**, badges de temporada, de marco e de fundador |
| **Ganho por XP** | Exige alcançar o nível na trilha | Itens de coleção, acessórios e efeitos de trilha, títulos de marco |
| **Perk do passe** | Liberado direto, é ajuste de aparência | 6 temas extras, paletas, cor de destaque, efeitos de perfil, molduras, animações, catálogo ampliado, **retrospectiva da temporada**, **destaque no perfil do clã** |

Regras que sustentam a tabela:

1. **Item de conquista nunca é perk direto.** O dinheiro compra acesso ao catálogo e à trilha; o item só sai jogando.
2. **Traço de identidade nunca é pago.** Tom de pele, cabelo, textura e tipo de corpo são livres para todos, sempre.
3. **Acessibilidade nunca é paga.** Tamanho de fonte, alto contraste, redução de movimento e alvos de toque ampliados ficam fora do passe.
4. **Nada cosmético altera MMR, Trust Factor, matchmaking, troféu de clã ou qualquer resultado.**

### 6. Customização geral do app

Além do avatar, o passe libera ajustes de aparência e densidade da interface:

- temas adicionais e cor de destaque;
- densidade dos cartões (compacta ou confortável);
- blocos da home (o que aparece e em que ordem);
- sons e resposta háptica;
- animações e transições.

Os ajustes de **acessibilidade** listados na seção 5 permanecem livres para todos.

### 7. Estatísticas

1. Estatística só pode falar do que a plataforma observa: partida, presença, resultado, quadra, formato, horário e cancelamento.
2. **Não há mapa de calor, posicionamento, posse, finalização ou qualquer dado de evento de jogo.** O JOGA não controla esses dados e não deve simulá-los.
3. **Essencial e livre:** MMR atual, partidas jogadas, vitórias/empates/derrotas, taxa de presença, streak e sequência de temporadas. Sem isso o jogador não confia no sistema nem entende as consequências das próprias ações.
4. **Passe:** evolução do MMR em gráfico, histórico por quadra, passaporte de quadras, horários e formatos mais jogados e retrospectiva da temporada.
5. **Exportação de dados é livre** (LGPD), independente do plano.
6. **O nível da temporada (bronze/prata/ouro) é sempre visível para todos**, inclusive free. Não é item de catálogo: deriva do nível e aparece no perfil e na escalação. Um elo que ninguém vê não é elo.

### 8. O que sai

1. **Convite de estreia** deixa de existir como benefício do passe.
2. **"Sem anúncios"** deixa de ser benefício do passe. Publicidade permanece na Fase 18, sem relação com assinatura.
3. **Bônus de XP para assinante** não existe.
4. **Badges são livres.** Badge de temporada, de marco e de fundador são conquista, nunca benefício do passe.
5. **Escudo de clã é livre.** O clã aparece no perfil de todo jogador, então o escudo é identidade, não cosmético pago.

### 9. Escudo de clã

1. Com clãs no MVP (ADR 0044), o escudo de clã é **livre**: o clã aparece no perfil de todo jogador, então o escudo é identidade, não cosmético pago.
2. Escudo é expressão visual e **não** concede vantagem competitiva, prioridade ou pontuação.
3. **Destaque no perfil do clã** (moldura, cor e posição em evidência) é o único item de clã no passe.
4. Troféu de clã continua sendo conquista, conforme a ADR 0025.

### 10. Inteligência de rede

1. É dado sobre a **rede**, não sobre pessoas: horário e dia de maior movimento, quadras mais usadas, densidade competitiva por quadra e ocupação.
2. **Faixas e rótulos, nunca números.** "Alta competitividade", não MMR médio. O MMR segue oculto (ADR 0025).
3. **Apresentação simples, sem exigir interpretação.** Cada bloco é um cartão com um título, uma frase e uma escala visual de 3 a 5 níveis. Exemplo: *"Arena X — movimento alto, terça e quinta à noite"*. Sem eixo, sem legenda, sem tabela.
4. **Atualização diária.** Nunca tempo real.
5. **Não é filtro de matchmaking.** O painel informa onde e quando jogar; não restringe a busca nem permite selecionar partidas por nível. A linha é de informação, não de controle.
6. **Free:** quadras mais usadas e os próprios horários. **Passe:** mapa de calor da rede, densidade competitiva por quadra, ocupação e tendência.
7. Mostrar também os **horários com mais vaga**, para equilibrar o efeito de atração do mapa de pico.
8. Não exibir taxa de cancelamento por quadra, MMR absoluto de ninguém nem dado de adversário antes da partida.
9. O mesmo painel, visto pelo estabelecimento, é insumo do painel de gestão: ocupação, horário morto e perfil do público.

## Consequências

- Um único calendário: temporada, passe e reset coincidem no trimestre.
- O passe passa a ser vendido como **acesso à temporada**, não como ingresso com desconto. **Não existe desconto por ingresso:** o passe custa R$ 3,25 e o pacote grande R$ 3,10.
- A trilha tem 30 níveis, não 10; o passe não altera a velocidade de progressão.
- A customização deixa de ser integralmente não monetária. A ADR 0042 §10 é emendada pela seção 5 desta ADR: configuração é perk; conquista é XP.
- O catálogo cosmético precisa de versionamento por temporada, com itens que não retornam.

## Pendências

1. Balancear XP e níveis com dados reais de frequência.
2. Definir o catálogo inicial de cada estado (livre, XP, passe) e a arte necessária.
3. Definir preço final do trimestre e se haverá pagamento em 3 parcelas.
4. Definir o que acontece com o ingresso da franquia mensal não usado (não acumula; confirmar regra de devolução).
5. Definir a comunicação do reset trimestral.
6. Confirmar a emenda à ADR 0042 §10 na próxima revisão do documento de produto.
