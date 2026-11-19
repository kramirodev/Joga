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
