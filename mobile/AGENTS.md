# Instruções específicas de `mobile/` para agentes

## Conexão com a governança do projeto

Leia primeiro `AGENTS.md` (raiz), `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md`, `docs/JOGA_DOCUMENTACAO_TECNICA.md`, `PLANS.md`, `harness/build-log.md` e `harness/build/phase-01-prova-tecnica-mobile-nativa.md`. O conteúdo atual de `mobile/` cobre a prova da **Fase 1** e a reconstrução da UI de produto a partir de `telas/jogo/prototipo-v3.html`, com 134 definições de tela: 113 registradas na navegação e 21 sem caminho real marcadas como `hidden`, navegação por abas/pilha, tema claro/escuro e integração com os endpoints disponíveis. Telas sem endpoint correspondente permanecem visuais. A ADR 0049 e a 14E definem crédito em reais, ticket como unidade de consumo/exibição e preço em duas linhas; o app mobile consome `venue_price_cents`/`fee_cents`/`space_charge_cents`/`fee_charge_cents`, exibe tickets em vez de saldo em reais e trata `503 balance_unavailable` como indisponibilidade. Pagamentos reais, escrow, KYC e NFS-e operacional continuam fora do escopo até a fase correspondente.

- `mobile/app.json` tem `"name": "JOGA"` (slug `joga`); o package `com.anonymous.joga` é provisório e depende de decisão (pendência 15 da técnica).
- `android/` foi gerado por `expo prebuild`, é **git-ignorado** (`mobile/.gitignore`) e não comprova build nativo. `App.tsx` monta o app real da nova UI (`src/screens/`), com componentes em `src/ui/`, cliente HTTP em `src/api/`, estado global em `src/state/` e sessão em `src/session.ts`. Os antigos painéis técnicos (`IdentityPanel`, `ProfilePanel`, `CompetitivePanel`, `CommunicationPanel`) e a UI de demonstração em `src/joga/` foram removidos por decisão do produto.
- O tema claro/escuro segue o sistema via `Appearance` e a barra de navegação Android acompanha o esquema forçado pela aplicação; não há dependência adicional para isso.

- A estratégia mobile foi decidida no **ADR 0009 (aprovado)**: Expo development build com `expo prebuild`, mantendo `android/` e `ios/` gerados e não versionados neste momento. EAS Build, distribuição e OTA continuam sem decisão; não presumir EAS. Não introduzir dependências, telas ou módulos fora do escopo da fase em execução.
- O módulo nativo local `mobile/modules/passkey-proof` foi criado para a prova de Credential Manager e está registrado no **ADR 0011**; na Fase 3 passou a aceitar as opções WebAuthn emitidas pelo backend. É código de prova, não biblioteca de produção.
- O fluxo de identidade usa `expo-secure-store` para os tokens e `http://127.0.0.1:8000/api/v1`; no aparelho, as portas 8081 e 8000 precisam de `adb reverse`. `JOGA_DEV_FIXED_OTP` é apenas local e nunca deve ser usado em ambiente compartilhado.

## Tooling real do projeto

O projeto usa **pnpm** (não existe `bun.lock`; não usar bunx/npm diretamente). Comandos válidos (registrados no build-log da Fase 1, a partir de `mobile/`):

```text
pnpm install --frozen-lockfile
pnpm exec tsc --noEmit
pnpm exec eslint .
pnpm exec prettier --check .
pnpm exec expo export --platform android
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

- Não avançar para outras fases. A UI atual reproduz o guia `telas/jogo/prototipo-v3.html`; não criar telas ou funcionalidades fora desse guia sem autorização. Integrações de backend devem usar somente endpoints existentes; o que não tiver endpoint permanece visual.
- Não editar `android/`/`ios/` manualmente enquanto a estrutura for gerada por prebuild; o ADR 0009 mantém os projetos nativos gerados e não versionados e prevê reavaliar se surgir módulo nativo próprio.
- Não configurar chaves, credenciais, bundles/identificadores de loja nem provedores reais de SMS/mapas/payment sem autorização explícita.
- Coordenadas de localização não devem ser exibidas nem persistidas no protótipo (decisão vigente da prova).
- Ações externas com custo (build cloud, aceitação de licenças Android, domínio, registro em lojas) exigem autorização e registro no `harness/build-log.md`.
- Ao concluir a tarefa: registrar evidências no build-log/ficha da fase e NÃO iniciar a próxima fase automaticamente.
