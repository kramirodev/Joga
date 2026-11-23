import assert from 'node:assert/strict';
import test from 'node:test';

import { dark, light } from './theme.ts';

const TOLERANCE = 0.05;

/** Luminância relativa WCAG 2.x para um hex `#RRGGBB`. */
function luminance(hex) {
  const value = hex.replace('#', '');
  const channels = [0, 2, 4].map((offset) => parseInt(value.slice(offset, offset + 2), 16) / 255);
  const linear = channels.map((channel) =>
    channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

/** Razão de contraste entre duas cores, arredondada como na documentação. */
function contrast(foreground, background) {
  const a = luminance(foreground);
  const b = luminance(background);
  const [lighter, darker] = a > b ? [a, b] : [b, a];
  return Math.round(((lighter + 0.05) / (darker + 0.05)) * 100) / 100;
}

function atLeast(foreground, background, minimum, label) {
  const ratio = contrast(foreground, background);
  assert.ok(
    ratio >= minimum - TOLERANCE,
    `${label}: ${foreground} sobre ${background} = ${ratio}, esperado >= ${minimum}`,
  );
  return ratio;
}

function below(foreground, background, maximum, label) {
  const ratio = contrast(foreground, background);
  assert.ok(
    ratio <= maximum + TOLERANCE,
    `${label}: ${foreground} sobre ${background} = ${ratio}, esperado <= ${maximum}`,
  );
  return ratio;
}

test('escuro possui as chaves de paleta novas', () => {
  for (const key of [
    'brand',
    'brandStrong',
    'brandInk',
    'lineSubtle',
    'focus',
    'subtle',
    'success',
    'warning',
    'danger',
    'info',
  ]) {
    assert.equal(typeof dark[key], 'string', `dark.${key} ausente`);
    assert.equal(typeof light[key], 'string', `light.${key} ausente`);
    assert.match(dark[key], /^#[0-9A-F]{6}$/i, `dark.${key} não é hex`);
  }
});

test('escuro usa exatamente a paleta do Prompt 18', () => {
  assert.equal(dark.bg, '#0A0B0D');
  assert.equal(dark.surface, '#131417');
  assert.equal(dark.surface2, '#191A1E');
  assert.equal(dark.surface3, '#222327');
  assert.equal(dark.ink, '#F4F2EE');
  assert.equal(dark.muted, '#A6A6A6');
  assert.equal(dark.subtle, '#8E8E8E');
  assert.equal(dark.brand, '#F03B3B');
  assert.equal(dark.brandStrong, '#FF5C5C');
  assert.equal(dark.brandInk, '#140404');
  assert.equal(dark.line, '#2A2B2F');
  assert.equal(dark.lineSubtle, '#414349');
  assert.equal(dark.lineStrong, '#6E7077');
  assert.equal(dark.focus, '#FF5C5C');
  assert.equal(dark.success, '#79D8BF');
  assert.equal(dark.warning, '#FFCF72');
  assert.equal(dark.danger, '#FF8F7F');
  assert.equal(dark.info, '#8EC8FF');
});

test('claro mantém os valores atuais', () => {
  assert.equal(light.bg, '#F1F3F0');
  assert.equal(light.surface, '#FFFFFF');
  assert.equal(light.ink, '#17191B');
  assert.equal(light.lime, '#E53935');
  assert.equal(light.line, '#D5D9D6');
  assert.equal(light.brand, '#E53935');
  assert.equal(light.brandInk, '#F1F3F0');
  assert.equal(light.lineSubtle, '#D5D9D6');
});

test('texto do escuro tem contraste >= 4,5', () => {
  atLeast(dark.ink, dark.surface, 4.5, 'ink');
  atLeast(dark.ink, dark.bg, 4.5, 'ink no fundo');
  atLeast(dark.muted, dark.surface, 4.5, 'muted');
  atLeast(dark.subtle, dark.surface2, 4.5, 'subtle em surface2');
  atLeast(dark.brandStrong, dark.surface2, 4.5, 'brandStrong em surface2');
  atLeast(dark.brandStrong, dark.surface3, 4.5, 'brandStrong em surface3');
});

test('preenchimento de marca usa brandInk', () => {
  atLeast(dark.brandInk, dark.brand, 4.5, 'brandInk sobre brand');
  atLeast(dark.brandInk, dark.brandStrong, 4.5, 'brandInk sobre brandStrong');
  atLeast(dark.brandInk, dark.danger, 4.5, 'brandInk sobre danger');
});

test('branco sobre a marca reprova (por isso brandInk)', () => {
  below('#F4F2EE', dark.brand, 4.5, 'branco sobre brand');
  below('#F1F3F0', dark.brand, 4.5, 'claro legado sobre brand');
});

test('contorno interativo tem contraste >= 3 em todas as superfícies', () => {
  atLeast(dark.lineStrong, dark.surface, 3, 'lineStrong em surface');
  atLeast(dark.lineStrong, dark.bg, 3, 'lineStrong em bg');
  atLeast(dark.lineStrong, dark.surface2, 3, 'lineStrong em surface2');
  atLeast(dark.lineStrong, dark.surface3, 3, 'lineStrong em surface3');
});

test('foco tem contraste >= 3 em surface e bg', () => {
  atLeast(dark.focus, dark.surface, 3, 'focus em surface');
  atLeast(dark.focus, dark.bg, 3, 'focus em bg');
});

test('marca é preenchimento/ícone; texto pequeno em surface2/3 usa brandStrong', () => {
  atLeast(dark.brand, dark.surface, 3, 'brand em surface');
  const onSurface2 = contrast(dark.brand, dark.surface2);
  assert.ok(
    onSurface2 < 4.5,
    `brand em surface2 = ${onSurface2}; texto pequeno deve usar brandStrong`,
  );
  atLeast(dark.brandStrong, dark.surface2, 4.5, 'brandStrong em surface2');
  atLeast(dark.brandStrong, dark.surface3, 4.5, 'brandStrong em surface3');
});

test('contêiner estático e divisor ficam abaixo do interativo, mas visíveis', () => {
  const subtleOnBg = atLeast(dark.lineSubtle, dark.bg, 1.8, 'lineSubtle em bg');
  const divider = contrast(dark.line, dark.surface);
  assert.ok(divider < subtleOnBg, `divisor ${divider} deve ser mais fraco que o contorno estático`);
  assert.ok(divider > 1, `divisor ${divider} precisa existir`);
});

test('semânticos existem e não viram vermelho de marca', () => {
  for (const tone of ['success', 'warning', 'danger', 'info']) {
    atLeast(dark[tone], dark.surface, 4.5, `${tone} como texto`);
    assert.notEqual(dark[tone], dark.brand, `${tone} não pode ser a cor de marca`);
  }
});
