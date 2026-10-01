/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */
import schema from '@earworm/core/schemas/record-evolution.schema.json' with {type:'json'};
import {compileContractSchema,schemaErrors,assertSupportedContracts} from './listening-contracts.js';
import {listeningContextErrors} from './listening-context.js';
import {nextRecordErrors} from './record-evolution.js';
export const MEASUREMENT_SET_CONTRACT='earworm/measurement-set/v1';
export const AGENT_SECTOR_CONTRACT='earworm/agent-sector/v1';
const setSchema=compileContractSchema(schema.$defs.measurementSet);
const sectorSchema=compileContractSchema(schema.$defs.agentSector);
const object=v=>v!==null && typeof v==='object' && !Array.isArray(v);
const scalar=v=>typeof v==='number' && Number.isFinite(v);
const finite=v=>typeof v==='number'?Number.isFinite(v):v&&typeof v==='object'?Object.values(v).every(finite):true;
function stable(v) {
  if(Array.isArray(v))return `[${v.map(stable).join(',')}]`;
  if(object(v))return `{${Object.keys(v).sort().map(k=>`${JSON.stringify(k)}:${stable(v[k])}`).join(',')}}`;
  return JSON.stringify(v);
}
const same=(a,b)=>stable(a)===stable(b);
const units={spectral_centroid:{Hz:'frequency'},band_energy:{'sample^2':'digital_energy','sample^2*s':'digital_energy'},level:{dBFS:'digital_full_scale',LUFS:'perceptual_loudness',dB_SPL:'sound_pressure'},duration:{s:'time'}};
function resolve(set,id) {
  const descriptor=set.descriptors.find(d=>d.descriptor_id===id);
  if(!descriptor)throw new Error(`Unresolved measurement descriptor: ${id}`);
  const source=set.sources.find(s=>s.record_ref===descriptor.source_record_ref)?.record;
  const measurement=source?.measurements?.find(m=>m.id===descriptor.measurement_ref);
  if(!measurement)throw new Error(`Unresolved MASA measurement: ${descriptor.measurement_ref}`);
  return {descriptor,source,measurement};
}
export function measurementSetBindingErrors(value) {
  if(!finite(value))return ['Measurements require finite JSON numbers'];
  const errors=schemaErrors(setSchema,value);
  if(errors.length)return errors;
  const sourceIds=new Set(),descriptorIds=new Set();
  for(const source of value.sources) {
    if(sourceIds.has(source.record_ref))errors.push('Duplicate MASA source identity');
    sourceIds.add(source.record_ref);
    const raw=source.record;
    if(raw.id!==source.record_ref || raw.masaVersion!=='0.2.0' || !Array.isArray(raw.measurements) || !Array.isArray(raw.representations))errors.push('Invalid retained MASA source binding');
    else if(raw.measurements.some(m=>!object(m)||typeof m.id!=='string') || new Set(raw.measurements.map(m=>m.id)).size!==raw.measurements.length)errors.push('Malformed or duplicate MASA measurements');
  }
  if(errors.length)return errors;
  for(const descriptor of value.descriptors) {
    if(descriptorIds.has(descriptor.descriptor_id))errors.push('Duplicate descriptor identity');
    descriptorIds.add(descriptor.descriptor_id);
    let selected;try{selected=resolve(value,descriptor.descriptor_id);}catch(e){errors.push(e.message);continue;}
    const {source,measurement:m}=selected;
    if(m.type!=='masa:Measurement'||typeof m.metric!=='string'||!m.metric.trim()||!scalar(m.value)||units[descriptor.feature][m.unit]!==descriptor.reference_basis)errors.push('Unsupported measurement scalar/unit/reference basis');
    if(descriptor.feature!=='level' && (!scalar(m.value)||m.value<0))errors.push('Duration, energy and centroid must be nonnegative');
    const w=m.window;
    if(!object(w)||w.kind!=='temporal'||w.unit!=='s'||!scalar(w.start)||!scalar(w.end)||w.start<0||w.start>=w.end)errors.push('Measurement requires an increasing temporal window in seconds');
    if(!source.representations.some(r=>object(r)&&r.id===m.about))errors.push('Measurement representation is unresolved');
    if(!object(m.method)||typeof m.method.name!=='string'||!object(m.method.version)||!object(m.method.parameters))errors.push('Measurement method must remain attributable');
    const band=descriptor.band_hz;
    if(band.status==='known' && band.lower>=band.upper)errors.push('Descriptor band must increase');
    if(['spectral_centroid','band_energy'].includes(descriptor.feature) && band.status!=='known')errors.push('Spectral descriptor requires an explicit band');
    if(descriptor.feature==='spectral_centroid' && band.status==='known' && (m.value<band.lower || m.value>band.upper))errors.push('Centroid falls outside its declared analysis band');
    if(descriptor.reference_basis==='sound_pressure') {
      const method=m.method;
      if(!Array.isArray(method?.apparatusRefs)||!method.apparatusRefs.length||typeof method.parameters?.calibration_ref!=='string'||!method.parameters.calibration_ref.trim()||!scalar(method.parameters.reference_pressure_pa)||method.parameters.reference_pressure_pa<=0)errors.push('Physical SPL requires declared apparatus, calibration and pressure reference');
    }
  }
  return errors;
}
export function measurementSetErrors(value,validateMasa) {
  const errors=measurementSetBindingErrors(value);
  if(errors.length)return errors;
  if(typeof validateMasa!=='function')throw new TypeError('The negotiated MASA validator is required');
  for(const source of value.sources) {
    const result=validateMasa(source.record);
    if(!Array.isArray(result)||result.some(e=>typeof e!=='string'))throw new TypeError('MASA validator must return error strings');
    errors.push(...result);
  }
  return errors;
}
export function createMeasurementSet(sources,descriptors,validateMasa,supportedContracts) {
  assertSupportedContracts([MEASUREMENT_SET_CONTRACT,'masa/0.2.0'],supportedContracts);
  const value={contract:MEASUREMENT_SET_CONTRACT,sources:sources.map(record=>({record_ref:record.id,record:structuredClone(record)})),descriptors:structuredClone(descriptors)};
  const errors=measurementSetErrors(value,validateMasa);if(errors.length)throw new Error(errors.join('; '));return value;
}
export function agentSectorBindingErrors(record) {
  const extensions=record.extensions??{},set=extensions.earworm_measurements,sector=extensions.earworm_agent_sector;
  const errors=set===undefined?[]:measurementSetBindingErrors(set);
  if(!sector)return errors;
  errors.push(...schemaErrors(sectorSchema,sector));
  if(errors.length)return errors;
  const context=extensions.earworm_listening_context;
  errors.push(...listeningContextErrors(context,record));
  if(errors.length)return errors;
  const ids=new Set(),accesses=[...(extensions.earworm_listening_access?[extensions.earworm_listening_access]:[]),...(context.access_declarations??[])];
  for(const entry of sector.entries) {
    if(ids.has(entry.sector_id))errors.push('Duplicate sector identity');ids.add(entry.sector_id);
    const listening=record.auditum.listenings.find(l=>l.listening_id===entry.listening_ref);
    const ctx=context.contexts.find(c=>c.listening_ref===entry.listening_ref);
    if(!ctx || !listening || !['agent','sensor','hybrid'].includes(listening.listener_type)){errors.push('Sector requires an attributable agent/sensor/hybrid listening');continue;}
    const access=accesses.find(a=>a.declaration_id===entry.access_declaration_ref);
    if(!access||ctx.access_declaration_ref!==entry.access_declaration_ref||ctx.subject_ref!==entry.subject_ref){errors.push('Sector subject/access binding mismatch');continue;}
    const claims=new Set(context.claims.filter(c=>c.listening_ref===entry.listening_ref).map(c=>c.claim_ref));
    if(entry.claim_refs.some(ref=>!claims.has(ref)))errors.push('Sector claim belongs to a missing or different listening');
    const allowedSources=new Set([entry.subject_ref,ctx.report.ref]);
    if(entry.basis==='retained_measurement' && !entry.measurement_refs.length)errors.push('Retained measurement sector requires descriptors');
    if(entry.basis!=='retained_measurement' && entry.measurement_refs.length)errors.push('Measurement references require retained_measurement basis');
    for(const ref of entry.measurement_refs) {
      let selected;try{selected=resolve(set??{descriptors:[]},ref);}catch(e){errors.push(e.message);continue;}
      const {descriptor,measurement:m}=selected;allowedSources.add(m.id);allowedSources.add(m.about);
      if(entry.source_kind!=='acoustic_signal')errors.push('Scalar audio descriptors belong to acoustic signal sectors');
      const model=access.model_input;
      if(model.status!=='known'||model.representation_ref!==m.about)errors.push('Acoustic sector measurement must resolve to the effective input');
      else {
        if(m.window.start<model.window_s.start||m.window.end>model.window_s.end)errors.push('Measurement window exceeds the effective input');
        if(descriptor.band_hz.status==='known' && (descriptor.band_hz.lower<model.effective_band_hz.lower||descriptor.band_hz.upper>model.effective_band_hz.upper))errors.push('Descriptor band exceeds the effective input');
      }
    }
    if(entry.source_kind==='non_acoustic_observation'||entry.basis==='retained_observation') {
      const binding=extensions.earworm_observation,modality=extensions.earworm_matter_context?.source_modality;
      if(entry.source_kind!=='non_acoustic_observation'||entry.basis!=='retained_observation'||binding?.listening_ref!==entry.listening_ref||binding?.observation_ref!==entry.subject_ref||modality?.status!=='known'||modality.value!=='non_acoustic')errors.push('Non-acoustic sector requires its explicit observation binding');
    }
    if(extensions.earworm_observation?.listening_ref===entry.listening_ref && entry.source_kind==='acoustic_signal')errors.push('Structured observation cannot become an acoustic signal sector');
    for(const ref of entry.renderings) {
      const rendering=ctx.renderings.find(r=>r.rendering_id===ref);
      if(!rendering)errors.push('Sector rendering must resolve within its own listening');
      else if(!allowedSources.has(rendering.source_ref))errors.push('Sector rendering source is unrelated to its evidence');
    }
  }
  return errors;
}
export function agentSectorView(record,sectorId) {
  const errors=nextRecordErrors(record);if(errors.length)throw new Error(errors.join('; '));
  const entry=record.extensions?.earworm_agent_sector?.entries.find(e=>e.sector_id===sectorId);
  if(!entry)throw new Error('Unknown sector');
  const context=record.extensions.earworm_listening_context;
  const ctx=context.contexts.find(c=>c.listening_ref===entry.listening_ref);
  const access=[record.extensions.earworm_listening_access,...(context.access_declarations??[])].find(a=>a?.declaration_id===entry.access_declaration_ref);
  return structuredClone({entry,access,renderings:ctx.renderings.filter(r=>entry.renderings.includes(r.rendering_id)),measurements:entry.measurement_refs.map(ref=>{const {descriptor,measurement}=resolve(record.extensions.earworm_measurements,ref);return {descriptor,measurement};})});
}
function comparison(source,target,options) {
  if(source.akousma_id===target.akousma_id)throw new Error('Similarity requires two distinct records');
  const left=resolve(source.extensions?.earworm_measurements??{descriptors:[]},options.source_descriptor_ref),right=resolve(target.extensions?.earworm_measurements??{descriptors:[]},options.target_descriptor_ref);
  for(const key of ['feature','reference_basis','band_hz'])if(!same(left.descriptor[key],right.descriptor[key]))throw new Error(`Incompatible descriptor ${key}`);
  const l=left.measurement,r=right.measurement;
  if(l.unit!==r.unit||l.metric!==r.metric||!same(l.window,r.window)||l.method.name!==r.method.name||l.method.version.state!=='known'||typeof l.method.version.value!=='string'||!l.method.version.value.trim()||!same(l.method.version,r.method.version)||!same(l.method.parameters,r.method.parameters))throw new Error('Comparison requires matching metrics, units, windows and versioned methods');
  if(left.source.id===right.source.id&&!same(left.source,right.source)||l.id===r.id&&!same(l,r))throw new Error('Conflicting retained source or measurement identity');
  const distance=Math.abs(l.value-r.value);if(!Number.isFinite(distance))throw new Error('Scalar difference is not finite');
  return {contract:'earworm/relations/v1',relation_id:options.relation_id,type:'similar_by',target_akousma_id:target.akousma_id,declared_by:options.declared_by,evidence_refs:[...new Set([l.id,r.id])],epistemic_status:'inferred',review:{status:'unreviewed'},criterion:{criterion_id:options.criterion_id,feature:left.descriptor.feature,unit:l.unit,method_ref:'earworm:absolute-difference',method_revision:'1',input_refs:[source.akousma_id,target.akousma_id],normalization:'none',score:{status:'known',value:distance,policy:'absolute_difference; lower is closer under this descriptor only'},descriptor_refs:[{record_ref:source.akousma_id,descriptor_ref:options.source_descriptor_ref},{record_ref:target.akousma_id,descriptor_ref:options.target_descriptor_ref}]}};
}
export function compareMeasurementDescriptors(source,target,options) {
  assertSupportedContracts(['earworm/akousma/v1.7',MEASUREMENT_SET_CONTRACT,'earworm/relations/v1'],options.supported_contracts);
  for(const key of ['relation_id','criterion_id','declared_by'])if(typeof options[key]!=='string'||!options[key].trim())throw new TypeError(`Missing comparison option: ${key}`);
  const errors=[...nextRecordErrors(source),...nextRecordErrors(target)];if(errors.length)throw new Error(errors.join('; '));
  return comparison(source,target,options);
}
export function descriptorRelationErrors(record,scope) {
  const errors=[];
  for(const relation of record.lineage.relations??[]) {
    const refs=relation.criterion?.descriptor_refs;if(!refs)continue;
    if(relation.type!=='similar_by'||refs.length!==2||refs[0].record_ref!==record.akousma_id||refs[1].record_ref!==relation.target_akousma_id){errors.push('Descriptor comparison requires ordered source/target record references');continue;}
    const target=scope.get(refs[1].record_ref);if(!target){errors.push('Unresolved descriptor comparison target');continue;}
    try {
      const expected=comparison(record,target,{relation_id:relation.relation_id,criterion_id:relation.criterion.criterion_id,declared_by:relation.declared_by,source_descriptor_ref:refs[0].descriptor_ref,target_descriptor_ref:refs[1].descriptor_ref});
      if(!same(expected.criterion,relation.criterion)||!same(expected.evidence_refs,relation.evidence_refs)||relation.epistemic_status!=='inferred')errors.push('Descriptor comparison differs from its retained inputs');
    }catch(e){errors.push(e.message);}
  }
  return errors;
}
