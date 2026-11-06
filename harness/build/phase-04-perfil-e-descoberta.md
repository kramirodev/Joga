# Fase 04 — Perfil e descoberta

**Status:** Complete (backend + Android) — validado no moto g24
**Branch:** `feat/04-perfil-e-descoberta`
**Decisão de sequenciamento:** `docs/ADR/0018-inicio-fase-4-com-pendencia-ios.md`
**Data de início:** 2026-11-03

## Fontes e contexto

- `AGENTS.md`, `GOALS.md`, `PLANS.md` (Fase 4)
- `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §6 (modalidades/formatos), §7 (localização) e §10 (locais)
- `docs/JOGA_DOCUMENTACAO_TECNICA.md` §6 (localização/privacidade), §7 (catálogo), §18 (modelo), §19 (API), §23 (testes) e §26 (pendências)
- `docs/ADR/0017-encerramento-fase-3-com-ios-aceito.md`, `docs/ADR/0018-inicio-fase-4-com-pendencia-ios.md`
- Fase 3 (`feat/03-identidade-e-seguranca`, integrada em `main`)
- `harness/build-log.md`

## Objetivo

Permitir que o jogador configure perfil esportivo, modalidades/formatos, nível autodeclarado, disponibilidade e região, e descubra locais/partidas por GPS em primeiro plano ou por região manual, com minimização de dados e autorização por recurso.

## Escopo da fase

- Perfil esportivo mínimo do jogador (sem perfil comercial).
- Catálogo de modalidades e formatos versionados, com duração oficial definida pelo produto.
- Nível inicial autodeclarado e preferência de quadra (`PUBLIC_ONLY`, `PRIVATE_ONLY`, `ANY`).
- Janelas de disponibilidade recorrentes (dia/horário/fuso) para o matchmaking futuro.
- Região manual obrigatória como alternativa ao GPS.
- Localização em primeiro plano, aproximada; sem rastreamento contínuo.
- Descoberta de locais/partidas por raio, com limites, paginação e autorização.
- Minimização: não expor coordenada residencial nem histórico de deslocamento.

## Fora do escopo

- Matchmaking, filas, formação de partidas e rating (Fase 5+).
- Reservas pagas, agenda comercial e organizações (Fases 12–15).
- Chat, amigos, clãs e moderação.
- Rastreamento em segundo plano.
- Ranking competitivo.
- Dados reais de locais/estabelecimentos sem fonte autorizada.

## Pré-requisitos e dependências

- Fase 3 `Complete` (backend + Android).
- Conta autenticada e sessão da Fase 3.
- Decisões de produto sobre formatos, nível, região e locais (ver abaixo).
- PostgreSQL/PostGIS local e CI já configurados.

## Decisões de produto tomadas em 2026-11-03

1. **Futebol 5x5:** 10 participantes (2 equipes de 5), **50 minutos de jogo + 10 minutos de intervalo = 60 minutos totais**.
2. **Vôlei:** **6x6**, 12 participantes, **60 minutos**.
3. **Nível autodeclarado:** três níveis — `beginner`, `intermediate`, `advanced`; público no perfil, sem validação competitiva.
4. **Região manual:** **CEP + raio em km**, resolvido pelo **BrasilAPI CEP v2** (público, sem chave), que retorna cidade/UF e coordenadas aproximadas; sem exigir coordenada residencial exata.
5. **Locais:** modelo e endpoint de descoberta prontos, **catálogo vazio** nesta fase; cadastro público fica para Fases 12–15 e testes usam fixtures.

## Pendências resolvidas

- ViaCEP não retorna latitude/longitude; o resolvedor escolhido é o BrasilAPI CEP v2, com timeout, cache em memória e testes com resolvedor fake.
- GPS em primeiro plano, quando usado, é arredondado e guardado apenas como centro aproximado; não há histórico de deslocamento.

## Decisões que seguem a recomendação

- Disponibilidade: janelas recorrentes por dia da semana + faixa horária, com fuso padrão `America/Sao_Paulo`.
- Visibilidade: nome de exibição, modalidades, nível e disponibilidade aproximada visíveis; telefone e coordenada exata privados.
- **Centro do raio por CEP (2026-11-03):** o centro é o ponto retornado pelo BrasilAPI para o CEP, arredondado em duas casas (~1 km), e não o centroide do município. A cidade/UF exibida é apenas rótulo; a API não devolve `lat`/`lng` e não há histórico de pontos. Escolha explícita do responsável para preservar a precisão do raio de busca.

## Implementação entregue

### Backend

- `backend/app/modules/profile/models.py`: `Sport`, `SportFormat`, `UserProfile`, `UserSportProfile`, `Availability`, `UserRegion`, `Venue`.
- `backend/app/modules/profile/service.py`: catálogo, perfil, substituição de modalidades/disponibilidade, região por CEP/GPS e descoberta (`ST_DWithin`/`ST_Distance` no PostgreSQL, haversine apenas no fallback SQLite dos testes).
- `backend/app/modules/profile/cep.py`: resolvedor BrasilAPI CEP v2 com normalização, cache em memória, timeout e `User-Agent` próprio (o provedor responde 403 ao agente padrão do `urllib`).
- `backend/app/api/v1/profile.py`: `GET /sports`, `GET|PUT /me/profile`, `PUT /me/sports`, `PUT /me/availability`, `PUT /me/region`, `PUT /me/location`, `GET /discovery/venues`.
- `backend/migrations/versions/b8d2f4a6c910_add_profile_and_discovery.py`: tabelas, constraints, índice GiST em `venues` e seeds `futebol-5x5` / `volei-6x6`.
- Configuração nova em `app/core/config.py` e `.env.example` (`JOGA_CEP_*`, `JOGA_DISCOVERY_*`, `JOGA_LOCATION_ROUND_DECIMALS`, `JOGA_DEFAULT_TIMEZONE`).

### Mobile (Android)

- `mobile/src/api.ts`: tipos de catálogo/perfil/região/local e cliente `profileApi`.
- `mobile/src/ProfilePanel.tsx`: edição de dados básicos, modalidade/nível/preferência, disponibilidade, região por CEP ou GPS e descoberta.
- `mobile/App.tsx`: renderiza `<ProfilePanel />` abaixo do painel de identidade.

## Evidências executadas

| Verificação | Resultado |
|---|---|
| Alembic `upgrade head` / `downgrade a7c3e9f2b415` / `upgrade head` | aplicado, revertido e reaplicado; head `b8d2f4a6c910` |
| Seeds | `sports` = 2, `sport_formats` = 2 (`futebol-5x5` 10/60, `volei-6x6` 12/60), `venues` = 0 |
| Índice espacial | `ix_venues_location_gist` presente em `venues` |
| Ruff / Ruff format | sem achados |
| Mypy | sem erros em 36 arquivos |
| Pytest sem PostgreSQL | 112 passed, 6 skipped |
| Pytest com `JOGA_TEST_DATABASE_URL` | 119 passed (inclui PostGIS de raio, ordenação e paginação) |
| Mobile `tsc --noEmit` | sem erros |
| Mobile ESLint | sem warnings |
| Mobile Prettier `--check` | todos os arquivos no padrão |
| Smoke HTTP real (API local + banco real) | catálogo, perfil, modalidade, disponibilidade, CEP `01001-000` → São Paulo/SP, descoberta vazia, GPS, e rejeições 400/422 |

Detalhe do smoke: autenticação por OTP fixo local, `PUT /me/region` com CEP real resolvido pelo BrasilAPI, `GET /discovery/venues` retornando `total = 0`, `PUT /me/location` trocando a fonte para `gps`; `cep inválido` → 400 `invalid_cep`, `radius_km = 500` → 422, `lat = 91` → 422.

## Critérios de aceite da fase

- [x] Perfil esportivo e preferência de quadra gravados com autorização do dono.
- [x] Catálogo versionado sem duração arbitrária; formatos só ativos após definição.
- [x] Nível autodeclarado e disponibilidade editáveis.
- [x] GPS negado/aproximado não bloqueia a busca por região manual.
- [x] Coordenadas e raio validados no servidor; raio máximo e paginação aplicados.
- [x] Consultas PostGIS com índice e limites.
- [x] Nenhuma coordenada residencial exata ou histórico exposto (resposta não devolve `lat`/`lng`; centro arredondado em duas casas).
- [x] Testes de autorização negativa, validação e fallback manual passam.
- [x] Evidências, ADRs e build log atualizados.

## Validação no aparelho e correção da agenda

O APK anterior era `armeabi-v7a` e não instalava no moto g24 (arm64, Android 14). Foi gerado um debug `arm64-v8a` com o SDK local, instalado via `adb install -r`, com `adb reverse` para 8000 e 8081.

Evidências no aparelho:

- Login/cadastro por OTP fixo real contra a API local (conta criada, sessão persistida em `expo-secure-store`).
- `PUT /me/region` com CEP `01001000` retornou São Paulo/SP e a tela exibiu `São Paulo/SP · 10 km · cep`.
- `GET /discovery/venues` retornou `0 local(is) encontrado(s) no raio atual.`
- `PUT /me/location` salvou `GPS · 10 km · gps` e a descoberta voltou a funcionar.
- Agenda semanal: 4 faixas em 3 dias (Seg 14–15, Ter 17–19, Sáb 14–15 e Sáb 18–19), remoção de uma faixa e `PUT /me/availability` 200; o banco confirmou exatamente as 3 faixas restantes.

**Correção descoberta na validação:** o painel tratava disponibilidade como um único dia + uma faixa. O backend já suportava várias janelas por dia; o painel passou a funcionar como agenda:

- rascunho local de faixas, agrupadas por dia;
- adicionar e remover faixas por dia, com validação local de formato, ordem e sobreposição;
- contador por dia nos chips (`Sáb · 2`);
- salvar envia a agenda inteira (lista vazia limpa a disponibilidade).

**Seleção em vez de digitação:** horários e raio deixaram de ser campos de texto. Início e fim abrem uma lista modal com intervalos de 30 minutos (00:00–23:30), o fim lista apenas horários depois do início, e o raio usa chips de 5/10/20/50/100 km. Continuam digitáveis apenas dados do próprio usuário: CEP (somente dígitos), nome de exibição e bio.

Teste de regressão adicionado em `backend/tests/test_profile_api.py` cobrindo várias faixas no mesmo dia e dias com quantidades diferentes.

## Pendências e limites conhecidos

- Validação no aparelho Android do `ProfilePanel` foi executada no moto g24 (arm64, Android 14); o build arm32 anterior continua não instalável nele.
- Catálogo `venues` vazio por decisão; quadras, vínculo esporte–quadra, agenda e reservas ficam para as Fases 12–15.
- BrasilAPI é dependência externa gratuita e sem SLA; falha retorna 503 `cep_unavailable`.
- Cache de CEP é por processo e não sobrevive a restart; não há rate limiting dedicado ao endpoint de região além do já existente na autenticação.
- Nenhum local real foi semeado; a descoberta permanece vazia até existir catálogo autorizado.

## Condição de parada

Fase 4 encerrada no escopo backend + Android. Não iniciar a Fase 5 sem autorização. As Fases 12–15 permanecem responsáveis por quadras, vínculo esporte–quadra, agenda e reservas.
