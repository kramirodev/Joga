# Registro de execução das fases

Este arquivo registra fatos observados, não intenções. Só marcar uma fase como `Complete` após executar e comprovar seus critérios de aceite.

| Fase | Status | Branch | Evidências | Bloqueios |
|---|---|---|---|---|
| 0 — Repositório e governança | Complete | `main` | Documentação governada; remoto local e GitHub confirmam `kramirodev/Joga`; critérios da Fase 0 verificados | — |
| 1 — Prova técnica mobile/nativa | In progress | `feat/01-prova-mobile-nativa` | Build Android próprio instalado e executado no Moto G24; permissões precisa/aproximada/negada provadas; React Native CLI comparado; OTP por SMS com adapter simulado (12 testes); ADR 0009 aprovado (Expo development build) | Domínio/RP com arquivos reais e iOS/Xcode pendentes, por decisão de manter a fase em andamento |
| 2 — Fundação de engenharia | In progress | `feat/02-fundacao-engenharia` | Backend FastAPI mínimo com health live/ready, PostgreSQL/PostGIS local, migração baseline reversível, lint/formatação/tipos/testes verdes, CI escrita e app aberto no Moto G24 via Expo Go | CI ainda não observada no GitHub Actions; build nativo não repetido por ausência de Android SDK no ambiente atual |
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
