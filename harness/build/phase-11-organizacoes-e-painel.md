# Fase 11 — Organizações e painel de gestão

**Status:** 11A (fundação backend) implementado em 2026-11-06; 11B (painel web) autorizado pelo ADR 0028 em 2026-11-06.
**Branch:** `feat/11-organizacoes-painel`

## Objetivo

Permitir que estabelecimentos esportivos administrem apenas as operações originadas no JOGA, com identidade compartilhada com o aplicativo, papéis explícitos, isolamento entre organizações e trilha auditável. O painel web é uma ferramenta autenticada de gestão, não um site público nem um ERP.

## Escopo 11A — fundação backend (implementado)

- Organizações e vínculo do criador como `OWNER` na mesma transação.
- Membros com papéis `OWNER`, `ADMIN` e `OPERATOR`.
- Capacidades por papel verificadas no servidor em cada operação.
- Perfil comercial do estabelecimento (`organization_venues`) vinculado à organização.
- Auditoria append-only de criação/alteração de organização, membros e estabelecimentos.
- Paginação e limites na consulta de auditoria.
- Testes HTTP de autorização negativa, BOLA/IDOR e confusão de IDs entre organizações.
- Teste PostgreSQL de unicidade de vínculo e concorrência do último proprietário.
- Migração Alembic reversível e validada com `alembic check`.

## Fora do escopo imediato

- Painel web visual antes da confirmação do ADR 0028.
- Quadras, agenda, preços, bloqueios e exceções (Fase 12).
- Reservas, temporizadores e fluxo financeiro (Fases 13–15).
- KYC/recebedor no PSP (Fase 12).
- Clãs, moderação e publicidade (Fases 16–18).
- ERP, catálogo, estoque, vendas presenciais ou site público.
- Convite por e-mail/WhatsApp, recuperação de conta e onboarding comercial completo.

## Decisão sobre `venues`

A tabela `venues` já existe desde a Fase 4 como catálogo de locais descobertos (`kind`, `lat`, `lng`, endereço e estado ativo). Ela não será sobrescrita nem reinterpretada.

A Fase 11 cria `organization_venues` para o perfil comercial do estabelecimento, com vínculo obrigatório à organização. A ligação entre o catálogo de descoberta e o perfil comercial, incluindo geografia e publicação, fica para a Fase 12. Isso evita quebrar a descoberta existente e evita tratar um local público como estabelecimento reservável sem autorização.

## Papéis e capacidades

| Capacidade | `OWNER` | `ADMIN` | `OPERATOR` |
|---|---|---|---|
| `organization:read` | sim | sim | sim |
| `organization:update` | sim | sim | não |
| `members:read` | sim | sim | sim |
| `members:manage` | sim | sim | não |
| `venues:read` | sim | sim | sim |
| `venues:manage` | sim | sim | sim |
| `audit:read` | sim | sim | não |

Regras adicionais:

- Somente `OWNER` concede ou altera papéis `OWNER` e `ADMIN`.
- `ADMIN` gerencia apenas `OPERATOR`; não altera nem remove `OWNER` ou outro `ADMIN`.
- O último `OWNER` não pode ser removido nem rebaixado.
- Alterações de vínculo travam a linha da organização no PostgreSQL para evitar duas remoções concorrentes do último proprietário.
- Um usuário sem vínculo recebe `404 organization_not_found`; um membro sem capacidade recebe `403 forbidden`. Isso reduz enumeração entre organizações.

## Endpoints 11A

| Método | Rota | Capacidade |
|---|---|---|
| `POST` | `/api/v1/organizations` | autenticado; criador vira `OWNER` |
| `GET` | `/api/v1/organizations` | lista apenas vínculos do usuário |
| `GET` | `/api/v1/organizations/{id}` | `organization:read` |
| `PATCH` | `/api/v1/organizations/{id}` | `organization:update` |
| `GET` | `/api/v1/organizations/{id}/members` | `members:read` |
| `POST` | `/api/v1/organizations/{id}/members` | `members:manage` + hierarquia |
| `PATCH` | `/api/v1/organizations/{id}/members/{user_id}` | `members:manage` + hierarquia |
| `DELETE` | `/api/v1/organizations/{id}/members/{user_id}` | `members:manage` + hierarquia |
| `POST` | `/api/v1/organizations/{id}/venues` | `venues:manage` |
| `GET` | `/api/v1/organizations/{id}/venues` | `venues:read` |
| `GET` | `/api/v1/organizations/{id}/venues/{venue_id}` | `venues:read` |
| `PATCH` | `/api/v1/organizations/{id}/venues/{venue_id}` | `venues:manage` |
| `GET` | `/api/v1/organizations/{id}/audit` | `audit:read` |

## Critérios de aceite

- [x] Membro de uma organização não lê nem altera recursos de outra (testes BOLA/cruzados).
- [x] Papéis respeitados por ação, incluindo hierarquia e último proprietário.
- [x] Contratos HTTP versionados com schemas explícitos.
- [x] Identidade compartilhada com o app; o mesmo usuário pode ter papéis diferentes em organizações distintas.
- [x] Auditoria registra ator, ação, recurso e organização, sem exclusão silenciosa.
- [x] Migração revisável, com upgrade/downgrade/check validados.
- [ ] Painel web responsivo e autenticado — ADR 0028 aprovado; implementação em andamento.
- [ ] Operações de reservas/pagamentos no painel — dependem das Fases 12–15.

## Evidências de execução

- `pytest` sem PostgreSQL: **296 passed, 25 skipped**.
- `pytest` com `JOGA_TEST_DATABASE_URL`: **321 passed**.
- Testes específicos da fase: 8 HTTP + 2 PostgreSQL.
- `ruff check`, `ruff format --check` e `mypy app` passam.
- Migração `a1b2c3d4e5f6`: upgrade, downgrade e novo upgrade em banco descartável com PostGIS; `alembic check` sem operações pendentes.

## Próximo passo (11B)

1. Confirmar o ADR 0028 (React + TypeScript + Vite).
2. Implementar autenticação do painel sem conta separada, preferindo cookie `HttpOnly` same-origin, CSRF e curta duração de acesso.
3. Criar seleção de organização, tela de membros/papéis e tela de estabelecimentos.
4. Exibir a auditoria apenas para `OWNER`/`ADMIN`.
5. Testar responsividade no navegador do celular e no desktop, além de estados vazio/erro/carregamento.
6. Não iniciar reservas, agenda, pagamentos ou KYC nesta fase.

## Condição de parada

Encerrar a 11A com os testes e a migração validados. Não implementar o painel web, reservas ou ações externas sem confirmação do ADR e autorização específica.
