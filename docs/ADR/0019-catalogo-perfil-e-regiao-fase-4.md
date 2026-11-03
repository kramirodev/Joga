# ADR 0019 — Catálogo, perfil e região da Fase 4

- **Status:** Aprovado pelo responsável do produto em 2026-11-03, durante a abertura da Fase 4.
- **Data:** 2026-11-03
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0018, `PLANS.md` (Fase 4), `docs/JOGA_DOCUMENTACAO_TECNICA.md` §6, §7, §18 e §26.

## Contexto

A Fase 4 precisa de parâmetros que estavam pendentes na documentação: duração oficial dos formatos, composição do vôlei, escala de nível, contrato da região manual e origem dos locais. Sem isso, o catálogo e a descoberta não podem ser implementados sem inventar regras de produto.

## Decisão

1. **Futebol 5x5:** 10 participantes, duas equipes de 5, 50 minutos de jogo e 10 minutos de intervalo, totalizando 60 minutos por partida.
2. **Vôlei:** formato 6x6, 12 participantes, 60 minutos.
3. **Nível autodeclarado:** `beginner`, `intermediate` e `advanced`; sem validação competitiva nesta fase.
4. **Preferência de quadra:** `PUBLIC_ONLY`, `PRIVATE_ONLY` e `ANY`, com padrão `ANY`.
5. **Disponibilidade:** janelas recorrentes por dia da semana e faixa horária, com fuso padrão `America/Sao_Paulo`.
6. **Região manual:** CEP + raio em km, resolvido pelo **BrasilAPI CEP v2** (público, sem chave), com timeout e cache; o centro é aproximado e nunca a coordenada residencial exata.
7. **GPS em primeiro plano:** quando usado, o centro é arredondado (duas casas decimais) e substitui o centro anterior; não há histórico.
8. **Locais:** catálogo vazio nesta fase; o modelo e a descoberta ficam prontos, mas o cadastro público pertence às fases de organizações/quadras.
9. **Visibilidade:** nome de exibição, modalidades, nível e disponibilidade aproximada podem ser públicos; telefone, coordenada exata e histórico de localização são privados.

## Consequências

- A duração total e a composição ficam versionadas no formato; um lobby futuro copia a configuração aplicada.
- O BrasilAPI é uma dependência externa gratuita, mas sem SLA; falhas retornam erro controlado e o usuário pode tentar novamente.
- A descoberta por CEP depende de rede; a localização por GPS em primeiro plano continua sendo uma alternativa, e o perfil não bloqueia a edição por falta de GPS.
- Nenhum local real é semeado; a descoberta fica vazia no ambiente local até existir catálogo autorizado.
