# Identidade visual e assets — JOGA

Este documento registra os tokens, o inventário de assets e as regras de uso da
marca no aplicativo mobile e no painel web. A fonte de arte é o wordmark
`mobile/assets/brand/JOGA-wordmark.png`; o arquivo `JOGA.png` não fica na raiz do
repositório.

## 1. Tokens

| Token | Valor | Uso |
|---|---|---|
| Fundo | `#0F1214` | splash, loader, ícone sólido, favicon, `backgroundColor` do app e `theme-color` do painel |
| Brilho do loader | `#2A1214` | segunda camada do gradiente do loader |
| Texto do logo | `#F4F2EE` | letras do wordmark e do símbolo "J." |
| Ponto | `#F03B3B` | ponto do wordmark e do símbolo "J." |

O gradiente do loader vai de `#0F1214` a `#2A1214` em um ciclo lento de 10 s
(metade para cada sentido), por cross-fade de opacidade. Com redução de
movimento ativa, o fundo fica estático.

## 2. Wordmark

- Arquivo: `mobile/assets/brand/JOGA-wordmark.png` (687 × 183 px, RGBA). O
  binário recebido como `JOGA.png` media 687 × 183 px, não 866 × 224 px; as
  proporções originais foram preservadas.
- Cópia web: `web/public/brand/JOGA-wordmark.png`.
- Composição: "JOGA." em Segoe UI Bold, já convertido para curvas no arquivo de
  arte. A fonte Segoe UI **não** é empacotada, redistribuída nem usada em tempo
  de execução.
- Foi usado o PNG em 2x/3x: o wordmark de 687 px é exibido a ~198 px no splash e
  no loader, cerca de 3,5x. Não foi produzido `JOGA-wordmark.svg` nesta entrega;
  o único SVG de marca é o favicon "J.", vetorizado a partir das curvas do "J" e
  do ponto do wordmark. **Pendente:** vetorizar o wordmark completo para
  `JOGA-wordmark.svg`; até lá, o PNG é a fonte de exibição.
- O splash usa o wordmark completo; o launcher e o favicon usam somente "J.".

## 3. Inventário de assets

| Arquivo | Conteúdo | Fundo | Tamanho |
|---|---|---|---|
| `mobile/assets/brand/JOGA-wordmark.png` | wordmark completo "JOGA." | transparente | 687 × 183 |
| `web/public/brand/JOGA-wordmark.png` | cópia do wordmark | transparente | 687 × 183 |
| `mobile/assets/icon.png` | "J." branco + ponto vermelho | `#0F1214` sólido | 1024 × 1024 |
| `mobile/assets/android-icon-foreground.png` | "J." centralizado na zona segura (~61%) | transparente | 1024 × 1024 |
| `mobile/assets/android-icon-background.png` | somente `#0F1214` | sólido | 1024 × 1024 |
| `mobile/assets/android-icon-monochrome.png` | silhueta de "J." em branco | transparente | 1024 × 1024 |
| `mobile/assets/splash-icon.png` | "JOGA." completo | transparente | 1024 × 1024 |
| `mobile/assets/favicon.png` | "J." | `#0F1214` | 196 × 196 |
| `web/public/favicon.png` | "J." (apple-touch-icon) | `#0F1214` | 196 × 196 |
| `web/public/favicon.svg` | "J." vetorial | `#0F1214` arredondado | viewBox próprio |
| `mobile/assets/fonts/Selawik-Regular.ttf` | interface, peso 400 | — | TTF |
| `mobile/assets/fonts/Selawik-SemiBold.ttf` | interface, peso 600 | — | TTF |
| `mobile/assets/fonts/Selawik-Bold.ttf` | interface, pesos 700–900 | — | TTF |
| `web/public/fonts/Selawik-*.woff2` | interface web, 400/600/700 | — | WOFF2 |

Regras do ícone:

- Símbolo compacto "J." no launcher e no favicon; wordmark completo no splash e
  no loader.
- O "J." mantém as proporções do "J" e do ponto do wordmark. O ponto isolado é
  uma elipse limpa com a mesma proporção medida (47,1 × 45,8 unidades), porque
  no wordmark o ponto encosta na perna do "A".
- Nada de texto pequeno, sombra ou gradiente dentro do ícone.
- O foreground do Android usa ~61% do canvas para caber na zona segura da
  máscara adaptativa. O ícone legado usa ~66%, para leitura a 48 px.
- O splash tem 920 px de wordmark em um canvas de 1024 px (~5% de margem por
  lado); o plugin usa `imageWidth: 220`, `resizeMode: "contain"` e variante
  `dark` idêntica. O wordmark exibido fica em ~198 px.

## 4. Tipografia

A interface usa **Selawik** (SIL Open Font License 1.1), substituta de código
aberto com métrica compatível com Segoe UI.

Mapa de pesos:

| Peso do tema | Arquivo |
|---|---|
| 400 | `Selawik-Regular` |
| 600 | `Selawik-SemiBold` |
| 700, 800, 900 | `Selawik-Bold` |

No mobile, os arquivos são carregados por `expo-font` em `App.tsx` e o
`src/ui/text.tsx` escolhe a família pelo peso, mantendo `fontWeight: normal`
para evitar negrito sintético no Android. O splash nativo permanece visível até
as fontes e a sessão estarem prontas.

No painel, os três arquivos são declarados em `@font-face` com
`font-display: swap`, servidos de `/fonts/` (self-host, sem CDN). O Bold é
declarado para a faixa 700–900, então títulos 800/900 usam o mesmo arquivo sem
negrito sintético. A stack de `web/src/styles.css` começa por `"Selawik"` e não
inclui `"Inter"`.

O peso 900 do display fica levemente mais leve que o Segoe UI Black. Para
compensar, os títulos mantêm caixa alta e tracking negativo; não foi adicionada
outra fonte de display.

## 5. Licenças

- **Segoe UI:** fonte proprietária da Microsoft. Não é redistribuível. Nenhum
  arquivo de Segoe UI é versionado nem empacotado no APK. O wordmark foi
  convertido para curvas antes de entrar no repositório.
- **Selawik:** SIL Open Font License 1.1. O texto integral da licença está em
  `mobile/assets/fonts/LICENSE-Selawik.txt` e
  `web/public/fonts/LICENSE-Selawik.txt`. Origem: repositório
  `microsoft/Selawik`, release 1.01.
- O nome reservado "Selawik" e a licença OFL continuam valendo para cópias e
  versões modificadas dos arquivos.

## 6. Como regerar os assets

1. Parta do wordmark `mobile/assets/brand/JOGA-wordmark.png`. Não use um PNG
   com fundo embutido no splash nem no foreground do Android.
2. Extraia o "J" (cerca de 109 × 183 px a partir da origem) e o ponto vermelho
   do wordmark. Vetorize o "J" com Potrace em modo silhueta (o ponto isolado é
   reconstruído como elipse na proporção medida).
3. Componha o "J." com o ponto alinhado à base do "J" e recoloque:
   - `icon.png`: 1024 × 1024, fundo `#0F1214`, marca com ~66% da largura;
   - `android-icon-foreground.png`: 1024 × 1024 transparente, marca com ~61%;
   - `android-icon-background.png`: 1024 × 1024 `#0F1214`;
   - `android-icon-monochrome.png`: 1024 × 1024 transparente, silhueta branca;
   - `favicon.png`: 196 × 196, fundo `#0F1214`, marca com ~66%;
   - `favicon.svg`: mesmas curvas do "J" e elipse do ponto, sobre fundo
     `#0F1214` arredondado.
4. Para o splash, redimensione o wordmark para 920 px de largura (~5% de margem
   por lado), centralize em um canvas transparente de 1024 × 1024 e salve como
   `splash-icon.png`.
5. Rode `pnpm exec expo config --type public --json` para conferir os caminhos e
   o plugin do splash. Teste a máscara Android (círculo, squircle e arredondado)
   e um cold start em build de release.

Comandos úteis de conferência (a partir da raiz):

```powershell
magick identify mobile/assets/icon.png mobile/assets/android-icon-foreground.png mobile/assets/splash-icon.png
magick identify web/public/favicon.svg
```

## 7. Configuração vigente

- `mobile/app.json`: `backgroundColor: "#0F1214"`, `android.adaptiveIcon.backgroundColor: "#0F1214"`,
  plugin `expo-splash-screen` com `#0F1214` e `imageWidth: 220`.
- `App.tsx`: `expo-status-bar` em `style="light"` enquanto o loader escuro está
  visível; depois acompanha o tema claro/escuro do app.
- Não foi necessário adicionar `expo-system-ui`: o splash nativo, o root view e
  o `backgroundColor` do app já cobrem o fundo escuro no cold start.
- `web/index.html`: `theme-color` `#0F1214`, `favicon.svg`, fallback
  `favicon.png` e `apple-touch-icon` `/favicon.png`.
