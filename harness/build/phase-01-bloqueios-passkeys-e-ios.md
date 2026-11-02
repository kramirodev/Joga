# Fase 01 — Bloqueios de passkeys/domínio e iOS

**Status:** bloqueios externos registrados; nenhum dos dois caminhos foi executado.
**Data:** 2026-11-02
**Relacionado:** `PLANS.md` (Fase 1), `docs/JOGA_DOCUMENTACAO_TECNICA.md` §5.3–5.4 e §26, `docs/ADR/0009-estrategia-react-native-expo-vs-cli.md`.

## 1. Por que estes itens não foram provados

A Fase 1 exige exercitar o registro/autenticação com passkey e validar os arquivos de
associação de domínio, além de abrir o protótipo em Android e iOS. Nenhum dos dois pode
ser executado no ambiente atual sem decisões e autorizações que ainda não existem:

| Item | O que falta | Natureza do bloqueio |
|---|---|---|
| Passkeys | Domínio HTTPS definido e autorização para publicar os arquivos de associação | Decisão de produto + ação externa |
| Passkeys no Android | Domínio, `assetlinks.json` publicado e impressão SHA-256 do certificado de assinatura | Depende do domínio e do keystore |
| Passkeys no iOS | Domínio, `apple-app-site-association`, Apple Developer Team ID, bundle ID e provisioning | Depende de conta Apple (custo) |
| Build iOS | macOS com Xcode **ou** build cloud autorizado | Ambiente indisponível |

Registrar o bloqueio é o comportamento exigido por `PLANS.md`: não declarar suporte
multiplataforma completo quando uma plataforma não foi exercitada.

## 2. Requisitos de passkeys e associação de domínio

Passkeys usam WebAuthn. O **RP ID** é o domínio (sem esquema e sem porta) e a **origem**
inclui o esquema HTTPS. Por isso, a associação entre app e domínio precisa ser publicada
no próprio domínio, em HTTPS válido, sem redirecionamentos.

### 2.1 Android — Digital Asset Links

Arquivo: `https://<domínio>/.well-known/assetlinks.json`

Conteúdo mínimo esperado (ilustrativo; os valores reais dependem do domínio, do package e
do certificado):

```json
[
  {
    "relation": ["delegate_permission/common.handle_all_urls"],
    "target": {
      "namespace": "android_app",
      "package_name": "com.anonymous.joga",
      "sha256_cert_fingerprints": ["<SHA-256 do certificado de assinatura>"]
    }
  }
]
```

Requisitos adicionais:

- `Content-Type: application/json`, resposta `200` e sem redirecionamento.
- A impressão digital deve corresponder ao certificado usado no build (debug e release
  têm certificados diferentes).
- O app precisa declarar o domínio em intent filter verificado (`autoVerify`) para o
  vínculo de App Links; no projeto Expo isso seria configurado em `app.json`/config
  plugin, e não editando `android/` gerado.
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
- Nada disso substitui a validação real: sem domínio publicado, não há como confirmar que
  Android/iOS aceitam a associação, e a cerimônia WebAuthn não pode ser concluída.

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
   jogadores, conforme `AGENTS.md`).
2. Definir identificadores definitivos: `android.package` e `ios.bundleIdentifier`.
3. Definir a conta Apple Developer e quem assina os builds iOS.
4. Autorizar hospedagem dos arquivos de associação e registrar a ação no build log.
5. Escolher a biblioteca de passkeys com ADR própria, após necessidade concreta.
6. Publicar `assetlinks.json` e `apple-app-site-association` e validar com builds reais.
7. Registrar os resultados em ADR, incluindo o que falhou e em qual sistema.

## 5. O que não foi feito

- Nenhum domínio foi registrado, comprado ou configurado.
- Nenhum arquivo `.well-known` foi publicado.
- Nenhuma conta Apple, keystore de release ou credencial foi criada.
- Nenhuma biblioteca de passkeys foi adicionada ao projeto.
- Nenhum build iOS foi tentado.
