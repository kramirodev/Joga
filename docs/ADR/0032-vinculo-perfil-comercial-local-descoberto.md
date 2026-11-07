# ADR 0032 — Vínculo entre perfil comercial e local descoberto

- **Status:** Aprovado para a 12A em 2026-11-07.
- **Data:** 2026-11-07
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_TECNICA.md` §13.1; `PLANS.md` Fases 4, 11 e 12.

## Contexto

A Fase 4 criou `venues` como catálogo de locais descobertos, com geografia, tipo público/privado e estado ativo. A Fase 11 criou `organization_venues` como perfil comercial do estabelecimento, deliberadamente separado para não tratar local público como reservável nem quebrar a descoberta. A Fase 12 precisa ligar os dois conceitos sem fundi-los.

## Decisão

1. `organization_venues` ganha `venue_id` opcional, único, com `ON DELETE SET NULL`.
2. Só é possível vincular um local `venues` ativo e do tipo `private`.
3. Local público ou inativo não pode ser vinculado; a API responde `invalid_input`.
4. O vínculo pode ser removido (`venue_id = null`) sem apagar o perfil comercial.
5. O vínculo não concede autorização de reserva nem publica o estabelecimento automaticamente; serve para reconciliar descoberta e operação.
6. A Fase 13 usará o vínculo para relacionar reservas ao local descoberto quando aplicável.

## Alternativas consideradas

### A. Fundir `venues` e `organization_venues`

Rejeitada: quebraria a descoberta da Fase 4 e misturaria local público com estabelecimento reservável.

### B. Manter tudo separado sem vínculo

Rejeitada: impede reconciliar o local descoberto com o perfil comercial e a agenda.

### C. FK opcional e única (adotada)

Preserva os dois modelos e permite evolução incremental.

## Consequências

- Um local privado pode ter no máximo um perfil comercial vinculado.
- Local público continua descoberto, mas não reservável sem autorização verificável.
- A migração é reversível e não altera os dados existentes.
- A interface do painel pode evoluir para escolher o local descoberto sem criar um novo cadastro duplicado.

## Critérios para revisão

- Necessidade de múltiplos perfis comerciais para o mesmo local.
- Regras de publicação e moderação de locais descobertos.
- Integração com a agenda e reservas da Fase 13.
