# ADR 0006 — Resultados preliminares da prova mobile/nativa

- **Status:** Em avaliação; nenhuma escolha de framework ou biblioteca foi ratificada.
- **Data:** 2026-11-02
- **Decisores:** responsável pelo produto e equipe técnica; decisão final pendente de prova executável Android/iOS.

## Contexto

A Fase 1 precisa comparar Expo development build com React Native CLI e provar build, passkeys/associação de domínio e permissões de localização em Android e iOS antes de fixar a tecnologia mobile.

## Evidências observadas

- O workspace contém um scaffold mínimo Expo em `mobile/`, declarando Expo `~58.0.22`, React Native `0.88.1`, React `19.3.0` e TypeScript `~6.0.3`.
- O lockfile `mobile/pnpm-lock.yaml` foi inicialmente gerado sem instalar dependências; depois, as dependências foram instaladas em modo frozen. O protótipo inclui `expo-location`, mas ainda não inclui development client ou integração de passkeys. Scaffold, lockfile e execução em Expo Go não comprovam build nativo.
- No ambiente Windows disponível, Node `24.22.1`, pnpm `11.25.0`, Java `25.0.2` e adb antigo `1.0.31` estavam no PATH. Android SDK, emulador e Xcode/macOS não estão disponíveis.
- O Moto G24 foi autorizado via USB. Para este workspace foi baixado o Platform-Tools oficial `37.0.1` (ADB `1.0.41`) em `.tools/`, ignorado pelo Git. O dispositivo passou a aparecer como `device`; o ADB atualizado encaminhou a porta local `8081`.
- O Metro respondeu HTTP 200 e compilou `index.ts` para Android (721 módulos). A atividade Expo Go `ExperienceActivity` abriu e a árvore de acessibilidade exibiu a tela JOGA.
- Foi adicionado `expo-location` `~58.0.20`, compatível com SDK 58. A tela de prova solicita somente permissão foreground e oferece leitura única; `app.json` contém permissões coarse/fine e mensagem de uso durante busca, sem configurar background.
- No Moto G24, a permissão retornou `fine`. Uma leitura única concluiu com precisão estimada de `100 m`; a UI confirma que coordenadas não foram exibidas nem armazenadas. Localização aproximada e negada ainda não foram exercitadas.
- O primeiro servidor Metro retornou HTTP 500 ao tentar escrever estado do Expo em `.expo` no perfil pessoal. O servidor foi reiniciado com estado local apontado para `%TEMP%\joga-expo-home` e telemetria desativada; depois disso respondeu HTTP 200 e compilou o app. Na execução final, o cache DotSlash foi apontado para `%TEMP%\joga-dotslash-cache`, mas a busca da versão mais recente do React Native DevTools falhou por rede e usou fallback; isso não bloqueou Metro ou o app.
- A primeira consulta ao registry foi bloqueada por EACCES no sandbox. Com acesso de registry aprovado, `pnpm install --lockfile-only --ignore-scripts` gerou lockfile sem instalar dependências; nenhum `node_modules` foi criado.
- A prova de passkeys depende da associação do app a um domínio HTTPS controlado pelo projeto, incluindo os arquivos de associação requeridos pelas plataformas. O projeto ainda não tem domínio selecionado/configurado; não se registrou nem hospedou domínio.
- Foi pesquisada uma biblioteca React Native/Expo de passkeys como candidata, mas não testada. Não há evidência suficiente para recomendá-la como dependência do produto.

## Decisão provisória

Manter Expo development build e React Native CLI como alternativas em avaliação. Não fixar framework, versões finais ou biblioteca de passkeys até que o protótipo passe por builds e testes nativos em ambas as plataformas. O bloqueio de ambiente não é evidência de incompatibilidade técnica.

## Próximas evidências necessárias nesta fase

1. **Comprovado:** lockfile validado offline/congelado, dependências instaladas, `expo install --check` e `tsc --noEmit` passaram.
2. Build e execução em Android e iOS, registrando sistema, toolchain e comandos.
3. Comparação prática com React Native CLI ou justificativa baseada em evidências de custo/benefício da prova.
4. Exercício de passkey nos dois sistemas e validação de RP ID, origem e arquivos de associação usando domínio autorizado.
5. Exercício das permissões aproximada, precisa e negada; alternativa de seleção manual.
6. Exercício de SMS por adapter simulado ou sandbox autorizada, sem credenciais reais/custos não autorizados.

## Consequências e limites

- A Fase 1 permanece em andamento. A execução JavaScript em Expo Go e uma leitura foreground foram comprovadas, mas isso não prova um development build com código nativo próprio nem dá base para decisão final Expo/React Native CLI.
- Para build nativo Android local, ainda é necessário instalar/configurar Android SDK e toolchain compatível. Para build/teste iOS, é necessário macOS com Xcode ou serviço de build cloud autorizado. Domínio/hospedagem para associação de passkeys exige decisão e autorização próprias.
- Passkeys, arquivos de associação, localização aproximada/negada, SMS simulado/sandbox e comparação prática com React Native CLI continuam pendentes.
- Esta ADR registra observações e pendências; não autoriza uso de serviço externo, compra ou registro de domínio.
