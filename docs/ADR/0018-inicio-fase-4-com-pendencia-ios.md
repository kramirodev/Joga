# ADR 0018 — Início da Fase 4 com a pendência iOS da Fase 1

- **Status:** Aprovado pelo responsável do produto em 2026-11-03, ao autorizar o início da Fase 4.
- **Data:** 2026-11-03
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `PLANS.md` (Fases 1, 3 e 4), ADR 0012, ADR 0017, `harness/build/phase-03-identidade-e-seguranca.md`.

## Contexto

A Fase 3 está `Complete` para backend e Android, com o bloqueio iOS formalmente aceito no ADR 0017. O `PLANS.md` declara a Fase 4 dependente da Fase 3, o que está satisfeito. A Fase 1 continua `In progress` apenas pela associação/build iOS, que não é pré-requisito para perfil e descoberta.

A Fase 4 exige decisões de produto ainda não registradas: duração oficial dos formatos, composição do vôlei, escala do nível autodeclarado, contrato da região manual e origem dos locais descobertos.

## Decisão

1. Iniciar a Fase 4 na branch `feat/04-perfil-e-descoberta`, a partir de `main` (`a2c9649`).
2. Manter a Fase 1 como `In progress` e não declarar suporte iOS.
3. Não modelar formatos esportivos com duração arbitrária nem implementar o vôlei antes da definição do produto.
4. Separar a fase em iterações; a primeira cobre perfil básico, disponibilidade e descoberta por região manual, após as decisões registradas.
5. Nenhuma ação externa, custo ou provedor real é autorizado por esta decisão.

## Consequências

- A Fase 4 pode avançar no backend/Android sem esperar o iOS.
- As decisões de catálogo/nível/região precisam ser tomadas antes do modelo de dados definitivo; até lá, o trabalho fica limitado a governança e desenho.
- A fase não pode ser marcada `Complete` sem os critérios de GPS negado/aproximado, busca manual, limites de raio/paginação e autorização.
