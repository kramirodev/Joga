import assert from 'node:assert/strict';
import test from 'node:test';

import {
  cycleStatusLabel,
  freeTickets,
  legacyTickets,
  passStatusLabel,
  planCycleName,
  planDurationLabel,
  planInstallmentsLabel,
  receiptAvailable,
} from './billing.ts';

test('duração e nome do ciclo do catálogo', () => {
  assert.equal(planDurationLabel(1), '1 mês');
  assert.equal(planDurationLabel(3), '3 meses');
  assert.equal(planDurationLabel(6), '6 meses');
  assert.equal(planCycleName(1), 'Mensal');
  assert.equal(planCycleName(3), 'Trimestral');
  assert.equal(planCycleName(6), 'Semestral');
  assert.equal(planInstallmentsLabel(1), 'à vista no Pix');
  assert.equal(planInstallmentsLabel(3), '3 parcelas');
});

test('status da assinatura e dos ciclos', () => {
  assert.equal(passStatusLabel('active'), 'ATIVA');
  assert.equal(passStatusLabel('pending'), 'AGUARDANDO PAGAMENTO');
  assert.equal(passStatusLabel('expired'), 'EXPIRADA');
  assert.equal(passStatusLabel('cancelled'), 'CANCELADA');
  assert.equal(cycleStatusLabel('delivered'), 'Entregue');
  assert.equal(cycleStatusLabel('scheduled'), 'Agendado');
  assert.equal(cycleStatusLabel(null), '—');
});

test('crédito legado é separado da franquia e do grátis', () => {
  const lots = [
    { id: '1', source: 'purchase', original_amount: 10, remaining: 4 },
    { id: '2', source: 'refund', original_amount: 3, remaining: 2 },
    { id: '3', source: 'pass', original_amount: 20, remaining: 7 },
    { id: '4', source: 'free', original_amount: 5, remaining: 1 },
    { id: '5', source: 'free_level', original_amount: 2, remaining: 2 },
    { id: '6', source: 'admin', original_amount: 1, remaining: 1 },
  ];
  assert.equal(legacyTickets(lots), 6);
  assert.equal(freeTickets(lots), 3);
});

test('recibo só fica disponível após o pagamento', () => {
  assert.equal(receiptAvailable({ paid_at: null, payment: null }), false);
  assert.equal(receiptAvailable({ paid_at: '2026-11-27T12:00:00Z', payment: null }), true);
  assert.equal(receiptAvailable({ paid_at: null, payment: { paid: true } }), true);
  assert.equal(receiptAvailable(null), false);
});
