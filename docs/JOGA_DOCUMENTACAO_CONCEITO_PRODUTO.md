# JOGA — Documentação de conceito e produto

**Versão:** 2.0  
**Status:** visão de produto atualizada  
**Data:** 2 de novembro de 2026  
**Nome principal:** JOGA  
**Nome de exibição pretendido na loja de aplicativos:** JOGA y JOGA

> Este documento consolida a visão de produto e as decisões conceituais atuais do JOGA. Ele substitui a nomenclatura anterior e versões conceituais incompatíveis. Não afirma que as funcionalidades descritas já estejam implementadas. A ordem normativa de desenvolvimento permanece em `PLANS.md`.

---

## 1. Visão geral

O **JOGA** é uma plataforma mobile para conectar pessoas que praticam ou desejam praticar esportes coletivos, organizar partidas presenciais, desenvolver comunidades esportivas e facilitar o acesso a espaços e produtos relacionados ao esporte.

O projeto parte de um problema recorrente: pessoas interessadas em jogar muitas vezes não possuem um grupo fixo, não encontram participantes suficientes, têm dificuldade para conciliar horários e localização ou acabam participando de partidas pouco equilibradas.

O JOGA busca centralizar essa experiência. O usuário informa seus esportes, preferências, disponibilidade e localização. A plataforma utiliza essas informações para aproximar jogadores, formar grupos compatíveis, organizar partidas e facilitar a escolha de locais.

A proposta também inclui uma camada social e comercial. Jogadores poderão manter contato por meio de lobbies e clãs, enquanto o aplicativo permitirá descobrir quadras, reservar espaços privados e comprar produtos esportivos. Lojas e estabelecimentos terão um painel web próprio para administrar exclusivamente as operações originadas pelo JOGA.

A visão de longo prazo é que o JOGA seja um ambiente recorrente para jogar, encontrar pessoas, participar de comunidades, descobrir espaços esportivos e consumir produtos relacionados às modalidades praticadas.

## 2. Problema identificado

A prática de esportes coletivos amadores enfrenta dificuldades que vão além da disponibilidade de quadras ou equipamentos:

- **Dificuldade para encontrar jogadores:** muitas pessoas não possuem um grupo fixo para praticar esportes.
- **Organização descentralizada:** partidas dependem de grupos de mensagens, contatos pessoais e convites informais.
- **Disponibilidade incompatível:** encontrar participantes que possam jogar no mesmo dia e horário é difícil.
- **Diferença de habilidade:** partidas podem ficar desequilibradas quando os participantes possuem níveis muito diferentes.
- **Distância geográfica:** jogadores podem precisar percorrer trajetos longos para encontrar partidas.
- **Falta de continuidade:** depois de uma partida, frequentemente não existe uma estrutura que incentive o grupo a voltar a jogar.
- **Dificuldade para encontrar espaços:** jogadores nem sempre sabem quais quadras existem, quanto custam ou quais horários estão disponíveis.
- **Fragmentação comercial:** lojas, arenas e jogadores utilizam canais distintos para anúncios, reservas, vendas e comunicação.

O JOGA pretende reduzir essa fragmentação, sem transformar o produto em um sistema genérico de gestão empresarial.

## 3. Proposta de solução

O JOGA combina quatro pilares conectados:

1. **Competitividade:** matchmaking, partidas casuais e ranqueadas, MMR e rankings individuais.
2. **Social:** lobbies, chat por lobby, lista de amigos, clãs e comunidades.
3. **Infraestrutura esportiva:** descoberta de locais públicos e privados, disponibilidade e reservas de quadras particulares.
4. **Comércio:** marketplace de produtos esportivos e ferramentas para estabelecimentos administrarem vendas e reservas originadas no JOGA.

A plataforma deve facilitar a jornada completa: encontrar pessoas, definir quando jogar, localizar um espaço adequado, realizar a partida e manter contato com a comunidade.

## 4. Estrutura de produtos e experiências

O JOGA terá duas experiências principais, conectadas à mesma plataforma e ao mesmo backend.

### 4.1 Aplicativo para jogadores e consumidores — JOGA y JOGA

O aplicativo Android/iOS será a experiência principal do consumidor. O nome de exibição pretendido na loja de aplicativos é **JOGA y JOGA**; a marca e o nome curto do produto continuam sendo **JOGA**.

O aplicativo reunirá:

- Cadastro, autenticação e perfil do jogador.
- Modalidades esportivas, preferências e disponibilidade.
- Matchmaking casual e ranqueado.
- Lobbies abertos e fechados.
- Chat de lobby e compartilhamento de conteúdo interno do JOGA.
- Lista de amigos e convites.
- Clãs abertos e fechados, com chat e ranking competitivo.
- Histórico, MMR e rankings individuais.
- Descoberta de quadras e espaços esportivos.
- Reserva e pagamento de quadras particulares, quando oferecidos pelo estabelecimento.
- Marketplace de produtos esportivos, com compra integrada.
- Acompanhamento de pedidos e reservas.

O Marketplace será uma área do aplicativo. **Não está previsto, no escopo inicial, um site público independente para consumidores.**

### 4.2 Site de gestão — JOGA y GESTÃO

O JOGA terá um painel web responsivo destinado exclusivamente a proprietários, gerentes e funcionários autorizados de lojas, arenas e outros estabelecimentos admitidos na plataforma.

O gerente não precisará utilizar o aplicativo de jogadores para administrar seu negócio. Ele poderá acessar o painel pelo computador ou navegador do celular.

O painel será voltado exclusivamente às operações originadas no JOGA. Não pretende substituir um ERP nem administrar automaticamente vendas presenciais, clientes externos, fornecedores ou toda a operação financeira do estabelecimento.

**Módulo de lojas — JOGA y LOJA:**

- Cadastro e administração da loja.
- Cadastro de produtos, descrições, imagens, preços e variantes.
- Definição da quantidade de estoque comprometida com o canal JOGA.
- Consulta de pedidos recebidos pelo JOGA.
- Atualização de preparação, disponibilidade para retirada e entrega pelo vendedor.
- Consulta de comissões, pagamentos, cancelamentos e solicitações de devolução.
- Configuração das condições de retirada e, quando oferecida, da entrega própria do vendedor.

**Módulo de quadras — JOGA y QUADRA:**

- Cadastro de estabelecimento, espaços e quadras.
- Definição de preços, horários e regras de reserva.
- Bloqueio de horários e registro de reservas originadas no JOGA.
- Administração de reservas, cancelamentos e disponibilidade.
- Consulta de pagamentos, comissões e relatórios básicos.

**Administração comercial:**

- Cadastro de proprietários, funcionários e permissões.
- Histórico das operações realizadas pelo JOGA.
- Relatórios básicos de vendas, reservas e faturamento da plataforma.
- Consulta de campanhas e ferramentas de publicidade, quando liberadas.

A proposta inicial é oferecer ferramentas básicas gratuitamente e monetizar principalmente as transações originadas pelo JOGA. Planos opcionais de gestão poderão ser avaliados no futuro.

### 4.3 Estrutura compartilhada

O aplicativo e o painel web utilizarão a mesma API, identidade central, banco de dados e infraestrutura comercial, com permissões diferentes conforme o papel do usuário e o estabelecimento ao qual está vinculado.

Uma mesma pessoa poderá ser jogador, proprietário ou funcionário. Entretanto, um gerente poderá utilizar o painel sem criar perfil esportivo ou participar do matchmaking.

O acesso a dados de estabelecimentos será isolado por organização e por permissão. Uma loja não poderá visualizar pedidos, estoque, reservas ou dados financeiros de outra.

### 4.4 Convenção de nomes

- **JOGA:** marca principal e nome curto do produto.
- **JOGA y JOGA:** nome de exibição pretendido do aplicativo.
- **JOGA y GESTÃO:** painel web dos estabelecimentos.
- **JOGA y LOJA:** módulo comercial de produtos e vendedores.
- **JOGA y QUADRA:** módulo comercial de quadras e reservas.
- **JOGA y CLÃ:** nome possível para a área de clãs, caso a nomenclatura seja utilizada na interface.

O uso de “y” é intencional e faz parte da identidade verbal da marca. Os nomes derivados devem continuar subordinados à marca JOGA, sem criar produtos tecnicamente independentes sem necessidade.

A disponibilidade jurídica da marca, dos nomes derivados e dos títulos nas lojas de aplicativos deve ser verificada antes do lançamento comercial.

## 5. Público-alvo

**Público primário:**

- Pessoas que querem jogar, mas não possuem um grupo fixo.
- Jogadores que desejam conhecer novas pessoas por meio do esporte.
- Grupos pequenos que precisam completar equipes.
- Pessoas que procuram partidas de nível técnico semelhante.
- Jogadores que desejam competir sem integrar clubes formais.
- Consumidores interessados em produtos e equipamentos esportivos.

**Público comercial:**

- Proprietários e administradores de quadras particulares.
- Arenas e complexos esportivos.
- Lojas de artigos esportivos.
- Vendedores de produtos esportivos aceitos na plataforma.

Academias, clubes com gestão completa de matrículas, prestadores individuais e organizadores de torneios poderão ser avaliados em etapas futuras, mas não são prioridade do escopo inicial.

## 6. Modalidades e formatos iniciais

O lançamento deve começar com modalidades de organização relativamente simples:

- **Futebol 5x5:** 10 jogadores no total, divididos em duas equipes de cinco.
- **Vôlei:** formato inicial a ser configurado e validado antes da implementação definitiva.

Cada modalidade/formato terá uma duração padrão definida pelo produto. A duração não será livremente escolhida por cada lobby: será determinada pela configuração oficial do formato esportivo.

Os parâmetros exatos de duração, composição do vôlei, tolerâncias de atraso e regras de encerramento deverão ser registrados antes da implementação do respectivo formato.

Outras modalidades poderão ser adicionadas depois, sem assumir que suas regras sejam iguais às do futebol ou do vôlei.

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

## 8. Lobbies e organização das partidas

O lobby é o espaço de organização de uma partida. Ele reúne participantes, horário, modalidade, preferências de local, chat e ações relacionadas à partida.

### 8.1 Origens e visibilidade

- **Lobby manual:** criado por um usuário, com data e horário fixos. Pode ser fechado, por convite, ou aberto para descoberta, conforme as regras de publicação definidas no produto.
- **Lobby do matchmaking:** criado pelo sistema após a formação de um grupo compatível. Não possui um dono com poder unilateral para decidir mudanças de quadra.

Origem e visibilidade são conceitos distintos: o sistema deve registrar quem/como criou o lobby e se ele é aberto ou fechado.

### 8.2 Chat do lobby

Cada lobby terá um chat próprio para os participantes autorizados. A primeira versão será focada em texto e compartilhamento de referências internas do JOGA, como partidas, quadras, produtos e convites.

Mensagens automáticas poderão informar entradas, saídas, votações, alterações de horário, reservas e outros eventos relevantes.

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

### 9.2 Confirmação do resultado

Ao final da partida, todos os jogadores deverão informar o resultado individualmente, selecionando a equipe vencedora ou indicando empate, quando permitido pelo formato.

Além disso, os capitães poderão informar o resultado de suas respectivas equipes. Essa confirmação será uma informação adicional para o sistema, não uma decisão absoluta.

Os votos dos participantes serão visíveis aos demais jogadores. Essa transparência é intencional: a expectativa é reduzir votos aleatórios ou incorretos por meio da responsabilidade social entre os participantes.

O prazo de votação será limitado, configurável entre 5 e 10 minutos após o encerramento da partida.

Jogadores que não votarem dentro do prazo serão registrados como votos anulados, e não como votos favoráveis a qualquer resultado.

### 9.3 Divergências e validação

O sistema comparará os resultados informados pelos participantes e as confirmações dos capitães.

Pequenas divergências, como um ou dois votos isolados, não deverão interromper automaticamente a validação. O resultado majoritário poderá ser aceito quando a divergência estiver dentro da tolerância definida para a modalidade e a quantidade de participantes.

Quando mais de 50% dos votos válidos divergirem do resultado predominante, a partida entrará em disputa.

A quantidade de votos anulados será registrada separadamente e não deverá ser interpretada automaticamente como concordância ou discordância.

A disputa será uma medida de proteção, não um mecanismo para anular partidas automaticamente. A anulação deverá ser considerada apenas como última alternativa, depois de avaliadas as evidências disponíveis.

### 9.4 Desempate de resultados e análise de confiabilidade

Quando a primeira votação terminar exatamente em 50% para cada resultado, o JOGA solicitará uma segunda confirmação a todos os participantes.

Os jogadores poderão confirmar ou corrigir suas respostas anteriores. O histórico da primeira votação será preservado para auditoria.

Se a segunda votação continuar exatamente empatada, a partida entrará em uma análise interna e invisível de confiabilidade.

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
- Outras evidências disponíveis e pertinentes.

A primeira análise poderá ser automatizada por regras de consistência e mecanismos de detecção de comportamento suspeito.

Casos inconclusivos ou com indícios relevantes de fraude poderão ser encaminhados para revisão humana.

As decisões possíveis incluem:

- Confirmar o resultado predominante.
- Solicitar informações adicionais.
- Corrigir o resultado quando houver evidência suficiente.
- Aplicar medidas de integridade quando houver fraude comprovada.
- Anular a partida somente quando não houver alternativa confiável.

Toda decisão deverá ser registrada e possuir justificativa auditável.

### 9.6 Integridade do sistema de resultados

O sistema deverá evitar que usuários manipulem resultados por meio de votos coordenados, contas falsas ou denúncias abusivas.

O MMR poderá reduzir a vantagem de combinações artificiais de resultados ao longo do tempo, mas não será considerado proteção suficiente contra fraude.

O JOGA deverá manter mecanismos independentes de detecção de padrões suspeitos, sem presumir que o balanceamento competitivo elimina sozinho o problema.

Resultados não confirmados ou em disputa não podem alterar o MMR. A plataforma deverá manter histórico auditável dos relatos originais e das decisões finais.

## 10. Locais e infraestrutura esportiva

O JOGA contemplará:

**Espaços públicos:** quadras e espaços de acesso público. O aplicativo poderá ajudar a descobrir e combinar encontros nesses locais. A indicação de um espaço público não representa, por si só, garantia de disponibilidade ou direito de reserva. Só haverá reserva formal se existir autorização e integração operacional com o responsável pelo espaço.

**Espaços privados:** quadras particulares, arenas e complexos esportivos. O estabelecimento poderá cadastrar espaços, preços, horários e regras. O usuário poderá consultar disponibilidade e reservar/pagar pelo aplicativo quando a reserva estiver habilitada.

A preferência de espaço público/particular acompanha a entrada na fila e o lobby. A troca de local deve respeitar a categoria permitida.

## 11. Marketplace de produtos

O aplicativo terá um marketplace especializado em produtos esportivos, inicialmente com foco em artigos relacionados às modalidades suportadas.

Categorias possíveis incluem bolas, chuteiras, uniformes, meias, acessórios e equipamentos esportivos.

### 11.1 Estoque comprometido com o canal JOGA

A quantidade que o vendedor publica no JOGA será estoque alocado e comprometido para vendas realizadas pelo JOGA. O vendedor não deverá vender essas mesmas unidades por outro canal sem atualizar previamente a quantidade disponível no JOGA.

O produto continua pertencendo ao vendedor até a conclusão da venda, mas a quantidade anunciada fica comprometida com a operação do marketplace.

O sistema controlará disponibilidade, reservas temporárias durante o checkout, vendas confirmadas e liberações após falha ou expiração do pagamento. O histórico de movimentações deverá ser auditável.

### 11.2 Retirada e entrega pelo vendedor

O JOGA não terá logística própria e não contratará transportadoras no escopo atual.

As opções comerciais serão:

- **Retirada:** o comprador paga no aplicativo e retira o pedido no estabelecimento ou no local indicado pelo vendedor.
- **Entrega pelo vendedor:** o próprio vendedor organiza e executa a entrega, definindo regiões atendidas, preço, prazo e condições. A execução e o cumprimento da entrega ficam sob responsabilidade do vendedor, sem que isso elimine as obrigações legais que possam caber à plataforma.

O JOGA não fará cotação de frete, emissão de etiqueta, contratação de transportadora, pagamento de transportadora ou rastreamento logístico próprio no escopo atual.

### 11.3 Código de confirmação de recebimento

Para retirada e entrega pelo vendedor, o JOGA poderá gerar um código único de confirmação. O código ficará disponível ao comprador e será informado ao vendedor/entregador somente quando o produto for efetivamente entregue ao consumidor.

O backend validará o código, limitará tentativas, controlará expiração e impedirá reutilização. O código confirma a entrega física registrada, mas não comprova que o produto estava correto, sem defeitos ou de acordo com o anúncio. Ele não representa renúncia a direitos do consumidor.

### 11.4 Compras e aluguel

A compra de produtos integra o escopo comercial inicial, com limites operacionais definidos acima. O aluguel de equipamentos é uma possibilidade futura, pois exige controle de períodos, disponibilidade, retirada, devolução, atraso, danos e eventual caução.

## 12. Pagamentos, cancelamentos e devoluções

O JOGA utilizará um provedor de pagamentos apropriado para marketplace, com recursos compatíveis com cadastro de vendedores, split quando disponível, webhooks, estornos, chargebacks e conciliação.

O JOGA não construirá processador próprio nem carteira custodial. O status financeiro oficial deverá ser confirmado por eventos autenticados do provedor, nunca apenas pelo retorno visual do aplicativo.

O painel e o aplicativo deverão permitir registrar cancelamentos, solicitações de devolução, análise, instruções de retorno, recebimento e reembolso. A operação logística de devolução será conduzida pelo vendedor, mas o sistema deverá registrar os eventos e respeitar a legislação aplicável. O direito de arrependimento em compras à distância e os custos de logística reversa não podem ser afastados por termos da plataforma.

Se o vendedor não conseguir cumprir o pedido, o consumidor deverá receber uma solução adequada e, quando o cancelamento for cabível, reembolso integral dos valores pagos, inclusive valores de entrega cobrados pelo vendedor.

## 13. Clãs, amizades e comunidade

O JOGA não terá um chat global universal no escopo atual. A comunicação será organizada por contexto.

### 13.1 Lista de amigos

Os usuários poderão adicionar amigos, consultar conexões, convidá-los para lobbies e controlar bloqueios e notificações.

### 13.2 Clãs abertos e fechados — JOGA y CLÃ

Os clãs serão comunidades permanentes dentro do JOGA:

- **Abertos:** usuários poderão entrar diretamente, respeitando limite de membros e regras.
- **Fechados:** entrada por convite ou aprovação de administradores.

Cada clã poderá possuir nome, descrição, identidade visual, membros, administradores, chat permanente, convites e histórico de atividades.

O chat de clã será inicialmente baseado em texto e compartilhamento de referências internas do JOGA.

### 13.3 Troféus e ranking de clãs

Cada modalidade terá seu próprio ranking de clãs. Futebol e vôlei não serão somados em uma pontuação única na primeira versão.

O modelo inicial de troféus terá três componentes:

- **50% — resultados/vitórias competitivas validadas.**
- **30% — contribuição/desempenho competitivo dos membros.**
- **20% — participação em partidas competitivas válidas.**

A contribuição será calculada a partir de eventos competitivos confiáveis do backend, sem aceitar pontos enviados pelo cliente. A participação terá limites para evitar que volume artificial de partidas gere vantagem.

Para evitar que clãs grandes vençam apenas por terem mais integrantes, a pontuação considerará inicialmente os 10 melhores membros elegíveis de cada clã por modalidade. Regras de elegibilidade, permanência mínima no clã, normalização dos componentes e prevenção de partidas combinadas deverão ser versionadas e testadas.

Os pesos 50/30/20 constituem a fórmula-base aprovada para prototipação e balanceamento. O algoritmo final deverá ser validado com simulações antes de ser usado em ranking público.

O ranking poderá funcionar em temporadas de duração configurável, por exemplo 30 ou 60 dias. A duração definitiva ainda deverá ser definida. O histórico de temporadas será preservado.

Troféus de clã não são MMR individual. Compras, assinaturas, publicidade, número bruto de membros e pagamento não concedem pontos competitivos.

## 14. Publicidade e monetização

O modelo de receita prevê principalmente:

1. **Comissão por reserva:** sobre reservas de quadras originadas e concluídas pelo JOGA.
2. **Comissão por venda:** sobre produtos vendidos pelo marketplace.
3. **Publicidade:** produtos patrocinados, lojas em destaque, quadras em destaque e campanhas de marcas.

A gestão básica deverá começar gratuita ou sem mensalidade obrigatória, reduzindo a barreira de entrada dos estabelecimentos. Planos opcionais com recursos avançados poderão ser avaliados depois da validação comercial.

A publicidade deverá ser identificada como patrocinada. A posição paga não poderá alterar o MMR, o Trust Factor, a composição do matchmaking ou a justiça dos rankings. Recomendações patrocinadas deverão respeitar filtros e restrições relevantes do usuário.

A publicidade avançada depende de audiência e volume de uso. Não deve ser tratada como receita garantida antes de existir tráfego suficiente.

## 15. Integridade competitiva e comercial

O JOGA manterá separados:

- **MMR:** estimativa de habilidade competitiva por modalidade/formato.
- **Trust Factor esportivo:** sinais de confiabilidade relacionados ao comportamento em partidas e ao cumprimento de compromissos.
- **Reputação comercial:** avaliações e histórico de cumprimento de pedidos/reservas por estabelecimentos.
- **Troféus de clã:** pontuação coletiva baseada em resultados competitivos válidos.

Compras, publicidade, assinaturas e pagamentos não poderão alterar MMR, elegibilidade competitiva de forma oculta ou troféus de clã.

## 15.1 Prevenção de fraudes comerciais

O JOGA deverá proteger compradores e vendedores contra fraudes, tanto durante a compra quanto após a confirmação do pedido.

Os principais riscos considerados incluem:

- Comprador alegar falsamente que não recebeu um produto.
- Vendedor registrar entrega que não aconteceu.
- Comprador utilizar comprovantes falsos.
- Vendedor anunciar produtos inexistentes ou diferentes dos entregues.
- Tentativas de obter reembolso indevido.
- Uso de contas falsas ou múltiplas contas para manipular avaliações e transações.
- Acordos entre comprador e vendedor para explorar o sistema de pagamentos ou reembolsos.

O sistema deverá manter registros auditáveis de pedidos, pagamentos, alterações de status, mensagens, códigos de recebimento e solicitações de suporte.

O código de confirmação de recebimento será uma evidência operacional, mas não será considerado prova absoluta de que o produto estava correto ou sem defeitos.

### 15.2 Denúncia de transações

O comprador e o vendedor poderão denunciar problemas relacionados a uma transação.

O formulário de denúncia deverá permitir:

- Selecionar o tipo de problema.
- Descrever detalhadamente o ocorrido.
- Anexar até três imagens como evidência.
- Vincular automaticamente a denúncia ao pedido correspondente.

As imagens e mensagens deverão possuir limites de tamanho e formatos permitidos, além de controles de segurança.

A IA poderá auxiliar na classificação da denúncia, identificação de inconsistências e priorização de casos. Ela não deverá realizar decisões irreversíveis de reembolso ou penalização apenas com base em uma classificação automatizada.

Casos com indícios relevantes de fraude, evidências conflitantes ou consequências financeiras significativas poderão ser encaminhados para revisão humana.

### 15.3 Comunicação entre comprador e vendedor

O JOGA deverá oferecer comunicação direta entre comprador e loja durante o processo comercial.

Além do contato relacionado ao pedido, haverá um espaço separado para negociação e propostas, permitindo que o comprador converse com a loja sobre condições do produto, defeitos identificados, alternativas ou possíveis soluções.

Essa comunicação deverá permanecer vinculada ao contexto comercial correspondente, com histórico preservado para consulta em eventuais disputas.

O recurso não deverá permitir que a conversa seja utilizada para contornar pagamentos ou controles de segurança da plataforma.

### 15.4 Decisão de disputas comerciais

As disputas comerciais deverão seguir um fluxo de análise progressiva:

1. Coleta automática de dados do pedido, pagamento, mensagens e evidências.
2. Classificação inicial e identificação de inconsistências por regras e IA.
3. Tentativa de resolução entre comprador e vendedor, quando apropriado.
4. Encaminhamento de casos complexos ou suspeitos para revisão humana.
5. Registro da decisão, justificativa e ações executadas.

A anulação, o cancelamento ou o reembolso deverão respeitar as condições comerciais e a legislação aplicável.

O sistema deverá evitar tanto fraudes de compradores quanto práticas abusivas de vendedores. Nenhuma das partes deverá ser considerada culpada automaticamente apenas por abrir uma denúncia.

## 15.5 Moderação de chats e denúncias de usuários

A moderação deverá abranger os chats de lobby e de clãs, com prioridade para automação e revisão humana apenas quando necessária.

Como o escopo inicial dos chats será limitado a texto e referências internas do JOGA, não haverá moderação de imagens, áudios ou vídeos enviados diretamente pelos usuários.

### 15.5.1 Denúncia de perfil no lobby

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

### 15.5.2 Moderação automatizada por IA

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

### 15.5.3 Revisão humana

No estágio inicial, o próprio responsável pelo JOGA poderá atuar como moderador humano.

A revisão humana deverá ser reservada principalmente para:

- Casos graves.
- Denúncias com evidências conflitantes.
- Situações que envolvam risco à segurança de usuários.
- Recursos contra medidas automatizadas.
- Casos em que a IA não tenha confiança suficiente.
- Possíveis fraudes ou denúncias coordenadas.

O sistema deverá fornecer uma interface de análise com histórico, mensagens relevantes, evidências, classificação automatizada e ações recomendadas.

### 15.5.4 Medidas e histórico de moderação

As medidas possíveis poderão incluir:

- Aviso ao usuário.
- Remoção ou ocultação de mensagens.
- Restrição temporária de envio de mensagens.
- Restrição de participação em lobbies.
- Suspensão temporária da conta.
- Suspensão permanente em casos graves ou reincidentes.

As medidas deverão ser proporcionais à gravidade e reincidência, com registro da justificativa e possibilidade de contestação.

Denúncias não deverão reduzir automaticamente o Trust Factor. O sistema deverá considerar a confiabilidade da denúncia e a existência de evidências antes de aplicar penalidades.

### 15.5.5 Privacidade e retenção

O acesso às mensagens e evidências utilizadas na moderação deverá ser limitado às pessoas e processos autorizados.

A plataforma deverá armazenar apenas o contexto necessário para analisar a denúncia, respeitando políticas de retenção, privacidade e requisitos legais.

A automação deverá priorizar o processamento eficiente, evitando que toda conversa precise ser encaminhada continuamente para análise humana ou por IA.

## 16. Escopo futuro e exclusões atuais

Não fazem parte do escopo inicial:

- Torneios organizados, chaves, fases de grupos, inscrições e premiações.
- Competições presenciais próprias.
- Gestão completa de academias e clubes, incluindo matrículas, mensalidades, catracas e frequência.
- Marketplace de profissionais individuais, como personal trainers, árbitros e fotógrafos.
- Logística própria, cálculo de frete, contratação de transportadoras, geração de etiquetas e rastreamento centralizado.
- Aluguel de equipamentos com caução e fluxo completo de devolução.
- ERP completo ou gestão das vendas externas do estabelecimento.
- Chat global universal.
- Envio livre de mídia/arquivos em chats.
- Integrações genéricas com ERPs e pontos de venda no primeiro lançamento.

Esses itens poderão ser reavaliados após validação do núcleo esportivo e comercial.

## 17. Roadmap conceitual

O roadmap abaixo representa uma visão de produto, não substitui a ordem técnica normativa de `PLANS.md`.

| Etapa | Objetivo |
|---|---|
| 1. Fundação do jogador | Identidade, perfil, modalidades e preferências |
| 2. Matchmaking | Fila única, disponibilidade, localização e formação de grupos |
| 3. Lobbies e partidas | Horário fixo, participantes, confirmações e ciclo de partida |
| 4. Competitivo | Resultados validados, MMR, histórico e Trust Factor inicial |
| 5. Integridade esportiva | Capitães, votação de resultados, detecção de divergências, disputas e prevenção de manipulação |
| 6. Comunicação | Chat de lobby, lista de amigos e convites |
| 7. Moderação | Denúncias de perfil, seleção de mensagens, análise contextual por IA e revisão humana |
| 8. Quadras | Cadastro, descoberta, disponibilidade e reserva de espaços privados |
| 9. Gestão web | Organizações, lojas, quadras e permissões comerciais |
| 10. Marketplace | Produtos, estoque comprometido, pedidos, pagamentos, retirada e entrega pelo vendedor |
| 11. Integridade comercial | Denúncias de pedidos, evidências, comunicação comprador-vendedor e análise de fraude |
| 12. Clãs | Clãs abertos/fechados, chat e ranking competitivo por modalidade |
| 13. Publicidade | Produtos e estabelecimentos patrocinados após existir audiência |
| 14. Expansões | Aluguel de equipamentos, academias, torneios e outros serviços |

## 18. Princípios fundamentais

- **Acessibilidade:** praticar esportes não deve depender de possuir um grupo previamente organizado.
- **Justiça competitiva:** o balanceamento prioriza partidas equilibradas.
- **Proximidade:** deslocamentos e preferências geográficas são considerados.
- **Horário concreto:** cada lobby representa uma partida com data e horário definidos.
- **Confiabilidade:** resultados, reservas, pedidos e entregas precisam de registros auditáveis.
- **Privacidade:** localização e dados pessoais são minimizados e protegidos.
- **Autonomia comercial:** estabelecimentos administram somente os dados e operações aos quais têm acesso.
- **Sustentabilidade:** monetização não deve prejudicar a experiência esportiva.
- **Comunidade:** o produto deve criar razões reais para voltar, por meio de partidas, amigos e clãs.

## 19. Visão de futuro

O JOGA pretende evoluir para uma plataforma na qual qualquer pessoa possa encontrar jogadores, organizar partidas, escolher espaços esportivos, comprar equipamentos e participar de comunidades.

O objetivo não é substituir clubes, arenas, lojas ou grupos existentes, mas conectar esses agentes a uma experiência esportiva mais organizada e acessível.
