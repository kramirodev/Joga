# Instruções específicas de `mobile/` para agentes

## Conexão com a governança do projeto

Leia primeiro `AGENTS.md` (raiz), `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md`, `docs/JOGA_DOCUMENTACAO_TECNICA.md`, `PLANS.md`, `harness/build-log.md` e `harness/build/phase-01-prova-tecnica-mobile-nativa.md`. O conteúdo atual de `mobile/` é o protótipo mínimo da **Fase 1 (prova técnica mobile/nativa)** — não é o aplicativo de produto.

- `mobile/app.json` tem `"name": "JOGA"` (slug `joga`); o package `com.anonymous.joga` é provisório e depende de decisão (pendência 15 da técnica).
- `android/` foi gerado por `expo prebuild`, é **git-ignorado** (`mobile/.gitignore`) e não comprova build nativo; `App.tsx` é a tela única de prova, com as seções de permissão de localização e de passkey (Android), sem navegação/funcionalidade de produto.
- A estratégia mobile foi decidida no **ADR 0009 (aprovado)**: Expo development build com `expo prebuild`, mantendo `android/` e `ios/` gerados e não versionados neste momento. EAS Build, distribuição e OTA continuam sem decisão; não presumir EAS. Não introduzir dependências, telas ou módulos fora do escopo da fase em execução.
- O módulo nativo local `mobile/modules/passkey-proof` foi criado para a prova de Credential Manager e está registrado no **ADR 0011**; é código de prova, não biblioteca de produção.

## Tooling real do projeto

O projeto usa **pnpm** (não existe `bun.lock`; não usar bunx/npm diretamente). Comandos válidos (registrados no build-log da Fase 1, a partir de `mobile/`):

```text
pnpm install --frozen-lockfile
pnpm exec tsc --noEmit
pnpm exec expo config --type public --json
pnpm exec expo install --check
pnpm exec expo start --localhost --go --clear
pnpm exec expo prebuild --platform android --no-install   # apenas no contexto aprovado da Fase 1
```

- `pnpm exec tsc --noEmit` deve passar antes de declarar qualquer tarefa concluída. O lint existe via `pnpm exec eslint .`; não instalar novas ferramentas de lint sem aprovação da fase.
- Novo módulo nativo (ex.: passkeys, push) só mediante escopo aprovado da fase, decisão registrada e build nativo correspondente; módulos locais ficam em `modules/` e são autolinkados pelo Expo.

## Expo muda entre versões — não confie em dados de treino

Expo entrega breaking changes a cada SDK. Antes de escrever código que toque APIs de Expo/EAS/React Native:

1. Leia a versão major do pacote `expo` em `package.json` (hoje `~58.0.22`).
2. Consulte a doc versionada: `https://docs.expo.dev/versions/v<major>.0.0/`
3. Para o resto, use `https://docs.expo.dev/llms.txt` e siga para a página específica; nunca responda de memória.

## Regras de escopo

- Não avançar fase; não criar telas/features de produto (perfil, matchmaking, lobbies, chat, marketplace).
- Não editar `android/`/`ios/` manualmente enquanto a estrutura for gerada por prebuild; o ADR 0009 mantém os projetos nativos gerados e não versionados e prevê reavaliar se surgir módulo nativo próprio.
- Não configurar chaves, credenciais, bundles/identificadores de loja nem provedores reais de SMS/mapas/payment sem autorização explícita.
- Coordenadas de localização não devem ser exibidas nem persistidas no protótipo (decisão vigente da prova).
- Ações externas com custo (build cloud, aceitação de licenças Android, domínio, registro em lojas) exigem autorização e registro no `harness/build-log.md`.
- Ao concluir a tarefa: registrar evidências no build-log/ficha da fase e NÃO iniciar a próxima fase automaticamente.
