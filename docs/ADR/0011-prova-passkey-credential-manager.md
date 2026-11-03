# ADR 0011 — Módulo nativo local para a prova de passkey (Credential Manager)

- **Status:** Aprovado para a prova em 2026-11-03, ao autorizar a implementação mínima de Credential Manager. Não ratifica biblioteca de passkeys para produção.
- **Data:** 2026-11-03
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0009 (estratégia Expo), `harness/build/phase-01-bloqueios-passkeys-e-ios.md`, `mobile/AGENTS.md`.

## Contexto

O ADR 0009 decidiu Expo development build com `expo prebuild` e determinou reavaliar a estratégia caso surgisse um módulo nativo próprio. A Fase 1 exige provar a cerimônia de passkey com um RP ID real, e o `androidx.credentials` (Credential Manager) precisa ser chamado diretamente — não há pacote Expo pronto no escopo aprovado e não é permitido editar manualmente o `android/` gerado.

A alternativa de adicionar uma biblioteca de passkeys de terceiros foi descartada para esta prova: introduziria uma dependência de produção sem decisão registrada e misturaria a prova técnica com a escolha de biblioteca do produto. Um módulo local, versionado no repositório e autolinkado, mantém o código sob controle e não altera o projeto nativo gerado.

## Decisão

1. Criar o módulo Expo local `mobile/modules/passkey-proof`, autolinkado pelo diretório `modules/` (padrão do Expo), sem editar `android/` ou `ios/` manualmente.
2. Escopo restrito à prova: funções `createPasskeyAsync`, `getPasskeyAsync` e `getPlatformSummary`, com desafio aleatório gerado no aparelho (`SecureRandom`), RP ID fixo `joga-passkeys.vercel.app` e retorno apenas de dados públicos da cerimônia.
3. Usar `androidx.credentials:credentials:1.6.0` e `androidx.credentials:credentials-play-services-auth:1.6.0`, sem implementação iOS neste protótipo.
4. Carregar o módulo com `requireOptionalNativeModule`, para que Expo Go ou builds sem o módulo nativo não quebrem a tela de prova.
5. Não persistir chaves privadas, não registrar material secreto e não implementar verificação WebAuthn no backend nesta fase.
6. Reavaliar a biblioteca de passkeys de produção em fase própria, quando houver backend, desafios emitidos pelo servidor, verificação de assinatura, atestação e política de recuperação.

## Consequências

- O build Android passa a exigir `expo prebuild` e recompilação nativa; a cerimônia não funciona em Expo Go.
- `mobile/modules/passkey-proof` é código versionado e revisável; o `android/` continua gerado e ignorado pelo Git.
- O módulo é específico da prova e não deve ser promovido a biblioteca de produto sem revisão de segurança, testes e decisão registrada.
- A prova comprovou a associação de domínio e a cerimônia, mas não comprova verificação de credencial no servidor, nem iOS.
