# Fase 01 — Bloqueios de passkeys/domínio e iOS

**Status:** associação Android publicada em `https://joga-passkeys.vercel.app`, reconhecida pela API Digital Asset Links do Google e **cerimônia de passkey executada** no Android 10 de 32 bits via Credential Manager; associação/build iOS ainda pendentes.
**Data:** 2026-11-02 (atualizado em 2026-11-03)
**Relacionado:** `PLANS.md` (Fase 1), `docs/JOGA_DOCUMENTACAO_TECNICA.md` §5.3–5.4 e §26, `docs/ADR/0009-estrategia-react-native-expo-vs-cli.md`, `docs/ADR/0011-prova-passkey-credential-manager.md`.

## 1. Por que estes itens não foram provados por completo

A Fase 1 exige exercitar o registro/autenticação com passkey e validar os arquivos de
associação de domínio, além de abrir o protótipo em Android e iOS. Em 2026-11-03 a
associação **e a cerimônia** Android foram executadas; o que resta depende das condições abaixo:

| Item | O que falta | Situação em 2026-11-03 |
|---|---|---|
| Passkeys | Domínio HTTPS e autorização para publicar os arquivos de associação | **Resolvido para Android** na Vercel (`joga-passkeys.vercel.app`); iOS pendente |
| Passkeys no Android | `assetlinks.json` publicado, impressão SHA-256 e cerimônia no app | **Concluído**: associação reconhecida pelo Google e criação + autenticação via Credential Manager executadas |
| Passkeys no iOS | Domínio, `apple-app-site-association`, Apple Developer Team ID, bundle ID e provisioning | Pendente; depende de conta Apple (custo) |
| Build iOS | macOS com Xcode **ou** build cloud autorizado | Pendente; ambiente indisponível |

Registrar o bloqueio é o comportamento exigido por `PLANS.md`: não declarar suporte
multiplataforma completo quando uma plataforma não foi exercitada. A associação e a
cerimônia Android foram resolvidas em 2026-11-03; o registro continua válido para o iOS.

## 2. Requisitos de passkeys e associação de domínio

Passkeys usam WebAuthn. O **RP ID** é o domínio (sem esquema e sem porta) e a **origem**
inclui o esquema HTTPS. Por isso, a associação entre app e domínio precisa ser publicada
no próprio domínio, em HTTPS válido, sem redirecionamentos.

### 2.1 Android — Digital Asset Links

Arquivo: `https://<domínio>/.well-known/assetlinks.json`

Conteúdo mínimo esperado para **passkeys** (ilustrativo; os valores reais dependem do
domínio, do package e do certificado):

```json
[
  {
    "relation": ["delegate_permission/common.get_login_creds"],
    "target": {
      "namespace": "android_app",
      "package_name": "com.anonymous.joga",
      "sha256_cert_fingerprints": ["<SHA-256 do certificado de assinatura>"]
    }
  }
]
```

`delegate_permission/common.handle_all_urls` atende a App Links, não a credenciais. Para
passkeys a relação obrigatória é `delegate_permission/common.get_login_creds`.

**Observação empírica (2026-11-03):** o Google Password Manager recusou o RP ID com
`[50152] RP ID cannot be validated` mesmo com a API do Google confirmando a associação; a
falha só desapareceu quando o arquivo passou a declarar **as duas relações**
(`get_login_creds` e `handle_all_urls`). O arquivo publicado segue esse formato. Isso não
transforma `handle_all_urls` em requisito de credenciais: é uma exigência observada do
validador do GPM nesta versão do Google Play services.

Requisitos adicionais:

- `Content-Type: application/json`, resposta `200` e sem redirecionamento.
- A impressão digital deve corresponder ao certificado usado no build (debug e release
  têm certificados diferentes).
- Para passkeys, o vínculo é verificado pela API Digital Asset Links durante a cerimônia;
  `autoVerify`/intent filters são requisitos de App Links, não de credenciais.
- O `package_name` atual (`com.anonymous.joga`) é provisório; mudar o identificador
  invalida qualquer associação já publicada.

### 2.2 iOS — Associated Domains

Arquivo: `https://<domínio>/.well-known/apple-app-site-association`

Conteúdo mínimo esperado:

```json
{
  "webcredentials": {
    "apps": ["<TeamID>.<BundleID>"]
  }
}
```

Requisitos adicionais:

- Entitlement `com.apple.developer.associated-domains` com `webcredentials:<domínio>`.
- `Team ID` de uma conta Apple Developer e `Bundle ID` estável. `mobile/app.json` ainda
  não declara `ios.bundleIdentifier`; o prebuild usaria um valor padrão provisório.
- Arquivo servido em HTTPS, `Content-Type: application/json`, sem redirecionamento.
- Instalação em aparelho físico exige assinatura/provisioning; simulador exige macOS.

### 2.3 O que pode ser validado sem domínio

- Formato dos JSONs e presença dos campos obrigatórios, por inspeção local.
- Coerência entre `package_name`/`bundleIdentifier` e os valores que seriam publicados.
- Geração e teste da ferramenta de associação, incluindo um servidor HTTP local que simula
  a publicação (status, `Content-Type` e conteúdo).

Nada disso substitui a validação real: é preciso publicar o arquivo em um domínio e executar
a cerimônia WebAuthn; só a inspeção local não confirma a associação.

### 2.4 Estrutura da prova e publicação (2026-11-03)

`harness/proofs/passkeys/` contém a estrutura usada para publicar e validar a associação Android:

| Item | Conteúdo |
|---|---|
| `scripts/passkeys_tool.py` | `fingerprint` lê o SHA-256 de um APK; `statement` gera o `assetlinks.json` (com opção `--app-links-relation`); `verify` confere status, `Content-Type`, redirecionamento e a API Digital Asset Links do Google |
| `scripts/test_passkeys_tool.py` | 8 testes com `unittest` e servidor HTTP local, sem rede externa |
| `site/.well-known/assetlinks.json` | Declaração publicada para `com.anonymous.joga` e o certificado de debug |
| `site/vercel.json` | Cabeçalho `Content-Type: application/json` para Vercel |
| `site/_headers` | Equivalente para Cloudflare Pages |
| `site/.nojekyll` | Necessário para GitHub Pages servir `.well-known` |
| `evidence/android-create-result.png` | Tela do app após criar a passkey (dados públicos) |
| `evidence/android-get-result.png` | Tela do app após autenticar (rpIdHashMatches, userVerified) |
| `README.md` | Requisitos, opções de hospedagem, comandos, cerimônia e limites |

Valores provisórios atuais:

- Package: `com.anonymous.joga` (padrão do Expo).
- Certificado: keystore de **debug** em `mobile/android/app/debug.keystore` (ignorado pelo
  Git). O SHA-256 é `FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C`.
- Consequência: é a chave de debug padrão do template, não um segredo de produção. A
  impressão muda se o build usar outro keystore (release/EAS) ou outra configuração de
  assinatura; confirme com o comando `fingerprint` antes de publicar.

**Publicação (2026-11-03):** host `https://joga-passkeys.vercel.app` (Vercel, projeto
`joga-passkeys`, conta `kramirodev`). O arquivo responde HTTP 200,
`Content-Type: application/json; charset=utf-8`, sem redirecionamento. A API Digital Asset
Links retornou a declaração com `packageName` `com.anonymous.joga` e o fingerprint
esperado. O comando de verificação retornou:

```text
OK: com.anonymous.joga associado a https://joga-passkeys.vercel.app
```

O que a publicação resolve e o que ainda falta:

- **Resolvido:** a associação Android está publicada e reconhecida pelo Google.
- **Resolvido:** a cerimônia de criação e autenticação com Credential Manager foi executada
  no Android.
- **Ainda falta:** a associação iOS/`apple-app-site-association` e o build iOS.

### 2.5 Cerimônia de passkey no Android (2026-11-03)

O módulo Expo local `mobile/modules/passkey-proof` (registrado no ADR 0011) chama
`androidx.credentials` 1.6.0 no app `com.anonymous.joga`, com RP ID
`joga-passkeys.vercel.app`. O app foi recompilado para `armeabi-v7a`, instalado e executado
no moto g(7) play (Android 10, API 29), com Google Password Manager e tela protegida por PIN.

| Etapa | Resultado observado |
|---|---|
| Criação | `webauthn.create`; origem `android:apk-key-hash:-sYXRdwJA3hvue3mKpYrOZ9zSPC7b4mbgzJmdZEDO5w`; `credentialId` `dKcZmRwJaD4crwZegBb6yw` |
| Autenticação | `webauthn.get`; mesma credencial; `rpIdHashMatches: true`; `userPresent: true`; `userVerified: true` |

O `rpIdHashMatches` é calculado no aparelho (SHA-256 do RP ID contra os primeiros 32 bytes
do `authenticatorData`). A origem `android:apk-key-hash:...` confirma que a cerimônia foi
emitida para o app assinado com o certificado do `assetlinks.json`.

Limites: o desafio é local (`SecureRandom`) e não há backend de verificação WebAuthn; a
prova cobre a associação de domínio e a cerimônia, não uma autenticação de produção. O
`timeout` do fluxo foi elevado para 300 s porque, com 60 s, o GPM encerrou a cerimônia
(`[15] Flow has timed out.`) durante a digitação do PIN.

## 3. Bloqueio de iOS

O ambiente é Windows 11. Não há macOS, Xcode, CocoaPods nem conta Apple Developer
autorizada. Consequências:

- `expo run:ios` não pode ser executado.
- Não há como gerar IPA, instalar em aparelho iPhone ou exercitar passkeys no iOS.
- Build cloud (por exemplo, EAS Build) não foi autorizado; envolve conta, custo e
  upload de código para terceiros, o que exige decisão explícita e registro no
  `harness/build-log.md`.

O bloqueio é **de ambiente**, não conclusão de incompatibilidade do Expo ou do React
Native com iOS. Nenhuma afirmação de suporte iOS comprovado deve ser feita até existir
execução real.

## 4. Checklist para desbloquear

1. Decidir e autorizar o domínio técnico (apenas `.well-known`, sem site público para
   jogadores, conforme `AGENTS.md`). — **Feito para Android**: Vercel `joga-passkeys.vercel.app`.
2. Definir identificadores definitivos: `android.package` e `ios.bundleIdentifier`. — Pendente.
3. Definir a conta Apple Developer e quem assina os builds iOS. — Pendente.
4. Autorizar hospedagem dos arquivos de associação e registrar a ação no build log. — **Feito para Android**.
5. Escolher a biblioteca de passkeys com ADR própria, após necessidade concreta. — Para a
   prova, o módulo local foi registrado no ADR 0011; a biblioteca de produção continua em aberto.
6. Publicar `assetlinks.json` e `apple-app-site-association` e validar com builds reais. —
   **Android concluído, incluindo a cerimônia**; iOS pendente.
7. Registrar os resultados em ADR, incluindo o que falhou e em qual sistema. — **Feito para Android**.

O item 6 está concluído para Android: `assetlinks.json` publicado, reconhecido pelo Google e
cerimônia de criação + autenticação executada. Para iOS, `apple-app-site-association` e a
validação com build real continuam pendentes.

## 5. O que não foi feito

- Nenhum domínio próprio foi registrado, comprado ou configurado; a prova usa o subdomínio
  gratuito `joga-passkeys.vercel.app`.
- O `apple-app-site-association` não foi publicado.
- Nenhuma conta Apple, keystore de release ou credencial foi criada.
- Nenhuma biblioteca de passkeys de terceiros foi adotada; existe apenas o módulo local de
  prova `mobile/modules/passkey-proof` com `androidx.credentials`.
- Nenhum build iOS foi tentado.
- Nenhuma cerimônia WebAuthn foi executada no iOS.
