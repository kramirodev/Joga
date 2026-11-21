import assert from 'node:assert/strict';
import test from 'node:test';

import {
  EMOTE_TOKEN_LIMIT,
  chatEmoteOptions,
  emoteToken,
  isEmoteOnly,
  parseEmoteBody,
} from './emote.ts';

// Mesmo formato do fallback local de `identity.ts`; o parser não deve resolver
// chaves locais.
const localCatalog = {
  version: 'local-1',
  items: [
    {
      key: 'emote:wave',
      kind: 'emote',
      name: 'Aceno',
      asset_ref: 'icon:users',
      unlock_state: 'free',
      active: true,
    },
  ],
};

const serverCatalog = {
  version: 'server-1',
  items: [
    {
      key: 'emote-joinha',
      kind: 'emote',
      name: 'Joinha',
      asset_ref: 'emotes/emote-joinha.svg',
      unlock_state: 'free',
      active: true,
    },
    {
      key: 'emote-icone',
      kind: 'emote',
      name: 'Sorriso',
      asset_ref: 'icon:users',
      unlock_state: 'free',
      active: true,
    },
    {
      key: 'emote-xp',
      kind: 'emote',
      name: 'Fogo',
      asset_ref: 'emotes/emote-fogo.svg',
      unlock_state: 'xp',
      active: true,
    },
    {
      key: 'icon-user',
      kind: 'icon',
      name: 'Jogador',
      asset_ref: 'icon:user',
      unlock_state: 'free',
      active: true,
    },
  ],
};

test('token do emote usa o campo body existente', () => {
  assert.equal(emoteToken('emote-joinha'), '[emote:emote-joinha]');
});

test('texto puro não é alterado', () => {
  const segments = parseEmoteBody('Boa jogada, pessoal!', serverCatalog);
  assert.deepEqual(segments, [{ type: 'text', text: 'Boa jogada, pessoal!' }]);
  assert.equal(isEmoteOnly(segments), false);
});

test('um emote é separado do texto e resolve nome', () => {
  const segments = parseEmoteBody('Valeu [emote:emote-joinha] demais', serverCatalog);
  assert.deepEqual(
    segments.map((segment) => segment.type),
    ['text', 'emote', 'text'],
  );
  const emote = segments[1];
  assert.equal(emote.type, 'emote');
  assert.equal(emote.name, 'Joinha');
  // asset SVG não é carregado: cai no nome, nunca em ícone aleatório.
  assert.equal(emote.icon, null);
});

test('asset icon:* usa o mapeamento existente de ícones', () => {
  const segments = parseEmoteBody('[emote:emote-icone]', serverCatalog);
  assert.equal(segments.length, 1);
  const emote = segments[0];
  assert.equal(emote.type, 'emote');
  assert.equal(emote.icon, 'users');
  assert.equal(isEmoteOnly(segments), true);
});

test('vários emotes preservam a ordem e o texto entre eles', () => {
  const segments = parseEmoteBody(
    '[emote:emote-joinha] meio [emote:emote-icone] fim',
    serverCatalog,
  );
  assert.deepEqual(
    segments.map((segment) => (segment.type === 'emote' ? segment.key : segment.text)),
    ['emote-joinha', ' meio ', 'emote-icone', ' fim'],
  );
});

test('token desconhecido e chave de outro kind continuam literais', () => {
  assert.deepEqual(parseEmoteBody('[emote:nao-existe]', serverCatalog), [
    { type: 'text', text: '[emote:nao-existe]' },
  ]);
  assert.deepEqual(parseEmoteBody('[emote:icon-user]', serverCatalog), [
    { type: 'text', text: '[emote:icon-user]' },
  ]);
  assert.deepEqual(parseEmoteBody('[emote:Emote-Joinha]', serverCatalog), [
    { type: 'text', text: '[emote:Emote-Joinha]' },
  ]);
});

test('catálogo local ou vazio não resolve token', () => {
  const local = parseEmoteBody('[emote:emote-joinha]', localCatalog);
  assert.deepEqual(local, [{ type: 'text', text: '[emote:emote-joinha]' }]);
  const empty = parseEmoteBody('[emote:emote-joinha]', { items: [] });
  assert.deepEqual(empty, [{ type: 'text', text: '[emote:emote-joinha]' }]);
});

test('corpo de 2000 caracteres não quebra e mantém o texto', () => {
  const body = `${'a'.repeat(1980)}[emote:emote-joinha]`;
  const segments = parseEmoteBody(body, serverCatalog);
  assert.equal(body.length, 2000);
  assert.equal(segments.length, 2);
  assert.equal(segments[0].type, 'text');
  assert.equal(segments[1].type, 'emote');
});

test('acima do limite de tokens o excedente fica literal', () => {
  const token = '[emote:emote-joinha]';
  const body = token.repeat(EMOTE_TOKEN_LIMIT + 2);
  const segments = parseEmoteBody(body, serverCatalog);
  const emotes = segments.filter((segment) => segment.type === 'emote');
  assert.equal(emotes.length, EMOTE_TOKEN_LIMIT);
  const last = segments[segments.length - 1];
  assert.equal(last.type, 'text');
  assert.equal(last.text, token.repeat(2));
});

test('seletor oferece só emotes grátis do catálogo do servidor', () => {
  const keys = chatEmoteOptions(serverCatalog).map((item) => item.key);
  assert.deepEqual(keys, ['emote-joinha', 'emote-icone']);
  assert.deepEqual(chatEmoteOptions(localCatalog), []);
});
