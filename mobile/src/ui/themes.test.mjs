import assert from 'node:assert/strict';
import test from 'node:test';

import { light } from './theme.ts';
import { contrastRatio, isThemeId, themeById, themes } from './themes.ts';

const paletteKeys = Object.keys(light).sort();
const expectedIds = [
  'claro',
  'escuro',
  'noite-quadra',
  'golden-hour',
  'dia-de-jogo',
  'ceu-vermelho',
  'ceu-claro',
];
const expectedArts = ['noite-quadra', 'golden-hour', 'dia-de-jogo', 'ceu-vermelho', 'ceu-claro'];

test('catálogo cobre claro, escuro e as cinco artes', () => {
  assert.deepEqual(
    themes.map((theme) => theme.id),
    expectedIds,
  );
  assert.equal(new Set(expectedIds).size, expectedIds.length);
});

test('todos os temas têm a paleta completa em hex', () => {
  for (const theme of themes) {
    assert.equal(typeof theme.name, 'string');
    assert.ok(theme.name.length > 0, `${theme.id} sem nome`);
    assert.equal(typeof theme.dark, 'boolean', `${theme.id} sem dark`);
    assert.ok(expectedArts.includes(theme.art), `${theme.id} aponta para arte desconhecida`);
    assert.deepEqual(
      Object.keys(theme.palette).sort(),
      paletteKeys,
      `${theme.id} com chaves erradas`,
    );
    for (const key of paletteKeys) {
      assert.match(
        theme.palette[key],
        /^#[0-9A-F]{6}$/i,
        `${theme.id}.${key} não é hex de 6 dígitos`,
      );
    }
  }
});

test('texto e marca têm contraste mínimo de 4,5 em todos os temas', () => {
  for (const theme of themes) {
    const { palette } = theme;
    assert.ok(
      contrastRatio(palette.ink, palette.bg) >= 4.5,
      `${theme.id}: ink sobre bg = ${contrastRatio(palette.ink, palette.bg)}`,
    );
    assert.ok(
      contrastRatio(palette.ink, palette.surface) >= 4.5,
      `${theme.id}: ink sobre surface = ${contrastRatio(palette.ink, palette.surface)}`,
    );
    assert.ok(
      contrastRatio(palette.brandInk, palette.brand) >= 4.5,
      `${theme.id}: brandInk sobre brand = ${contrastRatio(palette.brandInk, palette.brand)}`,
    );
  }
});

test('themeById cai no claro quando o id é desconhecido', () => {
  const fallback = themeById('tema-que-nao-existe');
  assert.equal(fallback.id, 'claro');
  assert.equal(fallback.palette, light);
  assert.equal(themeById('noite-quadra').id, 'noite-quadra');
});

test('isThemeId valida apenas ids do catálogo', () => {
  assert.equal(isThemeId('ceu-vermelho'), true);
  assert.equal(isThemeId('claro'), true);
  assert.equal(isThemeId('nope'), false);
  assert.equal(isThemeId(null), false);
  assert.equal(isThemeId(7), false);
});

test('contrastRatio é pura e segue a escala WCAG', () => {
  assert.equal(contrastRatio('#FFFFFF', '#000000'), 21);
  assert.equal(contrastRatio('#000000', '#000000'), 1);
  assert.equal(contrastRatio('#000', '#fff'), 21);
});
