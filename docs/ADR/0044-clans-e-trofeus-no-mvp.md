# ADR 0044 — Clãs e troféus no escopo do MVP

- **Status:** Aprovado; altera a ordem de fases do `PLANS.md`. Não implementado.
- **Data:** 2026-11-11
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0007 (hierarquia documental e roadmap), ADR 0025 (MMR, rankings e troféus), ADR 0043 (temporada e customização), `PLANS.md` Fase 16 e Fase 17.

## Contexto

O `PLANS.md` colocava clãs e troféus na **Fase 16**, depois das fases comerciais 11 a 15 e antes do lançamento comercial da Fase 19. Na prática, clãs chegariam ao fim de uma fila longa.

O primeiro evento de marketing do aplicativo depende de clãs. Se clãs só existirem no fim da fila, o evento não acontece, ou acontece sem a funcionalidade que o justifica. Isso muda a natureza de clãs: deixa de ser "recurso posterior" e passa a ser **condição de lançamento**.

## Decisão

1. **Clãs e troféus passam a integrar o escopo do MVP.**
2. A Fase 16 é **antecipada** e pode ser executada **em paralelo** às Fases 11 a 15, mantendo a dependência técnica da Fase 8 (competitivo).
3. A Fase 16 precisa estar **concluída antes do primeiro evento de marketing** e antes da Fase 19.
4. A Fase 17 (moderação) mantém a dependência da Fase 16. Como clãs incluem chat, **uma fatia mínima de moderação de chat de clã** precisa entrar junto com a Fase 16, mesmo que a moderação completa continue na 17.
5. O escudo de clã entra no catálogo cosmético da ADR 0043, sem vantagem competitiva.
6. Troféu de clã continua sendo conquista: não se compra, não se recebe por publicidade e não se transfere ao trocar de clã (ADR 0025).

## Consequências

- O `PLANS.md` registra a antecipação e a nova dependência.
- O escopo do MVP cresce: clãs, chat de clã, troféus por modalidade, escudo e moderação mínima de chat.
- O primeiro evento de marketing passa a ter uma data condicionada à Fase 16, não à Fase 19.
- A moderação mínima de chat de clã vira requisito de segurança de lançamento, não melhoria futura.
- Nenhuma outra fase muda de posição.

## Riscos

1. **Escopo.** Clãs mexem em matchmaking, troféus, moderação e customização ao mesmo tempo. É a fase com maior superfície de integração do roadmap.
2. **Segurança.** Chat de clã sem canal de denúncia é risco de moderação e de imagem, e o evento de marketing amplifica a exposição.
3. **Troféus.** A fórmula 50/30/20 e a elegibilidade precisam estar estáveis antes do evento, senão o ranking nasce contestado.

## Pendências

1. Definir o corte mínimo de moderação de chat de clã que acompanha a Fase 16.
2. Definir tamanho de clã, limites de entrada e regra de troca.
3. Definir a temporada de troféus e se ela coincide com a temporada trimestral da ADR 0043.
4. Definir a data-alvo do primeiro evento de marketing e usá-la como critério de saída da Fase 16.
5. Atualizar `docs/ADR/0007` ou registrar que esta ADR prevalece sobre a ordem ali descrita.
