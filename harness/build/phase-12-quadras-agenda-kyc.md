# Fase 12 — Quadras, agenda e KYC

**Status:** 12A implementada e validada localmente em 2026-11-07; 12B (KYC/recebedor) pendente de decisão e contrato de PSP.
**Branch:** `feat/12a-quadras-fotos-agenda`

## Fontes e contexto

- `AGENTS.md`
- `GOALS.md`
- `PLANS.md` — Fase 12
- `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §10.1–10.8, §20.4 e §26
- `docs/JOGA_DOCUMENTACAO_TECNICA.md` §12.6, §13, §18, §19 e §20
- `docs/ADR/0029-sem-fotos-de-pessoas-e-avatares-gerados.md`
- Fase 11 (`organizations`, `organization_venues`, painel web e auditoria)

## Objetivo

Permitir que o estabelecimento cadastre suas quadras, modalidades, agenda, preços, bloqueios e fotos no painel, com isolamento por organização, revisão de mídia e trilha auditável. Em 12B, permitir o onboarding do recebedor no PSP e expor seu estado, sem liberar cobrança para recebedor não ativo.

## Escopo 12A — quadras, fotos e agenda

- Modelo de espaços reserváveis (`venue_spaces`), vínculo com modalidade (`venue_sports`), agenda (`venue_availability`), bloqueios e exceções (`venue_blackouts`).
- CRUD no painel com autorização por organização e auditoria de criação, alteração, desativação e remoção.
- Ligação explícita entre o catálogo `venues` da Fase 4 e o perfil comercial `organization_venues` da Fase 11, sem quebrar a descoberta existente.
- Fotos de quadra/estabelecimento (`venue_photos`):
  - upload autenticado por membro com capacidade de gerenciar estabelecimentos;
  - allowlist de tipo real (JPEG, PNG e WebP), limite de tamanho e dimensões, verificação por magic bytes;
  - remoção de EXIF/metadados e reencode seguro antes de armazenar;
  - armazenamento privado, nome aleatório e acesso somente por endpoint autorizado;
  - estados de revisão (`PENDING`, `APPROVED`, `REJECTED`, `REMOVED`), motivo de rejeição e auditoria;
  - foto só é exibida após aprovação e vínculo com organização ativa;
  - proibição de pessoas identificáveis; revisão rejeita foto com pessoa em primeiro plano;
  - remoção, retenção e limpeza de arquivos órfãos documentadas.
- Leitura de quadras/fotos para o app do jogador, respeitando publicação e revisão. A UI mobile de descoberta pode ser um incremento separado se o escopo crescer.
- Agenda com fuso do estabelecimento, duração do formato, preços por faixa, intervalos de manutenção, dias fechados e reservas externas.

### Implementação 12A

- Modelos `venue_spaces`, `venue_sports`, `venue_availability`, `venue_blackouts` e `venue_photos`, além de `organization_venues.venue_id` (FK opcional e única para local privado ativo) e `organization_venues.timezone`.
- API aninhada em `/api/v1/organizations/{org}/venues/{venue}/spaces`, com modalidades, agenda, bloqueios e fotos.
- Upload de foto com validação real por Pillow, reencode em JPEG, remoção de EXIF, limites configuráveis e storage local privado.
- Revisão inicial por `OWNER`/`ADMIN`, com auditoria; `OPERATOR` gerencia quadras/fotos, mas não revisa. Revisão independente fica para a Fase 17.
- Painel com aba de quadras, modalidades, agenda, bloqueios e fotos; serving autenticado por blob e CSP com `img-src blob:`.
- Testes backend unitários, HTTP e PostgreSQL; testes de painel com Vitest/Testing Library.

Limitações conhecidas da 12A:

- storage local não serve para produção; provedor, criptografia e backup ficam pendentes;
- revisão não é independente até a Fase 17;
- a UI mobile de descoberta de quadras/fotos não foi implementada nesta rodada;
- reservas e cobrança continuam nas Fases 13–15.

## Escopo 12B — KYC e recebedor

- `venue_payment_accounts` com referência do recebedor, estado (`PENDING`, `ACTIVE`, `REJECTED`, `SUSPENDED`) e dados contratuais mínimos.
- Adaptador de PSP com implementação simulada em `local`/`test`/`ci`; provedor real somente com decisão, contrato e credenciais autorizadas.
- Onboarding e consulta de estado no painel, com acesso restrito e auditoria.
- Regra preparatória: nenhuma cobrança de reserva pode ser aberta para recebedor não `ACTIVE`. A enforcement completa ocorre na Fase 14.
- Dados de KYC nunca são públicos, não entram em logs e não são servidos ao app do jogador.

## Fora do escopo

- Reservas, bloqueios temporários de reserva, T1/T2/T3 e substituições (Fase 13).
- Pix, cobranças, split, custódia, webhooks, reembolsos e conciliação (Fases 14–15).
- Site público, SSR, SEO ou página pública de estabelecimento.
- ERP, PDV, estoque, produtos, logística ou aluguel de equipamento.
- Upload livre de mídia por usuários, foto de pessoa, áudio ou vídeo em perfil/chat.
- Clãs, moderação de chat, publicidade e lançamento comercial (Fases 16–19).

## Pré-requisitos e dependências

- Fase 11 integrada na `main` ou autorização explícita para empilhar a Fase 12 na branch atual.
- Decisão registrada em ADR sobre armazenamento de mídia (disco local no desenvolvimento vs storage de objetos na produção), retenção e serving autorizado.
- Decisão registrada sobre o vínculo `venues` ↔ `organization_venues` antes da migração.
- Para 12B: decisão de PSP, contrato, KYC e ambiente sandbox. Sem isso, 12B fica bloqueada e 12A segue isolada.
- Limites de upload, rate limiting e backup definidos para o storage escolhido.

## Arquivos/componentes esperados

Proposta sujeita à inspeção antes da implementação:

- `backend/app/modules/venues/models.py` — espaços, esportes, agenda, bloqueios, fotos e recebedor.
- `backend/app/modules/venues/service.py` — regras de domínio e autorização.
- `backend/app/modules/venues/photos.py` — validação, reencode, revisão e serving.
- `backend/app/modules/venues/storage.py` — adaptador de armazenamento privado.
- `backend/app/modules/venues/kyc.py` — adaptador e estados do recebedor.
- `backend/app/api/v1/venues.py` (ou extensão de `organizations.py`) — contratos HTTP.
- Migração Alembic revisável e reversível.
- `backend/tests/test_venues_api.py`, `test_venues_postgres.py`, `test_venue_photos.py`, `test_kyc.py`.
- `web/src/pages/VenuePage.tsx` ou aba “Quadras” em `OrganizationPage.tsx`.
- `web/src/components/VenuePhotos.tsx` e ajustes no cliente HTTP.
- `web/src/**/*.test.tsx` para permissões, upload e estados de revisão.
- `docs/ADR/0031-*` para armazenamento/revisão de fotos e `docs/ADR/0032-*` para o vínculo de locais, se confirmados.

## Riscos e decisões pendentes

- **Alto:** upload de imagem é superfície de abuso (polyglot, malware, decompression bomb, EXIF com localização, pessoa em segundo plano). Exige validação real, reencode, limites e revisão.
- **Alto:** vazamento de foto entre organizações ou antes da aprovação. Testar BOLA/IDOR em cada operação e no serving.
- **Alto:** KYC e dados bancários. Acesso restrito, logs limpos, retenção e contrato com PSP.
- **Médio:** fusão `venues`/`organization_venues` pode quebrar a descoberta da Fase 4. Resolver com ADR e migração compatível.
- **Médio:** concorrência e sobreposição de agenda; constraints e transações precisam ser definidas antes do código.
- **Médio:** custo e retenção de storage; política de remoção e arquivos órfãos.
- **Baixo:** ordenação, foto de capa e alt text/descrição acessível.
- **Pendente:** provedor de storage, PSP, limites de imagem, prazo de revisão e retenção.

## Plano de verificação

- **Red:** escrever testes que falham para: membro de outra organização lendo/enviando/revisando foto; foto não aprovada servida; tipo/tamanho inválido aceito; sobreposição de agenda; recebedor não ativo liberando cobrança.
- **Green:** implementar o mínimo para passar, com autorização no servidor e constraints no PostgreSQL.
- **Refactor:** extrair storage/revisão, reduzir duplicação, manter rotas finas e schemas explícitos.
- **Verify:** testes unitários, HTTP e PostgreSQL; lint, formatação, tipos e build; revisão do diff; `git diff --check`; teste manual no painel com dois usuários de organizações diferentes.

## Comandos reais de validação

Backend:

```bash
cd backend
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy app
.venv/bin/python -m pytest
JOGA_TEST_DATABASE_URL="postgresql+psycopg://joga:joga@127.0.0.1:5434/joga" .venv/bin/python -m pytest tests/test_venues_postgres.py -v
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic check
```

Painel:

```bash
cd web
pnpm lint
pnpm format:check
pnpm typecheck
pnpm test
pnpm build
```

## Critérios de aceite

- [x] Espaços/quadras, modalidades, agenda, preços e bloqueios são escopados por organização.
- [x] Membro de uma organização não lê, cria, altera nem remove recursos de outra (BOLA/IDOR).
- [x] Agenda respeita fuso, duração do formato, intervalos e reservas externas; sobreposição é impedida por constraint/transação.
- [x] Upload rejeita tipo, tamanho e dimensões fora do limite, remove metadados e não confia no nome/content-type original.
- [x] Foto só é servida após aprovação, por endpoint autorizado, sem cache público.
- [x] Rejeição, remoção e retenção são auditáveis; arquivos órfãos são tratados.
- [x] Foto com pessoa identificável é rejeitada na revisão; o fluxo não aceita upload livre.
- [ ] Recebedor tem estado consultável e auditável; KYC pendente bloqueia abertura de cobrança quando a Fase 14 existir. (12B)
- [x] Migração revisável com upgrade, downgrade e `alembic check`.
- [x] Painel cobre o fluxo com estados de carregamento, erro, vazio e sucesso.
- [x] Nenhum provedor real de storage, PSP ou KYC é acionado sem autorização.

## Evidências exigidas

- Saída de `pytest`, testes PostgreSQL, `ruff`, `mypy` e `alembic`.
- Saída de `pnpm lint`, `format:check`, `typecheck`, `test` e `build`.
- Revisão do diff e `git diff --check`.
- Smoke no painel com duas organizações distintas.
- Atualização de `harness/build-log.md` e do arquivo da fase.

## Evidências da 12A (2026-11-07)

- Backend sem PostgreSQL: **315 passed, 28 skipped**.
- Backend com `JOGA_TEST_DATABASE_URL`: **344 passed**.
- `ruff check`, `ruff format --check` e `mypy app` passam.
- Migrações `99c1055b81b5` e `0261da35ece5` aplicadas; `alembic upgrade head` → `downgrade base` → `upgrade head` e `alembic check` validados em banco descartável com PostGIS.
- Painel: **7 arquivos e 17 testes** passando; `lint`, `format:check`, `typecheck` e `build` verdes.
- Smoke no painel: criação de quadra, modalidade, janela de agenda, bloqueio, upload de foto, aprovação e serving autenticado, sem erros de console.
- CSP do build validada com `img-src 'self' data: blob:`; `pnpm build` falha se a política regredir.

## Pendências abertas

- **12B — KYC/recebedor:** bloqueada por decisão de PSP, contrato, ambiente sandbox e revisão jurídica. Não iniciar sem essas definições.
- **Storage de produção:** provedor de objetos, criptografia, backup, retenção e limpeza de órfãos.
- **Revisão independente de fotos:** revisão, denúncia e moderação de foto pertencem à Fase 17.
- **UI mobile de descoberta:** exibir quadras e fotos aprovadas no aplicativo do jogador.
- **Reservas e cobrança:** pertencem à Fase 13 e seguintes.

## Aprovação e condição de parada

A 12A foi concluída e validada localmente. A 12B só começa após decisão e contrato de PSP e autorização explícita. Ao cumprir ou ficar bloqueada, parar e reportar. Não iniciar a Fase 13 automaticamente.
