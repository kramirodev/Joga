# Fase 11 — Organizações e painel de gestão

**Status:** 11A (fundação backend) e 11B (painel web) implementados e validados localmente em 2026-11-06; sem deploy.
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

## Escopo 11B — painel web (implementado)

- Painel `web/` em React + TypeScript + Vite, responsivo, sem site público e sem SSR.
- Login e criação de conta por OTP, reutilizando a identidade do aplicativo.
- Sessão web com refresh em cookie `HttpOnly`, access token em memória e CSRF de duplo envio para refresh/logout.
- Rotas autenticadas: `/login`, `/` (organizações) e `/organizations/:id`.
- Seleção/criação de organização, edição de nome, membros/papéis, estabelecimentos e auditoria.
- Exibição de controles conforme o papel: operador não edita organização, não gerencia membros e não vê auditoria; pode consultar membros e gerenciar estabelecimentos.
- Estados de carregamento, erro, vazio e sucesso; layout responsivo para desktop e navegador do celular.
- CI do painel: `lint`, `format:check`, `typecheck` e `build`.

### Autenticação web

| Método | Rota | Função |
|---|---|---|
| `POST` | `/api/v1/auth/web/registration` | cria conta e sessão web |
| `POST` | `/api/v1/auth/web/login` | autentica conta existente |
| `POST` | `/api/v1/auth/web/refresh` | rotaciona o refresh com CSRF |
| `POST` | `/api/v1/auth/web/logout` | revoga a sessão e limpa cookies |

O refresh cookie usa `Path=/api/v1/auth/web`, `HttpOnly` e `SameSite=Strict`. O cookie CSRF é legível pelo JavaScript e o header `X-CSRF-Token` é exigido em refresh/logout. Em produção, `JOGA_WEB_COOKIE_SECURE=true` e HTTPS são obrigatórios.

## Fora do escopo imediato

- Site público, SSR, SEO ou página pública de estabelecimento.
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
- [x] Painel web responsivo e autenticado — login/registro por OTP, organizações, membros, estabelecimentos e auditoria validados no navegador.
- [ ] Operações de reservas/pagamentos no painel — dependem das Fases 12–15.

## Evidências de execução

- `pytest` sem PostgreSQL: **302 passed, 25 skipped**.
- `pytest` com `JOGA_TEST_DATABASE_URL`: **327 passed**.
- Testes específicos da fase: 8 HTTP de organizações + 2 PostgreSQL + 5 HTTP de sessão web + 1 teste de revogação por refresh.
- `ruff check`, `ruff format --check` e `mypy app` passam.
- Migração `a1b2c3d4e5f6`: upgrade, downgrade e novo upgrade em banco descartável com PostGIS; `alembic check` sem operações pendentes.
- Painel: `pnpm lint`, `pnpm format:check`, `pnpm typecheck` e `pnpm build` passam.
- Smoke no navegador: criação de conta por OTP, criação de organização, criação/ativação de estabelecimento, auditoria, recarga da página com refresh, logout e login de conta existente.
- Smoke de papéis no navegador: operador não vê edição de organização, gestão de membros nem auditoria; consegue consultar membros e criar estabelecimento.
- CI da branch `feat/11-organizacoes-painel`: run `42211679165` verde nos jobs Backend, Web e Mobile.
- Nenhum deploy, provedor real ou custo externo foi acionado.

## Próximos passos

1. Revisar a 11B em code review e, se aprovada, integrar a branch.
2. Iniciar a Fase 12 somente após autorização específica: quadras, agenda, preços e KYC.
3. Adicionar testes automatizados de UI (Vitest/Testing Library ou Playwright) antes de ampliar o painel.
4. Definir CSP, política de origem e observabilidade do painel antes de produção.

## Condição de parada

Encerrar a Fase 11 com 11A/11B validados localmente. Não iniciar a Fase 12, reservas, pagamentos ou ações externas sem autorização específica.
