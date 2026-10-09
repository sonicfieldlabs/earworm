import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { nextRecordErrors, nextRecordReferenceErrors, promoteLegacyAppeal, akousmaShapeErrors } from "../packages/sdk-js/src/index.js";
import { compileContractSchema } from "../packages/sdk-js/src/listening-contracts.js";
import legacySchema from "../packages/core/schemas/akousma.schema.json" with { type: "json" };
const legacyValid = compileContractSchema(legacySchema);
const read = (name) => JSON.parse(readFileSync(new URL(`../tests/contracts/evolution/${name}.json`, import.meta.url), "utf8"));
const appeal = read("appeal");
const before = JSON.stringify(appeal);
assert.deepEqual(promoteLegacyAppeal(appeal.record, appeal.options), appeal.expected);
assert.equal(JSON.stringify(appeal), before);
const changed = promoteLegacyAppeal(appeal.record, appeal.options);
changed.auditum.appeal.legacy_source.payload.unexpected.push("changed");
assert.equal(JSON.stringify(appeal), before);
assert.equal(appeal.expected.auditum.appeal.status, "unreviewed", "legacy status must not become authority");
assert.throws(() => promoteLegacyAppeal(appeal.record, { ...appeal.options, akousma_id: appeal.record.akousma_id }));
assert.throws(() => promoteLegacyAppeal(appeal.record, { ...appeal.options, supported_contracts: [] }));
assert.equal(legacyValid(appeal.record), true);
assert.equal(legacyValid(appeal.expected), false, "legacy schema rejects auditum/v3");
assert.deepEqual(akousmaShapeErrors(appeal.expected), []);
for (const name of ["research", "decision", "report"]) {
  const record = read(name);
  assert.deepEqual(nextRecordErrors(record), []);
  assert.deepEqual(nextRecordReferenceErrors(record, read("scope")), []);
  assert.deepEqual(JSON.parse(JSON.stringify(record)), record);
  assert.equal(legacyValid(record), false);
}
for (const item of read("cases")) {
  const record = read(item.base);
  let target = record;
  for (const key of item.path.slice(0, -1)) target = target[key];
  target[item.path.at(-1)] = item.value;
  assert.equal(nextRecordErrors(record).length === 0, item.valid, item.name);
}
const decision = read("decision");
assert.notDeepEqual(nextRecordReferenceErrors(decision, []), []);
const scope = read("scope");
scope[2].auditum.listenings[0].created_at = "2026-09-06T09:00:00Z";
assert.notDeepEqual(nextRecordReferenceErrors(decision, scope), []);
assert.notDeepEqual(nextRecordReferenceErrors(decision, [...read("scope"), read("scope")[0]]), []);
console.log("record evolution: negotiated appeal parity, legacy rejection, typed relation/research/decision fixtures and scoped chronology passed");
assert.deepEqual(nextRecordReferenceErrors(appeal.expected, [appeal.record]), []);
const forged = structuredClone(appeal.expected);
forged.auditum.appeal.legacy_source.payload.unexpected[1] = false;
assert.notDeepEqual(nextRecordReferenceErrors(forged, [appeal.record]), []);
const resolved = structuredClone(appeal.expected);
resolved.auditum.appeal.status = "resolved";
assert.notDeepEqual(nextRecordErrors(resolved), []);
assert.notDeepEqual(nextRecordReferenceErrors(decision, [{ akousma_id: "ak_generation" }]), []);
assert.throws(() => promoteLegacyAppeal(appeal.record, { ...appeal.options, created_at: "2020-01-01T00:00:00Z" }));
for (const outcome of ["keep", "discard", "revise", "variation"]) {
  const proposal = read("decision");
  const payload = proposal.extensions.earworm_generation_decision;
  payload.outcome = outcome;
  if (["keep", "discard"].includes(outcome)) {
    payload.next_job = { status: "none", reason: "No next job proposed." };
    payload.stop_outcome = "stop";
  }
  assert.deepEqual(nextRecordErrors(proposal), []);
}
