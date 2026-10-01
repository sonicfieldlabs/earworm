import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  listeningContextErrors, claimValidityAt, claimRetentionAt, akousmaShapeErrors,
  LISTENING_CONTEXT_CONTRACT, assertSupportedContracts
} from "../packages/sdk-js/src/index.js";
const read = (path) => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const record = read("tests/fixtures/human-context.akousma.json");
const context = record.extensions.earworm_listening_context;
const before = JSON.stringify(record);
assert.deepEqual(akousmaShapeErrors(record), []);
assert.deepEqual(listeningContextErrors(context, record), []);
for (const item of read("tests/contracts/context-cases.json")) {
  const changed = structuredClone(context);
  let target = changed;
  for (const key of item.path.slice(0, -1)) target = target[key];
  target[item.path.at(-1)] = item.value;
  assert.equal(listeningContextErrors(changed, record).length === 0, item.valid, item.name);
}
const claim = context.claims[0];
for (const [time, status] of [
  ["2026-09-06T11:59:59.999Z", "not_yet_valid"],
  ["2026-09-06T12:00:00Z", "current"],
  ["2026-09-06T12:59:59.999Z", "current"],
  ["2026-09-06T13:00:00Z", "expired"]
]) assert.equal(claimValidityAt(claim, time), status);
assert.equal(claimRetentionAt(claim, "2026-09-06T13:00:00Z"), "review_not_due");
assert.equal(claimRetentionAt(claim, "2026-09-08T13:00:00Z"), "review_due");
assert.throws(() => claimValidityAt(claim, "2026-02-30T00:00:00Z"));
assert.throws(() => claimValidityAt(claim, "0000-01-01T00:00:00Z"));
const unknown = structuredClone(claim);
unknown.validity = { status: "unknown", reason: "Not assessed." };
unknown.retention = { status: "unknown", reason: "Needs policy." };
assert.equal(claimValidityAt(unknown, "2026-09-06T13:00:00Z"), "unknown");
assert.equal(claimRetentionAt(unknown, "2026-09-06T13:00:00Z"), "policy_required");
assert.throws(() => assertSupportedContracts([LISTENING_CONTEXT_CONTRACT], []));
assert.equal(JSON.stringify(record), before, "assessment cannot rewrite records or action authority");
assert.deepEqual(JSON.parse(JSON.stringify(record)), record);
const malformed = structuredClone(record);
malformed.auditum.listenings = [null];
assert.notDeepEqual(listeningContextErrors(context, malformed), []);
console.log("listening context: shared cases, references, distinct renderings, expiry boundaries, retention separation and preservation passed");
const rendered = structuredClone(context);
rendered.contexts[0].renderings = read("tests/contracts/context-cases.json").find((item) => item.name === "interpretation has its own author and output").value;
rendered.contexts[0].report.human_rendering = { status: "available", rendering_refs: ["rendering:text"] };
assert.deepEqual(listeningContextErrors(rendered, record), []);
const noExpiry = structuredClone(claim);
noExpiry.validity = { status: "no_expiry", issued_at: "2026-09-06T12:00:00Z", reason: "Declared policy." };
assert.equal(claimValidityAt(noExpiry, "2026-09-09T12:00:00Z"), "current");
const pluralRecord = structuredClone(record);
const plural = pluralRecord.extensions.earworm_listening_context;
const secondListening = { ...pluralRecord.auditum.listenings[0], listening_id: "listening:second", listener_id: "agent:second", listener_type: "agent" };
pluralRecord.auditum.listenings.push(secondListening);
const secondAccess = structuredClone(record.extensions.earworm_listening_access);
secondAccess.declaration_id = "access:second";
secondAccess.subject_ref = "record:another-subject";
plural.access_declarations = [secondAccess];
const secondContext = structuredClone(plural.contexts[0]);
secondContext.listening_ref = secondListening.listening_id;
secondContext.subject_ref = secondAccess.subject_ref;
secondContext.access_declaration_ref = secondAccess.declaration_id;
plural.contexts.push(secondContext);
assert.deepEqual(listeningContextErrors(plural, pluralRecord), []);
plural.access_declarations.push(secondAccess);
assert.notDeepEqual(listeningContextErrors(plural, pluralRecord), [], "apparatus identities cannot be ambiguous");
