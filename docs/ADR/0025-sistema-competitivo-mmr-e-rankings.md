# ADR 0025 — Sistema competitivo: Glicko-2 adaptado, ranking e Trust Factor

- **Status:** Aprovado em 2026-11-06; 8A, 8B e 8C implementados.
- **Data:** 2026-11-06
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `PLANS.md` Fase 8; `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §19–21; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §11; ADR 0008; ADR 0023; `harness/build/phase-08-sistema-competitivo.md`.

## Contexto

A Fase 7 encerrou o ciclo de resultado, mas nenhum rating é aplicado. A Fase 8 precisa transformar partidas ranqueadas `FINALIZED` em MMR auditável, sem aceitar resultado ou métricas do cliente, sem misturar Trust Factor com habilidade e sem expor números internos que incentivem manipulação.

O produto também precisa de ranking e de uma experiência mobile motivadora, mas o MMR bruto deve permanecer oculto.

## Decisões aprovadas

### Motor de rating

1. **Algoritmo:** Glicko-2 adaptado para equipes, versão `glicko2_team_v1`.
2. **Escopo:** um rating por usuário e formato/modalidade.
3. **Parâmetros iniciais:** `rating = 1500`, `RD = 350`, `volatility = 0.06`, `RD máximo = 350`.
4. **Resultado coletivo:** apenas vitória, derrota ou empate alteram o rating; nenhuma métrica individual de desempenho é usada.
5. **Expectativa de vitória:** calculada pela média de rating das equipes e pela incerteza agregada; zebras rendem mais e derrotas como favorito custam mais.
6. **Incerteza individual:** cada jogador usa seu próprio `RD` na atualização; jogadores novos ou inativos se movem mais.
7. **Inatividade:** aumenta o `RD` em períodos de 7 dias, sem reduzir o rating.
8. **Cap:** delta máximo de `±100` por partida na v1.
9. **Aplicação:** somente partidas `ranked` em `FINALIZED`; `DISPUTED`, `RESULT_PENDING`, `VOIDED`, `CANCELLED` e casuais não geram rating.
10. **Idempotência:** um evento por `(match_id, user_id, algorithm_version)`, garantido por constraint; worker desacoplado `apply_ratings.py`.
11. **Histórico:** `rating_events` append-only; correções futuras geram eventos compensatórios, nunca exclusão.

### Divisão e ranking

12. **MMR oculto:** o app não mostra rating bruto, `RD` nem volatilidade.
13. **Divisão visível:** Bronze `< 1200`, Prata `1200–1399`, Ouro `1400–1599`, Platina `1600–1799`, Diamante `1800+`.
14. **Colocação:** as 5 primeiras partidas ranqueadas são exibidas como “Provisório”.
15. **Ranking:** top 100 por formato + posição individual do usuário; paginado e determinístico.

### Trust Factor

16. **Oculto e separado:** score interno neutro (`100`) e `trust_events` auditáveis.
17. **Sem punição automática na Fase 8:** faltas, cancelamentos e anulações podem ser registrados como sinais, mas não alteram o score automaticamente.
18. **Sem mistura:** Trust Factor não altera MMR, divisão, ranking ou matchmaking nesta fase.
19. **Evolução:** aplicação de penalidades e contestação completa ficam para a Fase 17.

### Matchmaking ranqueado

20. **Fila ranqueada habilitada** na Fase 8.
21. **Política `mmr_v1`:** usa MMR médio por equipe e limita a dispersão interna (maior − menor MMR) para evitar equipes “equilibradas na média” mas desbalanceadas na prática.
22. **Casual preservado:** a fila casual continua com a política por nível.

### Mobile

23. **Backend + telas mobile** na Fase 8.
24. **Exibição:** divisão, progresso, posição e histórico competitivo; sem MMR bruto e sem Trust Factor.
25. **Conquistas e troféus:** ficam para a Fase 16; não criar `user_achievements` na Fase 8.

### Simulações

26. **Simulações obrigatórias antes de ranking público:** convergência de novos jogadores, favoritos, zebras, empates e efeito da inatividade.
27. **Versionamento:** qualquer mudança de fórmula ou parâmetros gera nova `algorithm_version`; eventos antigos permanecem legíveis.

## Consequências

- O schema ganha `rating_accounts`, `rating_events`, `trust_accounts` e `trust_events`.
- O worker de resultados continua separado do worker de rating.
- A fila ranqueada deixa de retornar `ranked_not_available`.
- O ranking público só deve ser habilitado após as simulações e testes de concorrência.
- A interface mobile precisa de uma área competitiva, mas não de tela de Trust Factor.
- Trust Factor permanece um histórico de sinais, não uma punição automática.

## O que este ADR não decide

- Fórmula de troféus e conquistas (Fase 16).
- Pesos e limites definitivos de Trust Factor (Fase 17).
- Temporadas, recompensas e cosméticos.
- Política de privacidade de ranking além de nome de exibição e divisão.
- MMR entre modalidades diferentes; cada formato é independente.
