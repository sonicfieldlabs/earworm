import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { representationRecordErrors, representationErrors, admitRepresentationRecord, REPRESENTATION_CONTRACTS, record19Errors, akousmaShapeErrors } from "../packages/sdk-js/src/index.js";
import { compileContractSchema } from "../packages/sdk-js/src/listening-contracts.js";
import legacySchema from "../packages/core/schemas/akousma-1.8.schema.json" with { type: "json" };
const read = name => JSON.parse(readFileSync(new URL(`../tests/contracts/representations/${name}.json`, import.meta.url)));
const mutate = entry => {
  const value = read(entry.base);
  if (entry.action === "none") return value;
  let parent = value;
  for (const key of entry.path.slice(0, -1)) parent = parent[key];
  const key = entry.path.at(-1);
  if (entry.action === "delete") Array.isArray(parent) ? parent.splice(key, 1) : delete parent[key];
  else if (entry.action === "append") parent[key].push(entry.value);
  else parent[key] = entry.value;
  return value;
};
for (const entry of read("cases")) {
  assert.equal(representationRecordErrors(mutate(entry)).length === 0, entry.valid, entry.name);
}
for (const name of ["listen", "account", "sound", "work", "partial", "read-file", "no-response", "refused"]) {
  const input = read(name), before = JSON.stringify(input);
  const result = admitRepresentationRecord(input, { supportedContracts: REPRESENTATION_CONTRACTS });
  assert.deepEqual(result, input);
  result.representations[0].subject_ref = "changed";
  assert.equal(JSON.stringify(input), before, "admission cannot mutate its input");
}
assert.throws(() => admitRepresentationRecord(read("listen"), { supportedContracts: [] }), /Unsupported/);
const external = read("work");
for (const r of external.representations) delete r.artifact.inline_text;
const originals = new Map(read("work").representations.map(r => [r.representation_id, Buffer.from(r.artifact.inline_text)]));
assert.throws(() => admitRepresentationRecord(external, { supportedContracts: REPRESENTATION_CONTRACTS }), /unavailable/);
assert.deepEqual(admitRepresentationRecord(external, {
  supportedContracts: REPRESENTATION_CONTRACTS, resolveArtifact: rep => originals.get(rep.representation_id)
}), external);
assert.throws(() => admitRepresentationRecord(external, {
  supportedContracts: REPRESENTATION_CONTRACTS, resolveArtifact: () => Buffer.from("wrong")
}), /mismatched/);
assert.throws(() => admitRepresentationRecord(read("instruction"), { supportedContracts: REPRESENTATION_CONTRACTS }), /owner/);
assert.deepEqual(admitRepresentationRecord(read("instruction"), {
  supportedContracts: REPRESENTATION_CONTRACTS, validateBinding: () => []
}), read("instruction"));
assert.throws(() => admitRepresentationRecord(read("instruction"), {
  supportedContracts: REPRESENTATION_CONTRACTS, validateBinding: () => ["Revoked by owner"]
}), /Revoked/);
for (const name of ["return", "original-return"]) {
  assert.throws(() => admitRepresentationRecord(read(name), { supportedContracts: REPRESENTATION_CONTRACTS }), /unresolved/);
  assert.deepEqual(admitRepresentationRecord(read(name), {
    supportedContracts: REPRESENTATION_CONTRACTS, resolveOperation: () => read("previous-operation")
  }), read(name));
}
assert.throws(() => admitRepresentationRecord(read("return"), {
  supportedContracts: REPRESENTATION_CONTRACTS, resolveOperation: () => ({ ...read("previous-operation"), output_representation_refs: [] })
}), /previous output/);
const record = read("record-19");
const contextual = read("return");
const earlier = read("account").representations[1];
const excerpt = structuredClone(earlier);
excerpt.representation_id = "fixture:context-excerpt";
excerpt.artifact.inline_text = earlier.artifact.inline_text.slice(0, 6);
const excerptBytes = Buffer.from(excerpt.artifact.inline_text, "utf-8");
excerpt.artifact.ref = "fixture:context-excerpt";
excerpt.artifact.sha256 = createHash("sha256").update(excerptBytes).digest("hex");
excerpt.artifact.byte_count = excerptBytes.length;
excerpt.origin = { kind: "transformed", domain: "non_acoustic", source_refs: [earlier.representation_id] };
excerpt.preservation = { layout: "transformed", losses: ["Remaining account omitted."] };
contextual.representations.push(earlier, excerpt);
contextual.relations.push({ relation_id: "fixture:context-transform", kind: "transformed_from", from_ref: excerpt.representation_id,
  to_ref: earlier.representation_id, declared_by: "fixture-author", method_ref: "fixture/selection/v1", losses: excerpt.preservation.losses });
contextual.accesses.push({ contract: "earworm/representation-access/v1", access_id: "fixture:context-access", operation_ref: contextual.operation_ref,
  representation_ref: earlier.representation_id, received_representation_ref: excerpt.representation_id, role: "context", status: "available",
  coverage: { kind: "partial", unit: "byte", ranges: [{ start: 0, end: excerpt.artifact.byte_count }], omissions: ["Remaining account omitted."] } });
assert.deepEqual(representationRecordErrors(contextual), []);
assert.throws(() => admitRepresentationRecord(contextual, {
  supportedContracts: REPRESENTATION_CONTRACTS, resolveOperation: () => read("previous-operation")
}), /prior account/, "an excerpt cannot conceal supplied prior-account context");
assert.deepEqual(record19Errors(record), []);
assert.deepEqual(akousmaShapeErrors(record), []);
const validate18 = compileContractSchema(legacySchema);
assert.equal(validate18(record), false, "1.9 is never silently a 1.8 record");
const stale = structuredClone(record); stale.extensions.earworm_representation.record_ref = "other";
assert.notDeepEqual(record19Errors(stale), []);
const pretend = structuredClone(record); pretend.audio = { asset_id: "placeholder" };
assert.notDeepEqual(record19Errors(pretend), []);
const nonfinite = read("listen"); nonfinite.representations[0].artifact.byte_count = NaN;
assert.notDeepEqual(representationRecordErrors(nonfinite), []);
assert.notDeepEqual(representationErrors(null), []);
const audio = read("listen").representations[0];
delete audio.artifact.inline_text; delete audio.encoding;
audio.form = "audio"; audio.media_type = "audio/wav";
audio.origin = { kind: "generated", domain: "non_acoustic", source_refs: [] };
audio.preservation = { layout: "not_applicable", losses: [] };
assert.deepEqual(representationErrors(audio), [], "generated audio is a real representation without an acoustic-origin assertion");
console.log(`representations: ${read("cases").length} shared cases; byte admission, roles, returns, version rejection and immutability passed`);
