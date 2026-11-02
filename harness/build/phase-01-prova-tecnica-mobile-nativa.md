# Fase 01 — Prova técnica mobile/nativa

**Status:** Em andamento — app e leitura foreground exercitados no Expo Go/Android; provas nativas completas pendentes
**Branch:** `feat/01-prova-mobile-nativa` em `kramirodev/Joga`

## Fontes e contexto

- `AGENTS.md`
- `GOALS.md`
- `PLANS.md` (fonte normativa das fases)
- `docs/DOCUMENTACAO_TECNICA.md`, especialmente seções 3, 5.4, 6 e 18
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

- O preflight encontrou Node 24.22.1, pnpm 11.25.0 e Java 25.0.2. O `adb` inicial 1.0.31 foi substituído para esta sessão/workspace pelo Platform-Tools oficial 37.0.1 (ADB 1.0.41), guardado em `.tools/` e ignorado pelo Git. Android SDK, `emulator`, macOS e `xcodebuild` continuam indisponíveis.
- O scaffold Expo existente declara Expo `~58.0.22`, React Native `0.88.1`, React `19.3.0` e TypeScript `~6.0.3`; o lockfile foi instalado em modo frozen e o pacote compatível `expo-location ~58.0.20` foi adicionado. TypeScript e `expo install --check` passaram. Ainda não há development client nem integração de passkeys; execução em Expo Go não valida build nativo.
- O Moto G24 foi autorizado; `adb devices -l` retornou `0087722228 device` (`moto_g24`).
- ADB 1.0.41 confirmou novamente o Moto G24 como autorizado (`0087722228 device`) e o encaminhamento `tcp:8081 tcp:8081` ativo.
- O Metro local respondeu HTTP 200, compilou o bundle Android (`index.ts`, 721 módulos), e a tela JOGA foi confirmada no Expo Go.
- `pnpm exec expo prebuild --platform android --no-install` gerou o projeto nativo `mobile/android/`, ignorado pelo Git, e atualizou `mobile/app.json`/scripts de plataforma. O package ID `com.anonymous.joga` é valor padrão gerado, provisório e pendente de decisão.
- `mobile/android/gradlew.bat assembleDebug` iniciou Gradle 9.4.1 após baixar a distribuição com acesso de rede aprovado, mas não chegou a apresentar resultado de compilação; a tentativa foi interrompida. Android SDK/build-tools não estão configurados, então build nativo não está comprovado.
- Ferramentas oficiais Android SDK CLI para Windows (`15859902`) foram baixadas em `.tools/android-sdk/cmdline-tools/latest` e verificadas pelo SHA-256 publicado pelo Android. Plataformas/build-tools não foram instalados porque a aceitação de licenças precisa ser feita pelo usuário; build Android continua bloqueado por isso e pela configuração restante.
- `expo-location` `~58.0.20` foi instalado via `pnpm exec expo install`; permissão foreground retornou `fine` e uma leitura única concluiu com precisão estimada de 100 m. Coordenadas não foram exibidas nem persistidas.
- Não foram testadas localização aproximada/negada nem permissions num app nativo próprio; no Expo Go a permissão pertence ao app hospedeiro Expo Go.
- A leitura do bundle via Expo Go não comprova build de desenvolvimento com módulos nativos próprios. Sem Android SDK/toolchain não é possível completar o build nativo Android; sem macOS/Xcode não é possível completar o build/teste nativo iOS.
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
- `mobile/android/gradlew.bat assembleDebug` (tentativa inconclusiva; Gradle 9.4.1 iniciou, sem resultado de compilação; Android SDK/build-tools ausentes)
- Nova execução de `pnpm exec tsc --noEmit` (passou)
- Nova tentativa de `pnpm exec expo install --check` (sandbox bloqueou acesso à rede; repetida com rede aprovada e estado Expo em `%TEMP%`, resultado `Dependencies are up to date`)

Resultados: manifesto e lockfile instalaram 454 dependências fixadas; TypeScript passou; `expo config` mostrou apenas permissões coarse/fine de localização; Metro respondeu `packager-status:running` e HTTP 200; bundle Android compilado e tela JOGA aberta no Moto G24. A leitura foreground `fine` concluiu com precisão estimada de 100 m. `expo prebuild` gerou o projeto Android, mas `assembleDebug` não foi concluído; Android SDK/build-tools, emulador e Xcode continuam ausentes.

## Critérios de aceite

- [ ] ADR compara Expo development build e React Native CLI e decide com evidências e versões.
- [ ] Protótipo mínimo builda e abre em Android e iOS, ou limitação/bloqueio de plataforma fica documentado sem declarar suporte completo.
- [ ] Registro/autenticação de passkey é exercitado nos dois sistemas ou bloqueios são detalhados por sistema.
- [ ] Requisitos de domínio/RP e arquivos de associação são validados; não registrar/hospedar domínio sem autorização.
- [ ] Localização aproximada, precisa e negada é exercitada; busca manual permanece viável.
- [ ] SMS funciona em sandbox autorizada ou adaptador simulado, sem custos não aprovados.
- [ ] Versões, limitações, comandos e evidências estão registrados no ADR e build log.
- [ ] `git diff --check` passa; nenhum segredo real foi adicionado.

## Condição de parada

Fase 0 concluída. A prova está em andamento no workspace vinculado a `kramirodev/Joga`. Expo Go no Moto G24 comprova execução do bundle e uma leitura de localização em primeiro plano, mas não substitui builds nativos; a geração do projeto Android também não comprova build. Ainda faltam Android SDK/toolchain, ambiente macOS/Xcode (ou cloud autorizado), provas de permissão aproximada/negada, passkeys/domínio, SMS e comparação CLI. Não iniciar a Fase 2 automaticamente.
