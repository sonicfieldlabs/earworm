import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createMeasurementSet,measurementSetErrors,agentSectorView,compareMeasurementDescriptors,nextRecordErrors,nextRecordReferenceErrors} from '../packages/sdk-js/src/index.js';
const read=name=>JSON.parse(readFileSync(new URL(`../tests/contracts/sectors/${name}.json`,import.meta.url)));
const fixture=read('comparison'),before=structuredClone(fixture);
assert.deepEqual(compareMeasurementDescriptors(fixture.left,fixture.right,fixture.options),fixture.expected);
assert.deepEqual(agentSectorView(fixture.left,'sector:descriptors'),read('view'));
const view=agentSectorView(fixture.left,'sector:descriptors');view.renderings[0].access.value='public';assert.deepEqual(fixture,before);
const set=fixture.left.extensions.earworm_measurements;
assert.deepEqual(createMeasurementSet(set.sources.map(s=>s.record),set.descriptors,()=>[],['earworm/measurement-set/v1','masa/0.2.0']),set);
assert.deepEqual(measurementSetErrors(set,()=>['Invalid MASA source']),['Invalid MASA source']);
assert.throws(()=>measurementSetErrors(set,()=>false));
assert.throws(()=>createMeasurementSet(set.sources.map(s=>s.record),set.descriptors,()=>[],[]));
for(const row of read('cases')) {
 const record=structuredClone(row.base==='observation'?read('observation'):fixture.left);let target=record;
 for(const key of row.path.slice(0,-1))target=target[key];target[row.path.at(-1)]=row.value;
 const errors=row.scope?nextRecordReferenceErrors(record,[fixture.right]):nextRecordErrors(record);
 assert.equal(errors.length===0,row.valid,row.name);
}
for(const feature of ['spectral_centroid','band_energy','level','duration']) {
 const rel=compareMeasurementDescriptors(fixture.left,fixture.right,{...fixture.options,source_descriptor_ref:`descriptor:${feature}`,target_descriptor_ref:`descriptor:${feature}`});
 assert.equal(rel.criterion.score.value,feature==='spectral_centroid'?250:0);
}
for(const change of ['version','window','parameters','metric']) {
 const right=structuredClone(fixture.right),m=right.extensions.earworm_measurements.sources[0].record.measurements[0];
 if(change==='version')m.method.version={state:'unknown',reason:'Missing version'};
 if(change==='window')m.window.end=0.9;
 if(change==='parameters')m.method.parameters={weighting:'other'};
 if(change==='metric')m.metric='different metric';
 assert.throws(()=>compareMeasurementDescriptors(fixture.left,right,fixture.options),change);
}
const unknown=structuredClone(set);unknown.sources[0].record.extensions['fixture:nonfinite']=Infinity;
assert.notDeepEqual(measurementSetErrors(unknown,()=>[]),[]);
assert.deepEqual(fixture,before);
console.log(`Agent sectors: ${read('cases').length} shared vectors, preserved rendering views, four scalar descriptors and recomputed comparison parity passed.`);

const cross=structuredClone(fixture.left),context=cross.extensions.earworm_listening_context;
const other=structuredClone(context.contexts[0]);other.listening_ref='listening:other';other.renderings[0].rendering_id='rendering:other';other.report.human_rendering.rendering_refs=['rendering:other'];context.contexts.push(other);
cross.auditum.listenings.push({...structuredClone(cross.auditum.listenings[0]),listening_id:'listening:other'});
cross.extensions.earworm_agent_sector.entries[0].renderings=['rendering:other'];
assert(nextRecordErrors(cross).some(error=>error.includes('own listening')));
