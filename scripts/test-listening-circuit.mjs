import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { LISTENING_CIRCUIT_CONTRACT, listeningCircuitErrors, circuitRecordErrors, runMemoryErrors, emptyRunMemory, foldRunMemory, windowsSince } from '../packages/sdk-js/src/index.js';
const read = name => JSON.parse(readFileSync(new URL(`../tests/contracts/circuit/${name}.json`, import.meta.url)));
const fixture = read('circuit');
assert.equal(fixture.circuit.contract, LISTENING_CIRCUIT_CONTRACT);
assert.deepEqual(listeningCircuitErrors(fixture.circuit), []);
assert.deepEqual(listeningCircuitErrors(fixture.circuit, fixture.record), []);
assert.deepEqual(circuitRecordErrors(fixture.record), []);
assert.deepEqual(circuitRecordErrors({ extensions: {} }), []);
assert.notDeepEqual(listeningCircuitErrors(fixture.circuit, { akousma_id: 'x' }), []);
const set = (value, path, next) => { let t = value; for (const k of path.slice(0, -1)) t = t[k]; t[path.at(-1)] = next; };
const cases = read('cases');
for (const row of cases) {
  const circuit = structuredClone(fixture.circuit);
  set(circuit, row.path, row.value);
  for (const extra of row.also ?? []) set(circuit, extra.path, extra.value);
  assert.equal(listeningCircuitErrors(circuit, fixture.record).length === 0, row.valid, row.name);
}
const fold = read('fold');
const before = structuredClone(fixture.circuit);
let memory = emptyRunMemory(fold.session_id, fold.started_at);
for (const input of fold.inputs) {
  const args = { ...input };
  if (args.circuit) args.circuit = fixture.circuit; else delete args.circuit;
  memory = foldRunMemory(memory, args);
}
assert.deepEqual(memory, fold.expected, 'JS fold matches the Python fold');
assert.deepEqual(fixture.circuit, before, 'folding does not change its circuit');
assert.deepEqual(runMemoryErrors(memory), []);
assert.equal(windowsSince(memory, 'locustream_2020'), 1);
assert.equal(windowsSince(memory, 'never-heard'), null);
assert.throws(() => foldRunMemory(emptyRunMemory('ses_other', fold.started_at), { at: '2026-10-30T03:05:00Z', source_key: 'locustream_1010', circuit: fixture.circuit }), /another run/);
assert.throws(() => foldRunMemory(memory, { at: '2026-10-30T03:00:00Z', source_key: 's' }), /time order/);
const bad = structuredClone(memory); bad.sources.locustream_1010.audio = 'raw.wav';
assert.notDeepEqual(runMemoryErrors(bad), []);
console.log(`Listening circuit: ${cases.length} shared cases, record resolution, fold parity with Python, purity and run boundaries passed.`);
