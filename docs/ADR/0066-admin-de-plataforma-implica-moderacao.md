# ADR 0066 — Administrador de plataforma implica moderação

- **Status:** Aprovado em 2026-11-21.
- **Data:** 2026-11-21
- **Relaciona:** `docs/ADR/0047-painel-moderacao-e-operadores.md`,
  `backend/app/api/v1/admin_guards.py`,
  `backend/app/api/v1/moderation.py`,
  `backend/app/modules/moderation/service.py`.

## Decisão

Contas listadas em `JOGA_PLATFORM_ADMINS` (o mesmo critério de `/admin/*`) são
tratadas como moderadoras com papel `ADMIN`, sem exigir inclusão em
`JOGA_MODERATION_ADMIN_USER_IDS` nem linha em `moderation_operators`. A allowlist
de moderação e a tabela de operadores permanecem inalteradas para as demais
contas, e a política de operadores do ADR 0047 não é reescrita.

`GET /api/v1/moderation/me` responde `200` com `role = "ADMIN"` para o admin de
plataforma; usuários comuns continuam recebendo `403 moderator_required`. A
auditoria das decisões continua registrando o ator como antes (campo
`operator`).
