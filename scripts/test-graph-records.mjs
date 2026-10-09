import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createGraphRecord, reviseGraphRecord, graphRevisionErrors, nextRecordErrors, nextRecordReferenceErrors, transpositionRecipeErrors, createTransformationGraph } from '../packages/sdk-js/src/index.js';
const read = path => JSON.parse(readFileSync(new URL('../'+path,import.meta.url)));
const f = read('tests/contracts/graphs/processing.json'), g = read('tests/contracts/graphs/records.json');
const adapter = { validateMasa: () => [], lineageDirections: f.lineage_directions }; // Unit boundary stub.
const before = structuredClone(g);
assert.deepEqual(createGraphRecord(f.expected,g.options,adapter),g.record);
assert.deepEqual(reviseGraphRecord(g.record,g.revisionOptions,adapter),g.revised);
assert.deepEqual(nextRecordErrors(g.record),[]);
assert.deepEqual(nextRecordReferenceErrors(g.revised,[g.record]),[]);
assert(nextRecordReferenceErrors(g.revised,[]).length);
for (const mutate of [r=>r.extensions.earworm_transformation_graph.revision=4,
 r=>r.extensions.earworm_transformation_graph.source_record.title='rewritten',
 r=>r.created_at='2020-01-01T00:00:00Z', r=>r.extensions.earworm_transformation_graph.graph_id='other']) {
 const record=structuredClone(g.revised);mutate(record);assert(graphRevisionErrors(record,g.record).length);
}
assert.throws(()=>createGraphRecord(f.expected,{...g.options,supported_contracts:[]},adapter));
assert.throws(()=>reviseGraphRecord(g.record,{...g.revisionOptions,akousma_id:g.record.akousma_id},adapter));
const noGraph=structuredClone(g.revised);delete noGraph.extensions.earworm_transformation_graph;noGraph.record_kind='other';assert(nextRecordErrors(noGraph).length);
const leaked=structuredClone(g.revised);leaked.record_kind='research_proposal';assert(nextRecordErrors(leaked).length);
assert.deepEqual(g,before);
const sources=read('tests/contracts/recipes/sources.json'),cases=read('tests/contracts/recipes/cases.json');
for (const row of sources) {
 assert.deepEqual(transpositionRecipeErrors(row.source),[],row.kind);
 assert.equal(createTransformationGraph(row.source,row.options,adapter).source_record.history.events[0].operationType,row.source.history.events[0].operationType);
}
for (const row of cases) {
 const source=structuredClone(sources[row.base].source);let target=source;
 for(const key of row.path.slice(0,-1))target=target[key];target[row.path.at(-1)]=row.value;
 assert(transpositionRecipeErrors(source).length,row.name);
 assert.throws(()=>createTransformationGraph(source,sources[row.base].options,adapter),undefined,row.name);
}
const changedPitch=structuredClone(sources[3].source);
changedPitch.representations[1].audio.durationSeconds.value=.75;
changedPitch.history.events[0].extensions['earworm:transposition'].duration_behavior='changed';
assert.deepEqual(transpositionRecipeErrors(changedPitch),[]);
console.log(`graph persistence contracts: source-preserving revision parity and ${cases.length} shared recipe negatives passed`);
for (const row of sources) assert.throws(() => createTransformationGraph(row.source, { ...row.options, supported_contracts: ['earworm/transformation-graph/v1','masa/0.2.0'] }, adapter));
const unsafeRevision=structuredClone(f.expected);unsafeRevision.revision=9007199254740992;
assert.throws(()=>createGraphRecord(unsafeRevision,g.options,adapter));
