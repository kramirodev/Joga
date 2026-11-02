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
- **Validação:** `git diff --check` executado ao final desta alteração documental; nenhum segredo adicionado; nenhuma implementação de produto iniciada; status das fases inalterado (Fase 0 `Complete`; Fase 1 `In progress`).
