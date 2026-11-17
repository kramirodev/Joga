# Registro de execução das fases

Este arquivo registra fatos observados, não intenções. Só marcar uma fase como `Complete` após executar e comprovar seus critérios de aceite.

| Fase | Status | Branch | Evidências | Bloqueios |
|---|---|---|---|---|
| 0 — Repositório e governança | Complete | `main` | Documentação governada; remoto local e GitHub confirmam `kramirodev/Joga`; critérios da Fase 0 verificados | — |
| 1 — Prova técnica mobile/nativa | In progress | `feat/01-prova-mobile-nativa` | Build Android próprio instalado e executado no Moto G24 e no moto g(7) play; permissões precisa/aproximada/negada provadas; React Native CLI comparado; OTP por SMS com adapter simulado (12 testes); ADR 0009 aprovado (Expo development build); associação Android publicada em `https://joga-passkeys.vercel.app` e reconhecida pela API Digital Asset Links; cerimônia de passkey Android executada via Credential Manager (criação + autenticação, `rpIdHashMatches: true`); ADR 0011 | iOS/Xcode e associação AASA pendentes, por decisão de manter a fase em andamento |
| 2 — Fundação de engenharia | Complete | `feat/02-fundacao-engenharia` | Backend FastAPI mínimo com health live/ready, PostgreSQL/PostGIS local, migração baseline reversível, lint/formatação/tipos/testes verdes, CI verde nos dois jobs (run 41475001880) e app aberto no Moto G24 e no moto g(7) play (Android 10, 32 bits, APK nativo) | — |
| 3 — Identidade e segurança | Complete | `feat/03-identidade-e-seguranca` | ADRs 0012–0017; backend de identidade com OTP, contas, sessões, passkeys, telefone, dispositivos, recuperação e retenção; app Android integrado (OTP, passkey real, troca de telefone); 95 testes unitários/API + 5 de integração PostgreSQL | iOS/AASA bloqueado e formalmente aceito no ADR 0017; SMS real e ratificação de produção pendentes |
| 4 — Perfil e descoberta | Complete (local) | `main` | Perfil, modalidades, disponibilidade, região, descoberta PostGIS e fallback SQLite; testes de perfil e venues; validação Android | Mapas/geocodificação de produção pendentes |
| 5 — Filas e matchmaking | Complete (local) | `main` | Fila persistente, formação transacional, locks/constraints e testes de concorrência | Redis/fan-out multi-processo não necessários nesta fase |
| 6 — Ciclo de partidas | Complete (local) | `main` | Máquina de estados, confirmação, check-in, expiração e worker `advance_matches` | Piloto real pendente |
| 7 — Resultados e disputas | Complete (local) | `main` | Relatos, quórum, segunda rodada, evidência privada, disputa e revisão humana; validado com PostgreSQL local | CLI de revisão sem operadores configurados; retenção LGPD na Fase 19 |
| 8 — Sistema competitivo | Complete (local) | `main` | Glicko-2, histórico append-only, divisão, ranking e Trust Factor separado; MMR bruto não exposto | Calibração e simulações em produção pendentes |
| 9 — Comunicação em tempo real | Complete (local) | `main` | Chat de lobby, amigos, convites, bloqueios, Outbox, WebSocket e tokens de push; retenção provisória | Push real, central de notificações e fan-out multi-processo pendentes |
| 10 — Hardening e piloto | In progress | `main` | 10A (hardening local) e 10B (limites, auditoria e carga autenticada) concluídos | Piloto real depende de provedores, orçamento, infraestrutura e LGPD |
| 11 — Organizações e painel | Complete (local) | `main` | 11A (organizações, papéis, BOLA e auditoria), 11B (painel web) e 11C (CSP, testes de UI e observabilidade) | Sem deploy; painel ainda precisa das atualizações 14D |
| 12 — Quadras, agenda e KYC | In progress | `main` | 12A (quadras, modalidades, agenda, preços, bloqueios e fotos) implementada e testada | 12B (fornecedor/KYC contratual) pendente de PSP e revisão jurídica |
| 13 — Reservas e temporizadores | In progress | `main` | 13A (reservas, holds e T1/T2/T3) e 13B (painel mobile de reservas) implementados localmente | Criação automática a partir do lobby, descoberta comercial e jornada completa do app pendentes; T2 comercial pendente |
| 14 — Pagamentos Pix e reembolsos | In progress | `main` | 14A (Mercado Pago sandbox, webhook e ledger) e 14C (reembolsos, extrato e conciliação simulada) | 14B (Inter PJ, KYC, transferência real, MED e chargeback) pendente |
| 14D — Ingresso, carteira e temporada | In progress | `main` | 14D.1–14D.15 implementadas no backend: faixas, fornecedor/Pix, carteira, pacotes, quitação, devolução, temporada, trilha, passe, Pix de checkout, fechamento, estatísticas e rede | UI mobile, buckets/validade do ingresso e conciliação de `purchase_payments` pendentes |
| 15 — Interface financeira e conciliação | In progress | `main` | 15A/15B implementados como proposta técnica local: liberações, contestações, extrato, recebíveis, conciliação e aba Financeiro | Prazo de repasse real, contestação, PSP, MED, comprovantes e política financeira não aprovados |
| 16 — Clãs e troféus | In progress | `main` | Backend implementado (ADR 0046): clãs, papéis, carência, chat, denúncia, troféus e snapshot; testes locais | UI mobile e moderação completa da Fase 17 pendentes |

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

### 2026-11-02 — Reconfirmação ADB e geração do projeto Android

- **Acesso ao aparelho:** ADB 1.0.41 confirmou novamente `0087722228 device` (`moto_g24`, Android 14); `adb reverse --list` confirmou `tcp:8081 tcp:8081`.
- **Prebuild:** `pnpm exec expo prebuild --platform android --no-install` gerou `mobile/android/` (ignorado pelo Git), atualizou `mobile/app.json` e alterou os scripts `android`/`ios` para `expo run:*`. O package ID `com.anonymous.joga` veio do padrão do Expo e permanece provisório.
- **Build nativo:** `mobile/android/gradlew.bat assembleDebug` primeiro não conseguiu baixar Gradle no sandbox. Após autorização de rede, Gradle 9.4.1 foi baixado e o daemon iniciou, mas nenhuma saída de compilação foi produzida antes da interrupção da sessão. Resultado: tentativa inconclusiva, sem build nativo comprovado. Android SDK/build-tools não foram localizados.
- **Verificação:** `pnpm exec tsc --noEmit` executado novamente sem erro. A primeira repetição de `pnpm exec expo install --check` foi bloqueada por acesso de rede no sandbox; repetida com acesso de rede aprovado e estado Expo redirecionado para `%TEMP%`, terminou com `Dependencies are up to date`.
- **Status:** Fase 1 continua em andamento. A geração do projeto Android não equivale a compilação; nenhum critério pendente foi marcado como concluído.
- **Limites:** nenhuma alteração remota além do commit/push explicitamente solicitado; nenhum domínio registrado; nenhuma outra fase iniciada.
- **Ferramentas Android:** pacote oficial Windows de command-line tools `15859902` baixado para `.tools/android-sdk/cmdline-tools/latest`; SHA-256 `90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a` conferido com o publicado pelo Android. Ainda não foram instalados pacotes `platforms`/`build-tools` nem aceitas licenças Android; essa autorização legal deve vir do usuário.

### 2026-11-02 — Correção documental (sincronização com origin e alinhamento à conceitual)

- **Sincronização:** workspace fast-forward de `fcbc90d` para `42df97a` (`git fetch` + `git merge --ff-only origin/feat/01-prova-mobile-nativa`), absorvendo as edições de documentação feitas pela interface web do GitHub. O estado anterior da conceitual (blob `267b683`, commit `41a560a`) permanece preservado no histórico; cópia adicional no diretório `.tools`-equivalente externo ao repositório.
- **Referências corrigidas:** todas as referências vivas a `docs/DOCUMENTACAO_TECNICA.md` (renomeado no GitHub para `docs/JOGA_DOCUMENTACAO_TECNICA.md`) foram atualizadas em `AGENTS.md`, `PROMPTS.md`, `README.md`, `README_INICIO.md`, `harness/build/PHASE_TEMPLATE.md`, `harness/build/phase-00-repositorio-e-governanca.md` (somente linhas vigentes) e `harness/build/phase-01-prova-tecnica-mobile-nativa.md`. Linhas históricas do build-log e as linhas de comandos/situação da ficha da Fase 0 foram preservadas como registro.
- **Precedência documentada:** `AGENTS.md` agora declara a conceitual como referência máxima de produto, `PLANS.md` como fonte de ordem/escopo e a técnica como tradução em arquitetura; o arquivo antigo é marcado como não vigente.
- **GOALS.md:** escopo reconciliado com o conceito (quatro pilares), separando "fora do escopo do produto" de "fora do escopo do MVP (fases 0–10)" — marketplace/reservas de quadras deixaram de constar como excluídos do produto geral.
- **PLANS.md:** estendidas as fases 11–19 (organizações/gestão web; catálogo/estoque; pedidos/pagamentos/cumprimento; quadras/reservas; integridade comercial; clãs/troféus; moderação/Trust & Safety; publicidade; hardening final/lançamento comercial), com dependências; fase 9 passa a incluir amigos/convites/bloqueios; fase 10 marcada como núcleo esportivo.
- **Documentação técnica:** adicionadas especificações para capitães, relato/confirmação de resultado (faixa 5–10 min, votos visíveis, anulados), tolerâncias e disputas (§10.1–10.5); moderação e denúncias de usuários (§12.5); denúncias de transação, antifraude comercial e conversa comprador-vendedor (§16.5–16.6); entidades/constraints do modelo de dados; famílias de API; itens de teste; critérios de produção; pendências 15–20. Tabela de fases (§24) renumerada para espelhar `PLANS.md`.
- **Sem inventar regras:** divergência de exatamente 50%, abstenções na votação de troca de quadra, tolerância por modalidade, prazo efetivo, substituição de capitão e similares permanecem listadas como pendências (seção 26), sem decisão tomada.
- **Registro de decisão:** hierarquia documental, nome canônico e renumeração do roadmap registrados em `docs/ADR/0007-hierarquia-documental-e-roadmap.md`.

### 2026-11-02 — Decisão de desempate em 50% aprovada; correção do mobile/AGENTS.md

- **Decisão do produto:** tratada a divergência de relatos exatamente em 50% (segunda confirmação com histórico preservado; empate persistente gera análise interna e invisível que avalia relato a relato, sem média de grupo de Trust Factor, com capitães como sinal sem peso automático; desfecho por indicadores, revisão humana quando inseguro, anulação como último recurso; MMR congelado durante todo o processo). Registrada em `docs/ADR/0008-desempate-resultados-confiabilidade.md`.
- **Documentação:** texto aprovado incorporado como §9.4 da conceitual (seções 9.4/9.5 anteriores renumeradas para 9.5/9.6); técnica recebeu §10.4 (desempate/análise, com renumeração das antigas 10.4/10.5 para 10.5/10.6), remissão em §10.3, constraints e testes em §18.1/§23, critério de produção em §25 e revisão da pendência 17 em §26; `GOALS.md` e `PLANS.md` (fase 7) atualizados.
- **mobile/AGENTS.md:** substituído o template genérico por instruções coerentes com o projeto (pnpm, neutralidade Expo×CLI pendente da prova da Fase 1, restrições de escopo), encerrando o último item da auditoria documental.
- **Validação:** `git diff --check` executado; nenhuma implementação de produto iniciada; status das fases inalterado (Fase 0 `Complete`; Fase 1 `In progress`).

### 2026-11-02 — Ambiente Android confirmado; development build falhou em CMake/Ninja

- **Verificação somente leitura do ambiente:** `.tools/android-sdk` contém `platforms;android-36` e `platforms;android-37.0`, `build-tools;36.0.0` e `build-tools;37.0.0`, Platform-Tools 37.0.1, NDK 27.1.12297006 e `cmdline-tools/latest`; arquivos de licença Android estão presentes. O Moto G24 `0087722228` aparece em `adb devices -l` como `device` autorizado.
- **Runtime de build:** Node 24.22.1 portable verificado pelo SHA-256 publicado (`d2046d28c2c3dcd211ac5145c0bf30e2047ef9dfb306693c8c6e2eccd8b95fa5`); pnpm 11.25.0 via Corepack; JDK 17.0.20.1 em `.tools/temurin-17`; Gradle 9.4.1 reutilizado de `%TEMP%\joga-gradle-home`. Nenhuma instalação global ou aceitação de licença foi executada nesta sessão.
- **Build solicitado:** `pnpm exec expo run:android --no-build-cache --device 0087722228`, com `ANDROID_HOME`/`ANDROID_SDK_ROOT` apontando para `.tools/android-sdk` e `GRADLE_USER_HOME` para o cache temporário.
- **Resultado:** após 13m59s, tarefas de configuração Android, recursos/manifests, autolinking e Kotlin de `expo-modules-core` avançaram; o build falhou em `:expo-modules-core:buildCMakeDebug[arm64-v8a]`. Ninja 1.10.2 repetiu `Re-running CMake...` 100 vezes e terminou com `manifest 'build.ninja' still dirty after 100 tries`. Saída completa em `%TEMP%\joga-expo-run-android.log`. Não há `app-debug.apk`; app não foi instalado/aberto e permissões no app próprio não foram testadas.
- **Diagnóstico pós-falha:** as três listas de arquivos C++ registradas em `CMakeFiles/VerifyGlobs.cmake` correspondem aos arquivos presentes; executar `cmake -P VerifyGlobs.cmake` não reportou mismatch. A causa da regeneração repetida não foi isolada; não atribuir ainda a falha a SDK/permissões nem declarar suporte nativo validado.
- **Estado:** Fase 1 permanece `In progress`; critério de build Android ainda não atendido. Nenhum código-fonte foi editado, nenhuma dependência do projeto foi alterada, nenhum commit/push foi feito e nenhuma fase seguinte foi iniciada.
- **Validação:** `git diff --check` executado ao final desta alteração documental; nenhum segredo adicionado; nenhuma implementação de produto iniciada; status das fases inalterado (Fase 0 `Complete`; Fase 1 `In progress`).

### 2026-11-02 — Isolamento da regeneração CMake/Ninja

- **Validação do comando:** `:expo-modules-core:buildCMakeDebug[arm64-v8a] --dry-run --no-configure-on-demand` passou, confirmou o task alvo e selecionou compileSdk 37, Build Tools 37.0.0, NDK 27.1.12297006 e Kotlin 2.2.10.
- **Reprodução isolada:** task CMake real executado sem `--configure-on-demand` e sem build completo; falhou em 1m19s com o mesmo `manifest 'build.ninja' still dirty after 100 tries`. A falha, portanto, não depende da configuração sob demanda nem do fluxo completo do Expo.
- **Ninja direto:** `ninja -d explain expo-modules-v2` reproduziu o ciclo. Ninja lista `CMakeFiles/VerifyGlobs.cmake_force` (phony, sem entradas) e múltiplos arquivos de configuração CMake/NDK como dirty. Não há `GLOB mismatch`; as listas C++ conferem. O alvo sem entradas é parte do mecanismo do CMake para validar globs; a explicação por si só ainda não identifica qual dependência deixa o manifesto dirty.
- **Evidência de caminhos:** o maior caminho absoluto de objeto em `build.ninja` tem 283 caracteres; `CMAKE_OBJECT_PATH_MAX=1024`. A política Windows `LongPathsEnabled=1` está ativa, mas não foi verificado se o Ninja 1.10.2 bundled é `longPathAware`. A hora do Windows estava sincronizada por NTP, sem salto reportado. Os logs de build não contêm aviso CMake explícito de limite de caminho.
- **Conclusão provisória:** caminhos de objeto longos induzidos pelo virtual store do pnpm são a hipótese de maior aderência às evidências (há ocorrências análogas em builds Android/Windows), mas ainda não são causa comprovada. Nenhuma mudança no package manager, CMake, SDK ou configuração do projeto foi feita. Próximo teste seguro a propor: usar store virtual do pnpm em caminho curto, sem alterar lockfile/manifesto, e repetir apenas o task CMake para ver se o manifesto estabiliza.
- **Estado:** não foi gerado APK e não foram testadas permissões no app próprio. Fase 1 segue `In progress`; nenhum commit/push ou avanço de fase.

### 2026-11-02 — Causa raiz resolvida, build Android nativo concluído e permissões validadas

- **Prova da causa:** reprodução com virtual store em `C:\p` (caminho curto) compilou `expo-modules-v2` sem nenhuma reconfiguração CMake. Reproduções com store em `%TEMP%` e em `.tools` mantiveram caminhos ≥260 caracteres e falharam, mostrando que o fator decisivo é o comprimento absoluto do caminho, não o local do store em si.
- **Correção aplicada:** criado `mobile/pnpm-workspace.yaml` com `nodeLinker: hoisted`. Motivo: o Expo documenta essa configuração para pnpm (é o padrão do `create-expo-app`) e o pnpm 11 não lê `node-linker` do `.npmrc` — só de `pnpm-workspace.yaml` ou de `--config.node-linker`. `pnpm install --frozen-lockfile --offline` recompôs 492 pacotes em 1m50s sem baixar da rede e sem alterar `pnpm-lock.yaml`.
- **Efeito:** caminho de `node_modules/expo-modules-core/android` passou de 168 para 58 caracteres; maior caminho de objeto C++ de 283 para 203. `:expo-modules-core:buildCMakeDebug[arm64-v8a]` isolado passou em 5m06s com zero reconfigurações.
- **Build completo:** `pnpm exec expo run:android --device 0087722228` concluiu em 4m41s (176 tasks), gerou APK de 47,6 MB, instalou e abriu `com.anonymous.joga/.MainActivity` no Moto G24; Metro conectado por `adb reverse tcp:8081`. Bundle Android recompilado após alteração de JS.
- **Permissões no app próprio (Android, Moto G24):** precisa → `precisão fine`, leitura com 32 m; aproximada (revogado só `ACCESS_FINE_LOCATION`) → `precisão coarse`, leitura com 2000 m; negada → estado "Localização negada…" e leitura bloqueada com orientação para autorizar. Diálogo do sistema exibiu `Exata`/`Aproximada` e `Durante o uso do app`/`Apenas esta vez`/`Não permitir`. Nenhuma coordenada foi exibida ou persistida.
- **Correção de texto:** o rodapé do `App.tsx` citava o Expo Go; passou a citar o app JOGA e o recarregamento foi confirmado no aparelho. `pnpm exec tsc --noEmit` e `pnpm exec expo install --check` passaram após a alteração.
- **Limpeza:** cópias temporárias de diagnóstico removidas (`C:\p`, `%TEMP%\opencode\joga-mobile-*`, `.tools\mobile-short`, `.tools\pnpm-short`).
- **Estado:** Fase 1 segue `In progress` — Android comprovado; iOS, passkeys/domínio, SMS simulado e ADR Expo×CLI pendentes. Nenhum commit/push e nenhum avanço de fase.

### 2026-11-02 — Comparação prática Expo development build × React Native CLI

- **Objetivo:** cumprir o primeiro item pendente da Fase 1 (`PLANS.md`): comparar as duas pilhas com evidência executável e registrar a decisão em ADR próprio.
- **Projeto CLI:** `@react-native-community/cli` 20.2.0 criou um projeto com React Native 0.88.1, React 19.3.0 e template padrão (`react-native-safe-area-context`, New Architecture e Hermes habilitados). Dependências instaladas com npm, sem pods (Windows).
- **Primeira tentativa em caminho profundo:** build em `%TEMP%\opencode\rn-cli\JogaCliProof` falhou após 5m45s com `ninja: error: Stat(...RNCSafeAreaViewShadowNode.cpp.o): Filename longer than 260 characters`. A falha é do limite de caminho do Windows, não de uma pilha específica.
- **Segunda tentativa em caminho curto:** projeto recriado em `C:\prog\rncli\JogaCliProof` (raiz de 26 caracteres). `gradlew.bat assembleDebug` concluiu em 2m59s, gerou APK universal de 125,3 MB com `arm64-v8a` (31,5 MB de bibliotecas nativas), `armeabi-v7a`, `x86` e `x86_64`.
- **Execução:** APK instalado como `com.jogacliproof`; com Metro do CLI na porta 8081, o app abriu a tela "Welcome to React Native", versão 0.88.1, motor Hermes. Antes disso, o app chegou a carregar o bundle do Metro do Expo e falhou com `EventEmitter of undefined` — evidência de que os dois bundlers não são intercambiáveis e que a porta 8081 precisa ser exclusiva.
- **Comparação de configuração:** o manifesto Expo, gerado a partir de `app.json`, já continha `ACCESS_COARSE_LOCATION` e `ACCESS_FINE_LOCATION`; o manifesto do template CLI continha apenas `INTERNET`. O CLI exigiria edição manual do manifesto ou biblioteca de permissões para um requisito já previsto.
- **Comparação de artefato:** APK Expo 47,6 MB restrito a `arm64-v8a`; APK CLI 125,3 MB universal. Os tamanhos não são diretamente comparáveis porque o Expo gerou apenas a ABI do dispositivo. Tempo Expo 4m41s com cache aquecido; CLI 2m59s com cache Gradle reaproveitado — não usar como benchmark definitivo.
- **Ambiente comum:** mesmo Windows 11, Node 24.22.1, JDK 17.0.20.1, Android SDK (compileSdk 37, Build Tools 37.0.0), NDK 27.1.12297006, CMake 3.22.1, Gradle 9.4.1 e `GRADLE_USER_HOME` temporário.
- **Limpeza:** projeto CLI, caches `.cxx`/`build` e cópias em `%TEMP%` removidos; `com.jogacliproof` desinstalado; Metro do JOGA restaurado na porta 8081 e app JOGA reaberto no Moto G24.
- **Revalidação pós-reinício:** após reiniciar o PC, `adb kill-server`/`start-server` reconectou o Moto G24; `adb reverse tcp:8081 tcp:8081` e `pnpm exec expo start --dev-client` restauraram o app, que abriu com permissão `fine` preservada e o texto corrigido na tela.
- **Decisão registrada:** `docs/ADR/0009-estrategia-react-native-expo-vs-cli.md`, status **Proposta** (Expo development build com `expo prebuild`), aguardando aprovação do responsável do produto. `docs/ADR/0006-...` marcado como substituído pelo ADR 0009.
- **Estado:** Fase 1 segue `In progress`. Restam aprovação do ADR 0009, iOS (sem macOS/Xcode), passkeys/domínio (sem domínio autorizado) e SMS por adaptador simulado. Nenhum segredo, custo ou serviço externo utilizado; nenhum commit/push feito nesta execução; Fase 2 não iniciada.

### 2026-11-02 — OTP por SMS provado com adapter simulado

- **Objetivo:** cumprir o item de SMS da Fase 1 sem provedor real, credencial ou custo, exercitando o contrato de `docs/JOGA_DOCUMENTACAO_TECNICA.md` §5.3.
- **Local:** `harness/proofs/sms-otp/` (`otp.py`, `test_otp.py`, `README.md`), em Python 3.14 sem dependências externas. A pasta `backend/` não foi criada para não antecipar a Fase 2; o README explica que a lógica deve ser portada ao backend na Fase 3.
- **Contrato implementado:** normalização E.164 (aceita separadores e prefixo `00`), código de 6 dígitos, HMAC-SHA-256 com segredo de ao menos 32 bytes, validade de 5 minutos, uso único, 5 tentativas por desafio, reenvio com intervalo mínimo de 60 segundos e invalidação do desafio anterior no reenvio. `Challenge.__repr__` não expõe telefone nem código.
- **Adapter:** `SimulatedSmsAdapter` registra remetente e código apenas em memória, para o teste ler. Nenhuma rede, nenhum número real.
- **Testes:** `python -X utf8 -m unittest discover -s harness\proofs\sms-otp -v` → 12 testes, todos `ok` (normalização, hash sem código em claro, uso único, expiração, tentativas esgotadas, reenvio, desafio inexistente, não vazamento em `repr`).
- **Limites:** sem persistência, HTTP, Redis ou rate limit por IP/dispositivo; números locais sem país não são normalizados. A prova valida a lógica e o contrato, não a entrega por operadora.
- **Estado:** Fase 1 segue `In progress`. Restam aprovação do ADR 0009, iOS (sem macOS/Xcode) e passkeys/domínio (sem domínio autorizado). Nenhum segredo, custo ou serviço externo; nenhum commit/push nesta execução; Fase 2 não iniciada.

### 2026-11-02 — Bloqueios de passkeys/domínio e iOS documentados

- **Motivo:** `PLANS.md` exige registrar bloqueio quando um caminho não pode ser testado, sem declarar suporte multiplataforma completo. Os dois itens restantes dependem de decisões e ações externas ainda não autorizadas.
- **Documento criado:** `harness/build/phase-01-bloqueios-passkeys-e-ios.md`, com requisitos de RP ID/origem, `assetlinks.json` (Android), `apple-app-site-association` e entitlement `webcredentials` (iOS), identificadores provisórios e checklist de desbloqueio.
- **Passkeys:** nenhum domínio foi escolhido, registrado ou autorizado; nenhum arquivo `.well-known` foi publicado; nenhuma biblioteca de passkeys foi adicionada; nenhuma cerimônia WebAuthn foi executada. O bloqueio foi detalhado por sistema.
- **iOS:** sem macOS/Xcode e sem conta Apple Developer autorizada, não há IPA nem execução em iPhone; build cloud não foi autorizado. O bloqueio é de ambiente, não conclusão de incompatibilidade.
- **Ficha da fase:** critério de passkeys marcado como atendido pela via "bloqueios detalhados por sistema"; critério de validação real de domínio/RP permanece aberto.
- **Estado:** Fase 1 segue `In progress`; falta aprovação do ADR 0009 e a validação dependente de domínio/iOS. Nenhum commit/push; Fase 2 não iniciada.

### 2026-11-02 — ADR 0009 aprovado; Fase 1 mantida em andamento com pendências explícitas

- **Decisão do responsável do produto:** aprovada a estratégia **Expo development build com `expo prebuild`**, mantendo `android/` e `ios/` gerados e não versionados neste momento. A aprovação não cobre EAS Build, distribuição, OTA, biblioteca de passkeys nem provedor de SMS.
- **Documentos atualizados:** `docs/ADR/0009-...` passou a **Aprovado**; `docs/ADR/0006-...` permanece marcado como substituído; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §5.4, pendência 1 da §26 e §28 refletem a decisão; `mobile/AGENTS.md` deixou de tratar Expo × CLI como pendente.
- **Status da fase:** por decisão do responsável, a Fase 1 **permanece `In progress`**. A ficha da fase ganhou a seção "Pendências para conclusão", detalhando domínio/assetlinks, bundle ID/AASA, ambiente macOS/Xcode, escolha da biblioteca de passkeys e SMS real opcional.
- **Critério aberto:** apenas a validação real de domínio/RP com arquivos de associação publicados. Os demais critérios estão atendidos ou têm bloqueio documentado.
- **Condição para `Complete`:** execução dos itens de domínio/iOS ou aceite formal do responsável de que o bloqueio externo basta para encerrar a fase sem declarar suporte completo.
- **Estado:** nenhum domínio, conta Apple, build iOS, credencial ou custo foi gerado. Nenhuma fase seguinte iniciada.

### 2026-11-02 — Início da Fase 2 em paralelo à Fase 1

- **Decisão do responsável do produto:** não manter o trabalho parado nas pendências externas da Fase 1; iniciar a Fase 2 em paralelo. Registrada em `docs/ADR/0010-inicio-fase-2-com-pendencias-da-fase-1.md`, com a Fase 1 mantida `In progress` e sem declarar suporte multiplataforma.
- **Branch:** `feat/02-fundacao-engenharia`, criada a partir de `e59b46c`. Nenhum commit/push feito nesta execução.
- **Mobile — ferramentas:** `pnpm add -D eslint eslint-config-expo prettier`. O primeiro `pnpm add` falhou com `ERR_PNPM_ENOENT` ao importar `metro-source-map`; `pnpm install --frozen-lockfile` recompôs a árvore. ESLint 10.14.0 foi instalado inicialmente e quebrou `eslint-plugin-react` 7.37.5 (`contextOrFilename.getFilename is not a function`); fixado `eslint@^9` → **9.39.5**. Prettier 3.9.10. `App.tsx` passou a usar `Location.Accuracy.Balanced` (export público de `expo-location`).
- **Mobile — verificação:** `pnpm run lint` (exit 0), `pnpm run format:check` (todos os arquivos formatados), `pnpm run typecheck` (exit 0) e `pnpm exec expo install --check` (`Dependencies are up to date`).
- **Backend — estrutura:** criados `backend/app` (`api/v1`, `core`, `infrastructure/database`, `modules`), `workers/`, testes, `pyproject.toml`, `.env.example` e `requirements.lock` (45 linhas, ambiente Python 3.14.7). Dependências fixadas: FastAPI 0.162.0, Uvicorn 0.54.0, SQLAlchemy 2.1.6, psycopg 3.3.6, Alembic 1.20.1, pydantic-settings 2.16.2; ferramentas Ruff 0.17.3, Mypy 2.4.1, Pytest 9.2.0.
- **Backend — health:** `/api/v1/health/live` não toca dependências; `/api/v1/health/ready` consulta `SELECT 1` e devolve 503 genérico em falha, com log do erro. Testes cobrem sucesso, falha e ausência de vazamento de credenciais.
- **Backend — migração:** Alembic configurado para ler `JOGA_DATABASE_URL`; baseline `af763231ef2f` vazia e reversível.
- **Infra:** `infra/compose.yaml` com `postgis/postgis:16-3.4`, healthcheck e volume; `infra/postgres/init/001-extensions.sql` habilita `postgis`.
- **Conflito de portas:** 5432 já era usada pelo PostgreSQL 18 do host e 5433 por outro projeto (`matchmaking-engine-db-1`). O Compose foi movido para **5434** (configurável por `POSTGRES_PORT`) e `JOGA_DATABASE_URL` acompanhou; o container alheio não foi tocado.
- **Banco:** container `joga-postgres-1` recriado e `healthy` em 8 s; `postgis` confirmado. `alembic upgrade head` → `af763231ef2f`, `downgrade base`, `upgrade head` e `current` = `af763231ef2f (head)`.
- **API ao vivo:** Uvicorn em `127.0.0.1:8000`; `live` → `200 {"status":"ok"}`; `ready` → `200 {"status":"ok","database":"ok"}`. Segunda instância apontando para porta fechada: `ready` → `503 {"detail":{"status":"unavailable","database":"unavailable"}}` e `live` → `200`. Processos encerrados ao final.
- **Backend — verificação:** `ruff check .` sem achados, `ruff format --check .` sem alterações, `mypy app` sem erros (14 arquivos) e `pytest` com 5 testes aprovados. Permanece um aviso do Starlette sobre `httpx`/`httpx2`; dependência não alterada.
- **Lock reproduzível:** `pip install -r requirements.lock` em venv descartável instalou as 42 versões fixadas; importações confirmaram FastAPI 0.162.0, SQLAlchemy 2.1.6, Alembic 1.20.1 e psycopg 3.3.6. `pip install --dry-run --python-version 3.13 --only-binary=:all:` também terminou com exit 0, cobrindo a diferença de versão usada na CI.
- **CI:** `.github/workflows/ci.yml` com job backend (Python 3.13, serviço PostGIS em 5432, `requirements.lock`, lint, formatação, tipos, upgrade/downgrade/upgrade, testes) e job mobile (Node 24, pnpm 11.25.0, lint, formatação, tipos, `expo install --check`). **Ainda não executada no GitHub.**
- **App no aparelho:** sem Android SDK no ambiente atual, a execução foi feita com Expo Go pela rede local (`expo start --lan`; `exp://192.168.0.107:8081`). O Moto G24 (`0087722228`) abriu `ExperienceActivity`, o bundle compilou, `ReactNativeJS: Running "main"` apareceu no logcat e a captura de tela confirmou a tela de prova renderizada. Isso valida abertura do app, não um novo build nativo.
- **Documentação:** `docs/RUNBOOK.md` com pré-requisitos, portas, backend, migrações, verificações, mobile, CI e problemas conhecidos; `README.md` atualizado; ficha `harness/build/phase-02-fundacao-de-engenharia.md` criada.
- **Estado:** Fase 2 `In progress`. Falta observar a CI verde no GitHub e repetir o build nativo Android no ambiente atual. Fase 1 permanece `In progress` com as pendências externas já registradas. Nenhum segredo, custo, serviço externo, domínio ou ação de deploy.

### 2026-11-02 — Fase 1 na `main` e Fase 2 concluída com CI verde

- **Merge da Fase 1:** `origin/main` estava em `e965146`, ancestral de `e59b46c` e sem commits ausentes na branch. O merge foi fast-forward `e965146..e59b46c` e publicado em `main`; nenhum conflito ou reescrita de histórico.
- **Publicação da Fase 2:** commit `3e6c692` (`feat(foundation): bootstrap backend, local PostGIS and CI`, 41 arquivos) enviado para `feat/02-fundacao-engenharia` com tracking de `origin`.
- **CI observada:** run [41475001880](https://github.com/kramirodev/Joga/actions/runs/41475001880), commit `3e6c692`, concluída com `success`. Job `Backend (lint, tipos, migrações, testes)`: success; job `Mobile (lint, formatação, tipos)`: success. A CI exercitou o lock em Python 3.13, o serviço PostGIS em 5432 e o ciclo `upgrade`/`downgrade`/`upgrade`.
- **Critérios de aceite:** todos atendidos — app abre no Moto G24 (Expo Go), API sobe, readiness verifica o banco e falha fechado, migração baseline aplica e reverte em banco descartável, CI valida os dois projetos e `docs/RUNBOOK.md` reproduz o ambiente local.
- **Ficha e build log:** `harness/build/phase-02-fundacao-de-engenharia.md` marcada `Complete`; linha da Fase 2 na tabela atualizada. Itens não bloqueantes (repetir build nativo, Dockerfile, Dependabot, Redis) ficaram registrados como próximos passos.
- **Fase 1:** continua `In progress`; o merge não alterou o status nem as pendências externas de domínio/RP e iOS.
- **Limites:** nenhum segredo, custo, domínio, deploy ou serviço pago; nenhuma fase 3 iniciada.

### 2026-11-02 — Validação em aparelho novo (Android 10, 32 bits)

- **Aparelho:** troca de celular informada pelo usuário. Novo aparelho detectado por Platform-Tools 37.0.1 (`.tools/android-sdk/platform-tools/adb.exe`, ADB 1.0.41): `0062710182`, **moto g(7) play**, Motorola, **Android 10 (API 29)**, ABI **`armeabi-v7a`** (sem arm64), `pt-BR`, 8,5 GB livres.
- **Incompatibilidade encontrada:** o APK existente tinha apenas `arm64-v8a` e não podia ser instalado no aparelho novo; nenhum pacote `com.anonymous.joga` ou Expo Go estava presente.
- **Build 32 bits:** `gradlew.bat assembleDebug -PreactNativeArchitectures=armeabi-v7a --console=plain` em `mobile/android`, com `JAVA_HOME=.tools/temurin-17/jdk-17.0.20.1+1`, `ANDROID_HOME=.tools/android-sdk` e `GRADLE_USER_HOME=%TEMP%\joga-gradle-home`. Resultado: `BUILD SUCCESSFUL in 2m44s`, 232 tasks (76 executadas), APK de **33,3 MB** (33.254.887 bytes) com `native-code: 'armeabi-v7a'`, `minSdkVersion 24`, `targetSdkVersion 36`.
- **Instalação:** `adb install -r app-debug.apk` concluiu; `dumpsys package com.anonymous.joga` confirma `versionName=1.0.0` e `primaryCpuAbi=armeabi-v7a`.
- **Execução:** Metro iniciado com `pnpm exec expo start --dev-client --localhost --port 8081`; `adb reverse tcp:8081 tcp:8081` ativo. O aparelho estava bloqueado (AOD) e precisou de `KEYCODE_WAKEUP` + `wm dismiss-keyguard`. `MainActivity` ficou em foco, o logcat registrou `ReactNativeJS: Running "main" ... "fabric":true` e a captura de tela confirmou a tela de prova renderizada. Nenhum erro de JS.
- **Limpeza:** Metro encerrado, porta 8081 liberada e `adb reverse --remove-all` executado.
- **Estado:** Fase 2 permanece `Complete`; a evidência foi acrescentada à ficha da fase e ao RUNBOOK (build por ABI). Nenhuma alteração de código, nenhum commit de produto e nenhuma fase nova iniciada.

### 2026-11-03 — Scaffold da associação de passkeys (Android)

- **Objetivo:** preparar a parte de associação de domínio da Fase 1 antes da infraestrutura definitiva, sem criar site público e sem publicar nada.
- **Ferramenta:** `harness/proofs/passkeys/scripts/passkeys_tool.py`, sem dependências externas, com `fingerprint` (lê o SHA-256 de um APK assinado via `apksigner`), `statement` (gera o `assetlinks.json`) e `verify` (confere status 200, `Content-Type`, redirecionamento, conteúdo e a API Digital Asset Links do Google).
- **Impressão digital:** `FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C`, extraída do APK `mobile/android/app/build/outputs/apk/debug/app-debug.apk` assinado pelo keystore de debug em `mobile/android/app/debug.keystore`.
- **Arquivo gerado:** `harness/proofs/passkeys/site/.well-known/assetlinks.json`, com `com.anonymous.joga` e a relação `delegate_permission/common.get_login_creds` (a relação `handle_all_urls` é de App Links e não habilita credenciais).
- **Configurações de hospedagem:** `vercel.json` (header `application/json`), `_headers` (Cloudflare Pages), `.nojekyll` (GitHub Pages) e `README.md` com requisitos e comandos. GitHub Pages só atende em `<usuario>.github.io` na raiz; site de projeto não serve.
- **Testes:** `python -X utf8 -m unittest discover -s harness\proofs\passkeys\scripts` executou **7 testes, todos aprovados**, com servidor HTTP local e sem rede externa. `ruff check` e `ruff format --check` passaram.
- **Limites:** nada foi publicado; nenhuma conta, domínio, deploy, custo ou credencial foi acionado. O package é provisório e o certificado é a chave de debug padrão do template (SHA-1 `5E:8F:16:06:2E:A3:CD:2C:4A:0D:54:78:76:BA:A6:F3:8C:AB:F6:25`), não um segredo de produção; um build release/EAS usará outra impressão e exigirá regerar o arquivo.
- **Próximo passo bloqueado por autorização:** escolher o host, publicar `site/` e rodar `verify --origin <url> --package com.anonymous.joga`. A cerimônia de passkey/RP ID exige uma implementação mínima de Credential Manager no Android e um novo build, fora deste scaffold.
- **Estado:** Fase 1 continua `In progress`; nenhuma fase nova iniciada e nenhuma ação externa executada.

### 2026-11-03 — Publicação e validação da associação Android (Vercel)

- **Autorização:** o responsável criou a conta Vercel vinculada ao GitHub e autorizou o login pelo device flow. A CLI autenticou como `kramirodev`.
- **Publicação:** deploy de produção a partir de `harness/proofs/passkeys/site` com `npx vercel --prod --yes --project joga-passkeys --create-if-missing`. Projeto `joga-passkeys`; URL de produção **`https://joga-passkeys.vercel.app`**; deployment `joga-passkeys-e1hasexek-joga10.vercel.app`. Nenhum arquivo do projeto Vercel foi criado no repositório e nenhum segredo foi publicado.
- **Resposta HTTP:** `GET https://joga-passkeys.vercel.app/.well-known/assetlinks.json` → **HTTP 200**, `Content-Type: application/json; charset=utf-8`, `Cache-Control: public, max-age=300`, sem redirecionamento. A raiz responde 404, pois não existe site público.
- **Validação pela ferramenta:** `python -X utf8 harness\proofs\passkeys\scripts\passkeys_tool.py verify --origin https://joga-passkeys.vercel.app --package com.anonymous.joga --fingerprint FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C` → `OK: com.anonymous.joga associado a https://joga-passkeys.vercel.app`.
- **API Digital Asset Links:** `statements:list` retornou `packageName` `com.anonymous.joga` e `sha256Fingerprint` `FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C`, com source `https://joga-passkeys.vercel.app.`.
- **Escopo:** a metade de associação Android do critério está resolvida. A cerimônia de passkey via Credential Manager, a associação iOS e o build iOS continuam pendentes; a Fase 1 permanece `In progress`.
- **Git:** por decisão do responsável, nenhum commit ou push foi feito nesta etapa; o scaffold e as atualizações de documentação seguem locais.

### 2026-11-03 — Cerimônia de passkey no Android (Credential Manager)

- **Autorização:** o responsável autorizou a implementação mínima de Credential Manager e o deploy do arquivo atualizado.
- **Módulo:** `mobile/modules/passkey-proof` (Expo local module, ADR 0011), `androidx.credentials:credentials:1.6.0` + `credentials-play-services-auth:1.6.0`; funções `createPasskeyAsync`, `getPasskeyAsync` e `getPlatformSummary`; desafio local com `SecureRandom`; retorno apenas de dados públicos.
- **Integração:** `requireOptionalNativeModule('PasskeyProof')`; a tela `mobile/App.tsx` ganhou a seção "Passkey (Android)" com criação e autenticação.
- **Build:** `pnpm exec expo prebuild --platform android --no-install` recriou `android/` e manteve o mesmo `debug.keystore`/fingerprint `FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C`; `gradlew.bat :app:assembleDebug -PreactNativeArchitectures=armeabi-v7a` concluiu em 3m05s; APK de 33.946.574 bytes; `:passkey-proof:compileDebugKotlin` sem erros.
- **Instalação/execução:** `adb install -r`, Metro com `--dev-client --localhost --port 8081`, `adb reverse tcp:8081 tcp:8081`; moto g(7) play `0062710182`, Android 10 (API 29), `armeabi-v7a`.
- **Falha 1 — RP ID:** o Google Password Manager recusou com `[50152] RP ID cannot be validated` mesmo com a associação reconhecida pela API do Google e o arquivo acessível pelo aparelho (HTTP 200, `application/json`). Correção: incluir `delegate_permission/common.handle_all_urls` junto de `get_login_creds`; arquivo regerado com `--app-links-relation`, republicado na Vercel e `verify` OK.
- **Falha 2 — timeout:** com `timeout` de 60 s, o fluxo expirou (`[15] Flow has timed out.`) enquanto o PIN era digitado. Correção: 300 s no pedido de criação e de autenticação.
- **Resultado da criação:** `clientData.type` `webauthn.create`; origem `android:apk-key-hash:-sYXRdwJA3hvue3mKpYrOZ9zSPC7b4mbgzJmdZEDO5w`; `credentialId` `dKcZmRwJaD4crwZegBb6yw`.
- **Resultado da autenticação:** `clientData.type` `webauthn.get`; mesma credencial; `rpIdHashMatches: true`; `userPresent: true`; `userVerified: true`.
- **Evidências:** `harness/proofs/passkeys/evidence/android-create-result.png` e `android-get-result.png` (somente dados públicos; sem PIN nem e-mail).
- **Testes/verificações:** 8 testes da ferramenta (`unittest`), ruff check/format e `git diff --check` verdes.
- **Escopo:** a cerimônia Android está provada. Não há verificação no backend (desafio local) e o iOS continua pendente. A Fase 1 permanece `In progress`.
- **Git:** nenhum commit ou push nesta etapa.

### 2026-11-03 — Fase 3, iteração 1: identidade, migração e OTP simulado

- **Abertura:** o ADR 0012 registra o início da Fase 3 com a pendência iOS da Fase 1; a fase permanece `In progress` e não declara suporte iOS. Branch `feat/03-identidade-e-seguranca`, empilhada sobre o commit `565f854` da Fase 1.
- **ADRs propostos:** 0013 (JWT de acesso curto + refresh opaco rotativo; 10 min/30 dias/7 dias) e 0014 (`py_webauthn` para verificação WebAuthn). Ambos exigem aprovação antes dos blocos correspondentes; nenhuma dependência foi adicionada.
- **Modelo:** `backend/app/modules/identity/models.py` e a migração `3c9d51a7e2b4_identity_foundation.py` criam `users`, `user_phones`, `phone_challenges`, `devices`, `passkey_credentials`, `sessions`, `security_events` e `audit_logs`, com UUID, `timestamptz`, índice único parcial de telefone ativo e constraints de estado/finalidade.
- **OTP:** `PhoneChallengeService` normaliza E.164, guarda HMAC de telefone/IP/OTP, gera 6 dígitos com `secrets`, aplica TTL de 300 s, 5 tentativas, reenvio de 60 s e limite de 5 por hora; `RecordingSmsSender` é o adaptador simulado, sem provedor real.
- **Configuração:** `JOGA_PHONE_HASH_SECRET` (placeholder local), TTL, tentativas, reenvio e limite por hora; o valor padrão é rejeitado fora de `local/test/development/ci`.
- **Validações locais:** `ruff check`, `ruff format --check`, `mypy app` e `pytest` verdes — 30 testes. A migração foi gerada em SQL offline para PostgreSQL (`upgrade`/`downgrade`) e executada em SQLite descartável (`upgrade`/`downgrade`/`upgrade`).
- **Limitações:** Docker local desligado, então a migração ainda não rodou em PostgreSQL real nesta máquina; a CI cobre `upgrade`/`downgrade`/`upgrade` com PostGIS. E.164 exige número já internacional; telefone cifrado, endpoints, sessões, passkeys no backend e mobile ficam para as próximas iterações.
- **Git:** nenhum commit ou push nesta etapa; o working tree contém apenas os arquivos da iteração 1.

### 2026-11-03 — Fase 3, validação em PostgreSQL real e concorrência

- **Docker:** engine 29.6.2 ativa; `docker compose -f infra/compose.yaml up -d` subiu `joga-postgres-1` (`postgis/postgis:16-3.4`) na porta 5434, com healthcheck `healthy`.
- **Migração:** `alembic upgrade head` aplicou `3c9d51a7e2b4` em PostgreSQL real; `alembic downgrade base` removeu as tabelas e `alembic upgrade head` reaplicou. A extensão PostGIS permaneceu habilitada.
- **Schema verificado:** `users`, `user_phones`, `phone_challenges`, `devices`, `passkey_credentials`, `sessions`, `security_events`, `audit_logs`, `alembic_version` e `spatial_ref_sys`; índice único parcial `uq_user_phones_active_hash` e unicidades de `credential_id` e `refresh_token_hash` presentes.
- **Testes de integração:** `tests/test_identity_postgres.py` usa o schema isolado `identity_test` no banco descartável. Validou o índice parcial, a persistência de hash HMAC e a concorrência de verificação: duas sessões verificam o mesmo desafio ao mesmo tempo e apenas uma tem sucesso (`FOR UPDATE`).
- **CI:** `JOGA_TEST_DATABASE_URL` adicionado ao job de backend; o workflow já sobe PostgreSQL/PostGIS e aplica as migrações antes do pytest.
- **Resultados:** 30 testes unitários + 3 testes de integração aprovados; Ruff, formatação e Mypy verdes; `git diff --check` limpo.
- **Próximo passo:** endpoints de desafio/verificação, rate limiting por IP, eventos de segurança e recibo; sessões/passkeys dependem da aprovação dos ADRs 0013/0014.
- **Git:** nenhum commit ou push nesta etapa.

### 2026-11-03 — Fase 3, iteração 2: endpoints de OTP, limites e recibo

- **Endpoints:** `POST /api/v1/auth/phone/challenges` (202) e `POST /api/v1/auth/phone/challenges/{id}/verify` (200), com schemas explícitos e OpenAPI automático. A resposta de criação não revela se o telefone tem conta; falhas de verificação usam `400 invalid_code_or_challenge` genérico.
- **Limites:** por telefone (reenvio e hora) e por IP (hora, padrão 20). `Retry-After` nas respostas 429. Criação serializada por telefone/IP com `pg_advisory_xact_lock`; verificação usa `FOR UPDATE`.
- **Eventos de segurança:** `otp.challenge_requested`, `otp.challenge_verified`, `otp.verification_failed` e `otp.rate_limited`, sem telefone, OTP ou IP em claro.
- **Recibo:** o `challenge_id` consumido é o recibo de verificação (`verified_at` + `receipt_expires_at`, TTL de 600 s), documentado no ADR 0015; não é sessão.
- **SMS:** somente adaptador simulado em `local/test/development/ci`; fora desses ambientes o endpoint responde `503 sms_provider_unavailable`.
- **Configuração:** `JOGA_OTP_MAX_PER_IP_PER_HOUR` e `JOGA_OTP_RECEIPT_TTL_SECONDS`.
- **Testes:** 38 testes de unidade/API + 4 de integração PostgreSQL (42 com `JOGA_TEST_DATABASE_URL`; 38 + 4 ignorados sem a variável). Inclui concorrência de criação (um sucesso e um `ResendTooSoon`) e de verificação (um sucesso).
- **Smoke HTTP real:** uvicorn contra PostgreSQL 5434 — `POST` 202, repetição 429 com `Retry-After: 60` e telefone inválido 400; eventos `otp.challenge_requested` e `otp.rate_limited` persistidos; nenhum telefone em claro. Dados de fumaça removidos ao final.
- **Correção de isolamento:** a primeira versão do teste de integração usava `search_path` via `options` e acabou criando/removendo tabelas no schema `public`. Corrigido para `schema_translate_map={None: "identity_test"}`; `alembic stamp base` + `upgrade head` restaurou o schema. O `public` permaneceu intacto após a suíte corrigida.
- **Verificações:** Ruff, formatação, Mypy (23 arquivos) e `git diff --check` verdes.
- **Pendências:** fluxo de conta/sessão, passkeys no backend, recuperação, mobile, limite de tentativas de verificação por IP e tratamento de proxy confiável.
- **Git:** nenhum commit ou push nesta etapa.

### 2026-11-03 — Fase 3, iteração 3: contas e sessões

- **ADR 0013 ajustado:** access e refresh opacos (não JWT), armazenados apenas como HMAC; access de 10 min, refresh absoluto de 30 dias e inatividade de 7 dias. Revogação imediata com consulta por requisição. Status: aprovado para o MVP, pendente de ratificação para produção.
- **Cadastro/login:** `POST /api/v1/auth/registration` e `/login` consomem o recibo de verificação de uso único, criam a conta/telefone ou localizam a conta ativa e emitem sessão.
- **Sessões:** `/me`, `/refresh`, `/logout` e `/logout-all`; rotação invalida o refresh anterior; reutilização revoga toda a família; logout revoga access e refresh imediatamente.
- **Migração:** `d4a7f2c9e610` adiciona `sessions.access_token_hash`, `sessions.access_expires_at` e `phone_challenges.receipt_used_at`, aplicada e revertida em PostgreSQL real.
- **Testes:** 64 testes de unidade/API + 5 de integração PostgreSQL (69 com `JOGA_TEST_DATABASE_URL`). Inclui rotação, reutilização, logout, logout-all, expiração de access/refresh, recibo reutilizado e concorrência de rotação (um sucesso e uma detecção de reutilização).
- **Smoke real em PostgreSQL:** challenge 202 → verify 200 → register 201 → me 200 → refresh 200 → access antigo 401 → logout 204 → me 401. Dados de fumaça removidos.
- **Verificações:** Ruff, formatação, Mypy (26 arquivos) e `git diff --check` verdes.
- **Pendências:** passkeys no backend (ADR 0014), recuperação/troca de telefone, integração mobile, vínculo de dispositivo, limpeza/retenção e rate limit de verificação por IP.
- **Git:** nenhum commit ou push nesta etapa.

### 2026-11-03 — Fase 3, iteração 4: troca de telefone

- **Endpoints:** `POST /api/v1/auth/phone-change/challenges` (autenticado, 202) e `POST /api/v1/auth/phone-change` (autenticado, 204).
- **Regras:** recusa telefone igual (`400 phone_unchanged`) e telefone de outra conta (`409 phone_already_registered`); exige desafio do próprio usuário com finalidade `phone_change`; o endpoint público de desafio agora aceita apenas `registration` e `login`.
- **Efeito:** libera o telefone antigo, grava o novo como verificado/primário, marca o recibo como usado e revoga todas as sessões, incluindo a atual.
- **ADR:** 0016 registra a decisão.
- **Testes:** 72 de unidade/API + 5 de integração PostgreSQL (77 com `JOGA_TEST_DATABASE_URL`); cobre autenticação, telefone igual, telefone de outra conta, troca, revogação de sessões, código errado, outro usuário e finalidade pública.
- **Verificações:** Ruff, formatação, Mypy (27 arquivos) e `git diff --check` verdes.
- **Swagger local:** API reiniciada em `http://127.0.0.1:8000/api/docs`; OpenAPI com 12 rotas (10 de auth + 2 de health). Banco em `d4a7f2c9e610`, 10 tabelas no `public`.
- **Pendências:** recuperação com segundo fator, passkeys no backend, mobile, vínculo de dispositivo, limpeza/retenção e rate limit de verificação por IP.
- **Git:** nenhum commit ou push nesta etapa.

### 2026-11-03 — Fase 3 concluída: passkeys, integração Android e hardening

- **Passkeys no backend:** `webauthn==3.0.1`, desafios em `passkey_challenges` (migração `a7c3e9f2b415`), registro/autenticação/lista/revogação, RP ID `joga-passkeys.vercel.app`, origem Android do certificado de debug e limite de desafios por IP/hora.
- **Integração Android:** `mobile/src/api.ts`, `session.ts` (tokens em `expo-secure-store`) e `IdentityPanel.tsx`; o módulo nativo passou a aceitar as opções JSON emitidas pelo backend.
- **Evidência no aparelho (moto g(7) play, Android 10, 32 bits):** cadastro OTP 201; passkey real registrada no backend 201; login por passkey 200; troca de telefone 204; login no novo número 200; passkeys preservadas após a troca.
- **Hardening:** dispositivos e revogação de sessões por dispositivo; limpeza/retenção (`scripts/cleanup_identity.py`); recuperação automatizada via passkey + troca de telefone; OTP fixo apenas local (`JOGA_DEV_FIXED_OTP`).
- **Testes:** 95 de unidade/API + 5 de integração PostgreSQL (100 com `JOGA_TEST_DATABASE_URL`); Ruff, formatação e Mypy (31 arquivos) verdes.
- **Banco:** migração `a7c3e9f2b415` aplicada/revertida em PostgreSQL real; 11 tabelas no `public`.
- **Encerramento:** ADR 0017 aceita formalmente o bloqueio iOS; a Fase 3 é marcada `Complete` para backend + Android, sem declarar suporte iOS.
- **CI:** runs [41599704881](https://github.com/kramirodev/Joga/actions/runs/41599704881) (Fase 1), [41599705103](https://github.com/kramirodev/Joga/actions/runs/41599705103) (Fase 3), [41599901863](https://github.com/kramirodev/Joga/actions/runs/41599901863) (`main` em `f77f77f`) e [41600011091](https://github.com/kramirodev/Joga/actions/runs/41600011091) (`main` em `fdd7fe3`), todos `success`.
- **Git:** commit da feature `f77f77f`; `main` avançou por fast-forward de `489fe8d` para `f77f77f`, recebeu o registro documental `fdd7fe3` e está sincronizado com `origin/main`.

### 2026-11-03 — Fase 4: perfil, disponibilidade, região e descoberta

- **Decisões de produto:** ADR 0019 registra futebol 5x5 (50 min + 10 de intervalo = 60), vôlei 6x6 (60 min), três níveis autodeclarados, preferência de quadra `PUBLIC_ONLY`/`PRIVATE_ONLY`/`ANY`, disponibilidade semanal com fuso `America/Sao_Paulo`, região por CEP + raio via BrasilAPI e catálogo de locais vazio nesta fase.
- **Backend:** módulo `app/modules/profile` (modelos, serviço e resolvedor de CEP) e rotas `/sports`, `/me/profile`, `/me/sports`, `/me/availability`, `/me/region`, `/me/location` e `/discovery/venues`, todas autenticadas exceto o catálogo e validadas no servidor.
- **Migração:** `b8d2f4a6c910` cria `sports`, `sport_formats`, `user_profiles`, `user_sport_profiles`, `availabilities`, `user_regions` e `venues`, com constraints de duração/participantes, índice GiST espacial e seeds `futebol-5x5`/`volei-6x6`. Aplicada, revertida e reaplicada em PostgreSQL real; 18 tabelas no `public`.
- **Descoberta:** `ST_DWithin`/`ST_Distance` sobre `geography` com raio em metros e ordenação por distância no PostgreSQL; haversine apenas como fallback para SQLite nos testes. Raio máximo 100 km, página padrão 20 e limite de 50.
- **Privacidade:** a região guarda apenas centro arredondado (duas casas) e substitui o anterior, sem histórico; a resposta do perfil não devolve `lat`/`lng`; GPS em primeiro plano é opcional e o CEP é a alternativa manual.
- **Correções durante a validação:** `Settings` não é hashable e quebrava o `lru_cache` do resolvedor (teste de regressão adicionado); o BrasilAPI responde 403 ao `User-Agent` padrão do `urllib`, então o resolvedor envia agente próprio (teste de regressão adicionado).
- **Mobile (Android):** `ProfilePanel.tsx`, tipos e `profileApi` em `api.ts`, renderização em `App.tsx`; `tsc --noEmit`, ESLint e Prettier verdes.
- **Testes:** 112 sem PostgreSQL (6 ignorados) e 119 com `JOGA_TEST_DATABASE_URL`, incluindo o teste PostGIS de raio/ordenação/paginação; Ruff, formatação e Mypy (36 arquivos) verdes.
- **Smoke HTTP real:** catálogo com as durações corretas; perfil, modalidade e disponibilidade persistidos; CEP `01001-000` resolvido para São Paulo/SP; descoberta `total = 0` por catálogo vazio; troca para GPS; rejeições `400 invalid_cep`, `422` para raio 500 e latitude 91.
- **Escopo não incluído:** quadras (`venue_spaces`), vínculo esporte–quadra, agenda e reservas pertencem às Fases 11/14.
- **Git:** branch `feat/04-perfil-e-descoberta`.

### 2026-11-03 — Fase 5: fila casual e formação transacional

- **Governança:** ADR 0020 registra fila somente casual, janela de horário pela agenda do perfil (7 dias, slots de 30 min, 2 h de antecedência), balanceamento `level_v1` e MMR reservado para a Fase 8 como `mmr_v1`.
- **Modelo:** `queue_entries`, `lobbies`, `lobby_participants` e `matchmaking_runs` (migração `c5e1a7d3f208`, aplicada/revertida/reaplicada). Índice único parcial impede duas entradas ativas do mesmo usuário/formato/modo.
- **API:** `POST|GET|DELETE /api/v1/matchmaking/queue`, autenticados, com 409 para região/perfil ausentes e duplicidade, e 400 para ranqueada.
- **Worker:** `scripts/run_matchmaking.py` (rodada única ou loop) seleciona com `FOR UPDATE SKIP LOCKED`, revalida quadra/região/agenda/horário na transação e cria lobby + participantes, gravando `algorithm_version`.
- **Balanceamento:** `level_v1` minimiza a diferença de soma de níveis; a versão fica no lobby e na rodada. MMR entra depois sem mudar o schema da fila.
- **Testes:** 145 sem PostgreSQL (13 ignorados) e 158 com a variável, incluindo 2 workers concorrentes com 20 entradas (2 lobbies, 20 participantes distintos), reexecução idempotente, expiração e incompatibilidades.
- **Smoke real:** enfileirar 201, duplicado 409, ranqueada 400, estado `waiting`; worker gravou rodada `completed`/`level_v1` com 0 lobbies para um único jogador.
- **Pendências:** notificações ao parear, app mobile da fila, política `mmr_v1` e quadra real (Fases 6/8/9/14).

### 2026-11-03 — Fase 6: ciclo de partidas

- **Decisões:** confirmação de 100% com prazo de `min(formado + 24 h, início − 45 min)`; sem tolerância após o início; recusa ou prazo vencido dissolvem a partida e devolvem quem confirmou à fila mantendo a prioridade; ausente no check-in gera suplente automático com 15 min; sem suplente, cancela; capitães e penalidades adiados.
- **Modelo:** `matches`, `match_participants` e `match_state_transitions` (migração `d7f2b9c4e615`, aplicada/revertida/reaplicada). A formação da Fase 5 agora cria a partida em `PENDING_CONFIRMATION`.
- **API:** `GET /matches`, `GET /matches/{id}` e `POST /matches/{id}/confirm|decline|check-in`, restritos a participantes.
- **Worker:** `scripts/advance_matches.py` dissolve por prazo, marca `no_show`, convida suplentes, inicia com check-in completo e cancela sem suplente.
- **Testes:** 161 sem PostgreSQL e 175 com a variável; inclui 10 confirmações concorrentes gerando uma única transição `READY`, suplente completo, dissolução com prioridade e autorização negativa.
- **Correção fora do escopo:** testes de passkey dependiam do relógio real e passaram a falhar quando o horário avançou; passaram a usar `now` explícito em todas as verificações.
- **Pendências:** notificação da partida, app mobile, penalidades de no-show (Fases 8/17), capitães e resultado (Fase 7).

### 2026-11-03 — Fase 4: validação no moto g24 e agenda semanal

- **Build:** o APK da Fase 3 era `armeabi-v7a` e não instalava no moto g24 (arm64, Android 14); gerado debug `arm64-v8a` com o SDK local (`gradlew assembleDebug -PreactNativeArchitectures=arm64-v8a`), instalado com `adb install -r` e `adb reverse` para 8000/8081.
- **Aparelho:** cadastro por OTP fixo contra a API local; CEP `01001000` salvou `São Paulo/SP · 10 km · cep`; descoberta retornou `0 local(is)`; GPS salvou `GPS · 10 km · gps`.
- **Correção de produto:** disponibilidade era tratada como um único dia + faixa. O backend já aceitava várias janelas por dia; o painel virou uma agenda semanal com rascunho local, adicionar/remover faixas por dia, contador nos chips e validação de formato/ordem/sobreposição antes de salvar.
- **Evidência da agenda:** 4 faixas em 3 dias (Seg 14–15, Ter 17–19, Sáb 14–15 e Sáb 18–19), remoção de uma e `PUT /me/availability` 200; o banco confirmou as 3 faixas restantes.
- **Seleção em vez de digitação:** horários agora vêm de uma lista modal de 30 em 30 minutos (fim filtrado depois do início) e o raio virou chips de 5/10/20/50/100 km; no aparelho, Seg 19:00–19:30 foi adicionado pelos seletores e salvo, e a região por CEP foi refeita com raio 20 km (`São Paulo/SP · 20 km · cep`).
- **Testes:** `test_profile_api.py` com 10 testes, incluindo várias faixas no mesmo dia e dias com quantidades diferentes; Ruff, formatação e Mypy verdes.
- **Pendência conhecida:** o app faz polling em `/health` (sem `/api/v1`) e acumula 404 no log; corrigir em fase de hardening.
- **Decisão sobre o centro do raio por CEP:** mantido o ponto retornado pelo BrasilAPI (nível de rua), arredondado em duas casas (~1 km), em vez do centroide do município; a cidade/UF é só rótulo e a API não devolve coordenadas.

### 2026-11-05 — Revisão documental: precificação, fluxo financeiro e escopo sem marketplace

- **Decisão:** ADR 0021 registra a fórmula `TAXA = c·V + C_k + C_c·μ·S + p_t·V`, com `μ = (1 − q)/q` e `S = 1 + z·√(φ/μ)`. O antigo 1,8 passa a ser lido como fator de segurança de 95% para cancelamentos em `q = 20%`, não como markup sobre o custo total. Piso, preço variável e teto `α` foram removidos; a proteção contra prejuízo passa a ser uma regra de elegibilidade (referência de 25% e valor mínimo de R$ 100 em `q = 20%`).
- **Fluxo financeiro:** Pix individual por participante; Pagar.me Flex como primeira opção condicionada (order por reserva, cobrança por jogador, split, saldo por recebedor e `POST /transfers`); Inter como alternativa centralizada. KYC do recebedor passa a ser portão de elegibilidade. A liberação ao estabelecimento só ocorre depois da reserva confirmada e da partida realizada, com liberação automática após `N` horas e janela de disputa ainda pendentes. A interface financeira do recebedor (Res. 264/349) entra como escopo obrigatório quando houver split.
- **Escopo:** ADR 0022 remove o comércio de produtos do escopo inicial. `GOALS.md` passa a ter três pilares; `PLANS.md` Fases 11–19 foram reorganizadas em organizações/painel, quadras/agenda/KYC, reservas/temporizadores, pagamentos/reembolsos, interface financeira/conciliação, clãs, moderação, publicidade e lançamento.
- **Documentos atualizados:** `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` v3.2; `GOALS.md`; `PLANS.md`; `docs/JOGA_DOCUMENTACAO_TECNICA.md` v2.1; `docs/DATA_MODEL.md`; `docs/RUNBOOK.md`; `README.md`; `README_INICIO.md`; `mobile/AGENTS.md`; ADRs 0021 e 0022.
- **Não incluído:** nenhum código, migração, tabela, endpoint, contrato de PSP, chave, deploy ou ação externa. Nenhuma fase 7–19 foi iniciada.
- **Limitações:** as simulações usam hipóteses de `C_k`, `C_c`, `p` e `p_t`; as tarifas do Pagar.me Flex e o comportamento de saque/estorno/MED ainda precisam de confirmação formal. `N` da liberação automática e a política de cancelamento após confirmação continuam pendentes.

### 2026-11-06 — Planejamento da Fase 7: resultados, disputas e capitão provisório

- **Decisões:** relato de resultado em 10 minutos, controlado pelo backend; três resultados (`TEAM_1`, `TEAM_2`, `DRAW`); sem tolerância separada de 1–2 votos — abaixo de 50% finaliza, exatamente 50% abre segunda rodada, acima de 50% abre disputa; votos ausentes/anulados fora do denominador; capitão provisório por partidas `FINALIZED` e UUID, sem nível e sem alteração retroativa; evidência apenas textual; revisão humana por CLI; backend-only; sem MMR.
- **Documentos:** ADR 0023, `harness/build/phase-07-resultados-e-disputas.md`, `PLANS.md` Fase 7, conceito §9 e §26, técnica §10 e §26, `DATA_MODEL.md` e `RUNBOOK.md`.
- **Pontos abertos:** resultado avaliado com três opções sem maioria absoluta; quórum mínimo; empate por formato; limite da evidência; confirmação do prazo de 5 min da segunda rodada; regra para segunda rodada sem 50% exato; abrangência/momento do capitão; visibilidade dos relatos; autorização da CLI; contrato HTTP.
- **Não incluído:** nenhum código, migração, endpoint, tela, teste ou ação externa. A Fase 7 não foi iniciada.

### 2026-11-06 — Fase 7: plano finalizado para revisão

- **Regras fechadas:** quórum `ceil(elegíveis/2)` com elegíveis congelados; resultado por maioria simples (plurality); divergência de 50% sobre votos válidos; segunda rodada de 5 minutos com todas as alternativas permitidas pelo formato; sem terceira rodada; `DRAW` só no futebol 5x5; evidência textual de até 2.000 caracteres; CLI com operador autorizado e motivo.
- **Contrato HTTP:** rotas, payloads, códigos de erro, autorização, idempotência e controle de prazo documentados em `harness/build/phase-07-resultados-e-disputas.md`.
- **Modelo previsto:** rodadas, elegíveis congelados, relatos, confirmações de capitão, disputa, evidência, análise, revisão e decisão, além de `idempotency_records`.
- **Pontos pendentes:** confirmar análise interna sempre em revisão humana na Fase 7; confirmar confirmação do capitão como registro separado; definir retenção; configurar operadores da CLI.
- **Não incluído:** nenhum código, migração, endpoint, tela, teste ou ação externa. A Fase 7 não foi iniciada.

### 2026-11-06 — Fase 7 implementada localmente: resultados, disputas e capitão provisório

- **Implementado:** domínio `results` com rodadas 1/2, elegíveis congelados, relatos, confirmações de capitão, disputa, evidência textual, análise `INCONCLUSIVE`, revisão e decisão auditável; domínio `idempotency` para replay de POSTs; endpoints HTTP de resultado, relatos, confirmações e evidência; CLI `review_match_result.py`; worker `advance_matches.py` apurando rodadas; migração `e1a4c7d9b230_add_match_results.py`.
- **Regras:** prazo de 10 minutos, segunda rodada de 5 minutos, quórum `ceil(elegíveis/2)`, plurality, divergência em inteiros (abaixo de 50% finaliza, 50% abre segunda rodada, acima de 50% abre disputa), sem terceira rodada, `DRAW` só no futebol, capitão `provisional_v1` por `FINALIZED` do mesmo formato e UUID.
- **Testes:** `test_results_policy.py`, `test_results_service.py`, `test_results_api.py`, `test_review_cli.py` e `helpers_results.py`. Suíte local: 209 passed, 14 skipped (PostgreSQL sem `JOGA_TEST_DATABASE_URL`). `ruff check app scripts tests migrations` passa. Migração validada por `alembic upgrade head --sql`, sem aplicar em banco.
- **Documentos atualizados:** ADR 0023, `PLANS.md`, `GOALS.md`, `README.md`, `docs/JOGA_DOCUMENTACAO_TECNICA.md`, `docs/DATA_MODEL.md`, `docs/RUNBOOK.md`, `harness/build/phase-07-resultados-e-disputas.md` e `backend/.env.example`.
- **Desvios e limites:** rate limiting `429 rate_limited` não implementado; retenção de relatos/evidências pendente; naquele momento, testes de concorrência e migração com PostgreSQL real ainda não executados (ver entrada seguinte); `missing_idempotency_key`/`invalid_idempotency_key` são extensões ao contrato; `signals` e `response_body` usam JSONB no PostgreSQL e JSON no SQLite; `result_version` começa em 0.
- **Não incluído:** MMR/rating, telas mobile, painel administrativo, upload de arquivos, notificações, commit, push, merge ou ação externa.

### 2026-11-06 — Fase 7 validada com PostgreSQL local e concorrência real

- **Banco:** container `joga-postgres-1` (`postgis/postgis:16-3.4`) iniciado via `infra/compose.yaml`; `alembic upgrade head`, `alembic downgrade d7f2b9c4e615` e novo `alembic upgrade head` executados com sucesso no banco descartável local.
- **Testes:** suíte completa com `JOGA_TEST_DATABASE_URL` apontando para o banco local: **229 passed, 0 skips**. Sem a variável: 209 passed, 20 skipped.
- **Novo arquivo:** `backend/tests/test_results_postgres.py` com seis testes de concorrência: voto duplicado do mesmo participante, votos de participantes distintos, dois workers fechando a mesma rodada, confirmações concorrentes do capitão, abertura única da segunda rodada e decisões humanas concorrentes.
- **Correção relacionada:** os testes novos usam o `participant_id` correto ao contar relatos; a primeira versão contava por `user_id` e foi corrigida antes da validação final.
- **Observação:** `alembic check` ainda reporta divergências pré-existentes de fases anteriores (`spatial_ref_sys`, índices/constraints de sessões, perfil e locais). Nenhuma divergência foi introduzida pela migração `e1a4c7d9b230`.
- **Documentação:** ADR 0023, `PLANS.md`, `GOALS.md`, `docs/JOGA_DOCUMENTACAO_TECNICA.md`, `docs/DATA_MODEL.md`, `docs/RUNBOOK.md` e `harness/build/phase-07-resultados-e-disputas.md` atualizados com a evidência de PostgreSQL.
- **Ainda pendente:** rate limiting; retenção de relatos/evidências; revisão/commit. Nenhum MMR, tela mobile ou painel administrativo foi implementado.

### 2026-11-06 — Divergências de `alembic check` verificadas e corrigidas

- **Diagnóstico:** quatro divergências reportadas, todas anteriores à Fase 7: tabela `spatial_ref_sys` do PostGIS; índice único de `sessions.access_token_hash` versus constraint declarada no modelo; nome da constraint única de `user_sport_profiles`; índice GiST `ix_venues_location_gist` criado só por SQL na migração e ausente do modelo.
- **Classificação:** `spatial_ref_sys` é objeto de extensão e não pertence ao schema da aplicação; as demais eram diferenças reais de metadata, sem mudança de comportamento esperado; o índice GiST é intencional e específico de PostgreSQL.
- **Correções:** `migrations/env.py` passou a excluir `spatial_ref_sys` do autogenerate; `sessions` passou a declarar `uq_sessions_access_token_hash` como índice único; `user_sport_profiles` passou a usar o nome `uq_user_sport_profiles_user_format`; `venues` passou a declarar o índice GiST com expressão e `ddl_if(dialect="postgresql")`. Nenhuma migração histórica foi reescrita.
- **CI:** adicionada a etapa `python -m alembic check` após reaplicar as migrações.
- **Resultado:** `alembic check` agora retorna “No new upgrade operations detected”; `ruff check`, `ruff format --check` e `mypy app` passam; **209 passed, 20 skipped** sem PostgreSQL e **229 passed, 0 skips** com `JOGA_TEST_DATABASE_URL`.
- **Ajustes de CI encontrados na verificação:** um erro de tipagem em `results/service.py` (variável `match` reutilizada com tipos diferentes) foi corrigido, e 10 arquivos da Fase 7 foram formatados para atender `ruff format --check`.

### 2026-11-06 — Rate limiting dos POSTs de resultado

- **Implementado:** módulo `backend/app/modules/ratelimit/` com contador persistente por `scope`/`key`/janela fixa; tabela `rate_limit_counters`; migração `f2b5d8e1a7c3_add_rate_limit_counters.py`; configuração `JOGA_RESULTS_RATE_LIMIT_PER_MINUTE` (padrão 30).
- **Integração:** relatos, confirmações de capitão e evidências aplicam o limite por usuário em janela de 60 segundos. A tentativa é contabilizada e commitada antes da ação, para que requisições inválidas também consumam o limite. Excesso retorna `429 {"detail":{"code":"rate_limited"}}` com `Retry-After`.
- **Concorrência:** a linha é bloqueada com `FOR UPDATE`; criação concorrente da mesma janela é resolvida pelo índice único e tratada com savepoint. Teste PostgreSQL com 10 requisições concorrentes e limite 5 confirmou exatamente 5 permitidas e 5 bloqueadas.
- **Testes:** `test_ratelimit.py` (6), dois casos novos em `test_results_api.py` (429 com `Retry-After` e tentativa inválida consumindo o limite) e novo caso em `test_results_postgres.py` (concorrência). Sem PostgreSQL: **217 passed, 21 skipped**. Com `JOGA_TEST_DATABASE_URL`: **238 passed, 0 skips**. `ruff`, `ruff format`, `mypy` e `alembic check` passam.
- **Migração:** aplicada, revertida (`f2b5d8e1a7c3 -> e1a4c7d9b230`) e reaplicada no PostgreSQL local; `alembic check` sem divergências.
- **Pendente:** retenção dos contadores de rate limit, além da retenção já pendente de relatos, confirmações, evidências e decisões. Nenhum commit/push executado.

### 2026-11-06 — Retenção provisória dos dados de resultado

- **ADR:** `docs/ADR/0024-retencao-provisoria-resultados.md`, aprovado provisoriamente para desenvolvimento/piloto e sujeito à revisão LGPD das Fases 10/19.
- **Prazos:** contadores de rate limit 24 h; evidências 365 dias após o encerramento da disputa; relatos, confirmações, decisões, revisões e análises 730 dias após o encerramento da partida. `matches` e `match_result_rounds` são mantidos.
- **Implementação:** `backend/app/modules/results/cleanup.py` e `backend/scripts/cleanup_results.py`, com `--dry-run` e prazos configuráveis. Só remove partidas `FINALIZED`/`VOIDED` e revisões `RESOLVED`/`CANCELLED`; partidas em andamento ou com revisão pendente são preservadas.
- **Testes:** `test_results_cleanup.py` (7), cobrindo partida finalizada antiga, partida recente, partida anulada, partida ativa, prazos separados, contadores e prazo negativo. Sem PostgreSQL: **224 passed, 21 skipped**. Com `JOGA_TEST_DATABASE_URL`: **245 passed, 0 skips**. `ruff`, `ruff format`, `mypy` e `alembic check` passam.
- **Limite:** a limpeza é manual, sem agendador; a política definitiva será revista na fase de LGPD. Nenhum commit/push executado.

### 2026-11-06 — Fase 7 integrada à main

- **PRs:** #1 (documentação de precificação), #2 (Expo 58.0.23) e #3 (Fase 7) mesclados em `main`; branch final `feat/07-resultados-e-disputas` reaplicada sobre `main` antes do merge.
- **CI da main:** run `42179305339` concluído com sucesso para backend e mobile.
- **Validação final na main:** 224 passed e 21 skipped sem PostgreSQL; 245 passed com `JOGA_TEST_DATABASE_URL`; `ruff check`, `ruff format --check`, `mypy app` e `alembic check` passam.
- **Ambiente:** banco local na revisão `f2b5d8e1a7c3`; banco temporário de simulação da CI removido.
- **Pendências:** configurar `JOGA_REVIEW_OPERATORS` para usar a CLI; revisar a retenção provisória do ADR 0024 na fase de LGPD; agendar a limpeza apenas após essa revisão. Nenhuma fase comercial ou MMR foi iniciada.

### 2026-11-06 — Fase 8A: motor de rating Glicko-2 e Trust Factor oculto

- **Decisão:** ADR 0025 aprovado com Glicko-2 adaptado para equipes, MMR oculto, divisão visível, fila ranqueada com `mmr_v1`, Trust Factor neutro e sem punição automática.
- **Schema:** migração `a3f7c9e2d641_add_ratings_and_trust_events.py` cria `rating_accounts`, `rating_events`, `trust_accounts` e `trust_events`; aplicada, revertida e reaplicada no PostgreSQL local.
- **Motor:** `glicko2_team_v1` com rating inicial 1500, RD 350, volatilidade 0.06, RD máximo 350, inatividade de 7 dias, delta máximo ±100 e 5 partidas de colocação. Validação contra o exemplo canônico do Glicko-2 passou.
- **Worker:** `scripts/apply_ratings.py` aplica MMR somente em partidas `ranked`/`FINALIZED`, com constraint única por partida/usuário/versão; reexecução é idempotente.
- **Trust Factor:** score neutro 100 e eventos auditáveis; nenhuma penalidade automática na Fase 8.
- **Simulação:** 60 jogadores e 3.000 partidas produziram quartil inferior ≈1279 e superior ≈1666, mostrando convergência.
- **Testes:** `test_ratings_engine.py` (11), `test_ratings_service.py` (10) e `test_ratings_postgres.py` (1). Sem PostgreSQL: **245 passed, 22 skipped**; com `JOGA_TEST_DATABASE_URL`: **267 passed**. `ruff`, `ruff format`, `mypy` e `alembic check` passam.
- **Pendente:** 8B (fila ranqueada, ranking e endpoints) e 8C (telas mobile). Nenhuma fase seguinte foi iniciada.

### 2026-11-06 — Fase 8B: fila ranqueada, divisão e ranking

- **Ranked:** `ranked` habilitado na fila; `ranked_not_available` removido. A política `mmr_v1` ordena candidatos por proximidade de MMR e limita a dispersão interna a 800 pontos por equipe.
- **Team balance:** `balance_teams_by_rating` minimiza diferença de média e dispersão; grupos acima de 16 jogadores usam fallback guloso determinístico.
- **API:** `GET /api/v1/ratings/me` retorna divisão, progresso, colocação, posição e partidas; `GET /api/v1/rankings` retorna top 100 paginado por formato. Jogadores em colocação não entram no ranking público. Nenhum endpoint expõe MMR bruto, RD, volatilidade ou Trust Factor.
- **Testes:** `test_ratings_api.py` (6), casos de `mmr_v1` em `test_matchmaking_policy.py` (4) e caso ranked em `test_matchmaking_postgres.py` (1). Sem PostgreSQL: **256 passed, 23 skipped**; com `JOGA_TEST_DATABASE_URL`: **279 passed**. `ruff`, `ruff format`, `mypy` e `alembic check` passam.
- **Conflito de escopo mobile:** `mobile/AGENTS.md` ainda declara o app como protótipo da Fase 1 e proíbe telas de produto. A tela competitiva (8C) não foi implementada; é necessário atualizar a governança mobile antes.
- **Pendente:** 8C (mobile) e decisão de escopo correspondente. Nenhuma fase seguinte foi iniciada.

### 2026-11-06 — Fase 8C: painel competitivo mobile

- **Governança:** `mobile/AGENTS.md` atualizado para autorizar exclusivamente a tela competitiva da Fase 8C; as demais telas de produto continuam fora de escopo.
- **API mobile:** tipos `MyRating`, `RankingPage` e `ratingsApi` em `mobile/src/api.ts`.
- **Tela:** `mobile/src/CompetitivePanel.tsx`, integrada ao `App.tsx`, com seletor de formato, divisão, progresso, posição, partidas e top 50. Não exibe MMR bruto, RD, volatilidade ou Trust Factor.
- **Estados:** carregamento, erro, sessão ausente, colocação provisória e ranking vazio.
- **Validação:** `pnpm run typecheck`, `pnpm run lint`, `pnpm run format:check`, `pnpm exec expo install --check` e `expo config --type public` passam.
- **Limite:** sem teste automatizado de UI ou execução em aparelho nesta sessão; a validação visual exige development build/Expo com backend local.
- **Fase 8:** 8A, 8B e 8C concluídos. Nenhuma fase seguinte foi iniciada.

### 2026-11-06 — Smoke test mobile do painel competitivo

- **Ambiente:** moto g(7) play, Android 10, development build `com.anonymous.joga`; Metro em 8081 e API em 8000 via `adb reverse`; worker `scripts.apply_ratings.py --loop` ativo.
- **Login:** OTP local fixo com telefone de teste `+5511955554444`; sessão persistida no SecureStore.
- **Dados de teste:** contas de rating semeadas no banco local para futebol 5x5, incluindo o usuário de teste e dois rankings sintéticos.
- **Resultado observado:** painel exibiu “Platina”, progresso até Diamante, posição 2 e 10 partidas; ranking com Diamante/Platina/Ouro. Ao trocar para Vôlei, exibiu “Provisório”, 5 partidas restantes e ranking vazio. A troca de formato e a atualização funcionaram.
- **Rede:** API respondeu 200 para `/ratings/me` e `/rankings`; nenhum crash ou erro de renderização observado.
- **Limite:** é um smoke test manual em um aparelho; não substitui testes automatizados de UI ou validação em iOS.

### 2026-11-06 — Fase 9A: chat, amigos, convites, Outbox e WebSocket

- **Decisão:** ADR 0026 aprovado; WebSocket/push são canais de entrega, nunca fonte de verdade. Redis fica opcional nesta fase.
- **Schema:** migração `b4e8d1f6c752_add_social_chat_outbox.py` cria `lobby_messages`, `outbox_events`, `friendships`, `user_blocks`, `lobby_invites` e `device_push_tokens`; aplicada, revertida e reaplicada no PostgreSQL local.
- **Chat:** serviço e endpoints `GET/POST /api/v1/lobbies/{id}/messages`, com persistência antes da entrega, idempotência, paginação e autorização por participante.
- **Social:** solicitação/aceite/remoção de amizade, bloqueio, convite de lobby, aceite/recusa, limites por hora e respeito a bloqueios.
- **Outbox/WebSocket:** eventos transacionais, dispatcher e entrega local best-effort; endpoint `/api/v1/ws` autenticado e assinatura de lobby autorizada.
- **Push:** tokens por dispositivo e adaptador de teste; nenhum provedor real configurado.
- **Testes:** 25 novos testes (chat, API, social, push, Outbox, realtime e WebSocket). Sem PostgreSQL: **281 passed, 23 skipped**; com `JOGA_TEST_DATABASE_URL`: **304 passed**. `ruff`, `ruff format`, `mypy` e `alembic check` passam.
- **Limite:** fan-out multi-processo/Redis e push real permanecem para hardening; 9B mobile não iniciado.

### 2026-11-06 — Fase 9B: painel mobile de comunicação

- **Governança:** `mobile/AGENTS.md` atualizado para autorizar chat, amigos e convites da Fase 9B.
- **Backend de apoio:** `MatchSummary` passou a expor `lobby_id`, permitindo que o app selecione a sala de chat da partida.
- **API mobile:** `matchesApi`, `chatApi` e `socialApi` em `mobile/src/api.ts`.
- **Tela:** `mobile/src/CommunicationPanel.tsx`, integrada ao `App.tsx`, com seleção de partida/lobby, histórico, envio de mensagem, amigos, participantes para adicionar, convites pendentes e ações de aceitar/recusar.
- **Smoke test:** login local, chat exibindo mensagem semeada, envio de mensagem pelo app (`201`) e solicitação de amizade (`201`) observados no aparelho moto g(7) play.
- **Validação:** `pnpm run typecheck`, `pnpm run lint`, `pnpm run format:check` e `expo install --check` passam; backend com 281 passed/23 skipped sem PostgreSQL e 304 passed com a variável.
- **Limite:** o app usa atualização manual/HTTP; WebSocket nativo no mobile e testes automatizados de UI ainda não existem.

### 2026-11-06 — Fase 9C: WebSocket mobile e retenção de comunicação

- **WebSocket mobile:** `CommunicationPanel` abre o socket com `Authorization`, assina o lobby, mescla mensagens por ID e tenta reconectar após queda; o histórico continua vindo da API.
- **Retenção:** ADR 0027 e `scripts/cleanup_communication.py` com `--dry-run`; mensagens 730 dias, convites encerrados 90 dias, Outbox entregue/falha 30 dias e tokens revogados 90 dias. Eventos pendentes, convites ativos e tokens ativos são preservados.
- **Testes:** `test_communication_cleanup.py` cobre remoção e preservação; backend segue com 281 passed/23 skipped sem PostgreSQL e 304 passed com a variável. Mobile: typecheck, lint, format e Expo check passam.
- **Smoke:** chat HTTP e solicitação de amizade foram exercitados no aparelho; a validação visual do WebSocket depende de sessão válida e backend ativo.
- **Fase 9:** encerrada. Redis/fan-out, push real, LGPD definitiva e hardening ficam para a Fase 10.

### 2026-11-06 — Fase 10A: hardening backend local

- **Observabilidade:** `X-Request-ID` seguro, headers `X-Content-Type-Options`, `Referrer-Policy` e `Cache-Control`; log `joga.http` sem query string/corpo/PII. Testes em `test_observability.py`.
- **Carga:** `scripts/load_test.py`; `/health/live` 200 requisições/concorrência 20 → 0 falhas, p50 37,9 ms, p95 146,8 ms; `/sports` 100/10 → 0 falhas, p50 41,2 ms, p95 79,2 ms.
- **Backup/restore:** `pg_dump` + `pg_restore` em `joga_restore_test`; versão `b4e8d1f6c752`, 13 usuários e 1 partida restaurados; banco temporário removido.
- **Segurança:** `docs/THREAT_MODEL.md` com ativos, ameaças, controles e riscos residuais.
- **Testes:** **287 passed, 23 skipped** sem PostgreSQL e **310 passed** com a variável; `ruff`, `ruff format`, `mypy` e `alembic check` passam.
- **Bloqueios de piloto:** celular, provedores reais, orçamento, LGPD/jurídico e infraestrutura de produção. Nenhuma fase seguinte iniciada.

### 2026-11-06 — Smoke test em Android 14 (moto g24)

- **Dispositivo:** moto g24, Android 14 (API 34), APK de debug `com.anonymous.joga`; aviso de compatibilidade do Android exibido, mas o app abriu.
- **Ambiente:** Metro em 8081, API em 8000 e `adb reverse` ativos.
- **Login:** OTP local fixo com telefone de teste; sessão persistida.
- **Competitivo:** painel exibiu Platina, progresso para Diamante, posição e ranking.
- **Comunicação:** chat carregou histórico, enviou mensagem (`201`), recebeu mensagem de outro usuário via WebSocket sem atualizar, mostrou “Tempo real conectado”, reconectou após reinício da API e recebeu nova mensagem.
- **Social:** solicitação de amizade, lista de amigos e convite de lobby (`201`); aceite do convite adicionou o participante.
- **Limite:** dados de teste no banco local; sem teste automatizado de UI.

### 2026-11-06 — Fase 10B: limites, auditoria e carga autenticada

- **Payload:** `JOGA_MAX_REQUEST_BODY_BYTES` (padrão 1 MB) rejeita `Content-Length` acima do limite com `413 payload_too_large`; teste de observabilidade cobre o caso.
- **Dependências:** `pip-audit -r requirements.lock` sem vulnerabilidades conhecidas. `pnpm audit --prod` encontrou 2 vulnerabilidades moderadas transitivas (`glob`, `minimatch`) via Expo CLI; aceitas temporariamente como ferramenta de build, correção depende de atualização do SDK.
- **Carga autenticada:** 100 requisições em `/api/v1/matches`, concorrência 10, 0 falhas; p50 98,3 ms, p95 155,0 ms, p99 165,7 ms.
- **Testes:** 288 passed/23 skipped sem PostgreSQL e 311 passed com a variável; `ruff`, `ruff format`, `mypy` e `alembic check` passam.
- **Piloto:** ainda bloqueado por provedores reais, orçamento, LGPD/jurídico e infraestrutura de produção. Nenhuma fase seguinte iniciada.

### 2026-11-06 — Fase 11A: organizações, papéis, BOLA e auditoria

- **Modelo:** `organizations`, `organization_memberships` e `organization_venues`; o catálogo `venues` da Fase 4 permanece intacto. A ligação entre catálogo e perfil comercial fica para a Fase 12.
- **Autorização:** capacidades `organization:*`, `members:*`, `venues:*` e `audit:read` verificadas no servidor; `OWNER`, `ADMIN` e `OPERATOR`; último proprietário protegido; consultas sempre escopadas pela organização.
- **Auditoria:** `audit_logs.organization_id` e helper `record_audit`; criação/alteração de organização, vínculos e estabelecimentos geram eventos append-only.
- **Contratos:** endpoints versionados em `/api/v1/organizations`, com schemas explícitos e paginação de auditoria.
- **Testes:** **296 passed, 25 skipped** sem PostgreSQL e **321 passed** com `JOGA_TEST_DATABASE_URL`; 8 testes HTTP de BOLA/papéis e 2 testes PostgreSQL de unicidade/concorrência.
- **Migração:** `a1b2c3d4e5f6`; upgrade, downgrade e novo upgrade em banco descartável com PostGIS; `alembic check` sem operações pendentes.
- **Painel web:** ADR 0028 proposto (React + TypeScript + Vite, cookie HttpOnly + CSRF); implementação da 11B bloqueada até confirmação.
- **Fora do escopo:** reservas, agenda, pagamentos, KYC, clãs, moderação, publicidade, ERP e site público.

### 2026-11-06 — Fase 11B: painel web, sessão HttpOnly e CSRF

- **Sessão web:** `POST /api/v1/auth/web/registration`, `/login`, `/refresh` e `/logout`; refresh em cookie `HttpOnly` com `Path=/api/v1/auth/web`, access token apenas em memória e `X-CSRF-Token` de duplo envio em refresh/logout.
- **Revogação:** `SessionService.revoke_by_refresh` revoga a sessão do cookie sem rotacionar o token; logout limpa cookies e registra evento de segurança.
- **Painel:** `web/` com React 19, TypeScript 6, Vite 8, React Router 7 e TanStack Query; rotas de login, organizações e detalhe da organização; membros/papéis, estabelecimentos e auditoria.
- **Permissões na UI:** operador não vê edição de organização, gestão de membros nem auditoria; pode consultar membros e gerenciar estabelecimentos. O backend continua sendo a autoridade.
- **CI:** job `Web` com `pnpm install --frozen-lockfile`, `lint`, `format:check`, `typecheck` e `build`.
- **Testes backend:** **302 passed, 25 skipped** sem PostgreSQL e **327 passed** com `JOGA_TEST_DATABASE_URL`.
- **Verificações web:** `pnpm lint`, `pnpm format:check`, `pnpm typecheck` e `pnpm build` passam; bundle de produção gerado.
- **Smoke no navegador:** registro por OTP fixo local, criação de organização, criação/ativação de estabelecimento, auditoria, refresh após recarga, logout e login de conta existente; smoke de operador confirmou ocultação de controles administrativos.
- **Ambiente local:** API em 8000 (com `JOGA_DEV_FIXED_OTP=123456`) e Vite em 5173; banco local migrado para `a1b2c3d4e5f6`.
- **CI:** run `42211679165` verde nos jobs Backend, Web e Mobile.
- **Fora do escopo:** deploy, domínio, CSP definitiva, testes automatizados de UI, reservas, agenda, pagamentos e KYC.

### 2026-11-07 — Fase 11C: CSP, testes de UI e observabilidade do painel

- **Documentação:** commit `eebeac3` registra a v3.4 do conceito, as ADRs 0029 (avatares e mídia restrita) e 0030 (kit da partida), a documentação técnica e o threat model.
- **CSP:** política estrita injetada somente no build do painel; `pnpm build` valida `dist/index.html` e falha se faltar diretiva ou aparecer `unsafe-inline`/`unsafe-eval`. `frame-ancestors`, HSTS e `Permissions-Policy` ficam documentados para a hospedagem.
- **Testes de UI:** Vitest + jsdom + Testing Library; **6 arquivos e 15 testes** cobrindo CSRF, refresh em 401, erros da API, login/registro por OTP, proteção de rota e permissões de `OWNER`/`OPERATOR`. CI `Web` executa `pnpm test`.
- **Observabilidade:** `ApiError` carrega o `X-Request-ID`; o painel exibe a referência de suporte nos erros e tem error boundary global.
- **Verificações:** `pnpm lint`, `pnpm format:check`, `pnpm typecheck`, `pnpm test` e `pnpm build` passam; preview do build carregou o login sem erros de console.
- **Estado:** Fase 11 segue sem merge e sem deploy; Fase 12 não iniciada.

### 2026-11-07 — Alinhamento documental da Fase 12

- `PLANS.md` passou a dividir a Fase 12 em **12A** (quadras, fotos e agenda) e **12B** (KYC/recebedor), com fotos de quadra explicitamente no escopo e critérios de revisão/isolamento.
- A Fase 17 foi corrigida: não há upload livre de mídia por usuários, mas fotos de quadra têm fluxo próprio na Fase 12 e não entram na fila de denúncias.
- Criado `harness/build/phase-12-quadras-agenda-kyc.md` com escopo, riscos, testes e condição de parada; nenhuma implementação iniciada.

### 2026-11-07 — Fase 12A: quadras, fotos e agenda

- **Modelo:** `venue_spaces`, `venue_sports`, `venue_availability`, `venue_blackouts` e `venue_photos`; `organization_venues` ganhou `timezone` e `venue_id` (FK opcional/única para local privado ativo do catálogo da Fase 4).
- **API:** CRUD de quadras, substituição de modalidades, agenda semanal, bloqueios e fotos em `/api/v1/organizations/{org}/venues/{venue}/...`; autorização por organização em todas as operações.
- **Fotos:** validação real com Pillow, reencode JPEG, remoção de EXIF, limites de bytes/pixels/dimensões, storage local privado, serving autenticado e `Cache-Control: no-store`.
- **Revisão:** `OWNER`/`ADMIN` aprovam ou rejeitam com auditoria; `OPERATOR` gerencia quadras/fotos, mas não revisa. Revisão independente fica para a Fase 17.
- **Painel:** rota de estabelecimento com quadras, modalidades, agenda, bloqueios e fotos; upload, preview autenticado, aprovação/rejeição e remoção.
- **Testes backend:** **315 passed, 28 skipped** sem PostgreSQL e **344 passed** com `JOGA_TEST_DATABASE_URL`.
- **Testes painel:** **7 arquivos e 17 testes**; `lint`, `format:check`, `typecheck` e `build` verdes.
- **Migrações:** `99c1055b81b5` e `0261da35ece5`; `alembic check` sem operações pendentes e ciclo upgrade → downgrade → upgrade validado em banco descartável com PostGIS.
- **Smoke:** quadra, modalidade, agenda, bloqueio, upload, aprovação e serving de foto no navegador, sem erro de console.
- **Fora do escopo:** 12B (KYC/PSP), UI mobile de descoberta de quadras, reservas, pagamentos e storage de produção. Nenhum provedor externo acionado.

### 2026-11-07 — Fase 13A: reservas, holds e T1/T2/T3

- **Modelo:** `bookings`, `booking_participants`, `booking_holds`, `booking_timers`, `booking_events` e `booking_payments`; T1/T2/T3 independentes e hold por espaço/intervalo.
- **Fluxo:** criação idempotente por lobby, confirmação/recusa de participante (T1), aceite/recusa do estabelecimento (T2), hold transacional, pagamento simulado (T3), substituição sem reiniciar T3, cancelamento e conclusão.
- **Autorização:** participante só acessa as próprias reservas; organização só acessa reservas dos próprios estabelecimentos; capacidades `bookings:read`/`bookings:manage`.
- **Concorrência:** lock da linha do espaço e verificação transacional de holds/reservas; teste PostgreSQL com dois aceites concorrentes gera um hold e um conflito.
- **Worker:** `scripts/advance_bookings.py` expira T1/T2/T3 e libera holds vencidos; idempotente.
- **Painel:** aba de reservas com aceite/recusa/conclusão e prazos; teste de UI cobre o aceite por operador.
- **Testes:** **352 passed** com `JOGA_TEST_DATABASE_URL`; `ruff`, formatação e `mypy` verdes; migração `26b70fd0fbc7` com upgrade/downgrade/upgrade e `alembic check`.
- **Fora do escopo:** 13B (jornada mobile completa), T2 em horário comercial, PSP real, reembolso real, redirecionamento de quadra e conclusão automática pelo ciclo da partida.

### 2026-11-07 — Fase 13B: painel mobile de reservas

- **Mobile:** `BookingPanel` lista reservas do jogador, exibe T1/T2/T3, vaga, contribuição e estado de pagamento; permite confirmar/recusar participação e pagamento simulado local.
- **API mobile:** tipos de reserva e `bookingsApi` adicionados; o painel foi incluído no `App.tsx` após comunicação.
- **Escopo:** `mobile/AGENTS.md` atualizado para autorizar a tela de reservas da 13B. A criação da reserva ainda depende do lobby/quadra; seletor de quadra no mobile e pagamento real ficam pendentes.
- **Verificações:** `tsc --noEmit`, `eslint .` e `prettier --check .` passam. Backend e painel web seguem com **352 passed** e **18 testes** de UI.
- **Fora do escopo:** criação automática a partir do lobby, T2 em horário comercial, PSP, reembolso real e Fase 14.

### 2026-11-07 — ADR 0034: Mercado Pago no protótipo/beta e Pagar.me na produção

- **Decisão:** protótipo e beta fechado usam Mercado Pago Checkout Transparente com Pix e custódia centralizada de teste; o valor fica na conta do JOGA e o repasse ao estabelecimento é simulado/manual após a partida ser declarada como acontecida (`COMPLETED`).
- **Limite:** o fluxo é de teste, não é escrow nem garantia de reembolso de produção. Dinheiro real no beta exige CNPJ/MEI, contrato e revisão jurídica; CPF fica restrito a protótipo/sandbox.
- **Produção:** permanece o Pagar.me Flex para retenção/split/liberação controlada, conforme ADR 0021.
- **Documentação:** ADR 0034 criada; ADR 0021, conceito v3.7, técnica §15, PLANS Fase 14, threat model e README atualizados. Nenhuma integração de PSP implementada.

### 2026-11-07 — Fase 14A: Mercado Pago Orders API, webhook e ledger

- **PSP:** adaptador `simulator` (local/CI) e `mercadopago` (Orders API `/v1/orders`), com uma ordem Pix por participante, `X-Idempotency-Key` e `payer.email` de teste no sandbox.
- **Pagamento:** cobranças vinculadas à reserva, participante, vaga e versão; QR Code, copia-e-cola, ticket URL e expiração persistidos.
- **Webhook:** rota pública com validação HMAC opcional, `psp_webhook_events` idempotente e consulta server-to-server antes de aplicar status.
- **Confirmação:** reserva só confirma com todas as vagas ativas pagas; replay e status repetidos são idempotentes.
- **Ledger:** `CHARGE_CREATED`, `PAYMENT_CONFIRMED`, `PAYMENT_REFUNDED` e `VENUE_RELEASE` (este simulado/manual após `COMPLETED`).
- **Mobile:** QR Code/copia-e-cola exibido apenas ao próprio participante; organização vê apenas status.
- **Migração:** `c97807d1b140`; upgrade/downgrade/upgrade e `alembic check`.
- **Testes:** **364 passed** com PostgreSQL; adaptador com HTTP simulado, webhook idempotente, valor divergente e autorização negativa cobertos.
- **Fora do escopo:** dinheiro real, split, retenção de produção, reembolso real, KYC e Pagar.me (14B).

### 2026-11-07 — Hipótese de p_t dinâmico por Trust Factor

- **Registro:** ADR 0036 documenta a hipótese de calcular a provisão de fraude `p_t` pela mediana do Trust Factor dos participantes, com faixa ilustrativa de 0,05% a 0,5%.
- **Decisão atual:** a hipótese **não foi aprovada**; o modelo permanece com `p_t = 0,2%` fixo (ADR 0021).
- **Motivos:** Trust Factor mede confiabilidade esportiva, não risco de pagamento; ainda está neutro/oculto; mediana é manipulável por grupos; conta nova seria penalizada; impacto financeiro por reserva é pequeno; preço variável exige revisão jurídica/LGPD e versionamento.
- **Avaliação futura:** modo sombra, sem cobrança diferente, comparando Trust Factor/mediana com MED, chargeback e estorno sem saldo por pelo menos 90 dias.
- **Documentação:** conceito v3.9, técnica §26 e ADR 0036 atualizados. Nenhum código ou preço foi alterado.

### 2026-11-07 — Validação sandbox real da Orders API

- **Credencial:** token de usuário de teste (`@testuser.com`) validado em `GET /users/me`.
- **Ordem Pix:** criada com sucesso em sandbox, status `action_required`, com QR Code, copia-e-cola e ticket URL.
- **Correção:** a Orders API rejeitou `notification_url` no payload (`unsupported_properties`); o adaptador deixou de enviá-lo. A URL de webhook deve ser configurada no painel de Webhooks do Mercado Pago.
- **Webhook:** ainda sem segredo configurado; o endpoint local/teste aceita sem validação, mas produção exige a chave secreta.
- **Nenhum pagamento real** foi realizado; apenas uma ordem sandbox de R$ 1,00.

### 2026-11-07 — Fase 14C: reembolsos, extrato e conciliação simulada

- **Reembolsos:** cancelamento por jogador/estabelecimento, expiração T3 e substituição reembolsam cobranças pagas via PSP simulado.
- **Modelo:** `payment_refunds` idempotente por cobrança, com status `PENDING`, `PROCESSED` e `FAILED`; ledger `PAYMENT_REFUNDED`.
- **Conciliação:** resumo por organização (cobrado, pago, reembolsado, pendente, repassado) e extrato por reserva.
- **Painel:** cartão de resumo financeiro na aba de reservas.
- **Worker:** `advance_bookings` expira prazos e executa reembolsos de reservas terminais.
- **Migração:** `bb4083b7b697`; upgrade/downgrade/upgrade e `alembic check`.
- **Testes:** reembolso total, substituição, expiração, idempotência, autorização negativa, resumo e extrato cobertos.
- **Fora do escopo:** reembolso real, MED, conciliação com PSP e política pós-confirmação (14B/15).

### 2026-11-09 — Fase 15A/15B: interface financeira e conciliação (proposta técnica)

- **Status:** implementação técnica de referência. `N`, modelo de repasse, moderação financeira e tratamento de divergência **não foram aprovados**.
- **Modelo:** `venue_releases` (valor por reserva, `PENDING`/`RELEASED`/`FAILED`/`REVERSED`, prazo e referência) e `financial_disputes` (motivo, evidência, decisão, operador e timestamps), com índice parcial que impede duas contestações abertas por reserva.
- **Liberação:** reserva só entra em `COMPLETED`; `eligible_at = completed_at + JOGA_RELEASE_DELAY_HOURS` (default técnico de 24 h, **não aprovado**). O ledger `VENUE_RELEASE` é gravado apenas na liberação, de forma idempotente.
- **Contestação:** `OWNER`/`ADMIN` abrem pelo painel ou API; contestação aberta suspende a liberação na proposta técnica. Decisão por CLI com `JOGA_REVIEW_OPERATORS` (**provisória para teste; modelo não aprovado**); decisão `ACCEPTED` libera, `REJECTED` mantém o prazo.
- **API:** resumo estendido (`pending_release_cents`, `disputed_cents`), `financial/receivables`, `financial/statement`, `financial/disputes` (GET/POST/detalhe) e capacidades `financial:read`/`financial:manage`.
- **Worker:** `scripts/release_payments.py` cria liberações faltantes e libera o que venceu, sem duplicar ledger. `scripts/reconcile_financials.py` compara pagamentos, reembolsos, liberações e ledger e reporta divergências.
- **Painel:** aba **Financeiro** com resumo, recebíveis, contestações e extrato; `OPERATOR` lê, mas não contesta.
- **Migração:** `c15a1b2c3d4e` com backfill das liberações da 14C; upgrade, downgrade, novo upgrade e `alembic check` limpos.
- **Testes:** **376 passed** com `JOGA_TEST_DATABASE_URL`; ruff, formatação e mypy sem achados. Painel: **19 testes**, lint, formatação, typecheck e build verdes. Evidência técnica, não aprovação de política.
- **Fora do escopo:** dinheiro real, split/retenção, MED/chargeback, comprovantes fiscais, KYC, exportação e definição comercial de `N` (14B/15 futura).
- **Decisões pendentes:** `N` de liberação, janela de contestação, regra de repasse, moderação financeira, tratamento oficial de divergência e PSP real.

### 2026-11-09 — ADR 0038: desistência após confirmação e ausência de jogadores

- **Decisão aprovada:** o serviço contratado é a reserva coletiva da quadra; a partida é melhor esforço.
- **Desistência após confirmação:** sem reembolso, salvo substituição efetiva por jogador pagante (reembolso apenas do substituído, sem reiniciar T3).
- **Ausência/no-show:** sem reembolso ao faltante; partida inviabilizada só por ausências não gera reembolso automático aos presentes.
- **Falha da quadra/JOGA:** reembolso integral, preservados os direitos legais do consumidor.
- **Relação com a 14C:** a ADR 0038 emenda o item 1 da ADR 0037 apenas para desistência após confirmação.
- **Implementação:** ver entrada seguinte.
- **Sem alteração de código na rodada da ADR.** Termos de uso e tela de pagamento dependem de revisão jurídica.

### 2026-11-09 — Implementação da ADR 0038 no cancelamento

- **Modelo:** `bookings.cancellation_refund_allowed` (nullable; `NULL` = legado/reembolsável, `false` = desistência pós-confirmação sem reembolso).
- **Cancelamento:** `BookingService.cancel` grava a decisão na própria reserva; o endpoint genérico distingue jogador (criador) de organização (quadra). Cancelamento pela quadra e anterior à confirmação continuam reembolsáveis.
- **Worker:** `PaymentService.refund_cancelled_bookings` ignora reservas com `cancellation_refund_allowed=false`, evitando que o reembolso automático desfaça a regra.
- **Contrato:** novas reservas usam `policy_version="v2"` e `cancellation_policy="no_refund_after_confirmation"`; reservas antigas mantêm os valores anteriores.
- **Testes:** **380 passed** com `JOGA_TEST_DATABASE_URL`; ruff, formatação e mypy sem achados. Casos cobertos: desistência pós-confirmação sem reembolso, worker sem efeito, desistência antes da confirmação com reembolso, cancelamento pela quadra com reembolso e membro da organização usando o endpoint genérico como falha da quadra.
- **Migração:** `e2f3a4b5c6d7`; upgrade, downgrade, novo upgrade e `alembic check` limpos.
- **Pendência:** o valor não reembolsado permanece no ledger sem regra específica de repasse/liberação à quadra; não liberar automaticamente sem decisão.

### 2026-11-09 — ADR 0039: política consolidada de cancelamento, substituição e presença

- **Decisão:** a ADR 0039 supera a ADR 0038. O destino financeiro passa a depender do desfecho da reserva, não apenas de `CANCELLED_BY_PLAYER`.
- **Fila de substitutos:** alvo `(F - M) + 1`, limitado a 4; na prática, muitas vezes +1 para fechar o time par. Casual opcional; ranqueado exige standby.
- **Temporizadores:** T2 com máximo de 60 min; T4 = 25% do tempo restante, piso 30 min, teto 12 h, terminando no cutoff; cutoff de 6 h antes; fila em T-2h; pré-check-in em T-1h; presença em T-30m; substituto fechado em T-15m.
- **Presença:** pré-check-in + confirmação no local com geofence/QR/NFC/capitão; GPS não é prova isolada; validação no servidor e retenção mínima.
- **Formato:** 9 em 5x5 vira 4x4 + rodízio; partida adaptada não conta como 5x5 ranqueado.
- **Financeiro:** substituto chamado após cutoff ocupa a vaga já paga, sem nova cobrança; cancelador sem reembolso; demais pagantes reembolsados quando o lobby é cancelado antes do cutoff; no-show sem reembolso.
- **Código:** a implementação da ADR 0038 foi revertida na fatia seguinte.
- **Pendências:** percentual do T4, cutoff definitivo, destino do valor não reembolsado, modelo de vaga paga, evidência/LGPD, limite mensal, integração match/booking e revisão jurídica.

### 2026-11-09 — ADR 0039, fatia 1: fila, T4/T5, cancelamento e reembolso

- **Reversão da 0038:** coluna `cancellation_refund_allowed`, migração, lógica no cancelamento/worker, campos de API e testes foram removidos; `cancellation_policy` voltou a `full_refund_until_confirmed`/`policy_version="v1"`.
- **Modelo:** `lobby_substitutes` (fila em standby), `booking_substitutions` (vaga/T4), `booking_refund_exclusions` (quem não deve ser reembolsado) e `booking_participants.left_at`.
- **API:** `POST/DELETE/GET /lobbies/{id}/substitutes`, `POST /bookings/{id}/participant-cancellations` e `GET /bookings/{id}/substitutions`.
- **Regra:** cancelamento individual só em `CONFIRMED` e antes do cutoff de 6 h; T4 = 25% do tempo restante (30 min–12 h); cria exclusão de reembolso do desistente. T2 passa a ter teto de 60 min.
- **Expiração:** worker `advance_bookings` expira T4, cancela reserva/lobby, libera hold e reembolsa os demais pagantes; o desistente permanece `PAID` e não é reembolsado.
- **Cancelamento integral pelo jogador:** também respeita cutoff e exclusão; cancelamento pela quadra continua reembolsando todos.
- **Migração:** `f4b5c6d7e8f9`; upgrade, downgrade, novo upgrade e `alembic check` limpos.
- **Testes:** **382 passed** com `JOGA_TEST_DATABASE_URL`; ruff, formatação e mypy sem achados. Casos: fila/idempotência, cancelamento antes do cutoff, bloqueio após cutoff, expiração com reembolso dos demais, worker sem reembolsar o desistente, acesso negado e cancelamento integral do jogador.
- **Pendente na fatia 1:** atribuição/pagamento do substituto (entregue na fatia 2), vaga paga em no-show, T6–T9/check-in, adaptação, integração com partida/Trust Factor e destino do valor não reembolsado.

### 2026-11-09 — ADR 0039, fatia 2: atribuição e pagamento do substituto

- **Atribuição:** `POST /bookings/{id}/substitutions/{substitution_id}/assign` cria participante ativo, nova versão de cobrança `PENDING`, marca a vaga `AWAITING_PAYMENT` e a fila como `CONFIRMED`.
- **Pagamento:** o substituto paga pela cobrança normal; ao confirmar `PAID`, a vaga vira `FILLED`, a fila vira `PLAYED` e o substituído é reembolsado.
- **Falha:** se o substituto não pagar até T4, a vaga expira, o participante substituto é desativado, a cobrança fica `FAILED`, o lobby/reserva é cancelado e os demais pagantes são reembolsados; o desistente continua sem reembolso.
- **Autorização:** criador da reserva ou membro da organização com `bookings:manage`.
- **Migração:** `a5c6d7e8f9a0` adiciona `substitute_payment_id` e o status `AWAITING_PAYMENT`; upgrade, downgrade, novo upgrade e `alembic check` limpos.
- **Testes:** **385 passed** com `JOGA_TEST_DATABASE_URL`; ruff, formatação e mypy sem achados. Casos: atribuição, pagamento e reembolso do substituído, expiração sem pagamento, fila `CONFIRMED`/`PLAYED`, acesso negado e cancelamento integral.
- **Pendente na fatia 2:** vaga paga em no-show (entregue na fatia 3), T6–T9/presença, adaptação e integração com partida/Trust Factor.

### 2026-11-09 — ADR 0039, fatia 3: vaga paga em no-show

- **No-show:** `POST /bookings/{id}/participants/{user}/no-show` exige cutoff vencido e cria vaga `paid_seat=True`; o ausente permanece sem reembolso.
- **Substituto sem cobrança:** ao atribuir, o participante entra com `payment_status=WAIVED` e a vaga aponta `covered_by_payment_id` para a cobrança paga do ausente. Não há nova cobrança nem reembolso.
- **Sem substituto:** a vaga expira, mas a reserva continua `CONFIRMED`; a quadra recebe normalmente, pois o horário foi entregue.
- **Modelo:** `booking_substitutions.paid_seat` e `covered_by_payment_id`; evita ciclo de FK entre participantes e pagamentos.
- **Migração:** `b6d7e8f9a0b1`; upgrade, downgrade, novo upgrade e `alembic check` limpos.
- **Testes:** **388 passed** com `JOGA_TEST_DATABASE_URL`; ruff, formatação e mypy sem achados. Casos: no-show pago, substituto `WAIVED`, fila `PLAYED`, expiração sem cancelar a reserva, cutoff e acesso negado.
- **Pendente na fatia 3:** T6–T9 (entregue na fatia 4), adaptação e integração com partida/Trust Factor.

### 2026-11-09 — ADR 0039, fatia 4: presença e no-show automático

- **Modelo:** `bookings.presence_closed_at` e, por participante, `pre_checked_in_at`, `presence_status`, `presence_method`, `presence_confirmed_at`, `presence_distance_m` e `presence_accuracy_m`.
- **API:** `POST /bookings/{id}/pre-check-in`, `POST /bookings/{id}/presence` e `GET /bookings/{id}/presence`.
- **GPS:** valida no servidor com distância haversine, raio de 200 m e precisão máxima de 100 m. Local sem coordenadas ou fora do raio/precisão fica `UNVERIFIED`; somente o estabelecimento pode confirmar como `PRESENT` (sem capitão).
- **Fechamento:** worker `advance_bookings` fecha presença em T-30m, marca `PENDING`/`UNVERIFIED` como `NO_SHOW` e cria vaga `paid_seat=True` para cada ausente.
- **Migração:** `c7e8f9a0b1c2`; upgrade, downgrade, novo upgrade e `alembic check` limpos.
- **Testes:** **393 passed** com `JOGA_TEST_DATABASE_URL`; ruff, formatação e mypy sem achados. Casos: geofence dentro/fora, local sem coordenadas, estabelecimento confirmando outro, GPS negado para terceiro, janela e fechamento automático.
- **Pendente na fatia 4:** adaptação, UI e Trust Factor.

### 2026-11-09 — Localização, chamada automática, formação e repasse

- **Localização:** `organization_venues.latitude/longitude` obrigatórios no cadastro; presença usa essas coordenadas e cai para o `venues` vinculado. Sem coordenadas, GPS fica `UNVERIFIED` e só o estabelecimento confirma.
- **Chamada automática:** só chama **um** substituto por vez e **somente quando o número de ativos está ímpar**. Se fica par, ninguém é chamado; chamada pendente é devolvida à fila. `CALLED` com timeout de 5 min, accept/decline e próximo da fila.
- **Formação:** `bookings.players_per_team` e `formation_note`. Par = dois times; ímpar = `NxN + 1 rodízio`; **não há quórum mínimo fixo**: 2+ presentes formam dois times, 1 não forma. É recomendação, sem cronômetro controlado.
- **Repasse:** ADR 0040; `eligible_at = starts_at + 2h` e `JOGA_RELEASE_DELAY_HOURS=2`. Reserva `CONFIRMED`/`COMPLETED` com pagamento gera liberação após 2 h; cancelamento antes do início não gera repasse.
- **Migrações:** `d8f9a0b1c2d3`, `e9a0b1c2d3e4`, `f0a1b2c3d4e5` e `b2c3d4e5f6a1`; upgrade, downgrade, novo upgrade e `alembic check` limpos.
- **Testes:** **400 passed** com `JOGA_TEST_DATABASE_URL`; ruff, formatação e mypy sem achados. Painel: **19 testes**, lint, typecheck e build verdes.
- **Trust Factor:** ADR 0041; no-show −30, cancelamento pós-confirmação −7, pré-pagamento −2, recuperação não linear e restrição ranqueada 7/30 dias.
- **Pendente:** UI de presença/fila, UI de suporte e conciliação/repasse real com PSP.

### 2026-11-12 — 14D.1 Faixas de preço e teto da quadra

- **Catálogo:** `pricing_bands` versionada com as seis faixas da ADR 0042 §3 (R$ 120/150/180/220/260/300).
- **Resolução:** por **teto**, não por escolha — a menor faixa ativa cujo `max_price_cents` cobre o preço. Impede a quadra de se declarar acima do próprio preço.
- **Atributo:** `venue_spaces.is_covered`, exposto no cadastro e na listagem. Alimenta rótulo e filtro; não decide a faixa.
- **Snapshot:** `venue_availability.band_id` grava a faixa no momento da escrita.
- **Reajuste:** bloqueado com `409 availability_has_future_booking` quando há reserva futura na mesma janela; permitido quando não há.
- **Fora do teto:** preço acima de R$ 300 retorna `422 price_above_band`.
- **API:** `GET /api/v1/pricing/bands`.
- **Migração:** `a1c2e3f40517`; upgrade aplicado no banco local e faixas conferidas. Backfill das janelas existentes pela menor faixa que cobre o preço.
- **Testes:** suíte completa verde, incluindo `tests/test_pricing_bands.py`; ruff e mypy --strict sem achados.
- **Pendente na fatia:** vigência de preço (`price_effective_from`) para reajuste com reserva recorrente e reclassificação contratual com aviso de 30 dias.

### 2026-11-12 — 14D.2 Fornecedor e chave de repasse

- **Modelo:** `organizations` ganha `legal_document`, `pix_key_type`, `pix_key`, `payout_status` e `payout_verified_at`, com constraints de coerência do par chave/tipo e de estado.
- **Validação:** CNPJ com dígitos verificadores; chave Pix por tipo (`cnpj`, `email`, `phone`, `random`).
- **Autorização:** `PUT /organizations/{id}/payout` exige `financial:manage`; operador recebe 403.
- **Exibição:** `pix_key_masked` na resposta; a chave completa nunca volta pela API.
- **Portão:** `payout_ready` exposto no `OrganizationView`; a reserva paga ainda não o consulta.
- **Migração:** `c2d3e4f50618`; upgrade, downgrade e novo upgrade aplicados; `alembic check` limpo.
- **Testes:** `tests/test_payout.py` com seis casos; suíte completa verde, ruff e mypy sem achados.
- **Pendente na fatia:** KYC contratual, histórico de chaves e chamada do portão na abertura de reserva.

### 2026-11-12 — 14D.3 Carteira de ingressos e ledger

- **Modelo:** `ticket_ledger` append-only com `idempotency_key` única e `ticket_balances` como projeção com `CHECK balance >= 0`.
- **Serviço:** `grant`, `consume`, `refund` com chaves determinísticas por `ref_type:ref_id:user`, impedindo débito ou crédito duplicado.
- **API:** `GET /api/v1/me/tickets` com saldo e últimos movimentos, escopado por usuário.
- **Concorrência:** `SELECT ... FOR UPDATE` na linha de saldo antes de aplicar o movimento.
- **Migração:** `d3e4f5061927`; upgrade, downgrade e novo upgrade aplicados; `alembic check` limpo.
- **Testes:** `tests/test_tickets.py` com sete casos; suíte completa verde, ruff e mypy sem achados.
- **Pendente na fatia:** compra não credita, reserva não consome e devolução ainda é em dinheiro.

### 2026-11-12 — 14D.4 Pacotes e compra de ingressos

- **Catálogo:** `ticket_packs` semeado com a escada da ADR 0042 (3 @ 3,70 · 10 @ 3,40 · 30 @ 3,20 · 50 @ 3,10).
- **Compra:** `ticket_purchases` com valor congelado; `POST /me/tickets/purchases` cria a intenção `pending`.
- **Confirmação:** `POST /me/tickets/purchases/{id}/confirm` só existe em ambiente local — dinheiro real depende da 14B.
- **Crédito:** `grant` com chave `purchase:{id}`; confirmar duas vezes não duplica.
- **API:** `GET /me/tickets/packs` expõe a escada; o preço unitário já é exibido ao jogador.
- **Migração:** `e4f5061a2838`; upgrade, downgrade e novo upgrade aplicados; `alembic check` limpo.
- **Testes:** `tests/test_ticket_purchases.py` com seis casos; suíte completa verde.
- **Pendente:** cobrança Pix, cancelamento e o consumo na reserva.

### 2026-11-12 — 14D.5 Quitação da vaga por ingressos (modelo A)

- **Decisão:** cada participante debita o próprio saldo; a reserva confirma quando todas as vagas ativas estão quitadas. Registrado na ADR 0042 §2 item 8.
- **Tabela 2D:** `pricing_band_tickets` com 24 linhas (6 faixas × 4 tamanhos de time).
- **Modelo:** `booking_participants.settled_with` (`pix`/`tickets`) e `tickets_consumed`.
- **Serviço:** `settle_with_tickets` resolve janela → faixa → formato, consome a carteira e chama `_confirm_if_all_paid`.
- **API:** `POST /api/v1/bookings/{id}/settle-with-tickets`.
- **Erros:** `409 insufficient_tickets` sem alterar a reserva; `409 tickets_not_configured` quando a matriz não cobre o formato.
- **Migração:** `f5a6172b3949`; upgrade, downgrade e novo upgrade aplicados; `alembic check` limpo.
- **Testes:** `tests/test_ticket_settlement.py` com três casos; suíte completa verde.
- **Pendente:** devolução em ingresso no cancelamento e parar de criar cobranças Pix quando a quitação é por ingresso.

### 2026-11-12 — 14D.6 Devolução em ingresso no cancelamento

- **Regra:** a matriz da ADR 0039 passa a valer sobre a carteira. Cancelamento pela quadra ou pelo sistema devolve para todos; cancelamento pelo jogador devolve só para os demais.
- **Serviço:** `_refund_tickets` com chave `booking_cancel:{booking_id}:{user}` — repetir não devolve duas vezes.
- **Corte:** continua na API (`cancellation_cutoff_hours`); depois do prazo, ninguém é reembolsado.
- **Testes:** `tests/test_ticket_settlement.py` sobe para seis casos, incluindo os três desfechos de cancelamento; suíte completa verde.
- **Pendente:** encerrar cobranças Pix `PENDING` de quem quitou por ingresso, e ligar a substituição à carteira.

### 2026-11-12 — 14D.6b Cobranças encerradas na quitação por ingresso

- **Status novo:** `booking_payments.status` passa a aceitar `CANCELLED`.
- **Comportamento:** quem quita a vaga com ingressos tem as cobranças `PENDING` encerradas como `CANCELLED`, para não aparecerem como recebível aberto.
- **Migração:** `a6b7283c4051` recria a constraint, e o downgrade converte `CANCELLED` em `EXPIRED`.
- **Testes:** o caso de quitação agora confere que todas as cobranças ficaram `CANCELLED`.

### 2026-11-12 — 14D.7 Temporada, XP, nível e streak (núcleo)

- **Modelo:** `seasons`, `xp_events` (append-only com chave única), `season_progress` e `win_streaks`.
- **Regras:** 150 XP por nível, 30 níveis, tiers bronze/prata/ouro, reset na virada, XP igual para todos.
- **Streak:** vitória soma; empate ou derrota zera; semana inteira sem jogar zera na leitura, mas a semana aberta não zera.
- **Serviço:** `level_for`, `tier_for`, `award_xp`, `record_match_result`, `effective_streak`, `seed_current_season`.
- **API:** `GET /api/v1/me/progress`.
- **Migração:** `b7c8394d5162`, com a temporada 2026-Q4 semeada; upgrade, downgrade e novo upgrade aplicados.
- **Testes:** `tests/test_season.py` com seis casos; suíte completa verde.
- **Pendente:** trilha com recompensas, missões, gancho de XP na partida, ingressos grátis por nível e fechamento de temporada.

### 2026-11-12 — 14D.8 Trilha, itens e insígnias

- **Decisões de produto:** 7 itens por temporada; nível 30 entrega a insígnia; insígnia não é medalha; até 3 insígnias equipadas no perfil.
- **Catálogo:** `season_items` com acessório, emote, animação de lobby, ícone de entrada e insígnia; arte em `placeholder/<code>`.
- **Trilha:** `season_track_levels` com 30 níveis, itens em 4/8/12/17/21/26/30 e ingressos grátis em 5/10/15/20/25/30.
- **Resgate:** `claim_level` valida XP, recusa trilha paga sem passe e é idempotente por nível.
- **Insígnias:** `badges`, `player_badges` (até 3 slots) e `player_items`.
- **API:** `GET /me/progress/track`, `POST /me/progress/track/{level}/claim`, `GET /me/progress/badges`, `PUT /me/progress/badges/equip`.
- **Migração:** `c8d94a5e6273`, com a trilha da 2026-Q4 semeada; upgrade, downgrade e novo upgrade aplicados.
- **Testes:** `tests/test_season_track.py` com seis casos; suíte completa verde.
- **Pendente:** arte final, passe como assinatura, equipar item de avatar, medalhas, fechamento de temporada, missões e gancho de XP.

### 2026-11-12 — 14D.9 Missões semanais e gancho de XP

- **Gatilhos:** partida concluída com presença `PRESENT` credita 100 XP; primeira visita à quadra credita 50 XP.
- **Missões:** `play_one` e `new_venue` avançam na conclusão e pagam 40 XP; `on_time_checkin` existe na definição e ainda não é chamada.
- **Idempotência:** `match:{booking_id}:{user}`, `venue:{space_id}:{user}` e `mission:{season}:{week}:{code}:{user}`.
- **Modelo:** `mission_progress` com PK `(user_id, season_id, week_start, mission_code)`; reset por linha nova, sem rotina destrutiva.
- **Sem temporada ativa:** o gancho é silencioso e não quebra a conclusão da partida.
- **API:** `GET /api/v1/me/progress/missions`.
- **Migração:** `d9e95b6f7384`; upgrade, downgrade e novo upgrade aplicados.
- **Testes:** `tests/test_season_hooks.py` com três casos; suíte completa verde.
- **Pendente:** XP de vitória (depende do resultado confirmado), missão de check-in e fechamento de temporada.

### 2026-11-13 - 14D.12 + 14D.13 Passe como assinatura e Pix no checkout

- **Assinatura:** `pass_subscriptions` com quatro planos (10/20/30/50 por mes, R$ 3,25 por ingresso), status `pending`/`active`/`expired`/`cancelled` e valor do trimestre gravado na compra.
- **Entrega:** `pass_deliveries` com uma linha por mes (1..3), chave `pass:{subscription}:{month}` e sem retroacao.
- **Trilha paga:** `claim_level` recebe `has_pass`; a API calcula pela assinatura vigente. Sem passe continua 403 `pass_required`.
- **Cobranca:** `purchase_payments` cobre pacote e passe com `kind` + `reference_id`; webhook do PSP liquida e `/sync` repete a consulta.
- **Idempotencia:** replay de webhook nao duplica ingressos nem ativacao; valor ou referencia divergente e recusado.
- **API:** `/me/pass/plans`, `/me/pass`, `/me/pass/subscriptions` e `/sync`, `/confirm` local, `DELETE` de pendente; `POST /me/tickets/purchases` agora abre Pix e `/sync` credita.
- **Rotina:** `python -m scripts.deliver_pass_months` entrega franquias e expira assinaturas.
- **Migracao:** `e4a1c9d7b203`; upgrade, downgrade e novo upgrade aplicados; `alembic check` limpo.
- **Testes:** `tests/test_pass.py` e `tests/test_ticket_pix.py` (11 casos); suite completa verde.
- **Pendente:** politica de venda no meio da temporada, reembolso de passe/pacote, conciliacao do PSP e UI.

### 2026-11-13 - 14D.10 + 14D.11 Resultado para XP/streak e missao de check-in

- **Gatilho:** resultado confirmado (apuro automatico ou decisao humana FINALIZE) credita +40 XP por vencedor presente e atualiza a streak; disputa e anulacao nao pagam.
- **Idempotencia:** chave `win:{match}:{user}` e guarda por `last_match_id` na streak.
- **Check-in:** presenca antes do inicio grava a missao semanal `on_time_checkin` (40 XP), uma vez por semana.
- **Testes:** `tests/test_season_result_hooks.py` (4 casos) e ajuste de `tests/test_season.py`.

### 2026-11-13 - 14D.14 Fechamento de temporada e reset suave

- **Rotina:** `close_expired_season` fecha a temporada vencida, abre a do trimestre e semeia a trilha; `scripts/close_seasons.py` roda em lote.
- **Reset suave:** `season_placements` conta ranqueadas por temporada; rating persiste e a divisao volta a Provisiorio ate 5 partidas.
- **API:** `/ratings/me`, posicao e top 100 usam a contagem da temporada ativa.
- **Migracao:** `f5b2d8e4c310`; upgrade, downgrade e novo upgrade aplicados; `alembic check` limpo.
- **Testes:** `tests/test_season_close.py` e ajuste de `tests/test_ratings_api.py`.

### 2026-11-13 - 14D.15 Estatisticas e inteligencia de rede

- **API:** `GET /me/stats` (livre), `/me/stats/courts` e `/me/stats/passport` (passe), `GET /me/network`.
- **Estatistica:** partidas, V/E/D, presenca, streak e recorte por formato; sem MMR bruto.
- **Rede:** faixas por quadra, janela de 30 dias, amostra minima de 20, atualizacao diaria representada pela data; faixas so no passe.
- **Testes:** `tests/test_stats.py` (3 casos), incluindo 19 partidas ocultas e 20 visiveis.

### 2026-11-13 - Fase 16 Clas, trofeus e moderacao minima

- **Decisoes (ADR 0046):** 30 membros, entrada por aprovacao, um cla ativo por jogador, carencia de 7 dias, trofeus por temporada/formato, denuncia com ocultacao imediata.
- **Modelo:** `clans`, `clan_members` (indice unico parcial por jogador ativo), `clan_join_requests`, `clan_trophy_events`, `clan_trophy_snapshots`, `clan_messages` e `clan_reports`.
- **Trofeus:** vitoria 50, empate 30, derrota 20; 10 melhores membros; 7 dias de permanencia; snapshot no fechamento da temporada (`scripts/close_seasons`).
- **Chat:** so para membros ativos; denuncia oculta na hora e o admin decide entre manter ou restaurar, com registro de autor e data.
- **API:** criacao, descoberta, pedidos/aprovacao, papeis, transferencia, saida, chat, denuncias, revisao e ranking de clas.
- **Migracao:** `b7d4f1a9c620`; upgrade, downgrade e novo upgrade aplicados; `alembic check` limpo.
- **Testes:** `tests/test_clans.py` (8 casos); suite completa verde.

### 2026-11-13 - UI mobile do JOGA (app de demonstracao)

- **Pedido:** levar a UI do prototipo `telas/jogo/prototipo-v3.html` para um app React Native/Expo, sem mexer no HTML.
- **Entrada:** `mobile/App.tsx` passa a renderizar `src/joga/JogaApp`; os paineis tecnicos continuam no repositorio, fora da entrada visual.
- **Navegacao:** 5 abas e 17 telas secundarias com pilha propria, barra de abas e tema claro/escuro.
- **Espacamento:** margem lateral de 20 px (HTML usava 16), gap de 16, padding de card 18, area segura no topo e na barra de abas. A correcao de margem foi feita no app, nao no prototipo.
- **Dependencia:** `@expo/vector-icons` para os icones do Ionicons.
- **Verificacao:** `tsc --noEmit` e `eslint` limpos; `expo export --platform android` gerou o bundle.
- **Execucao:** `expo start --lan` em `exp://192.168.0.105:8081`.

### 2026-11-13 - APK Android do app de UI

- **Toolchain local:** JDK 17, Android SDK platform 36/37, build-tools 36.0.0, NDK 27.1.12297006 e CMake 3.22.1 em `.tools` (ignorado pelo Git); platform-tools com adb.
- **Build:** `expo prebuild --platform android` e `gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a`; BUILD SUCCESSFUL em 31 min.
- **Artefato:** `mobile/android/app/build/outputs/apk/release/app-release.apk` (23,9 MB, minSdk 24, target 36, arm64-v8a, assinado com a debug key).
- **Instalacao:** pendente de aparelho visivel no adb (nenhum dispositivo detectado ate o momento).

### 2026-11-13 - UI mobile refeita 1:1 a partir do prototipo v3

- **Correcao de rumo:** a camada visual anterior foi descartada; as 5 abas foram reimplementadas copiando textos, ordem, tamanhos e componentes do HTML.
- **Tokens exatos:** header 16px, titulo 16/900, sub 13, corpo 16/14, card padding 16, raio 18, borda 1.5, botao 52, chip 46, tab bar 76.
- **Icones:** sprite SVG original extraido para `src/joga/icons.ts` e renderizado com react-native-svg; sem Ionicons.
- **Avatar:** SVG em camadas copiado do HTML, com recorte circular.
- **Telas portadas:** Jogar, Partidas, Temporada, Social (Amigos) e Perfil.
- **Ajuste forcado:** respiro inferior da tab bar para nao ficar sob os botoes de navegacao do Android.
- **Backend:** ainda nao conectado nestas telas; o lote de Entrada trara o fluxo real de telefone/OTP/passkey.

### 2026-11-14 - Reconstrução completa do app mobile a partir do protótipo v3

- **Escopo:** a UI anterior (`src/joga/`, painéis técnicos e `src/api.ts`) foi removida e o app foi refeito do zero em React Native a partir de `telas/jogo/prototipo-v3.html`, sem WebView.
- **Estrutura:** 136 telas registradas em `mobile/src/screens/` (entrada, núcleo, quadras/partidas, carteira/passe, temporada, estatísticas, social e sistema), kit visual em `mobile/src/ui/`, cliente HTTP em `mobile/src/api/` e estado global/sessão em `mobile/src/state/` e `mobile/src/session.ts`.
- **Navegação:** 5 abas (Jogar, Partidas, Temporada, Social, Perfil) + pilha própria, back do Android, modal/sheet e toast. Os títulos das telas passaram a rolar junto com o conteúdo, a pedido do produto.
- **Backend:** autenticação por telefone/OTP, refresh rotativo, perfil, modalidades, disponibilidade (com editor de dia/início/fim), região por GPS, fila casual/ranqueada, partidas, presença, resultados/disputa, carteira, compra Pix simulada, passe, temporada/XP/insígnias/missões, estatísticas, reservas, chat por lobby, amigos/convites/bloqueios, clãs, ranking e dispositivos/passkeys. Telas sem endpoint permanecem visuais.
- **Dados reais e zero state:** home, partidas, carteira, perfil, amigos, clã, ranking, notificações, quadras e estatísticas passaram a usar apenas dados do backend; sem partidas/saldo/amigos/quadras, exibem estado vazio. Formulários deixaram de pré-preencher nome, telefone e horários de exemplo; usam placeholders (“Seu nome”, “HH:MM”). Conta zerada `Zero Dois` (telefone `11900000002`) criada e login por OTP exercitado no aparelho.
- **Placar:** não existe campo/endpoint de gols por partida no backend; o resultado é apenas `TEAM_1`/`TEAM_2`/`DRAW`. Foram removidos os placares fabricados (“3x1”, “2x2”) do histórico e do detalhe da partida.
- **Tema:** claro/escuro seguindo o sistema e `Appearance`; a barra de navegação Android acompanha o esquema. Corrigido o título fixo, o corte de números grandes (line-height de `Txt`), o outline vermelho de botões `ghost` dentro de cartões ink/coloridos no tema escuro e o overflow do cartão de ingressos consumidos.
- **Dependência:** nenhuma nova dependência de tema; `expo-navigation-bar` foi removido após validar que `Appearance` resolve a barra Android.
- **Verificação:** `pnpm exec tsc --noEmit`, `pnpm exec eslint .` e `pnpm exec expo export --platform android` limpos; fluxo real de cadastro, onboarding, home, fila, perfil, carteira e disponibilidade exercitado em aparelho Android com backend local.

### 2026-11-14 - Checkpoint de continuidade do backend

- **Escopo:** revisão e consolidação do trabalho local de 14D.10–14D.15 e da Fase 16, sem alterar mobile, painel web ou contratos.
- **Auditoria:** rotas conferidas no OpenAPI (144 caminhos); banco local no head `b7d4f1a9c620`, 99 tabelas, PostGIS 3.6.2; `alembic check` sem operações novas.
- **Testes:** `pytest -o addopts="" -q` com **442 passed, 29 skipped** (integração PostgreSQL ignorada por falta de `JOGA_TEST_DATABASE_URL`); `ruff check .` e `mypy app` sem achados.
- **Correção:** normalizadas as 7 linhas CRLF do build-log e removida a linha em branco final de `backend/app/modules/payments/service.py`; `git diff --check` limpo.
- **Documentação:** tabela de fases atualizada para refletir 4–16; histórico preservado. O mobile permanece fora deste checkpoint e segue sujeito à revisão da outra IA.
- **Limites:** nenhum push, merge ou deploy; nenhum serviço reiniciado; nenhuma migração executada; nenhum arquivo de mobile ou `telas/` commitado neste checkpoint.

### 2026-11-14 - Auditoria de UX/UI, consistencia e fluidez do app mobile

- **Escopo:** auditoria de navegacao, estados, responsividade, fidelidade visual e microinteracoes sem alterar regras competitivas, contratos do backend ou endpoints.
- **Navegacao:** pilha propria por aba com memoria de posicao; `replace` e `reset` para fluxos pos-acao; aba ativa estavel; sem botao de voltar em raizes; back do Android encerra o app na raiz em vez de prender o usuario. Telas antes orfas ganharam entradas naturais: Configuracoes, seguranca e LGPD (Perfil), clas e ranking (Amigos e Inicio), quadras (Inicio), trilha/recompensas (Temporada, com nos e itens tocaveis), carteira/passe/custo/reembolso (Inicio e Carteira), check-in/resultado (Partidas e lobby), termos (cadastro e Configuracoes) e amizades (Social).
- **Sessao:** refresh concorrente deduplicado no cliente HTTP e sessao local encerrada apenas quando o refresh realmente falha. Evita logout acidental quando varias telas recebem 401 ao mesmo tempo apos a expiracao do access token.
- **Fluidez:** transicoes de pilha e de aba com `Animated` no driver nativo (slide/fade de 220 ms), sheet com entrada/saida, toast animado acima da tab bar, feedback de pressao em botoes/cards/linhas/chips, indicador ativo animado e skeleton pulsante.
- **Carregamento contextual:** o skeleton unico foi substituido por variantes que seguem o layout real de cada destino (home, lista, cards, quadras, carteira, temporada, trilha, timers, grade, social e cla), mantendo cabecalho e voltar visiveis; o boot passou a exibir a marca JOGA em vez de uma tela universal centralizada.
- **Transicoes:** o crossfade duplo foi removido. A camada de navegacao agora mantem a tela de origem montada e usa apenas slide/fade de cobertura (a nova tela entra opaca por cima; no voltar, a antiga sai revelando a nova), sem duas opacidades simultaneas em elementos grandes.
- **OTP:** os seis campos foram substituidos por um unico input oculto sobre as caixas visuais, com foco automatico, avanco de dígitos, apagar natural, colar código, autofill de SMS e limite de 6 dígitos.
- **Limites de entrada:** telefone (15), nome (60), bio (280), clã (nome 40, tag 8, descrição 280), chats (2.000), buscas (60), confirmação LGPD (7) e textarea padrão (2.000).
- **Integracao 13C/14D.16/13D/9D:** vitrine ligada a `GET /discovery/bookable-venues` e ao detalhe com espacos, formatos, faixas, cobertura e `next_slots`; reserva chama `POST /bookings`; central de notificacoes persistidas com contador de nao lidas; carteira exibe lotes com validade e consumo passe -> nivel -> comprado; `BookingView`, participantes e erros novos (`payout_not_ready`, `space_unavailable`, `insufficient_lead_time`, `tickets_not_configured`, `band_missing`) foram tratados no app.
- **Moderacao (Fase 17A):** denuncia real via `POST /moderation/reports`, historico em `/moderation/reports/me`, medidas em `/moderation/actions/me` e recurso em `/moderation/actions/{id}/appeal`. O app mostra apenas categoria, status, data e decisao; severidade e prioridade continuam internas. Nao ha upload de midia: o contexto usa mensagens reais do lobby e texto.
- **Tema e acessibilidade:** Claro e Escuro continuam gratuitos e sem gate de passe; o tema Alto contraste e a opcao Areia foram removidos do seletor; a preferencia de alto contraste tambem saiu da acessibilidade. Personalizacao deixou de ser marcada como PASSE.
- **Configuracoes:** linhas inteiras de Configuracoes, Seguranca, Privacidade, Ajuda, Sobre, Termos e Recuperacao passaram a abrir a tela; antes apenas o icone era clicavel.
- **Consistencia:** `Card` pressable passou a aplicar layout no proprio container (corrige cards 2-up que encolhiam), botoes ajustam a fonte em uma linha, cabecalho e labels de aba nao quebram, textos tem limite de escala, OTP e flexivel em 320 dp, avatar do perfil e adaptativo e insets superior/inferior do Android sao calculados.
- **Estados:** loading, erro e vazio reais em Quadras, Partidas, Amigos, Cla, Temporada/Trilha, Carteira, Ingressos, Passe e Reservas; removidos saldo, extrato, reservas e planos fabricados nessas telas. Saldo e custo da partida agora refletem a carteira.
- **Verificacao:** `pnpm exec tsc --noEmit`, `pnpm exec eslint .`, `pnpm exec prettier --check .` e `pnpm exec expo export --platform android` limpos; login OTP, home, perfil, configuracoes, cla, temporada/trilha, carteira, custo da partida e loja exercitados no aparelho Android com backend local.
- **Pendencias:** telas de estados terminais (offline, erro generico, loading, recusa/expiracao de reserva, no-show, segunda rodada e disputa) continuam acessiveis apenas quando o estado de dominio ocorrer; passkey real, pagamentos reais e KYC seguem fora do escopo atual.

### 2026-11-14 - Barra inferior, suspensao de conta e moderacao no app mobile

- **Barra inferior:** o calculo manual de `bottomInset` foi removido e o app passou a usar `react-native-safe-area-context` (`SafeAreaProvider`/`useSafeAreaInsets`). A barra de abas tem conteudo de 54 dp, icones de 19 e rotulos de 11; o inset inferior do sistema fica em uma area separada com a cor de fundo da pagina, sem encostar na barra de navegacao Android. O `toast` tambem respeita o inset.
- **Dependencia:** `react-native-safe-area-context@~5.11.1` instalado via Expo; `node_modules` foi reinstalado do lockfile apos falha de importacao do pnpm no Windows.
- **Suspensao:** o refresh agora responde `401 account_suspended` quando o usuario esta suspenso (o acesso comum continua `401 invalid_token`). O app preserva a sessao, remove a barra de abas e exibe `SuspendedScreen` com motivo, inicio, fim, recurso, "Tentar novamente" e "Sair da conta". Recuperacao apos revogacao exercitada no aparelho.
- **Contrato de moderacao:** `GET /moderation/actions/me` e `POST /moderation/actions/{id}/appeal` aceitam sessao de conta suspensa para o jogador contestar a propria medida; a autorizacao continua limitada as acoes em que ele e o alvo. Severidade, prioridade e identidade do denunciante nao sao expostas.
- **Denuncia e historico:** categoria, status, data e decisao continuam sendo o unico conteudo exibido; recurso e mensagens do lobby como contexto seguem sem upload de midia.
- **Verificacao:** `pnpm exec tsc --noEmit`, `pnpm exec eslint .`, `pnpm exec prettier --check .` e `pnpm exec expo export --platform android` limpos. Backend: `python -m pytest -o addopts="" -q` com 473 passed e 29 skipped; `ruff check` e `mypy` limpos nos arquivos alterados. Testes novos cobrem refresh de conta suspensa e leitura/recurso da propria medida.
- **Aparelho:** Moto G24 via Expo Go/USB; login OTP, barra inferior, suspensao, motivo/datas, envio de recurso e retorno a home apos revogacao validados. `screen_off_timeout` restaurado para 60000 ms.
- **Limites:** iOS nao foi exercitado; a barra foi ajustada para Android com 3 botoes e inset reportado pelo sistema. O limite de OTP do ambiente local (5/hora) exigiu limpeza de desafios durante os testes.

### 2026-11-15 - Backend: contratos de suspensao, reservas e listas do painel

- **App:** refresh de conta suspensa rotaciona a sessao e responde `200` com `user.status=suspended`, permitindo renovar o access token durante toda a suspensao; `GET /moderation/actions/me` e `POST /moderation/actions/{id}/appeal` aceitam sessao suspensa para contestar a propria medida, com autoria limitada ao alvo. Demais rotas continuam `401 invalid_token`; refresh web do painel continua `401 account_suspended`.
- **Reservas:** `GET /bookings` e `GET /organizations/{id}/bookings` aceitam `status`, `from`, `to`, `limit` e `offset`, devolvem `total` e `BookingView.timezone` (IANA). Datas sem fuso ou periodo invalido retornam `422 invalid_time_range`.
- **Erros:** handler global de `RequestValidationError` padroniza `422` em `{detail:{code,message,fields}}`, sem ecoar o valor enviado.
- **Painel:** sessao web passa a devolver `capabilities` (`moderation.read`/`moderation.manage`); recebiveis, extrato, disputas e auditoria devolvem `total` antes da paginacao.
- **Notificacoes 17C:** recurso novo gera `moderation_appeal` para operadores ativos; decisao do recurso gera `moderation_appeal_result` para o jogador. A denuncia continua gerando `moderation_report`.
- **Canais 17C:** notificacoes internas (`moderation_report`, `moderation_appeal`) usam `channel=moderation`; `GET /me/notifications` lista apenas `player` e o dispatcher nao envia push interno ao app. `GET /moderation/appeals/me` aceita conta suspensa e mostra o resultado do recurso.
- **Verificacao:** `ruff check`, `ruff format --check` e `mypy app` limpos; backend **477 passed, 29 skipped**.
- **Limites:** convite de membro por telefone/e-mail/QR fica para fatia propria com ADR; nenhum arquivo de `mobile/` ou `web/` alterado.

### 2026-11-15 - CEP e geocodificacao de estabelecimento (Fase 1)

- **Endpoint:** `GET /api/v1/geo/postal-codes/{postal_code}?number=...`, autenticado, sem alterar o `POST` de venue.
- **Provedor:** BrasilAPI CEP v2, reaproveitado do perfil; endereco e coordenadas com `precision` (`street`/`approximate`/`unresolved`) e `source=brasilapi`.
- **Cache:** tabela `postal_code_cache` (migracao `c5d6e7f8a9b0`), TTL de 30 dias, chave CEP+numero+versao do provedor.
- **Protecoes:** rate limit de 30/min por usuario, timeout de 3 s e erros `invalid_postal_code`/`postal_code_not_found`/`rate_limited`/`geocoding_provider_error`/`geocoding_timeout` sem vazar o provedor.
- **Testes:** `tests/test_geo_api.py` com resolver falso, cache hit, erros, `unresolved` e rate limit; nenhuma chamada externa.
- **Limites:** sem mapa, sem persistencia de CEP no venue e sem provedor pago; Fase 2 pendente.

### 2026-11-15 - Validacao do fluxo de suspensao no app mobile

- **Escopo:** somente front-end. Nenhum arquivo de `backend/` foi alterado nesta validacao.
- **API local:** reiniciada com o contrato de suspensao ja suportado pelo backend.
- **Fluxo exercitado no Moto G24:** chamada autenticada recebeu `401 invalid_token`, o refresh respondeu `401 account_suspended`, a sessao local foi preservada e a tela `SuspendedScreen` apareceu no lugar das abas.
- **Dados da medida:** `GET /moderation/actions/me` retornou `200` e a tela exibiu motivo, inicio e fim previsto.
- **Recurso:** `POST /moderation/actions/{id}/appeal` retornou `200`; a tela limpou o campo e mostrou "Recurso enviado. A analise e interna.".
- **Recuperacao:** com a medida revogada e a conta reativada, "Tentar novamente" voltou para a aba Partidas com a barra inferior visivel.
- **Limpeza:** a medida de teste (`operator=test-local`) foi removida, a denuncia usada no teste voltou para `RESOLVED` e a conta `Zero Dois` voltou para `active`.
- **Verificacao front-end:** `pnpm exec tsc --noEmit`, `pnpm exec eslint .` e `pnpm exec prettier --check .` limpos.
- **Observacao para o backend:** `actions/me` e `appeal` autenticam a sessao suspensa, mas `SessionService.authenticate` continua rejeitando access token expirado. Se o access token vencer durante a suspensao, o refresh nao emite novo token e essas rotas passam a `401 invalid_token`; vale validar se a contestacao precisa ficar disponivel durante toda a suspensao.

### 2026-11-15 - Correcao do refresh para conta suspensa

- **Backend:** o refresh mobile de conta suspensa agora rotaciona a sessao e responde `200` com `user.status = "suspended"`. O app deve tratar esse status como suspensao, preservar os tokens e usar o access token apenas em `GET /moderation/actions/me` e `POST /moderation/actions/{id}/appeal`.
- **Escopo:** as demais rotas continuam exigindo conta ativa (`401 invalid_token`); o refresh web do painel continua `401 account_suspended`.
- **Motivo:** o access token expira em poucos minutos e o app precisa renová-lo durante toda a suspensão para manter a contestação disponível.
- **Verificacao:** testes de auth e moderação passaram; suíte completa e contagem no fechamento desta entrada.

### 2026-11-15 - App: refresh 200 de suspensao e notificacao de recurso

- **Escopo:** somente `mobile/`; nenhum arquivo de backend alterado. A API local foi reiniciada antes do teste.
- **Refresh:** ao receber `200` com `user.status = "suspended"`, o app atualiza os tokens, preserva a sessao, nao executa a carga normal e mantem a `SuspendedScreen`. O fallback para `401 account_suspended` continua existindo.
- **Token novo:** o retry automatico do cliente HTTP usa o access token renovado. `GET /moderation/actions/me` e `POST /moderation/actions/{id}/appeal` funcionam mesmo depois da expiracao do access token anterior; as demais rotas seguem `401 invalid_token`.
- **Recuperacao:** com a conta reativada, "Tentar novamente" autentica, recarrega os dados e volta ao app.
- **Notificacao:** a central passou a reconhecer `moderation_appeal_result`, exibir a decisao de `data.decision` como `RECURSO ACEITO` ou `RECURSO REJEITADO` e abrir a tela de moderacao ao tocar.
- **Erros de recurso:** mensagens especificas para `appeal_already_exists`, `action_not_active`, `not_found`, `forbidden` e `account_suspended`. O caso `action_not_active` foi exercitado no aparelho.
- **Verificacao no aparelho:** refresh `200`, sessao preservada, motivo/datas via `actions/me` `200`, notificacao de recurso renderizada com decisao e navegacao para moderacao. O envio de recurso retornou `409 action_not_active` porque a medida foi revogada durante o teste, e o app exibiu a mensagem correta.
- **Comandos:** `pnpm exec tsc --noEmit`, `pnpm exec eslint .`, `pnpm exec prettier --check .` e `pnpm exec expo export --platform android` limpos.
- **Limpeza:** notificacao de teste e medida de teste removidas; denuncia restaurada para `RESOLVED`; conta `Zero Dois` ativa.
- **Observacao:** a conta `Zero Dois` e operadora `ADMIN` em `moderation_operators`, por isso recebe notificacoes internas `moderation_report` com severidade/prioridade. Se a regra for que o app do jogador nunca exiba triagem interna, o backend deve separar o canal do painel ou o app deve filtrar esses kinds quando a conta nao estiver em modo operador.

### 2026-11-15 - CEP e geocodificacao de estabelecimento (Fase 2)

- **Persistencia:** organization_venues ganhou `postal_code` (8 digitos), `geocoding_source`, `geocoding_precision` (`street`/`venue`/`approximate`/`manual`) e `geocoded_at` na migracao `e7f8a9b0c1d2`.
- **Contrato:** `POST`/`PATCH` de venue aceitam CEP com ou sem hifen e a proveniencia da coordenada; `GET` devolve os quatro campos. `latitude`/`longitude` continuam obrigatorias na API.
- **Regra:** sem proveniencia a coordenada e `manual`; mudar coordenada ou CEP sem reenviar proveniencia rebaixa para `manual` e zera `geocoding_source`/`geocoded_at`. `street`/`venue`/`approximate` exigem `geocoding_source` e gravam `geocoded_at` no servidor.
- **Backfill:** registros existentes com coordenada foram marcados como `manual`; nao houve geocodificacao retroativa.
- **Auditoria:** `venue.created`/`venue.updated` registram CEP e mudancas de proveniencia.
- **Testes:** novo teste em `tests/test_organizations.py` para normalizacao, persistencia, rebaixamento para manual, cadastro sem CEP e erros 422; suite completa com **485 passed, 29 skipped**, `ruff` e `mypy` limpos, Alembic no head `e7f8a9b0c1d2`.
- **Limites:** mapa/pino ajustavel, provedor pago e backfill de endereco continuam pendentes.

### 2026-11-15 - Fechamento da Fase 17C: central interna do painel

- **Endpoints dedicados:** `GET /moderation/notifications`, `GET /moderation/notifications/unread-count`, `POST /moderation/notifications/{id}/read` e `POST /moderation/notifications/read-all`, todos com `get_moderator`.
- **Isolamento:** operam sempre `channel = "moderation"`; conta comum recebe `403 moderator_required`; notificacao de outro operador ou do canal `player` responde `404 notification_not_found`.
- **App do jogador:** `GET /me/notifications` continua listando apenas `player`, sem parametro novo e sem mudanca de contrato.
- **Teste:** novo caso em `tests/test_moderation.py` cobre autorizacao, leitura, contagem, `read-all` e isolamento entre operadores e canal.
- **Fase 17:** backend concluido; restam classificador local, suspensao permanente e retencao/LGPD, todos dependentes de politica/dataset.

### 2026-11-15 - App: appeals/me na suspensao e revalidacao automatica

- **Escopo:** somente `mobile/`; API local reiniciada para carregar o endpoint novo. Nenhum arquivo de backend alterado.
- **Endpoint:** `GET /api/v1/moderation/appeals/me` consumido por `mobile/src/api/client.ts` e carregado junto com `actions/me`.
- **SuspendedScreen:** exibe o recurso do jogador com status `EM ANALISE`, `ACEITO` ou `REJEITADO`, datas e `decision_reason` como justificativa. Com recurso existente, o formulario de nova contestacao e ocultado para evitar duplicidade.
- **Atualizacao:** apos enviar, a tela recarrega `actions/me` e `appeals/me` para refletir `OPEN`; a decisao aparece ao reabrir a tela ou tocar em "Tentar novamente".
- **Revalidacao:** a tela agora chama `recheckSuspension` ao montar. Se a conta foi reativada enquanto o app estava fechado, ela volta ao app sem exigir novo login.
- **Notificacoes:** o backend separou os canais; `GET /me/notifications` entrega somente o canal do jogador. O app mantem o tratamento de `moderation_appeal_result` e a navegacao para moderacao.
- **Verificacao:** `pnpm exec tsc --noEmit`, `pnpm exec eslint .`, `pnpm exec prettier --check .` e `pnpm exec export --platform android` limpos. A API registrou `actions/me` e `appeals/me` com `200` durante a suspensao.
- **Limites:** o ADB ficou sem responder no fechamento; a tela de decisao (`REJECTED` com `decision_reason`) foi validada por tipos/compilacao, mas nao teve screenshot final. A conta de teste `Zero Dois` foi reativada e a medida de teste removida.

### 2026-11-15 - Contrato de conta suspensa travado por teste

- **App validou:** refresh `200` com `user.status = "suspended"`, `actions/me` e `appeals/me` `200` com o token novo, recurso aceito com o token novo e `/me/notifications` `401` durante a suspensao.
- **Backend:** o teste de suspensao temporaria agora exige `status`, `reason`, `created_at`, `decided_at` e `decision_reason` em `appeals/me`; confirma que recurso `REJECTED` mantem a conta suspensa, que `moderation_appeal_result` chega no canal `player` com `data.decision` e `data.appeal_id` e que notificacoes internas nao aparecem na central do jogador.
- **Testes:** `tests/test_moderation.py` e `tests/test_auth_flow_api.py` com 24 passed; `ruff` limpo.
- **Sem mudanca de contrato:** os campos e canais esperados pelo app continuam os mesmos.

### 2026-11-15 - Mercado Pago em producao (Bloco A)

- **ADR 0048:** Mercado Pago Orders API passa a ser o PSP do prototipo com jogadores reais; Inter/Pagar.me ficam para o futuro e nao bloqueiam a fase. PLANS, PENDENCIAS, THREAT_MODEL e RUNBOOK atualizados.
- **Configuracao:** fora de local/teste o startup exige `JOGA_PSP_PROVIDER=mercadopago`, token, `JOGA_MERCADO_PAGO_WEBHOOK_SECRET` e URL HTTPS publica; o e-mail global ficticio foi removido.
- **E-mail do pagador:** `users.email` normalizado, `GET/PUT /me/email`, snapshot em `booking_payments`/`purchase_payments` e erro `422 payer_email_required` antes de abrir cobranca com Mercado Pago.
- **Webhook:** evento bruto persistido antes do processamento, replay nao duplica, falha responde 5xx e agenda `next_attempt_at`; worker `scripts.retry_webhooks` com `--dry-run`.
- **Confirmacao local:** `POST /tickets/purchases/{id}/confirm` e `POST /pass/subscriptions/{id}/confirm` seguem dev-only com `403 confirmation_requires_psp`, agora cobertos por teste.
- **Contrato de pagamento (C-01):** reserva e compra expoem `status_detail`, `external_reference` e `amount_cents`, alem dos campos que ja existiam.
- **Parser Orders API:** `date_of_expiration`, `external_reference` e `status_detail` do payload real sao lidos; fixture cobre o formato esperado. Validacao live depende de credenciais.
- **Migracoes:** `f9b0c1d2e3f4` (e-mail), `g0c1d2e3f4a5` (retry) e `h1d2e3f4a5b6` (status detail); `alembic check` limpo no head `h1d2e3f4a5b6`.
- **Testes:** suite completa com **499 passed, 29 skipped**; `ruff`, `ruff format --check` e `mypy app` limpos.
- **Pendente:** MP-03 live, MP-07 reembolso real, MP-08 conciliacao real, MP-09 metricas/alertas, MP-10 MED/chargeback.

### 2026-11-16 - ADR 0049: ledger, taxa e placeholders fiscais

- **Documentos:** ADR 0049, decisoes de backend, termo de referencia e pesquisa de custodia versionados; pendencias juridicas atualizadas.
- **Placeholders:** modulos `fiscal/` e `legal/`, migracao `i2e3f4a5b6c7`, flags da ADR 0049 e `.env.example` corrigido (sem e-mail global e sem "sandbox only"). `money_mode=real` exige referencia, SHA-256 e data do parecer; `custody_model=C` e `fiscal_mode=provider` falham no boot.
- **BUG-01:** aceite de reserva sem e-mail com Mercado Pago responde `422 payer_email_required` e sofre rollback; nenhuma reserva fica aceita pela metade.
- **A49-01:** `money.py` com `compute_fee_cents` (round half up, piso, teto) e `allocate_cents` (resto por assento), com testes de propriedade.
- **A49-02:** ledger de dupla entrada com `ledger_accounts`, `ledger_transactions`, `ledger_entries`, ids idempotentes, validacao de balanceamento no servico, view `v_ledger_balances` e triggers Postgres (saldo diferido e append-only). A tabela antiga `ledger_entries` foi renomeada para `booking_ledger_entries` (migracao `j3f4a5b6c7d8`).
- **Testes:** suite completa com **525 passed, 29 skipped, 1 failed**; a falha e ambiental (`test_access_log_does_not_include_query_string` consulta PostgreSQL e o banco em 127.0.0.1:5434 esta fora do ar). `ruff` e `mypy app` limpos. Alembic nao foi validado enquanto o Postgres estiver parado.
- **Proximo:** A49-03 (migracao de saldos em dry-run) exige PostgreSQL de pe.

### 2026-11-16 - App: pagamento Pix real, e-mail e acessibilidade

- **A3:** alteracoes pendentes de `mobile/` commitadas em `1440751`; depois disso, a entrega abaixo ficou no working tree, sem novo commit.
- **A-EMAIL-01:** `GET/PUT /me/email` consumidos; tela `payment-email`; o checkout de pacote/passe e a solicitacao de reserva exigem e-mail antes da cobranca. `payer_email_required` tambem redireciona para a tela de e-mail.
- **A-PAY-01:** checkout de pacote usa QR/codigo reais, `expires_at`, `status_detail`, `external_reference` e `amount_cents`; polling de 7 s via `/purchases/{id}/sync`; `confirmPurchase` removido. Compra pendente e reaproveitada por `SecureStore` para evitar cobrancas duplicadas.
- **A-PAY-02:** checkout de passe usa QR real e `/subscriptions/{id}/sync`; `passes.confirm` removido; estados pago/expirado/falhou e cancelamento de pendente ao gerar novo Pix.
- **A-PAY-03:** nova tela `booking-payment` le `booking.payments`, mostra QR/status e usa `POST /bookings/{booking}/payments/{payment}/sync`.
- **A-PAY-04:** polling de 7 s, contagem regressiva por `expires_at` e estados pago/expirado/nao concluido nas tres telas.
- **A-PAY-05:** tipos ganharam `status_detail`, `external_reference` e `amount_cents`.
- **A-PAY-06:** `simulatePayment` e os caminhos de confirmacao local foram removidos do app.
- **A-ENV-01:** `EXPO_PUBLIC_API_URL` com fallback local; `mobile/.env.example` adicionado.
- **A-A11Y-01:** preferencias de acessibilidade persistidas em SecureStore; reducao de movimento aplicada as transicoes. Fonte e alvos ampliados ainda nao alteram o layout global.
- **A1/E1:** E2E do backend exercitado com login, suspensao, appeal `200`, `appeals/me` `OPEN`, decisao `REJECTED` com `decision_reason`, `appeals/me` refletindo a decisao e rota normal `401 invalid_token`. Dados de teste limpos. Screenshot final do app bloqueado por ausencia de dispositivo ADB.
- **Verificacao:** `pnpm exec tsc --noEmit`, `pnpm exec eslint .`, `pnpm exec prettier --check .` e `pnpm exec expo export --platform android` limpos. Nenhum arquivo de backend alterado.
- **Pendente:** A-AUTH-01 (passkey WebAuthn real), A-PUSH-01 (token/push exige development build e provedor), A-BUILD-01 (EAS/prebuild/iOS) e A-SCREENS-01 (inventario de telas sem endpoint).

### 2026-11-16 - Auditoria integral e revisao documental (ADR 0049)

- **Escopo:** revisao somente leitura de documentacao, planos, pendencias e codigo; nenhuma alteracao de codigo, banco ou servico. Em seguida, atualizacao documental autorizada pelo usuario.
- **Verificacao backend:** `pytest` com **524 passed, 2 failed, 29 skipped**. Falhas: `test_observability` (PostgreSQL local em 127.0.0.1:5434 parado) e `test_trust` (data fixa; a restricao de 7 dias expirou em 16/11 12:00 UTC). `ruff check` e `mypy` limpos; `ruff format --check` falha em `app/modules/fiscal/service.py:50`.
- **Verificacao mobile:** `tsc --noEmit`, ESLint e Prettier limpos.
- **Verificacao web:** 73 testes passando; typecheck, ESLint, Prettier, build e CSP limpos.
- **Achados P0:** ledger de dupla entrada sem chamador; `compute_fee_cents` sem chamador; T3 expirado sem devolver ingressos; Pix pago + quitacao por ingressos; reembolso sem reversao de repasse; `EXPIRED` viola constraint; migracao `a6b7` dropa constraint com nome divergente; `migrations/env.py` omite fiscal/legal/ledger; `main` 54 commits atras da branch.
- **Documentos atualizados:** `PLANS.md` (14E, 14B, 15, 19A/19B, precedencia 0049), conceito 3.17, tecnica 2.3, `DATA_MODEL.md` 2.0, `PENDENCIAS.md`, `RUNBOOK.md`, `THREAT_MODEL.md`, `JURIDICO_PENDENCIAS.md`, `ESPECIFICACAO_TEMPORADA_E_CATALOGO.md`, `CONTRATO_RESERVAS_APP.md`, `README.md`, `GOALS.md`, `web/README.md`, `mobile/AGENTS.md`, ADRs 0021/0042/0043/0044/0045/0048, fichas 13D/17C e novas fichas 14E/14B.
- **Nao alterado:** `docs/ADR/0049-modelo-tributario-da-intermediacao.md` (decisao vigente, sem alteracao), codigo de aplicacao, migrations, banco e configuracoes.
- **Pendente:** estabilizacao (merge em fatias, CI verde, migrations validadas) antes da 14E.

### 2026-11-16 - Mobile M1 (sem contrato novo)

- **Estado restaurado:** o working tree de `mobile/` estava no `stash@{0}` ("wip frontends e telas antes do merge da onda 0"). O stash foi reaplicado; conflito de `package.json`/`pnpm-lock.yaml` resolvido mantendo Expo 58.0.25 e adicionando `expo-clipboard@~58.0.4`; `pnpm install` e `expo install --check` limpos. Nada foi descartado.
- **Pagamento da reserva:** a cobranca era procurada por `payment.participant_id == session.userId`; o campo e o id da vaga. Agora o app localiza `BookingParticipant` por `user_id` e usa o `id` da vaga para achar a cobranca. O botao "Pagar minha vaga" tambem usa a cobranca da propria vaga.
- **Retry do checkout:** `retry` limpava o estado, mas o efeito de criacao nao dependia de nenhum valor alterado. Foi adicionado um contador `attempt` nas dependencias; pacote e passe voltam a gerar nova cobranca Pix.
- **Polling da fila:** a cada 5 s o app empilhava `lobby-found` com `nav.go`. Agora usa `nav.replace` com guarda local; a tela de busca e substituida uma unica vez.
- **Cold start offline:** a sessao era apagada em qualquer falha de refresh. Agora so `401` encerra a sessao; falha de rede preserva os tokens e abre o app.
- **Dados ficticios removidos (decisao do usuario: manter telas):** fallbacks de passkeys, dispositivos e membros de cla; lista fake de substitutos; mensagens fake do chat de lobby; `2026-Q4` fixo no perfil; toasts de "no prototipo" nessas telas. `security` passou a usar a cerimonia WebAuthn real; `devices` usa apenas `GET /auth/devices`.
- **Acessibilidade global:** `Text` passou a aplicar a escala A/AA/AAA em todos os textos com `fontSize`; `Btn`, `TextBtn`, `IconBtn`, `Chip`, `SegBtn`, `Input`, `ListRow` e a tab bar aumentam quando "alvos ampliados" esta ativo. Preferencias seguem persistidas em SecureStore.
- **Reserva:** confirmacao/recusa de participacao, cancelamento com motivo, pre-check-in e confirmacao de presenca por GPS usam os endpoints existentes. As acoes ficam em `BookingActions`, compartilhado por `booking-t1t2` e `booking-confirmed`.
- **Check-in de partida:** telas deixaram de exibir timer/endereco/distancia fake; usam `check_in_opens_at`, `check_in_deadline` e `POST /matches/{id}/check-in`. "Ativar localizacao" abre as configuracoes do aparelho.
- **Passkey:** o app usa `modules/passkey-proof` com `POST /auth/passkeys/registration/options`, `.../registration/verify` e `.../authentication/options|verify`. Em Expo Go o modulo nativo e `null` e o app informa a limitacao; a cerimonia exige development build Android (iOS segue sem modulo).
- **WebSocket:** cliente `src/api/realtime.ts` conecta em `/api/v1/ws` com `Authorization`, faz ping/pong, reassina lobbies e reconecta. O chat do lobby recarrega em `lobby.message.created`; convites disparam recarga de notificacoes.
- **Verificacao:** `pnpm exec tsc --noEmit`, `pnpm exec eslint .`, `pnpm exec prettier --check .` e `pnpm exec expo export --platform android` limpos. O app abriu no Moto G (Expo Go), com OTP de 6 digitos preenchendo e avancando automaticamente; login E2E nao concluiu porque o backend em execucao recusou `123456` como expirado, entao os fluxos autenticados de reserva/pagamento nao tiveram screenshot.
- **Fora do escopo:** credito em reais, preco em duas linhas, NFS-e, busca de usuario para "adicionar amigo", administracao completa de cla e push real (sem provedor/development build).
- **Nao iniciado:** Fase 18 (Publicidade).

### 2026-11-16 - Onda 1: P0 financeiro

- **T3 expirado:** devolve ingressos consumidos antes de cancelar a reserva; teste cobre saldo antes/depois.
- **Pix + ingressos:** vaga paga por Pix nao aceita quitacao por ingressos; teste garante que o saldo nao e consumido.
- **Reembolso:** status `processing` fica `PENDING` e nao marca jogador como `REFUNDED`; release da quadra vira `REVERSED` ao reembolsar a reserva.
- **Compra:** pacote pendente e unico por jogador/pacote (indice parcial + `IntegrityError`), com teste de concorrencia PostgreSQL; passe ja era idempotente e ganhou teste.
- **Reembolso de compra:** `purchase.apply_status` trata `REFUNDED`, revoga credito nao usado do pacote e cancela a assinatura.
- **Constraint:** `booking_participants.payment_status` aceita `EXPIRED` e `CANCELLED`.
- **Webhook:** payload ganhou hash; mesmo evento com corpo diferente responde `409 webhook_payload_mismatch`; falha de processamento faz rollback antes de gravar `last_error` e `next_attempt_at`.
- **Migracao:** `k5b6c7d8e9f0`; ciclo upgrade/downgrade/upgrade e `alembic check` validados no PostgreSQL.
- **Testes:** `ruff` e `mypy` limpos; suite completa e resultado no fechamento.
- **Proximo:** 14E (ledger em reais, preco em duas linhas) e MP-03/05 live.

### 2026-11-16 - 14E.0: plano de contas do ledger

- **Contas:** modulo `app/modules/ledger/accounts.py` com as 14 contas, prefixos por dono e helpers de codigo.
- **Seed:** migracao `l6c7d8e9f0a1` cria as 10 contas singleton (`psp_clearing`, `bank`, `fee_revenue`, `pass_deferred_revenue`, `pass_revenue`, `tax_payable`, `tax_expense`, `psp_fee_expense`, `writeoff_expense`, `opening_equity`); contas por usuario/quadra continuam sob demanda.
- **Testes:** seed idempotente e compra de credito lancada contra `player_credit`.
- **Migracao:** ciclo downgrade/upgrade e `alembic check` validados no PostgreSQL.
- **Proximo (14E.1):** sombra de escrita no ledger para compra/consumo/estorno, com reconciliador por usuario e sem trocar a leitura.

### 2026-11-16 - S0: reconhecimento e estabilizacao verificada

- **Branch:** `feat/17c-painel-moderacao`, HEAD `37e3871`, 10 commits a frente de `main` e nenhum commit de `main` fora da branch.
- **Arvore suja:** apenas `mobile/`, `web/` e `telas/` de outra sessao. Nada de backend pendente. Os arquivos foram preservados e **nao** commitados nesta etapa.
- **Portoes:** `pytest` **538 passed, 30 skipped**; `ruff check`, `ruff format --check` e `mypy app` limpos. Os P0 de CI (`test_trust` com data fixa, `ruff format` em fiscal, `test_observability`) ja estavam fechados pelos commits `99c5225`, `a8a258e` e `ed61c1e`.
- **Migracoes:** head unico `l6c7d8e9f0a1`; `alembic upgrade head` -> `downgrade base` -> `upgrade head` executados no PostgreSQL local (`127.0.0.1:5434`) e `alembic check` sem diff.
- **`migrations/env.py`:** importa `fiscal`, `legal` e `ledger`; o commit `99c5225` corrigiu a lacuna.
- **`a6b7283c4051`:** o `drop_constraint("status_valid")` resolve para `ck_booking_payments_status_valid` pela convencao de nomes do Alembic; o ciclo completo (inclusive downgrade) passou. Nao foi necessaria migracao corretiva.
- **P0 financeiros:** T3 com devolucao, Pix + ingressos, `REFUNDED` prematuro, reversao de repasse, `EXPIRED` na constraint, idempotencia de compra e revogacao de credito estao implementados por `ed61c1e`, com testes proprios.
- **Pendente para as proximas etapas:** ledger ainda sem chamador, `compute_fee_cents` sem chamador e preco em duas linhas ainda nao persistido.

### 2026-11-16 - 17C.1: PATCH de expediente do estabelecimento

- **API:** `PATCH /api/v1/organizations/{organization_id}/venues/{venue_id}/business-hours/{business_hour_id}` aceita `weekday`, `opens_at` e `closes_at` (parcial), mantendo os demais campos.
- **Validacao:** dia 1-7, abertura antes do fechamento, unicidade exata e ausencia de sobreposicao no mesmo dia. Conflito responde `409 business_hour_conflict`; entrada invalida responde `422 invalid_input`.
- **Autorizacao:** mesma capacidade do `POST`/`DELETE` (`venues:manage`), escopada pela organizacao; membro de outra organizacao recebe `404`.
- **Auditoria:** `venue_business_hour.updated` com `before` e `after`.
- **T2:** confirmado no codigo que `booking_timers`/`response_due_at` sao gravados apenas em `_start_t2`; editar expediente nao recalcula prazos ja gravados.
- **Testes:** 5 novos testes (atualizacao feliz, duplicidade, sobreposicao/encostar, janela invalida e autorizacao negativa) em `tests/test_business_hours.py`; suite completa **543 passed, 30 skipped**.
- **Contrato:** `docs/CONTRATO_RESERVAS_APP.md` e `docs/JOGA_DOCUMENTACAO_TECNICA.md` atualizados.

### 2026-11-16 - 14E.0b: verificacao e fechamento dos P0 financeiros

- **Itens ja fechados em `ed61c1e` e confirmados no codigo:** T3 devolve ingressos (`bookings/service.py:1083-1092`); Pix pago bloqueia quitacao por ingresso (`settle_with_tickets`, linhas 674-679); `REFUNDED` so e gravado quando o estorno retorna `processed` (`payments/service.py:424-447`); reembolso reverte `venue_releases` para `REVERSED` (`financial.py:114-147`); `EXPIRED`/`CANCELLED` aceitos pela constraint (`k5b6c7d8e9f0`); reembolso de compra revoga credito (`purchase.apply_status`); webhook grava hash e responde `409 webhook_payload_mismatch`.
- **Idempotencia de compra:** `POST /me/tickets/purchases` e `POST /me/pass/subscriptions` passaram a aceitar `Idempotency-Key` opcional. Replay do mesmo corpo devolve a resposta gravada; a mesma chave com outro pacote/plano responde `409 idempotency_conflict`. Sem o cabecalho, a regra de pendencia unica continua igual.
- **Testes:** `test_purchase_idempotency_key_replays_without_second_charge` e `test_pass_idempotency_key_replays_and_rejects_different_plan`, alem dos testes existentes de T3, Pix + ingressos, refund `processing`, reversao de release, compra concorrente (PostgreSQL) e replay de webhook.
- **Concorrencia (2):** `settle_with_tickets` e `register_payment_result` adquirem `SELECT ... FOR UPDATE` na reserva antes de ler o estado da vaga; a checagem de cobranca paga acontece depois do lock.
- **Item (5):** e uma constraint de schema validada pela migracao aditiva `k5b6c7d8e9f0` e pelo teste de modelo `test_participant_accepts_expired_payment_status`; nao ha cenario concorrente aplicavel.
- **Verificacao:** `ruff`, `ruff format --check`, `mypy app` limpos; suite **545 passed, 30 skipped**.

### 2026-11-16 - 14E.0c: sanidade do plano de contas e invariante do credito

- **Plano:** `app/modules/ledger/accounts.py` contem as 14 contas (10 singleton + 4 prefixos por dono) e a migracao `l6c7d8e9f0a1` semeia as 10 globais. Contas por usuario/quadra sao criadas sob demanda por `LedgerService.account`, com `owner_kind`/`owner_id`.
- **Sanidade:** novo teste carrega a migracao de seed por caminho e compara `ACCOUNTS` com `SINGLETON_ACCOUNTS`; outro teste garante que todo prefixo por dono tem tipo declarado e nao colide com contas globais.
- **Balanceamento:** `LedgerService.post` ja rejeita transacao desbalanceada, valor nao positivo, partida duplicada na mesma conta/direcao e chave vazia; testes existentes cobrem inclusive 100 transacoes aleatorias.
- **Invariante:** `tests/test_ledger_invariant.py` define `assert_credit_invariant` (saldo de `player_credit:<user>` == lotes de compra pelo preco pago). O teste esta **explicitamente ignorado** com motivo `14E.1` porque nenhum fluxo escreve no ledger ainda; sera habilitado na Etapa 6.
- **Leitura:** nenhuma leitura publica mudou.
- **Verificacao:** `9 passed, 1 skipped` nos testes do ledger; `ruff` e formatacao limpos.

### 2026-11-16 - 14E.1: preco em duas linhas e semantica do credito

- **Preco congelado:** a reserva nova grava `venue_price_cents`, `fee_cents`, `fee_percent_applied`, `total_cents` e `pricing_version="adr0049_v1"`. `compute_fee_cents` e a unica fonte do calculo, com `fee_percent_bps` e `fee_min_cents` vindos da configuracao (sem aliquota no codigo).
- **Rateio e repasse:** a soma dos `contribution_cents` usa `total_cents` (espaco + taxa); o repasse da quadra continua sobre `venue_price_cents` (o valor do espaco nunca e receita do JOGA).
- **Migracao `m7d8e9f0a1b2`:** colunas aditivas em `bookings`, backfill `legacy_v0` (`fee=0`, `total=price`), `ticket_lots.period` e backfill de passe por `expires_at - 1 mes`; constraint `total_cents = venue_price_cents + fee_cents` e `source <> 'pass' OR period IS NOT NULL`. Downgrade funcional.
- **Credito:** comprado e devolucao nunca expiram; `expire_due` so encerra passe por competencia vencida e `free_level`/`admin` por `expires_at`; passe entrega `period` (`YYYY-MM`) e nao grava mais `expires_at`; franquia nao acumula.
- **Ordem de consumo:** `pass -> free_level -> admin -> purchase -> refund` (ADR 0049 §9.1), com teste proprio.
- **Contrato:** `BookingView` ganhou os cinco campos (aditivo); `GET /me/tickets` ganhou `period` no lote. `CONTRATO_RESERVAS_APP.md`, `DATA_MODEL.md` e `PENDENCIAS.md` atualizados.
- **Testes:** reserva grava as quatro colunas com piso/soma; credito comprado sobrevive a `expire_due`; passe nao acumula e expira por periodo; ordem de consumo; suite **548 passed, 31 skipped**; `ruff`, formatacao e `mypy` limpos.
- **Migracao validada:** `upgrade head`, `downgrade -1`, `upgrade head` e `alembic check` sem diff no PostgreSQL local.
- **Fora do escopo desta etapa:** escrita no ledger e inversao da leitura (14E.2/14E.3).

### 2026-11-16 - 14E.2: sombra de escrita do ledger e consumo em reais

- **Decisão aplicada (adendo §11):** a vaga consome `contribution_cents`; `k = ceil(contribution / 310)` é exibição e baixa de lote; o ticket vale R$ 3,10.
- **Schema (`n8e9f0a1b2c3`):** `ticket_lots.remaining_cents`, `ticket_lot_consumptions.amount_cents`, `booking_participants.space_charge_cents`/`fee_charge_cents`/`funding_source`, conta `purchase_premium_deferred`. Backfill de `remaining_cents = remaining × 310`, rateio retroativo em duas linhas e origem de quitação. Downgrade funcional.
- **Rateio:** `venue_price_cents` e `fee_cents` são divididos separadamente; `Σ espaço = venue_price`, `Σ taxa = fee` e `space + fee = contribution`.
- **Consumo:** `settle_with_tickets` usa `contribution_cents`; `ticket_lot_consumptions.amount_cents` fecha a cota e `booking_participants.tickets_consumed` guarda `k`. Vaga coberta por passe/grátis/admin não debita `player_credit` e é marcada como excluída (Etapa 6b).
- **Ledger:** compra (`purchase:{id}`) com prêmio em `purchase_premium_deferred`; confirmação (`booking:{id}:confirm`) debita `player_credit` ou `psp_clearing` e credita `venue_payable` + `fee_revenue`; devolução (`booking:{id}:refund`) usa payable/receivable conforme o repasse; liberação (`release:{id}`); passe (`pass:{id}:sale`, `pass:{id}:month:{n}`); reembolso Pix (`payment_refund:{id}`); reversão de compra/chargeback (`purchase_refund:{id}`) com receivable do jogador.
- **Abertura e reconciliação:** `ledger/opening.py` (dry-run e `opening:{user}` contra `opening_equity`, lendo `remaining_cents`) e `ledger/reconciliation.py` (ledger × lotes, lista vagas excluídas). CLIs: `scripts/ledger_opening.py` e `scripts/reconcile_ledger.py`.
- **Invariante sem skip:** `tests/test_ledger_invariant.py` valida compra, quitação (ledger == contribution == consumo, tickets == k) e ausência de saldo negativo. `tests/test_ledger_shadow.py` cobre regra 4 crédito/Pix, regra 5, regras 6/7, 8/9, 10/11, abertura idempotente e reconciliação limpa.
- **Verificação:** `559 passed, 30 skipped`; `ruff`, `ruff format --check` e `mypy app` limpos; `upgrade head`, `downgrade -1`, `upgrade head` e `alembic check` sem diff no PostgreSQL.
- **Fora do escopo:** leitura pública (Etapa 7), vagas por passe/grátis/admin (Etapa 6b) e classificação contábil do prêmio.
