# Registro de execução das fases

Este arquivo registra fatos observados, não intenções. Só marcar uma fase como `Complete` após executar e comprovar seus critérios de aceite.

| Fase | Status | Branch | Evidências | Bloqueios |
|---|---|---|---|---|
| 0 — Repositório e governança | Complete | `main` | Documentação governada; remoto local e GitHub confirmam `kramirodev/Joga`; critérios da Fase 0 verificados | — |
| 1 — Prova técnica mobile/nativa | In progress | `feat/01-prova-mobile-nativa` | Build Android próprio instalado e executado no Moto G24 e no moto g(7) play; permissões precisa/aproximada/negada provadas; React Native CLI comparado; OTP por SMS com adapter simulado (12 testes); ADR 0009 aprovado (Expo development build); associação Android publicada em `https://joga-passkeys.vercel.app` e reconhecida pela API Digital Asset Links; cerimônia de passkey Android executada via Credential Manager (criação + autenticação, `rpIdHashMatches: true`); ADR 0011 | iOS/Xcode e associação AASA pendentes, por decisão de manter a fase em andamento |
| 2 — Fundação de engenharia | Complete | `feat/02-fundacao-engenharia` | Backend FastAPI mínimo com health live/ready, PostgreSQL/PostGIS local, migração baseline reversível, lint/formatação/tipos/testes verdes, CI verde nos dois jobs (run 41475001880) e app aberto no Moto G24 e no moto g(7) play (Android 10, 32 bits, APK nativo) | — |
| 3 — Identidade e segurança | Complete | `feat/03-identidade-e-seguranca` | ADRs 0012–0017; backend de identidade com OTP, contas, sessões, passkeys, telefone, dispositivos, recuperação e retenção; app Android integrado (OTP, passkey real, troca de telefone); 95 testes unitários/API + 5 de integração PostgreSQL | iOS/AASA bloqueado e formalmente aceito no ADR 0017; SMS real e ratificação de produção pendentes |
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
