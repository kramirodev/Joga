# ADR 0045 — Estatísticas, leitura competitiva e inteligência de rede

- **Status:** Aprovado como direção de produto; não implementado.
- **Data:** 2026-11-12
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0025 (MMR, rankings e Trust Factor), ADR 0042 (ingresso e passe), ADR 0043 (temporada, passe e customização), ADR 0044 (clãs no MVP).
- **Esclarece:** ADR 0043 §7 e §10. **Não altera a ADR 0025.**

## Contexto

A ADR 0043 §7 definiu as estatísticas essenciais e as do passe. A §10 definiu a inteligência de rede. Faltava explicitar três pontos:

1. **O que significa "MMR" nas estatísticas?** A ADR 0025 mantém o rating bruto oculto; a ADR 0043 fala em "MMR atual" e "evolução do MMR".
2. **O que exatamente o assinante vê sobre a rede?** Horário e dia de maior atividade, quadras mais usadas e quadras onde acontecem partidas mais fortes — para decidir onde e quando competir mais.
3. **Como evitar que esse painel vire identificação de pessoas, filtro de matchmaking ou profecia autorrealizável?**

A decisão é a **Leitura A**: "MMR" nas estatísticas é a **leitura visível** — divisão, progresso e posição —, não o rating bruto. O rating bruto, o `RD` e a volatilidade continuam ocultos, conforme a ADR 0025. A inteligência de rede é **descoberta**, não controle.

## Decisão

### 1. Leitura competitiva (free)

1. **Essencial e livre:** divisão, progresso, posição, partidas jogadas, vitórias/empates/derrotas, taxa de presença, streak e sequência de temporadas.
2. "MMR atual" na ADR 0043 é lido como **divisão + progresso + posição**. O número bruto do rating não é exibido.
3. `RD`, volatilidade, fórmula e parâmetros internos nunca são exibidos.
4. Sem isso, o jogador não entende as consequências das próprias ações. É requisito de confiança, não perk.
5. A taxa de presença é histórica e pessoal. **Não é o Trust Factor** e não expõe o score interno.

### 2. Estatísticas do passe

1. **Evolução da divisão/progresso** em gráfico, por formato, com janelas de 7 dias, 30 dias e temporada. O gráfico não mostra o rating bruto.
2. **Histórico por quadra:** partidas, V/E/D, variação de divisão/progresso, último jogo, formatos e horário mais frequente.
3. **Passaporte de quadras:** quadras visitadas, primeira visita, cidades/regiões e progresso de descoberta.
4. **Horários e formatos mais jogados:** mapa de calor pessoal por dia × faixa horária e distribuição por formato.
5. **Retrospectiva da temporada:** snapshot de fechamento com partidas, V/E/D, melhor streak, divisão, quadras novas, horário e formato favoritos.
6. Quando a amostra for pequena, o histórico por quadra mostra **"amostra pequena"** em vez de aproveitamento. Não se tiram conclusões de uma ou duas partidas.

### 3. Inteligência de rede (dados do próprio app)

1. **Free:** lista de quadras mais usadas e os próprios horários.
2. **Passe:** mapa de calor semanal da rede (dia × faixa horária), densidade competitiva por quadra, ocupação e tendência.
3. **Densidade competitiva** é a resposta a "onde acontecem partidas de maior nível competitivo" / "onde o jogo é mais forte". Exibida em **faixas** — recreativa, intermediária, alta — nunca em MMR médio, MMR absoluto, lista de jogadores ou número de pessoas identificáveis. O cálculo interno pode usar o MMR agregado das partidas; o que nunca aparece é o número.
4. **Amostra mínima:** nenhuma célula (quadra × período, ou quadra × faixa horária) aparece com menos de **20 partidas concluídas** no período, com janela móvel inicial de **30 dias**. Abaixo disso, a célula é ocultada ou agrupada. Valores iniciais, calibráveis no piloto.
5. **Agregado, nunca individual:** sem nome, sem perfil, sem "quem joga lá", sem dado de adversário.
6. **Defasagem:** atualização **diária**; nunca tempo real. Tempo real é rastreamento e não é necessário para decidir onde jogar.
7. **Não é filtro de matchmaking:** o painel informa onde e quando jogar; não restringe a busca, não permite selecionar partidas por nível e não altera a composição das partidas.
8. **Equilíbrio de fluxo:** mostrar também os **horários com mais vaga**. O mapa de pico atrai; o mapa de disponibilidade distribui. O produto não deve induzir todo mundo ao mesmo horário.
9. **Não exibir:** taxa de cancelamento por quadra, MMR absoluto de qualquer pessoa, média de MMR por quadra e dados de adversário antes da partida.
10. **B2B:** o mesmo painel, na visão do estabelecimento, mostra ocupação, horário morto e perfil agregado do público. É insumo do painel de gestão, sem dado pessoal e sem custo adicional de coleta.

### 4. Fontes de dados e governança

1. As estatísticas são **projeções de dados já existentes**: partidas, participantes, resultados, `rating_events`, presença, quadras e reservas.
2. Não há nova coleta, rastreamento contínuo, histórico de GPS ou telemetria de evento de jogo.
3. Só entram partidas concluídas com presença confirmada e resultados confirmados. Partidas em disputa, anuladas ou canceladas não contam para V/E/D nem para densidade competitiva.
4. O acesso é autorizado no servidor por titular e por plano. Nenhum endpoint retorna dados de outro jogador.
5. A agregação e a amostra mínima existem para impedir reidentificação em quadras pequenas.
6. A retenção segue as políticas existentes. A exportação LGPD é livre.

## Consequências

- A ADR 0025 permanece válida: o MMR bruto continua oculto; a leitura é por divisão, progresso e posição.
- O contrato de `GET /api/v1/ratings/me` não muda. As estatísticas do passe usam projeções sobre `rating_events` para reconstruir a evolução da divisão/progresso, sem expor o número.
- O mobile ganha a área de estatísticas e o painel de rede.
- O painel do estabelecimento ganha a visão B2B de ocupação e horário morto.
- Nada disso altera matchmaking, MMR, Trust Factor, ranking ou troféus por pagamento.
- Nenhuma fase comercial é aberta por esta ADR. A implementação entra na Fase 14D.

## O que esta ADR não decide

- A fórmula ou os parâmetros do MMR, que continuam na ADR 0025.
- A exibição do MMR bruto, que continua proibida.
- O preço do passe ou dos pacotes, que continua na ADR 0042.
- O catálogo cosmético, que continua na ADR 0043 e em `docs/ESPECIFICACAO_TEMPORADA_E_CATALOGO.md`.
- O preço e o acesso comercial do painel B2B.

## Pendências

1. Calibrar a amostra mínima (20 partidas) e o período (30 dias) com dados do piloto.
2. Definir as faixas e os rótulos de densidade competitiva e ocupação (3 a 5 níveis).
3. Definir o que acontece com as estatísticas avançadas quando o passe termina: o dado continua do jogador; a leitura avançada pode ser bloqueada.
4. Definir o formato da retrospectiva e as regras de compartilhamento.
5. Definir a regra exata de "sequência de temporadas".
6. Definir o acesso e o preço do painel B2B.
7. Definir a comunicação de "onde o jogo é mais forte" para não parecer filtro de nível.
