import assert from 'node:assert/strict';
import test from 'node:test';

import { decideThemeSync } from './themeSync.ts';

test('tema conhecido no servidor vence e é aplicado sem upload', () => {
  assert.deepEqual(decideThemeSync({ serverThemeId: 'noite-quadra', localThemeId: 'claro' }), {
    kind: 'apply',
    themeId: 'noite-quadra',
  });
});

test('servidor nulo envia o tema local na primeira sincronização', () => {
  assert.deepEqual(decideThemeSync({ serverThemeId: null, localThemeId: 'golden-hour' }), {
    kind: 'upload',
    themeId: 'golden-hour',
  });
  assert.deepEqual(decideThemeSync({ serverThemeId: undefined, localThemeId: 'escuro' }), {
    kind: 'upload',
    themeId: 'escuro',
  });
});

test('ID desconhecido no servidor cai no local sem sobrescrever o servidor', () => {
  assert.deepEqual(
    decideThemeSync({ serverThemeId: 'tema-do-futuro', localThemeId: 'dia-de-jogo' }),
    { kind: 'keep' },
  );
});

test('sem tema local e sem tema válido no servidor mantém o fallback', () => {
  assert.deepEqual(decideThemeSync({ serverThemeId: null, localThemeId: null }), {
    kind: 'keep',
  });
  assert.deepEqual(decideThemeSync({ serverThemeId: null, localThemeId: 'nao-existe' }), {
    kind: 'keep',
  });
});

test('alteração local pendente é reenviada mesmo com tema no servidor', () => {
  assert.deepEqual(
    decideThemeSync({
      serverThemeId: 'escuro',
      localThemeId: 'ceu-vermelho',
      pendingUpload: true,
    }),
    { kind: 'upload', themeId: 'ceu-vermelho' },
  );
});

test('pendência sem tema local válido não inventa upload', () => {
  assert.deepEqual(
    decideThemeSync({ serverThemeId: 'claro', localThemeId: null, pendingUpload: true }),
    { kind: 'apply', themeId: 'claro' },
  );
  assert.deepEqual(
    decideThemeSync({ serverThemeId: null, localThemeId: null, pendingUpload: true }),
    { kind: 'keep' },
  );
});
