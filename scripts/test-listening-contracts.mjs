import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  LISTENING_ACCESS_CONTRACT, listeningAccessErrors, adaptListeningPasses,
  assertSupportedContracts, createAkousma, akousmaShapeErrors
} from "../packages/sdk-js/src/index.js";

const read = (name) => JSON.parse(readFileSync(new URL(`../tests/contracts/${name}`, import.meta.url), "utf8"));
const cases = read("access-cases.json");
for (const item of cases) assert.equal(listeningAccessErrors(item.value).length === 0, item.valid, item.name);
const { input, expected } = read("pass-adapter.json");
const original = JSON.stringify(input);
const adapted = adaptListeningPasses(input);
assert.deepEqual(adapted, expected);
assert.equal(JSON.stringify(input), original);
adapted.source.passes[0].route.push("changed");
adapted.listenings[0].route.push("changed");
assert.equal(JSON.stringify(input), original, "outputs must not alias retained source");
for (const item of read("invalid-adapters.json")) assert.throws(() => adaptListeningPasses(item.input), undefined, item.name);
for (const type of ["human", "agent", "hybrid", "community", "institution", "sensor", "habitat", "other_animal", "ensemble", "other"]) {
  const variant = structuredClone(input);
  variant.participants[0].type = type;
  assert.equal(adaptListeningPasses(variant).listenings[0].listener_type, type);
}
const access = cases[0].value;
assertSupportedContracts([LISTENING_ACCESS_CONTRACT], [LISTENING_ACCESS_CONTRACT]);
assert.throws(() => assertSupportedContracts([LISTENING_ACCESS_CONTRACT], []), /Unsupported/);
assert.throws(() => assertSupportedContracts("contract", []), /array/);
const record = createAkousma({ audio: { asset_id: "asset:synthetic-01" }, originatingApp: "fixture", extensions: {
  earworm_listening_access: access, opaque_future: { unknown: ["preserve", 0, null] }
} });
assert.deepEqual(akousmaShapeErrors(record), []);
const restored = JSON.parse(JSON.stringify(record));
assert.deepEqual(restored, record);
assert.deepEqual(listeningAccessErrors(restored.extensions.earworm_listening_access), []);
assert.throws(() => assertSupportedContracts(["future/contract/v9"], [LISTENING_ACCESS_CONTRACT]), /Unsupported/);
assert.equal(readFileSync(new URL("../packages/core/schemas/listening-access.schema.json", import.meta.url), "utf8"),
  readFileSync(new URL("../packages/py-akousma/akousma/listening-access.schema.json", import.meta.url), "utf8"));
console.log(`listening contracts: ${cases.length} shared access cases, adapter parity and rejection cases, taxonomy, negotiation, source preservation`);
for (const number of [NaN, Infinity]) {
  const invalid = structuredClone(access);
  invalid.model_input.sample_rate_hz = number;
  assert.notDeepEqual(listeningAccessErrors(invalid), []);
}
