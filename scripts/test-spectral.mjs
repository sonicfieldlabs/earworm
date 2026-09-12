import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {spectralBundleErrors,record18Errors,admitRecord18} from '../packages/sdk-js/src/spectral.js';
import {nextRecordErrors} from '../packages/sdk-js/src/record-evolution.js';
const fixture=async p=>JSON.parse(await readFile(new URL('../tests/contracts/'+p,import.meta.url),'utf8'));
const bundle=await fixture('spectral/bundle.json');
assert.deepEqual(spectralBundleErrors(bundle),[]);
for(const mutate of [v=>v.views.push(structuredClone(v.views[0])),v=>v.views[0].expanded_bytes++,v=>v.views[0].sha256='b'.repeat(64),v=>v.views[0].state='omitted',v=>v.views[0].axis_units=[]]){
 const bad=structuredClone(bundle);mutate(bad);assert.ok(spectralBundleErrors(bad).length);
}
const record=await fixture('evolution/research.json');record.schema_version='1.8.0';
record.extensions['unknown.example']={preserved:[1,2,3]};
assert.deepEqual(record18Errors(record),[]);
assert.throws(()=>admitRecord18(record,{supportedVersions:['1.7.0']}));
assert.deepEqual(admitRecord18(record,{supportedVersions:['1.8.0']}),record);
record.extensions['akouo.agent-native']={contract:'akouo/agent-native-evidence/v1'};
assert.ok(record18Errors(record).length);
assert.deepEqual(record18Errors(record,{validateNative:()=>[]}),[]);
assert.ok(record18Errors(record,{validateNative:()=>['unresolved']}).length);

const scenarios=await fixture('spectral/scenarios.json');
for(const scenario of scenarios){
 const candidate=await fixture('evolution/research.json');candidate.schema_version=scenario.schema_version;
 if(scenario.extension==='agent_native')candidate.extensions['akouo.agent-native']={contract:'akouo/agent-native-evidence/v1'};
 if(scenario.extension==='spectral'){
  const spectral=structuredClone(bundle);spectral.record_ref=candidate.akousma_id;candidate.extensions['oida.spectral']=spectral;
 }
 const before=structuredClone(candidate);
 if(scenario.expected==='accepted')assert.deepEqual(nextRecordErrors(candidate),[]);
 if(scenario.expected==='refused')assert.throws(()=>admitRecord18(candidate,{supportedVersions:scenario.supported_versions}));
 if(scenario.expected==='host_validation_required'){
  assert.throws(()=>admitRecord18(candidate,{supportedVersions:scenario.supported_versions}));
  assert.deepEqual(admitRecord18(candidate,{supportedVersions:scenario.supported_versions,validateNative:()=>[]}),candidate);
 }
 if(scenario.expected==='host_resolution_required'){
  assert.throws(()=>admitRecord18(candidate,{supportedVersions:scenario.supported_versions}));
  const spectral=candidate.extensions['oida.spectral'];
  assert.deepEqual(admitRecord18(candidate,{supportedVersions:scenario.supported_versions,
   resolveObject:()=>spectral.views[0],resolveRepresentation:()=>spectral}),candidate);
 }
 assert.deepEqual(candidate,before,`${scenario.name} mutated its input`);
}
console.log('Spec 1.8: version refusal, opaque retention, spectral negatives and host validation pass');
