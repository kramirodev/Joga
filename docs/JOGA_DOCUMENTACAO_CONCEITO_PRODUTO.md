# JOGA — Documentação de conceito e produto

**Versão:** 3.15<br>
**Status:** visão de produto atualizada — escada de preços, passe com franquia mensal e ingressos grátis por nível<br>
**Data:** 12 de novembro de 2026<br>
**Nome principal:** JOGA<br>**Nome de exibição pretendido na loja de aplicativos:** JOGA y JOGA

> Este documento consolida a visão de produto e as decisões conceituais atuais do JOGA. Ele substitui as versões anteriores e as versões conceituais incompatíveis. Não afirma que as funcionalidades descritas já estejam implementadas. A ordem normativa de desenvolvimento permanece em `PLANS.md`. Em matéria de produto, prevalece este documento; em matéria de ordem, escopo e critérios de saída de execução, prevalece `PLANS.md`.

## Controle de versão

| Versão | Data | Alteração principal |
|---|---|---|
| 2.0 | 2 de novembro de 2026 | Visão inicial com quatro pilares, incluindo marketplace de produtos |
| 3.0 | 5 de novembro de 2026 | Marketplace de produtos adiado; reservas de quadras por solicitação; Pix individual e coletivo; política de taxa com acréscimo de 80%; simulações financeiras; pendências separadas |
| 3.1 | 5 de novembro de 2026 | Coeficiente 1,8 reposicionado como hipótese inicial de segurança; piso, preço variável e teto; PSP com múltiplos pagamentos individuais por reserva como condição de viabilidade |
| 3.2 | 5 de novembro de 2026 | Fórmula `TAXA = c·V + C_k + C_c·μ·S + p_t·V`; 1,8 reinterpretado como fator de segurança de 95%; piso, preço variável e teto removidos; elegibilidade mínima; Pagar.me Flex como primeira opção; KYC, liberação após a partida e interface financeira do recebedor; comércio de produtos fora do escopo |
| 3.3 | 6 de novembro de 2026 | Fase 7: relato de resultado em 10 minutos; três resultados; regra de 50% sem tolerância separada; segunda rodada; capitão provisório por partidas finalizadas e UUID; evidência apenas textual; revisão humana por CLI; backend-only sem MMR |
| 3.4 | 7 de novembro de 2026 | Sem fotos de pessoas no aplicativo; identidade visual por avatar ilustrado gerado a partir de catálogo fechado; fotos restritas a quadras/estabelecimentos; kit da partida como requisito logístico, sem alterar o critério de capitão |
| 3.5 | 7 de novembro de 2026 | Fase 12A: quadras/espaços, modalidades, agenda, preços, bloqueios e fotos de quadra; revisão inicial pelo proprietário/administrador da organização, com revisão independente prevista para a Fase 17 |
| 3.6 | 7 de novembro de 2026 | Fase 13A: reservas com T1/T2/T3 independentes, hold transacional, substituição sem reiniciar T3 e pagamento simulado apenas em ambiente local/teste; T2 em tempo corrido nesta fase |
| 3.7 | 7 de novembro de 2026 | Protótipo/beta fechado usa Mercado Pago Checkout Transparente com Pix e custódia centralizada de teste; produção continua com Pagar.me e retenção controlada (ADR 0034) |
| 3.8 | 7 de novembro de 2026 | Fase 14A: Orders API do Mercado Pago, cobrança Pix por participante, webhook assinado, idempotência e ledger interno de teste |
| 3.9 | 7 de novembro de 2026 | Hipótese de `p_t` dinâmico pela mediana de Trust Factor registrada; modelo atual mantém `p_t = 0,2%` fixo e avaliação futura em modo sombra (ADR 0036) |
| 3.10 | 7 de novembro de 2026 | Fase 14C: reembolso integral em cancelamentos/expirações do beta, reembolso de substituto, extrato e resumo financeiro com PSP simulado |
| 3.11 | 9 de novembro de 2026 | ADR 0038: reserva da quadra é o serviço contratado; desistência após confirmação e ausência não geram reembolso; substituição com substituto pagante continua reembolsando o substituído; falha da quadra/JOGA mantém reembolso integral |
| 3.12 | 9 de novembro de 2026 | ADR 0039: fila de substitutos, cutoff de cancelamento, confirmação de presença, adaptação de formato com rodízio e desfecho financeiro pelo resultado da reserva; ADR 0038 superada |
| 3.13 | 11 de novembro de 2026 | ADR 0042: Ingresso JOGA de R$ 3,00 como unidade de acesso; tabela 2D formato × faixa ancorada em atributo visível; passe com quantidade fixa e reset mensal; natureza jurídica de intermediação com base de cálculo na comissão; margem como saída e piso de 10% líquido; matchmaking por intenção com saldo como restrição; ADR 0021 superada no fluxo de ingresso |
| 3.14 | 11 de novembro de 2026 | ADR 0043: temporada trimestral e passe trimestral com franquia mensal; XP igual para todos; trilha de 30 níveis; customização em três estados e customização geral do app; estatísticas sem dado de evento. ADR 0044: clãs e troféus passam a integrar o MVP |
| 3.15 | 12 de novembro de 2026 | Escada de preços decrescente (3/10/30/50 a R$ 3,70/3,40/3,20/3,10); passe a R$ 3,25 com franquia mensal; ingressos grátis por nível (1 no free, 2 no passe); C_c recalibrado para R$ 0,60 por jogador; tabela 2D recomputada; produção no Inter PJ |

## Como interpretar as decisões neste documento

- **Decisão aprovada:** regra que deve fazer parte do produto.
- **Parâmetro inicial:** valor de referência que poderá ser ajustado após testes.
- **Proposta:** solução recomendada, ainda sujeita a validação.
- **Pendência:** questão que precisa ser resolvida antes da implementação.
- **Expansão futura:** funcionalidade deliberadamente fora do escopo inicial.

As pendências não foram respondidas por suposição. Quando uma seção depende de uma definição ainda aberta, isso é indicado explicitamente.

---

## 1. Visão geral

O **JOGA** é uma plataforma mobile para conectar pessoas que praticam ou desejam praticar esportes coletivos, organizar partidas presenciais, desenvolver comunidades esportivas e facilitar o acesso a espaços esportivos, com ênfase em **reservas de quadras particulares**.

O projeto parte de um problema recorrente: pessoas interessadas em jogar muitas vezes não possuem um grupo fixo, não encontram participantes suficientes, têm dificuldade para conciliar horários e localização ou acabam participando de partidas pouco equilibradas. Além disso, mesmo quando o grupo existe, reservar uma quadra ainda depende de contatos dispersos, agendas manuais, mensagens em aplicativos de conversa e adiantamento do valor por uma única pessoa.

O JOGA busca centralizar essa experiência. O usuário informa seus esportes, preferências, disponibilidade e localização. A plataforma utiliza essas informações para aproximar jogadores, formar grupos compatíveis, organizar partidas e conduzir a solicitação de reserva de um espaço adequado.

A camada social continua sendo parte central do produto: lobbies, chat por contexto, lista de amigos, clãs e rankings. A camada comercial inicial é composta por **reservas de quadras originadas no JOGA, parcerias com estabelecimentos, patrocínios e publicidade contextual**, quando houver audiência suficiente.

A visão de longo prazo é que o JOGA seja um ambiente recorrente para jogar, encontrar pessoas, participar de comunidades, descobrir espaços esportivos e reservar quadras com segurança e transparência financeira.

O produto dos jogadores é exclusivamente mobile, para Android e iOS. Não está previsto site público para jogadores. O painel web responsivo é destinado aos estabelecimentos e às operações originadas no JOGA.

---

## 2. Problema identificado

A prática de esportes coletivos amadores enfrenta dificuldades que vão além da disponibilidade de quadras ou equipamentos:

- **Dificuldade para encontrar jogadores:** muitas pessoas não possuem um grupo fixo para praticar esportes.
- **Organização descentralizada:** partidas dependem de grupos de mensagens, contatos pessoais e convites informais.
- **Disponibilidade incompatível:** encontrar participantes que possam jogar no mesmo dia e horário é difícil.
- **Diferença de habilidade:** partidas podem ficar desequilibradas quando os participantes possuem níveis muito diferentes.
- **Distância geográfica:** jogadores podem precisar percorrer trajetos longos para encontrar partidas.
- **Falta de continuidade:** depois de uma partida, frequentemente não existe uma estrutura que incentive o grupo a voltar a jogar.
- **Dificuldade para encontrar espaços:** jogadores nem sempre sabem quais quadras existem, quanto custam, quais horários estão disponíveis ou como reservar.
- **Fragmentação das reservas:** estabelecimentos usam agendas manuais, planilhas, telefone e mensagens; não há um fluxo único, rastreável e previsível para solicitar, bloquear e confirmar um horário.
- **Coordenação financeira do grupo:** é comum uma pessoa adiantar o valor da quadra e depois cobrar os demais, criando atrito, esquecimentos e inadimplência.
- **Falta de compromisso formal:** nem o jogador nem o estabelecimento têm um registro claro do que foi combinado, até quando e sob quais condições.

O JOGA pretende reduzir essa fragmentação, sem transformar o produto em um sistema genérico de gestão empresarial e sem substituir a operação cotidiana do estabelecimento.

---

## 3. Proposta de solução

O JOGA combina três pilares conectados, com uma camada transversal de confiança operacional e financeira:

1. **Competitividade:** matchmaking, partidas casuais e ranqueadas, MMR e rankings individuais.
2. **Comunidade:** lobbies, chat por contexto, lista de amigos, clãs e comunidades.
3. **Infraestrutura esportiva e reservas:** descoberta de locais públicos e privados, solicitação de reserva, bloqueio temporário do espaço, pagamentos individuais e confirmação da quadra.

A camada transversal reúne identidade, autorização, auditoria, notificações, prazos controlados pelo servidor, prevenção de abuso e transparência de preços.

A plataforma deve facilitar a jornada completa: encontrar pessoas, definir quando jogar, localizar um espaço adequado, solicitar a reserva, confirmar a participação, pagar individualmente, realizar a partida e manter contato com a comunidade.

A jornada inicial não inclui comércio de produtos. Lojas esportivas poderão futuramente ser patrocinadoras ou anunciantes, mas não estarão habilitadas a vender produtos dentro do aplicativo.

---

## 4. Estrutura de produtos e experiências

O JOGA terá duas experiências principais, conectadas à mesma plataforma e ao mesmo backend.

### 4.1 Aplicativo para jogadores — JOGA y JOGA

O aplicativo Android/iOS será a experiência principal do jogador. O nome de exibição pretendido na loja de aplicativos é **JOGA y JOGA**; a marca e o nome curto do produto continuam sendo **JOGA**.

O aplicativo reunirá:

- Cadastro, autenticação e perfil do jogador.
- Modalidades esportivas, preferências e disponibilidade.
- Matchmaking casual e ranqueado.
- Lobbies abertos e fechados.
- Confirmação de participação em partidas que exigem reserva de quadra particular.
- Chat de lobby e compartilhamento de referências internas do JOGA.
- Lista de amigos e convites.
- Clãs abertos e fechados, com chat e ranking competitivo.
- Histórico, MMR e rankings individuais.
- Descoberta de quadras e espaços esportivos.
- Solicitação de reserva de quadras particulares.
- Acompanhamento do estado da solicitação, do bloqueio e dos pagamentos.
- Pagamento individual por Pix, quando as cobranças forem abertas.
- Notificações push sobre prazos, confirmações, substituições, cancelamentos e reembolsos.
- Histórico de reservas e comprovantes.

### 4.2 Painel de gestão — JOGA y GESTÃO

O JOGA terá um painel web responsivo destinado a proprietários, gerentes e funcionários autorizados de quadras, arenas e complexos esportivos admitidos na plataforma.

O gerente não precisará utilizar o aplicativo de jogadores para administrar as operações originadas no JOGA. Ele poderá acessar o painel pelo computador ou pelo navegador do celular.

O painel será voltado exclusivamente às operações originadas no JOGA. Não pretende substituir um ERP nem administrar automaticamente vendas presenciais, clientes externos, fornecedores ou toda a operação financeira do estabelecimento.

**Módulo de quadras — JOGA y QUADRA:**

- Receber solicitações de reserva.
- Visualizar modalidade, data, horário, duração, quantidade de participantes e espaço físico solicitado.
- Aceitar ou recusar solicitações.
- Confirmar o bloqueio temporário do espaço específico.
- Acompanhar o estado dos pagamentos.
- Consultar reservas confirmadas, cancelamentos e histórico de solicitações.
- Configurar horários de funcionamento, dias fechados, feriados e exceções.
- Configurar prazos operacionais e a duração máxima do bloqueio, conforme o acordo comercial.
- Consultar informações financeiras relacionadas às reservas originadas no JOGA.
- Manter histórico das ações realizadas por seus usuários autorizados.

O painel não deverá se transformar em um ERP. Sua finalidade é administrar as operações originadas no JOGA, com simplicidade operacional e rastreabilidade.

**Operação com agendas manuais:**

O JOGA deverá conseguir operar com estabelecimentos que utilizam agendas manuais, planilhas, WhatsApp ou sistemas sem API. A integração com sistemas de terceiros não será exigida para o lançamento.

Quando o estabelecimento aceitar uma solicitação, ele deverá confirmar que o horário foi efetivamente bloqueado em sua agenda operacional. Se utiliza WhatsApp, telefone, papel ou outro controle externo, o responsável deverá atualizar esse controle antes de confirmar o bloqueio no painel. A confirmação no painel representa um compromisso do estabelecimento.

Integrações externas poderão ser avaliadas futuramente para consultar disponibilidade, bloquear horários, confirmar reservas, cancelar reservas e sincronizar agendas. A estrutura deverá permitir essas integrações sem tornar o produto dependente delas.

**Administração e permissões:**

- Cadastro de proprietários, funcionários e permissões.
- Histórico das operações realizadas no JOGA.
- Relatórios básicos de reservas e faturamento da plataforma.
- Consulta de campanhas e ferramentas de publicidade, quando liberadas.

A gestão básica deverá começar gratuita ou sem mensalidade obrigatória, reduzindo a barreira de entrada dos estabelecimentos. Planos opcionais de gestão poderão ser avaliados no futuro.

### 4.3 Estrutura compartilhada

O aplicativo e o painel web utilizarão a mesma API, identidade central, banco de dados e infraestrutura, com permissões diferentes conforme o papel do usuário e o estabelecimento ao qual está vinculado.

Uma mesma pessoa poderá ser jogador, proprietário ou funcionário. Entretanto, um gerente poderá utilizar o painel sem criar perfil esportivo ou participar do matchmaking.

O acesso a dados de estabelecimentos será isolado por organização e por permissão. Um estabelecimento não poderá visualizar reservas, dados financeiros ou informações operacionais de outro.

O aplicativo nunca acessará o banco de dados diretamente. Toda operação passará por contratos HTTP/WebSocket versionados, com autorização verificada no servidor em cada recurso e operação.

Não haverá site público independente para jogadores ou para estabelecimentos. O painel é uma ferramenta autenticada de gestão, não uma vitrine pública.

### 4.4 Convenção de nomes

- **JOGA:** marca principal e nome curto do produto.
- **JOGA y JOGA:** nome de exibição pretendido do aplicativo.
- **JOGA y GESTÃO:** painel web dos estabelecimentos.
- **JOGA y QUADRA:** módulo de quadras e reservas.
- **JOGA y CLÃ:** nome possível para a área de clãs, caso a nomenclatura seja utilizada na interface.

O uso de “y” é intencional e faz parte da identidade verbal da marca. Os nomes derivados devem continuar subordinados à marca JOGA, sem criar produtos tecnicamente independentes sem necessidade.

A disponibilidade jurídica da marca, dos nomes derivados e dos títulos nas lojas de aplicativos deve ser verificada antes do lançamento comercial.

---

## 5. Público-alvo

**Público primário:**

- Pessoas que querem jogar, mas não possuem um grupo fixo.
- Jogadores que desejam conhecer novas pessoas por meio do esporte.
- Grupos pequenos que precisam completar equipes.
- Pessoas que procuram partidas de nível técnico semelhante.
- Jogadores que desejam competir sem integrar clubes formais.
- Pessoas que precisam reservar uma quadra particular e dividir o pagamento entre os participantes.
- Organizadores informais de partidas que hoje dependem de mensagens e cobranças manuais.

**Público comercial:**

- Proprietários e administradores de quadras particulares.
- Arenas e complexos esportivos.
- Gestores de estabelecimentos que utilizam agendas manuais ou sistemas sem integração.
- Estabelecimentos interessados em divulgação, parcerias e patrocínios locais.

Lojas de artigos esportivos poderão ser patrocinadoras ou anunciantes futuramente, mas não são público-alvo comercial do escopo inicial. Academias, clubes com gestão completa de matrículas, prestadores individuais e organizadores de torneios poderão ser avaliados em etapas futuras, mas não são prioridade do escopo inicial.

---

## 6. Modalidades e formatos iniciais

O lançamento deve começar com modalidades de organização relativamente simples:

- **Futebol 5x5:** 10 jogadores no total, divididos em duas equipes de cinco.
- **Vôlei:** formato inicial a ser configurado e validado antes da implementação definitiva.

Cada modalidade/formato terá uma duração padrão definida pelo produto. A duração não será livremente escolhida por cada lobby: será determinada pela configuração oficial do formato esportivo.

Os parâmetros exatos de duração, composição do vôlei, tolerâncias de atraso e regras de encerramento deverão ser registrados antes da implementação do respectivo formato.

Outras modalidades poderão ser adicionadas depois, sem assumir que suas regras sejam iguais às do futebol ou do vôlei.

A quantidade de participantes de cada formato é a base para o cálculo da contribuição individual e das cobranças Pix. Não se deve inventar uma composição definitiva para modalidades cujo formato ainda não foi aprovado.

---

## 7. Matchmaking

O matchmaking considera, conforme a modalidade:

- Esporte e formato.
- Preferência por partida casual ou ranqueada.
- MMR e incerteza do rating, quando aplicável.
- Disponibilidade e horário.
- Localização e distância aceitável.
- Quantidade de participantes necessária.
- Preferência por quadras públicas, particulares ou indiferentes.
- Tempo de espera e regras de elegibilidade.

### 7.1 Uma única fila com preferência de quadra

Não haverá filas independentes para quadras públicas e particulares. O usuário terá uma preferência no perfil, que poderá ser alterada antes de entrar na fila:

- **Somente públicas.**
- **Somente particulares.**
- **Tanto faz.**

O matchmaking aplicará a preferência como filtro de compatibilidade. Se participantes com preferências incompatíveis forem agrupados, o sistema não deve selecionar um espaço que viole a restrição de qualquer participante. Uma combinação sem interseção de preferências não deve ser formada como se fosse compatível.

A preferência poderá ser ajustada especificamente para uma entrada na fila, sem necessariamente alterar a configuração permanente do perfil.

### 7.2 Horário fixo por lobby

Toda partida/lobby representa um horário concreto. Um lobby manual exige data e horário definidos na criação.

No matchmaking, o usuário poderá informar disponibilidade ou uma janela de horários. O sistema procurará uma combinação comum e, ao formar o lobby, gravará uma data e um horário específicos. Depois de criado, o horário da partida fica definido; não é apenas uma intenção genérica de jogar algum dia.

A duração é herdada do formato esportivo configurado.

### 7.3 Localização

No matchmaking, o JOGA calcula automaticamente uma região de encontro considerando a localização e as preferências dos participantes, sem exigir que o criador escolha manualmente uma quadra antes da formação do grupo.

A localização exata de cada participante não será exposta aos demais. O sistema deverá considerar distância, privacidade e viabilidade de deslocamento.

### 7.4 Relação com a reserva

Quando o lobby exigir uma quadra particular, a formação do grupo não garante a quadra. O espaço só será considerado reservado depois que o estabelecimento aceitar a solicitação e confirmar o bloqueio temporário do espaço específico, e depois que todos os participantes concluírem os pagamentos dentro do prazo.

O fluxo completo está nas seções 10 a 14.

---

## 8. Lobbies e organização das partidas

O lobby é o espaço de organização de uma partida. Ele reúne participantes, horário, modalidade, preferências de local, chat e ações relacionadas à partida.

### 8.1 Origens e visibilidade

- **Lobby manual:** criado por um usuário, com data e horário fixos. Pode ser fechado, por convite, ou aberto para descoberta, conforme as regras de publicação definidas no produto.
- **Lobby do matchmaking:** criado pelo sistema após a formação de um grupo compatível. Não possui um dono com poder unilateral para decidir mudanças de quadra.

Origem e visibilidade são conceitos distintos: o sistema deve registrar quem/como criou o lobby e se ele é aberto ou fechado.

### 8.2 Chat do lobby

Cada lobby terá um chat próprio para os participantes autorizados. A primeira versão será focada em texto e compartilhamento de referências internas do JOGA, como partidas, quadras e convites.

Mensagens automáticas poderão informar entradas, saídas, votações, alterações de horário, solicitações de reserva, bloqueios, pagamentos e outros eventos relevantes.

Não está previsto, no escopo inicial, envio livre de vídeos, áudios, arquivos ou imagens no chat.

### 8.3 Votação de troca de quadra

A votação de troca de quadra será uma funcionalidade dos lobbies abertos originados pelo matchmaking. Não existirá votação de troca de arena em lobbies fechados ou em lobbies criados manualmente.

Nos lobbies elegíveis:

- Não haverá um dono com poder unilateral de trocar o local.
- Qualquer participante poderá sugerir uma alternativa compatível.
- Cada participante poderá votar uma vez por proposta.
- Haverá apenas uma votação ativa por lobby.
- A proposta deverá respeitar o tipo de espaço permitido no lobby.
- O sistema verificará disponibilidade, horário, duração e demais restrições antes de efetivar a mudança.

A aprovação exige quórum mínimo de 50% dos participantes elegíveis e mais de 50% dos votos válidos favoráveis. Empate, maioria contrária ou ausência de quórum rejeitam a proposta.

A votação deve preservar a transparência entre os participantes: os votos poderão ser visualizados pelos demais jogadores, incentivando responsabilidade e reduzindo decisões aleatórias.

A aprovação não substitui a confirmação da disponibilidade nem a conclusão de uma nova reserva. Uma reserva já paga não será cancelada automaticamente apenas porque uma votação foi aprovada. O sistema deverá apresentar os efeitos de cancelamento e reembolso antes de confirmar a mudança.

### 8.4 Confirmação de participação para reservas privadas

Quando a partida exigir reserva de quadra particular, após a formação do lobby os participantes deverão confirmar sua intenção de participar. O prazo inicial é de **1 hora**, contado pelo backend.

O sistema deverá:

- Enviar uma notificação inicial.
- Permitir confirmar ou recusar a participação.
- Registrar a confirmação no servidor.
- Permitir substituições dentro da janela original.
- Enviar lembretes sem excesso de notificações.
- Encerrar a etapa no prazo estabelecido.

O JOGA é pensado para ficar disponível no celular, inclusive em segundo plano. O usuário não precisa ficar olhando continuamente para a tela.

Se um participante recusar ou não confirmar dentro do prazo, o sistema poderá procurar um substituto. A substituição deverá ocorrer dentro da janela original de uma hora, sem reiniciar ou estender o prazo geral. Se não houver participantes suficientes ao final da janela, o lobby será desfeito.

**A quadra ainda não terá recebido nenhuma solicitação nesse momento.** O JOGA deve estabilizar o grupo antes de ocupar o tempo operacional do estabelecimento.

Não haverá uma segunda etapa obrigatória de confirmação de prontidão de cinco minutos. A confirmação de participação de uma hora já cumpre essa função.

A confirmação de participação é o primeiro dos três temporizadores independentes descritos na seção 11. Ela não se confunde com o prazo de resposta do estabelecimento nem com o prazo de bloqueio e pagamento.

### 8.5 Kit da partida e equipamento

Uma partida coletiva também depende de equipamento. O JOGA deverá tratar esse requisito como **condição logística da partida**, não como atributo de status, elo, Trust Factor ou capitania.

Cada formato terá um catálogo versionado de requisitos mínimos. Referência inicial:

| Formato | Requisitos |
|---|---|
| Futebol 5x5 | bola |
| Basquete 3x3 | bola |
| Vôlei de praia | rede e bola |
| Tênis | bolas (raquete é responsabilidade individual) |

Regras:

- O requisito pertence à partida, não ao jogador. Itens diferentes podem ter responsáveis diferentes.
- **Itens fixos da modalidade** — rede de vôlei, cesta de basquete, trave — são responsabilidade do **estabelecimento que declarou aceitar a modalidade**. Se o local aceita vôlei, deve fornecer a rede; a falta é falha da quadra.
- **Itens móveis** — bola, coletes, bolas de tênis — são uma marcação **opcional** do jogador ("tenho bola" / "talvez tenha") ou fornecidos pelo local. Não é compromisso obrigatório, não prova posse e não gera penalidade automática.
- A cobertura do kit é conferida antes do check-in por um responsável logístico: quem criou o lobby manual ou um participante designado pelo grupo. É um **checklist/aviso**, não um bloqueio. Esse papel não dá autoridade sobre o resultado e não altera a capitania simbólica da seção 9.1.
- O kit **não bloqueia** o lobby, o matchmaking, a confirmação, o pagamento, o check-in nem o início da partida. A interface mostra o que falta e permite combinar/assumir.
- O estado do kit é visível apenas aos participantes e ao responsável logístico, com os itens faltantes e quem assumiu cada um.
- Partidas ranqueadas devem priorizar equipamento fornecido pelo local ou pela organização. O kit não influencia a escolha do capitão.
- Não levar um item móvel marcado como "tenho" não gera penalidade automática; a marcação é informativa. A ausência de item fixo é falha do estabelecimento.
- O JOGA não verifica posse, não exige foto do equipamento e não usa “ter bola” como elegibilidade, recomendação ou ranking.
- Se o kit estiver incompleto, a interface mostra o que falta e permite que outro participante assuma o item; a partida não é cancelada automaticamente por causa de item móvel. Item fixo ausente é falha do estabelecimento e segue as regras de reserva/reembolso.
- Aluguel, venda ou caução de equipamento permanecem fora do escopo inicial (seção 15).

A decisão está registrada na ADR 0030.

---

## 9. Partidas, equipes e resultados

O JOGA terá partidas casuais e ranqueadas.

**Partidas casuais:** priorizam diversão, socialização e descoberta de jogadores. Não alteram o rating competitivo.

**Partidas ranqueadas:** utilizam o MMR específico da modalidade/formato. Resultados validados podem alterar o rating e os rankings individuais.

### 9.1 Escolha do capitão

Nas partidas formadas pelo matchmaking, cada equipe terá um capitão simbólico, escolhido automaticamente pelo sistema.

O capitão não terá autoridade administrativa sobre os demais jogadores nem poderá decidir unilateralmente o resultado da partida. Sua função principal será representar a equipe na comunicação e na confirmação inicial do resultado.

A escolha seguirá esta ordem de prioridade:

1. Maior Trust Factor esportivo.
2. Maior número de partidas válidas realizadas.
3. Maior MMR.
4. Maior idade, em caso de empate nos critérios anteriores.

O Trust Factor será o principal critério porque o capitão deve ser, prioritariamente, o jogador considerado mais confiável pelo sistema.

A posse ou disponibilidade de equipamento não faz parte deste critério. Ela é tratada como requisito logístico da partida na seção 8.5 e não altera a capitania simbólica.

**Na Fase 7, a seleção é provisória.** Como Trust Factor e MMR ainda não existem, o capitão será escolhido pelo maior número de partidas válidas concluídas (`FINALIZED`) e, em caso de empate, pelo UUID como desempate determinístico. Não será usado critério de nível. A seleção e a versão do critério ficam registradas, e capitães ou registros históricos não são alterados retroativamente. Na Fase 8, os critérios completos poderão ser aplicados a partidas futuras, incorporando Trust Factor, partidas válidas, MMR e idade quando houver dado confiável.

### 9.2 Confirmação do resultado

Ao final da partida, todos os jogadores deverão informar o resultado individualmente. A votação tem **três resultados possíveis**: vitória da equipe A, vitória da equipe B ou empate esportivo, este último apenas quando o formato permitir. Não tratar a votação como binária.

Além disso, os capitães poderão informar o resultado de suas respectivas equipes. Essa confirmação será uma informação adicional para o sistema, não uma decisão absoluta.

Os votos dos participantes serão visíveis aos demais jogadores. Essa transparência é intencional: a expectativa é reduzir votos aleatórios ou incorretos por meio da responsabilidade social entre os participantes.

O prazo padrão de votação será de **10 minutos** após o encerramento da partida, controlado pelo backend. O valor poderá ser configurado por formato no futuro, mas cada lobby não poderá alterá-lo livremente.

Jogadores que não votarem dentro do prazo serão registrados como votos anulados, e não como votos favoráveis a qualquer resultado. Votos ausentes ou anulados não entram no cálculo e não significam concordância nem discordância.

### 9.3 Divergências e validação

O sistema comparará os resultados informados pelos participantes e as confirmações dos capitães.

**Não existe uma tolerância separada de “1 ou 2 votos”.** A regra é calculada sobre os votos válidos:

- divergência **abaixo de 50%** em relação ao resultado avaliado: o resultado pode ser finalizado;
- divergência **exatamente igual a 50%**: segunda rodada de votação;
- divergência **acima de 50%**: a partida entra em disputa.

Na prática, 1 ou 2 jogadores divergentes em uma partida de 10 ficam abaixo do limite e não abrem disputa automaticamente.

O resultado com mais votos válidos é o **resultado avaliado** (maioria simples/plurality). Isso não significa maioria absoluta: um resultado pode ser o mais votado sem ultrapassar 50% dos votos. Se houver empate na primeira posição, abre-se a segunda rodada.

A votação exige **quórum mínimo de `ceil(participantes_elegíveis / 2)` votos válidos**. O conjunto de elegíveis é congelado na abertura da primeira rodada e reutilizado na segunda. Abaixo do quórum, o caso vai para revisão humana e não é finalizado automaticamente.

Votos ausentes ou anulados não entram no denominador e não são interpretados como concordância ou discordância.

A partida entra em disputa quando a divergência ultrapassa 50% dos votos válidos. A disputa será uma medida de proteção, não um mecanismo para anular partidas automaticamente. A anulação deverá ser considerada apenas como última alternativa, depois de avaliadas as evidências disponíveis.

### 9.4 Desempate de resultados e análise de confiabilidade

Quando a divergência em relação ao resultado avaliado for exatamente 50%, o JOGA solicitará uma segunda confirmação a todos os participantes.

Os jogadores poderão confirmar ou corrigir suas respostas anteriores. O histórico da primeira votação será preservado para auditoria.

A segunda rodada terá prazo próprio de **5 minutos**, controlado pelo backend, sem renovação automática.

A segunda rodada apresenta **todas as alternativas permitidas pelo formato** (`TEAM_1`, `TEAM_2` e, quando permitido, `DRAW`), independentemente da distribuição da primeira rodada. Não haverá terceira rodada.

Na segunda rodada: resultado único com divergência abaixo de 50% finaliza; exatamente 50% vai para análise interna; acima de 50% vai para disputa e revisão humana; empate na primeira posição, ausência de resultado único ou falta de quórum vão para revisão humana.

Se a segunda votação continuar sem resultado confiável, a partida entrará em uma análise interna e invisível de confiabilidade.

Nessa análise, o sistema avaliará os relatos individualmente — e não por média simples de grupo —, buscando consistência de votos, histórico competitivo, coerência em eventuais alterações de voto e detecção de padrões de comportamento coordenado ou manipulação.

Os relatos dos capitães serão considerados como sinais relevantes, em função de seu histórico de confiabilidade, mas não receberão peso automático de voto adicional nem autoridade para determinar o resultado sozinhos.

Os indicadores internos não serão exibidos aos participantes. Eles serão utilizados exclusivamente pelo sistema para auxiliar na identificação do resultado mais confiável.

Caso as evidências não permitam uma conclusão segura, a partida será encaminhada para revisão humana. A anulação deverá permanecer como último recurso.

Durante todo o processo, o MMR permanecerá sem atualização definitiva.

### 9.5 Disputas de partidas

Uma partida em disputa não poderá alterar o MMR até a resolução.

O sistema deverá reunir:

- Resultado informado por cada participante.
- Resultado informado pelos capitães.
- Histórico de alterações e confirmações.
- Denúncias relacionadas à partida.
- Histórico de confiabilidade relevante dos envolvidos.
- Justificativa textual privada apresentada na disputa.
- Outras evidências disponíveis e pertinentes.

A evidência da Fase 7 é **apenas textual**, limitada a **2.000 caracteres**, com no máximo uma justificativa por participante em cada disputa. O acesso é restrito e auditável. Não há upload de imagens, áudios, vídeos ou arquivos nesta fase. O conteúdo não é exposto publicamente no lobby.

A primeira análise poderá ser automatizada por regras de consistência e mecanismos de detecção de comportamento suspeito.

Casos inconclusivos ou com indícios relevantes de fraude poderão ser encaminhados para revisão humana.

As decisões possíveis incluem:

- Confirmar o resultado predominante.
- Solicitar informações adicionais.
- Corrigir o resultado quando houver evidência suficiente.
- Aplicar medidas de integridade quando houver fraude comprovada.
- Anular a partida somente quando não houver alternativa confiável.

Toda decisão deverá ser registrada e possuir justificativa auditável.

Enquanto não existir estrutura de staff/admin, a revisão humana poderá ser feita por script interno auditável, com operador autorizado, justificativa e timestamp. Não será criado um sistema completo de administração na Fase 7.

### 9.6 Integridade do sistema de resultados

O sistema deverá evitar que usuários manipulem resultados por meio de votos coordenados, contas falsas ou denúncias abusivas.

O MMR poderá reduzir a vantagem de combinações artificiais de resultados ao longo do tempo, mas não será considerado proteção suficiente contra fraude.

O JOGA deverá manter mecanismos independentes de detecção de padrões suspeitos, sem presumir que o balanceamento competitivo elimina sozinho o problema.

Resultados não confirmados ou em disputa não podem alterar o MMR. A plataforma deverá manter histórico auditável dos relatos originais e das decisões finais.

---

## 10. Locais, quadras e reservas

O JOGA contemplará espaços públicos e privados, com regras diferentes de descoberta e reserva.

**Espaços públicos:** quadras e espaços de acesso público. O aplicativo poderá ajudar a descobrir e combinar encontros nesses locais. A indicação de um espaço público não representa, por si só, garantia de disponibilidade ou direito de reserva. Só haverá reserva formal se existir autorização e integração operacional com o responsável pelo espaço.

**Espaços privados:** quadras particulares, arenas e complexos esportivos. O estabelecimento poderá cadastrar espaços, preços, horários e regras. O usuário poderá solicitar uma reserva pelo aplicativo; a confirmação dependerá do aceite do estabelecimento e da conclusão dos pagamentos.

A preferência de espaço público/particular acompanha a entrada na fila e o lobby. A troca de local deve respeitar a categoria permitida.

### 10.1 Descoberta de espaços

A descoberta deverá permitir:

- Consultar estabelecimentos e espaços compatíveis com a modalidade e a região.
- Visualizar informações operacionais relevantes, como endereço aproximado, horários de funcionamento, regras e faixa de preço.
- Verificar se o espaço aceita solicitações pelo JOGA.
- Identificar se o espaço é público ou particular.
- Iniciar uma solicitação de reserva para um horário compatível.

A disponibilidade exibida antes do aceite do estabelecimento é uma referência operacional, não uma garantia. A garantia nasce do bloqueio temporário confirmado pelo estabelecimento, nas condições da seção 10.4.

### 10.2 Painel de gestão das quadras

O painel deverá permitir ao responsável pelo estabelecimento:

- Receber solicitações de reserva.
- Visualizar modalidade.
- Visualizar data e horário.
- Consultar duração da partida.
- Consultar quantidade de participantes.
- Consultar o espaço físico solicitado.
- Aceitar ou recusar solicitações.
- Confirmar bloqueios temporários.
- Acompanhar o estado dos pagamentos.
- Consultar reservas confirmadas.
- Consultar cancelamentos.
- Consultar histórico de solicitações.
- Configurar horários de funcionamento.
- Configurar dias fechados.
- Cadastrar feriados e exceções.
- Configurar prazos operacionais.
- Consultar informações financeiras relacionadas às reservas do JOGA.

O gerente não precisa utilizar o aplicativo de jogadores para executar essas atividades. O painel deverá ser responsivo e acessível pelo computador ou navegador do celular.

O painel não deverá se transformar em um ERP. Sua finalidade é administrar as operações originadas no JOGA.

### 10.3 Solicitação ao estabelecimento

O sistema de reservas funciona por meio de solicitações ao estabelecimento, inspirado no modelo operacional de plataformas de solicitação de serviço. A ideia é que o usuário consiga solicitar uma quadra sem depender da integração do JOGA com o software de gestão utilizado pelo estabelecimento.

O estabelecimento receberá a solicitação pelo próprio painel do JOGA.

A solicitação deverá conter, no mínimo:

- Modalidade e formato.
- Data e horário pretendidos.
- Duração da partida.
- Quantidade de participantes.
- Espaço físico solicitado.
- Identificação da reserva e do lobby.
- Prazo de resposta do estabelecimento.
- Condições comerciais aplicáveis.

Antes de enviar a solicitação, o JOGA deverá calcular se ainda existe tempo suficiente para o estabelecimento responder, realizar o bloqueio e os jogadores pagarem antes da partida. Se não houver tempo suficiente, a solicitação não deverá ser enviada.

O aceite do estabelecimento representa um compromisso condicional de honrar a reserva, desde que todos os participantes paguem dentro do prazo. Não deverá existir uma segunda aprovação manual após os pagamentos se o estabelecimento já confirmou o bloqueio.

Em caso de recusa ou expiração da solicitação, o lobby poderá ser cancelado ou redirecionado para outra quadra compatível, se houver alternativa e tempo operacional. A regra definitiva sobre redirecionamento permanece pendente.

### 10.4 Bloqueio temporário obrigatório

Todas as quadras parceiras que receberem solicitações deverão trabalhar com um mecanismo de bloqueio temporário.

Esse bloqueio é obrigatório porque a quadra não pode aceitar uma solicitação, deixar o horário disponível em outros canais e vender o mesmo espaço para outra pessoa enquanto os participantes do JOGA realizam os pagamentos.

Quando o estabelecimento aceitar uma solicitação, deverá confirmar que o horário foi efetivamente bloqueado em sua agenda operacional. Isso vale também para estabelecimentos que utilizam agendas manuais.

Se utiliza WhatsApp, telefone, papel ou outro sistema, o responsável deverá atualizar esse controle fora do JOGA antes de confirmar o bloqueio no painel. A confirmação de bloqueio pelo painel representa um compromisso do estabelecimento.

Se todos os participantes concluírem os pagamentos dentro do prazo, a reserva será efetivada sem precisar de uma segunda autorização comercial.

A quadra não poderá aceitar, manter bloqueio e depois exigir uma nova aprovação sem motivo operacional previsto.

O bloqueio deverá ser registrado com identificação do espaço, início, fim, reserva associada, responsável pela confirmação e histórico de alterações.

### 10.5 Bloqueio de um espaço específico

O bloqueio deverá identificar a quadra ou espaço físico específico.

Uma arena pode possuir vários campos ou quadras. O sistema não poderá considerar que todo o estabelecimento está indisponível quando apenas um espaço foi reservado.

Também deverá impedir sobreposição de bloqueios para o mesmo espaço e intervalo de tempo. A verificação deverá ser feita de forma transacional no backend, com constraints e proteção contra concorrência. Não basta uma checagem visual no painel.

### 10.6 Duração e expiração do bloqueio

A referência inicial será de **60 minutos**.

Entretanto, cada estabelecimento poderá configurar a duração máxima do bloqueio conforme suas condições operacionais e o compromisso comercial acordado com o JOGA.

Não haverá renovação automática. Se o bloqueio expirar sem a conclusão dos pagamentos, será liberado.

O estabelecimento poderá continuar recebendo novas solicitações para outros horários disponíveis.

A expiração do bloqueio não apaga o histórico. O sistema deverá registrar que o bloqueio existiu, quando expirou e quais pagamentos estavam pendentes naquele momento.

### 10.7 Fluxo completo da reserva

1. O lobby é formado pelo matchmaking ou criado manualmente.
2. Quando a partida exige quadra particular, os participantes confirmam participação em até 1 hora.
3. O backend identifica uma quadra compatível e verifica se há tempo operacional suficiente.
4. A solicitação é enviada ao painel do estabelecimento.
5. O estabelecimento aceita ou recusa dentro do prazo de resposta.
6. Se aceitar, confirma o bloqueio temporário do espaço específico em sua agenda operacional e no painel do JOGA.
7. As cobranças Pix dos participantes são abertas simultaneamente, com o mesmo prazo limite.
8. Cada participante paga sua própria contribuição.
9. Se todos os pagamentos necessários forem aprovados dentro do prazo, a reserva é confirmada sem segunda aprovação manual.
10. Se alguém não pagar, o sistema poderá substituir a vaga dentro da janela original de pagamento.
11. Se não houver substituto ou tempo suficiente, o lobby será cancelado, o bloqueio liberado e os valores pagos reembolsados.
12. Se o estabelecimento cancelar ou descumprir o bloqueio depois de os participantes terem pago, o JOGA deverá cancelar a reserva e iniciar os reembolsos.
13. Todos os eventos deverão ser registrados e auditáveis.

### 10.8 Responsabilidade do estabelecimento

Ao aceitar uma solicitação, a quadra deverá:

1. Confirmar que o espaço físico está disponível.
2. Bloquear o horário na agenda operacional que utiliza.
3. Confirmar o bloqueio pelo painel do JOGA.
4. Manter o horário reservado durante a janela de bloqueio.
5. Honrar a reserva caso todos os pagamentos sejam concluídos no prazo.

Se a quadra descumprir o compromisso depois de os participantes terem pago, o JOGA deverá cancelar a reserva e iniciar os reembolsos.

O histórico do estabelecimento deverá registrar:

- Solicitações aceitas.
- Solicitações recusadas.
- Tempo de resposta.
- Bloqueios confirmados.
- Reservas efetivadas.
- Cancelamentos provocados pelo estabelecimento.
- Falhas de disponibilidade.
- Descumprimentos de reservas.

Esses registros poderão contribuir para um indicador de confiabilidade comercial do estabelecimento. Não punir automaticamente por ocorrência isolada. Considerar contexto, gravidade e reincidência.

---

## 11. Os três temporizadores independentes

O sistema deverá possuir três prazos diferentes. Eles não devem ser confundidos ou somados indiscriminadamente.

| Temporizador | Início | Referência inicial | Quem controla | Efeito ao expirar |
|---|---|---|---|---|
| T1 — Confirmação de participação | Formação do lobby que exige quadra particular | 1 hora | Backend | Substituição dentro da janela ou dissolução do lobby; a quadra não é acionada |
| T2 — Resposta do estabelecimento | Envio da solicitação, após todos confirmarem | 30 minutos de funcionamento + prazo máximo em tempo corrido | Backend, com horário de funcionamento do estabelecimento | Recusa/expiração; cancelamento ou redirecionamento, se houver tempo |
| T3 — Bloqueio e pagamento | Aceite e confirmação do bloqueio pelo estabelecimento | 60 minutos, configurável por estabelecimento, com buffer de 5 a 10 minutos | Backend e PSP | Liberação do bloqueio e reembolso do que foi pago |

Os prazos são independentes. O tempo total entre a formação do lobby e a confirmação da reserva pode ser maior do que a soma simples dos três, especialmente quando o prazo de resposta atravessa períodos de funcionamento ou dias fechados.

### 11.1 T1 — Confirmação de participação dos jogadores

Após a formação do lobby, os participantes deverão confirmar sua intenção de participar da partida, quando ela exigir reserva de quadra particular.

O prazo inicial será de **1 hora**. Esse valor é uma decisão de produto para a primeira versão do fluxo.

O sistema deverá enviar notificação, permitir confirmar ou recusar, registrar a confirmação no servidor, permitir substituições e encerrar a etapa no prazo.

Se um participante recusar ou não confirmar, o sistema poderá procurar um substituto. A substituição deverá ocorrer dentro da janela original de uma hora, sem reiniciar ou estender o prazo geral.

Se não houver participantes suficientes ao final da janela, o lobby será desfeito. A quadra ainda não terá recebido nenhuma solicitação nesse momento.

Não criar uma segunda etapa obrigatória de confirmação de prontidão de cinco minutos. A confirmação de participação de uma hora já cumpre essa função.

### 11.2 T2 — Prazo de resposta do estabelecimento

Depois que todos os participantes necessários confirmarem, o JOGA enviará a solicitação à quadra.

O estabelecimento terá um prazo para aceitar ou recusar. A referência inicial discutida é de **30 minutos de funcionamento**.

A contagem deverá considerar o horário de funcionamento cadastrado:

- Solicitação durante o expediente: começa imediatamente.
- Solicitação próxima ao fechamento: a contagem continua no próximo período aberto.
- Solicitação durante a madrugada: começa na próxima abertura.
- Solicitação em dia fechado: começa no próximo período de funcionamento.

O painel deverá permitir configurar os horários e períodos excepcionais.

Além disso, haverá um prazo máximo em tempo corrido, para que uma solicitação não fique pendente indefinidamente.

O JOGA deverá calcular se ainda existe tempo suficiente para a quadra responder, realizar o bloqueio e os jogadores pagarem antes da partida. Se não houver tempo suficiente, a solicitação não deverá ser enviada.

A referência de 30 minutos é inicial e deverá ser validada com os primeiros estabelecimentos. Uma sugestão posterior de duas horas não deve ser tratada como decisão aprovada.

> **Nota de implementação da Fase 13A:** o backend controla T1/T2/T3 com timers independentes, mas T2 usa tempo corrido nesta fase. O cálculo por horário de funcionamento, feriados e dias fechados permanece pendente.

### 11.3 T3 — Prazo de bloqueio e pagamento

Quando o estabelecimento aceitar e confirmar o bloqueio, começa o prazo de bloqueio temporário.

A referência inicial é de **60 minutos**, configurável por estabelecimento.

As cobranças dos participantes serão disponibilizadas simultaneamente. Todos terão exatamente o mesmo horário limite.

O pagamento deverá terminar antes da expiração do bloqueio, deixando um pequeno buffer operacional para conferir os eventos do PSP e concluir a reserva. Esse buffer poderá começar em **5 a 10 minutos**, sujeito a validação.

Exemplo ilustrativo:

| Evento | Horário |
|---|---|
| Estabelecimento aceita e bloqueia | 14:00 |
| Cobranças disponibilizadas | 14:00 |
| Prazo limite para pagamentos | 14:50 |
| Buffer operacional | 10 minutos |
| Expiração do bloqueio | 15:00 |

Os horários são apenas ilustrativos.

Não deverá existir prorrogação automática do bloqueio ou do prazo de pagamento.

Os prazos antigos de 24 horas e 2 horas para pagamento deverão ser removidos desta etapa. Eles não são compatíveis com o novo modelo de bloqueio temporário.

### 11.4 Independência, transparência e autoridade do servidor

Os três temporizadores deverão ter estados, eventos e responsáveis distintos. O sistema não deve somar os prazos nem reiniciar um temporizador quando outro termina.

O backend é a autoridade sobre todos os prazos. O aplicativo não deve usar tarefas locais, notificações ou o relógio do dispositivo como fonte oficial. Se o dispositivo estiver desligado ou sem conexão, o prazo continuará sendo controlado pelo servidor.

A interface deverá exibir cada prazo com um nome claro, para evitar que o usuário interprete a confirmação de participação, a resposta da quadra e o pagamento como uma única etapa.

---

## 12. Pagamentos Pix individuais e fluxo financeiro

### 12.1 Meio de pagamento inicial

A primeira versão de pagamentos das reservas utilizará exclusivamente **Pix**.

No **protótipo e beta fechado**, o PSP será o **Mercado Pago Checkout Transparente** (ADR 0034), com Pix, custódia centralizada de teste e repasse após a partida declarada. Em **produção**, permanece o Pagar.me Flex com split e liberação controlada (ADR 0021).

Débito e crédito serão avaliados posteriormente. Os benefícios do Pix deverão ser comunicados como vantagem econômica, sem apresentar o cartão como punição. Se futuramente houver cartão, o valor final deverá ser apresentado com transparência antes da confirmação.

A tarifa do PSP não é presumidamente gratuita. O JOGA deverá negociar e medir:

- Tarifa de recebimento Pix.
- Tarifas de devolução e de estorno.
- Tarifas de split e de repasse.
- Tarifa de transferência/liberação por reserva.
- Custos de manutenção e de cadastro de recebedores.
- Webhooks, conciliação e suporte.

### 12.2 Modelo de pagamentos individuais

**Cada participante deverá realizar seu próprio pagamento Pix.**

O JOGA não utilizará um modelo em que uma única pessoa paga a reserva inteira em nome do grupo. Esse modelo não corresponde à experiência planejada e não deverá ser sugerido como solução alternativa.

Exemplo: uma reserva de R$ 180 com dez participantes exige dez pagamentos individuais.

Cada pagamento deverá estar vinculado:

- À reserva.
- Ao lobby.
- Ao participante.
- À vaga ocupada.
- À contribuição individual.
- À taxa de serviço correspondente.
- À transação registrada pelo PSP.

Todas as cobranças deverão ser abertas simultaneamente depois que a quadra aceitar e confirmar o bloqueio. Todos terão o mesmo prazo de pagamento.

### 12.3 Condição para confirmação

A reserva será confirmada quando todos os participantes necessários tiverem pagamentos aprovados dentro do prazo.

O aceite inicial da quadra já representa um compromisso condicional de honrar a reserva, desde que todos paguem.

Não deverá existir uma segunda aprovação manual após os pagamentos se o estabelecimento já confirmou o bloqueio.

### 12.4 Custódia, split e liberação

O JOGA não construirá carteira própria nem custodiará valores de terceiros de forma informal. O desenho preferencial é o **split de pagamentos** com um PSP licenciado:

- Cada estabelecimento é cadastrado como recebedor (`recipient`).
- Cada participante paga sua cobrança Pix.
- A cobrança é dividida entre a parte do estabelecimento e a taxa do JOGA.
- O valor do estabelecimento permanece no saldo do recebedor até a liberação.
- O JOGA solicita a liberação **2 h após o início da reserva**, depois de pagamentos confirmados, conforme a ADR 0040; o serviço contratado é a quadra, não a realização da partida.
- A liberação é idempotente e registrada no ledger interno.

A liberação não pode depender de confirmação manual indefinida. Deve existir uma regra de liberação automática após `N` horas da partida, precedida de janela de disputa. O valor de `N` permanece pendente.

Se o estabelecimento conseguir sacar o saldo por conta própria, a retenção deixa de ser técnica e passa a ser apenas contratual. Nesse caso, o JOGA precisa:

1. Registrar a limitação no contrato.
2. Aumentar a provisão de cauda `p_t` da fórmula de precificação.
3. Rever a política de reembolso após a confirmação.

Na alternativa centralizada, o valor fica na conta do JOGA e o repasse ao estabelecimento ocorre depois da confirmação. Essa custódia exige revisão jurídica, segregação contábil e não é presumida como permitida.

No **protótipo e beta fechado**, a ADR 0034 permite uma custódia centralizada **de teste** no Mercado Pago: o valor fica na conta do JOGA, o ledger registra a obrigação por participante e o repasse ao estabelecimento é simulado ou manual após a partida ser declarada como acontecida (`COMPLETED`). Esse fluxo não é escrow, não promete reembolso de produção e só pode operar dinheiro real com MEI/CNPJ, contrato e revisão jurídica. A produção continua com Pagar.me e retenção controlada.

Na **Fase 14C**, cancelamentos e expirações do beta reembolsam integralmente as cobranças pagas usando o PSP simulado. A política de reembolso real, cancelamento após confirmação e conciliação com PSP continua pendente para a 14B.

### 12.5 Portão de KYC do estabelecimento

Um estabelecimento recém-cadastrado pode levar até 24 horas para ter a identidade validada e o recebedor ativo.

Regra obrigatória: **não abrir reserva paga para estabelecimento cujo recebedor não esteja ativo**. Se o KYC estiver pendente, a solicitação fica bloqueada e o jogador não é cobrado. Não se coleta Pix para uma quadra que ainda não pode receber.

O cadastro do recebedor exige dados cadastrais, conta bancária na mesma titularidade, validação de identidade e, conforme o PSP, prova de vida por QR Code. O JOGA deverá acompanhar o estado do recebedor e refleti-lo no painel.

### 12.6 Interface financeira do estabelecimento

Quando houver split, o PSP pode não oferecer dashboard própria ao recebedor. A interface financeira do estabelecimento passa a ser **escopo obrigatório**, não conveniência:

- Extrato por reserva e por cobrança.
- Agenda de recebíveis e status de liberação.
- Comprovantes e notas de repasse.
- Dados contratuais do recebedor.
- Canal de contestação de valores.
- Histórico de estornos e ajustes.

Essa interface atende às obrigações de transparência aplicáveis a facilitadores de pagamento (Res. 264/349) e deve ser tratada como parte do produto, com custo operacional próprio.

### 12.7 Requisitos do PSP

O provedor precisa suportar, direta ou contratualmente:

- Diversas cobranças Pix individuais para uma única reserva.
- Identificação de cada pagador.
- Associação das cobranças a uma reserva comum.
- Split por cobrança.
- Saldo por recebedor e liberação controlada.
- Estorno individual.
- Webhooks autenticados e idempotentes.
- Tratamento de pagamentos tardios.
- Conciliação e relatórios.

O ideal é que o PSP mantenha controle dos valores enquanto os pagamentos são concluídos e permita a distribuição no horário da reserva, conforme a ADR 0040.

**Se nenhum PSP conseguir oferecer um fluxo adequado de pagamentos individuais, split e liberação controlada, o lançamento das reservas com pagamento integrado deverá aguardar uma solução viável.** Essa capacidade é condição de viabilidade comercial, não um detalhe de integração.

Não substituir o modelo de pagamentos individuais pelo modelo de um único pagador.

### 12.8 Estados financeiros

A reserva e os pagamentos individuais não deverão compartilhar um único estado financeiro simplificado.

Cada participante deverá ter um estado financeiro individual, como:

- `CREATED`
- `PENDING`
- `PAID`
- `EXPIRED`
- `REFUND_PENDING`
- `REFUNDED`
- `REFUND_FAILED`

O estado agregado da reserva deverá ser derivado dos estados individuais e dos eventos do PSP, e não substituí-los. Uma reserva com dez participantes pode ter, por exemplo, oito pagamentos `PAID`, um `EXPIRED` e um `PENDING`, sem que isso seja representado como um único estado “pago” ou “não pago”.

### 12.9 Webhooks, idempotência e pagamentos tardios

O status financeiro oficial deverá ser confirmado por eventos autenticados do provedor, nunca apenas pelo retorno visual do aplicativo.

O sistema deverá:

- Validar a autenticidade dos webhooks.
- Processar eventos de forma idempotente.
- Impedir que o reenvio de um evento duplique pagamento, vaga, confirmação ou reembolso.
- Conciliar o estado interno com o PSP por consulta server-to-server quando necessário.
- Identificar pagamentos tardios.
- Encaminhar pagamentos tardios de reservas canceladas para reembolso.
- Encaminhar pagamentos de participantes já substituídos para reembolso.
- Registrar todas as transições com horário e referência do evento.

O aplicativo não poderá informar que um pagamento foi confirmado ou que um reembolso foi concluído enquanto o PSP não confirmar o resultado.

---

## 13. Substituição de participantes

### 13.1 Quando a substituição é permitida

A substituição continua sendo possível mesmo após a aceitação da quadra, para evitar cancelar toda a partida por causa de uma pessoa que não pagou.

A substituição deve ocorrer dentro da janela original de pagamento. Ela não reinicia o prazo e não prorroga o bloqueio da quadra.

### 13.2 Fonte de candidatos

A fonte prioritária será a fila de espera. Também poderão ser considerados outros usuários elegíveis para aquela partida.

### 13.3 Fluxo

1. Um participante não paga dentro do prazo.
2. O sistema identifica a vaga.
3. Verifica o tempo restante.
4. Seleciona um candidato elegível.
5. Envia o convite.
6. O candidato confirma sua participação.
7. Recebe sua cobrança Pix.
8. Realiza o pagamento dentro do prazo original.
9. A vaga é ocupada pelo novo participante.

O candidato deverá pagar exatamente a mesma contribuição prevista para aquela vaga, sem recalcular os valores dos demais participantes.

### 13.4 Regras obrigatórias

- A substituição não reinicia o prazo de pagamento.
- O bloqueio da quadra não é prorrogado.
- Apenas um candidato poderá ocupar uma vaga específica.
- Uma pessoa substituída não poderá ser restaurada automaticamente.
- Se houver pagamento tardio de uma pessoa já substituída, o JOGA deverá identificar a cobrança e iniciar o reembolso.
- O sistema deverá manter o histórico de qual participante ocupou cada vaga e em qual momento.
- As cobranças deverão estar associadas à versão correspondente da participação no lobby.

Inicialmente, poderá existir apenas uma tentativa de substituição por vaga durante a janela de pagamento. Essa regra deverá ser validada operacionalmente e não é uma decisão definitiva.

Se não houver substituto ou tempo suficiente, o lobby será cancelado. Os valores já pagos deverão ser devolvidos.

### 13.5 Confiabilidade dos participantes

O sistema poderá registrar padrões recorrentes de confirmação seguida de inadimplência.

Uma ocorrência isolada não deverá gerar punição automática.

Padrões repetidos poderão ser utilizados para avaliar a confiabilidade do cumprimento de compromissos, desde que existam critérios transparentes e tratamento de exceções. Esse indicador não deverá ser misturado automaticamente ao MMR.

---

## 14. Cancelamentos e reembolsos

### 14.1 Falha na formação da reserva

Se a reserva não for concluída por falta de pagamentos, indisponibilidade, falha de substituição ou expiração do bloqueio:

1. O lobby será cancelado.
2. O bloqueio será liberado.
3. Nenhuma nova cobrança será emitida.
4. Todos os participantes que pagaram receberão reembolso integral.
5. O reembolso incluirá a contribuição da quadra e a taxa de serviço paga ao JOGA.
6. As tarifas não recuperáveis do PSP serão custos operacionais do JOGA, cobertos pelo componente `C_c` da precificação.

Não deduzir automaticamente as tarifas do PSP do reembolso dos participantes nesse fluxo.

O valor principal devolvido não é prejuízo integral do JOGA quando está disponível para reembolso. O custo relevante é o que a plataforma efetivamente perde: tarifas não recuperáveis, atendimento, falhas de estorno e outros encargos. Esse custo é medido em `C_c`, nunca estimado como se o valor principal fosse perdido.

### 14.2 Estados do reembolso

O estado financeiro deverá distinguir:

- Reembolso solicitado.
- Reembolso em processamento.
- Reembolso concluído.
- Reembolso com falha.

O aplicativo não poderá informar que o reembolso foi concluído enquanto o PSP não confirmar o resultado.

### 14.3 Pagamentos tardios

Pagamentos tardios de reservas canceladas também deverão passar pelo fluxo de devolução, inclusive quando o cancelamento ocorreu depois da confirmação: a cobrança não corresponde a uma vaga ativa.

O mesmo vale para pagamentos de participantes que já foram substituídos. O sistema deverá identificar a cobrança, impedir a reativação automática da reserva e iniciar o reembolso.

### 14.4 Cancelamento depois da reserva confirmada

A política consolidada é definida pela **ADR 0039**:

- O serviço contratado é a reserva coletiva da quadra; a realização da partida é melhor esforço e depende do comparecimento dos participantes.
- **Antes do cutoff:** o jogador que cancela não recebe reembolso. O sistema abre a janela T4 de substituição. Se um substituto pagar a vaga, o substituído recebe reembolso da própria cobrança e a reserva continua. Se não houver substituto, o lobby é cancelado, o hold é liberado e os **demais pagantes** recebem reembolso integral; quem cancelou continua sem reembolso.
- **Depois do cutoff:** não há cancelamento voluntário com reembolso. A ausência é no-show: sem reembolso, com possibilidade de um substituto da fila ocupar a vaga já paga.
- **Falha da quadra ou do JOGA:** reembolso integral, respeitados os direitos legais do consumidor.
- O destino do valor não reembolsado do cancelador (compensação da quadra ou crédito de boa-fé) permanece pendente e exige evento próprio no ledger.

O valor do estabelecimento é liberado 2 h após o início da reserva, conforme a ADR 0040. Se a quadra mantém o horário disponível, a reserva é entregue mesmo que a partida não ocorra; a ausência de jogadores não impede o repasse. Se a quadra falhar, não há repasse e o estorno deve refletir a reversão.

Se o estabelecimento já tiver sacado o valor, a recuperação deixa de ser automática. Esse é um evento de cauda, tratado por `p_t` e por cláusula contratual específica.

### 14.5 Desistência individual, fila de substitutos e presença

A política aprovada na **ADR 0039** é:

- **Fila de substitutos:** cada lobby pode manter uma fila em standby. O alvo é `(titulares - quórum mínimo) + 1`, limitado a 4; na prática, muitas vezes basta **+1 para fechar o time par**. Casual é opcional; ranqueado exige pelo menos 1 substituto em standby.
- **Substituto não é convocado** até haver vaga. Ele confirma disponibilidade em T-2h; se não confirmar, sai da fila.
- **Antes do cutoff**, com substituto pagante: o substituído recebe reembolso; o substituto paga; T3 não reinicia.
- **Sem substituto antes do cutoff:** o lobby é cancelado, os demais pagantes recebem reembolso e quem cancelou não recebe.
- **Depois do cutoff/no-show:** o ausente não recebe reembolso; um substituto chamado pode jogar na **vaga já paga**, sem nova cobrança, e a quadra recebe normalmente.
- **Presença:** pré-check-in em T-1h (obrigatório no ranqueado) e confirmação no local em T-30m, com geofence, QR/NFC, capitão ou estabelecimento. GPS não é prova isolada; o servidor valida e há fallback.
- **Confiabilidade:** desistências e ausências geram eventos de Trust Factor em fase própria; uma ausência isolada não gera punição pesada. Cancelamentos da quadra afetam a confiabilidade comercial da quadra, não o ranking do jogador.
- **Limite proposto:** 2 cancelamentos confirmados por 30 dias; acima disso, Trust Factor e restrição temporária a partidas ranqueadas.
- **Transparência:** a regra deve aparecer antes do pagamento, nos termos de uso e nas condições da reserva, com exemplos claros.

### 14.6 Descumprimento pelo estabelecimento

Se o estabelecimento descumprir o compromisso depois de os participantes terem pago, o JOGA deverá cancelar a reserva e iniciar os reembolsos.

O histórico do estabelecimento deverá registrar o evento e contribuir para o indicador de confiabilidade comercial, sem punição automática por ocorrência isolada.

### 14.7 MED, chargeback e estorno sem saldo

No Pix, o risco relevante não é apenas o chargeback de cartão. O **MED (Mecanismo Especial de Devolução)** pode debitar o valor do recebedor ou da plataforma, conforme a regra de responsabilidade e o saldo disponível.

O JOGA deverá:

- Confirmar com o PSP quem é debitado em caso de MED.
- Definir o que acontece quando o recebedor não tem saldo.
- Manter canal e prazo de contestação.
- Provisionar o risco de cauda em `p_t·V`.
- Registrar cada evento e sua resolução.

O MED pode chegar depois da liberação. A retenção até a partida protege contra reserva frustrada; não protege contra fraude. Contra fraude existe provisão e contrato, não apenas bloqueio de saldo.

### 14.8 Base financeira dos reembolsos

A precificação separa três coisas:

1. **Valor principal:** pertence ao jogador e é devolvido quando a reserva não se conclui.
2. **Custo da reserva cancelada (`C_c`):** tarifas não recuperáveis, devolução e atendimento. É custo do JOGA e entra na fórmula.
3. **Provisão de cauda (`p_t·V`):** eventos raros, como MED, estorno sem saldo e disputa após liberação.

Não contar o valor principal como perda. Não contar `C_c` duas vezes. Não usar o markup de segurança como se fosse lucro livre.

### 14.9 Adaptação de formato, presença e temporizadores

Quando o número de presentes não fecha o formato original, a partida pode ser adaptada para manter o jogo:

| Presentes | 5x5 | 6x6 | 3x3 |
|---:|---|---|---|
| 12 | — | 6x6 | — |
| 11 | — | 5x5 + 1 rodízio | — |
| 10 | 5x5 | 5x5 | — |
| 9 | **4x4 + 1 rodízio** | **4x4 + 1 rodízio** | **três times de 3** |
| 8 | 4x4 | 4x4 | 4x4 ou 3x3 + 2 |
| 7 | **3x3 + 1 rodízio** | **3x3 + 1 rodízio** | **3x3 + 1 rodízio** |
| 6 | 3x3 | 3x3 | 3x3 |
| menos de 6 | sem jogo | sem jogo | sem jogo |

- O excedente entra em **rodízio**, não em reembolso. Reembolsar um jogador para “fechar 4x4” deixa o valor abaixo do preço da quadra; só é possível se a quadra reduzir o preço ou o JOGA conceder crédito de boa-fé.
- Rodízio por tempo ou por evento, com fila única e registro de minutos jogados.
- Partida adaptada de 5x5 para 4x4 não conta como 5x5 ranqueado; usar casual ou o MMR do formato efetivamente jogado.
- Temporizadores: T1 60 min; T2 30 min comercial com máximo 60 min; T3 60 min; T4 = 25% do tempo restante, piso 30 min, teto 12 h, terminando no cutoff; cutoff de cancelamento 6 h antes; fila confirma em T-2h; pré-check-in em T-1h; presença no local em T-30m; substituto fechado em T-15m.
- Contestação financeira e repasse (`N`) continuam **não definidos** e não se confundem com esses prazos.

---

## 15. Comércio de produtos — fora do escopo

O comércio de produtos **não faz parte do escopo inicial** e não é especificado nesta versão.

Não haverá, nesta etapa:

- catálogo de produtos;
- estoque;
- pedidos;
- cadastro de vendedores;
- retirada ou entrega de produtos;
- código de recebimento;
- avaliações comerciais;
- disputas de produtos;
- pagamentos ou split de produtos.

Lojas esportivas poderão participar apenas como patrocinadoras ou anunciantes, sem vender produtos dentro do aplicativo.

Qualquer reintrodução exige nova decisão de produto, nova especificação técnica, revisão jurídica, definição de PSP e avaliação de capacidade operacional. Não reativar por documento antigo, código antigo ou fase antiga. A decisão está registrada no ADR 0022.

---

## 16. Publicidade e monetização

### 16.1 Fontes de receita iniciais

A monetização inicial deverá se concentrar principalmente em:

1. **Margem de intermediação no Ingresso JOGA** — pacotes e passe (ADR 0042, §16.7 e §16.8).
2. **Parcerias comerciais.**
3. **Patrocínios.**
4. **Publicidade contextual**, quando houver audiência suficiente.

Funcionalidades essenciais de jogadores, matchmaking, partidas e comunidades continuarão predominantemente gratuitas.

A assinatura do produto é o **passe trimestral** definido na ADR 0043. Não criar outra assinatura apenas para adicionar uma fonte de receita.

### 16.2 Comissão sobre reservas

> **Escopo.** Esta seção descreve a comissão da **reserva avulsa**. No fluxo de ingresso, a receita é a margem entre o preço do ingresso e a cota da quadra (ADR 0042 §5), e a variável `c` não existe.

O JOGA poderá cobrar uma taxa de serviço sobre reservas originadas pela plataforma.

A comissão não deverá incidir sobre reservas que o estabelecimento conseguiu de maneira independente.

A receita deverá estar associada a uma reserva efetivamente concluída. Quando uma solicitação não se transforma em reserva, não existe receita comercial realizada com aquela reserva.

A comissão `c·V` é a fonte de receita que cobre custo fixo da operação e lucro-alvo. O custo variável de cada reserva e a provisão de cancelamento entram como componentes explícitos da fórmula da seção 17. Não usar a comissão para financiar silenciosamente o custo variável já cobrado do jogador.

### 16.3 Estabelecimentos parceiros

As quadras particulares poderão participar do JOGA por meio de um painel próprio de gestão.

O sistema deverá permitir administrar solicitações, horários bloqueados, reservas, pagamentos e histórico.

Não será necessário que a quadra utilize um software externo específico. O JOGA deverá conseguir operar com estabelecimentos que utilizam agendas manuais, planilhas, WhatsApp ou sistemas sem API.

Integrações externas serão desejáveis futuramente, mas não obrigatórias para o lançamento.

### 16.4 Publicidade

A publicidade deverá ser identificada como patrocinada. A posição paga não poderá alterar o MMR, o Trust Factor, a composição do matchmaking ou a justiça dos rankings. Recomendações patrocinadas deverão respeitar filtros e restrições relevantes do usuário.

A publicidade avançada depende de audiência e volume de uso. Não deve ser tratada como receita garantida antes de existir tráfego suficiente.

### 16.5 Assinaturas

O passe trimestral da ADR 0043 é a assinatura do produto: cobrança única por trimestre, franquia de ingressos entregue mês a mês, trilha de temporada, customização e estatísticas. Não existe passe mensal. Não criar uma assinatura apenas para adicionar uma fonte de receita.

### 16.6 Regras gerais de monetização

- Nenhuma taxa oculta.
- Nenhuma vantagem competitiva comprada.
- Nenhuma alteração de MMR, Trust Factor, matchmaking ou ranking por pagamento.
- Nenhuma comissão sobre reservas externas ao JOGA sem acordo explícito.
- Nenhuma receita de comércio de produtos no escopo inicial.
- Toda cobrança deverá ser explicável ao usuário antes do pagamento.

### 16.7 Ingresso JOGA

O fluxo comercial principal passa a ser o **Ingresso JOGA**, registrado na ADR 0042. Ele não é saldo em reais, não é moeda e não é transferível: é uma unidade de acesso pessoal, com preço de referência de R$ 3,10 no pacote grande e R$ 3,70 no avulso.

- **O jogador vê apenas ingressos.** Reais aparecem somente no checkout de pacote e de passe.
- **Custo da partida em ingressos** decorre de uma tabela 2D (formato × faixa). A faixa é ancorada em atributo visível — cobertura e dia/noite —, nunca no preço da quadra.
- **Consumo na confirmação da reserva**, não no check-in. A matriz de devolução da ADR 0039 é preservada, sempre em ingressos.
- **Passe trimestral** com franquia mensal de 10, 20, 30 ou 50 ingressos, quantidade fixa, reset mensal e sem acumular. Ingresso comprado nunca expira.
- **Sem mercado de saldo:** sem transferência, revenda, saque ou troca entre usuários. A única exceção é o direito de arrependimento de 7 dias.
- **Matchmaking por intenção:** região, horário, formato e nível primeiro; o saldo é restrição sobre o resultado, não a consulta.
- **Reajuste sem quebrar a reserva feita:** o estabelecimento reajusta apenas janelas futuras sem reserva, na virada de temporada e com aviso de 30 dias. Pausar ou fechar com reserva confirmada conta como falha da quadra e devolve os ingressos.

A natureza jurídica é de **intermediação**: o saldo é obrigação com o jogador e a parte da quadra é obrigação com o estabelecimento, reconhecida na reserva. A base de cálculo pretendida dos tributos é a comissão, sujeita a parecer fiscal.

O saldo carregado é **passivo, não receita**. O ganho econômico do modelo pré-pago é capital de giro dispensado — não precisa ser contratado para pagar as quadras — e não rendimento de float nem receita de ingresso não usado.

Ficam inalteradas as fontes de receita das seções 16.1 a 16.6: comissão sobre reservas, parcerias, patrocínios e publicidade contextual. Publicidade e customização continuam **não** sendo vantagem competitiva.

### 16.8 Temporada, passe e customização

A temporada, o passe trimestral e as regras de customização estão na ADR 0043.

- **Temporada de 3 meses.** Um único reset, alinhado ao passe. Não existe passe mensal.
- **Passe trimestral** com cobrança única e franquia mensal de 10, 20, 30 ou 50 ingressos, a **R$ 3,25 por ingresso** (R$ 32,50 a R$ 162,50 por mês). A entrega é mensal e não pode ser adiantada.
- **Pacotes com preço decrescente:** 3 a R$ 3,70 · 10 a R$ 3,40 · 30 a R$ 3,20 · 50 a R$ 3,10. O avulso é mais caro de propósito; é ele que financia o pacote grande.
- **Ingressos grátis por nível:** o tier gratuito recebe 1 a cada 5 níveis (até 6 por temporada) e o passe recebe 2 (até 12). Expiram no fim da temporada.
- O passe custa mais por ingresso que o pacote grande porque entrega algo fora do dinheiro real: franquia mensal, ingressos grátis, Temporada e cosméticos.
- **XP igual para todos.** A assinatura muda o que se desbloqueia, nunca a velocidade de progressão.
- **Trilha de 30 níveis**, três missões semanais, **streak de vitórias com validade semanal** e nível de temporada (bronze/prata/ouro) que reseta na virada e **é visível para todos, inclusive no free**.
- **Jogador que entra no meio da temporada começa no nível 1**, sem crédito proporcional.
- **Customização em três estados:** livre, ganho por XP e perk do passe. Traço de identidade e acessibilidade nunca são pagos.
- **Customização geral do app** no passe: temas, cor de destaque, densidade dos cartões, blocos da home, sons e háptica. Acessibilidade continua livre.
- **Estatísticas** apenas sobre o que a plataforma observa. **Essencial e livre:** MMR atual, partidas, V/E/D, presença, streak e sequência de temporadas. **Do passe:** evolução do MMR, histórico por quadra, passaporte, horários e formatos, retrospectiva da temporada. Sem mapa de calor nem dado de evento de jogo.
- **Não são benefícios do passe:** convite de estreia, remoção de anúncios, bônus de XP, badges, escudo de clã e as estatísticas essenciais.
- **Inteligência de rede** no passe: mapa de calor de horários, densidade competitiva por quadra e ocupação, sempre em faixas e com apresentação simples. Free vê a lista de quadras mais usadas. Não é filtro de busca.
- **Lobby privado é benefício do passe.**
- **Escudo de clã é livre** — o clã aparece no perfil de todo jogador. Do passe, só o **destaque no perfil do clã**.

---

## 17. Política de precificação

### 17.1 Princípio

A taxa deve cobrir o custo real de operar a reserva, o risco de cancelamento e a margem necessária para manter o serviço, sem cobrar do jogador um coeficiente arbitrário sobre custos que não existem.

A política não usa piso, preço variável nem teto percentual como mecanismos independentes. Usa uma fórmula com componentes explícitos e uma regra de elegibilidade.

> **Escopo.** Esta seção vale para reserva avulsa paga em reais. No **fluxo de ingresso** ela é substituída pela ADR 0042: o preço passa a vir da tabela 2D, a margem passa a ser saída (`(R − custeio) / V`) e o piso passa a ser 10% líquido no topo da faixa. Permanecem válidos os componentes de custo e a lógica de elegibilidade, recalibrados.

### 17.2 Fórmula

```text
TAXA = c·V + C_k + C_c·μ·S + p_t·V

μ = (1 − q) / q
S = 1 + z·√(φ / μ)
```

| Termo | Significado | Quem paga |
|---|---|---|
| `c·V` | Comissão comercial sobre o valor da quadra | Custo fixo da operação e lucro-alvo |
| `C_k` | Custo variável de uma reserva concluída | Tarifas do PSP, split, transferência, operação |
| `C_c` | Custo de uma reserva cancelada | Tarifas não recuperáveis, devolução e atendimento |
| `μ` | Cancelamentos esperados por reserva concluída | — |
| `S` | Fator de segurança para a variância dos cancelamentos | — |
| `p_t·V` | Provisão de cauda | MED, estorno sem saldo, disputa após liberação |

`q` é a taxa de conclusão: reservas pagas que efetivamente se confirmam e se realizam, divididas pelas tentativas de reserva paga abertas no período.

O valor principal pago pelo jogador **não** entra em `C_c` nem em `p_t`. Ele é devolvido integralmente quando a reserva não se conclui.

### 17.3 O que o 1,8 significava

Com `q = 20%`, `μ = 4` e `φ = 1`:

```text
S = 1 + 1,645/√4 = 1,82
μ·S = 7,29
```

O antigo coeficiente **1,8** é, na prática, o fator de segurança de 95% para a variância do número de cancelamentos no cenário de 80% de cancelamento. Ele **não** é markup sobre o custo total.

Regras decorrentes:

- O 1,8 não incide sobre `C_k`.
- O 1,8 não incide sobre `CUSTOS + LUCRO_ALVO`.
- O 1,8 não é lucro livre.
- O 1,8 não é aplicado duas vezes.
- A proteção de 95% aparece em `S`, apenas sobre a provisão de cancelamento.

### 17.4 Componentes e medição

**Comissão (`c·V`).** Parâmetro comercial. Cobre custo fixo da plataforma (produto, suporte, KYC, interface financeira do recebedor, infraestrutura) e lucro-alvo. O valor inicial de trabalho é `c = 10%`, a validar no piloto.

**Custo da reserva concluída (`C_k`).** Agrega:

- tarifa percentual do PSP sobre o valor total pago;
- custo fixo por cobrança;
- tarifa de split;
- tarifa de transferência/liberação;
- conciliação e operação variável.

**Custo da reserva cancelada (`C_c`).** Agrega:

- tarifa de recebimento não recuperada;
- tarifa de devolução/estorno;
- custo de atendimento;
- custo de reprocessamento e falha de reembolso.

Não inclui o valor principal devolvido.

**Cancelamentos esperados (`μ`).** `(1 − q) / q`. Se 20% das tentativas concluem, há 4 cancelamentos esperados por reserva concluída.

**Fator de segurança (`S`).** `1 + z·√(φ/μ)`. `z = 1,645` corresponde a 95% de confiança. `φ = 1` assume cancelamentos com dispersão de Poisson; `φ > 1` deve ser usado quando cancelamentos são correlacionados (chuva, feriado, horário).

**Provisão de cauda (`p_t·V`).** Cobre eventos raros e de valor alto: MED, estorno sem saldo, disputa depois da liberação, falha de PSP. Valor inicial de trabalho: `p_t = 0,2%`.

### 17.5 Base de cálculo e ponto fixo

As tarifas percentuais do PSP incidem sobre o valor total pago (`V + TAXA`), não apenas sobre o valor da quadra. O cálculo deve ser resolvido como ponto fixo:

```text
S_total = V + TAXA
C_k = a_k + p·S_total + τ
C_c = a_c + p·S_total·(m/k)
TAXA = c·V + C_k + C_c·μ·S + p_t·V
```

Onde:

- `a_k` = custo fixo agregado da reserva concluída.
- `p` = tarifa percentual do PSP.
- `τ` = tarifa de transferência/liberação.
- `a_c` = custo fixo por cancelamento.
- `m` = cobranças médias pagas antes do cancelamento.
- `k` = participantes/cobranças da reserva concluída.

O valor exibido ao jogador é congelado quando a cobrança é aberta. Recalibrações valem apenas para reservas futuras.

### 17.6 Parâmetros iniciais

| Parâmetro | Valor inicial | Natureza |
|---|---|---|
| `q` | Medido em janela móvel de 90 dias | Dado operacional |
| `c` | 10% | Hipótese comercial |
| `z` | 1,645 | 95% de confiança |
| `φ` | 1,0 | Poisson; revisar com dados |
| `p_t` | 0,2% | Provisão inicial de cauda |
| `C_k`, `C_c`, `τ` | Medidos por contrato e operação | Substituir hipóteses por dados reais |

Nenhum desses valores é preço final aprovado. O piloto deve medir `q`, `C_k`, `C_c`, `τ` e `p_t` antes de qualquer promessa comercial.

### 17.7 Elegibilidade mínima da quadra

O antigo teto de 15%–20% é substituído por uma regra de elegibilidade.

- Se a taxa calculada ultrapassar o limite operacional aceito para a faixa (referência inicial: **25% do valor da quadra**), a reserva paga não é oferecida.
- Se o valor da quadra for baixo demais para diluir os custos fixos, o estabelecimento deve renegociar o preço da quadra ou operar sem pagamento integrado.
- A decisão é registrada com valor calculado, faixa e motivo.

A regra não é um desconto nem um subsídio. É uma recusa consciente de operar no prejuízo. Com `q = 20%`, a referência de **R$ 100** de valor mínimo mantém a taxa abaixo de 25%; esse número é ilustrativo e será recalibrado.

### 17.8 Calibração e governança

- `q` é medido por modalidade e faixa de preço, com janela móvel e amortecimento.
- Não usar `q` por quadra sem amostra suficiente; isso gera seleção adversa.
- A taxa não varia em tempo real. A variação por ciclo é limitada a ±10%.
- A taxa de uma reserva não muda depois que o pagamento foi aberto.
- Aumentos e reduções exigem justificativa econômica, simulação e versionamento.
- `C_k`, `C_c`, `τ` e `p_t` são revisados quando o contrato do PSP ou o comportamento observado mudar.
- A fórmula e os parâmetros aplicados ficam registrados por reserva, para auditoria.

### 17.9 Divisão da taxa

O valor total da taxa será distribuído entre os participantes conforme a regra de divisão financeira da reserva.

Não cobrar a taxa integral de cada participante.

A contribuição individual deverá ser transparente antes do pagamento.

### 17.10 Exemplo ilustrativo

Com `V = R$ 180`, `k = 10`, `c = 10%`, PSP a 0,90%, `C_k ≈ R$ 3,46`, `C_c ≈ R$ 2,18` e `p_t = 0,2%`:

| `q` | `μ` | `S` | `μ·S` | Taxa | % da quadra |
|---:|---:|---:|---:|---:|---:|
| 20% | 4,00 | 1,82 | 7,29 | R$ 37,68 | 20,9% |
| 40% | 1,50 | 2,34 | 3,51 | R$ 29,23 | 16,2% |
| 80% | 0,25 | 4,29 | 1,07 | R$ 23,95 | 13,3% |

O exemplo serve para explicar a fórmula. Não é uma tabela de preços aprovada.

---

## 18. Simulações financeiras e análise de viabilidade

### 18.1 Objetivo e método

Esta seção testa a fórmula aprovada em cenários de conclusão, custo de cancelamento, tarifa de transferência e valor de quadra. Também compara a fórmula com o antigo coeficiente 1,8 e registra a decisão de PSP.

As simulações são **ilustrativas**. Não constituem tabela de preços nem promessa de margem.

### 18.2 Hipóteses de simulação

| Parâmetro | Valor adotado | Natureza |
|---|---|---|
| Valor da quadra (`V`) | R$ 180 | Exemplo para futebol 5x5; não é preço oficial |
| Participantes (`k`) | 10 | Formato futebol 5x5 |
| Comissão (`c`) | 10% | Hipótese de trabalho |
| Tarifa percentual do PSP (`p`) | 0,90% | Hipótese; negociar no Flex |
| Custo fixo da reserva concluída (`a_k`) | R$ 1,50 | Hipótese; substituir pelo contrato |
| Custo fixo do cancelamento (`a_c`) | R$ 1,00 | Hipótese; substituir pelo contrato |
| Cobranças pagas antes do cancelamento (`m`) | 6 | Média de trabalho |
| Tarifa de transferência (`τ`) | R$ 0,00 no cenário-base | Testar sensibilidade |
| Nível de confiança (`z`) | 1,645 | 95% |
| Sobredispersão (`φ`) | 1,0 | Poisson |
| Provisão de cauda (`p_t`) | 0,2% | Hipótese conservadora |
| Impostos | Não modelados | Dependem do regime e do município; revisão fiscal necessária |
| Divisão da taxa | Igual entre participantes | Regra conceitual; validar |

Cenários de conclusão: **20%, 30%, 40%, 60%, 80% e 90%**. O cenário de 20% representa estresse e não deve ser tratado como previsão.

### 18.3 Resultado por taxa de conclusão

`V = R$ 180`, `k = 10`, `c = 10%`, PSP a 0,90%, `C_k ≈ R$ 3,46`, `C_c ≈ R$ 2,18`, `p_t = 0,2%`.

| `q` | `μ` | `S` | `μ·S` | Taxa | % da quadra |
|---:|---:|---:|---:|---:|---:|
| 20% | 4,00 | 1,82 | 7,29 | R$ 37,68 | 20,9% |
| 30% | 2,33 | 2,08 | 4,85 | R$ 32,17 | 17,9% |
| 40% | 1,50 | 2,34 | 3,51 | R$ 29,23 | 16,2% |
| 60% | 0,67 | 3,01 | 2,01 | R$ 25,96 | 14,4% |
| 80% | 0,25 | 4,29 | 1,07 | R$ 23,95 | 13,3% |
| 90% | 0,11 | 5,93 | 0,66 | R$ 23,07 | 12,8% |

A taxa cai quando a conclusão melhora porque o custo esperado de cancelamento cai. Não é um desconto comercial: é o mesmo custo, distribuído sobre mais reservas concluídas.

### 18.4 Comparação com o coeficiente 1,8

A comparação usa `C = C_k + μ·C_c` e `TAXA = c·V + 1,8·C`, mantendo o PSP a 0,90%.

| `q` | Fórmula aprovada | Referência 1,8 |
|---:|---:|---:|
| 20% | R$ 37,68 (20,9%) | R$ 40,02 (22,2%) |
| 40% | R$ 29,23 (16,2%) | R$ 29,86 (16,6%) |
| 80% | R$ 23,95 (13,3%) | R$ 24,97 (13,9%) |

A fórmula aprovada fica levemente mais barata em todos os cenários e mais próxima do custo real. A diferença é o buffer que o 1,8 aplicava sobre a parte determinística.

### 18.5 Sensibilidade ao custo de cancelamento

`q = 20%`, `V = R$ 180`, variando o custo fixo por cancelamento (`a_c`).

| `a_c` | Taxa | % da quadra |
|---:|---:|---:|
| R$ 0,50 | R$ 33,85 | 18,8% |
| R$ 1,00 | R$ 37,68 | 20,9% |
| R$ 2,00 | R$ 45,34 | 25,2% |
| R$ 3,00 | R$ 53,00 | 29,4% |
| R$ 5,00 | R$ 68,32 | 38,0% |

`C_c` é o parâmetro mais sensível da fórmula. Um cancelamento com muitas cobranças pagas e devolução cara pode inviabilizar a faixa. Por isso a regra de elegibilidade existe.

### 18.6 Sensibilidade à tarifa de transferência

`q = 20%`, variando a tarifa de liberação por reserva (`τ`).

| `τ` | Taxa | % da quadra |
|---:|---:|---:|
| R$ 0,00 | R$ 37,68 | 20,9% |
| R$ 1,00 | R$ 38,73 | 21,5% |
| R$ 3,67 | R$ 41,53 | 23,1% |

O exemplo documentado de `POST /transfers` do Pagar.me retorna `fee: 367`. Se a liberação Pix custar algo nessa ordem, ela é custo **por reserva**, não por cobrança, e precisa entrar em `C_k`. A tarifa real deve ser confirmada em contrato.

### 18.7 Quadras baratas e elegibilidade

`q = 20%`, `k = 10`, demais parâmetros do cenário-base.

| `V` | Taxa | % da quadra | Total por pessoa |
|---:|---:|---:|---:|
| R$ 60 | R$ 18,72 | 31,2% | R$ 7,87 |
| R$ 90 | R$ 23,46 | 26,1% | R$ 11,35 |
| R$ 120 | R$ 28,20 | 23,5% | R$ 14,82 |
| R$ 180 | R$ 37,68 | 20,9% | R$ 21,77 |

Abaixo de aproximadamente **R$ 100**, a taxa ultrapassa 25% no cenário de 20% de conclusão. A resposta correta não é subsidiar a reserva: é não oferecer pagamento integrado naquela faixa, renegociar o preço da quadra ou aumentar a conclusão operacional.

### 18.8 PSP: Inter em produção e Mercado Pago no teste

> **Escopo.** O split e o recebedor analisados aqui valem para o fluxo de **reserva avulsa**. No fluxo de ingresso (ADR 0042) a cobrança é por pacote ou passe, sem split e sem recebedor de marketplace.

**Inter PJ — produção.**

- Conta corrente, não conta de pagamento: o dinheiro cai direto na conta da PJ.
- API Pix e de extratos gratuita; Pix de saída gratuito.
- **0,90% no QR dinâmico imediato**, mínimo de R$ 0,10 e teto de R$ 1,50. O teto faz o passe grande custar 0,35% por real transacionado.
- Usar o **QR imediato**, não o com vencimento (0,99%).
- Dispensa segundo provedor para o repasse: recebe e paga pela mesma conta.

**Mercado Pago — protótipo e beta fechado (ADR 0034).** Já integrado. Restrito ao teste: libera o saldo do vendedor com prazo e só paga contas Mercado Pago.

**Pagar.me — reserva técnica.** Forte em split e recebedores; é o candidato natural se o produto migrar para cobrança na reserva, em que a quadra já é conhecida no momento da cobrança.

**Por que a tarifa fixa foi descartada:** Asaas (R$ 2,15 por Pix) e OpenPix (0,80% com mínimo de R$ 0,50) cobram por cobrança. Com dez cobranças por partida, a tarifa fixa consome uma parte desproporcional do valor da quadra.

Perguntas abertas para o Inter antes do contrato:

1. aceite escrito da atividade (crédito pré-pago de serviços) e do perfil transacional;
2. tarifa confirmada para conta PJ de LTDA;
3. teto e mínimo por transação aplicados a volume;
4. estorno parcial de Pix por API, após liquidação, com prazo;
5. webhook e idempotência por `txid`;
6. limite de requisições, sandbox e prazo de onboarding.

### 18.9 Financiamento dos cancelamentos

O custo esperado de cancelamento é explícito:

```text
custo esperado = μ·C_c
buffer estatístico = μ·C_c·(S − 1)
```

Com `q = 20%`, `μ = 4`, `S = 1,82` e `C_c = R$ 2,18`:

```text
custo esperado = R$ 8,72
buffer = R$ 7,15
provisão total = R$ 15,87
```

O custo esperado de cancelamento é financiado pela parcela `C_c·μ·S` embutida na taxa de todas as reservas: as reservas que concluem pagam a provisão que cobre as que cancelam. A comissão `c·V` permanece separada, para custo fixo e lucro. O buffer `S` existe para a variância, não para o valor principal.

> **No fluxo de ingresso** (ADR 0042) o `q` sobe, porque o pagamento sai do caminho, e o `C_c` cai, porque cancelar devolve ingresso e não dinheiro. Com `q = 75%` e `C_c = R$ 0,47`, a provisão é **R$ 0,60 por jogador** — não R$ 15,87 por reserva. Ver ADR 0042 §5.

Para continuidade histórica: no desenho antigo, a comissão mais o markup sobre a reserva concluída cobriam o custo dos cancelamentos. Com `V = R$ 180`, `c = 10%`, `C_k ≈ R$ 4,86` e markup de 80%, o ponto de equilíbrio ocorria com `C_c ≈ R$ 5,47`. Esse número continua útil como referência de quanto custo de cancelamento a comissão mais o buffer suportavam. Na fórmula nova, se `C_c` subir acima do previsto, a taxa sobe e a reserva pode se tornar inelegível; não há prejuízo silencioso.

### 18.10 Custo fixo e suficiência da comissão

A comissão também precisa pagar custo fixo: produto, suporte, KYC, interface financeira do recebedor e eventual cobrança por recebedor.

Com `V = R$ 180`, `c = 10%` e `q = 20%`, o excedente esperado por reserva concluída depois de cobrir o custo esperado de cancelamento e a provisão de cauda fica em cerca de **R$ 23 a R$ 25**. Esse excedente é a contribuição disponível para custo fixo e lucro.

| Custo fixo por estabelecimento/mês | Reservas/mês só para cobrir esse custo |
|---:|---:|
| R$ 30 | 1,3 |
| R$ 60 | 2,6 |
| R$ 100 | 4,3 |
| R$ 200 | 8,6 |

Se a interface financeira, o KYC e a taxa por recebedor custarem R$ 100 por quadra/mês e cada quadra fizer 5 reservas, são R$ 20 por reserva só nisso. A comissão de R$ 18 não paga. Esse é o item que decide se `c = 10%` é suficiente — e ele **não** entra em `C_k`.

### 18.11 O que a fórmula não resolve

- **Conclusão baixa.** A 20% de conclusão, a taxa é 21% da quadra em qualquer fórmula honesta. O que corrige isso é T1/T2/T3 e tempo de resposta do estabelecimento, não precificação.
- **Quadra barata.** A `V = R$ 60`, a taxa chega a 31,2%. Isso pede elegibilidade mínima, não teto.
- **Transparência.** A provisão de cancelamento é um subsídio dos 20% que concluem para os 80% que cancelam. Precisa estar explicada na seção 19.
- **Custo fixo.** A fórmula não decide se a comissão é suficiente para operar; isso é uma decisão separada de negócio.

### 18.12 Conclusão e plano de calibração

A fórmula aprovada substitui o coeficiente fixo, o piso e o teto por componentes com significado econômico.

| Parâmetro | Como medir | Inicial |
|---|---|---|
| `q` | Lobbies concluídos / tentativas de reserva paga, EWMA de 90 dias | medir |
| `C_k` | Tarifa real por cobrança + transferência / reserva | medir |
| `C_c` | Tarifa não recuperada + atendimento por devolução | medir |
| `φ` | Variância / média dos cancelamentos por período | 1,0 |
| `z` | Apetite de risco | 1,645 |
| `p_t` | Perdas efetivas com MED e estorno sem saldo / `V` | 0,2% |

Recomendações:

1. Rodar piloto com poucos estabelecimentos antes de abrir pagamento integrado em escala.
2. Medir `q`, `C_k`, `C_c`, `τ` e `p_t` por modalidade e faixa de preço.
3. Não recalcular a taxa em tempo real.
4. Não individualizar `q` por quadra sem amostra suficiente.
5. Fixar a taxa no momento da abertura do pagamento.
6. Revisar a elegibilidade mínima depois dos primeiros dados.

### 18.13 Fontes consultadas

- Pagar.me — Plano Flex: https://www.pagar.me/ofertas
- Pagar.me — Documentação V5: https://docs.pagar.me/docs/overview-principal
- Pagar.me — Incluir cobrança no pedido: https://docs.pagar.me/reference/incluir-cobrança-no-pedido
- Pagar.me — Recebedores: https://docs.pagar.me/docs/recebedores
- Pagar.me — Criando uma transferência: https://docs.pagar.me/reference/criando-uma-transferência
- Pagar.me — Estorno parcial com split: https://docs.pagar.me/docs/estorno-parcial-com-split
- Inter — Tarifas e Pix: https://bancointer.com.br/
- Asaas — Preços e taxas: https://www.asaas.com/precos-e-taxas
- AbacatePay — Preços: https://abacatepay.com/
- OpenPix — Preços: https://openpix.com.br/

Consulta em 5 de novembro de 2026. Tarifas públicas podem mudar e não substituem contrato comercial.

---

## 19. Experiência do usuário e transparência de preço

A taxa do JOGA deverá ser apresentada de maneira transparente.

Antes do pagamento, cada jogador deverá visualizar:

- Valor da reserva.
- Sua contribuição para a quadra.
- Taxa de serviço do JOGA.
- Valor total a pagar.
- Meio de pagamento.
- Prazo limite.

A experiência deve ser simples. Não apresentar uma taxa individual que pareça maior do que realmente é por confundir o preço total da reserva com a contribuição de cada jogador. O sistema deverá calcular e apresentar o valor individual corretamente.

Não utilizar taxas ocultas ou modificar valores depois que o usuário abriu o pagamento.

A taxa inclui custo operacional, proteção contra cancelamento e provisão de cauda. O jogador não precisa ver os parâmetros internos, mas a explicação deve ser honesta: a taxa não é apenas “comissão”; ela também sustenta a devolução integral quando a reserva não se completa.

Quando a reserva não for elegível para pagamento integrado, a interface deve explicar o motivo de forma simples, sem sugerir que o jogador foi cobrado indevidamente.

Se a reserva for cancelada no fluxo de pagamento incompleto, todos os valores efetivamente pagos deverão ser devolvidos integralmente.

O aplicativo poderá mostrar o progresso agregado dos pagamentos, como “8 de 10 pagamentos confirmados”, sem expor valores ou dados financeiros individuais de outros participantes. Cada participante deverá ver o próprio estado e o prazo, não a situação financeira detalhada dos demais.

---

## 20. Clãs, amizades e comunidade

O JOGA não terá um chat global universal no escopo atual. A comunicação será organizada por contexto.

### 20.1 Lista de amigos

Os usuários poderão adicionar amigos, consultar conexões, convidá-los para lobbies e controlar bloqueios e notificações.

### 20.2 Clãs abertos e fechados — JOGA y CLÃ

Os clãs serão comunidades permanentes dentro do JOGA:

- **Abertos:** usuários poderão entrar diretamente, respeitando limite de membros e regras.
- **Fechados:** entrada por convite ou aprovação de administradores.

Cada clã poderá possuir nome, descrição, identidade visual, membros, administradores, chat permanente, convites e histórico de atividades.

O chat de clã será inicialmente baseado em texto e compartilhamento de referências internas do JOGA.

### 20.3 Troféus e ranking de clãs

Cada modalidade terá seu próprio ranking de clãs. Futebol e vôlei não serão somados em uma pontuação única na primeira versão.

O modelo inicial de troféus terá três componentes:

- **50% — resultados/vitórias competitivas validadas.**
- **30% — contribuição/desempenho competitivo dos membros.**
- **20% — participação em partidas competitivas válidas.**

A contribuição será calculada a partir de eventos competitivos confiáveis do backend, sem aceitar pontos enviados pelo cliente. A participação terá limites para evitar que volume artificial de partidas gere vantagem.

Para evitar que clãs grandes vençam apenas por terem mais integrantes, a pontuação considerará inicialmente os 10 melhores membros elegíveis de cada clã por modalidade. Regras de elegibilidade, permanência mínima no clã, normalização dos componentes e prevenção de partidas combinadas deverão ser versionadas e testadas.

Os pesos 50/30/20 constituem a fórmula-base aprovada para prototipação e balanceamento. O algoritmo final deverá ser validado com simulações antes de ser usado em ranking público.

O ranking poderá funcionar em temporadas de duração configurável, por exemplo 30 ou 60 dias. A duração definitiva ainda deverá ser definida. O histórico de temporadas será preservado.

Troféus de clã não são MMR individual. Compras futuras, assinaturas, publicidade, número bruto de membros e pagamento não concedem pontos competitivos.

### 20.4 Identidade visual, avatares e ausência de fotos de pessoas

O JOGA não terá fotos de pessoas no aplicativo: nem no perfil, nem no lobby, nem no chat ou no clã.

A identidade visual do jogador será um **avatar ilustrado gerado**, no estilo boneco, montado a partir de um catálogo fechado de peças — tom de pele, cabelo, barba, óculos, roupas, cores e acessórios. O usuário escolhe combinações válidas; não envia imagem, não desenha livremente e não insere texto no avatar.

Regras:

- O catálogo de peças e combinações é definido pelo produto, versionado e validado pelo backend; o cliente não inventa atributos.
- O avatar é escolhido no onboarding e pode ser editado depois, sempre dentro do catálogo vigente.
- O avatar é público e não contém dado pessoal, localização, telefone, nome real ou referência a terceiros.
- A identidade visual de clã segue a mesma regra: peças, cores e símbolos do catálogo fechado, sem upload de imagem.
- Nome de exibição e `#tag` continuam sendo texto sujeito a validação e moderação.
- Fotos são permitidas apenas para **quadras e estabelecimentos**, enviadas por organização autenticada, com revisão, sem pessoas identificáveis e com retenção controlada.
- Na Fase 12A, a revisão inicial é feita por `OWNER`/`ADMIN` da organização, com auditoria e motivo obrigatório na rejeição; a revisão independente, a denúncia de foto e a moderação de abuso entram na Fase 17.
- Documentos de KYC são privados, nunca exibidos no aplicativo e não se confundem com a política de mídia pública.
- Não há upload livre de imagem, áudio, vídeo ou arquivo em perfil, lobby ou chat no MVP.
- Avatares também podem ser usados para abuso — combinações ofensivas, assédio por identidade ou impersonação. Denúncias continuam existindo e a moderação pode restringir nome, avatar ou conta.
- A política reduz moderação de imagem, risco de exposição de menores, doxxing, sextorsão, catfishing e impersonação, além de diminuir custo de armazenamento e revisão.
- Qualquer mudança que permita foto de pessoa ou upload livre exige nova decisão em ADR e revisão de moderação, privacidade e retenção.

A decisão está registrada na ADR 0029.

---

## 21. Integridade competitiva e operacional

### 21.1 Separação de indicadores

O JOGA manterá separados:

- **MMR:** estimativa de habilidade competitiva por modalidade/formato.
- **Trust Factor esportivo:** sinais de confiabilidade relacionados ao comportamento em partidas e ao cumprimento de compromissos esportivos.
- **Confiabilidade de reservas do jogador:** histórico de confirmações, faltas, cancelamentos e inadimplência em reservas.
- **Confiabilidade comercial do estabelecimento:** histórico de aceitação, resposta, bloqueios, cancelamentos e cumprimento de reservas.
- **Troféus de clã:** pontuação coletiva baseada em resultados competitivos válidos.

Compras futuras, publicidade, assinaturas e pagamentos não poderão alterar MMR, elegibilidade competitiva de forma oculta ou troféus de clã.

### 21.2 Integridade das reservas

O sistema deverá evitar:

- Duplo bloqueio do mesmo espaço.
- Pagamento de vagas já substituídas.
- Dupla ocupação de uma vaga.
- Confirmação de reserva com pagamentos incompletos.
- Reativação automática de reserva cancelada por webhook tardio.
- Reembolso duplicado.
- Solicitação para uma quadra sem tempo operacional suficiente.
- Cobrança aberta antes do aceite e do bloqueio do estabelecimento.
- Confirmação de reserva sem bloqueio confirmado.

As operações críticas deverão ser transacionais e idempotentes, com constraints no banco de dados e verificação de autorização no servidor.

### 21.3 Confiabilidade dos jogadores

O novo sistema gera compromissos de duas partes:

- O jogador confirma que pretende participar.
- A quadra confirma que bloqueou o espaço.

O JOGA deverá preservar histórico dessas ações.

Pode haver usuários que confirmam participação repetidamente, mas não pagam depois. Uma falta isolada não deve gerar punição automática. A reincidência poderá ser usada como sinal de risco e confiabilidade de cumprimento de compromissos, de maneira proporcional e transparente.

Não misturar automaticamente esse indicador ao MMR. O jogador deverá ter acesso às regras e possibilidade de contestar medidas.

### 21.4 Confiabilidade dos estabelecimentos

O JOGA deverá registrar:

- Taxa de aceitação.
- Tempo médio de resposta.
- Cancelamentos após aceite.
- Problemas com disponibilidade.
- Descumprimento de bloqueios.
- Reincidência.

Essas informações poderão formar um indicador de confiabilidade comercial da quadra. Não punir automaticamente por uma ocorrência isolada. Considerar contexto, gravidade e reincidência.

O estabelecimento deverá ter acesso ao seu histórico e possibilidade de contestar informações incorretas.

### 21.5 Moderação de chats e denúncias de usuários

A moderação deverá abranger os chats de lobby e de clãs, com prioridade para automação e revisão humana apenas quando necessária.

Como o escopo inicial dos chats será limitado a texto e referências internas do JOGA, não haverá moderação de imagens, áudios ou vídeos enviados diretamente pelos usuários. Essa regra é reforçada pela seção 20.4: o aplicativo não exibe fotos de pessoas. Fotos de quadras e estabelecimentos seguem fluxo próprio, autenticado e moderado.

#### 21.5.1 Denúncia de perfil no lobby

Cada participante poderá denunciar outro jogador diretamente pelo perfil disponível no lobby.

O formulário deverá permitir selecionar categorias de comportamento, incluindo:

- Ofensas e insultos.
- Assédio e intimidação.
- Discurso de ódio ou discriminação.
- Atitude antidesportiva.
- Provocação ou comportamento abusivo.
- Spam e mensagens indesejadas.
- Tentativa de fraude ou manipulação de partida.
- Outras condutas inadequadas.

O usuário também poderá selecionar até cinco mensagens específicas relacionadas à denúncia.

A IA deverá analisar o contexto dessas mensagens e uma faixa limitada de mensagens próximas, respeitando o limite de contexto definido pelo sistema. A finalidade é evitar interpretações isoladas de frases que dependem do contexto da conversa.

A denúncia deverá registrar o autor, o denunciado, o lobby, as mensagens selecionadas, o contexto autorizado e o horário dos eventos.

#### 21.5.2 Moderação automatizada por IA

A IA será utilizada como primeira camada de moderação, auxiliando em:

- Classificação de denúncias.
- Identificação de ofensas, assédio e discriminação.
- Detecção de spam e mensagens repetitivas.
- Identificação de ameaças e comportamentos potencialmente perigosos.
- Agrupamento de denúncias relacionadas.
- Priorização de casos por gravidade e risco.
- Identificação de possíveis denúncias abusivas ou coordenadas.

A automação poderá aplicar medidas preventivas proporcionais e reversíveis, conforme regras previamente definidas, como ocultação temporária de conteúdo ou limitação de mensagens.

Suspensões permanentes e decisões graves deverão exigir critérios mais rigorosos e, quando necessário, revisão humana.

A IA não deverá ser tratada como autoridade infalível. Suas classificações deverão possuir níveis de confiança e possibilidade de contestação.

#### 21.5.3 Revisão humana

No estágio inicial, o próprio responsável pelo JOGA poderá atuar como moderador humano.

A revisão humana deverá ser reservada principalmente para:

- Casos graves.
- Denúncias com evidências conflitantes.
- Situações que envolvam risco à segurança de usuários.
- Recursos contra medidas automatizadas.
- Casos em que a IA não tenha confiança suficiente.
- Possíveis fraudes ou denúncias coordenadas.

O sistema deverá fornecer uma interface de análise com histórico, mensagens relevantes, evidências, classificação automatizada e ações recomendadas.

#### 21.5.4 Medidas e histórico de moderação

As medidas possíveis poderão incluir:

- Aviso ao usuário.
- Remoção ou ocultação de mensagens.
- Restrição temporária de envio de mensagens.
- Restrição de participação em lobbies.
- Suspensão temporária da conta.
- Suspensão permanente em casos graves ou reincidentes.

As medidas deverão ser proporcionais à gravidade e reincidência, com registro da justificativa e possibilidade de contestação.

Denúncias não deverão reduzir automaticamente o Trust Factor. O sistema deverá considerar a confiabilidade da denúncia e a existência de evidências antes de aplicar penalidades.

#### 21.5.5 Privacidade e retenção

O acesso às mensagens e evidências utilizadas na moderação deverá ser limitado às pessoas e processos autorizados.

A plataforma deverá armazenar apenas o contexto necessário para analisar a denúncia, respeitando políticas de retenção, privacidade e requisitos legais.

A automação deverá priorizar o processamento eficiente, evitando que toda conversa precise ser encaminhada continuamente para análise humana ou por IA.

### 21.6 Integridade financeira das reservas

A integridade do fluxo financeiro de reservas é tratada separadamente da integridade competitiva.

O sistema deverá evitar:

- Cobrança aberta antes do aceite e do bloqueio do estabelecimento.
- Reserva confirmada sem todos os pagamentos aprovados.
- Liberação para a quadra antes da confirmação da reserva e da realização da partida.
- Reembolso duplicado ou reembolso de valor principal contabilizado como perda.
- Estorno sem saldo não tratado como evento de cauda.
- Conciliação divergente entre PSP, ledger interno e reserva.

As regras de fraude de produtos não se aplicam às reservas. São riscos e fluxos diferentes.

---

## 22. Escopo futuro e exclusões atuais

Não fazem parte do escopo inicial:

- Comércio de produtos, conforme a seção 15 e o ADR 0022.
- Torneios organizados, chaves, fases de grupos, inscrições e premiações.
- Competições presenciais próprias.
- Gestão completa de academias e clubes, incluindo matrículas, mensalidades, catracas e frequência.
- Intermediação de profissionais individuais, como personal trainers, árbitros e fotógrafos.
- Aluguel de equipamentos com caução e fluxo completo de devolução.
- ERP completo ou gestão das vendas externas do estabelecimento.
- Chat global universal.
- Envio livre de mídia/arquivos em chats.
- Integrações genéricas com ERPs e pontos de venda no primeiro lançamento.
- Pagamento com cartão de crédito ou débito no fluxo inicial de reservas; Pix é o meio inicial.
- Carteira própria, custódia informal de valores ou processador de pagamentos próprio.
- Rastreamento contínuo de localização em segundo plano.

Os itens poderão ser reavaliados após validação do núcleo esportivo e do sistema de reservas, com decisão de produto e ADR próprios.

---

## 23. Roadmap conceitual

O roadmap abaixo representa uma visão de produto, não substitui a ordem técnica normativa de `PLANS.md`.

| Etapa | Objetivo |
|---|---|
| 1. Fundação do jogador | Identidade, perfil, modalidades e preferências |
| 2. Matchmaking | Fila única, disponibilidade, localização e formação de grupos |
| 3. Lobbies e ciclo de partidas | Horário fixo, participantes, confirmação de participação e ciclo de partida |
| 4. Competitivo e MMR | Resultados validados, MMR, histórico e Trust Factor inicial |
| 5. Integridade esportiva | Capitães, votação de resultados, divergências, disputas e prevenção de manipulação |
| 6. Comunicação e amizades | Chat de lobby, lista de amigos, convites e notificações |
| 7. Moderação | Denúncias de perfil, análise contextual por IA e revisão humana |
| 8. Descoberta de espaços | Espaços públicos e particulares, informações operacionais e compatibilidade |
| 9. Painel de gestão de quadras | Organizações, espaços, permissões, horários, exceções e histórico |
| 10. Onboarding e interface financeira | Cadastro do fornecedor e chave de repasse, agenda de recebíveis, contratos, comprovantes e contestação |
| 11. Solicitação e confirmação de reservas | Solicitação ao estabelecimento, aceite, recusa e compromisso condicional |
| 12. Bloqueio temporário e disponibilidade | Bloqueio do espaço específico, expiração e prevenção de sobreposição |
| 13. Pagamentos Pix e ingresso | PSP, cobrança por pacote e passe, webhooks, conciliação e repasse ao fornecedor |
| 14. Substituição, cancelamentos e reembolsos | Substituição dentro da janela, cancelamentos, reembolsos, MED e estados financeiros |
| 15. Clãs e rankings | Clãs abertos/fechados, chat e ranking competitivo por modalidade |
| 16. Moderação e Trust & Safety | Denúncias de perfil, análise contextual por IA e revisão humana |
| 17. Parcerias e publicidade | Estabelecimentos, patrocínios e publicidade contextual após audiência |
| 18. Expansões futuras | Somente após validação das condições e decisão de produto própria |

Essa sequência é uma proposta conceitual. A ordem técnica normativa está em `PLANS.md`; não assumir que o roadmap conceitual substitui dependências técnicas.

---

## 24. Princípios fundamentais

- **Acessibilidade:** praticar esportes não deve depender de possuir um grupo previamente organizado.
- **Justiça competitiva:** o balanceamento prioriza partidas equilibradas.
- **Proximidade:** deslocamentos e preferências geográficas são considerados.
- **Horário concreto:** cada lobby representa uma partida com data e horário definidos.
- **Confiabilidade:** resultados, reservas, bloqueios, pagamentos e reembolsos precisam de registros auditáveis.
- **Confiabilidade operacional:** prazos, compromissos e estados devem ser controlados pelo servidor e resistir a falhas de notificação, conexão e dispositivos desligados.
- **Transparência financeira:** o jogador deve saber quanto paga, por quê e em qual prazo; o estabelecimento deve saber quanto recebe e quando.
- **Privacidade:** localização e dados pessoais são minimizados e protegidos. Dados financeiros individuais não devem ser expostos a outros participantes.
- **Autonomia comercial:** estabelecimentos administram somente os dados e operações aos quais têm acesso.
- **Sustentabilidade:** monetização não deve prejudicar a experiência esportiva nem criar vantagens competitivas compradas.
- **Precificação sustentável:** a taxa deve cobrir custos e riscos reais, sem transformar ganhos de eficiência operacional em preço excessivo para o usuário.
- **Comunidade:** o produto deve criar razões reais para voltar, por meio de partidas, amigos e clãs.
- **Proporcionalidade:** uma ocorrência isolada de falha não deve gerar punição automática; decisões graves exigem contexto, evidência e possibilidade de contestação.
- **Expansão disciplinada:** novas frentes de produto só devem ser abertas quando houver demanda, viabilidade financeira e capacidade operacional comprovadas.

---

## 25. Visão de futuro

O JOGA pretende evoluir para uma plataforma na qual qualquer pessoa possa encontrar jogadores, organizar partidas, escolher espaços esportivos, solicitar e confirmar reservas, pagar individualmente e participar de comunidades.

O objetivo não é substituir clubes, arenas ou grupos existentes, mas conectar esses agentes a uma experiência esportiva mais organizada, acessível e financeiramente transparente.

---

## 26. Decisões aprovadas, parâmetros iniciais, propostas e pendências

### 26.1 Decisões aprovadas

1. A precificação usa a fórmula `TAXA = c·V + C_k + C_c·μ·S + p_t·V`, com `μ = (1 − q)/q` e `S = 1 + z·√(φ/μ)`.
2. O antigo coeficiente 1,8 é o fator de segurança de 95% para a variância dos cancelamentos em `q = 20%`; não é markup sobre o custo total.
3. O 1,8 não incide sobre `C_k`, não incide sobre custos + lucro e não é aplicado duas vezes.
4. O piso, o preço variável e o teto `α` de 15%–20% foram removidos.
5. O teto foi substituído por uma regra de elegibilidade: acima de 25% de taxa na faixa, a reserva paga não é oferecida.
6. A comissão `c·V` cobre custo fixo e lucro-alvo; `C_k` e `C_c` são componentes explícitos e separados.
7. O valor principal devolvido não é contabilizado como perda; o custo relevante é `C_c`.
8. O marketplace de produtos está fora do escopo inicial e não será especificado nem implementado nesta etapa (ADR 0022).
9. A monetização inicial se concentra em taxas de serviço sobre reservas de quadras, parcerias, patrocínios e publicidade contextual.
10. Funcionalidades essenciais de jogadores, matchmaking, partidas e comunidades continuam predominantemente gratuitas.
11. As reservas funcionam por solicitação ao estabelecimento, sem exigir integração com software externo.
12. O painel do estabelecimento é responsivo, voltado às operações do JOGA e não é um ERP.
13. O bloqueio temporário do espaço específico é obrigatório e confirmado pelo estabelecimento.
14. Existem três temporizadores independentes: confirmação de participação, resposta do estabelecimento e bloqueio/pagamento.
15. O prazo inicial de confirmação de participação é de 1 hora, controlado pelo backend.
16. O prazo inicial de resposta do estabelecimento é de cerca de 30 minutos de funcionamento, com prazo máximo em tempo corrido.
17. O prazo inicial de bloqueio e pagamento é de 60 minutos, configurável por estabelecimento, com buffer de 5 a 10 minutos.
18. Os prazos antigos de 24 horas e 2 horas para pagamento foram removidos.
19. Cada participante paga sua própria contribuição por Pix; não há um único pagador pelo grupo.
20. Todas as cobranças são abertas simultaneamente e têm o mesmo prazo.
21. A reserva é confirmada quando todos os participantes necessários pagam dentro do prazo; o aceite do estabelecimento é um compromisso condicional e não há segunda aprovação manual.
22. A substituição é permitida após o aceite do estabelecimento, dentro da janela original de pagamento, sem reiniciar o prazo nem prorrogar o bloqueio.
23. Se a reserva não se completa, todos os valores pagos são devolvidos integralmente, incluindo a contribuição da quadra e a taxa de serviço do JOGA.
24. As tarifas não recuperáveis do PSP são custos do JOGA, cobertos por `C_c`, e não são deduzidas do reembolso dos participantes.
25. O Pix é o meio de pagamento inicial; débito e crédito serão avaliados depois.
26. O backend controla todos os prazos; notificações e o relógio do dispositivo não são fonte oficial.
27. O JOGA não construirá carteira própria nem custódia financeira informal.
28. Se nenhum PSP atender ao fluxo de pagamentos individuais, split e liberação controlada, o lançamento do pagamento integrado deverá aguardar.
29. O **Inter PJ** é o PSP de produção; o Mercado Pago fica no protótipo e beta; o Pagar.me é reserva técnica e candidato do fluxo de reserva avulsa.
30. Um estabelecimento com recebedor em credenciamento não pode originar reserva paga; o KYC é portão de elegibilidade.
31. A quadra só recebe a liberação depois que tudo estiver confirmado, inclusive a realização da partida; a liberação automática após `N` horas e a janela de disputa dependem de definição.
32. A interface financeira do estabelecimento é escopo obrigatório quando houver split (Res. 264/349).
33. Denúncias e falhas isoladas não geram punição automática; confiabilidade é separada de MMR.
34. A taxa não deve ser reduzida automaticamente quando a conclusão melhorar; a revisão exige verificar se a margem cobre riscos reais.
35. O prazo padrão de relato de resultado é de **10 minutos**, controlado pelo backend e configurável por formato no futuro.
36. O resultado tem **três opções**: equipe A, equipe B ou empate esportivo, quando o formato permitir.
37. Não existe tolerância separada de “1–2 votos”: a regra é o limite de 50% sobre votos válidos — abaixo de 50% finaliza, exatamente 50% abre segunda rodada, acima de 50% abre disputa.
38. Votos ausentes ou anulados não entram no denominador e não significam concordância nem discordância.
39. O capitão da Fase 7 é provisório: maior número de partidas válidas concluídas (`FINALIZED`) e, em empate, UUID; sem critério de nível; seleção registrada e não retroativa.
40. A evidência da Fase 7 é apenas textual, privada e auditável; não há upload de arquivos.
41. A Fase 7 é backend-only e não implementa nem atualiza MMR.
42. A revisão humana da Fase 7 pode ser feita por CLI/script interno auditável, sem painel administrativo completo.
43. O quórum mínimo é `ceil(participantes_elegíveis / 2)` votos válidos; os elegíveis são congelados na abertura da primeira rodada e reutilizados na segunda.
44. O resultado avaliado é o de maior número de votos válidos (maioria simples/plurality), não maioria absoluta.
45. A segunda rodada dura 5 minutos, apresenta todas as alternativas permitidas pelo formato e não há terceira rodada.
46. A evidência textual tem limite de 2.000 caracteres e no máximo uma justificativa por participante por disputa.
47. A CLI de revisão exige `--operator` validado contra lista autorizada e `--reason` obrigatório.
48. Relatos e votos individuais são visíveis aos participantes; a contagem agregada e o resultado parcial só aparecem após o fechamento da rodada.
49. Futebol 5x5 permite empate esportivo; vôlei não permite na primeira versão.
50. O aplicativo não exibe fotos de pessoas; a identidade visual é um avatar ilustrado gerado a partir de catálogo fechado, sem upload livre. Fotos são restritas a quadras e estabelecimentos, enviadas por organização autenticada e moderadas.
51. O kit da partida é um requisito logístico do formato, assumido por participantes ou pelo responsável logístico; não é critério de capitão, elegibilidade, MMR ou Trust Factor automático, e descumprimento isolado não pune automaticamente.
52. Na Fase 12A, a revisão inicial de foto de quadra é feita por `OWNER`/`ADMIN` da organização, com auditoria e motivo obrigatório na rejeição; `OPERATOR` não revisa. A revisão independente e a denúncia de foto entram na Fase 17.
53. O vínculo entre perfil comercial e local descoberto (`organization_venues.venue_id`) é opcional e único, e só aceita local privado ativo; não concede autorização de reserva nem publica o estabelecimento automaticamente.

### 26.2 Parâmetros iniciais

- Confirmação de participação: 1 hora.
- Resposta do estabelecimento: cerca de 30 minutos de funcionamento, com prazo máximo em tempo corrido.
- Bloqueio e pagamento: 60 minutos, configurável por estabelecimento.
- Buffer de conciliação: 5 a 10 minutos.
- Comissão inicial de trabalho: 10% do valor da quadra.
- Nível de confiança: 95% (`z = 1,645`).
- Sobredispersão: `φ = 1,0`.
- Provisão de cauda: `p_t = 0,2%`.
- Limite operacional de elegibilidade: 25% do valor da quadra (referência).
- Valor mínimo de referência para a taxa ficar abaixo de 25% em `q = 20%`: cerca de R$ 100.
- Tarifa percentual de PSP adotada nas simulações: 0,90%.
- Meio de pagamento: Pix.
- Relato de resultado: 10 minutos.
- Segunda rodada de resultado: 5 minutos.
- Quórum mínimo de resultado: `ceil(elegíveis / 2)` votos válidos.
- Evidência textual: até 2.000 caracteres por participante por disputa.
- Quantidade de participantes do futebol 5x5: 10.
- Formato do vôlei: ainda a definir.
- Duração da partida: definida pelo formato esportivo, não pelo lobby.
- Equipamento: catálogo inicial por formato — futebol 5x5 e basquete 3x3: bola; vôlei de praia: rede e bola; tênis: bolas.
- Avatar: catálogo fechado de peças, sem upload de imagem.

### 26.3 Propostas em validação

1. Medir `q`, `C_k`, `C_c`, `τ` e `p_t` em piloto controlado antes de fixar a taxa.
2. Manter a taxa estável por ciclo, com variação máxima de ±10%.
3. Calcular `q` por modalidade e faixa de preço, não por quadra isolada.
4. Permitir apenas uma tentativa de substituição por vaga durante a janela de pagamento.
5. Redirecionar o lobby para outra quadra compatível em caso de recusa ou expiração, se houver tempo e alternativa.
6. Manter reserva de contingência equivalente a três meses de custos não recuperáveis no cenário de 20%, ou 10% da receita de taxas, o que for maior.
7. Divulgar o progresso agregado de pagamentos aos participantes, sem expor valores individuais de terceiros.
8. Criar um indicador de confiabilidade comercial do estabelecimento, com direito de contestação.
9. Criar um indicador de confiabilidade de reservas do jogador, separado do MMR e do Trust Factor esportivo.
10. Formalizar as perguntas ao Pagar.me antes de qualquer contrato.
11. Tratar a interface financeira do recebedor e o KYC como custo fixo coberto pela comissão.
12. Revisar a política de cancelamento após confirmação junto com a regra de liberação.
13. Avaliar, em modo sombra, uma provisão de fraude baseada na mediana de Trust Factor dos participantes, sem alterar a cobrança; hipótese registrada na ADR 0036.

### 26.4 Pendências

As questões abaixo continuam abertas. Este documento não as resolve por suposição.

1. PSP escolhido em contrato.
2. Tarifa Pix negociada e tarifas de split, transferência e saque.
3. Possibilidade de controlar a liberação dos repasses e o saque autônomo do estabelecimento.
4. Comportamento do estorno Pix com split na V5.
5. Responsabilidade e efeito do MED sem saldo.
6. Prazo final de resposta da quadra.
7. Duração configurável dos bloqueios.
8. Buffer exato para conciliação.
9. Tempo concedido a um substituto.
10. Limite definitivo de substituições.
11. Valor de `N` para liberação automática após a partida.
12. Janela de disputa antes da liberação.
13. Política de cancelamento depois da reserva confirmada.
14. Política para desistência individual após confirmação.
15. Valor definitivo de `c`.
16. Valores medidos de `q`, `C_k`, `C_c`, `τ` e `p_t`.
17. Limite operacional de elegibilidade por faixa de preço.
18. Reserva de contingência necessária.
19. Contratos comerciais com quadras.
20. Regras jurídicas e fiscais aplicáveis ao modelo de intermediação e à custódia.
21. Regra definitiva para recusa ou expiração da solicitação: cancelar o lobby ou tentar outra quadra.
22. Tratamento fiscal da taxa de serviço (ISS, retenções e município competente).
23. Termos de uso, política de cancelamento e direito de arrependimento aplicáveis ao consumidor.
24. Retenção de dados financeiros, comprovantes e histórico de reservas.
25. Revisar, na fase de LGPD, a política provisória de retenção do ADR 0024 para relatos, confirmações, evidências, decisões e contadores.
26. Configurar a lista de operadores autorizados da CLI (`JOGA_REVIEW_OPERATORS`).
27. Critérios e limites do indicador de confiabilidade de jogadores e estabelecimentos.
28. Periodicidade e amostra mínima da recalibração.
29. Metodologia de amortecimento para evitar oscilações bruscas de preço.
30. Estratégia de onboarding e cobrança por recebedor.
31. Catálogo definitivo de peças de avatar, limites de combinação e critérios de moderação de nome/avatar.
32. Processo de revisão, remoção e retenção de fotos de quadras, incluindo pessoas em segundo plano.
33. Catálogo definitivo de equipamento por formato e se o kit é obrigatório em partidas casuais e ranqueadas.
34. Consequências de descumprir um item assumido: limiar, contestação e efeito no Trust Factor.
35. Definir se o responsável logístico do kit é explícito ou apenas uma confirmação coletiva, e como isso se relaciona com o criador do lobby.
36. Provedor de storage de fotos de produção, criptografia, backup, retenção e limpeza de arquivos órfãos.
37. Revisão independente, denúncia e moderação de fotos de quadra na Fase 17.
38. UI mobile de descoberta de quadras e fotos.
39. Medir o poder preditivo de Trust Factor, mediana do grupo e outros sinais sobre MED/chargeback antes de qualquer preço dinâmico de fraude (ADR 0036).

### 26.5 O que este documento não decide

- Não escolhe PSP em definitivo.
- Não define preço final.
- Não define `c` definitivo.
- Não define `q`, `C_k`, `C_c`, `τ` ou `p_t` medidos.
- Não define `N` da liberação automática.
- Não define política de cancelamento após confirmação.
- Não define política de desistência individual.
- Não define prazo definitivo de retenção de relatos, confirmações, evidências e decisões; o ADR 0024 fixa uma política provisória.
- Não define a lista nominal de operadores autorizados da CLI.
- Não define contratos com estabelecimentos.
- Não afirma que o fluxo já está implementado.
- Não substitui `PLANS.md` como ordem normativa de execução.
- Não altera código, banco de dados ou infraestrutura.

---

## 27. Governança documental e próximos passos

Esta versão 3.3 atualiza a documentação conceitual, `GOALS.md`, `PLANS.md`, a documentação técnica e os documentos operacionais. A implementação backend-only da Fase 7 foi feita na mesma data, em alteração separada.

Documentos alinhados nesta revisão:

- `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md`: fórmula, fluxo financeiro, escopo sem marketplace, transparência e regras da Fase 7.
- `GOALS.md`: três pilares, sem comércio de produtos.
- `PLANS.md`: Fases 11–19 reorganizadas; Fase 7 detalhada com regras de resultado.
- `docs/JOGA_DOCUMENTACAO_TECNICA.md`: arquitetura, modelo de dados, contratos e testes sem marketplace; §10 com as regras da Fase 7.
- `docs/ADR/0021-politica-de-precificacao-e-fluxo-financeiro.md`: decisão de precificação e PSP.
- `docs/ADR/0022-remocao-do-marketplace-de-produtos-do-escopo.md`: decisão de escopo.
- `docs/ADR/0023-fase-7-resultados-e-disputas.md`: decisões da Fase 7, com implementação local registrada.
- `harness/build/phase-07-resultados-e-disputas.md`: plano e estado da implementação da fase.

Próximos passos recomendados, em ordem:

1. Revisar, commitar e mergear a documentação e a implementação local da Fase 7; revisar a retenção provisória do ADR 0024 e configurar os operadores da CLI.
2. Manter os testes de concorrência e migração com PostgreSQL real na CI e em ambiente descartável.
3. Em paralelo, obter resposta formal do Pagar.me sobre as 15 perguntas do ADR 0021 e comparar com o Inter.
4. Fazer revisão jurídica e fiscal do modelo de split, custódia, cancelamento, reembolso e retenção de valores.
5. Especificar o domínio de reservas, a máquina de estados, as constraints de bloqueio e os contratos HTTP/WebSocket.
6. Especificar o painel do estabelecimento, o onboarding/KYC e a interface financeira do recebedor.
7. Executar piloto controlado com poucos estabelecimentos e medir os dados da seção 18.12.
8. Somente depois disso, decidir o valor final de `c` e a expansão do pagamento integrado.
---

## Anexo A — Glossário mínimo

- **Solicitação:** pedido de reserva enviado ao estabelecimento, ainda sem confirmação.
- **Bloqueio temporário (hold):** reserva operacional temporária de um espaço específico, confirmada pelo estabelecimento, enquanto os pagamentos são concluídos.
- **Lobby:** espaço de organização de uma partida, com participantes, horário, modalidade e ações relacionadas.
- **Vaga:** posição individual de participante no lobby.
- **Contribuição para a quadra:** parte do valor da reserva que corresponde ao espaço, dividida entre os participantes.
- **Taxa de serviço do JOGA:** valor cobrado pela intermediação, calculado pela fórmula da seção 17.
- **Taxa de conclusão (`q`):** proporção de tentativas de reserva paga que efetivamente se confirmam e se realizam.
- **Cancelamento esperado (`μ`):** cancelamentos por reserva concluída, calculado como `(1 − q)/q`.
- **Fator de segurança (`S`):** proteção estatística para a variância dos cancelamentos.
- **Provisão de cauda (`p_t·V`):** reserva para MED, estorno sem saldo e disputas após liberação.
- **PSP:** provedor de serviços de pagamento.
- **Split:** divisão automática do valor recebido entre recebedores.
- **Recebedor (`recipient`):** conta do estabelecimento no PSP, com saldo próprio.
- **KYC:** verificação de identidade e cadastro do recebedor.
- **Liquidação:** momento em que o PSP libera o valor para o recebedor.
- **Repasse:** transferência do valor devido ao estabelecimento.
- **Conciliação:** comparação entre os estados internos do JOGA e os eventos do PSP.
- **Webhook:** notificação enviada pelo PSP ao backend sobre um evento de pagamento.
- **Idempotência:** propriedade que impede que o reprocessamento do mesmo evento duplique efeitos.
- **MED:** Mecanismo Especial de Devolução do Pix.
- **Pagamento tardio:** pagamento confirmado depois do prazo ou depois do cancelamento/substituição.
- **Reembolso:** devolução do valor pago ao participante.
- **Reserva confirmada:** reserva com bloqueio confirmado e todos os pagamentos necessários aprovados dentro do prazo.

---

## Anexo B — Resumo das mudanças em relação às versões anteriores

- O marketplace de produtos saiu do escopo inicial e deixou de ser um pilar do produto.
- Os quatro pilares foram substituídos por três pilares: competitividade, comunidade e infraestrutura esportiva/reservas, com camada transversal de confiança.
- O aplicativo deixou de listar compra de produtos, pedidos e marketplace.
- O painel de gestão deixou de tratar lojas, catálogo, estoque e vendas; passou a priorizar quadras, solicitações, bloqueios e reservas.
- O público-alvo deixou de incluir compradores e vendedores de produtos.
- Foi criado o fluxo de solicitação de reserva ao estabelecimento, com bloqueio temporário obrigatório.
- Foram definidos três temporizadores independentes: 1 hora de confirmação de participação; cerca de 30 minutos de funcionamento para resposta do estabelecimento; 60 minutos de bloqueio e pagamento, com buffer de 5 a 10 minutos.
- Foram removidos os prazos antigos de 24 horas e 2 horas para pagamento.
- O modelo de pagamento passou a ser Pix individual por participante, com cobranças simultâneas e mesmo prazo.
- Foi detalhado o fluxo de substituição de participantes.
- Foram detalhados cancelamentos, reembolsos, MED e estados financeiros.
- Na versão 3.0, a política de taxa passou a ser `1,8 × (custos + lucro)`.
- Na versão 3.1, o coeficiente 1,8 foi reposicionado como hipótese inicial de segurança.
- Na versão 3.2, o 1,8 foi reinterpretado como fator de segurança estatístico de 95% para cancelamentos em `q = 20%`.
- A fórmula passou a ser `TAXA = c·V + C_k + C_c·μ·S + p_t·V`, com `μ = (1 − q)/q` e `S = 1 + z·√(φ/μ)`.
- O piso, o preço variável e o teto `α` foram removidos; a proteção contra prejuízo passou a ser uma regra de elegibilidade.
- A comissão passou a ser a fonte explícita de custo fixo e lucro; `C_k` e `C_c` são componentes separados.
- Foi adotado o Pagar.me Flex como primeira opção de PSP, condicionado a confirmação contratual, com o Inter como alternativa centralizada.
- Foram incluídos o portão de KYC do recebedor, a liberação após a partida e a interface financeira obrigatória do estabelecimento.
- Foram incluídas simulações para 20%, 30%, 40%, 60%, 80% e 90% de conclusão, sensibilidade a `C_c` e `τ`, quadras baratas e custo fixo.
- Na versão 3.3, a Fase 7 passou a ter relato de resultado em 10 minutos, três resultados possíveis e regra de 50% sem tolerância separada.
- O capitão da Fase 7 passou a ser provisório, por partidas `FINALIZED` e UUID, sem critério de nível e sem alteração retroativa.
- A evidência de disputa passou a ser apenas textual e privada; upload de arquivos ficou para fase posterior.
- A revisão humana da Fase 7 passou a ser feita por CLI/script auditável, sem painel administrativo.
- Foi registrado que a Fase 7 é backend-only e não implementa nem atualiza MMR.
- Foram separadas decisões aprovadas, parâmetros iniciais, propostas e pendências.
- Na versão 3.4, o aplicativo passou a não exibir fotos de pessoas; a identidade visual é um avatar ilustrado gerado a partir de catálogo fechado, e fotos ficaram restritas a quadras e estabelecimentos.
- Foi criado o kit da partida como requisito logístico do formato, sem alterar o critério de capitão, a elegibilidade ou o MMR.
- Na versão 3.5, a Fase 12A passou a cobrir quadras, modalidades, agenda, preços, bloqueios e fotos de quadra; a revisão inicial de foto é feita por `OWNER`/`ADMIN`, com revisão independente na Fase 17.
- Na versão 3.6, a Fase 13A passou a implementar reservas com T1/T2/T3 independentes, hold transacional e substituição sem reiniciar T3; T2 usa tempo corrido e o pagamento é simulado apenas em ambiente local/teste.
- Na versão 3.7, o protótipo/beta fechado passou a usar Mercado Pago Checkout Transparente com Pix e custódia centralizada de teste; produção continua com Pagar.me e retenção controlada (ADR 0034).
- Na versão 3.8, a Fase 14A passou a usar Orders API do Mercado Pago, cobrança Pix por participante, webhook assinado, idempotência e ledger interno de teste.
- Na versão 3.9, foi registrada a hipótese de `p_t` dinâmico pela mediana de Trust Factor; o modelo atual mantém `p_t = 0,2%` fixo e a avaliação futura será em modo sombra (ADR 0036).
- Na versão 3.10, a Fase 14C passou a reembolsar integralmente cancelamentos/expirações do beta, reembolsar substituto e oferecer extrato/resumo financeiro com PSP simulado.
