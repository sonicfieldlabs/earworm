import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createObservationAccount,observationAccountErrors,nextRecordErrors,matterContextErrors} from '../packages/sdk-js/src/index.js';
const read=name=>JSON.parse(readFileSync(new URL(`../tests/contracts/observations/${name}.json`,import.meta.url)));
const fixture=read('account');
const before=structuredClone(fixture);
assert.deepEqual(createObservationAccount(fixture.mapping,fixture.options,()=>[]),fixture.expected);
assert.deepEqual(fixture,before);
assert.deepEqual(observationAccountErrors(fixture.expected,()=>[]),[]);
assert.deepEqual(observationAccountErrors(fixture.expected,()=>['Invalid foreign source']),['Invalid foreign source']);
assert.throws(()=>createObservationAccount(fixture.mapping,{...fixture.options,supported_contracts:[]},()=>[]));
assert.throws(()=>createObservationAccount(fixture.mapping,fixture.options,()=>true));
assert.throws(()=>createObservationAccount(fixture.mapping,{...fixture.options,akousma_id:fixture.mapping.report.report_id},()=>[]));
const record=createObservationAccount(fixture.mapping,fixture.options,()=>[]);
record.listening['akouo.observation'].payload.source_snapshot.extensions['example:clone']='changed';
assert.deepEqual(fixture,before);
for(const row of read('cases')) {
  const record=structuredClone(fixture.expected);let target=record;
  for(const key of row.path.slice(0,-1)) target=target[key];
  target[row.path.at(-1)]=row.value;
  assert.equal(nextRecordErrors(record).length===0,row.valid,row.name);
}
const context=structuredClone(fixture.expected.extensions.earworm_matter_context);
const source=fixture.mapping.source_snapshot,access=fixture.options.access;
context.temporal_scope={status:'known',domain:'mathematical_construction',window_s:{start:0,end:1},resolution_s:1/96000,sample_rate_hz:{status:'known',value:48000},evidence_refs:['method:numerical-fixture']};
assert.deepEqual(matterContextErrors(context,source,access),[]);
for(const domain of ['physical_observation','sampled_representation']) {
  context.temporal_scope.domain=domain;
  assert.notDeepEqual(matterContextErrors(context,source,access),[]);
}
context.temporal_scope.domain='mathematical_construction';
for(const value of [0,-1,NaN,Infinity]) {
  context.temporal_scope.resolution_s=value;
  assert.notDeepEqual(matterContextErrors(context,source,access),[]);
}
context.temporal_scope.resolution_s=0.01; context.temporal_scope.window_s.end=0;
assert.notDeepEqual(matterContextErrors(context,source,access),[]);
console.log(`Observation accounts: constructor parity, ${read('cases').length} shared cases, source isolation, foreign validation and numerical/physical boundaries passed.`);
