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
3. O estabelecimento declara no cadastro quais modalidades aceita e **garante o equipamento base** dessas modalidades (ex.: rede de vôlei, cesta, trave). Itens móveis (bola, coletes) são uma marcação **opcional** do jogador — “talvez tenha” —, não um compromisso obrigatório.
4. A cobertura do kit é conferida antes do check-in por um responsável logístico — criador do lobby manual ou participante designado — como **checklist/aviso**, sem autoridade sobre o resultado.
5. O kit **não bloqueia** o lobby, o matchmaking, a confirmação, o pagamento, o check-in nem o início da partida. A ausência de um item é mostrada e combinada, não vira portão automático.
6. Itens fixos da modalidade — rede de vôlei, cesta de basquete, trave — são responsabilidade do **estabelecimento que declarou aceitar a modalidade**. Se o local aceita vôlei, deve fornecer a rede; a falta é falha da quadra, não do jogador.
7. Itens móveis — bola, coletes, bolas de tênis — podem ser marcados opcionalmente pelo jogador como “tenho” ou fornecidos pelo local. A falta não impede a partida e não gera penalidade automática.
8. O kit não é critério de capitão, MMR, Trust Factor ou elegibilidade, e não altera a seleção da seção 9.1.
9. Partidas ranqueadas priorizam equipamento fornecido pelo local ou pela organização.
10. Não há verificação de posse, foto de equipamento, aluguel, venda ou caução no MVP.
11. Não há evento de Trust Factor por item móvel não levado; a marcação é informativa. Item fixo ausente é falha do estabelecimento e segue as regras de reserva/reembolso.

## Alternativas consideradas

### A. Equipamento como critério de capitão

Rejeitado: confunde confiabilidade com posse, é inverificável e exclui jogadores.

### B. Campo livre no lobby (“trazer equipamento”)

Rejeitado: não é estruturado, não permite estado de cobertura nem responsabilização.

### C. Catálogo de requisitos + declaração de responsabilidade (adotado)

Permite saber o que falta e quem assumiu, sem criar hierarquia ou barreira de entrada.

## Consequências

- Novas entidades e contratos para catálogo, estado do kit e responsáveis.
- A interface de partida/lobby precisa mostrar itens base fornecidos pelo local e permitir marcar “talvez tenha” itens móveis, sem bloquear a partida.
- A confiabilidade ganha um novo sinal, que deve ser auditável, contestável e desligado de punição automática.
- O responsável logístico ganha uma responsabilidade explícita, sem autoridade competitiva.
- O estabelecimento precisa declarar/confirmar os itens fixos das modalidades que aceita; a ausência desses itens é falha da quadra.
- O catálogo definitivo e a obrigatoriedade por formato permanecem pendentes.

## Critérios para revisão

- Evidência de que o kit incompleto impede partidas em escala.
- Necessidade de verificação (foto ou check-in de item), que exige nova ADR.
- Definição de penalidades e limites de confiabilidade.
