// Gera `src/ui/themeArt.ts` a partir de `assets/themes/*.svg`.
//
// O `SvgXml` do react-native-svg não resolve folhas de estilo CSS, então o
// Golden Hour (exportado com classes `.cls-N`) tem as declarações embutidas
// em `style` antes de virar string. Os ids de gradiente/máscara são
// prefixados pelo tema para que vários SVGs possam conviver na mesma tela.
//
// Uso: node scripts/generate-theme-art.mjs

import { readFile, writeFile } from 'node:fs/promises';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const assetsDir = join(root, 'assets', 'themes');
const output = join(root, 'src', 'ui', 'themeArt.ts');

const arts = {
  'noite-quadra': 'noite-quadra.svg',
  'golden-hour': 'golden-hour.svg',
  'dia-de-jogo': 'dia-de-jogo.svg',
  'ceu-vermelho': 'ceu-vermelho.svg',
  'ceu-claro': 'ceu-claro.svg',
};

function parseCssClasses(css) {
  const classes = new Map();
  for (const match of css.matchAll(/\.([\w-]+)\s*\{([^}]*)\}/g)) {
    // `&apos;` contém `;`, então decodifica antes de separar declarações.
    const declarations = match[2]
      .replaceAll('&apos;', "'")
      .split(';')
      .map((item) => item.trim())
      .filter(Boolean)
      // Fonte embutida não existe no aparelho e o fallback não é confiável.
      .filter((item) => !/^font-family\s*:/i.test(item))
      .join(';');
    classes.set(match[1], declarations);
  }
  return classes;
}

function inlineStyles(source) {
  const styleBlock = source.match(/<style>([\s\S]*?)<\/style>/);
  if (!styleBlock) {
    return source;
  }
  const classes = parseCssClasses(styleBlock[1]);
  const withoutStyle = source.replace(styleBlock[0], '');
  return withoutStyle.replace(/<([a-zA-Z]+)([^>]*?)(\/?)>/g, (tag, name, attributes, selfClose) => {
    const classMatch = attributes.match(/\sclass="([^"]*)"/);
    if (!classMatch) {
      return tag;
    }
    const declarations = classMatch[1]
      .split(/\s+/)
      .filter(Boolean)
      .map((className) => classes.get(className) ?? '')
      .filter(Boolean)
      .join(';');
    const clean = attributes.replace(classMatch[0], '');
    return `<${name}${clean} style="${declarations}"${selfClose}>`;
  });
}

function prepare(source, key) {
  let svg = source.replace(/<\?xml[^>]*\?>/g, '').replace(/<!--[\s\S]*?-->/g, '');
  svg = inlineStyles(svg);
  svg = svg
    .replace(/\s(?:role|aria-label|data-name|xml:space|xmlns(?::xlink)?)="[^"]*"/g, '')
    .replace(/<title>[\s\S]*?<\/title>/g, '');
  // Prefixa ids para que dois SVGs na mesma tela não compartilhem defs.
  svg = svg
    .replace(/\bid="([^"]+)"/g, (_, id) => `id="${key}__${id}"`)
    .replace(/url\(#([^)]+)\)/g, (_, id) => `url(#${key}__${id})`);
  return svg.replace(/>\s+</g, '><').trim();
}

function asTemplateLiteral(svg) {
  return `\`${svg.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$\{/g, '\\${')}\``;
}

const entries = [];
for (const [key, file] of Object.entries(arts)) {
  const source = await readFile(join(assetsDir, file), 'utf8');
  entries.push(`  '${key}': ${asTemplateLiteral(prepare(source, key))},`);
}

const file = `// Gerado por scripts/generate-theme-art.mjs a partir de assets/themes/*.svg.
// Não editar à mão: rode o script para regenerar.

export const themeArtXml = {
${entries.join('\n')}
} as const;

export type ThemeArtKey = keyof typeof themeArtXml;
`;

await writeFile(output, file, 'utf8');
process.stdout.write(
  `themeArt.ts gerado (${relative(root, output)}) com ${entries.length} artes.\n`,
);
