# Fase 17C — Painel interno de moderação

**Status:** implementado no backend e no painel web em 2026-11-14.
**Depende de:** 17A (denúncias), 17B (medidas e retenção), Fase 9 (notificações).
**Não inclui:** IA paga, classificador local treinado, suspensão permanente, alterações no app mobile.

## Problema

A 17A/17B permitiam denunciar e decidir, mas a operação dependia de CLI e os
operadores não tinham identidade própria no produto. Também não havia aviso
persistido ao administrador quando uma nova denúncia entrava na fila.

## Decisões

1. **Sem IA paga.** A triagem continua determinística (`rules_v1`). Nenhum texto
   é enviado a terceiros. O classificador local/open-source continua fora desta
   fatia e depende de dataset rotulado e avaliação offline.
2. **Identidade de operador no banco.** `moderation_operators` guarda
   `user_id`, papel `ADMIN|MODERATOR`, estado ativo e autoria da inclusão.
   O papel é sempre verificado no servidor; UUID de conta não concede acesso.
3. **Bootstrap por ambiente.** `JOGA_MODERATION_ADMIN_USER_IDS` promove contas a
   administrador sem seed manual no banco. Operadores gravados no banco têm
   precedência e podem ser desativados pelo painel.
4. **Painel separado.** A moderação vive em `/moderation`, com cabeçalho
   “JOGA y MODERAÇÃO”, distinto do JOGA y GESTÃO. O painel é autenticado e
   protegido por cookie/CSRF já usados pelo painel de gestão.
5. **Notificação persistida.** Ao criar uma denúncia, o backend grava uma
   notificação `moderation_report` para cada operador ativo e para os admins de
   bootstrap. Novo recurso grava `moderation_appeal` para os operadores; a
   decisão grava `moderation_appeal_result` para o jogador. A fila do painel
   também atualiza a cada 30 segundos.
6. **Decisão humana e auditável.** Medidas continuam sendo `DISMISS`, `WARN`,
   `RESTRICT_RANKED` e `SUSPEND_TEMP` (1–30 dias), com justificativa
   obrigatória e registro de auditoria.
7. **Suspensão permanente fora da fatia.** Continua exigindo política, segundo
   revisor e revisão jurídica.

## Superfície

Backend:

- `GET /api/v1/moderation/me` — papel do operador autenticado.
- `GET /api/v1/moderation/queue` — fila por status, com estatísticas.
- `GET /api/v1/moderation/reports/{id}` — detalhe com contexto anexado.
- `POST /api/v1/moderation/reports/{id}/decision` — decisão humana.
- `GET /api/v1/moderation/appeals` — recursos pendentes.
- `POST /api/v1/moderation/appeals/{id}/decision` — decisão do recurso.
- `GET/POST /api/v1/moderation/operators` — gestão de operadores (somente admin).
- `DELETE /api/v1/moderation/operators/{user_id}` — desativação (somente admin).

Modelo e migração:

- `moderation_operators` (`b4c5d6e7f8a9`): `user_id` PK, `role`, `active`,
  `created_by`, `created_at`, `deactivated_at`.
- `CheckConstraint` limita o papel a `ADMIN|MODERATOR`.

Painel web:

- `web/src/pages/ModerationPage.tsx`, rota `/moderation`.
- `AppHeader` ganhou a variante “JOGA y MODERAÇÃO”.
- Estatísticas, fila, detalhe com contexto, decisão, recursos e gestão de
  moderadores para administradores.

## Operação

```text
JOGA_MODERATION_ADMIN_USER_IDS=<uuid-admin-1>,<uuid-admin-2>
JOGA_MODERATION_OPERATORS=<operador-legado>   # compatibilidade com 17A
JOGA_MODERATION_MAX_REPORTS_PER_DAY=5
```

1. Defina ao menos um UUID em `JOGA_MODERATION_ADMIN_USER_IDS` e reinicie a API.
2. Entre no painel com a conta desse UUID e abra `/moderation`.
3. Cadastre os demais moderadores pelo bloco “Moderadores”, informando o UUID
   da conta. O papel `MODERATOR` opera a fila; `ADMIN` também gerencia papéis.
4. A decisão exige justificativa. Recursos aceitos revogam a medida.
5. A CLI `scripts.review_moderation.py` continua disponível para contingência.

## Segurança

- `get_moderator` valida o operador em todas as rotas internas; conta comum
  recebe `403 moderator_required`.
- `require_admin` protege a gestão de operadores; moderador recebe
  `403 admin_required`.
- Ações de operador e alterações de papel geram auditoria append-only.
- O painel não expõe score, Trust Factor, MMR nem dados de outros domínios.
- O contexto exibido é o mesmo conjunto limitado coletado na denúncia; a
  redação após 180 dias continua valendo.

## Testes

- `backend/tests/test_moderation.py`: fila, notificação, decisão, recurso,
  bloqueio de conta comum e inclusão de operador por admin.
- Suíte backend: **477 passed, 29 skipped**; `ruff check`, `ruff format --check`
  e `mypy app` limpos; Alembic no head `b4c5d6e7f8a9` com `alembic check` limpo.
- Painel web: **22 testes**, incluindo acesso restrito e decisão na
  `ModerationPage`; `tsc --noEmit`, `eslint .`, Prettier dos arquivos alterados
  e `vite build` com CSP limpos.
- O mobile não foi alterado nesta fatia.

## Pendente

1. Classificador local/open-source com dataset, avaliação offline e versionamento.
2. Central de notificações dentro do painel web; o backend já separa o canal
   `moderation` e o app do jogador não recebe essas notificações.
3. Suspensão permanente com política, dupla revisão e revisão jurídica.
4. Retenção definitiva/LGPD e direito de exclusão.
5. Tela mobile dedicada a acompanhar denúncias e medidas recebidas.
