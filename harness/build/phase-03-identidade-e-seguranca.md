# Fase 03 — Identidade e segurança

**Status:** Complete — backend e Android concluídos; iOS bloqueado e formalmente aceito no ADR 0017
**Branch:** `feat/03-identidade-e-seguranca` (empilhada sobre `feat/01-passkeys-credential-manager`)
**Decisão de sequenciamento:** `docs/ADR/0012-inicio-fase-3-com-pendencia-ios.md`
**Decisão de encerramento:** `docs/ADR/0017-encerramento-fase-3-com-ios-aceito.md`
**Data de início:** 2026-11-03
**Data de conclusão:** 2026-11-03
**Integração:** CI verde nos runs [41599704881](https://github.com/kramirodev/Joga/actions/runs/41599704881) (Fase 1), [41599705103](https://github.com/kramirodev/Joga/actions/runs/41599705103) (Fase 3), [41599901863](https://github.com/kramirodev/Joga/actions/runs/41599901863) (`main` em `f77f77f`) e [41600011091](https://github.com/kramirodev/Joga/actions/runs/41600011091) (`main` em `fdd7fe3`); `main` integrado em `fdd7fe3`.

## Fontes e contexto

- `AGENTS.md`, `GOALS.md`, `PLANS.md` (Fase 3)
- `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md`
- `docs/JOGA_DOCUMENTACAO_TECNICA.md` §5 (identidade), §18 (modelo), §19 (API), §20 (segurança), §23 (testes) e §26 (pendências)
- `docs/ADR/0009-estrategia-react-native-expo-vs-cli.md`
- `docs/ADR/0011-prova-passkey-credential-manager.md`
- `docs/ADR/0012-inicio-fase-3-com-pendencia-ios.md`
- `docs/ADR/0013-sessoes-e-tokens.md`, `0014-webauthn-no-backend.md`, `0015-recibo-de-verificacao-de-telefone.md`, `0016-troca-de-telefone.md`, `0017-encerramento-fase-3-com-ios-aceito.md`
- `harness/build-log.md`
- `harness/build/phase-01-prova-tecnica-mobile-nativa.md`
- `harness/build/phase-02-fundacao-de-engenharia.md`

## Objetivo

Entregar identidade e autenticação verificáveis no backend: telefone E.164, OTP de uso único com limites, passkey verificada no servidor, sessões com refresh rotativo e revogável, dispositivos, logout, recuperação e troca de telefone segura — sem depender de provedor real de SMS.

## Escopo da fase

- Telefone normalizado em E.164, armazenado apenas como hash/HMAC para busca; sem telefone em texto puro nem em logs.
- Desafios OTP de uso único, com expiração, limite de tentativas, intervalo de reenvio e limites por telefone/IP/dispositivo/operação.
- Adaptador de SMS simulado no desenvolvimento e nos testes; nenhum provedor real sem autorização.
- Passkeys verificadas no backend: desafio de uso única, RP ID, origem, flags, assinatura, múltiplas credenciais e revogação.
- Access token curto; refresh opaco, aleatório, armazenado como hash, rotacionado a cada uso e revogável por família.
- Dispositivos, logout da sessão atual e de todas, revogação e reação a reutilização de refresh.
- Recuperação de conta de risco elevado sem SMS como único fator e troca de telefone com reautenticação.
- Auditoria e eventos de segurança sem PII/segredos.
- Fluxo demonstrável no app Android; iOS conforme disponibilidade.

## Iteração 1 (autorizada em 2026-11-03)

- Ficha da Fase 3, ADR de abertura e ADRs propostos de tokens e WebAuthn.
- `docs/DATA_MODEL.md` com o subconjunto de identidade.
- Modelos SQLAlchemy e migração Alembic reversível para: `users`, `user_phones`, `phone_challenges`, `devices`, `passkey_credentials`, `sessions`, `security_events` e `audit_logs`.
- Serviço de desafio de telefone/OTP com:
  - normalização E.164;
  - hash HMAC de telefone, IP e OTP;
  - expiração, tentativas, intervalo de reenvio e limite por hora;
  - uso único e comparação em tempo constante;
  - adaptador de SMS em memória para desenvolvimento/teste.
- Testes unitários do serviço e das constraints básicas em SQLite.
- Sem endpoints HTTP, sem passkey no backend, sem sessões e sem mobile nesta iteração.

## Fora do escopo

- Perfil esportivo, modalidades, disponibilidade, matchmaking, partidas, ranking, chat e clãs.
- Provedor real de SMS, envio de mensagens, custos e contratos.
- Painel web, lojas, marketplace, pagamentos e reservas.
- EAS Build, publicação em loja e OTA.
- SMS como único fator de recuperação.
- OTP, token de refresh ou telefone em texto puro.
- Alterar a estratégia mobile aprovada no ADR 0009.

## Pré-requisitos e dependências

- Fase 2 concluída (`489fe8d`).
- Decisão de iniciar a Fase 3 com a Fase 1 `In progress` (ADR 0012).
- Nenhum provedor de SMS autorizado; usar adaptador simulado.
- Docker disponível; PostgreSQL/PostGIS local validado em `127.0.0.1:5434`.
- iOS/AASA segue bloqueado por conta Apple e macOS/Xcode.

## Arquivos/componentes esperados

- `backend/app/infrastructure/database/base.py` e `dependency.py`
- `backend/app/modules/identity/{models,phone,sms,otp,events,accounts,sessions,tokens,devices,cleanup,passkeys,phone_change,clock}.py`
- `backend/app/api/v1/auth.py`
- `backend/migrations/versions/<revisão>_identity_foundation.py`, `<revisão>_add_session_access_and_receipt.py` e `<revisão>_add_passkey_challenges.py`
- `backend/migrations/env.py` (metadata dos modelos)
- `backend/app/core/config.py` e `backend/.env.example`
- `backend/tests/test_identity_*.py`, `test_auth_api.py`, `test_auth_flow_api.py`, `test_passkey_api.py`, `test_phone_change_api.py`, `test_devices_api.py`, `test_cleanup.py`
- `backend/scripts/cleanup_identity.py`
- `mobile/src/api.ts`, `mobile/src/session.ts`, `mobile/src/IdentityPanel.tsx`
- `mobile/modules/passkey-proof` (funções com request JSON do backend)
- `docs/DATA_MODEL.md`
- `docs/ADR/0012-*`, `0013-*`, `0014-*`, `0015-*`, `0016-*`, `0017-*`
- `harness/build-log.md`

## Riscos e decisões pendentes

- **iOS:** bloqueio formalmente aceito no ADR 0017; AASA/build/cerimônia iOS continuam não executados e são risco para uma fase futura.
- **E.164:** o serviço aceita apenas números já em E.164 (`+` e 8–15 dígitos). Conversão de formato nacional exige biblioteca dedicada e decisão posterior.
- **Telefone em repouso:** só existe hash de busca; armazenamento cifrado do número para contato futuro será decidido antes de notificações/recuperação assistida.
- **WebAuthn:** ADR 0014 aprovado no MVP com `webauthn==3.0.1`; verificado com autenticador sintético, PostgreSQL e passkey real do app Android. A origem Android depende do certificado de debug e muda em release/EAS; o RP ID precisa permanecer estável.
- **Desafios de passkey:** há limite de criação por IP/hora; tentativas de verificação ainda dependem do desafio/credencial e do rate limit global.
- **Tokens:** ADR 0013 aprovado para o MVP com access/refresh opacos (consulta ao banco por requisição) e HMAC no servidor; requer ratificação para produção.
- **Vínculo de dispositivo:** endpoints e vínculo de sessão implementados; o app envia nome/plataforma, mas ainda não há atestação de dispositivo.
- **Custo do access opaco:** cada requisição autenticada consulta a sessão no banco; aceitável no MVP e candidato a cache/Redis quando houver necessidade comprovada.
- **Limpeza/retenção:** o script `cleanup_identity.py` existe, mas o agendamento em produção e a política final de retenção ainda precisam ser definidos.
- **Rate limiting por IP/dispositivo:** limites de criação por telefone/IP existem; verificação e múltiplos processos ainda dependem de uma camada global.
- **IP atrás de proxy:** o endpoint usa `request.client.host`; atrás de proxy reverso, é preciso configurar proxies confiáveis para não limitar todos os usuários pelo IP do proxy.
- **Envio antes do commit:** o adaptador recebe o código antes do commit da transação; falha de commit após o envio pode entregar um código sem desafio persistido. Em produção, usar Outbox/confirmação do provedor.
- **Recuperação:** implementada como login por passkey + troca de telefone autenticada; perder todas as passkeys e o telefone exige suporte humano.
- **Troca de telefone:** revoga todas as sessões; o número antigo liberado pode ser reciclado pela operadora e não deve recuperar a conta antiga.
- **Concorrência:** `FOR UPDATE`/advisory lock foram exercitados em PostgreSQL real para criação, verificação e rotação de refresh; duas rotações simultâneas resultam em um sucesso e uma detecção de reutilização.
- **Identificadores:** `com.anonymous.joga` e o RP ID atual continuam provisórios.

## Plano Red / Green / Refactor / Verify

- **Red:** testes do serviço de OTP falhando para expiração, reenvio, limite por hora, tentativas, replay e hash seguro; teste de constraint para hash de telefone ativo duplicado.
- **Green:** implementação mínima do modelo, migração e serviço que satisfaz os testes.
- **Refactor:** separar normalização/hash (`phone.py`), transporte (`sms.py`) e orquestração (`otp.py`); manter funções pequenas e tipadas.
- **Verify:** `ruff check`, `ruff format --check`, `mypy app`, `pytest`, migração `upgrade`/`downgrade`/`upgrade` em PostgreSQL da CI, revisão do diff e `git diff --check`.

## Comandos reais de validação

A partir de `backend/`:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy app
python -m pytest
python -m alembic upgrade head
python -m alembic downgrade base
python -m alembic upgrade head
```

Sem Docker local, os testes de serviço usam SQLite em memória; as migrações são validadas na CI com PostgreSQL/PostGIS.

## Critérios de aceite da fase

- [x] Telefone E.164 validado e nunca armazenado em texto puro.
- [x] OTP de uso único, com hash, expiração, limite de tentativas, reenvio e limite por hora testados.
- [x] Adaptador de SMS simulado usado no desenvolvimento; nenhum provedor real contatado.
- [x] Passkey verificada no backend (registro + autenticação) com autenticador sintético, PostgreSQL e credencial real do app Android.
- [x] iOS não executado; bloqueio formalmente aceito no ADR 0017.
- [x] Refresh rotativo, revogável e com detecção de reutilização testado.
- [x] Logout, revogação, dispositivos e troca de telefone testados.
- [x] Recuperação de conta com passkey como segundo fator (login por passkey + troca de telefone) implementada e testada.
- [x] Testes de replay, expiração, força bruta, rotação e revogação passam.
- [x] Não há recurso de produto nesta fase; autorização por dono e revogação por dispositivo foram testadas.
- [x] Nenhum OTP, token, telefone completo ou coordenada em logs.
- [x] Evidências, ADRs e build log atualizados.

## Resultado da iteração 1 (2026-11-03)

- Modelo e migração aplicados em PostgreSQL/PostGIS real: `upgrade → downgrade → upgrade` concluído, PostGIS preservado.
- Serviço de OTP validado em SQLite (testes unitários) e em PostgreSQL (integração).
- Teste de concorrência: duas verificações simultâneas do mesmo desafio, apenas uma sucesso.
- Índice único parcial de telefone ativo e constraint de status exercitados em SQLite e PostgreSQL.
- Suíte: 30 testes unitários + 3 testes de integração PostgreSQL.

## Critérios de aceite da iteração 1

- [x] Ficha da Fase 3 criada.
- [x] ADR 0012 aprovado e ADRs 0013/0014 propostos.
- [x] Migração de identidade aplicável, reversível e reaplicável (inclusive em PostgreSQL real).
- [x] Constraint de hash de telefone ativo único testada em SQLite e PostgreSQL.
- [x] Serviço de OTP com hash, expiração, tentativas, reenvio e limite por hora testado.
- [x] `ruff check`, `ruff format --check`, `mypy app` e `pytest` passam no ambiente local.
- [x] `git diff --check` limpo.

## Iteração 2 — endpoints de OTP (concluída em 2026-11-03)

- `POST /api/v1/auth/phone/challenges` — cria o desafio, responde `202` com `challenge_id`, `expires_at` e `resend_after_seconds`; não revela se o telefone tem conta.
- `POST /api/v1/auth/phone/challenges/{id}/verify` — valida o código e devolve o recibo (`challenge_id`, `purpose`, `verified_at`, `receipt_expires_at`).
- Erros genéricos para desafio inválido/expirado/bloqueado (`400 invalid_code_or_challenge`), `400 invalid_phone` e `429 rate_limited` com `Retry-After`.
- Limite por IP por hora (`JOGA_OTP_MAX_PER_IP_PER_HOUR`, padrão 20) além dos limites por telefone.
- `security_events` registra solicitação, verificação, falha e bloqueio, sem telefone/OTP/IP em claro.
- Serialização por telefone e por IP no PostgreSQL com `pg_advisory_xact_lock`; a verificação usa `FOR UPDATE`.
- Adaptador de SMS simulado; em ambiente fora de `local/test/development/ci`, o endpoint responde `503 sms_provider_unavailable`.
- Recibo de verificação documentado no ADR 0015 (TTL de 600 s, uso único, não é sessão).

Critérios da iteração 2:

- [x] Endpoints implementados e documentados no OpenAPI.
- [x] Limite por IP e por telefone testados.
- [x] Eventos de segurança sem PII.
- [x] Recibo de verificação com janela de validade.
- [x] Concorrência de criação e de verificação exercitada em PostgreSQL.
- [x] Smoke HTTP com uvicorn + PostgreSQL real: `202`, `429` com `Retry-After` e `400 invalid_phone`; eventos persistidos e nenhum telefone em claro.
- [x] 38 testes de unidade/API + 4 de integração PostgreSQL.
- [ ] Limite de tentativas de verificação por IP (será tratado com rate limit global; hoje só há limite por desafio).

## Iteração 3 — contas e sessões (concluída em 2026-11-03)

- `POST /api/v1/auth/registration` consome recibo de registro, cria `users` + `user_phones` verificados e emite sessão.
- `POST /api/v1/auth/login` consome recibo de login de conta existente e emite sessão.
- Access e refresh são tokens opacos; `sessions` guarda apenas HMAC. Access expira em 10 min; refresh tem 30 dias absolutos e 7 dias de inatividade.
- `POST /api/v1/auth/refresh` rotaciona; reutilização de refresh rotacionado revoga toda a família.
- `GET /api/v1/auth/me`, `POST /api/v1/auth/logout` e `POST /api/v1/auth/logout-all`.
- Migração `d4a7f2c9e610` adiciona `sessions.access_token_hash`, `sessions.access_expires_at` e `phone_challenges.receipt_used_at`.
- Eventos `auth.registration_completed`, `auth.login_completed`, `auth.refresh_rotated`, `auth.refresh_reuse_detected`, `auth.logout` e `auth.logout_all`, sem tokens.
- Smoke completo em PostgreSQL real: challenge 202 → verify 200 → register 201 → me 200 → refresh 200 → access antigo 401 → logout 204 → me 401.

Critérios da iteração 3:

- [x] Cadastro e login consomem recibo de uso único.
- [x] Sessões com access/refresh opacos, armazenados como HMAC.
- [x] Rotação de refresh e detecção de reutilização com revogação da família.
- [x] Logout, logout de todos e consulta da conta autenticada.
- [x] Migração reversível e smoke em PostgreSQL real.
- [x] 64 testes de unidade/API + 5 de integração PostgreSQL (69 com `JOGA_TEST_DATABASE_URL`).
- [ ] BOLA/acesso entre contas em recursos de produto (não há recurso de produto nesta fase).
- [ ] Recuperação e troca de telefone.

## Iteração 4 — troca de telefone (concluída em 2026-11-03)

- `POST /api/v1/auth/phone-change/challenges` (autenticado) cria desafio OTP no novo número e recusa número igual ou já vinculado a outra conta.
- `POST /api/v1/auth/phone-change` (autenticado) valida desafio do próprio usuário + OTP, libera o telefone antigo, grava o novo como verificado/primário, marca o recibo como usado e revoga todas as sessões.
- O endpoint público de desafio aceita apenas `registration` e `login`; `phone_change`/`recovery` não podem ser criados sem autenticação.
- Erros: `400 invalid_phone_change`, `400 phone_unchanged`, `409 phone_already_registered`; eventos sem telefone.
- ADR 0016 registra a decisão. Nenhuma migração nova: usa `user_phones.released_at` e `phone_challenges.receipt_used_at`.

Critérios da iteração 4:

- [x] Troca exige sessão autenticada.
- [x] OTP no novo número, vinculado ao usuário e com recibo de uso único.
- [x] Telefone antigo liberado e novo verificado/primário.
- [x] Todas as sessões revogadas após a troca.
- [x] Outro usuário não consegue confirmar a troca.
- [x] 72 testes de unidade/API + 5 de integração PostgreSQL (77 com `JOGA_TEST_DATABASE_URL`).
- [ ] Recuperação de conta (exige segundo fator forte; passkey).

## Iteração 5 — passkeys no backend (concluída em 2026-11-03)

- Dependência `webauthn==3.0.1` (py_webauthn) fixada; desafios persistidos em `passkey_challenges` (migração `a7c3e9f2b415`).
- `POST /api/v1/auth/passkeys/registration/options` e `/registration/verify` (autenticados) registram credencial pública.
- `POST /api/v1/auth/passkeys/authentication/options` e `/authentication/verify` (públicos) fazem login por passkey descobrível e emitem sessão.
- `GET /api/v1/auth/passkeys` lista credenciais; `DELETE /api/v1/auth/passkeys/{credential_id}` revoga.
- Verificação de RP ID, origem Android/web, flags, assinatura, contador de assinatura e desafio de uso único.
- Origem Android derivada do certificado de debug da prova; RP ID `joga-passkeys.vercel.app`.
- Testes com autenticador sintético P-256 (atestação `none`) e smoke completo em PostgreSQL real.
- ADR 0014 atualizado para aprovado no MVP, com `webauthn==3.0.1`.

Critérios da iteração 5:

- [x] Registro de passkey com desafio de uso único e verificação de atestação.
- [x] Login por passkey com verificação de asserção e emissão de sessão.
- [x] Listagem e revogação de credenciais por dono.
- [x] Contador de assinatura regressivo rejeitado.
- [x] Testes com autenticador sintético e PostgreSQL real.
- [x] Credencial gerada pelo app Android real enviada ao backend (integração mobile concluída).
- [x] iOS não executado; bloqueio aceito no ADR 0017.

## Iteração 6 — integração Android e experiência no app (concluída em 2026-11-03)

- `mobile/src/api.ts`: cliente HTTP tipado dos endpoints de identidade.
- `mobile/src/session.ts`: tokens em `expo-secure-store` (Keychain/Keystore).
- `mobile/src/IdentityPanel.tsx`: cadastro/login por OTP, sessão, passkey, logout e troca de telefone.
- Módulo nativo ganhou `createPasskeyFromRequestAsync`/`getPasskeyFromRequestAsync` para usar as opções emitidas pelo backend.
- OTP fixo apenas em desenvolvimento (`JOGA_DEV_FIXED_OTP`, rejeitado fora de local/test/development).
- Build Android `armeabi-v7a` gerado, instalado e executado no moto g(7) play.
- Evidência real: cadastro OTP `201`; passkey registrada no backend `201`; login por passkey `200`; troca de telefone `204`; login no novo número `200`; passkeys preservadas após a troca.

## Iteração 7 — dispositivos, retenção, limites e recuperação (concluída em 2026-11-03)

- `DeviceService` e endpoints `GET /auth/devices` e `DELETE /auth/devices/{id}`; sessões podem ser vinculadas a dispositivo no cadastro/login/passkey.
- Revogação de dispositivo revoga todas as sessões vinculadas.
- Script `backend/scripts/cleanup_identity.py` e serviço de limpeza de desafios, sessões e eventos antigos; retenção configurável.
- Limite de desafios de passkey por IP por hora (`JOGA_PASSKEY_MAX_PER_IP_PER_HOUR`).
- Teste automatizado de recuperação: passkey + troca de telefone, sem OTP no número antigo.
- Suíte final: 95 testes de unidade/API + 5 de integração PostgreSQL (100 com `JOGA_TEST_DATABASE_URL`).
- ADR 0017 encerra a fase com o bloqueio iOS aceito.

## Pendências para fase futura (não bloqueiam o encerramento aceito)

1. iOS: conta Apple, AASA, build e cerimônia real.
2. Provedor real de SMS, custos e política de abuso.
3. Rate limit de tentativas de verificação por IP e em múltiplos processos (Redis/API gateway).
4. Ratificação dos ADRs 0013–0017 e revisão de segurança para produção.
5. Limpeza agendada em produção e observabilidade de eventos de autenticação.

## Evidências exigidas

- Saída de `pytest`, `ruff`, `mypy` e migrações.
- Revisão do diff e `git diff --check`.
- Registro em `harness/build-log.md`.

## Aprovação e condição de parada

A Fase 3 foi autorizada pelo responsável do produto em 2026-11-03 e encerrada na mesma data, com o bloqueio iOS formalmente aceito no ADR 0017. Não iniciar a Fase 4 automaticamente.
