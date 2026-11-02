# Registro de execução das fases

Este arquivo registra fatos observados, não intenções. Só marcar uma fase como `Complete` após executar e comprovar seus critérios de aceite.

| Fase | Status | Branch | Evidências | Bloqueios |
|---|---|---|---|---|
| 0 — Repositório e governança | Complete | `main` | Documentação governada; remoto local e GitHub confirmam `kramirodev/Joga`; critérios da Fase 0 verificados | — |
| 1 — Prova técnica mobile/nativa | In progress | `feat/01-prova-mobile-nativa` | Bundle JOGA abriu no Moto G24 via Expo Go; leitura foreground `fine` executada; TypeScript e compatibilidade Expo passaram; achados em ADR 0006 | Android SDK/build nativo, iOS/Xcode, approximate/denied, passkeys/domínio, SMS e comparação CLI pendentes |
| 2 — Fundação de engenharia | Not started | — | — | — |
| 3 — Identidade e segurança | Not started | — | — | — |
| 4 — Perfil e descoberta | Not started | — | — | — |
| 5 — Filas e matchmaking | Not started | — | — | — |
| 6 — Ciclo de partidas | Not started | — | — | — |
| 7 — Resultados e disputas | Not started | — | — | — |
| 8 — Sistema competitivo | Not started | — | — | — |
| 9 — Comunicação em tempo real | Not started | — | — | — |
| 10 — Hardening e piloto | Not started | — | — | — |

## Histórico append-only

Adicionar abaixo uma entrada por execução concluída ou bloqueada, sem apagar evidência anterior.

### 2026-11-01 — Fase 0 (execução documental)

- **Fato observado:** `git status --short --branch` inicialmente indicou `main...origin/main` sem mudanças locais.
- **Alterações documentais:** ponto de entrada `README.md`; guia complementar `README_INICIO.md`; escopo/aceite da Fase 0 em `PLANS.md`; resumo de roadmap, início por fase e mapa de pendências em `docs/DOCUMENTACAO_TECNICA.md`; ADR em `docs/ADR/0001-repositorio-v2-e-roadmap.md`; ficha em `harness/build/phase-00-repositorio-e-governanca.md`.
- **Validação:** `git diff --check` executado sem erros de whitespace; busca de consistência confirmou a referência normativa a `PLANS.md` e as fases responsáveis; revisão do diff confirmou apenas alterações documentais e nenhuma credencial real adicionada. Corrigida também a referência antiga que exigia registro do domínio desde a Fase 0.
- **Status naquele registro:** `In progress`; à época, o destino remoto ainda não havia sido confirmado. A atualização posterior de nome/repositório e a evidência atual estão registradas na entrada seguinte. A preservação do projeto anterior continuou sem verificação.
- **Limites respeitados:** nenhuma implementação, dependência, Docker, CI funcional, banco, endpoint, ação GitHub ou alteração no projeto antigo foi executada.

### 2026-11-01 — Atualização de nome e repositório

- **Informado pelo usuário:** nome do produto atualizado para Joga; repositório criado e vinculado em `https://github.com/kramirodev/Joga`.
- **Verificado localmente:** `git remote -v` mostra `origin` com esse URL para fetch e push; branch observada `main`.
- **Ação documental:** corrigir branding e referência de destino, registrar a decisão em ADR 0002 e remover o provisionamento do repositório da lista de pendências.
- **Resultado naquele momento:** referências ativas passaram a usar Joga e a correspondência de `origin` foi confirmada. O status da Fase 0 foi registrado como `In progress` devido a um critério provisório que depois foi revogado.
- **Correção posterior:** não há critério de aceite ou pendência relativo a auditar, preservar operacionalmente ou verificar o projeto independente. A Fase 0 foi concluída conforme registro de 2026-11-02.

### 2026-11-01 — Correção de escopo e independência do JOGA

- **Registro histórico:** houve uma decisão intermediária de nome e destino que foi substituída posteriormente. Ela não representa a decisão vigente do produto.
- **Correção:** referências anteriores a preservar/verificar operacionalmente ou depender do projeto anterior ficam supersedidas e não são critérios de aceite nem bloqueios da Fase 0.
- **Estado local observado:** o `origin` deste checkout documental continua apontando para `kramirodev/Joga`; não foi alterado. Esse checkout não é considerado o destino da V2.
- **Status posterior:** o repositório vigente foi confirmado em decisão posterior; nenhuma ação remota foi feita nesta entrada histórica.

### 2026-11-01 — Decisão intermediária de nome e destino

- **Decisão intermediária registrada:** nome JOGA; destino ainda constava como decisão provisória e foi depois substituído pela decisão confirmada em ADR 0005.
- **Ação documental:** atualizar referências ativas para JOGA e registrar a decisão em ADR 0004.
- **Status posterior:** o nome e o repositório foram confirmados pelas ADRs 0004 e 0005; esta decisão intermediária não é fonte vigente.
- **Limites daquela entrada:** nenhuma ação no GitHub; nenhum conteúdo ou remoto alterado.

### 2026-11-02 — Encerramento da Fase 0 e início da Fase 1

- **Decisão vigente confirmada pelo usuário:** produto JOGA; repositório exclusivo `kramirodev/Joga`.
- **Fase 0:** concluída. O remoto local e a API somente leitura do GitHub confirmam o repositório e seu nome. README e documentos de governança estão preparados; critérios antigos de preservação do projeto anterior foram removidos.
- **GitHub:** nenhum rename foi necessário, pois o repositório já se chama `Joga`; nenhuma escrita remota executada nesta verificação.
- **Fase 1:** iniciada em `feat/01-prova-mobile-nativa`; ficha atualizada e preflight local/documental feito.
- **Ambiente observado:** Node 24.22.1, pnpm 11.25.0, Java 25.0.2 e adb 1.0.31 disponíveis; `adb devices -l` não listou dispositivos. `npm`, `npx`, Android SDK local e `xcodebuild`/Xcode não foram encontrados.
- **Fontes oficiais consultadas:** Expo development builds; Android Credential Manager e Digital Asset Links; Apple Authentication Services e Associated Domains.
- **Bloqueios:** builds e execução nativos não podem ser comprovados no ambiente atual; escolha de domínio técnico e eventual uso de build cloud dependem de decisão/autorização. Não declarar suporte multiplataforma enquanto pendentes.

### 2026-11-02 — Inspeção do scaffold e preflight da Fase 1

- **Fato observado:** `mobile/` contém scaffold Expo mínimo (Expo `~58.0.22`, React Native `0.88.1`, React `19.3.0`, TypeScript `~6.0.3`) e lockfile gerado; não contém dev client, passkeys ou localização. Nenhuma prova de build decorre apenas desses arquivos.
- **Ambiente:** Node `24.22.1`, pnpm `11.25.0`, Java `25.0.2`, adb `1.0.31`; não encontrados npm/npx, Android SDK, emulador, aparelho Android conectado, macOS ou Xcode. `adb devices -l` retornou lista vazia.
- **Comandos:** `Get-ChildItem -Recurse mobile`; leituras de `mobile/AGENTS.md`, `package.json`, `app.json`, `App.tsx`, `tsconfig.json`; `Get-Command ...`; `adb devices -l`; tentativas de `pnpm install --lockfile-only --ignore-scripts`.
- **Resultado do registry:** a primeira tentativa recebeu EACCES no sandbox. Com acesso de registry aprovado, `pnpm install --lockfile-only --ignore-scripts` gerou `mobile/pnpm-lock.yaml`, sem instalar dependências ou criar `node_modules`.
- **Registro:** ADR 0006 documenta evidências provisórias, não decide framework/biblioteca e explicita as provas faltantes.
- **Status:** Fase 1 em andamento e bloqueada para as provas nativas até haver toolchains/dispositivos ou ambiente cloud autorizado; domínio e hospedagem não foram comprados, registrados ou configurados. Nenhum serviço externo além do registry foi acessado.

### 2026-11-01 — Moto G24 e prova foreground Android

- **Acesso ao aparelho:** o Moto G24 (`moto_g24`, Android 14) foi autorizado pelo usuário para depuração USB. A primeira resposta ADB ficou `unauthorized`; após a confirmação RSA do usuário, passou a `device`.
- **ADB:** o `adb` inicialmente disponível era `1.0.31` e não suportou `adb reverse`. Baixado do site oficial Android o Platform-Tools `37.0.1` (ADB `1.0.41`) para `.tools/`, diretório ignorado pelo Git; nenhum binário foi instalado globalmente. `adb reverse tcp:8081 tcp:8081` funcionou.
- **Expo/Metro:** o primeiro servidor respondeu HTTP 500 por falta de acesso à pasta `.expo` no perfil pessoal. Reiniciado com estado do Expo em `%TEMP%\joga-expo-home` e telemetria desativada; `/status` retornou `packager-status:running`, `/` respondeu HTTP 200, Metro compilou `index.ts` (721 módulos) e Expo Go abriu `ExperienceActivity`.
- **Correção de scaffold:** instalado `expo-location ~58.0.20` por `pnpm exec expo install`; atualizados `mobile/App.tsx` e `mobile/app.json` para tela de prova de permissão foreground e leitura única. A configuração contém permissões coarse/fine, mensagem de localização durante busca e nenhuma permissão/background task.
- **Validação:** `pnpm install --frozen-lockfile --network-concurrency=3 --fetch-timeout=600000` concluiu; `pnpm exec tsc --noEmit` passou; `pnpm exec expo config --type public --json` listou as permissões coarse/fine; bundle compilou e textos da tela foram confirmados no Moto.
- **Resultado de localização:** estado reportado `fine`; leitura única concluída com precisão estimada de `100 m`. Latitude/longitude não foram mostradas nem persistidas. A autorização pertence ao host Expo Go nesta prova. Estados approximate e denied ainda não foram exercitados.
- **Pendências:** mesmo com o cache DotSlash redirecionado para `%TEMP%\joga-dotslash-cache`, o Expo DevTools não conseguiu buscar a versão mais recente por rede e usou fallback; Metro/app continuaram operacionais. Sem Android SDK não foi feito development build; iOS/Xcode, passkey/domínio, SMS, localização aproximada/negada e comparação prática com React Native CLI permanecem pendentes.
- **Limites:** nenhum commit/push/ação GitHub; nenhum domínio/serviço pago; nenhuma fase posterior iniciada.
