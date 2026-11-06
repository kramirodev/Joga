# ADR 0008 — Desempate de resultados em 50% e análise de confiabilidade

- **Status:** Aprovado pelo responsável do produto nesta conversa.
- **Data:** 2026-11-02

## Contexto

A documentação conceitual definiu que divergência de relatos acima de 50% leva a disputa, e que o resultado majoritário pode ser validado quando a divergência está dentro da tolerância por modalidade/formato — mas o tratamento exato de divergência igual a 50% permanecia em aberto (pendência 17 da técnica). Regras precisas de quórum tolerância eram bloqueadoras das fases 6–7.

O texto da decisão, redigido pelo responsável, foi incorporado como subseção 9.4 da conceitual e traduzido tecnicamente na seção 10.4 da documentação técnica.

## Decisão

1. **Fluxo de duas etapas:** divergência exatamente em 50% na primeira votação dispara uma segunda confirmação, aberta a todos os participantes, que podem confirmar ou corrigir a resposta anterior. O histórico da primeira votação é preservado para auditoria (nenhum relato é sobrescrito; registro append-only).
2. **Empate persistente:** se a segunda votação continuar exatamente empatada, a partida entra em análise interna e invisível de confiabilidade.
3. **Critério anti-acumulação:** a análise avalia cada relato individualmente — nunca por média simples do Trust Factor do grupo. Sinais avaliados: consistência de votos, histórico competitivo, coerência em alterações de voto e detecção de comportamento coordenado/manipulação. Objetivo: impedir que um grupo vença apenas acumulando contas de alta reputação.
4. **Papel do capitão:** os relatos dos capitães (escolhidos por Trust Factor) são sinais relevantes por sua confiabilidade, mas não têm peso automático de voto adicional nem autoridade para determinar o resultado sozinhos.
5. **Indicadores internos invisíveis:** os indicadores internos da análise não são exibidos aos participantes e servem exclusivamente ao sistema.
6. **Desfechos:** o sistema tenta resolver com base nos indicadores; sem conclusão segura, o caso vai para revisão humana; anulação permanece como último recurso.
7. **MMR congelado:** durante todo o processo (segunda votação e análise), nenhuma atualização definitiva de MMR é aplicada; rating só ocorre após decisão final validada, idempotente.

## Consequências

- A pendência de exatamente 50% está encerrada nos três níveis (conceito §9.4, técnica §10.4, PLANS fase 7).
- Continuam pendentes: tolerância por modalidade, prazo efetivo do relato e prazo da segunda rodada (na faixa curta a definir) — seção 26 da técnica.
- **Atualização 2026-11-06:** o prazo de relato foi fixado em 10 minutos, a segunda rodada em 5 minutos e a regra de 50% foi detalhada no ADR 0023.
- Nenhuma implementação é autorizada por este ADR; a regra será materializada na Fase 7 (PLANS 0–19).
- A análise interna deve gerar registro auditável append-only, sem exibir indicadores aos participantes.
