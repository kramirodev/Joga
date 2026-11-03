# Prova de associação de passkeys (Android)

Estrutura para publicar o `assetlinks.json` em uma hospedagem HTTPS estável e validar a associação entre o domínio e o app Android. É o primeiro passo para destravar a pendência de passkeys da Fase 1 **antes** de existir a infraestrutura definitiva.

**Status (2026-11-03):** publicado em `https://joga-passkeys.vercel.app`, reconhecido pela API Digital Asset Links do Google para `com.anonymous.joga` e **cerimônia de passkey executada com sucesso** no moto g(7) play (Android 10, 32 bits), com criação e autenticação via Credential Manager.

## O que esta prova cobre — e o que não cobre

**Cobre:**
- Publicar `/.well-known/assetlinks.json` na raiz de um domínio HTTPS, com `Content-Type: application/json`, HTTP 200 e sem redirecionamentos.
- Declarar o `package_name` e o SHA-256 do certificado de assinatura do app.
- Conferir que a API Digital Asset Links do Google reconhece a associação para `delegate_permission/common.get_login_creds`.
- Criar e autenticar uma passkey real no Android com o RP ID publicado, usando o Credential Manager e o Google Password Manager.

**Resultado:** o arquivo está público em `https://joga-passkeys.vercel.app/.well-known/assetlinks.json`, a API do Google retorna a declaração para `com.anonymous.joga` com a impressão esperada, e a cerimônia de criação + autenticação foi concluída no aparelho.

**Não cobre:**
- Verificação WebAuthn no backend: o desafio é gerado localmente e a resposta não é validada por servidor.
- iOS/`apple-app-site-association`.
- Biblioteca de passkeys de produção, atestação, recuperação de conta ou política de credenciais.

Concluir a hospedagem **não fecha** o critério da Fase 1 sozinha; com a cerimônia Android executada, resta a associação/build iOS.

## Valores atuais (provisórios)

| Item | Valor |
|---|---|
| Package | `com.anonymous.joga` (padrão do Expo, provisório) |
| Host publicado | `https://joga-passkeys.vercel.app` (Vercel, projeto `joga-passkeys`) |
| Certificado | Keystore de **debug** do template React Native em `mobile/android/app/debug.keystore` (chave de debug padrão, não é segredo de produção) |
| SHA-256 | `FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C` |
| Arquivo | `site/.well-known/assetlinks.json`, publicado em `https://joga-passkeys.vercel.app/.well-known/assetlinks.json` |

Se o package mudar, o build passar a usar outro keystore (release/EAS) ou a configuração de assinatura mudar, o arquivo precisa ser regerado. O script aceita mais de um `--fingerprint` (útil para múltiplas assinaturas). Confira sempre a impressão do APK que será usado na prova.

## Requisitos do arquivo

- URL exata: `https://<host>/.well-known/assetlinks.json` (raiz do domínio, não subpasta).
- HTTPS com certificado válido, resposta **200** direta (sem 301/302), `Content-Type: application/json`.
- Sem autenticação, sem HTML de interstitial, sem cache permanente.
- Relação de credenciais: `delegate_permission/common.get_login_creds`.
- **Google Password Manager (observado em 2026-11-03):** o GMS recusou o RP ID com
  `[50152] RP ID cannot be validated` mesmo com a API do Google reconhecendo a associação.
  A falha desapareceu ao incluir também `delegate_permission/common.handle_all_urls` na
  mesma declaração. O arquivo publicado usa as duas relações. Trate isso como requisito
  empírico do validador do GPM, não como substituto da relação de credenciais.

## Onde hospedar

| Opção | Veredito | Observações |
|---|---|---|
| **Vercel** (escolhido) | Publicado | `https://joga-passkeys.vercel.app` na raiz, HTTPS válido, `vercel.json` define o Content-Type. `vercel.app` está na Public Suffix List, então o subdomínio pode ser RP ID. |
| **Cloudflare Pages** | Funciona | `<projeto>.pages.dev`, `_headers` define o Content-Type. Também na PSL. Exige conta. |
| **GitHub Pages** | Apenas site de usuário | Só funciona em um repositório `<usuario>.github.io` (raiz). Site de projeto (`<usuario>.github.io/<repo>/...`) **não** atende à exigência de raiz. Precisa de `.nojekyll`. Não permite headers customizados, mas `.json` já é servido como `application/json`. |
| **ngrok** | Último recurso | Domínio gratuito muda a cada sessão (salvo domínio estático), o que invalida o RP ID depois; a página de aviso do plano gratuito pode quebrar o verificador. Só para um teste pontual e descartável. |

O host escolhido precisa permanecer o mesmo durante toda a prova: uma passkey criada com RP ID `a.vercel.app` não funciona em `b.vercel.app`.

## Publicar no Vercel

**Publicado em 2026-11-03** na conta `kramirodev`, projeto `joga-passkeys`, URL de produção `https://joga-passkeys.vercel.app`. O comando usado (sem vincular o diretório ao repositório):

```powershell
$env:PATH = "C:\prog\joga\.tools\nodejs\node-v24.22.1-win-x64;$env:PATH"
Set-Location C:\prog\joga\harness\proofs\passkeys\site
npx vercel --prod --yes --project joga-passkeys --create-if-missing
```

Para republicar depois de alterar o arquivo, use o mesmo comando. O `vercel.json` já define `Content-Type: application/json` para o arquivo.

**Importante:** mantenha a Deployment Protection (Vercel Authentication) desativada no domínio de produção. Com proteção ativa, o `assetlinks.json` deixa de ser público e a verificação falha.

## Publicar no Cloudflare Pages

```powershell
Set-Location C:\prog\joga\harness\proofs\passkeys\site
npx wrangler pages deploy .
```

O `_headers` define o Content-Type.

## Publicar no GitHub Pages (site de usuário)

1. Criar o repositório `<usuario>.github.io`.
2. Copiar o conteúdo de `site/` para a raiz do repositório (incluindo `.well-known/` e `.nojekyll`).
3. Commitar e publicar na branch configurada em Pages (root).
4. Confirmar `https://<usuario>.github.io/.well-known/assetlinks.json`.

Não usar site de projeto: a URL ficaria `.../<repo>/.well-known/...` e o Android exige a raiz.

## Gerar ou atualizar o assetlinks

Extrair a impressão do APK assinado:

```powershell
Set-Location C:\prog\joga
python -X utf8 harness\proofs\passkeys\scripts\passkeys_tool.py fingerprint `
  --apk mobile\android\app\build\outputs\apk\debug\app-debug.apk `
  --apksigner C:\prog\joga\.tools\android-sdk\build-tools\37.0.0\apksigner.bat
```

Gerar o arquivo (substitui `site/.well-known/assetlinks.json`):

```powershell
python -X utf8 harness\proofs\passkeys\scripts\passkeys_tool.py statement `
  --package com.anonymous.joga `
  --fingerprint FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C `
  --app-links-relation
```

O `--app-links-relation` adiciona `delegate_permission/common.handle_all_urls`; o arquivo
publicado usa as duas relações por causa do comportamento do Google Password Manager
descrito acima. Sem a flag, o arquivo é gerado só com `get_login_creds`.

## Validar

```powershell
python -X utf8 harness\proofs\passkeys\scripts\passkeys_tool.py verify `
  --origin https://joga-passkeys.vercel.app --package com.anonymous.joga `
  --fingerprint FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C
```

Resultado em 2026-11-03:

```text
OK: com.anonymous.joga associado a https://joga-passkeys.vercel.app
```

O arquivo respondeu HTTP 200, `Content-Type: application/json; charset=utf-8`, sem
redirecionamento. A API do Google retornou a declaração com `packageName`
`com.anonymous.joga` e o fingerprint esperado.

O comando confere status, `Content-Type`, redirecionamento, conteúdo e consulta a API:

```text
https://digitalassetlinks.googleapis.com/v1/statements:list
  ?source.web.site=https://joga-passkeys.vercel.app
  &relation=delegate_permission/common.get_login_creds
```

Também é possível conferir manualmente:

```powershell
curl.exe -i https://joga-passkeys.vercel.app/.well-known/assetlinks.json
```

A API do Google pode manter cache do resultado por algum tempo. Se o arquivo já estiver
correto e a API ainda não reconhecer, aguarde alguns minutos e repita; para validar apenas
a publicação HTTP, use `--skip-google`.

## Testes da ferramenta

```powershell
python -X utf8 -m unittest discover -s harness\proofs\passkeys\scripts -v
```

## Cerimônia de passkey (Android) — executada em 2026-11-03

| Item | Valor |
|---|---|
| Aparelho | moto g(7) play, serial `0062710182`, Android 10 (API 29), `armeabi-v7a` |
| Build | `gradlew.bat :app:assembleDebug -PreactNativeArchitectures=armeabi-v7a` (APK de debug de 33.946.574 bytes) |
| Módulo | `mobile/modules/passkey-proof` (Expo local module com `androidx.credentials:credentials:1.6.0` e `credentials-play-services-auth:1.6.0`), registrado no ADR 0011 |
| Provedor | Google Password Manager (Credential Manager do Google Play services) |
| Conta | conta Google ativa no aparelho; tela protegida por PIN |
| RP ID | `joga-passkeys.vercel.app` |

Resultado exibido pelo app:

Criação (`createPasskeyAsync`):

```text
Passkey criada e registrada pelo Google Password Manager.
clientData.type: webauthn.create
clientData.origin: android:apk-key-hash:-sYXRdwJA3hvue3mKpYrOZ9zSPC7b4mbgzJmdZEDO5w
credentialId: dKcZmRwJaD4crwZegBb6yw
```

Autenticação (`getPasskeyAsync`):

```text
Autenticação concluída: rpIdHash confere com o RP ID solicitado.
clientData.type: webauthn.get
clientData.origin: android:apk-key-hash:-sYXRdwJA3hvue3mKpYrOZ9zSPC7b4mbgzJmdZEDO5w
credentialId: dKcZmRwJaD4crwZegBb6yw
Mesma credencial criada nesta sessão: sim
rpIdHashMatches: true
userPresent: true
userVerified: true
```

Evidências visuais (dados públicos, sem PIN nem conta):
`evidence/android-create-result.png` e `evidence/android-get-result.png`.

Observações da execução:

- O GMS rejeitou o RP ID com `[50152] RP ID cannot be validated` até o
  `assetlinks.json` incluir também `delegate_permission/common.handle_all_urls`.
- Com `timeout` de 60 s na requisição, o fluxo expirou enquanto o PIN era digitado
  (`[15] Flow has timed out.`). O módulo usa 300 s.
- O `rpIdHashMatches` é calculado no aparelho comparando o SHA-256 do RP ID com os
  primeiros 32 bytes do `authenticatorData` da asserção.
- O desafio é local (`SecureRandom`) e não há verificação no servidor: a prova cobre a
  associação de domínio e a cerimônia, não a segurança de uma autenticação real.

## Próximo passo (iOS)

A associação Android e a cerimônia estão concluídas. Falta a associação
`apple-app-site-association`, a entitlement `webcredentials` e um build iOS real, que
dependem de conta Apple e macOS/Xcode (ou build cloud autorizado).

## Segurança

- A impressão SHA-256 é informação pública; o keystore e as senhas **não** devem ser publicados.
- O site contém somente o arquivo de associação; não criar interface pública.
- Nenhum segredo de backend, OTP ou credencial real entra no site.
