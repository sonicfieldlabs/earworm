import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createTransformationGraph, transformationGraphErrors } from '../packages/sdk-js/src/index.js';
const read = name => JSON.parse(readFileSync(new URL(`../tests/contracts/graphs/${name}.json`, import.meta.url)));
const f = read('processing'), before = structuredClone(f);
// Unit boundary stub only. The installed integration smoke uses MASA's real validator and registry.
const adapter = { validateMasa: () => [], lineageDirections: f.lineage_directions };
assert.deepEqual(createTransformationGraph(f.source, f.options, adapter), f.expected);
assert.deepEqual(transformationGraphErrors(f.expected, adapter), []);
const graph = createTransformationGraph(f.source, f.options, adapter);
graph.source_record.extensions['example:roundtrip'].deep.values.push('changed');
assert.deepEqual(f, before);
for (const row of read('cases')) {
  const value = structuredClone(f.expected); let target = value;
  for (const key of row.path.slice(0, -1)) target = target[key];
  target[row.path.at(-1)] = row.value;
  assert(transformationGraphErrors(value, adapter).length > 0, row.name);
}
const inverse = structuredClone(f.source), r = inverse.relations[0];
[r.subject, r.object] = [r.object, r.subject]; r.predicate = 'masa:derivation-of';
assert.deepEqual(createTransformationGraph(inverse, f.options, adapter).edges, f.expected.edges);
const refused = structuredClone(f.source);
refused.history.events[0].finalStatus = 'refused'; refused.history.events[0].outputs = []; refused.relations = [];
assert.deepEqual(createTransformationGraph(refused, f.options, adapter).edges, []);
assert.equal(createTransformationGraph(refused, f.options, adapter).operation_refs.length, 1);
assert.throws(() => createTransformationGraph(f.source, { ...f.options, supported_contracts: [] }, adapter));
assert.throws(() => createTransformationGraph(f.source, f.options, { ...adapter, validateMasa: () => ['invalid policy'] }), /invalid policy/);
assert.throws(() => transformationGraphErrors(f.expected, { ...adapter, validateMasa: () => false }), TypeError);
const mutationAdapter = { ...adapter, validateMasa: record => { record.title = 'changed'; return []; } };
assert.deepEqual(createTransformationGraph(f.source, f.options, mutationAdapter), f.expected);
console.log(`transformation graphs: ${read('cases').length} shared mutation vectors, direction, refusal and source retention passed`);
