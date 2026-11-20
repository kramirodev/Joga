# Build Android no Windows — caminho curto e MAX_PATH

**Data:** 19 de novembro de 2026<br>
**Escopo:** build local do app do jogador (`mobile/`) no Windows com Expo development build, React Native 0.88.1, CMake 3.22.1 e Ninja embutido.<br>
**Relaciona:** ADR 0009, `docs/RUNBOOK.md` §5, `harness/build-log.md` (histórico de 2026-11-02) e `mobile/pnpm-workspace.yaml`.

## 1. Sintoma

O build Android falha no codegen/compilação nativa do `react-native-safe-area-context`, antes de gerar o APK. Os erros observados são:

```text
ninja: error: Stat(...RNCSafeAreaViewShadowNode.cpp.o): Filename longer than 260 characters
```

ou o ciclo de reconfiguração:

```text
Re-running CMake...
manifest 'build.ninja' still dirty after 100 tries
```

O limite é o **MAX_PATH clássico do Windows (260 caracteres)**. O CMake 3.22.1 usa um Ninja embutido que não trata caminhos longos, mesmo com a política `LongPathsEnabled=1` ativa. O caminho do objeto gerado pelo codegen do safe-area ultrapassa 260 caracteres quando o repositório e o store do pnpm estão em caminhos profundos.

## 2. O que não resolve

- **`LongPathsEnabled=1`:** o Ninja embutido no CMake 3.22.1 não é `longPathAware`; a política do Windows não encurta o caminho absoluto gravado no `build.ninja`.
- **Junction:** o caminho canônico continua longo para o CMake/Ninja.
- **`subst`:** não é visível de forma consistente para todos os processos do Gradle/CMake e não reduz o caminho absoluto efetivo.
- **Apenas limpar o cache do Gradle:** o problema volta porque o caminho de origem continua acima do limite.

Manter `nodeLinker: hoisted` em `mobile/pnpm-workspace.yaml` continua necessário para evitar os caminhos longos do store virtual do pnpm, mas não basta quando a raiz do projeto já é profunda.

## 3. Solução: copiar `mobile` para uma raiz curta

Exemplo com `C:\m` (raiz de 4 caracteres):

```powershell
robocopy C:\prog\joga\mobile C:\m /E /XD node_modules /NFL /NDL /NJH /NJS /NP
Set-Location C:\m
pnpm install --frozen-lockfile
```

### 3.1 Apagar os builds antigos

O `autolinking.json` gerado pelo Expo/React Native grava **caminho absoluto**. Se o diretório `android` for copiado com os builds antigos, o Gradle reutiliza o caminho de `C:\prog\joga\mobile` e o erro volta. Apague:

```powershell
Remove-Item C:\m\android\build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item C:\m\android\app\build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item C:\m\android\.gradle -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item C:\m\android\app\.cxx -Recurse -Force -ErrorAction SilentlyContinue
```

Se o projeto nativo não existir ou estiver inconsistente, regenere antes do build:

```powershell
Set-Location C:\m
pnpm exec expo prebuild --platform android --no-install
```

> **Atenção:** `prebuild` (principalmente `--clean`) recria `android/` e pode gerar
> um novo `debug.keystore`. O release do demo é assinado com essa chave, e a
> troca muda o SHA-256 do certificado, quebra o `assetlinks.json` publicado e
> impede a atualização por cima de um APK já instalado. Antes de qualquer
> `prebuild --clean`, faça backup e restaure o keystore (§7.1).

### 3.2 Configurar `EXPO_PUBLIC_API_URL`

Defina a URL da API antes de iniciar o Metro ou gerar o bundle. Para aparelho conectado por USB com `adb reverse`:

```powershell
Set-Location C:\m
$env:EXPO_PUBLIC_API_URL = 'http://127.0.0.1:8000/api/v1'
```

Para acessar a API pela rede local, use o IP da máquina:

```powershell
$env:EXPO_PUBLIC_API_URL = 'http://192.168.0.105:8000/api/v1'
```

Também é possível gravar a variável em `C:\m\.env` (não versionar segredos). O valor é embutido pelo Metro no bundle; definir depois de iniciar o Metro não altera o bundle já carregado.

### 3.3 Compilar `arm64-v8a`

```powershell
Set-Location C:\m\android
$env:JAVA_HOME = 'C:\prog\joga\.tools\temurin-17\jdk-17.0.20.1+1'
$env:ANDROID_HOME = 'C:\prog\joga\.tools\android-sdk'
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:PATH = "C:\m\node_modules\.bin;$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:PATH"
"sdk.dir=C\:\\prog\\joga\\.tools\\android-sdk" | Set-Content local.properties -Encoding ASCII
.\gradlew.bat assembleDebug -PreactNativeArchitectures=arm64-v8a --console=plain
```

Para instalar e conectar o app:

```powershell
adb install -r C:\m\android\app\build\outputs\apk\debug\app-debug.apk
adb reverse tcp:8081 tcp:8081
adb reverse tcp:8000 tcp:8000
Set-Location C:\m
pnpm exec expo start --dev-client --localhost --port 8081
```

Confira a ABI do aparelho com `adb shell getprop ro.product.cpu.abilist`. Para aparelho 32 bits, troque `arm64-v8a` por `armeabi-v7a`. O APK de debug depende do Metro em `localhost:8081`.

## 4. Verificação

1. Confirme que o caminho mais longo gerado no build ficou abaixo de 260 caracteres:

   ```powershell
   Get-ChildItem C:\m\android\build -Recurse -File -ErrorAction SilentlyContinue |
     ForEach-Object { $_.FullName.Length } |
     Measure-Object -Maximum
   ```

2. Confirme que o `autolinking.json` não aponta para o caminho antigo:

   ```powershell
   Get-ChildItem C:\m\android -Recurse -Filter autolinking.json -ErrorAction SilentlyContinue |
     Select-String -Pattern 'C:\\prog\\joga'
   ```

   O comando não deve retornar ocorrências.

3. O build deve terminar com `BUILD SUCCESSFUL` e gerar `app\build\outputs\apk\debug\app-debug.apk`.

## 5. Alternativa: EAS Build ou Linux

Se o build local no Windows continuar bloqueado:

- **EAS Build:** build em Linux gerenciado, sem MAX_PATH. É ação externa com custo e exige autorização explícita e registro no `harness/build-log.md`; não presumir EAS por conta própria (ADR 0009).
- **Linux local ou WSL:** executar `pnpm install --frozen-lockfile`, `expo prebuild` e `gradlew assembleDebug -PreactNativeArchitectures=arm64-v8a` em um sistema sem o limite de 260 caracteres.

## 6. Limitações

- O procedimento foi descoberto no ambiente Windows deste projeto; versões diferentes de CMake/Ninja podem tratar caminhos longos de outra forma.
- A cópia para `C:\m` é uma cópia de trabalho. Não versionar `C:\m`, `android/build`, `android/app/build`, `android/.gradle` nem `android/app/.cxx`.
- `EXPO_PUBLIC_API_URL` é configuração de build, não segredo. Nunca colocar chaves, tokens ou credenciais em `.env` versionado.

## 7. Release do demo: assinatura, guarda de URL e MAX_PATH

### 7.1 Assinatura do demo (chave de debug)

O release do demo **não tem keystore de produção**. `mobile/android/app/build.gradle`
usa `signingConfigs.debug` também no `release`:

| Item | Valor |
|---|---|
| Keystore | `mobile/android/app/debug.keystore` (dentro de `android/`, git-ignorado) |
| Alias | `androiddebugkey` |
| Senha do keystore e da chave | `android` (padrão do template React Native) |
| SHA-256 do certificado | `FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C` |
| Uso | **Somente demo.** Não serve para Play Store, produção, KYC ou distribuição pública. |

O keystore **não é versionado** (fica em `android/`, recriado por `prebuild`). O
backup operacional deste host está **fora do repositório**, em:

```text
$env:USERPROFILE\.joga\keystores\joga-demo-debug.keystore
```

SHA-256 do arquivo do backup: `221E0A3106AA4C3CCC154E0A418B55020B3F9EA6E84F92E8749CD9E2F39F5E58`.
Guarde o backup em local durável e privado; ele é a única forma de manter a mesma
assinatura. Sem ele, `prebuild --clean` gera outra chave, o fingerprint muda e
quebra duas coisas: o `assetlinks.json` do demo e a atualização por cima do APK
já instalado.

Se o fingerprint mudar, atualize `web/public/.well-known/assetlinks.json`
(mesmo `package_name` e novo SHA-256) e publique no host do demo. A publicação é
ação externa separada, sujeita a autorização; gerar o arquivo não é deploy.
Ferramenta: `harness/proofs/passkeys/scripts/passkeys_tool.py`.

### 7.2 Guarda de `EXPO_PUBLIC_API_URL`

`mobile/app.config.js` (versionado) falha o bundle quando a variável está vazia,
aponta para `127.0.0.1`/`localhost` ou não é HTTPS, sempre que o build é de
release. O build de release precisa declarar explicitamente:

```powershell
$env:JOGA_RELEASE_BUILD = '1'
$env:EXPO_PUBLIC_API_URL = 'https://<host-do-demo>/api/v1'
```

Sem a variável ou com valor local, `gradlew ... assembleRelease/bundleRelease`
para antes de empacotar. Em desenvolvimento (`expo start`), `127.0.0.1` continua
válido.

Prova de que o bundle embutido usa o demo:

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead('C:\m\android\app\build\outputs\apk\release\app-release.apk')
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'assets/index.android.bundle' }
$reader = New-Object IO.StreamReader($entry.Open())
$text = $reader.ReadToEnd()
$reader.Close(); $zip.Dispose()

if (-not $env:EXPO_PUBLIC_API_URL) { throw 'EXPO_PUBLIC_API_URL nao definido' }
$expected = ([uri]$env:EXPO_PUBLIC_API_URL).Host
if ($expected -in @('127.0.0.1', 'localhost')) {
  throw 'EXPO_PUBLIC_API_URL aponta para local, nao para o demo'
}
if (-not $expected -or $text -notmatch [regex]::Escape($expected)) {
  throw 'Bundle sem o host do demo'
}
```

> O fallback `http://127.0.0.1:8000/api/v1` continua no bundle como valor de
> desenvolvimento em `mobile/src/api/client.ts`. A prova do release é a presença
> do host do demo **e** o fato de o build ter passado pela guarda do
> `app.config.js` com `JOGA_RELEASE_BUILD=1`; ausência de URL local no texto do
> bundle não é um critério válido.

### 7.3 Ajuste de MAX_PATH reproduzível

O `android/` é regenerado por `prebuild`; qualquer ajuste manual nele precisa ser
reaplicado de forma explícita. O caminho curto `C:\m` resolve o MAX_PATH sem
mudar a arquitetura (Expo/RN/CMake continuam os mesmos), mas o argumento de
CMake não é versionado.

**Não use `CMAKE_OBJECT_PATH_MAX=200`.** Medido no build de 2026-11-20 em
`C:\m`, o maior caminho de objeto gerado é **248 caracteres**. Com 200, o CMake
tenta encurtar o caminho para `C_/m/...`, avisa que não cabe e o Ninja falha com
`mkdir(...): No such file or directory`. Com 250 (o padrão do CMake 3.22.1),
nenhum caminho excede o limite e o build passa. Portanto: raiz curta **e** 250
(ou simplesmente remover a linha). O valor 200 existente em `android/app/build.gradle`
deve ser corrigido para 250 antes do build.

Receita usada no build de 2026-11-20:

```powershell
robocopy C:\prog\joga\mobile C:\m /E /XD node_modules build .gradle .cxx dist .expo .kotlin /NFL /NDL /NJH /NJS /NP
Set-Location C:\m
pnpm install --frozen-lockfile
# O build.gradle gerado precisa do limite de caminho de objeto:
#   arguments "-DCMAKE_OBJECT_PATH_MAX=250"
# Se o prebuild recriar o arquivo, reaplique a linha acima e restaure o keystore.
Set-Location C:\m\android
$env:JAVA_HOME = 'C:\prog\joga\.tools\jdk-17.0.21+9'
$env:ANDROID_HOME = 'C:\prog\joga\.tools\android-sdk'
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:JOGA_RELEASE_BUILD = '1'
$env:EXPO_PUBLIC_API_URL = 'https://<host-do-demo>/api/v1'
.\gradlew.bat assembleRelease bundleRelease '-PreactNativeArchitectures=arm64-v8a,armeabi-v7a' --console=plain --no-daemon
```

Não copie `android/build`, `android/app/build`, `android/.gradle` nem
`android/app/.cxx` para `C:\m`: o `autolinking.json` grava caminho absoluto e
reintroduz `C:\prog\joga`. Confira com:

```powershell
Get-ChildItem C:\m\android -Recurse -Filter autolinking.json |
  Select-String -Pattern 'C:\\prog\\joga'
```

O comando não deve retornar ocorrências.
