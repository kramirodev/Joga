# ADR 0009 — Estratégia React Native: Expo development build × React Native CLI

- **Status:** Aprovado pelo responsável do produto em 2026-11-02. A aprovação cobre a estratégia de framework; não ratifica bibliotecas de passkeys, provedor de SMS, EAS Build, distribuição ou OTA.
- **Data:** 2026-11-02
- **Decisores:** responsável pelo produto e equipe técnica.
- **Atualiza:** ADR 0006 (resultados preliminares), que permanece como registro histórico.

## Contexto

A Fase 1 do `PLANS.md` exige comparar Expo development build com React Native CLI usando evidências de execução, registrar versões e limitações e documentar a decisão. O ambiente disponível é Windows 11, Node 24.22.1, pnpm 11.25.0, JDK 17.0.20.1, Android SDK (compileSdk 37, Build Tools 37.0.0), NDK 27.1.12297006, CMake 3.22.1 e um Moto G24 com Android 14. Não há macOS/Xcode.

## Evidências observadas

| Aspecto | Expo development build | React Native CLI |
|---|---|---|
| Versões | Expo `~58.0.22`, React Native `0.88.1`, React `19.3.0`, TypeScript `~6.0.3`, `expo-location ~58.0.20` | React Native `0.88.1`, React `19.3.0`, `@react-native-community/cli` `20.2.0`, template com `react-native-safe-area-context` |
| Projeto nativo | Gerado por `expo prebuild` a partir de `app.json`; não versionado | Versionado no repositório desde o template |
| Build Android | Sucesso em 4m41s (176 tasks) após correção do pnpm | Sucesso em 2m59s no caminho curto; falhou antes em caminho profundo |
| Falha no Windows | Ninja repetiu `Re-running CMake...` 100 vezes (`build.ninja still dirty`), com caminhos de objeto de 283 caracteres | `ninja: error: ... Filename longer than 260 characters` em `RNCSafeAreaViewShadowNode.cpp.o` |
| APK de debug | 47,6 MB, apenas `arm64-v8a` (ABI do aparelho conectado), 35,2 MB em bibliotecas nativas | 125,3 MB com 4 ABIs, 31,5 MB em bibliotecas `arm64-v8a` |
| Execução no Moto G24 | App JOGA abre; tela de prova funcional | Template "Welcome to React Native" abre; `React Native 0.88.1`, Hermes |
| Permissões de localização | `app.json` gerou `ACCESS_COARSE_LOCATION` e `ACCESS_FINE_LOCATION` no manifesto; três cenários exercitados no app | Manifesto do template contém apenas `INTERNET`; exigiria edição manual ou biblioteca de permissões |
| Autolinking de módulos | Automático via Expo autolinking | Automático via React Native autolinking, sem camada de configuração declarativa |
| Configuração nativa | Centralizada em `app.json` e config plugins; projeto nativo descartável | Edição direta de Gradle/Manifest, com mais superfície para divergência entre ambientes |

Observações de método:

- As duas pilhas usaram o mesmo JDK, SDK, NDK, Gradle 9.4.1 e o mesmo cache Gradle; ambas rodaram com New Architecture e Hermes habilitados.
- A medição do Expo foi feita com cache aquecido (segundo build da mesma árvore); a do CLI partiu de projeto novo, ainda que com cache Gradle reaproveitado. Os tempos não devem ser lidos como benchmark definitivo.
- Os tamanhos de APK não são diretamente comparáveis: o Expo gerou apenas a ABI do dispositivo e inclui módulos Expo; o CLI gerou APK universal com quatro ABIs.
- O limite de caminho do Windows afetou as duas pilhas. Não é defeito de uma delas; a correção aplicada (`nodeLinker: hoisted`) é específica do layout do pnpm, e o projeto CLI só buildou em raiz curta.

## Decisão

1. Adotar **Expo development build com `expo prebuild`** (geração contínua do projeto nativo), mantendo `android/` e `ios/` gerados e não versionados neste momento.
2. Manter o pnpm com `nodeLinker: hoisted`, exigido para builds Android confiáveis no Windows.
3. Expressar configuração nativa em `app.json` e config plugins; qualquer módulo nativo fora do ecossistema Expo deve virar decisão registrada antes de ser adicionado.
4. Reavaliar a geração contínua se surgir módulo nativo próprio que exija manutenção manual do projeto Android/iOS.

**Justificativa:** as duas pilhas entregaram o mesmo runtime (React Native 0.88.1, Hermes, New Architecture) e as mesmas limitações de plataforma. O Expo development build reduziu trabalho manual de configuração nativa, gerou as permissões de localização a partir de `app.json` e produziu APK restrito à ABI do dispositivo. O React Native CLI não apresentou vantagem prática nas provas executadas e exigiu configuração manual para um requisito já previsto (localização).

## Consequências

- A Fase 1 passa a tratar o Expo development build como estratégia escolhida; a ADR 0006 fica marcada como substituída.
- A decisão não cobre EAS Build, distribuição ou OTA; esses pontos continuam pendentes de ADR próprio.
- Passkeys, arquivos de associação de domínio e build iOS continuam pendentes. A escolha não declara suporte multiplataforma completo.

## Limitações e bloqueios registrados

- **iOS:** sem macOS/Xcode ou build cloud autorizado, não há evidência de execução. O bloqueio é de ambiente, não conclusão de incompatibilidade.
- **Passkeys:** dependem de domínio HTTPS controlado pelo projeto e dos arquivos de associação das plataformas; não há domínio decidido nem autorização para registrar/hospedar.
- **SMS:** nenhum provedor real foi integrado; o contrato foi provado com adaptador simulado em `harness/proofs/sms-otp/` (12 testes).
- Requisitos e pendências de passkeys/domínio e iOS detalhados em `harness/build/phase-01-bloqueios-passkeys-e-ios.md`.
- Nenhuma credencial real, custo ou serviço externo foi utilizado nesta comparação.
