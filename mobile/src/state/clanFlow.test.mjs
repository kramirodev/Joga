import assert from 'node:assert/strict';
import test from 'node:test';

import {
  clanCardAction,
  clanCardActionLabel,
  clanCardHint,
  clanJoinState,
  clanRequestErrorCopy,
  clanRequestStatusLabel,
} from './clanFlow.ts';

const approval = { join_policy: 'approval', full: false };

test('card do clã: membro abre mesmo com pedido antigo', () => {
  assert.equal(
    clanCardAction({ is_member: true, my_request: { status: 'pending' }, ...approval }),
    'open',
  );
  assert.equal(clanCardAction({ is_member: true, my_request: null, ...approval }), 'open');
});

test('card do clã: pedido pendente bloqueia reenvio', () => {
  assert.equal(
    clanCardAction({ is_member: false, my_request: { status: 'pending' }, ...approval }),
    'pending',
  );
  // Pendente vence vaga e política: o pedido já está na fila do clã.
  assert.equal(
    clanCardAction({
      is_member: false,
      my_request: { status: 'pending' },
      join_policy: 'approval',
      full: true,
    }),
    'pending',
  );
});

test('card do clã: recusado ou cancelado permite solicitar de novo', () => {
  assert.equal(
    clanCardAction({ is_member: false, my_request: { status: 'rejected' }, ...approval }),
    'resend',
  );
  assert.equal(
    clanCardAction({ is_member: false, my_request: { status: 'cancelled' }, ...approval }),
    'resend',
  );
  assert.equal(clanCardAction({ is_member: false, my_request: null, ...approval }), 'request');
});

test('card do clã: vaga e política fechada vencem o reenvio', () => {
  assert.equal(
    clanCardAction({
      is_member: false,
      my_request: { status: 'rejected' },
      join_policy: 'approval',
      full: true,
    }),
    'full',
  );
  assert.equal(
    clanCardAction({
      is_member: false,
      my_request: { status: 'cancelled' },
      join_policy: 'closed',
      full: false,
    }),
    'closed',
  );
});

test('card do clã: clã aberto com vaga entra direto', () => {
  assert.equal(
    clanCardAction({
      is_member: false,
      my_request: null,
      join_policy: 'open',
      full: false,
    }),
    'join',
  );
  assert.equal(
    clanCardAction({
      is_member: false,
      my_request: null,
      join_policy: 'approval',
      full: true,
    }),
    'full',
  );
});

test('rótulos do card não repetem "Solicitar" quando já há pedido', () => {
  assert.equal(clanCardActionLabel('pending'), 'Pendente');
  assert.equal(clanCardActionLabel('resend'), 'Solicitar de novo');
  assert.equal(clanCardActionLabel('join'), 'Entrar');
  assert.equal(clanCardActionLabel('join', true), 'Entrando…');
  assert.equal(clanCardActionLabel('full'), 'Cheio');
  assert.equal(clanCardActionLabel('closed'), 'Fechado');
});

test('cancelar e recusar têm copy própria no card', () => {
  assert.equal(
    clanCardHint({ action: 'resend', myRequestStatus: 'cancelled', vacancies: 3 }),
    'Você cancelou seu pedido anterior.',
  );
  assert.equal(
    clanCardHint({ action: 'resend', myRequestStatus: 'rejected', vacancies: 3 }),
    'Seu pedido anterior não foi aprovado.',
  );
  assert.equal(
    clanCardHint({ action: 'pending', myRequestStatus: 'pending', vacancies: 0 }),
    'Aguardando aprovação do clã',
  );
  assert.equal(clanCardHint({ action: 'request', myRequestStatus: null, vacancies: 3 }), '3 vagas');
  assert.equal(
    clanCardHint({ action: 'request', myRequestStatus: null, vacancies: -2 }),
    '0 vagas',
  );
  assert.equal(
    clanCardHint({ action: 'open', myRequestStatus: null, vacancies: 0 }),
    'Você já participa deste clã',
  );
  assert.equal(clanCardHint({ action: 'full', myRequestStatus: null, vacancies: 0 }), 'Sem vaga');
  assert.equal(
    clanCardHint({ action: 'closed', myRequestStatus: null, vacancies: 0 }),
    'Não aceita entradas',
  );
});

test('etapa da entrada: detalhe pendente abre direto como enviado', () => {
  assert.equal(clanJoinState({ status: 'pending' }, null), 'pending');
  assert.equal(clanJoinState({ status: 'pending' }, undefined), 'pending');
});

test('etapa da entrada: recusado e cancelado voltam ao formulário', () => {
  assert.equal(clanJoinState({ status: 'rejected' }, null), 'form');
  assert.equal(clanJoinState({ status: 'cancelled' }, null), 'form');
  assert.equal(clanJoinState(null, null), 'form');
});

test('etapa da entrada: resposta do servidor vence o detalhe antigo', () => {
  assert.equal(clanJoinState(null, { status: 'joined' }), 'joined');
  assert.equal(clanJoinState({ status: 'rejected' }, { status: 'joined' }), 'joined');
  assert.equal(
    clanJoinState({ status: 'rejected' }, { status: 'pending', request: { status: 'pending' } }),
    'pending',
  );
  assert.equal(
    clanJoinState(null, { status: 'pending', request: { status: 'approved' } }),
    'joined',
  );
});

test('erros de pedido de clã viram texto curto sem código cru', () => {
  assert.equal(clanRequestErrorCopy('request_not_pending'), 'Este pedido já foi decidido.');
  assert.equal(clanRequestErrorCopy('already_member'), 'Você já é membro deste clã.');
  assert.match(clanRequestErrorCopy('already_in_clan'), /outro clã/);
  assert.match(clanRequestErrorCopy('clan_full'), /Clã cheio/);
  assert.match(clanRequestErrorCopy('clan_cooldown'), /7 dias/);
  assert.match(clanRequestErrorCopy('clan_closed'), /não aceita/);
  assert.match(clanRequestErrorCopy('admin_required'), /Dono e os Oficiais/);
  assert.equal(clanRequestErrorCopy(''), 'Não foi possível agora. Tente de novo.');
  assert.equal(clanRequestErrorCopy('codigo_novo'), 'Não foi possível agora. Tente de novo.');
  assert.doesNotMatch(clanRequestErrorCopy('codigo_novo'), /codigo_novo/);
});

test('status do pedido tem rótulo legível no histórico', () => {
  assert.equal(clanRequestStatusLabel('pending'), 'Pendente');
  assert.equal(clanRequestStatusLabel('approved'), 'Aprovado');
  assert.equal(clanRequestStatusLabel('rejected'), 'Recusado');
  assert.equal(clanRequestStatusLabel('cancelled'), 'Cancelado');
  assert.equal(clanRequestStatusLabel(null), 'Sem status');
});
