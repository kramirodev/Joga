# ADR 0001 — Governança do roadmap

- **Status:** Parcialmente vigente: `PLANS.md` permanece a fonte normativa. As demais decisões iniciais de nome, destino e relação entre projetos foram substituídas por ADRs posteriores.
- **Data:** 2026-11-01

## Registro histórico

Esta ADR surgiu para resolver divergências entre o roadmap e a documentação técnica sobre escopo de fases, ponto de entrada do repositório e organização de decisões arquiteturais. As decisões iniciais de branding, destino de repositório e tratamento do projeto independente deixaram de ser vigentes e não devem orientar o desenvolvimento atual.

## Decisões que permanecem

1. `PLANS.md` define a sequência, dependências, escopo e critérios de conclusão das fases.
2. `README.md` é o ponto de entrada principal; `README_INICIO.md` é complementar enquanto útil.
3. Decisões arquiteturais relevantes devem ser registradas em `docs/ADR/`.
4. Decisões técnicas pendentes devem indicar a fase responsável.

## Consequências

A Fase 0 não inclui código de aplicação, banco, Docker ou CI funcional. A documentação técnica resume o roadmap e remete a `PLANS.md` para sequência, limites e aceite.
