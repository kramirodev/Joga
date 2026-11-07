# ADR 0030 — Kit da partida e responsabilidade por equipamento

- **Status:** Aprovado pelo responsável em 2026-11-07.
- **Data:** 2026-11-07
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §8.5 e §9.1; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §7.3, §10.1 e §18; `PLANS.md` Fases 5, 6 e 13.

## Contexto

Para a partida acontecer, alguém precisa levar bola, rede e outros itens. Hoje o produto modela horário, local, participantes e pagamento, mas não a disponibilidade de equipamento. A tentação natural seria usar “tem bola” como critério para escolher o capitão ou recomendar jogadores. Isso premiaria posse, seria inverificável e criaria barreira de acesso.

## Decisão

1. Equipamento é um requisito logístico do formato, versionado no backend.
2. Catálogo inicial: futebol 5x5 e basquete 3x3 — bola; vôlei de praia — rede e bola; tênis — bolas, com raquete individual.
3. Qualquer participante pode assumir um item ou registrar que o local fornece. A declaração é compromisso, não prova de posse.
4. A cobertura do kit é confirmada antes do check-in por um responsável logístico — criador do lobby manual ou participante designado — sem autoridade sobre o resultado.
5. O kit não é critério de capitão, MMR, Trust Factor ou elegibilidade, e não altera a seleção da seção 9.1.
6. Partidas ranqueadas priorizam equipamento fornecido pelo local ou pela organização.
7. Descumprir um item assumido gera evento de confiabilidade após confirmação e contestação; evento isolado não pune automaticamente.
8. Não há verificação de posse, foto de equipamento, aluguel, venda ou caução no MVP.

## Alternativas consideradas

### A. Equipamento como critério de capitão

Rejeitado: confunde confiabilidade com posse, é inverificável e exclui jogadores.

### B. Campo livre no lobby (“trazer equipamento”)

Rejeitado: não é estruturado, não permite estado de cobertura nem responsabilização.

### C. Catálogo de requisitos + declaração de responsabilidade (adotado)

Permite saber o que falta e quem assumiu, sem criar hierarquia ou barreira de entrada.

## Consequências

- Novas entidades e contratos para catálogo, estado do kit e responsáveis.
- A interface de partida/lobby precisa mostrar itens faltantes e permitir assumir ou trocar o responsável.
- A confiabilidade ganha um novo sinal, que deve ser auditável, contestável e desligado de punição automática.
- O responsável logístico ganha uma responsabilidade explícita, sem autoridade competitiva.
- O catálogo definitivo e a obrigatoriedade por formato permanecem pendentes.

## Critérios para revisão

- Evidência de que o kit incompleto impede partidas em escala.
- Necessidade de verificação (foto ou check-in de item), que exige nova ADR.
- Definição de penalidades e limites de confiabilidade.
