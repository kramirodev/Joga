# ADR 0007 — Hierarquia documental e extensão do roadmap

- **Status:** Aprovado pelo responsável do produto nesta conversa.
- **Data:** 2026-11-02

> **Nota de vigência (2026-11-05):** os itens 3 e 4 abaixo descrevem o roadmap e o escopo da época. As Fases 11–19 foram reorganizadas pelo ADR 0022 e pelo `PLANS.md` vigente; a precificação e o fluxo financeiro foram definidos no ADR 0021. O restante deste ADR permanece como registro histórico.

## Contexto

- A documentação conceitual foi revisada pela interface web do GitHub (`41a560a` → `42df97a`), divergindo do workspace local até a sincronização via fast-forward na mesma branch.
- O arquivo técnico foi renomeado (`docs/DOCUMENTACAO_TECNICA.md` → `docs/JOGA_DOCUMENTACAO_TECNICA.md`), deixando referências quebradas em `AGENTS.md`, `PROMPTS.md`, `README.md`, `README_INICIO.md` e nos arquivos de `harness/`.
- `GOALS.md` constava marketplace, reservas e pagamentos de quadras como fora de escopo, contrariando o pilar 4 do conceito.
- Existiam três numerações de fases em conflito: `PLANS.md` (0–10, incompleto), a tabela técnica (0–12 com sentidos diferentes) e as etapas de produto do conceito (1–14, especificamente declaradas como não normativas).
- Novos requisitos do conceito (capitães, confirmação de resultado, disputas, antifraude comercial, moderação) não tinham tradução técnica.

## Decisão

1. **Hierarquia documental:** `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` é a referência máxima em matéria de produto. `PLANS.md` é a fonte normativa de ordem, escopo e critérios de saída das fases. `docs/JOGA_DOCUMENTACAO_TECNICA.md` traduz ambos em arquitetura, módulos, dados, fluxos e critérios de aceitação, sem copiar o texto do conceito. Em contradição: produto → conceitual; execução → PLANS; o conflito é sempre comunicado ao responsável, nunca resolvido em silêncio (`AGENTS.md` atualizado em conformidade).
2. **Nome canônico:** `docs/JOGA_DOCUMENTACAO_TECNICA.md` é o nome vigente; `docs/DOCUMENTACAO_TECNICA.md` é histórico e não vigente. Referências vivas foram corrigidas; linhas históricas do `harness/build-log.md` e registros da Fase 0 são preservados como registro.
3. **Roadmap único:** a numeração de fases passa a ser exclusivamente a de `PLANS.md`, estendida de 0–10 para 0–19:
   - 0–10 mantidos (com fase 10 delimitada como núcleo esportivo e fase 9 incluindo amigos/convites/bloqueios).
   - 11 Organizações e gestão web; 12 Catálogo e estoque comprometido; 13 Pedidos, pagamentos e cumprimento; 14 Quadras e reservas; 15 Integridade comercial; 16 Clãs e troféus; 17 Moderação e Trust & Safety; 18 Publicidade; 19 Hardening final e lançamento comercial.
   - A tabela de fases da documentação técnica espelha esta numeração (seção 24) e não define ordem própria.
4. **Tradução técnica dos novos requisitos:** capitães, relato/confirmação de resultado, divergências, disputas (seções técnicas 10.1–10.5), moderação e denúncias de usuários (12.4), denúncias de transação, antifraude comercial e conversa comprador-vendedor (16.5–16.6), com entidades, constraints, APIs e testes correspondentes.
5. **Pendências não resolvidas a inventar:** divergência de exatamente 50%, abstenções/“voto válido” na votação de troca de quadra, tolerância por modalidade, prazo efetivo do relato, substituição/ausência de capitão e similares permanecem em aberto (seção 26 técnica) até decisão do produto.

## Consequências

- Nenhuma implementação de produto é autorizada por este ADR. O estado das fases permanece: Fase 0 `Complete`; Fase 1 `In progress`.
- Prompts por número de fase passam a referir unicamente à numeração do `PLANS.md` 0–19.
- Alterações futuras de documentação devem passar pelo repositório local/PR, evitando divergência entre workspace e origin.
