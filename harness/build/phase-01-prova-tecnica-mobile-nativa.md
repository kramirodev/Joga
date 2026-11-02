# Fase 01 — Prova técnica mobile/nativa

**Status:** Em andamento — build Android próprio gerado, instalado e executado no Moto G24; permissões precisa, aproximada e negada provadas no app; iOS, passkeys e SMS pendentes
**Branch:** `feat/01-prova-mobile-nativa` em `kramirodev/Joga`

## Fontes e contexto

- `AGENTS.md`
- `GOALS.md`
- `PLANS.md` (fonte normativa das fases)
- `docs/JOGA_DOCUMENTACAO_TECNICA.md`, especialmente seções 3, 5.4, 6 e 26
- `harness/build-log.md`
- `harness/build/phase-00-repositorio-e-governanca.md`

## Objetivo

Obter evidência técnica em Android e iOS para escolher a estratégia React Native e validar os pontos nativos críticos antes de fixar bibliotecas: build, passkeys e associação de domínio, permissões de localização e integração de SMS em sandbox ou por adaptador simulado.

## Escopo

- Comparar Expo com development builds e React Native CLI com evidências práticas.
- Inspecionar o scaffold Expo já existente em `mobile/`; não o tratar como prova de build.
- Abrir/buildar o protótipo em Android e iOS quando os toolchains/dispositivos estiverem disponíveis.
- Provar o caminho de registro e autenticação de passkey nos dois sistemas e validar requisitos de RP/domínio/associação.
- Testar permissões de localização aproximada, precisa e negada, mantendo busca manual possível.
- Validar envio SMS somente em sandbox autorizada ou com adaptador simulado.
- Registrar decisão, versões, limitações, comandos e evidências em ADR.

## Fora do escopo

- Telas completas ou fluxo de conta de produção.
- Backend de produto, tabelas, banco de dados, autenticação de produção ou matchmaking.
- Uso de credenciais reais ou geração de custos sem autorização.
- Compra, registro, DNS ou hospedagem de domínio sem autorização específica.
- Publicar commits/PRs fora do escopo até uma solicitação explícita para publicar estas alterações.
- Iniciar a Fase 2.

## Pré-requisitos e dependências

- Fase 0 concluída conforme `PLANS.md`.
- Repositório `kramirodev/Joga` confirmado e workspace vinculado.
- Ambiente macOS/Xcode disponível para build e teste nativo de iOS; Windows não substitui esse requisito.
- SDK Android, device/emulator e toolchain necessários disponíveis.
- Aprovação de qualquer serviço externo, custo ou credencial real.

## Arquivos/componentes esperados

- `mobile/` com o protótipo mínimo e lockfile fixado, após escolha técnica.
- Configuração nativa Android/iOS necessária ao protótipo.
- Arquivos de associação somente se domínio e hospedagem forem aprovados; caso contrário, evidenciar bloqueio e requisitos.
- `docs/ADR/` com comparação, decisão, versões, evidências e limitações.
- `harness/build-log.md` com comandos executados e resultados comprovados.

## Riscos e decisões pendentes

- Ambiente verificado em 2026-11-02: Node 24.22.1 portable em `.tools/nodejs`, pnpm 11.25.0 via Corepack, JDK 17.0.20.1 portable em `.tools/temurin-17`; Platform-Tools 37.0.1 (ADB 1.0.41); Android SDK em `.tools/android-sdk` com plataformas 36 e 37.0, Build Tools 36.0.0 e 37.0.0, NDK 27.1.12297006 e licenças presentes. O Moto G24 (`0087722228`) está conectado e autorizado. `emulator`, macOS e `xcodebuild` continuam indisponíveis.
- O scaffold Expo existente declara Expo `~58.0.22`, React Native `0.88.1`, React `19.3.0` e TypeScript `~6.0.3`; o lockfile foi instalado em modo frozen e o pacote compatível `expo-location ~58.0.20` foi adicionado. TypeScript e `expo install --check` passaram. Ainda não há development client nem integração de passkeys; execução em Expo Go não valida build nativo.
- O Moto G24 foi autorizado; `adb devices -l` retornou `0087722228 device` (`moto_g24`).
- ADB 1.0.41 confirmou novamente o Moto G24 como autorizado (`0087722228 device`) e o encaminhamento `tcp:8081 tcp:8081` ativo.
- O Metro local respondeu HTTP 200, compilou o bundle Android (`index.ts`, 721 módulos), e a tela JOGA foi confirmada no Expo Go.
- `pnpm exec expo prebuild --platform android --no-install` gerou o projeto nativo `mobile/android/`, ignorado pelo Git, e atualizou `mobile/app.json`/scripts de plataforma. O package ID `com.anonymous.joga` é valor padrão gerado, provisório e pendente de decisão.
- A primeira tentativa de `mobile/android/gradlew.bat assembleDebug` foi interrompida e não comprovou build; essa tentativa ocorreu antes da verificação posterior do SDK completo.
- A verificação posterior confirmou que ferramentas oficiais Android SDK CLI, plataformas 36/37.0, Build Tools 36.0.0/37.0.0, NDK 27.1.12297006 e licenças já estão presentes em `.tools/android-sdk`. Não foi necessário instalar pacotes nem aceitar licenças nesta execução.
- Em 2026-11-02, `pnpm exec expo run:android --no-build-cache --device 0087722228` executou por 13m59s, completou configurações de Android/manifest/resources e Kotlin de `expo-modules-core`, mas falhou em `:expo-modules-core:buildCMakeDebug[arm64-v8a]`: Ninja 1.10.2 reportou `manifest 'build.ninja' still dirty after 100 tries` após 100 reconfigurações CMake. Não gerou APK, não instalou nem abriu o app. A lista de fontes C++ em `VerifyGlobs.cmake` correspondia ao filesystem na inspeção pós-falha.
- Diagnóstico isolado reproduziu a falha sem `--configure-on-demand` e sem build completo. `ninja -d explain` apontou o target phony `CMakeFiles/VerifyGlobs.cmake_force` como dirty e múltiplos inputs de configuração CMake/NDK; o script de glob não encontrou divergência de fontes. Relógio do Windows estava sincronizado por NTP, sem salto reportado. O maior caminho absoluto de objeto C++ gerado em `build.ninja` media 283 caracteres; `CMAKE_OBJECT_PATH_MAX` estava em 1024 e `LongPathsEnabled=1`, o que manteve a hipótese de caminho longo em aberto naquele momento.
- `expo-location` `~58.0.20` foi instalado via `pnpm exec expo install`; permissão foreground retornou `fine` e uma leitura única concluiu com precisão estimada de 100 m. Coordenadas não foram exibidas nem persistidas.
- **Causa raiz confirmada (2026-11-02):** o ciclo CMake/Ninja era efeito do comprimento dos caminhos absolutos do store virtual do pnpm. Com o layout `isolated`, `node_modules/.pnpm/expo-modules-core@<versão>_<hash>/node_modules/expo-modules-core/android` media 168 caracteres e os objetos C++ chegavam a 283, acima do limite clássico de 260 do Windows; o Ninja embutido no CMake 3.22.1 não trata caminhos longos. A prova de controle com store em `C:\p` (caminho curto) compilou o mesmo alvo sem reconfigurações.
- **Correção aplicada:** `mobile/pnpm-workspace.yaml` com `nodeLinker: hoisted` — configuração que o Expo documenta e que o `create-expo-app` usa por padrão para pnpm. O pnpm 11 ignora `node-linker` no `.npmrc`; a opção precisa estar em `pnpm-workspace.yaml` (ou via `--config.node-linker`). Reinstalação offline com `--frozen-lockfile` levou 1m50s e não alterou o lockfile.
- Efeito medido: caminho de `node_modules/expo-modules-core/android` caiu de 168 para 58 caracteres; maior caminho de objeto C++ caiu de 283 para 203.
- `pnpm exec expo prebuild --platform android --no-install` foi refeito sobre o novo layout; `pnpm exec expo run:android --device 0087722228` concluiu em 4m41s, gerou APK de 47,6 MB, instalou e abriu `com.anonymous.joga/.MainActivity` no Moto G24 com Metro conectado (`tcp:8081`).
- Testes de permissão no app próprio (Android 14, Moto G24): **precisa** → `precisão fine`, leitura única com 32 m; **aproximada** (revogado só `ACCESS_FINE_LOCATION`) → `precisão coarse`, leitura com 2000 m; **negada** → mensagem de permissão negada, leitura bloqueada com orientação para autorizar. O diálogo do sistema exibiu `Exata`/`Aproximada`, `Durante o uso do app`/`Apenas esta vez` e `Não permitir`.
- O rodapé da tela citava `Expo Go`; foi corrigido para o app JOGA e o recarregamento foi confirmado no aparelho.
- O build de desenvolvimento Android com módulos nativos próprios está comprovado: APK gerado, instalado e executado no Moto G24. Continua faltando o build/teste nativo iOS, que exige macOS/Xcode (ou build cloud autorizado).
- Domínio técnico é necessário para associações de passkey conforme o fluxo escolhido; qualquer registro/hospedagem requer autorização.
- Bibliotecas, estratégia Expo/CLI, SMS provider e integração devem ser escolhidos apenas com evidências do protótipo.

## Plano Red / Green / Refactor / Verify

- **Red:** registrar a falta de protótipos executáveis e a indisponibilidade de toolchains/plataformas no ambiente atual.
- **Green:** implementar o menor protótipo isolado que exercite os fluxos nativos autorizados, após o destino e os ambientes estarem disponíveis.
- **Refactor:** remover experimentos redundantes e documentar a decisão sem expandir para telas ou backend de produto.
- **Verify:** build e execução em Android e iOS; passkey e associação de domínio; permissões aproximada/precisa/negada; SMS simulado ou sandbox; revisão de segredos, versões, diff e evidências.

## Comandos reais de validação

Comandos executados na prova de viabilidade e no protótipo atual:

- `Get-Command node,npm,npx,corepack,pnpm,yarn,java,adb,emulator,xcodebuild,gradle,python,py,git -ErrorAction SilentlyContinue`
- `node --version`
- `java -version`
- `adb devices -l`
- `git remote -v`
- `pnpm install --frozen-lockfile --network-concurrency=3 --fetch-timeout=600000`
- `pnpm exec expo install expo-location`
- `pnpm exec tsc --noEmit`
- `pnpm exec expo config --type public --json`
- `pnpm exec expo start --localhost --go --clear` (estado Expo redirecionado para `%TEMP%\joga-expo-home`; telemetria desativada)
- `Invoke-RestMethod http://127.0.0.1:8081/status`
- ADB 1.0.41: `devices -l`, `reverse tcp:8081 tcp:8081`, abertura via Expo Go e consulta da árvore acessível da tela
- `pnpm exec expo prebuild --platform android --no-install`
- `pnpm exec expo run:android --no-build-cache --device 0087722228` (falhou após 13m59s em `expo-modules-core:buildCMakeDebug[arm64-v8a]`, Ninja `build.ninja still dirty after 100 tries`; sem APK)
- `mobile/android/gradlew.bat :expo-modules-core:buildCMakeDebug[arm64-v8a] --dry-run --no-configure-on-demand --console=plain -PreactNativeArchitectures=arm64-v8a -PreactNativeDevServerPort=8081` (passou; confirmou task e versões de SDK/NDK/Build Tools/Kotlin selecionadas)
- `mobile/android/gradlew.bat :expo-modules-core:buildCMakeDebug[arm64-v8a] --no-configure-on-demand --info --stacktrace --console=plain -PreactNativeArchitectures=arm64-v8a -PreactNativeDevServerPort=8081` (falhou em 1m19s, reproduzindo Ninja `build.ninja still dirty after 100 tries`)
- Ninja 1.10.2 diretamente: `ninja -C <expo-modules-core/android/.cxx/Debug/.../arm64-v8a> -d explain expo-modules-v2` (reproduziu falha e listou dependências CMake/NDK dirty; sem `GLOB mismatch`)
- Nova execução de `pnpm exec tsc --noEmit` (passou)
- Nova tentativa de `pnpm exec expo install --check` (sandbox bloqueou acesso à rede; repetida com rede aprovada e estado Expo em `%TEMP%`, resultado `Dependencies are up to date`)
- Criação de `mobile/pnpm-workspace.yaml` com `nodeLinker: hoisted` e reinstalação `pnpm install --frozen-lockfile --offline` (1m50s; layout confirmado em `node_modules/.modules.yaml`)
- `pnpm exec expo prebuild --platform android --no-install` sobre o layout hoisted (`prebuild-exit=0`)
- `mobile/android/gradlew.bat :expo-modules-core:buildCMakeDebug[arm64-v8a] --no-configure-on-demand --console=plain -PreactNativeArchitectures=arm64-v8a -PreactNativeDevServerPort=8081` (passou em 5m06s, zero reconfigurações CMake)
- `pnpm exec expo run:android --device 0087722228` (passou em 4m41s; 176 tasks; APK 47,6 MB; instalado e aberto no Moto G24)
- ADB 1.0.41 no app próprio: `dumpsys package com.anonymous.joga` (estado das permissões), `pm revoke`/`pm grant` de `ACCESS_FINE_LOCATION` e `ACCESS_COARSE_LOCATION`, `am force-stop`/`am start`, `uiautomator dump` e `input tap` para os três cenários de permissão
- `pnpm exec tsc --noEmit` e `pnpm exec expo install --check` após a correção do texto da tela (ambos passaram)

Resultado atual: as 492 dependências foram instaladas offline em layout hoisted sem alterar o lockfile; `pnpm exec tsc --noEmit` e `pnpm exec expo install --check` passam; o build Android de desenvolvimento concluiu, gerou APK de 47,6 MB, instalou e abriu o app no Moto G24 com Metro conectado; as três variações de permissão (precisa, aproximada, negada) foram exercitadas no app próprio e a tela recarregou com o texto corrigido. `emulator`, macOS e Xcode continuam ausentes; iOS, passkeys/domínio e SMS seguem pendentes.

## Critérios de aceite

- [ ] ADR compara Expo development build e React Native CLI e decide com evidências e versões.
- [x] Protótipo mínimo builda e abre em Android e iOS, ou limitação/bloqueio de plataforma fica documentado sem declarar suporte completo. — Android comprovado (build, instalação e execução); iOS documentado como bloqueado por ausência de macOS/Xcode.
- [ ] Registro/autenticação de passkey é exercitado nos dois sistemas ou bloqueios são detalhados por sistema.
- [ ] Requisitos de domínio/RP e arquivos de associação são validados; não registrar/hospedar domínio sem autorização.
- [x] Localização aproximada, precisa e negada é exercitada; busca manual permanece viável. — Provado no app próprio em Android: fine (32 m), coarse (2000 m) e negada, com leitura bloqueada.
- [ ] SMS funciona em sandbox autorizada ou adaptador simulado, sem custos não aprovados.
- [ ] Versões, limitações, comandos e evidências estão registrados no ADR e build log. — Parcial: build log e ficha da fase atualizados; ADR comparativo pendente.
- [x] `git diff --check` passa; nenhum segredo real foi adicionado.

## Condição de parada

Fase 0 concluída. A prova está em andamento no workspace vinculado a `kramirodev/Joga`. O build Android de desenvolvimento com módulos nativos próprios está comprovado (APK instalado e executado no Moto G24) e as permissões de localização precisa, aproximada e negada foram exercitadas no app. Ainda faltam: ambiente macOS/Xcode (ou cloud autorizado) para iOS, passkeys/domínio, SMS simulado ou sandbox e a comparação Expo development build × React Native CLI com ADR. Não iniciar a Fase 2 automaticamente.
