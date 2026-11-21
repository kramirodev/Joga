import assert from 'node:assert/strict';
import test from 'node:test';

import { buildVisualPayload } from './visualPayload.ts';

const DEFAULT_IDENTITY = {
  icon_key: 'icon:user',
  frame_key: 'frame:carbon',
  accent_key: 'accent:graphite',
  entry_key: 'entry:default',
  emote_key: 'emote:wave',
  badge_key: 'badge:none',
  catalog_version: 'local-1',
};

const item = (key, kind) => ({
  key,
  kind,
  name: key,
  asset_ref: key,
  unlock_state: 'free',
  active: true,
});

const serverCatalog = {
  version: 'server-1',
  items: [
    item('icon-server', 'icon'),
    item('frame-server', 'frame'),
    item('accent-server', 'accent'),
    item('entry-server', 'entry'),
    item('emote-server', 'emote'),
    item('badge-server', 'badge'),
  ],
};

const confirmed = {
  icon_key: 'icon-server',
  frame_key: 'frame-server',
  accent_key: 'accent-server',
  entry_key: 'entry-server',
  emote_key: 'emote-server',
  badge_key: 'badge-server',
  catalog_version: 'server-1',
};

test('sem catálogo do servidor o app não envia PUT com chave local', () => {
  const payload = buildVisualPayload({
    identity: DEFAULT_IDENTITY,
    catalog: serverCatalog,
    confirmed,
    localOnly: true,
  });
  assert.equal(payload, null);
});

test('entry/emote preservam a chave confirmada pelo servidor', () => {
  const payload = buildVisualPayload({
    identity: DEFAULT_IDENTITY,
    catalog: serverCatalog,
    confirmed,
    localOnly: false,
  });
  assert.ok(payload);
  assert.equal(payload.entry_key, 'entry-server');
  assert.equal(payload.emote_key, 'emote-server');
  assert.equal(payload.icon_key, 'icon-server');
});

test('chave editada fora do catálogo cai para a confirmada, nunca para o default', () => {
  const payload = buildVisualPayload({
    identity: DEFAULT_IDENTITY,
    catalog: serverCatalog,
    confirmed,
    localOnly: false,
  });
  assert.ok(payload);
  assert.equal(payload.icon_key, 'icon-server');
  assert.equal(payload.badge_key, 'badge-server');
  assert.equal(payload.entry_key, 'entry-server');
  assert.equal(payload.emote_key, 'emote-server');
});

test('sem confirmação do servidor não envia PUT (não apaga entry/emote)', () => {
  const payload = buildVisualPayload({
    identity: DEFAULT_IDENTITY,
    catalog: serverCatalog,
    confirmed: null,
    localOnly: false,
  });
  assert.equal(payload, null);
});

test('rascunho válido no catálogo remoto é respeitado', () => {
  const draft = {
    ...DEFAULT_IDENTITY,
    icon_key: 'icon-server',
    frame_key: 'frame-server',
    accent_key: 'accent-server',
    badge_key: 'badge-server',
  };
  const payload = buildVisualPayload({
    identity: draft,
    catalog: serverCatalog,
    confirmed,
    localOnly: false,
  });
  assert.ok(payload);
  assert.equal(payload.icon_key, 'icon-server');
});
