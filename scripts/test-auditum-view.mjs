import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { auditumView, forgettingReceiptView, AUDITUM_VIEW_CONTRACT, FORGETTING_RECEIPT_CONTRACT } from '../packages/sdk-js/src/index.js';
const f = JSON.parse(readFileSync(new URL('../tests/contracts/views/auditum.json', import.meta.url)));
const supported_contracts = [AUDITUM_VIEW_CONTRACT, FORGETTING_RECEIPT_CONTRACT];
const calls = [];
const options = { supported_contracts, canRead: id => id !== 'ak_withheld',
  readRecord: id => { calls.push(id); return id === f.record.akousma_id ? f.record : id === 'ak_available' ? f.available : null; },
  readReceipt: id => { calls.push(id); return id === 'ak_forgotten' ? f.receipt : null; } };
assert.deepEqual(auditumView(f.record.akousma_id, options), f.expected);
assert(!calls.includes('ak_withheld'));
const before = structuredClone(f), detached = auditumView(f.record.akousma_id, options);
detached.auditum.listenings.length = 0;
assert.deepEqual(f, before);
assert.deepEqual(auditumView('ak_withheld', options), { contract: AUDITUM_VIEW_CONTRACT, record_ref: 'ak_withheld', state: 'withheld' });
assert.equal(auditumView('ak_missing', options).state, 'unavailable');
assert.equal(auditumView('ak_forgotten', options).state, 'forgotten');
assert.throws(() => auditumView(f.record.akousma_id, { ...options, supported_contracts: [] }));
for (const canRead of [() => 1, () => 'yes', async () => true]) assert.throws(() => auditumView('ak_forgotten', { ...options, canRead }));
assert.throws(() => auditumView('ak_missing', { ...options, readRecord: () => { throw new Error('storage failure'); } }), /storage failure/);
assert.throws(() => auditumView('ak_missing', { ...options, readReceipt: () => f.receipt }));
assert.throws(() => auditumView('ak_missing', { ...options, readRecord: () => f.record }));
for (const mutation of [ { record_deleted: false }, { audio_deleted: 1 }, { contract: 'other' },
  { audio_deletion_requested: false }, { shared_audio_preserved: true }, { created_at: '2026-02-30T12:00:00Z' } ]) {
  assert.throws(() => forgettingReceiptView({ ...f.receipt, ...mutation }, 'ak_forgotten'));
}
const shared = forgettingReceiptView({ ...f.receipt, audio_deleted: false, shared_audio_preserved: true }, 'ak_forgotten');
assert.equal(shared.shared_audio_preserved, true);
assert(!JSON.stringify(shared).includes('sensitive'));
console.log('auditum views: permissions before lookup, allowlisted receipts, unavailable references and detached evidence passed');

import { compileContractSchema, schemaErrors } from '../packages/sdk-js/src/listening-contracts.js';
import viewSchema from '../packages/core/schemas/auditum-view.schema.json' with { type: 'json' };
const validateView = compileContractSchema(viewSchema);
for (const id of [f.record.akousma_id, 'ak_withheld', 'ak_missing', 'ak_forgotten']) {
  assert.deepEqual(schemaErrors(validateView, auditumView(id, options)), []);
}
const leaked = structuredClone(f.expected); leaked.references[1].receipt.reason = 'private content';
assert(schemaErrors(validateView, leaked).length > 0);

// Legacy extensions remain opaque even when they use an unreleased extension name.
const legacy = structuredClone(f.record); legacy.extensions.earworm_generation_decision = 'opaque legacy data';
assert.deepEqual(auditumView(legacy.akousma_id, { ...options, readRecord: id => id === legacy.akousma_id ? legacy : options.readRecord(id) }), f.expected);
